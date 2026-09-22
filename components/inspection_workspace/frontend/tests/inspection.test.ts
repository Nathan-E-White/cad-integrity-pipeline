import { test, expect } from 'bun:test';
import { parseInspection } from '../src/core/inspection';
const mesh = { id: 'original', revision: 'r1', stage: 'original', frame_id: 'source', length_unit: 'mm',
    positions: [0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 0], edges: [0, 1, 1, 2, 2, 3, 3, 0], face_count: 1,
    triangles: [0, 1, 2, 0, 2, 3], triangle_source_faces: [0, 0], boundary_segments: [0, 1, 1, 2, 2, 3, 3, 0],
    boundary_source_faces: [0, 0, 0, 0], categories: [{ id: 'boundary_edges', kind: 'edge', entity_ids: [0, 1, 2, 3] }], issues: [] };
export const square = () => structuredClone(mesh);
test('A01: V2 preserves source face identity and rejects malformed references', () => {
    expect(parseInspection({ schema_version: 2, meshes: [square()] }).meshes[0].face_count).toBe(1);
    expect(() => parseInspection({ schema_version: 1, meshes: [square()] })).toThrow();
    expect(() => parseInspection({ schema_version: 2, meshes: [{ ...square(), triangles: [0, 1, 9] }] })).toThrow();
});
import { resolveTarget, targetFromTriangle } from '../src/core/inspection';
test('A06/A09: triangle picks select the whole source face; stale targets do not resolve', () => {
    const m = parseInspection({ schema_version: 2, meshes: [square()] }).meshes[0];
    for (const triangle of [0, 1]) {
        const target = targetFromTriangle(m, triangle);
        expect(target).toEqual({ meshId: 'original', revision: 'r1', type: 'entity', kind: 'polygonal_face', entityId: 0 });
        expect(resolveTarget(m, target)?.triangleIds).toEqual([0, 1]);
        expect(resolveTarget(m, { ...target!, revision: 'old' })).toBeNull();
    }
    expect(targetFromTriangle(m, 2)).toBeNull();
});
test('A08: coincident entities and boundary-only faces remain addressable', () => {
    const raw = square();
    raw.face_count = 2;
    raw.triangle_source_faces = [0, 0];
    raw.categories.push({ id: 'duplicate_faces', kind: 'polygonal_face', entity_ids: [1] } as any);
    const m = parseInspection({ schema_version: 2, meshes: [raw] }).meshes[0];
    expect(resolveTarget(m, { meshId: m.id, revision: m.revision, type: 'entity', kind: 'polygonal_face', entityId: 1 })).toEqual({ kind: 'polygonal_face', ids: [1], triangleIds: [] });
    expect(resolveTarget(m, { meshId: m.id, revision: m.revision, type: 'entity', kind: 'vertex', entityId: 0 })?.ids).toEqual([0]);
    expect(resolveTarget(m, { meshId: m.id, revision: m.revision, type: 'entity', kind: 'edge', entityId: 0 })?.ids).toEqual([0]);
});
test('A02/A03: malformed payloads cannot create partially trusted targets', () => {
    for (const change of [{ positions: [0, NaN, 0] }, { triangle_source_faces: [2, 0] }, { boundary_source_faces: [] },
        { categories: [{ id: 'boundary_edges', kind: 'vertex', entity_ids: [0] }] },
        { categories: [{ id: 'boundary_edges', kind: 'edge', entity_ids: [0, 0] }] },
        { issues: [{ face_id: 9, code: 'unsupported', detail: 'bad' }] }]) {
        expect(() => parseInspection({ schema_version: 2, meshes: [{ ...square(), ...change }] })).toThrow();
    }
});
test('A01: primitive JSON transport retains V2 semantics without reactive arrays', () => {
    expect(parseInspection(JSON.stringify({ schema_version: 2, meshes: [square()] })).meshes[0].triangle_source_faces).toEqual([0, 0]);
    expect(() => parseInspection('{broken')).toThrow();
});
test('decoded snapshot owns and freezes nested collections', () => {
    const source = { schema_version: 2, meshes: [square()] };
    const parsed = parseInspection(source);
    source.meshes[0].positions[0] = 99;
    expect(parsed.meshes[0].positions[0]).toBe(0);
    expect(Object.isFrozen(parsed)).toBe(true);
    expect(Object.isFrozen(parsed.meshes)).toBe(true);
    expect(Object.isFrozen(parsed.meshes[0].issues)).toBe(true);
    expect(Object.isFrozen(parsed.meshes[0].categories)).toBe(true);
});

export const nativeSquare = () => ({ ...square(), face_kind: 'native_face', projection_id: 'p1', edges: [], boundary_segments: [], boundary_source_faces: [], categories: [] });
test('v3 native triangles resolve to native faces and reject stale or foreign references', () => {
    const m = parseInspection({ schema_version: 3, meshes: [nativeSquare()] }).meshes[0];
    const target = targetFromTriangle(m, 1, 'p1');
    expect(target).toEqual({ meshId: 'original', revision: 'r1', type: 'entity', kind: 'native_face', entityId: 0 });
    expect(resolveTarget(m, target)?.triangleIds).toEqual([0, 1]);
    expect(targetFromTriangle(m, 1, 'old-projection')).toBeNull();
    expect(targetFromTriangle(m, 1)).toBeNull();
    expect(resolveTarget(m, { ...target!, revision: 'old' })).toBeNull();
    expect(resolveTarget(m, { ...target!, meshId: 'candidate' })).toBeNull();
    expect(resolveTarget(m, { ...target!, type: 'entity', kind: 'polygonal_face', entityId: 0 })).toBeNull();
    expect(resolveTarget(m, { ...target!, type: 'entity', kind: 'vertex', entityId: 0 })).toBeNull();
});

test('v3 validates ownership, projection identity and face-only domain', () => {
    for (const change of [{ projection_id: undefined }, { face_kind: 'polygonal_face' },
        { triangle_source_faces: [0, 2] }, { triangle_source_faces: [0] },
        { edges: [0, 1] }, { positions: [0, Infinity, 1] }]) {
        expect(() => parseInspection({ schema_version: 3, meshes: [{ ...nativeSquare(), ...change }] })).toThrow();
    }
    const missing = { ...nativeSquare(), face_count: 2, issues: [{ face_id: 1, code: 'missing_triangulation', detail: 'Interior unavailable' }] };
    const m = parseInspection({ schema_version: 3, meshes: [missing] }).meshes[0];
    expect(resolveTarget(m, { meshId: m.id, revision: m.revision, type: 'entity', kind: 'native_face', entityId: 1 }))
        .toEqual({ kind: 'native_face', ids: [1], triangleIds: [] });
    const remeshed = parseInspection({ schema_version: 3, meshes: [{ ...nativeSquare(), projection_id: 'p2', triangles: [0, 1, 3], triangle_source_faces: [0] }] }).meshes[0];
    expect(targetFromTriangle(remeshed, 0, 'p1')).toBeNull();
    expect(targetFromTriangle(remeshed, 0, 'p2')?.type).toBe('entity');
});
