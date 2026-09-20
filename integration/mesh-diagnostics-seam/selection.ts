import type { MeshPayload, Selection } from "./contracts.js";
interface Scoped { meshId: string; revision: string }
export type Target = (Scoped & { kind: "selection"; id: string }) | (Scoped & { kind: "face"; faceId: number }) | (Scoped & { kind: "path"; pathId: string });
export function resolveTarget(mesh: MeshPayload, target: Target | null): Selection | null {
  if (!target || mesh.id !== target.meshId || mesh.revision !== target.revision) return null;
  if (target.kind === "selection") return mesh.selections.find(s => s.id === target.id) ?? null;
  if (target.kind === "path") return mesh.paths.some(p => p.id === target.pathId)
    ? { id: target.pathId, label: `Path ${target.pathId}`, face_ids: [], edge_pairs: [], segments: [], path_ids: [target.pathId] } : null;
  if (!Number.isInteger(target.faceId) || target.faceId < 0 || target.faceId >= mesh.triangles.length / 3) return null;
  return { id: `face:${target.faceId}`, label: `Triangle ${target.faceId}`, face_ids: [target.faceId], edge_pairs: [], segments: [], path_ids: [] };
}
export function sameTarget(a: Target | null, b: Target | null): boolean { return JSON.stringify(a) === JSON.stringify(b); }
export function selectionHasGeometry(selection: Selection | undefined): boolean {
  return !!selection && !!(selection.face_ids.length + selection.edge_pairs.length + selection.segments.length + selection.path_ids.length);
}
