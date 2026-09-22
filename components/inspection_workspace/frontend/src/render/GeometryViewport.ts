import * as T from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { ResourceScope } from '../../../../../integration/mesh-diagnostics-seam/src/render/ResourceScope';
import { displayPositions, fitDistance, type DisplayFrame, type Vec3 } from '../../../../../integration/mesh-diagnostics-seam/src/core/math';
import type { CameraPose } from '../../../../../integration/mesh-diagnostics-seam/src/render/CameraLink';
import { entityTarget, resolveTarget, targetFromTriangle, type Mesh, type Target } from '../core/inspection';
import { initialState, type WorkspaceState } from '../core/state';
import { InspectionOverlay } from './InspectionOverlay';
export class GeometryViewport {
    readonly camera = new T.PerspectiveCamera(45, 1, .001, 100);
    readonly renderer: T.WebGLRenderer;
    readonly controls: OrbitControls;
    onPose: ((pose: CameraPose) => void) | null = null;
    private scene = new T.Scene();
    private scope = new ResourceScope();
    private overlay: InspectionOverlay;
    private surface: T.Mesh;
    private points: T.Points;
    private edges: T.LineSegments;
    private resize: ResizeObserver;
    private frameId = 0;
    private disposed = false;
    private lostContext = false;
    private applying = false;
    private state = initialState();
    private selection: Target | null = null;
    private start: [
        number,
        number
    ] | null = null;
    private positions: Float32Array;
    constructor(private host: HTMLElement, private mesh: Mesh, private frame: DisplayFrame, private pick: (target: Target | null) => void, private error: (message: string | null) => void) {
        this.renderer = new T.WebGLRenderer({ antialias: true });
        try {
            this.renderer.localClippingEnabled = true;
            this.scene.background = new T.Color('#f8fafc');
            this.renderer.domElement.style.cssText = 'display:block;width:100%;height:100%;touch-action:none';
            host.appendChild(this.renderer.domElement);
            this.positions = displayPositions(mesh.positions, frame);
            const geometry = this.scope.own(new T.BufferGeometry());
            geometry.setAttribute('position', new T.BufferAttribute(this.positions, 3));
            geometry.setIndex(mesh.triangles);
            geometry.computeVertexNormals();
            const material = this.scope.own(new T.MeshStandardMaterial({ side: T.DoubleSide, color: '#b8c4cc', roughness: .85 }));
            this.surface = new T.Mesh(geometry, material);
            this.scene.add(this.surface);
            this.scene.add(new T.HemisphereLight('#ffffff', '#64748b', 2));
            const light = new T.DirectionalLight('#ffffff', 2);
            light.position.set(2, -3, 4);
            this.scene.add(light);
            const pointGeometry = this.scope.own(new T.BufferGeometry());
            pointGeometry.setAttribute('position', new T.BufferAttribute(this.positions, 3));
            this.points = new T.Points(pointGeometry, this.scope.own(new T.PointsMaterial({ size: 3, sizeAttenuation: false, color: '#475569' })));
            this.points.visible = mesh.face_kind !== 'native_face';
            this.scene.add(this.points);
            const edges = this.scope.own(new T.BufferGeometry());
            edges.setAttribute('position', new T.BufferAttribute(this.positions, 3));
            edges.setIndex(mesh.edges);
            this.edges = new T.LineSegments(edges, this.scope.own(new T.LineBasicMaterial({ color: '#64748b', transparent: true, opacity: .25 })));
            this.scene.add(this.edges);
            this.overlay = new InspectionOverlay(mesh, this.positions);
            this.scene.add(this.overlay.group);
            this.camera.up.set(0, 0, 1);
            this.camera.position.set(2, -3, 2);
            this.controls = new OrbitControls(this.camera, this.renderer.domElement);
            this.controls.enableDamping = false;
            this.controls.addEventListener('change', this.changed);
            this.resize = new ResizeObserver(this.resized);
            this.resize.observe(host);
            this.renderer.domElement.addEventListener('pointerdown', this.down);
            this.renderer.domElement.addEventListener('pointerup', this.up);
            this.renderer.domElement.addEventListener('webglcontextlost', this.lost);
            this.renderer.domElement.addEventListener('webglcontextrestored', this.restored);
            this.resized();
            this.focusBounds(new T.Box3(new T.Vector3(-1, -1, -1).divideScalar(Math.sqrt(3)), new T.Vector3(1, 1, 1).divideScalar(Math.sqrt(3))));
        }
        catch (error) {
            this.dispose();
            throw error;
        }
    }
    private render = () => {
        this.frameId = 0;
        if (!this.disposed && !this.lostContext)
            this.renderer.render(this.scene, this.camera);
    };
    private invalidate = () => {
        if (!this.frameId && !this.disposed)
            this.frameId = requestAnimationFrame(this.render);
    };
    private changed = () => {
        this.invalidate();
        if (!this.applying)
            this.onPose?.(this.getPose());
    };
    private resized = () => {
        const w = this.host.clientWidth, h = this.host.clientHeight;
        if (!w || !h)
            return;
        this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
        this.renderer.setSize(w, h, false);
        this.camera.aspect = w / h;
        this.camera.updateProjectionMatrix();
        this.invalidate();
    };
    private plane(): T.Vector4 {
        const clip = this.state.clips[this.mesh.stage];
        const p = new T.Vector4(0, 0, 0, 1);
        if (clip.enabled) {
            p.setComponent(clip.axis, -1);
            p.w = (clip.offset - this.frame.origin[clip.axis]) / this.frame.scale;
        }
        return p;
    }
    update(state: WorkspaceState, muted = false): void {
        this.state = state;
        this.selection = state.hover[this.mesh.stage] ?? state.selections[this.mesh.stage];
        const p = this.plane();
        const clipping = state.clips[this.mesh.stage].enabled ? [new T.Plane(new T.Vector3(p.x, p.y, p.z), p.w)] : [];
        for (const object of [this.surface, this.points, this.edges]) {
            const material = object.material as T.Material;
            const changed = (material.clippingPlanes?.length ?? 0) !== clipping.length;
            material.clippingPlanes = clipping;
            if (changed)
                material.needsUpdate = true;
        }
        this.points.visible = state.mode === 'vertex';
        this.overlay.update(state, this.selection, muted, p);
        this.invalidate();
    }
    focusSelection(): void {
        const selected = resolveTarget(this.mesh, this.state.selections[this.mesh.stage]);
        if (!selected)
            return;
        const indices = new Set<number>();
        if (selected.kind === 'vertex')
            for (const id of selected.ids)
                indices.add(id);
        if (selected.kind === 'edge')
            for (const id of selected.ids) {
                indices.add(this.mesh.edges[id * 2]);
                indices.add(this.mesh.edges[id * 2 + 1]);
            }
        if (selected.kind === this.mesh.face_kind) {
            for (const triangle of selected.triangleIds)
                for (let k = 0; k < 3; k++)
                    indices.add(this.mesh.triangles[triangle * 3 + k]);
            const ids = new Set(selected.ids);
            this.mesh.boundary_source_faces.forEach((f, s) => {
                if (ids.has(f)) {
                    indices.add(this.mesh.boundary_segments[s * 2]);
                    indices.add(this.mesh.boundary_segments[s * 2 + 1]);
                }
            });
        }
        const box = new T.Box3();
        for (const id of indices)
            box.expandByPoint(new T.Vector3().fromArray(this.positions, id * 3));
        if (!box.isEmpty())
            this.focusBounds(box);
    }
    private focusBounds(box: T.Box3) { const sphere = box.getBoundingSphere(new T.Sphere()); this.controls.target.copy(sphere.center); this.camera.position.copy(sphere.center).addScaledVector(new T.Vector3(1, -1.3, .9).normalize(), fitDistance(Math.max(sphere.radius, .01), 45, this.camera.aspect)); this.controls.update(); this.changed(); }
    getPose(): CameraPose { return { position: this.camera.position.toArray() as Vec3, target: this.controls.target.toArray() as Vec3, up: this.camera.up.toArray() as Vec3, fov: this.camera.fov, zoom: this.camera.zoom, near: this.camera.near, far: this.camera.far }; }
    setPose(pose: CameraPose) {
        this.applying = true;
        try {
            this.camera.position.fromArray(pose.position);
            this.controls.target.fromArray(pose.target);
            this.camera.up.fromArray(pose.up);
            this.camera.fov = pose.fov;
            this.camera.zoom = pose.zoom;
            this.camera.near = pose.near;
            this.camera.far = pose.far;
            this.camera.updateProjectionMatrix();
            this.controls.update();
            this.invalidate();
        }
        finally {
            this.applying = false;
        }
    }
    private down = (event: PointerEvent) => { this.start = event.button === 0 ? [event.clientX, event.clientY] : null; };
    private up = (event: PointerEvent) => {
        const start = this.start;
        this.start = null;
        if (!start || Math.hypot(event.clientX - start[0], event.clientY - start[1]) > 4)
            return;
        const r = this.renderer.domElement.getBoundingClientRect(), ray = new T.Raycaster();
        ray.setFromCamera(new T.Vector2((event.clientX - r.left) / r.width * 2 - 1, 1 - (event.clientY - r.top) / r.height * 2), this.camera);
        const distance = this.camera.position.distanceTo(this.controls.target);
        ray.params.Points.threshold = distance * .012;
        ray.params.Line.threshold = distance * .008;
        const object = this.state.mode === 'vertex' ? this.points : this.state.mode === 'edge' ? this.edges : this.surface;
        const p = this.plane();
        const hit = ray.intersectObject(object).find(h => p.x * h.point.x + p.y * h.point.y + p.z * h.point.z + p.w >= 0);
        this.pick(!hit ? null : this.state.mode === this.mesh.face_kind ? targetFromTriangle(this.mesh, hit.faceIndex!, this.mesh.projection_id ?? undefined) : entityTarget(this.mesh, this.state.mode, this.state.mode === 'edge' ? Math.floor(hit.index! / 2) : hit.index!));
    };
    private lost = (event: Event) => { event.preventDefault(); this.lostContext = true; this.error('WebGL context lost'); };
    private restored = () => { this.lostContext = false; this.error(null); this.invalidate(); };
    dispose() {
        if (this.disposed)
            return;
        this.disposed = true;
        cancelAnimationFrame(this.frameId);
        this.resize?.disconnect();
        this.controls?.removeEventListener('change', this.changed);
        this.controls?.dispose();
        for (const [name, fn] of [['pointerdown', this.down], ['pointerup', this.up], ['webglcontextlost', this.lost], ['webglcontextrestored', this.restored]] as const)
            this.renderer.domElement.removeEventListener(name, fn as EventListener);
        this.overlay?.dispose();
        this.scope.dispose();
        this.renderer.dispose();
        this.renderer.forceContextLoss();
        this.renderer.domElement.remove();
    }
}
