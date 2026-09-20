import { invariant, type Mat4, type ModelDocument, type Vec3 } from "./model";
export const IDENTITY: Mat4 = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
export function multiply(a: Mat4, b: Mat4): number[] {
  const result = new Array<number>(16).fill(0);
  for (let col = 0; col < 4; col++) for (let row = 0; row < 4; row++)
    for (let k = 0; k < 4; k++) result[col * 4 + row] += a[k * 4 + row] * b[col * 4 + k];
  return result;
}
export function transformPoint(m: Mat4, x: number, y: number, z: number): Vec3 {
  return [m[0] * x + m[4] * y + m[8] * z + m[12], m[1] * x + m[5] * y + m[9] * z + m[13], m[2] * x + m[6] * y + m[10] * z + m[14]];
}
/** Call validateDocument before this helper. */
export function worldTransforms(doc: ModelDocument): ReadonlyMap<string, Mat4> {
  const nodes = new Map(doc.nodes.map((node) => [node.id, node]));
  const result = new Map<string, Mat4>();
  for (const node of doc.nodes) {
    const path: typeof node[] = [];
    let current: typeof node | undefined = node;
    const seen = new Set<string>();
    while (current && !result.has(current.id)) {
      invariant(!seen.has(current.id), "Assembly cycle");
      seen.add(current.id);
      path.push(current);
      current = current.parentId === undefined ? undefined : nodes.get(current.parentId);
    }
    let parent = current ? result.get(current.id) ?? IDENTITY : IDENTITY;
    for (let i = path.length - 1; i >= 0; i--) {
      parent = multiply(parent, path[i].transform ?? IDENTITY);
      result.set(path[i].id, parent);
    }
  }
  return result;
}
export interface Bounds { min: Vec3; max: Vec3; }
export function boundsOf(values: ArrayLike<number>): Bounds | null {
  if (values.length === 0) return null;
  const min: [number, number, number] = [Infinity, Infinity, Infinity];
  const max: [number, number, number] = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < values.length; i += 3) for (let j = 0; j < 3; j++) {
    min[j] = Math.min(min[j], values[i + j]);
    max[j] = Math.max(max[j], values[i + j]);
  }
  return { min, max };
}
export function centerOf(bounds: Bounds | null): Vec3 {
  return bounds ? bounds.min.map((x, i) => x / 2 + bounds.max[i] / 2) as unknown as Vec3 : [0, 0, 0];
}
export function documentBounds(doc: ModelDocument, transforms = worldTransforms(doc)): Bounds | null {
  const assets = new Map(doc.geometries.map((asset) => [asset.id, asset]));
  const min: [number, number, number] = [Infinity, Infinity, Infinity];
  const max: [number, number, number] = [-Infinity, -Infinity, -Infinity];
  let found = false;
  for (const node of doc.nodes) {
    const asset = node.geometryId === undefined ? undefined : assets.get(node.geometryId);
    if (!asset) continue;
    const matrix = transforms.get(node.id) ?? IDENTITY;
    for (const coordinates of [asset.positions, ...(asset.edges ?? []).map((edge) => edge.positions)]) {
      for (let i = 0; i < coordinates.length; i += 3) {
        const p = transformPoint(matrix, coordinates[i], coordinates[i + 1], coordinates[i + 2]);
        for (let j = 0; j < 3; j++) {
          invariant(Number.isFinite(p[j]), "World coordinate overflow");
          min[j] = Math.min(min[j], p[j]); max[j] = Math.max(max[j], p[j]);
        }
        found = true;
      }
    }
  }
  return found ? { min, max } : null;
}
/** Camera fit for a bounding sphere. Works with portrait AND landscape viewports. */
export function fitSphere(radius: number, aspect: number, verticalFovDegrees: number, padding = 1.15) {
  invariant(radius >= 0 && Number.isFinite(radius) && aspect > 0 && Number.isFinite(aspect), "Invalid camera fit inputs");
  const vertical = verticalFovDegrees * Math.PI / 360;
  invariant(vertical > 0 && vertical < Math.PI / 2 && padding >= 1, "Invalid FOV/padding");
  const horizontal = Math.atan(Math.tan(vertical) * aspect);
  const r = Math.max(radius, 1e-9);
  return {
    distance: padding * r / Math.sin(Math.min(vertical, horizontal)),
    orthoHalfHeight: padding * r / Math.min(1, aspect),
    radius: r,
  };
}
