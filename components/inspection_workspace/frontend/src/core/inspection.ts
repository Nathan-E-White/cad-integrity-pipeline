/** V2 identities are source entities, never v1 display-triangle targets. */
export type Kind = 'vertex' | 'edge' | 'polygonal_face';
export type Target = {
    meshId: string;
    revision: string;
} & ({
    type: 'entity';
    kind: Kind;
    entityId: number;
} | {
    type: 'category';
    categoryId: string;
});
export interface Category {
    id: string;
    kind: Kind;
    entity_ids: number[];
}
export interface Mesh {
    id: string;
    revision: string;
    stage: 'original' | 'candidate';
    frame_id: string;
    length_unit: string;
    positions: number[];
    edges: number[];
    face_count: number;
    triangles: number[];
    triangle_source_faces: number[];
    boundary_segments: number[];
    boundary_source_faces: number[];
    categories: Category[];
    issues: {
        face_id: number;
        code: string;
        detail: string;
    }[];
}
export interface Document {
    schema_version: 2;
    meshes: Mesh[];
}
const kinds: Kind[] = ['vertex', 'edge', 'polygonal_face'];
const categoryKinds: Record<string, Kind> = { nonmanifold_vertices: 'vertex', unused_vertices: 'vertex',
    boundary_edges: 'edge', nonmanifold_edges: 'edge', winding_conflicts: 'edge', unused_edges: 'edge', collapsed_edges: 'edge',
    invalid_faces: 'polygonal_face', duplicate_faces: 'polygonal_face' };
