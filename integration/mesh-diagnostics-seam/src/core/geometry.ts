import type { MeshPayload } from "./contracts.js";
import { displayPositions, type DisplayFrame } from "./math.js";
export interface CornerBuffers { positions: Float32Array; centers: Float32Array; barycentric: Float32Array }
export function cornerBuffers(mesh: MeshPayload, frame: DisplayFrame, byteBudget = 96 * 1024 * 1024): CornerBuffers {
  // Base positions + centers + barycentric + colors + selection, plus canonical
  // position buffer; GPU copies and driver overhead are ADDITIONAL.
  const estimate = mesh.triangles.length * (3 + 3 + 3 + 3 + 1) * 4 + mesh.positions.length * 4;
  if (estimate > byteBudget) throw new Error(`Expanded triangle attributes exceed ${byteBudget} byte budget`);
  const source = displayPositions(mesh.positions, frame);
  const positions = new Float32Array(mesh.triangles.length * 3);
  const centers = new Float32Array(positions.length), barycentric = new Float32Array(positions.length);
  for (let face = 0; face < mesh.triangles.length / 3; face++) {
    const start = face * 9;
    for (let corner = 0; corner < 3; corner++) {
      const i = mesh.triangles[face * 3 + corner] * 3;
      positions.set(source.subarray(i, i + 3), start + corner * 3);
      barycentric[start + corner * 3 + corner] = 1;
    }
    for (let axis = 0; axis < 3; axis++) {
      const center = (positions[start + axis] + positions[start + 3 + axis] + positions[start + 6 + axis]) / 3;
      for (let corner = 0; corner < 3; corner++) centers[start + corner * 3 + axis] = center;
    }
  }
  return { positions, centers, barycentric };
}
export function pathSegments(points: readonly number[]): number[] {
  const out = new Array<number>(Math.max(0, points.length / 3 - 1) * 6);
  for (let i = 0; i < points.length / 3 - 1; i++) for (let k = 0; k < 6; k++) out[i * 6 + k] = points[i * 3 + k];
  return out;
}
