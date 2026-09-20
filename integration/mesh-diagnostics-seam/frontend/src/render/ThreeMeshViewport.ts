import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import type { MeshDocument } from "../model/types.ts";
import { DiagnosticsLayer } from "./DiagnosticsLayer.ts";
import { ResourceScope } from "./resources.ts";

export const MAX_WIREFRAME_TRIANGLES = 150_000;
export interface ViewOptions { ghost: boolean; wireframe: boolean; xray: boolean; pulse: boolean }
export const DEFAULT_OPTIONS: ViewOptions = { ghost: true, wireframe: true, xray: true, pulse: false };
export interface ViewportStatus { state: "ready" | "context-lost" | "error"; message: string }

/**
 * Owns browser/GPU resources, never Svelte state, Gradio calls, repair, or metrics.
 * setDocument replaces data; setSelection changes presentation without replacing
 * the surface geometry or recomputing normals. Small face overlays are lazy.
 */
export class ThreeMeshViewport {
  private host: HTMLElement;
  private lifetime = new ResourceScope();
  private surfaceScope = new ResourceScope();
  private scene = new THREE.Scene();
  private surfaceGroup = new THREE.Group();
  private camera = new THREE.PerspectiveCamera(45, 1, 0.001, 100);
  private renderer!: THREE.WebGLRenderer;
  private controls!: OrbitControls;
  private diagnostics: DiagnosticsLayer | null = null;
  private geometry: THREE.BufferGeometry | null = null;
  private material: THREE.MeshStandardMaterial | null = null;
  private depthOccluder: THREE.Mesh | null = null;
  private wire: THREE.LineSegments | null = null;
  private doc: MeshDocument | null = null;
  private options = { ...DEFAULT_OPTIONS };
  private selected: string | null = null;
  private frameId: number | null = null;
  private disposed = false;
  private contextLost = false;
  private hasSize = false;
  private pendingFit = false;
  private intersecting = true;
  private reduceMotion = false;
  private onStatus: (status: ViewportStatus) => void;
  geometryBuildCount = 0;

