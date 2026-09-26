/** V2 polygonal and V3 native identities remain distinct source domains. */
export type Kind = 'vertex' | 'edge' | 'polygonal_face' | 'native_face';
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
    face_kind: 'polygonal_face' | 'native_face';
    projection_id: string | null;
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
    quad_trace: QuadTrace | null;
}
export interface QuadTraceRow {
    trace_id: number;
    seed_vertex_id: number;
    seed_edge_id: number;
    termination: string;
    blocker_trace_id: number | null;
    segment_ids: number[];
}
export interface QuadTraceSegment {
    segment_id: number;
    trace_id: number;
    edge_id: number;
    start2: number;
    end2: number;
    coordinates: number[];
}
export interface QuadTrace {
    mesh_id: string;
    revision: string;
    length_unit: string;
    canonical: boolean;
    complete: boolean;
    stop: 'none' | 'work_budget' | 'event_budget' | 'segment_budget' | 'output_budget';
    last_committed_time2: number | null;
    unfinished_trace_ids: number[];
    usage: { owned_bytes: number; work_steps: number; output_bytes: number };
    traces: QuadTraceRow[];
    segments: QuadTraceSegment[];
}
export interface Document {
    schema_version: 2 | 3 | 4;
    meshes: Mesh[];
}
export function tracePage(trace: QuadTrace, page: number, pageSize = 50): { current: number; pages: number; rows: QuadTraceRow[] } {
    require(Number.isSafeInteger(page) && page >= 0 && Number.isSafeInteger(pageSize) && pageSize > 0, 'Invalid trace page');
    const pages = Math.max(1, Math.ceil(trace.traces.length / pageSize));
    const current = Math.min(page, pages - 1);
    return { current, pages, rows: trace.traces.slice(current * pageSize, (current + 1) * pageSize) };
}
export function entityKinds(mesh: Mesh): Kind[] { return mesh.face_kind === 'native_face' ? ['native_face'] : ['vertex', 'edge', 'polygonal_face']; }
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
    require(doc.schema_version === 2 || doc.schema_version === 3 || doc.schema_version === 4, 'Unsupported inspection version');
    const native = doc.schema_version === 3;
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
        const face_kind = native ? 'native_face' : 'polygonal_face';
        const projection_id = native ? text(m.projection_id) : null;
        require(!native || m.face_kind === 'native_face', 'Unknown native face domain');
        require(!native || (edges.length === 0 && boundary_segments.length === 0 && list(m.categories, 0).length === 0), 'Native display vertices and segments are not source entities');
        const counts = { vertex: nv, edge: edges.length / 2, polygonal_face: face_count, native_face: face_count };
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
        const id = text(m.id), revision = text(m.revision), length_unit = text(m.length_unit);
        const quad_trace = doc.schema_version === 4 && m.quad_trace !== undefined
            ? parseQuadTrace(m.quad_trace, { id, revision, length_unit, vertexCount: nv, edgeCount: edges.length / 2 })
            : null;
        require(doc.schema_version === 4 || m.quad_trace === undefined, 'Trace evidence requires inspection v4');
        return Object.freeze({ id, revision, stage: m.stage, face_kind, projection_id, frame_id: text(m.frame_id), length_unit,
            positions, edges, face_count, triangles, triangle_source_faces, boundary_segments, boundary_source_faces,
            categories: Object.freeze(categories) as unknown as Category[], issues: Object.freeze(issues) as unknown as Mesh["issues"], quad_trace });
    });
    require(new Set(meshes.map(m => m.id)).size === meshes.length, 'Duplicate mesh identity');
    require(new Set(meshes.map(m => m.stage)).size === meshes.length, 'Duplicate stage');
    if (meshes.length && !native)
        require(meshes[0].stage === 'original', 'Original must be first');
    if (meshes.length === 2)
        require(meshes[0].frame_id === meshes[1].frame_id && meshes[0].length_unit === meshes[1].length_unit, 'Comparison frame mismatch');
    if (doc.schema_version === 4)
        require(!native && meshes.some(mesh => mesh.quad_trace !== null), 'V4 requires polygonal trace evidence');
    return Object.freeze({ schema_version: doc.schema_version, meshes: Object.freeze(meshes) as unknown as Mesh[] });
}

