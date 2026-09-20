import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { fitSphere } from "../math";
import { invariant, type ModelDocument, type PickResult, type Selection, type SelectionMode, type Vec3 } from "../model";
import { isSelectionValid, triangleSelection } from "../selection";
import { type DisplayMode, RenderModel, type RenderInstance } from "./RenderModel";
import { DEFAULT_THEME, type ViewerTheme } from "./theme";

export type Projection = "perspective" | "orthographic";
export type ViewPreset = "isometric" | "front" | "back" | "left" | "right" | "top" | "bottom";
export interface ClipPlane { readonly normal: Vec3; readonly constant: number; }
export interface ViewerOptions {
  readonly theme?: Partial<ViewerTheme>;
  readonly maxPixelRatio?: number;
  readonly onSelectionChange?: (selection: Selection | null, hit: PickResult | null) => void;
  readonly onError?: (error: Error) => void;
}
export interface ViewerLayerContext {
  readonly group: THREE.Group;
  readonly document: ModelDocument | null;
  readonly origin: Vec3;
  /** Overlay coordinates are in the rebased display frame, not raw document coordinates. */
  readonly toRenderPoint: (point: Vec3) => THREE.Vector3;
  readonly camera: () => THREE.Camera;
  readonly invalidate: () => void;
}
export interface ViewerLayer {
  readonly id: string;
  /** Re-mounted on document replacement. Return cleanup for ALL layer-owned GPU resources/listeners. */
  mount(context: ViewerLayerContext): () => void;
}
type ViewerDomEvents = HTMLElementEventMap & { webglcontextlost: Event; webglcontextrestored: Event };
interface LayerRecord { layer: ViewerLayer; group?: THREE.Group; cleanup?: () => void; }

