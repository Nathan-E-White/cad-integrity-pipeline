import * as T from 'three';
import type { Mesh, Target, Kind } from '../core/inspection';
import { resolveTarget, entityCount, entityKinds } from '../core/inspection';
import { ResourceScope } from '../../../../../integration/mesh-diagnostics-seam/src/render/ResourceScope';
import type { WorkspaceState } from '../core/state';
/** One preallocated overlay per entity kind; interaction changes emphasis only. */
export class InspectionOverlay {
    readonly group = new T.Group();
    private scope = new ResourceScope();
    private batches: {
        kind: Kind;
        geometry: T.BufferGeometry;
        material: T.ShaderMaterial;
        owners: number[];
    }[] = [];
    private baseline = new Map<Kind, Uint8Array>();
    private visibilityKey: string | null = null;
    private emphasisKey: string | null = null;
    constructor(private mesh: Mesh, positions: Float32Array) {
        try {
            if (mesh.face_kind === 'polygonal_face') {
            const pointIds = Array.from({ length: positions.length / 3 }, (_, i) => i);
            this.batch('vertex', positions, pointIds, 'points');
            const edgePositions = new Float32Array(mesh.edges.length * 3);
            mesh.edges.forEach((v, i) => edgePositions.set(positions.subarray(v * 3, v * 3 + 3), i * 3));
            this.batch('edge', edgePositions, mesh.edges.map((_, i) => Math.floor(i / 2)), 'lines');
            // Point markers keep zero-length edges visible without changing source geometry.
            const centers = new Float32Array(mesh.edges.length / 2 * 3);
            for (let e = 0; e < mesh.edges.length / 2; e++)
                for (let k = 0; k < 3; k++)
                    centers[e * 3 + k] = (positions[mesh.edges[e * 2] * 3 + k] + positions[mesh.edges[e * 2 + 1] * 3 + k]) / 2;
            this.batch('edge', centers, Array.from({ length: mesh.edges.length / 2 }, (_, i) => i), 'points');
            }
            const faces = new Float32Array(mesh.triangles.length * 3);
            mesh.triangles.forEach((v, i) => faces.set(positions.subarray(v * 3, v * 3 + 3), i * 3));
            this.batch(mesh.face_kind, faces, mesh.triangles.map((_, i) => mesh.triangle_source_faces[Math.floor(i / 3)]), 'faces');
            // Unsupported faces still have selectable source segments.
            const boundary = new Float32Array(mesh.boundary_segments.length * 3);
            mesh.boundary_segments.forEach((v, i) => boundary.set(positions.subarray(v * 3, v * 3 + 3), i * 3));
            this.batch(mesh.face_kind, boundary, mesh.boundary_segments.map((_, i) => mesh.boundary_source_faces[Math.floor(i / 2)]), 'lines');
        }
        catch (error) {
            this.dispose();
            throw error;
        }
    }
    private batch(kind: Kind, positions: Float32Array, owners: number[], shape: 'points' | 'lines' | 'faces') {
        const geometry = this.scope.own(new T.BufferGeometry());
        geometry.setAttribute('position', new T.BufferAttribute(positions, 3));
        geometry.setAttribute('emphasis', new T.BufferAttribute(new Float32Array(owners.length), 1).setUsage(T.DynamicDrawUsage));
        const material = this.scope.own(new T.ShaderMaterial({ transparent: true, depthWrite: false, side: T.DoubleSide,
            uniforms: { clip: { value: new T.Vector4(0, 0, 0, 1) }, pointSize: { value: shape === 'points' ? 7 : 1 } },
            vertexShader: `attribute float emphasis; varying float strength; varying vec3 location; uniform float pointSize;
    void main(){strength=emphasis;location=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);gl_PointSize=pointSize;}`,
            fragmentShader: `varying float strength; varying vec3 location; uniform vec4 clip;
    void main(){if(strength<=0.0 || dot(clip.xyz,location)+clip.w<0.0) discard;
     gl_FragColor=vec4(mix(vec3(.85,.28,.05),vec3(1.,.5,.05),strength),strength);}`,
        }));
        const object = shape === 'points' ? new T.Points(geometry, material) : shape === 'lines' ? new T.LineSegments(geometry, material) : new T.Mesh(geometry, material);
        object.renderOrder = 3;
        this.group.add(object);
        this.batches.push({ kind, geometry, material, owners });
    }
    update(state: WorkspaceState, target: Target | null, muted: boolean, plane: T.Vector4): void {
        const visibilityKey = state.hiddenCategories.join('|');
        if (visibilityKey !== this.visibilityKey) {
            this.visibilityKey = visibilityKey;
            this.baseline.clear();
            for (const kind of entityKinds(this.mesh))
                this.baseline.set(kind, new Uint8Array(entityCount(this.mesh, kind)));
            for (const category of this.mesh.categories)
                if (!state.hiddenCategories.includes(category.id)) {
                    const flags = this.baseline.get(category.kind)!;
                    for (const id of category.entity_ids)
                        flags[id] = 1;
                }
        }
        const emphasisKey = JSON.stringify([target, muted, visibilityKey]);
        if (emphasisKey !== this.emphasisKey) {
            this.emphasisKey = emphasisKey;
            const selected = resolveTarget(this.mesh, target);
            const selectedIds = selected ? new Uint8Array(entityCount(this.mesh, selected.kind)) : null;
            for (const id of selected?.ids ?? [])
                selectedIds![id] = 1;
            for (const batch of this.batches) {
                const attr = batch.geometry.getAttribute('emphasis') as T.BufferAttribute;
                const baseline = this.baseline.get(batch.kind)!;
                for (let i = 0; i < batch.owners.length; i++) {
                    const owner = batch.owners[i];
                    attr.setX(i, selected?.kind === batch.kind && selectedIds![owner] ? (muted ? .25 : .95) : baseline[owner] ? .18 : 0);
                }
                attr.needsUpdate = true;
            }
        }
        for (const batch of this.batches) {
            batch.material.depthTest = !state.xray;
            batch.material.uniforms.clip.value.copy(plane);
        }
    }
    dispose() { this.group.removeFromParent(); this.scope.dispose(); }
}