function parseQuadTrace(value: unknown, source: { id: string; revision: string; length_unit: string; vertexCount: number; edgeCount: number }): QuadTrace {
    const raw = record(value);
    require(text(raw.mesh_id) === source.id && text(raw.revision) === source.revision, 'Stale trace scope');
    require(text(raw.length_unit) === source.length_unit, 'Trace units mismatch');
    require(typeof raw.canonical === 'boolean' && typeof raw.complete === 'boolean', 'Invalid trace state');
    require(raw.canonical, 'Trace evidence is not canonical');
    const stops = ['none', 'work_budget', 'event_budget', 'segment_budget', 'output_budget'] as const;
    require(stops.includes(raw.stop), 'Unknown trace stop');
    require(raw.complete === (raw.stop === 'none'), 'Trace completion mismatch');
    const last_committed_time2 = raw.last_committed_time2 === null ? null : integer(raw.last_committed_time2, Number.MAX_SAFE_INTEGER);
    const usageRaw = record(raw.usage);
    const usage = Object.freeze({
        owned_bytes: integer(usageRaw.owned_bytes, Number.MAX_SAFE_INTEGER),
        work_steps: integer(usageRaw.work_steps, Number.MAX_SAFE_INTEGER),
        output_bytes: integer(usageRaw.output_bytes, Number.MAX_SAFE_INTEGER),
    });
    const traceInputs = list(raw.traces, 100000);
    const traceIds = new Set<number>();
    let segmentReferenceCount = 0;
    const traces: QuadTraceRow[] = traceInputs.map(item => {
        const row = record(item), trace_id = integer(row.trace_id, Number.MAX_SAFE_INTEGER);
        require(!traceIds.has(trace_id), 'Duplicate trace ID'); traceIds.add(trace_id);
        const termination = text(row.termination);
        require(['boundary', 'deposited_track', 'self_collision', 'opposing', 'simultaneous', 'right_hand', 'extraordinary', 'unfinished'].includes(termination), 'Unknown trace termination');
        const blocker_trace_id = row.blocker_trace_id === null ? null : integer(row.blocker_trace_id, Number.MAX_SAFE_INTEGER);
        const segment_ids = numbers(row.segment_ids, 1, 100000, Number.MAX_SAFE_INTEGER);
        segmentReferenceCount += segment_ids.length;
        require(segmentReferenceCount <= 100000, 'Aggregate trace segment-reference budget exceeded');
        return Object.freeze({ trace_id, seed_vertex_id: integer(row.seed_vertex_id, source.vertexCount - 1),
            seed_edge_id: integer(row.seed_edge_id, source.edgeCount - 1), termination, blocker_trace_id,
            segment_ids: Object.freeze(segment_ids) as unknown as number[] });
    });
    const segments: QuadTraceSegment[] = list(raw.segments, 100000).map(item => {
        const segment = record(item);
        return Object.freeze({ segment_id: integer(segment.segment_id, Number.MAX_SAFE_INTEGER),
            trace_id: integer(segment.trace_id, Number.MAX_SAFE_INTEGER), edge_id: integer(segment.edge_id, source.edgeCount - 1),
            start2: integer(segment.start2, Number.MAX_SAFE_INTEGER), end2: integer(segment.end2, Number.MAX_SAFE_INTEGER),
            coordinates: Object.freeze(numbers(segment.coordinates, 6, 6)) as unknown as number[] });
    });
    const segmentIds = new Set(segments.map(segment => segment.segment_id));
    const segmentOwners = new Map(segments.map(segment => [segment.segment_id, segment.trace_id]));
    require(segmentIds.size === segments.length, 'Duplicate segment ID');
    for (const segment of segments) require(traceIds.has(segment.trace_id), 'Unknown segment trace');
    for (const row of traces) {
        require(new Set(row.segment_ids).size === row.segment_ids.length && row.segment_ids.every(id => segmentIds.has(id)), 'Unknown trace segment');
        require(row.blocker_trace_id === null || traceIds.has(row.blocker_trace_id), 'Unknown blocker trace');
        require(row.segment_ids.every(id => segmentOwners.get(id) === row.trace_id), 'Foreign trace segment');
    }
    const unfinished_trace_ids = Object.freeze(numbers(raw.unfinished_trace_ids, 1, 100000, Number.MAX_SAFE_INTEGER)) as unknown as number[];
    require(new Set(unfinished_trace_ids).size === unfinished_trace_ids.length && unfinished_trace_ids.every(id => traceIds.has(id)), 'Unknown unfinished trace');
    require(!raw.complete || unfinished_trace_ids.length === 0, 'Complete trace has unfinished rows');
    const listedSegmentIds = new Set<number>();
    for (const row of traces) for (const id of row.segment_ids) {
        require(!listedSegmentIds.has(id), 'Segment ownership mismatch');
        listedSegmentIds.add(id);
    }
    require(segmentReferenceCount === segments.length, 'Segment ownership mismatch');
    const unfinished = new Set(unfinished_trace_ids);
    require(traces.every(row => (row.termination === 'unfinished') === unfinished.has(row.trace_id)), 'Unfinished trace mismatch');
    return Object.freeze({ mesh_id: source.id, revision: source.revision, length_unit: source.length_unit,
        canonical: raw.canonical, complete: raw.complete, stop: raw.stop, last_committed_time2, unfinished_trace_ids, usage,
        traces: Object.freeze(traces) as unknown as QuadTraceRow[], segments: Object.freeze(segments) as unknown as QuadTraceSegment[] });
}
export function entityCount(mesh: Mesh, kind: Kind): number { if (!entityKinds(mesh).includes(kind)) return 0; return kind === 'vertex' ? mesh.positions.length / 3 : kind === 'edge' ? mesh.edges.length / 2 : mesh.face_count; }
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
        if (!entityKinds(mesh).includes(kind) || !Number.isSafeInteger(target.entityId) || target.entityId < 0 || target.entityId >= entityCount(mesh, kind))
            return null;
        ids = [target.entityId];
    }
    const selected = new Set(ids);
    const triangleIds = kind === mesh.face_kind ? mesh.triangle_source_faces.flatMap((f, t) => selected.has(f) ? [t] : []) : [];
    return { kind, ids, triangleIds };
}
export function targetFromTriangle(mesh: Mesh, triangle: number, projectionId?: string): Target | null {
    if (mesh.projection_id !== null && projectionId !== mesh.projection_id) return null;
    if (!Number.isSafeInteger(triangle) || triangle < 0 || triangle >= mesh.triangle_source_faces.length)
        return null;
    return entityTarget(mesh, mesh.face_kind, mesh.triangle_source_faces[triangle]);
}
