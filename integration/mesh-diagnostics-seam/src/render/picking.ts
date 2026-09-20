import * as THREE from "three";
import { clippingPlane } from "../core/math.js";
import type { InspectionState } from "../core/state.js";
import type { SurfaceLayer } from "./SurfaceLayer.js";

/** Click-only O(F) reference picker. Applies the SAME shrink/clip/centroid filter
 * as the shader. A future BVH must use conservative bounds plus exact filtering.
 * Standard Mesh.raycast would pick the undeformed, unfiltered triangles instead.
 */
export function pickTriangle(layer: SurfaceLayer, ray: THREE.Ray, state: InspectionState,
                             hasSelection: boolean): number | null {
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  const center = new THREE.Vector3(), point = new THREE.Vector3();
  const plane = clippingPlane(state.clipAxis, state.clipOffset, layer.frame);
  let best = Infinity, faceId: number | null = null;
  for (let face = 0; face < layer.positions.length / 9; face++) {
    if (state.isolate && hasSelection && !layer.selectedFaces.has(face)) continue;
    const start = face * 9;
    center.fromArray(layer.centers, start);
    if (state.peelEnabled && center.distanceTo(layer.center) > layer.radius * state.radialFraction) continue;
    a.fromArray(layer.positions, start).sub(center).multiplyScalar(state.shrink).add(center);
    b.fromArray(layer.positions, start + 3).sub(center).multiplyScalar(state.shrink).add(center);
    c.fromArray(layer.positions, start + 6).sub(center).multiplyScalar(state.shrink).add(center);
    if (!ray.intersectTriangle(a, b, c, false, point)) continue;
    if (state.clipEnabled && plane[0] * point.x + plane[1] * point.y + plane[2] * point.z + plane[3] < 0) continue;
    const distance = point.distanceToSquared(ray.origin);
    if (distance < best) { best = distance; faceId = face; }
  }
  return faceId;
}
