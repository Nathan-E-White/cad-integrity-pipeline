/** CPU-side interchange model. No Three.js, Solid, transport, or CAD-kernel types. */
export type Vec3 = readonly [number, number, number];
/** Column-major, affine, right-handed coordinates; may include a reflection. */
export type Mat4 = readonly number[];
export type Coordinates = Float32Array | Float64Array;
export type Metadata = Readonly<Record<string, unknown>>;
export type LengthUnit = "m" | "mm" | "cm" | "um" | "in" | "ft" | "unknown";

export interface FaceRef {
  readonly id: string;
  readonly kind: "brep-face" | "mesh-region";
  readonly label?: string;
  readonly metadata?: Metadata;
}

export interface EdgePolyline {
  readonly id: string;
  readonly kind: "brep-edge" | "mesh-edge";
  /** Consecutive XYZ triples in geometry-local coordinates. Repeat the first point to close. */
  readonly positions: Coordinates;
  readonly metadata?: Metadata;
}

export interface GeometryAsset {
  readonly id: string;
  readonly representation: "mesh" | "brep-tessellation";
  readonly positions: Coordinates;
  /** Indexed triangles, zero-based. Triangle order is NEVER changed by the viewer. */
  readonly indices: Uint32Array;
  readonly normals?: Float32Array;
  /** Original parameter coordinates, NOT assumed to lie in [0, 1]. */
  readonly uv?: Coordinates;
  readonly vertexIds?: readonly string[];
  readonly faces?: readonly FaceRef[];
  /** One entry per triangle: index into faces, or -1 for unmapped. */
  readonly triangleFaces?: Int32Array;
  readonly edges?: readonly EdgePolyline[];
  readonly color?: string;
  /** Opaque reference to the authoritative shape; never interpreted or fetched here. */
  readonly native?: {
    readonly provider: string;
    readonly key: string;
    readonly revision: string;
  };
  readonly metadata?: Metadata;
}

export interface ModelNode {
  readonly id: string;
  readonly name: string;
  readonly parentId?: string;
  /** Omit for an assembly/group node. Multiple nodes may share an asset. */
  readonly geometryId?: string;
  readonly transform?: Mat4;
  readonly visible?: boolean;
  readonly metadata?: Metadata;
}

export interface ModelDocument {
  readonly schema: "cad-view/1";
  readonly id: string;
  /** New immutable snapshot / tessellation => new revision. */
  readonly revision: string;
  readonly name: string;
  /** All positions AND translations use this one unit. Convert mixed-unit input upstream. */
  readonly units: LengthUnit;
  readonly upAxis: "Y" | "Z";
  readonly geometries: readonly GeometryAsset[];
  readonly nodes: readonly ModelNode[];
  readonly metadata?: Metadata;
}

export interface SelectionIdentity {
  readonly documentId: string;
  readonly revision: string;
  readonly nodeId: string;
  readonly geometryId: string;
}
export type Selection = SelectionIdentity & (
  | { readonly kind: "object" }
  | { readonly kind: "triangle"; readonly triangleIndex: number }
  | { readonly kind: "face"; readonly faceId: string; readonly faceKind: FaceRef["kind"] }
  | { readonly kind: "edge"; readonly edgeId: string; readonly edgeKind: EdgePolyline["kind"] }
);
export type SelectionMode = "object" | "face" | "edge" | "triangle";
export interface PickResult {
  readonly selection: Selection;
  /** In the ORIGINAL document coordinate system, before display rebasing. Approximate. */
  readonly point: Vec3;
  readonly triangleIndex?: number;
}

export interface ModelLimits {
  readonly maxGeometries: number;
  readonly maxNodes: number;
  readonly maxVertices: number;
  readonly maxTriangles: number;
  readonly maxEdgePoints: number;
  readonly maxDrawnTriangles: number;
}
export const DEFAULT_MODEL_LIMITS: ModelLimits = {
  maxGeometries: 10_000,
  maxNodes: 20_000,
  maxVertices: 5_000_000,
  maxTriangles: 5_000_000,
  maxEdgePoints: 5_000_000,
  maxDrawnTriangles: 10_000_000,
};

export class ModelValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ModelValidationError";
  }
}
export function invariant(condition: unknown, message: string): asserts condition {
  if (!condition) throw new ModelValidationError(message);
}
function checkId(value: unknown, path: string): asserts value is string {
  invariant(typeof value === "string" && value.length > 0 && value.length <= 512, `${path}: invalid ID`);
}
function checkCoordinates(value: unknown, stride: number, path: string): asserts value is Coordinates {
  invariant(value instanceof Float32Array || value instanceof Float64Array, `${path}: expected float array`);
  invariant(value.length % stride === 0, `${path}: length must be divisible by ${stride}`);
  for (const number of value) invariant(Number.isFinite(number) && Math.abs(number) <= 1e30, `${path}: nonfinite/out-of-range coordinate`);
}
export function validateTransform(value: Mat4, path = "transform"): void {
  invariant(value.length === 16 && value.every(Number.isFinite), `${path}: expected 16 finite values`);
  invariant(value[3] === 0 && value[7] === 0 && value[11] === 0 && value[15] === 1, `${path}: projective transforms are unsupported`);
  const d = value[0] * (value[5] * value[10] - value[9] * value[6])
    - value[4] * (value[1] * value[10] - value[9] * value[2])
    + value[8] * (value[1] * value[6] - value[5] * value[2]);
  invariant(Number.isFinite(d) && d !== 0, `${path}: singular transform`);
}

