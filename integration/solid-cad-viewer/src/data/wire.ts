import { invariant, type Coordinates, type EdgePolyline, type FaceRef, type GeometryAsset, type LengthUnit, type Metadata, type ModelDocument, validateDocument } from "../model";
function record(value: unknown): Record<string, unknown> { invariant(value !== null && typeof value === "object" && !Array.isArray(value), "Expected object"); return value as Record<string, unknown>; }
function text(value: unknown): string { invariant(typeof value === "string", "Expected string"); return value; }
function optionalText(value: unknown): string | undefined { return value === undefined ? undefined : text(value); }
function list(value: unknown): unknown[] { invariant(Array.isArray(value), "Expected array"); return value; }
function numbers(value: unknown, integer = false, min = -Infinity, max = Infinity): number[] {
  const items = list(value);
  invariant(items.length <= 15_000_000, "Numeric array exceeds element budget");
  for (const item of items) invariant(typeof item === "number" && Number.isFinite(item) && item >= min && item <= max && (!integer || Number.isSafeInteger(item)), "Invalid numeric array value");
  return items as number[];
}
function floats(value: unknown): Float64Array { return Float64Array.from(numbers(value)); }
function optionalFloats(value: unknown): Coordinates | undefined { return value === undefined ? undefined : floats(value); }
function metadata(value: unknown): Metadata | undefined { return value === undefined ? undefined : record(value); }
function faceKind(value: unknown): FaceRef["kind"] { invariant(value === "brep-face" || value === "mesh-region", "Invalid face kind"); return value; }
function edgeKind(value: unknown): EdgePolyline["kind"] { invariant(value === "brep-edge" || value === "mesh-edge", "Invalid edge kind"); return value; }

/** JSON is a simple reference transport; large deployments can replace it with binary buffers. */
export function decodeDocument(input: unknown): ModelDocument {
  const wire = record(input);
  invariant(wire.schema === "cad-view/1", "Unsupported model schema");
  const rawAssets = list(wire.geometries);
  const rawNodes = list(wire.nodes);
  invariant(rawAssets.length <= 10_000 && rawNodes.length <= 20_000, "Model object budget exceeded");
  const geometries: GeometryAsset[] = rawAssets.map((value) => {
    const asset = record(value);
    invariant(asset.representation === "mesh" || asset.representation === "brep-tessellation", "Invalid representation");
    const native = asset.native === undefined ? undefined : record(asset.native);
    return {
      id: text(asset.id), representation: asset.representation, positions: floats(asset.positions),
      // Validate BEFORE conversion: typed-array constructors would silently truncate/wrap bad indices.
      indices: Uint32Array.from(numbers(asset.indices, true, 0, 0xffffffff)),
      normals: asset.normals === undefined ? undefined : Float32Array.from(numbers(asset.normals)),
      uv: optionalFloats(asset.uv),
      vertexIds: asset.vertexIds === undefined ? undefined : list(asset.vertexIds).map(text),
      triangleFaces: asset.triangleFaces === undefined ? undefined : Int32Array.from(numbers(asset.triangleFaces, true, -1, 0x7fffffff)),
      faces: asset.faces === undefined ? undefined : list(asset.faces).map((value) => {
        const face = record(value);
        return { id: text(face.id), kind: faceKind(face.kind), label: optionalText(face.label), metadata: metadata(face.metadata) };
      }),
      edges: asset.edges === undefined ? undefined : list(asset.edges).map((value) => {
        const edge = record(value);
        return { id: text(edge.id), kind: edgeKind(edge.kind), positions: floats(edge.positions), metadata: metadata(edge.metadata) };
      }),
      color: optionalText(asset.color), metadata: metadata(asset.metadata),
      native: native ? { provider: text(native.provider), key: text(native.key), revision: text(native.revision) } : undefined,
    };
  });
  const unit = text(wire.units);
  invariant(["m", "mm", "cm", "um", "in", "ft", "unknown"].includes(unit), "Invalid units");
  invariant(wire.upAxis === "Y" || wire.upAxis === "Z", "Invalid up axis");
  const doc: ModelDocument = {
    schema: "cad-view/1", id: text(wire.id), revision: text(wire.revision), name: text(wire.name), units: unit as LengthUnit,
    upAxis: wire.upAxis, geometries, metadata: metadata(wire.metadata),
    nodes: rawNodes.map((value) => {
      const node = record(value);
      invariant(node.visible === undefined || typeof node.visible === "boolean", "Invalid visibility");
      return { id: text(node.id), name: text(node.name), parentId: optionalText(node.parentId), geometryId: optionalText(node.geometryId),
        transform: node.transform === undefined ? undefined : numbers(node.transform), visible: node.visible,
        metadata: metadata(node.metadata) };
    }),
  };
  validateDocument(doc);
  return doc;
}
export function encodeDocument(doc: ModelDocument) {
  validateDocument(doc);
  return {
    ...doc,
    geometries: doc.geometries.map((asset) => ({ ...asset,
      positions: Array.from(asset.positions), indices: Array.from(asset.indices),
      normals: asset.normals ? Array.from(asset.normals) : undefined,
      uv: asset.uv ? Array.from(asset.uv) : undefined,
      triangleFaces: asset.triangleFaces ? Array.from(asset.triangleFaces) : undefined,
      edges: asset.edges?.map((edge) => ({ ...edge, positions: Array.from(edge.positions) })),
    })),
  };
}
