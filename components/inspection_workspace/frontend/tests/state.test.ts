import { test, expect } from 'bun:test';
import { initialState, transition } from '../src/core/state';
import type { Target } from '../src/core/inspection';
const original: Target = { meshId: 'original', revision: '1', type: 'entity', kind: 'vertex', entityId: 0 };
const candidate: Target = { ...original, meshId: 'candidate' };
test('W19/W23/W27: pinned selections survive mode, pane, filter and hover changes', () => {
    let s = initialState();
    s = transition(s, { type: 'select', pane: 'original', target: original });
    s = transition(s, { type: 'select', pane: 'candidate', target: candidate });
    s = transition(s, { type: 'mode', mode: 'edge' });
    s = transition(s, { type: 'category', category: 'unused_vertices' });
    s = transition(s, { type: 'hover', pane: 'original', target: { ...original, entityId: 1 } });
    s = transition(s, { type: 'hover', pane: 'original', target: null });
    expect(s.selections).toEqual({ original, candidate });
    expect(s.mode).toBe('edge');
    expect(s.hover.original).toBeNull();
});
test('W09/W10: unlink is local and relink copies the active pane', () => {
    let s = initialState();
    s = transition(s, { type: 'clip', pane: 'original', clip: { enabled: true, axis: 2, offset: 4 } });
    expect(s.clips.candidate).toEqual({ enabled: true, axis: 2, offset: 4 });
    s = transition(s, { type: 'link', value: false });
    s = transition(s, { type: 'clip', pane: 'candidate', clip: { enabled: true, axis: 1, offset: 7 } });
    expect(s.clips.original.offset).toBe(4);
    s = transition(s, { type: 'active', pane: 'candidate' });
    s = transition(s, { type: 'link', value: true });
    expect(s.clips.original).toEqual({ enabled: true, axis: 1, offset: 7 });
});
test('comparison camera coupling is explicit browser-local workspace state', () => {
    let s = initialState();
    expect(s.linkedCameras).toBe(true);
    s = transition(s, { type: 'cameraLink', value: false });
    expect(s.linkedCameras).toBe(false);
    s = transition(s, { type: 'cameraLink', value: true });
    expect(s.linkedCameras).toBe(true);
});
test('comparison dock density is explicit browser-local workspace state', () => {
    let s = initialState('polygonal_face', true);
    expect(s.compactDocks).toBe(true);
    s = transition(s, { type: 'maximize', pane: 'original' });
    expect(s.compactDocks).toBe(false);
    s = transition(s, { type: 'maximize', pane: null });
    expect(s.compactDocks).toBe(true);
    s = transition(s, { type: 'docks', compact: false });
    expect(s.compactDocks).toBe(false);
});
test('W21/W22/W26: replacing and clearing selection only changes its pane', () => {
    let s = initialState();
    s = transition(s, { type: 'select', pane: 'candidate', target: candidate });
    s = transition(s, { type: 'select', pane: 'original', target: original });
    s = transition(s, { type: 'select', pane: 'original', target: { meshId: 'original', revision: '1', type: 'category', categoryId: 'boundary_edges' } });
    expect(s.selections.original?.type).toBe('category');
    s = transition(s, { type: 'select', pane: 'original', target: null });
    expect(s.selections.candidate).toEqual(candidate);
});
import { targetOutsideFilter } from '../src/core/state';
import { parseInspection } from '../src/core/inspection';
import { square } from './inspection.test';
test('retained category and entity targets mute outside the shared filter', () => {
    const mesh = parseInspection({ schema_version: 2, meshes: [square()] }).meshes[0];
    const category = { meshId: mesh.id, revision: mesh.revision, type: 'category' as const, categoryId: 'boundary_edges' };
    expect(targetOutsideFilter(mesh, category, 'unused_edges', true)).toBe(true);
    expect(targetOutsideFilter(mesh, category, null, true)).toBe(false);
    const entity = { meshId: mesh.id, revision: mesh.revision, type: 'entity' as const, kind: 'vertex' as const, entityId: 0 };
    expect(targetOutsideFilter(mesh, entity, null, true)).toBe(true);
    expect(targetOutsideFilter(mesh, entity, null, false)).toBe(false);
});
