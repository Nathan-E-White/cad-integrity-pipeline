import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import type { MeshPayload, Selection } from "../core/contracts.js";
import { type DisplayFrame, type Vec3, fitDistance, pulseOpacity, toDisplay } from "../core/math.js";
import { FrameScheduler } from "../core/scheduler.js";
import { defaultState, type InspectionState, validateState } from "../core/state.js";
import { resolveTarget, type Target } from "../core/selection.js";
import { SurfaceLayer } from "./SurfaceLayer.js";
import { DiagnosticLayer } from "./DiagnosticLayer.js";
import { pickTriangle } from "./picking.js";
import type { CameraPose } from "./CameraLink.js";

export interface ViewportOptions { onError?: (message: string | null) => void; onPick?: (target: Target | null) => void }
/** One WebGL context per viewport, at most two per document. No Svelte/Gradio dependency. */
export class Viewport {
  readonly scene = new THREE.Scene();
  readonly camera = new THREE.PerspectiveCamera(45, 1, 0.001, 1000);
  readonly renderer: THREE.WebGLRenderer;
  readonly controls: OrbitControls;
  onPose: ((pose: CameraPose) => void) | null = null;
  private readonly scheduler: FrameScheduler;
  private readonly resizeObserver: ResizeObserver;
  private readonly intersectionObserver: IntersectionObserver;
  private readonly reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  private surface: SurfaceLayer | null = null;
  private diagnostics: DiagnosticLayer | null = null;
  private mesh: MeshPayload | null = null;
  private frame: DisplayFrame | null = null;
  private state = defaultState();
  private selection: Selection | null = null;
  private targetKey: string | undefined;
  private disposed = false;
  private inView = true;
  private sized = false;
  private contextLost = false;
  private applyingPose = false;
  private dragStart: [number, number] | null = null;
  private focusTarget: THREE.Vector3 | null = null;
  private focusPosition: THREE.Vector3 | null = null;

