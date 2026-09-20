import type { GeometryAsset, ModelDocument, ModelNode, Selection, SelectionMode } from "./model";
export function triangleSelection(doc: ModelDocument, node: ModelNode, asset: GeometryAsset, triangleIndex: number, mode: SelectionMode): Selection {
  const identity = { documentId: doc.id, revision: doc.revision, nodeId: node.id, geometryId: asset.id };
  if (mode === "object") return { ...identity, kind: "object" };
  const faceIndex = asset.triangleFaces?.[triangleIndex] ?? -1;
  const face = faceIndex >= 0 ? asset.faces?.[faceIndex] : undefined;
  if (mode === "face" && face) return { ...identity, kind: "face", faceId: face.id, faceKind: face.kind };
  return { ...identity, kind: "triangle", triangleIndex };
}
export function isSelectionValid(doc: ModelDocument, selection: Selection): boolean {
  if (selection.documentId !== doc.id || selection.revision !== doc.revision) return false;
  const node = doc.nodes.find((n) => n.id === selection.nodeId);
  const asset = doc.geometries.find((g) => g.id === selection.geometryId);
  if (!asset || !node || node.geometryId !== asset.id) return false;
  switch (selection.kind) {
    case "object": return true;
    case "triangle": return Number.isInteger(selection.triangleIndex) && selection.triangleIndex >= 0 && selection.triangleIndex < asset.indices.length / 3;
    case "face": return !!asset.faces?.some((face) => face.id === selection.faceId && face.kind === selection.faceKind);
    case "edge": return !!asset.edges?.some((edge) => edge.id === selection.edgeId && edge.kind === selection.edgeKind);
  }
}
export function selectedTriangleIndices(asset: GeometryAsset, selection: Selection): Uint32Array {
  if (selection.kind === "object") return asset.indices.slice();
  if (selection.kind === "triangle") return asset.indices.slice(selection.triangleIndex * 3, selection.triangleIndex * 3 + 3);
  if (selection.kind !== "face" || !asset.triangleFaces) return new Uint32Array();
  const faceIndex = asset.faces?.findIndex((face) => face.id === selection.faceId) ?? -1;
  if (faceIndex < 0) return new Uint32Array();
  const result: number[] = [];
  for (let t = 0; t < asset.triangleFaces.length; t++) if (asset.triangleFaces[t] === faceIndex) {
    result.push(asset.indices[t * 3], asset.indices[t * 3 + 1], asset.indices[t * 3 + 2]);
  }
  return new Uint32Array(result);
}