  constructor(host: HTMLElement, onStatus: (status: ViewportStatus) => void = () => {}) {
    this.host = host;
    this.onStatus = onStatus;
    try {
      this.scene.background = new THREE.Color(0xf8fafc);
      this.scene.add(this.surfaceGroup, new THREE.AmbientLight(0xffffff, 0.8));
      const key = new THREE.DirectionalLight(0xffffff, 2.2);
      key.position.set(3, 5, 4);
      const fill = new THREE.DirectionalLight(0xcbd5e1, 0.7);
      fill.position.set(-4, 0, -3);
      this.scene.add(key, fill);
      this.renderer = this.lifetime.own(new THREE.WebGLRenderer({ antialias: true, alpha: false }));
      this.renderer.outputColorSpace = THREE.SRGBColorSpace;
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      const canvas = this.renderer.domElement;
      canvas.style.display = "block";
      canvas.style.width = "100%";
      canvas.style.height = "100%";
      canvas.tabIndex = 0;
      canvas.setAttribute("aria-label", "3D triangle mesh. Drag to orbit; scroll to zoom. Arrow keys pan when focused.");
      host.appendChild(canvas);
      this.lifetime.defer(() => canvas.remove());
      this.controls = this.lifetime.own(new OrbitControls(this.camera, canvas));
      this.controls.enableDamping = true;
      this.controls.dampingFactor = 0.08;
      this.controls.listenToKeyEvents(canvas);
      this.controls.addEventListener("change", this.invalidate);
      this.lifetime.defer(() => this.controls.removeEventListener("change", this.invalidate));
      const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
      const motionChanged = () => {
        this.reduceMotion = motion.matches;
        this.controls.enableDamping = !motion.matches;
        this.invalidate();
      };
      motionChanged();
      motion.addEventListener("change", motionChanged);
      this.lifetime.defer(() => motion.removeEventListener("change", motionChanged));
      const observer = new ResizeObserver(this.resize);
      observer.observe(host);
      this.lifetime.defer(() => observer.disconnect());
      if (typeof IntersectionObserver !== "undefined") {
        const visibility = new IntersectionObserver((entries) => {
          this.intersecting = entries.some((entry) => entry.isIntersecting);
          if (!this.intersecting) this.cancelFrame(); else this.invalidate();
        });
        visibility.observe(host);
        this.lifetime.defer(() => visibility.disconnect());
      }
      const visibilityChanged = () => {
        if (document.hidden) this.cancelFrame(); else this.invalidate();
      };
      document.addEventListener("visibilitychange", visibilityChanged);
      this.lifetime.defer(() => document.removeEventListener("visibilitychange", visibilityChanged));
      const lost = (event: Event) => {
        event.preventDefault();
        this.contextLost = true;
        this.cancelFrame();
        this.onStatus({ state: "context-lost", message: "Graphics context lost. Waiting for the browser to restore it." });
      };
      const restored = () => {
        this.contextLost = false;
        this.resize();
        this.onStatus({ state: "ready", message: "Graphics context restored." });
        this.invalidate();
      };
      canvas.addEventListener("webglcontextlost", lost);
      canvas.addEventListener("webglcontextrestored", restored);
      this.lifetime.defer(() => {
        canvas.removeEventListener("webglcontextlost", lost);
        canvas.removeEventListener("webglcontextrestored", restored);
      });
      this.camera.position.set(3, 2, 3);
      this.resize();
      this.onStatus({ state: "ready", message: "" });
    } catch (error) { this.dispose(); throw error; }
  }
  private canRender(): boolean {
    return !this.disposed && !this.contextLost && this.hasSize && this.intersecting && !document.hidden;
  }
  invalidate = (): void => {
    if (this.frameId === null && this.canRender()) this.frameId = requestAnimationFrame(this.render);
  };
  private cancelFrame(): void {
    if (this.frameId !== null) cancelAnimationFrame(this.frameId);
    this.frameId = null;
  }
  private render = (time: number): void => {
    this.frameId = null;
    if (!this.canRender()) return;
    try {
      const moving = this.controls.update();
      const pulsing = Boolean(this.selected && this.options.pulse && !this.reduceMotion);
      // Optional 1 Hz smooth modulation, not the original aggressive flash.
      this.diagnostics?.setPulse(pulsing ? 0.75 + 0.25 * Math.sin(2 * Math.PI * time / 1000) : 1);
      this.renderer.render(this.scene, this.camera);
      if (moving || pulsing) this.invalidate();
    } catch (error) {
      this.cancelFrame();
      this.onStatus({ state: "error", message: error instanceof Error ? error.message : "Rendering failed" });
    }
  };
  private resize = (): void => {
    if (this.disposed) return;
    const width = this.host.clientWidth, height = this.host.clientHeight;
    this.hasSize = width > 0 && height > 0;
    if (!this.hasSize) { this.cancelFrame(); return; }
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(width, height, false);
    if (this.pendingFit) { this.pendingFit = false; this.fit(); }
    this.invalidate();
  };
  setDocument(next: MeshDocument | null): void {
    if (this.disposed || next === this.doc) return;
    const previous = this.doc;
    const sameGeometry = Boolean(next && previous
      && next.payload.mesh_id === previous.payload.mesh_id
      && next.payload.geometry_revision === previous.payload.geometry_revision);
    if (sameGeometry && next?.payload.diagnostic_revision === previous?.payload.diagnostic_revision) return;
    this.diagnostics?.dispose();
    this.diagnostics = null;
    this.doc = next;
    if (!sameGeometry) {
      this.selected = null;
      this.surfaceGroup.clear();
      this.surfaceScope.dispose();
      this.surfaceScope = new ResourceScope();
      this.geometry = null; this.material = null; this.wire = null; this.depthOccluder = null;
      if (next && next.positions.length) {
        this.geometry = this.surfaceScope.own(new THREE.BufferGeometry());
        this.geometry.setAttribute("position", new THREE.BufferAttribute(next.positions, 3));
        this.geometry.setIndex(new THREE.BufferAttribute(next.triangles, 1));
        this.geometry.computeVertexNormals();
        this.geometry.computeBoundingSphere();
        this.material = this.surfaceScope.own(new THREE.MeshStandardMaterial({
          color: 0x64748b, roughness: 0.4, metalness: 0.1,
          side: THREE.DoubleSide, flatShading: true,
          polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1,
        }));
        this.material.forceSinglePass = true;
        this.surfaceGroup.add(new THREE.Mesh(this.geometry, this.material));
        // When ghosting with X-ray OFF, a depth-only prepass makes "occluded"
        // meaningful even though the visible translucent shell does not write depth.
        const depthMaterial = this.surfaceScope.own(new THREE.MeshBasicMaterial({
          colorWrite: false, depthWrite: true, depthTest: true, side: THREE.DoubleSide,
        }));
        this.depthOccluder = new THREE.Mesh(this.geometry, depthMaterial);
        this.depthOccluder.renderOrder = -10;
        this.depthOccluder.visible = false;
        this.surfaceGroup.add(this.depthOccluder);
        this.geometryBuildCount++;
      }
    }
    if (next) {
      if (this.selected && !next.targets.has(this.selected)) this.selected = null;
      this.diagnostics = new DiagnosticsLayer(next);
      this.scene.add(this.diagnostics.group);
      this.diagnostics.setSelection(this.selected);
    }
    this.applyOptions();
    if (!sameGeometry && next) this.fit();
    this.invalidate();
  }
  setSelection(id: string | null): void {
    if (this.disposed) return;
    const valid = id && this.doc?.targets.has(id) ? id : null;
    if (this.selected === valid) return;
    this.selected = valid;
    this.diagnostics?.setSelection(valid);
    this.applyOptions();
    this.invalidate();
  }
  setOptions(options: ViewOptions): void {
    if (this.disposed) return;
    this.options = { ...options };
    this.applyOptions();
    this.invalidate();
  }
  private applyOptions(): void {
    if (this.material) {
      const transparent = this.options.ghost || Boolean(this.selected);
      if (this.material.transparent !== transparent) this.material.needsUpdate = true;
      this.material.transparent = transparent;
      this.material.opacity = this.selected ? 0.12 : (this.options.ghost ? 0.28 : 1);
      this.material.depthWrite = !transparent;
      const useDepthPrepass = transparent && !this.options.xray;
      if (this.depthOccluder) this.depthOccluder.visible = useDepthPrepass;
      // A positive offset would put the color pass behind its own depth prepass.
      this.material.polygonOffset = this.options.wireframe && !useDepthPrepass;
    }
    if (this.options.wireframe && !this.wire && this.geometry && this.doc
        && this.doc.triangles.length / 3 <= MAX_WIREFRAME_TRIANGLES) {
      const geometry = this.surfaceScope.own(new THREE.WireframeGeometry(this.geometry));
      const material = this.surfaceScope.own(new THREE.LineBasicMaterial({
        color: 0x94a3b8, transparent: true, opacity: 0.35, depthWrite: false,
      }));
      this.wire = new THREE.LineSegments(geometry, material);
      this.wire.renderOrder = 1;
      this.surfaceGroup.add(this.wire);
    }
    if (this.wire) this.wire.visible = this.options.wireframe;
    this.diagnostics?.setXray(this.options.xray);
  }
  fit(): void {
    if (this.disposed) return;
    if (!this.hasSize) { this.pendingFit = true; return; }
    const sphere = this.geometry?.boundingSphere;
    const radius = Math.max(sphere?.radius || 1, 0.001);
    const center = sphere?.center ?? new THREE.Vector3();
    const verticalHalf = THREE.MathUtils.degToRad(this.camera.fov) / 2;
    const horizontalHalf = Math.atan(Math.tan(verticalHalf) * this.camera.aspect);
    const distance = radius / Math.sin(Math.min(verticalHalf, horizontalHalf)) * 1.15;
    this.controls.target.copy(center);
    this.camera.position.copy(center).add(new THREE.Vector3(1, 0.8, 1.2).normalize().multiplyScalar(distance));
    this.camera.near = radius / 1000;
    this.camera.far = Math.max(distance + radius * 100, radius * 1000);
    this.controls.minDistance = radius / 50;
    this.controls.maxDistance = this.camera.far / 2;
    this.camera.updateProjectionMatrix();
    this.controls.update();
    this.invalidate();
  }
  getResourceStats(): { geometries: number; textures: number; surfaceBuilds: number } {
    return { ...this.renderer.info.memory, surfaceBuilds: this.geometryBuildCount };
  }
  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.cancelFrame();
    this.diagnostics?.dispose();
    this.diagnostics = null;
    this.surfaceScope.dispose();
    this.surfaceGroup.clear();
    this.lifetime.dispose();
    this.scene.clear();
    this.doc = null;
  }
}