  constructor(private readonly host: HTMLElement, private readonly options: ViewportOptions = {}) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.localClippingEnabled = true;
    this.scene.background = new THREE.Color("#f8fafc");
    this.renderer.domElement.style.cssText = "display:block;width:100%;height:100%;touch-action:none";
    this.renderer.domElement.setAttribute("aria-label", "Interactive mesh viewport; use the adjacent diagnostic buttons for keyboard selection");
    this.host.appendChild(this.renderer.domElement);
    this.camera.position.set(2.5, -3, 2.5);
    this.camera.up.set(0, 0, 1);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true; this.controls.dampingFactor = 0.08;
    this.controls.minDistance = 1e-4; this.controls.maxDistance = 500;
    this.controls.update();
    this.scheduler = new FrameScheduler((seconds, delta) => this.renderFrame(seconds, delta));
    this.controls.addEventListener("change", this.changed);
    this.controls.addEventListener("start", this.cancelFocus);
    this.resizeObserver = new ResizeObserver(this.resize);
    this.resizeObserver.observe(host);
    this.intersectionObserver = new IntersectionObserver(entries => {
      this.inView = entries[0]?.isIntersecting ?? true; this.updateEnabled();
    });
    this.intersectionObserver.observe(host);
    document.addEventListener("visibilitychange", this.updateEnabled);
    window.addEventListener("resize", this.resize);
    this.reducedMotion.addEventListener("change", this.changed);
    this.renderer.domElement.addEventListener("webglcontextlost", this.lost);
    this.renderer.domElement.addEventListener("webglcontextrestored", this.restored);
    this.renderer.domElement.addEventListener("pointerdown", this.pointerDown);
    this.renderer.domElement.addEventListener("pointerup", this.pointerUp);
    this.renderer.domElement.addEventListener("pointercancel", this.pointerCancel);
    this.resize();
  }

  setMesh(mesh: MeshPayload, frame: DisplayFrame): void {
    if (this.disposed || (mesh === this.mesh && frame === this.frame)) return;
    // Build first, publish only after both layers succeed. Dispose partial builds.
    let nextSurface: SurfaceLayer | null = null, nextDiagnostics: DiagnosticLayer | null = null;
    try { nextSurface = new SurfaceLayer(mesh, frame); nextDiagnostics = new DiagnosticLayer(mesh, frame); }
    catch (error) { nextSurface?.dispose(); nextDiagnostics?.dispose(); throw error; }
    const refit = this.mesh?.id !== mesh.id || this.mesh?.revision !== mesh.revision ||
      JSON.stringify(this.frame) !== JSON.stringify(frame);
    this.surface?.dispose(); this.diagnostics?.dispose();
    this.surface = nextSurface; this.diagnostics = nextDiagnostics;
    this.mesh = mesh; this.frame = frame; this.selection = null; this.targetKey = undefined;
    this.scene.add(nextSurface.group, nextDiagnostics.group);
    this.resize(); this.applyState(this.state);
    if (refit) this.fit();
    this.scheduler.invalidate();
  }
  applyState(state: InspectionState): void {
    validateState(state); this.state = { ...state };
    this.surface?.update(state); this.diagnostics?.update(state); this.scheduler.invalidate();
  }
  select(target: Target | null): void {
    const key = JSON.stringify(target);
    if (key === this.targetKey) return;
    this.targetKey = key;
    const selection = this.mesh ? resolveTarget(this.mesh, target) : null;
    if (selection === this.selection) return;
    this.selection = selection;
    this.surface?.select(selection); this.diagnostics?.select(selection); this.applyState(this.state);
  }
  fit(aspect = this.camera.aspect): void {
    // All linked views share this origin and radius=1 display frame. Fitting an
    // individual mesh here would hide geometric displacement between revisions.
    this.focusTarget = null; this.focusPosition = null;
    const distance = fitDistance(1, this.camera.fov, aspect);
    this.controls.target.set(0, 0, 0);
    this.camera.position.copy(new THREE.Vector3(1, -1.3, 0.9).normalize().multiplyScalar(distance));
    this.controls.update(); this.changed();
  }
  focusSelection(): void {
    if (!this.mesh || !this.frame || !this.selection || !this.surface) return;
    const bounds = new THREE.Box3();
    const add = (p: ArrayLike<number>): void => { bounds.expandByPoint(new THREE.Vector3(...toDisplay(p, this.frame!))); };
    for (const id of this.selection.face_ids) for (let corner = 0; corner < 3; corner++) {
      const i = this.mesh.triangles[id * 3 + corner] * 3;
      add(this.mesh.positions.slice(i, i + 3));
    }
    for (const i of this.selection.edge_pairs) add(this.mesh.positions.slice(i * 3, i * 3 + 3));
    for (let i = 0; i < this.selection.segments.length; i += 3) add(this.selection.segments.slice(i, i + 3));
    for (const path of this.mesh.paths) if (this.selection.path_ids.includes(path.id)) {
      for (let i = 0; i < path.points.length; i += 3) add(path.points.slice(i, i + 3));
    }
    if (bounds.isEmpty()) return;
    const sphere = bounds.getBoundingSphere(new THREE.Sphere());
    const direction = this.camera.position.clone().sub(this.controls.target).normalize();
    this.focusTarget = sphere.center;
    this.focusPosition = sphere.center.clone().addScaledVector(direction, fitDistance(Math.max(sphere.radius, 0.002), this.camera.fov, this.camera.aspect));
    if (this.reducedMotion.matches) {
      this.camera.position.copy(this.focusPosition); this.controls.target.copy(this.focusTarget); this.cancelFocus(); this.controls.update();
    }
    this.scheduler.invalidate();
  }
  getPose(): CameraPose {
    return { position: this.camera.position.toArray() as Vec3, target: this.controls.target.toArray() as Vec3,
      up: this.camera.up.toArray() as Vec3, fov: this.camera.fov, zoom: this.camera.zoom, near: this.camera.near, far: this.camera.far };
  }
  setPose(pose: CameraPose): void {
    this.applyingPose = true;
    try {
      this.cancelFocus();
      // Flush follower damping before applying an external pose; stale momentum
      // otherwise causes ping-pong drift across linked controllers.
      const damping = this.controls.enableDamping;
      this.controls.enableDamping = false; this.controls.update();
      this.camera.position.fromArray(pose.position); this.controls.target.fromArray(pose.target); this.camera.up.fromArray(pose.up);
      this.camera.fov = pose.fov; this.camera.zoom = pose.zoom; this.camera.near = pose.near; this.camera.far = pose.far;
      this.camera.updateProjectionMatrix(); this.controls.update(); this.controls.enableDamping = damping;
    } finally { this.applyingPose = false; }
    this.scheduler.invalidate();
  }
  private cancelFocus = (): void => { this.focusTarget = null; this.focusPosition = null; };
  private changed = (): void => {
    if (this.disposed) return;
    this.scheduler?.invalidate();
    if (!this.applyingPose) this.onPose?.(this.getPose());
  };
  private updateEnabled = (): void => { this.scheduler.setEnabled(!this.disposed && this.inView && this.sized && !document.hidden && !this.contextLost); };
  private resize = (): void => {
    if (this.disposed) return;
    const width = this.host.clientWidth, height = this.host.clientHeight;
    this.sized = width > 0 && height > 0;
    if (this.sized) {
      const ratio = Math.min(window.devicePixelRatio || 1, 2, Math.sqrt(8_000_000 / (width * height)));
      this.renderer.setPixelRatio(ratio); this.renderer.setSize(width, height, false);
      this.camera.aspect = width / height; this.camera.updateProjectionMatrix();
      this.diagnostics?.resize(width, height);
    }
    this.updateEnabled();
  };
  private lost = (event: Event): void => { event.preventDefault(); this.contextLost = true; this.updateEnabled(); this.options.onError?.("WebGL context lost. Waiting for browser restoration."); };
  private restored = (): void => { this.contextLost = false; this.options.onError?.(null); this.updateEnabled(); };
  private renderFrame(seconds: number, delta: number): boolean {
    if (this.disposed) return false;
    if (this.focusTarget && this.focusPosition) {
      const alpha = 1 - Math.exp(-delta / 0.12);
      this.controls.target.lerp(this.focusTarget, alpha); this.camera.position.lerp(this.focusPosition, alpha);
      if (this.controls.target.distanceToSquared(this.focusTarget) < 1e-10 && this.camera.position.distanceToSquared(this.focusPosition) < 1e-10) this.cancelFocus();
    }
    const moving = this.controls.update();
    const pulse = this.state.pulse && !!this.selection && !this.reducedMotion.matches;
    const opacity = pulse ? pulseOpacity(seconds) : 1;
    this.surface?.pulse(opacity); this.diagnostics?.pulse(opacity);
    this.renderer.render(this.scene, this.camera);
    return moving || pulse || this.focusTarget !== null;
  }
  private pointerDown = (event: PointerEvent): void => { this.dragStart = event.button === 0 ? [event.clientX, event.clientY] : null; };
  private pointerCancel = (): void => { this.dragStart = null; };
  private pointerUp = (event: PointerEvent): void => {
    const start = this.dragStart; this.dragStart = null;
    if (!start || !this.surface || !this.mesh || Math.hypot(event.clientX - start[0], event.clientY - start[1]) > 4) return;
    const bounds = this.renderer.domElement.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return;
    const pointer = new THREE.Vector2(2 * (event.clientX - bounds.left) / bounds.width - 1, 1 - 2 * (event.clientY - bounds.top) / bounds.height);
    const raycaster = new THREE.Raycaster(); raycaster.setFromCamera(pointer, this.camera);
    const faceId = pickTriangle(this.surface, raycaster.ray, this.state, this.selection !== null);
    this.options.onPick?.(faceId === null ? null : { kind: "face", meshId: this.mesh.id, revision: this.mesh.revision, faceId });
  };
  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.scheduler.dispose(); this.resizeObserver.disconnect(); this.intersectionObserver.disconnect();
    document.removeEventListener("visibilitychange", this.updateEnabled); window.removeEventListener("resize", this.resize);
    this.reducedMotion.removeEventListener("change", this.changed);
    this.controls.removeEventListener("change", this.changed); this.controls.removeEventListener("start", this.cancelFocus); this.controls.dispose();
    const canvas = this.renderer.domElement;
    canvas.removeEventListener("webglcontextlost", this.lost); canvas.removeEventListener("webglcontextrestored", this.restored);
    canvas.removeEventListener("pointerdown", this.pointerDown); canvas.removeEventListener("pointerup", this.pointerUp); canvas.removeEventListener("pointercancel", this.pointerCancel);
    this.surface?.dispose(); this.diagnostics?.dispose(); this.scene.clear();
    this.renderer.dispose(); this.renderer.forceContextLoss(); canvas.remove(); this.onPose = null;
  }
}
