import type { CoordinateFrame } from "./types.ts";

export function coordinateFrame(positions: readonly number[]): CoordinateFrame {
  if (!positions.length) return { origin: [0, 0, 0], scale: 1 };
  const lo = [Infinity, Infinity, Infinity];
  const hi = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < positions.length; i++) {
    const axis = i % 3;
    lo[axis] = Math.min(lo[axis], positions[i]);
    hi[axis] = Math.max(hi[axis], positions[i]);
  }
  const origin = lo.map((v, i) => v / 2 + hi[i] / 2) as [number, number, number];
  const scale = Math.max(...lo.map((v, i) => hi[i] / 2 - v / 2)) || 1;
  return { origin, scale };
}

export function localCoordinate(value: number, axis: number, frame: CoordinateFrame): number {
  // Subtract before float32 conversion to preserve small details at large origins.
  const difference = value - frame.origin[axis];
  const result = Number.isFinite(difference)
    ? difference / frame.scale
    : value / frame.scale - frame.origin[axis] / frame.scale;
  if (!Number.isFinite(result) || Math.abs(result) > 3.4028234663852886e38) {
    throw new Error("Coordinates are not representable in this render frame.");
  }
  return result;
}

export function localPositions(world: readonly number[], frame: CoordinateFrame): Float32Array {
  const result = new Float32Array(world.length);
  for (let i = 0; i < world.length; i++) result[i] = localCoordinate(world[i], i % 3, frame);
  return result;
}
