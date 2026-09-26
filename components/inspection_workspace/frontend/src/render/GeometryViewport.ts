import * as T from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { ResourceScope } from '../../../../../integration/mesh-diagnostics-seam/src/render/ResourceScope';
import { displayPositions, fitDistance, type DisplayFrame, type Vec3 } from '../../../../../integration/mesh-diagnostics-seam/src/core/math';
import type { CameraPose } from '../../../../../integration/mesh-diagnostics-seam/src/render/CameraLink';
import { entityTarget, resolveTarget, targetFromTriangle, type Mesh, type Target } from '../core/inspection';
import { initialState, type WorkspaceState } from '../core/state';
import { InspectionOverlay } from './InspectionOverlay';
import { TraceOverlay } from './TraceOverlay';
export class GeometryViewport {
    readonly camera = new T.PerspectiveCamera(45, 1, .001, 100);
    readonly renderer: T.WebGLRenderer;
    readonly controls: OrbitControls;
    onPose: ((pose: CameraPose) => void) | null = null;
    private scene = new T.Scene();
    private gnomonScene = new T.Scene();
    private gnomonCamera = new T.PerspectiveCamera(34, 1, .1, 10);
    private scope = new ResourceScope();
    private overlay: InspectionOverlay;
    private traceOverlay: TraceOverlay | null = null;
    private surface: T.Mesh;
    private elementGrid: T.Mesh;
    private crease: T.LineSegments | null = null;
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
        this.renderer = new T.WebGLRenderer({ antialias: true, alpha: true });
        try {
            this.renderer.localClippingEnabled = true;
            this.renderer.setClearColor(0x000000, 0);
            this.scene.fog = new T.FogExp2('#0d1724', .16);
            this.renderer.domElement.style.cssText = 'display:block;width:100%;height:100%;touch-action:none';
            host.appendChild(this.renderer.domElement);
            this.positions = displayPositions(mesh.positions, frame);
            const geometry = this.scope.own(new T.BufferGeometry());
            geometry.setAttribute('position', new T.BufferAttribute(this.positions, 3));
            geometry.setIndex(mesh.triangles);
            geometry.computeVertexNormals();
            const material = this.scope.own(new T.ShaderMaterial({
                side: T.DoubleSide,
                fog: true,
                clipping: true,
                uniforms: T.UniformsUtils.merge([T.UniformsLib.fog, {
                    uBase: { value: new T.Color('#82909c') },
                    uCool: { value: new T.Color('#263747') },
                    uWarm: { value: new T.Color('#a7afb3') }
                }]),
                vertexShader: `
                    #include <common>
                    #include <fog_pars_vertex>
                    #include <clipping_planes_pars_vertex>
                    varying vec3 vNormalView;
                    void main() {
                        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
                        vNormalView = normalize(normalMatrix * normal);
                        gl_Position = projectionMatrix * mvPosition;
                        #include <clipping_planes_vertex>
                        #include <fog_vertex>
                    }
                `,
                fragmentShader: `
                    uniform vec3 uBase;
                    uniform vec3 uCool;
                    uniform vec3 uWarm;
                    varying vec3 vNormalView;
                    #include <clipping_planes_pars_fragment>
                    #include <fog_pars_fragment>
                    void main() {
                        #include <clipping_planes_fragment>
                        vec3 n = normalize(vNormalView);
                        if (!gl_FrontFacing) n = -n;
                        float matte = pow(max(dot(n, normalize(vec3(-0.35, 0.45, 0.82))), 0.0), 0.65);
                        float rim = pow(1.0 - abs(n.z), 2.0);
                        vec3 color = mix(uCool, uBase, 0.22 + 0.78 * matte);
                        color = mix(color, uWarm, 0.06 * max(n.x, 0.0));
                        color += rim * vec3(0.035, 0.045, 0.055);
                        gl_FragColor = vec4(color, 1.0);
                        #include <fog_fragment>
                    }
                `
            }));
            this.surface = new T.Mesh(geometry, material);
            this.scene.add(this.surface);
            this.elementGrid = new T.Mesh(geometry, this.scope.own(new T.MeshBasicMaterial({
                color: '#101a25', wireframe: true, transparent: true, opacity: .2, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -1
            })));
            this.scene.add(this.elementGrid);
            if (mesh.triangles.length <= 300000) {
                const creaseGeometry = this.scope.own(new T.EdgesGeometry(geometry, 28));
                this.crease = new T.LineSegments(creaseGeometry, this.scope.own(new T.LineBasicMaterial({ color: '#9aabba', transparent: true, opacity: .28 })));
                this.scene.add(this.crease);
            }
            const pointGeometry = this.scope.own(new T.BufferGeometry());
            pointGeometry.setAttribute('position', new T.BufferAttribute(this.positions, 3));
            this.points = new T.Points(pointGeometry, this.scope.own(new T.PointsMaterial({ size: 3, sizeAttenuation: false, color: '#475569' })));
            this.points.visible = mesh.face_kind !== 'native_face';
            this.scene.add(this.points);
            const edges = this.scope.own(new T.BufferGeometry());
            edges.setAttribute('position', new T.BufferAttribute(this.positions, 3));
            edges.setIndex(mesh.edges);
            this.edges = new T.LineSegments(edges, this.scope.own(new T.LineBasicMaterial({ color: '#152231', transparent: true, opacity: .55 })));
            this.scene.add(this.edges);
            const axes = new T.AxesHelper(.72);
            axes.setColors(new T.Color('#a46f78'), new T.Color('#739888'), new T.Color('#6f91aa'));
            this.scope.own(axes.geometry);
            const axisMaterials = Array.isArray(axes.material) ? axes.material : [axes.material];
            for (const owned of axisMaterials) this.scope.own(owned);
            this.gnomonScene.add(axes);
            this.overlay = new InspectionOverlay(mesh, this.positions);
            this.scene.add(this.overlay.group);
            if (mesh.quad_trace) {
                this.traceOverlay = new TraceOverlay(mesh.quad_trace, frame);
                this.scene.add(this.traceOverlay.group);
            }
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
        if (!this.disposed && !this.lostContext) {
            const width = this.host.clientWidth, height = this.host.clientHeight;
            this.renderer.setScissorTest(false);
            this.renderer.setViewport(0, 0, width, height);
            this.renderer.render(this.scene, this.camera);
            const size = Math.min(68, Math.max(52, width * .14));
            this.gnomonCamera.position.copy(this.camera.position).sub(this.controls.target).normalize().multiplyScalar(3);
            this.gnomonCamera.up.copy(this.camera.up);
            this.gnomonCamera.lookAt(0, 0, 0);
            this.renderer.clearDepth();
            this.renderer.setScissorTest(true);
            this.renderer.setScissor(width - size - 8, 8, size, size);
            this.renderer.setViewport(width - size - 8, 8, size, size);
            this.renderer.render(this.gnomonScene, this.gnomonCamera);
            this.renderer.setScissorTest(false);
        }
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
    update(state: WorkspaceState, muted = false, traceId: number | null = null): void {
        this.state = state;
        this.selection = state.hover[this.mesh.stage] ?? state.selections[this.mesh.stage];
        const p = this.plane();
        const clipping = state.clips[this.mesh.stage].enabled ? [new T.Plane(new T.Vector3(p.x, p.y, p.z), p.w)] : [];
        for (const object of [this.surface, this.elementGrid, this.points, this.edges, this.crease]) {
            if (!object) continue;
            const materials = Array.isArray(object.material) ? object.material : [object.material];
            for (const material of materials) {
                const changed = (material.clippingPlanes?.length ?? 0) !== clipping.length;
                material.clippingPlanes = clipping;
                if (changed) material.needsUpdate = true;
            }
        }
        this.points.visible = state.mode === 'vertex';
        this.overlay.update(state, this.selection, muted, p);
        this.traceOverlay?.update(traceId, state.xray, p);
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
        this.traceOverlay?.dispose();
        this.scope.dispose();
        this.renderer.dispose();
        this.renderer.forceContextLoss();
        this.renderer.domElement.remove();
    }
}