/** Structural/render-safety validation, NOT manifoldness, watertightness, or CAD validity. */
export function validateDocument(doc: ModelDocument, limits: ModelLimits = DEFAULT_MODEL_LIMITS): void {
  invariant(doc?.schema === "cad-view/1", "Unsupported model schema");
  checkId(doc.id, "document.id");
  checkId(doc.revision, "document.revision");
  invariant(typeof doc.name === "string", "document.name: expected string");
  invariant(["m", "mm", "cm", "um", "in", "ft", "unknown"].includes(doc.units), "Invalid length unit");
  invariant(doc.upAxis === "Y" || doc.upAxis === "Z", "Invalid up axis");
  invariant(Array.isArray(doc.geometries) && doc.geometries.length <= limits.maxGeometries, "Too many geometries");
  invariant(Array.isArray(doc.nodes) && doc.nodes.length <= limits.maxNodes, "Too many nodes");
  const assets = new Map<string, GeometryAsset>();
  let vertices = 0;
  let triangles = 0;
  let edgePoints = 0;
  for (const asset of doc.geometries) {
    checkId(asset.id, "geometry.id");
    invariant(!assets.has(asset.id), `Duplicate geometry ID: ${asset.id}`);
    assets.set(asset.id, asset);
    invariant(asset.representation === "mesh" || asset.representation === "brep-tessellation", "Invalid representation");
    checkCoordinates(asset.positions, 3, `${asset.id}.positions`);
    const count = asset.positions.length / 3;
    vertices += count;
    invariant(vertices <= limits.maxVertices, "Vertex budget exceeded");
    invariant(asset.indices instanceof Uint32Array && asset.indices.length % 3 === 0, "Invalid triangle indices");
    triangles += asset.indices.length / 3;
    invariant(triangles <= limits.maxTriangles, "Triangle budget exceeded");
    for (const index of asset.indices) invariant(index < count, `${asset.id}: out-of-bounds index ${index}`);
    if (asset.normals) {
      checkCoordinates(asset.normals, 3, "normals");
      invariant(asset.normals instanceof Float32Array && asset.normals.length === asset.positions.length, "Invalid normal count/type");
    }
    if (asset.uv) {
      checkCoordinates(asset.uv, 2, "uv");
      invariant(asset.uv.length === count * 2, "Invalid UV count");
    }
    if (asset.vertexIds) {
      invariant(asset.vertexIds.length === count, "Invalid vertex ID count");
      for (const id of asset.vertexIds) checkId(id, "vertexId");
    }
    const faces = new Set<string>();
    for (const face of asset.faces ?? []) {
      checkId(face.id, "face.id");
      invariant(!faces.has(face.id), "Duplicate face ID");
      faces.add(face.id);
      invariant(face.kind === "brep-face" || face.kind === "mesh-region", "Invalid face kind");
    }
    if (asset.triangleFaces) {
      invariant(asset.triangleFaces instanceof Int32Array && asset.triangleFaces.length === asset.indices.length / 3, "Invalid triangle-face map");
      for (const face of asset.triangleFaces) invariant(face >= -1 && face < (asset.faces?.length ?? 0), "Invalid face table index");
    }
    const edges = new Set<string>();
    for (const edge of asset.edges ?? []) {
      checkId(edge.id, "edge.id");
      invariant(!edges.has(edge.id), "Duplicate edge ID");
      edges.add(edge.id);
      invariant(edge.kind === "brep-edge" || edge.kind === "mesh-edge", "Invalid edge kind");
      checkCoordinates(edge.positions, 3, "edge.positions");
      invariant(edge.positions.length >= 6, "An edge needs at least two points");
      edgePoints += edge.positions.length / 3;
      invariant(edgePoints <= limits.maxEdgePoints, "Edge point budget exceeded");
    }
    if (asset.color) invariant(/^#[\da-fA-F]{6}$/.test(asset.color), "Colors must be #RRGGBB");
  }
  const nodes = new Map<string, ModelNode>();
  let drawnTriangles = 0;
  for (const node of doc.nodes) {
    checkId(node.id, "node.id");
    invariant(typeof node.name === "string", "Invalid node name");
    invariant(!nodes.has(node.id), `Duplicate node ID: ${node.id}`);
    nodes.set(node.id, node);
    if (node.geometryId !== undefined) {
      const asset = assets.get(node.geometryId);
      invariant(asset, `Missing geometry: ${node.geometryId}`);
      drawnTriangles += asset.indices.length / 3;
      invariant(drawnTriangles <= limits.maxDrawnTriangles, "Instanced triangle budget exceeded");
    }
    if (node.transform) validateTransform(node.transform, node.id);
  }
  // Iterative walk: deep/malicious assembly trees cannot overflow the call stack.
  const completed = new Set<string>();
  for (const start of doc.nodes) {
    const path = new Set<string>();
    let node: ModelNode | undefined = start;
    while (node && !completed.has(node.id)) {
      invariant(!path.has(node.id), `Assembly cycle at ${node.id}`);
      path.add(node.id);
      if (node.parentId === undefined) break;
      const parent: ModelNode | undefined = nodes.get(node.parentId);
      invariant(parent, `Missing parent: ${node.parentId}`);
      node = parent;
    }
    for (const id of path) completed.add(id);
  }
}
