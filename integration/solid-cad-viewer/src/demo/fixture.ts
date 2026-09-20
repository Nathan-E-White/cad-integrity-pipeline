import type { EdgePolyline, ModelDocument, Vec3 } from "../model";
/** Synthetic planar-face fixture, not the result of a STEP import or kernel certification. */
export function makeDemoDocument(): ModelDocument {
  const corners: Vec3[] = [[-20, -15, -10], [20, -15, -10], [20, 15, -10], [-20, 15, -10], [-20, -15, 10], [20, -15, 10], [20, 15, 10], [-20, 15, 10]];
  const quads = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]];
  const positions: number[] = []; const indices: number[] = []; const labels: number[] = [];
  for (let f = 0; f < quads.length; f++) {
    for (const vertex of quads[f]) positions.push(...corners[vertex]);
    const i = f * 4; indices.push(i, i + 1, i + 2, i, i + 2, i + 3); labels.push(f, f);
  }
  const pairs = [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]];
  const edges: EdgePolyline[] = pairs.map(([a, b], index) => ({ id: `edge-${index}`, kind: "brep-edge", positions: new Float64Array([...corners[a], ...corners[b]]) }));
  const c = Math.cos(Math.PI / 6); const s = Math.sin(Math.PI / 6);
  return {
    schema: "cad-view/1", id: "synthetic-box-assembly", revision: "1", name: "Two instances · six semantic faces each", units: "mm", upAxis: "Z",
    geometries: [{ id: "box", representation: "brep-tessellation", positions: new Float64Array(positions), indices: new Uint32Array(indices),
      triangleFaces: new Int32Array(labels), faces: quads.map((_, index) => ({ id: `face-${index}`, kind: "brep-face", label: `Planar face ${index}` })), edges,
      metadata: { fixture: true, authority: "Synthetic example only; no CAD kernel validation performed" } }],
    nodes: [
      { id: "assembly", name: "Assembly", transform: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 1e9, -2e9, 3e9, 1] },
      { id: "left", name: "Left box", parentId: "assembly", geometryId: "box", transform: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -30, -5, 0, 1] },
      { id: "right", name: "Rotated box", parentId: "assembly", geometryId: "box", transform: [c, s, 0, 0, -s, c, 0, 0, 0, 0, 1, 0, 30, 8, 5, 1] },
    ],
  };
}