function require(condition: unknown, message: string): asserts condition {
    if (!condition)
        throw new Error(message);
}
function record(value: unknown): Record<string, any> {
    require(value && typeof value === 'object' && !Array.isArray(value), 'Expected object');
    return value as Record<string, any>;
}
function text(value: unknown): string { require(typeof value === 'string' && value.length > 0 && value.length <= 4096, 'Invalid text'); return value; }
function integer(value: unknown, max: number): number { require(typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 && value <= max, 'Invalid integer'); return value; }
function list(value: unknown, max: number): any[] { require(Array.isArray(value) && value.length <= max, 'Array budget exceeded'); return value; }
function numbers(value: unknown, stride: number, max: number, bound?: number): number[] {
    const array = list(value, max);
    require(array.length % stride === 0, 'Incomplete coordinates');
    for (const n of array) {
        require(typeof n === 'number' && Number.isFinite(n), 'Nonfinite coordinate');
        if (bound !== undefined)
            integer(n, bound);
    }
    return Object.freeze(array.slice()) as unknown as number[];
}
export function parseInspection(value: unknown): Document {
    if (value == null)
        return Object.freeze({ schema_version: 2, meshes: Object.freeze([]) as unknown as Mesh[] });
    if (typeof value === 'string') {
        require(value.length <= 512000000, 'Encoded document budget exceeded');
        value = JSON.parse(value);
    }
    const doc = record(value);
    require(doc.schema_version === 2, 'Unsupported inspection version');
    const inputs = list(doc.meshes, 2);
    let aggregate = 0;
    for (const input of inputs) {
        const raw = record(input);
        for (const key of ['positions', 'edges', 'triangles', 'triangle_source_faces', 'boundary_segments', 'boundary_source_faces']) {
            aggregate += list(raw[key], 9000000).length;
        }
    }
    require(aggregate <= 60000000, 'Aggregate inspection budget exceeded');
    const meshes: Mesh[] = inputs.map(raw => {
        const m = record(raw), positions = numbers(m.positions, 3, 750000), nv = positions.length / 3;
        const edges = numbers(m.edges, 2, 3000000, nv - 1), face_count = integer(m.face_count, 500000);
        const triangles = numbers(m.triangles, 3, 3000000, nv - 1);
        const triangle_source_faces = numbers(m.triangle_source_faces, 1, 1000000, face_count - 1);
        require(triangle_source_faces.length === triangles.length / 3, 'Triangle owner length');
        const boundary_segments = numbers(m.boundary_segments, 2, 6000000, nv - 1);
        const boundary_source_faces = numbers(m.boundary_source_faces, 1, 3000000, face_count - 1);
        require(boundary_source_faces.length === boundary_segments.length / 2, 'Boundary owner length');
        const counts = { vertex: nv, edge: edges.length / 2, polygonal_face: face_count };
        const categories: Category[] = list(m.categories, 9).map(raw => {
            const c = record(raw), id = text(c.id), kind = c.kind as Kind;
            require(categoryKinds[id] === kind, 'Unknown category or entity kind');
            const entity_ids = numbers(c.entity_ids, 1, counts[kind], counts[kind] - 1);
            require(new Set(entity_ids).size === entity_ids.length, 'Duplicate category membership');
            return Object.freeze({ id, kind, entity_ids });
        });
        require(new Set(categories.map(c => c.id)).size === categories.length, 'Duplicate category');
        const issues = list(m.issues, face_count).map(raw => { const i = record(raw); return Object.freeze({ face_id: integer(i.face_id, face_count - 1), code: text(i.code), detail: text(i.detail) }); });
        require(m.stage === 'original' || m.stage === 'candidate', 'Unknown stage');
        require(['mm', 'cm', 'm', 'in'].includes(m.length_unit), 'Unknown units');
        return Object.freeze({ id: text(m.id), revision: text(m.revision), stage: m.stage, frame_id: text(m.frame_id), length_unit: m.length_unit,
            positions, edges, face_count, triangles, triangle_source_faces, boundary_segments, boundary_source_faces,
            categories: Object.freeze(categories) as unknown as Category[], issues: Object.freeze(issues) as unknown as Mesh["issues"] });
    });
    require(new Set(meshes.map(m => m.id)).size === meshes.length, 'Duplicate mesh identity');
    require(new Set(meshes.map(m => m.stage)).size === meshes.length, 'Duplicate stage');
    if (meshes.length)
        require(meshes[0].stage === 'original', 'Original must be first');
    if (meshes.length === 2)
        require(meshes[0].frame_id === meshes[1].frame_id && meshes[0].length_unit === meshes[1].length_unit, 'Comparison frame mismatch');
    return Object.freeze({ schema_version: 2, meshes: Object.freeze(meshes) as unknown as Mesh[] });
}
export function entityCount(mesh: Mesh, kind: Kind): number { return kind === 'vertex' ? mesh.positions.length / 3 : kind === 'edge' ? mesh.edges.length / 2 : mesh.face_count; }
export function entityTarget(mesh: Mesh, kind: Kind, entityId: number): Target { return { meshId: mesh.id, revision: mesh.revision, type: 'entity', kind, entityId }; }
export function resolveTarget(mesh: Mesh, target: Target | null): {
    kind: Kind;
    ids: number[];
    triangleIds: number[];
} | null {
    if (!target || target.meshId !== mesh.id || target.revision !== mesh.revision)
        return null;
    let kind: Kind, ids: number[];
    if (target.type === 'category') {
        const category = mesh.categories.find(c => c.id === target.categoryId);
        if (!category)
            return null;
        kind = category.kind;
        ids = category.entity_ids;
    }
    else {
        kind = target.kind;
        if (!kinds.includes(kind) || !Number.isSafeInteger(target.entityId) || target.entityId < 0 || target.entityId >= entityCount(mesh, kind))
            return null;
        ids = [target.entityId];
    }
    const selected = new Set(ids);
    const triangleIds = kind === 'polygonal_face' ? mesh.triangle_source_faces.flatMap((f, t) => selected.has(f) ? [t] : []) : [];
    return { kind, ids, triangleIds };
}
export function targetFromTriangle(mesh: Mesh, triangle: number): Target | null {
    if (!Number.isSafeInteger(triangle) || triangle < 0 || triangle >= mesh.triangle_source_faces.length)
        return null;
    return entityTarget(mesh, 'polygonal_face', mesh.triangle_source_faces[triangle]);
}