/** Imperative rendering core; no Solid dependency and no file-format knowledge. */
export class ThreeCadViewer {
  private readonly renderer: THREE.WebGLRenderer;
  private readonly scene = new THREE.Scene();
  private readonly perspective = new THREE.PerspectiveCamera(45, 1, 0.01, 1000);
  private readonly orthographic = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.01, 1000);
  private activeCamera: THREE.PerspectiveCamera | THREE.OrthographicCamera = this.perspective;
  private controls: OrbitControls;
  private readonly resizeObserver: ResizeObserver;
  private readonly raycaster = new THREE.Raycaster();
  private readonly theme: ViewerTheme;
  private model: RenderModel | null = null;
  private selection: Selection | null = null;
  private selectionMode: SelectionMode = "face";
  private displayMode: DisplayMode = "shaded-edges";
  private clipPlane: ClipPlane | null = null;
  private renderPlanes: THREE.Plane[] = [];
  private projection: Projection = "perspective";
  private orthoHalfHeight = 1;
  private width = 0;
  private height = 0;
  private frame = 0;
  private disposed = false;
  private contextLost = false;
  private readonly layers = new Map<string, LayerRecord>();
  private pointer?: { id: number; x: number; y: number; dragged: boolean };
  private readonly cleanups: (() => void)[] = [];
  private readonly owners = new WeakMap<THREE.Object3D, RenderInstance>();

  constructor(private readonly host: HTMLElement, private readonly options: ViewerOptions = {}) {
    invariant(typeof window !== "undefined", "Create ThreeCadViewer inside Solid onMount, not during SSR");
    const maxPixelRatio = options.maxPixelRatio ?? 2;
    invariant(Number.isFinite(maxPixelRatio) && maxPixelRatio > 0, "Invalid pixel ratio cap");
    this.theme = { ...DEFAULT_THEME, ...options.theme };
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
    this.renderer.setClearColor(this.theme.background);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.localClippingEnabled = true;
    const canvas = this.renderer.domElement;
    canvas.style.cssText = "display:block;width:100%;height:100%;touch-action:none;outline-offset:-3px";
    canvas.tabIndex = 0;
    canvas.setAttribute("aria-label", "3D model. Drag to orbit, wheel to zoom, right-drag to pan. F fits; Escape clears selection.");
    this.perspective.position.set(3, -4, 3);
    this.perspective.up.set(0, 0, 1);
    this.orthographic.up.copy(this.perspective.up);
    this.controls = this.makeControls(new THREE.Vector3());
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x65758a, 2.4));
    const key = new THREE.DirectionalLight(0xffffff, 3.1); key.position.set(4, -6, 9); this.scene.add(key);
    const fill = new THREE.DirectionalLight(0xffffff, 1.5); fill.position.set(-6, 4, -1); this.scene.add(fill);
    this.resizeObserver = new ResizeObserver(() => this.resize());
    try {
      host.append(canvas); this.resizeObserver.observe(host);
      this.listen(canvas, "pointerdown", this.pointerDown);
      this.listen(canvas, "pointermove", this.pointerMove);
      this.listen(canvas, "pointerup", this.pointerUp);
      this.listen(canvas, "pointercancel", () => { this.pointer = undefined; });
      this.listen(canvas, "dblclick", () => this.fit());
      this.listen(canvas, "keydown", this.keyDown);
      this.listen(canvas, "webglcontextlost", this.onContextLost);
      this.listen(canvas, "webglcontextrestored", this.onContextRestored);
      window.addEventListener("resize", this.resize);
      this.cleanups.push(() => window.removeEventListener("resize", this.resize));
      this.resize();
    } catch (error) { this.dispose(); throw error; }
  }
  get document(): ModelDocument | null { return this.model?.document ?? null; }
  get selected(): Selection | null { return this.selection; }
  get camera(): THREE.Camera { return this.activeCamera; }
  get origin(): Vec3 { return this.model?.origin ?? [0, 0, 0]; }
  private report(error: unknown): void {
    const normalized = error instanceof Error ? error : new Error(String(error));
    if (this.options.onError) this.options.onError(normalized);
    else console.error(normalized);
  }
  private listen<K extends keyof ViewerDomEvents>(target: HTMLElement, type: K, listener: (event: ViewerDomEvents[K]) => void): void {
    target.addEventListener(type, listener as EventListener);
    this.cleanups.push(() => target.removeEventListener(type, listener as EventListener));
  }
  private makeControls(target: THREE.Vector3): OrbitControls {
    const controls = new OrbitControls(this.activeCamera, this.renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.12;
    controls.screenSpacePanning = true;
    controls.target.copy(target);
    controls.addEventListener("change", this.invalidate);
    controls.update();
    return controls;
  }
  private replaceControls(target: THREE.Vector3): void {
    this.controls.removeEventListener("change", this.invalidate); this.controls.dispose();
    this.controls = this.makeControls(target);
  }
  readonly invalidate = (): void => {
    if (!this.disposed && !this.contextLost && this.frame === 0) this.frame = requestAnimationFrame(this.renderFrame);
  };
  private readonly renderFrame = (): void => {
    this.frame = 0;
    if (this.disposed || this.contextLost || this.width < 1 || this.height < 1) return;
    try {
      // update emits 'change' until damping settles. No permanent idle animation loop.
      this.controls.update(); this.updateDepthRange();
      this.renderer.render(this.scene, this.activeCamera);
    } catch (error) { this.report(error); }
  };
  private readonly resize = (): void => {
    if (this.disposed) return;
    const wasHidden = this.width < 1 || this.height < 1;
    const rect = this.host.getBoundingClientRect();
    this.width = Math.floor(rect.width); this.height = Math.floor(rect.height);
    if (this.width < 1 || this.height < 1) return;
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, this.options.maxPixelRatio ?? 2));
    this.renderer.setSize(this.width, this.height, false);
    const aspect = this.width / this.height;
    this.perspective.aspect = aspect; this.perspective.updateProjectionMatrix();
    this.orthographic.left = -this.orthoHalfHeight * aspect; this.orthographic.right = this.orthoHalfHeight * aspect;
    this.orthographic.top = this.orthoHalfHeight; this.orthographic.bottom = -this.orthoHalfHeight;
    this.orthographic.updateProjectionMatrix();
    if (wasHidden && this.model) this.fit();
    this.invalidate();
  };
  private readonly onContextLost = (event: Event): void => {
    event.preventDefault(); this.contextLost = true;
    cancelAnimationFrame(this.frame); this.frame = 0;
    this.report(new Error("WebGL context lost. The viewer will redraw if the browser restores it."));
  };
  private readonly onContextRestored = (): void => { this.contextLost = false; this.resize(); this.invalidate(); };

  setDocument(document: ModelDocument | null): void {
    invariant(!this.disposed, "Viewer is disposed");
    if (document === this.document) return;
    const next = document ? RenderModel.create(document, this.theme) : null;
    for (const record of this.layers.values()) this.detachLayer(record);
    const old = this.model;
    this.model = next;
    if (next) {
      this.scene.add(next.root); next.setDisplayMode(this.displayMode);
      for (const instance of next.instances.values()) {
        this.owners.set(instance.surface, instance); this.owners.set(instance.edges, instance);
      }
    }
    old?.dispose();
    this.selection = null;
    this.updateClipping();
    this.setPreset("isometric");
    for (const record of this.layers.values()) this.attachLayer(record);
    this.options.onSelectionChange?.(null, null); this.invalidate();
  }
  setSelectionMode(mode: SelectionMode): void { this.selectionMode = mode; }
  setDisplayMode(mode: DisplayMode): void { this.displayMode = mode; this.model?.setDisplayMode(mode); this.invalidate(); }
  setSelection(selection: Selection | null, hit: PickResult | null = null): void {
    invariant(selection === null || (!!this.document && isSelectionValid(this.document, selection)), "Selection is stale or not in this document");
    this.selection = selection; this.model?.highlightSelection(selection);
    this.options.onSelectionChange?.(selection, hit); this.invalidate();
  }
  setVisible(nodeId: string, visible: boolean): void { this.model?.setVisible(nodeId, visible); this.invalidate(); }
  isolate(nodeIds: readonly string[]): void { this.model?.isolate(nodeIds); this.fit(); }
  showAll(): void { this.model?.showAll(); this.fit(); }
  setProjection(projection: Projection): void {
    if (this.projection === projection) return;
    const old = this.activeCamera;
    const target = this.controls.target.clone();
    const direction = old.position.clone().sub(target).normalize();
    const tangent = Math.tan(THREE.MathUtils.degToRad(this.perspective.fov / 2));
    this.activeCamera = projection === "perspective" ? this.perspective : this.orthographic;
    this.activeCamera.up.copy(old.up); this.activeCamera.position.copy(old.position);
    if (projection === "orthographic") {
      this.orthoHalfHeight = old.position.distanceTo(target) * tangent;
      this.orthographic.zoom = 1;
    } else {
      const distance = this.orthoHalfHeight / this.orthographic.zoom / tangent;
      this.perspective.position.copy(target).addScaledVector(direction, distance);
    }
    this.projection = projection; this.replaceControls(target); this.resize(); this.updateDepthRange(); this.invalidate();
  }
  setPreset(preset: ViewPreset): void {
    const zUp = this.document?.upAxis !== "Y";
    const up = zUp ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(0, 1, 0);
    const front = zUp ? new THREE.Vector3(0, -1, 0) : new THREE.Vector3(0, 0, 1);
    let direction: THREE.Vector3;
    switch (preset) {
      case "front": direction = front; break;
      case "back": direction = front.negate(); break;
      case "left": direction = new THREE.Vector3(-1, 0, 0); break;
      case "right": direction = new THREE.Vector3(1, 0, 0); break;
      case "top": direction = up.clone(); break;
      case "bottom": direction = up.clone().negate(); break;
      default: direction = zUp ? new THREE.Vector3(1, -1, 0.8) : new THREE.Vector3(1, 0.8, 1);
    }
    const target = this.controls.target.clone();
    const distance = Math.max(this.activeCamera.position.distanceTo(target), 1e-9);
    this.activeCamera.up.copy(Math.abs(direction.clone().normalize().dot(up)) > 0.99
      ? (zUp ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(0, 0, -1)) : up);
    this.activeCamera.position.copy(target).addScaledVector(direction.normalize(), distance);
    // OrbitControls caches its up-axis transform; recreate when switching to a pole view.
    this.replaceControls(target); this.fit();
  }
  fit(): void {
    const box = this.model?.visibleBounds();
    if (!box || box.isEmpty()) { this.invalidate(); return; }
    const sphere = box.getBoundingSphere(new THREE.Sphere());
    const fit = fitSphere(sphere.radius, Math.max(this.width, 1) / Math.max(this.height, 1), this.perspective.fov);
    const direction = this.activeCamera.position.clone().sub(this.controls.target).normalize();
    if (direction.lengthSq() === 0) direction.set(1, -1, 1).normalize();
    const target = sphere.center;
    this.activeCamera.position.copy(target).addScaledVector(direction, fit.distance);
    this.orthoHalfHeight = fit.orthoHalfHeight; this.orthographic.zoom = 1;
    // Recreating also discards residual damping after an explicit fit operation.
    this.replaceControls(target);
    this.controls.minDistance = fit.radius * 1e-4; this.controls.maxDistance = fit.radius * 1e6;
    this.resize(); this.updateDepthRange(); this.invalidate();
  }
  private updateDepthRange(): void {
    const box = this.model?.visibleBounds();
    if (!box || box.isEmpty()) return;
    const sphere = box.getBoundingSphere(new THREE.Sphere());
    const radius = Math.max(sphere.radius, 1e-9);
    const distance = this.activeCamera.position.distanceTo(sphere.center);
    const near = Math.max(radius * 1e-6, (distance - radius) * 0.1);
    const far = Math.max(near * 100, distance + radius * 4);
    if (this.activeCamera.near !== near || this.activeCamera.far !== far) {
      this.activeCamera.near = near; this.activeCamera.far = far; this.activeCamera.updateProjectionMatrix();
    }
  }
  /** Keeps n·p + c >= 0. This is visual clipping, NOT a capped CAD section operation. */
  setClippingPlane(plane: ClipPlane | null): void {
    if (plane) {
      invariant(plane.normal.every(Number.isFinite) && Number.isFinite(plane.constant), "Invalid clipping plane");
      invariant(Math.hypot(...plane.normal) > 0, "Clipping plane normal is zero");
    }
    this.clipPlane = plane; this.updateClipping(); this.invalidate();
  }
  private updateClipping(): void {
    if (!this.clipPlane) this.renderPlanes = [];
    else {
      const normal = new THREE.Vector3(...this.clipPlane.normal);
      const constant = this.clipPlane.constant + normal.dot(new THREE.Vector3(...this.origin));
      this.renderPlanes = [new THREE.Plane(normal, constant).normalize()];
    }
    this.model?.setClippingPlanes(this.renderPlanes);
  }
  /** Picking is approximate on tessellation/polylines; no exact kernel query is implied. */
  pick(clientX: number, clientY: number): PickResult | null {
    if (!this.model || this.disposed || this.width < 1 || this.height < 1) return null;
    const rect = this.renderer.domElement.getBoundingClientRect();
    if (clientX < rect.left || clientX > rect.right || clientY < rect.top || clientY > rect.bottom) return null;
    const pointer = new THREE.Vector2((clientX - rect.left) / rect.width * 2 - 1, -(clientY - rect.top) / rect.height * 2 + 1);
    this.scene.updateMatrixWorld(true); this.activeCamera.updateMatrixWorld(true);
    this.raycaster.setFromCamera(pointer, this.activeCamera);
    const instances = [...this.model.instances.values()].filter((instance) => instance.group.visible);
    const unclipped = (hit: THREE.Intersection) => this.renderPlanes.every((plane) => plane.distanceToPoint(hit.point) >= 0);
    const surfaceHit = this.raycaster.intersectObjects(instances.map((instance) => instance.surface), false).find(unclipped);
    if (this.selectionMode === "edge") {
      if (this.displayMode !== "shaded-edges") return null;
      const viewHeight = this.projection === "orthographic" ? 2 * this.orthoHalfHeight / this.orthographic.zoom
        : 2 * this.activeCamera.position.distanceTo(this.controls.target) * Math.tan(THREE.MathUtils.degToRad(this.perspective.fov / 2));
      const threshold = Math.max(viewHeight / Math.max(1, this.height) * 6, 1e-12);
      this.raycaster.params.Line.threshold = threshold;
      const hits = this.raycaster.intersectObjects(instances.filter((instance) => instance.asset.segmentToEdge).map((instance) => instance.edges), false);
      for (const hit of hits) {
        if (!unclipped(hit) || (surfaceHit && hit.distance > surfaceHit.distance + threshold)) continue;
        const instance = this.owners.get(hit.object);
        const segment = Math.floor((hit.index ?? -2) / 2);
        const edgeIndex = instance?.asset.segmentToEdge?.[segment];
        const edge = edgeIndex === undefined ? undefined : instance?.asset.source.edges?.[edgeIndex];
        if (instance && edge) return {
          selection: { documentId: this.model.document.id, revision: this.model.document.revision,
            nodeId: instance.node.id, geometryId: instance.asset.source.id, kind: "edge", edgeId: edge.id, edgeKind: edge.kind },
          point: this.toDocumentPoint(hit.point),
        };
      }
      return null;
    }
    if (!surfaceHit || surfaceHit.faceIndex == null) return null;
    const instance = this.owners.get(surfaceHit.object);
    if (!instance) return null;
    return { selection: triangleSelection(this.model.document, instance.node, instance.asset.source, surfaceHit.faceIndex, this.selectionMode),
      point: this.toDocumentPoint(surfaceHit.point), triangleIndex: surfaceHit.faceIndex };
  }
  private toDocumentPoint(point: THREE.Vector3): Vec3 { return [point.x + this.origin[0], point.y + this.origin[1], point.z + this.origin[2]]; }
  private readonly pointerDown = (event: PointerEvent): void => {
    if (!event.isPrimary) { if (this.pointer) this.pointer.dragged = true; return; }
    if (event.button === 0) this.pointer = { id: event.pointerId, x: event.clientX, y: event.clientY, dragged: false };
  };
  private readonly pointerMove = (event: PointerEvent): void => {
    if (this.pointer?.id === event.pointerId && Math.hypot(event.clientX - this.pointer.x, event.clientY - this.pointer.y) > 5) this.pointer.dragged = true;
  };
  private readonly pointerUp = (event: PointerEvent): void => {
    const pointer = this.pointer; this.pointer = undefined;
    if (event.button !== 0 || pointer?.id !== event.pointerId || pointer.dragged) return;
    const hit = this.pick(event.clientX, event.clientY); this.setSelection(hit?.selection ?? null, hit);
  };
  private readonly keyDown = (event: KeyboardEvent): void => {
    if (event.key === "Escape") { event.preventDefault(); this.setSelection(null); }
    if (event.key.toLowerCase() === "f") { event.preventDefault(); this.fit(); }
  };
  installLayer(layer: ViewerLayer): () => void {
    invariant(!this.disposed && !this.layers.has(layer.id), "Viewer disposed or duplicate layer ID");
    const record = { layer }; this.layers.set(layer.id, record); this.attachLayer(record);
    return () => {
      if (this.layers.get(layer.id) !== record) return;
      this.detachLayer(record); this.layers.delete(layer.id); this.invalidate();
    };
  }
  private attachLayer(record: LayerRecord): void {
    const group = new THREE.Group(); record.group = group; this.scene.add(group);
    const origin = this.origin;
    try {
      record.cleanup = record.layer.mount({ group, origin, document: this.document,
        toRenderPoint: (point) => new THREE.Vector3(point[0] - origin[0], point[1] - origin[1], point[2] - origin[2]),
        camera: () => this.activeCamera, invalidate: this.invalidate });
    } catch (error) { group.removeFromParent(); record.group = undefined; this.report(error); }
    this.invalidate();
  }
  private detachLayer(record: LayerRecord): void {
    record.group?.removeFromParent(); record.group = undefined;
    const cleanup = record.cleanup; record.cleanup = undefined;
    try { cleanup?.(); } catch (error) { this.report(error); }
  }
  dispose(): void {
    if (this.disposed) return;
    this.disposed = true; cancelAnimationFrame(this.frame); this.frame = 0;
    this.resizeObserver?.disconnect();
    for (const cleanup of this.cleanups) cleanup(); this.cleanups.length = 0;
    for (const record of this.layers.values()) this.detachLayer(record); this.layers.clear();
    this.controls.removeEventListener("change", this.invalidate); this.controls.dispose();
    this.model?.dispose(); this.model = null; this.selection = null;
    this.scene.clear(); this.renderer.dispose(); this.renderer.forceContextLoss(); this.renderer.domElement.remove();
  }
}
