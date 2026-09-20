import type { MeshPayload } from "./contracts.js";
export type Vec3 = [number, number, number];
export interface Bounds { min: Vec3; max: Vec3 }
export interface DisplayFrame { origin: Vec3; scale: number }
export const clamp = (x: number, lo: number, hi: number): number => Math.max(lo, Math.min(hi, x));
export function boundsOf(positions: ArrayLike<number>): Bounds | null {
  if (positions.length === 0) return null;
  const min: Vec3 = [Infinity, Infinity, Infinity], max: Vec3 = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < positions.length; i++) {
    const k = i % 3;
    min[k] = Math.min(min[k], positions[i]); max[k] = Math.max(max[k], positions[i]);
  }
  return { min, max };
}
export function boundsFor(meshes: readonly MeshPayload[]): Bounds | null {
  const min: Vec3 = [Infinity, Infinity, Infinity], max: Vec3 = [-Infinity, -Infinity, -Infinity];
  let found = false;
  for (const mesh of meshes) {
    for (const values of [mesh.positions, ...mesh.paths.map(p => p.points), ...mesh.selections.map(s => s.segments)]) {
      const b = boundsOf(values); if (!b) continue; found = true;
      for (let k = 0; k < 3; k++) { min[k] = Math.min(min[k], b.min[k]); max[k] = Math.max(max[k], b.max[k]); }
    }
  }
  return found ? { min, max } : null;
}
export function frameFor(meshes: readonly MeshPayload[]): DisplayFrame {
  const bounds = boundsFor(meshes);
  if (!bounds) return { origin: [0, 0, 0], scale: 1 };
  const { min, max } = bounds;
  const origin = min.map((x, k) => x / 2 + max[k] / 2) as Vec3;
  const radius = Math.hypot(...min.map((x, k) => max[k] / 2 - x / 2));
  if (!Number.isFinite(radius)) throw new Error("Coordinate span exceeds display arithmetic range");
  return { origin, scale: radius > 0 ? radius : 1 };
}
export function toDisplay(point: ArrayLike<number>, frame: DisplayFrame): Vec3 {
  // Subtract in JS Float64 BEFORE the Float32 GPU conversion.
  return [(point[0] - frame.origin[0]) / frame.scale, (point[1] - frame.origin[1]) / frame.scale, (point[2] - frame.origin[2]) / frame.scale];
}
export function displayPositions(positions: ArrayLike<number>, frame: DisplayFrame): Float32Array {
  const result = new Float32Array(positions.length);
  for (let i = 0; i < result.length; i++) {
    const x = (positions[i] - frame.origin[i % 3]) / frame.scale;
    if (!Number.isFinite(x) || Math.abs(x) > 3.4e38) throw new Error("Coordinate is not representable in display frame");
    result[i] = x;
  }
  return result;
}
/** Keep source coordinate x_axis <= offset. Returned plane is in display coordinates. */
export function clippingPlane(axis: 0 | 1 | 2, offset: number, frame: DisplayFrame): [number, number, number, number] {
  const p: [number, number, number, number] = [0, 0, 0, (offset - frame.origin[axis]) / frame.scale];
  p[axis] = -1;
  return p;
}
export function shrinkPoint(point: Vec3, center: Vec3, factor: number): Vec3 {
  return point.map((p, k) => center[k] + factor * (p - center[k])) as Vec3;
}
export function fitDistance(radius: number, verticalFovDegrees: number, aspect: number, padding = 1.15): number {
  const v = verticalFovDegrees * Math.PI / 360;
  const h = Math.atan(Math.tan(v) * Math.max(aspect, 1e-6));
  return Math.max(radius, 1e-5) * padding / Math.sin(Math.min(v, h));
}
export function pulseOpacity(seconds: number): number { return 0.85 + 0.15 * Math.sin(2 * Math.PI * 0.8 * seconds); }
