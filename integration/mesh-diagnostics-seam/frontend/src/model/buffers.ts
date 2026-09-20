import { localPositions } from "./frame.ts";
import type { MeshDocument, Target } from "./types.ts";

export function trianglePositions(doc: MeshDocument, ids: readonly number[]): Float32Array {
  const positions = new Float32Array(ids.length * 9);
  for (let i = 0; i < ids.length; i++) {
    for (let corner = 0; corner < 3; corner++) {
      const source = doc.triangles[3 * ids[i] + corner] * 3;
      for (let axis = 0; axis < 3; axis++) positions[9*i + 3*corner + axis] = doc.positions[source + axis];
    }
  }
  return positions;
}
export function edgePositions(doc: MeshDocument, target: Exclude<Target, { kind: "faces" }>): Float32Array {
  if (target.kind === "segments") return localPositions(target.positions, doc.frame);
  const result = new Float32Array(target.indices.length * 3);
  for (let i = 0; i < target.indices.length; i++) {
    const index = target.indices[i] * 3;
    for (let axis = 0; axis < 3; axis++) result[i*3 + axis] = doc.positions[index + axis];
  }
  return result;
}
export function triangleEdgePositions(positions: Float32Array): Float32Array {
  const out = new Float32Array(positions.length * 2);
  const corners = [0, 1, 1, 2, 2, 0];
  for (let face = 0; face < positions.length / 9; face++) {
    for (let end = 0; end < 6; end++) {
      for (let axis = 0; axis < 3; axis++) out[face*18 + end*3 + axis] = positions[face*9 + corners[end]*3 + axis];
    }
  }
  return out;
}
