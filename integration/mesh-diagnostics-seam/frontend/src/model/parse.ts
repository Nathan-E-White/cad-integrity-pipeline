import { coordinateFrame, localPositions } from "./frame.ts";
import type { MeshDocument, MeshPayload, Metric, Status, Target } from "./types.ts";

export class PayloadError extends Error {
  constructor(message: string) { super(message); this.name = "PayloadError"; }
}
function record(value: unknown, at: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new PayloadError(`${at} must be an object`);
  return value as Record<string, unknown>;
}
function text(value: unknown, at: string, max = 256): string {
  if (typeof value !== "string" || !value.length || value.length > max) throw new PayloadError(`${at} must be a nonempty string (max ${max})`);
  return value;
}
function array(value: unknown, at: string, max: number): unknown[] {
  if (!Array.isArray(value) || value.length > max) throw new PayloadError(`${at} must be an array with <= ${max} entries`);
  return value;
}
function numbers(value: unknown, at: string, stride: number, max: number, upper?: number): number[] {
  const input = array(value, at, max);
  if (input.length % stride) throw new PayloadError(`${at} length must be divisible by ${stride}`);
  for (const item of input) {
    if (typeof item !== "number" || !Number.isFinite(item)) throw new PayloadError(`${at} must contain finite numbers`);
    if (upper !== undefined && (!Number.isSafeInteger(item) || item < 0 || item >= upper)) {
      throw new PayloadError(`${at} contains an invalid index`);
    }
  }
  return input.slice() as number[];
}
const statuses = new Set<Status>(["info", "pass", "warn", "fail", "not_checked"]);

/** Validate unknown JSON before constructing unsigned indices or WebGL buffers. */
export function parsePayload(value: unknown): MeshDocument {
  const source = record(value, "payload");
  if (source.schema_version !== "mesh-diagnostics/1") throw new PayloadError("Unsupported mesh diagnostics schema; use the Python legacy adapter first.");
  const mesh_id = text(source.mesh_id, "mesh_id");
  const geometry_revision = text(source.geometry_revision, "geometry_revision");
  const diagnostic_revision = text(source.diagnostic_revision, "diagnostic_revision");
  const positions = numbers(source.positions, "positions", 3, 750_000);
  const vertexCount = positions.length / 3;
  const triangles = numbers(source.triangles, "triangles", 3, 1_500_000, vertexCount);
  const faceCount = triangles.length / 3;
  const triangle_parent_faces = source.triangle_parent_faces == null ? null
    : numbers(source.triangle_parent_faces, "triangle_parent_faces", 1, 500_000, Number.MAX_SAFE_INTEGER + 1);
  if (triangle_parent_faces && triangle_parent_faces.length !== faceCount) throw new PayloadError("triangle_parent_faces length does not match triangles");
  const targets = new Map<string, Target>();
  let targetScalars = 0;
  for (const [i, input] of array(source.targets ?? [], "targets", 128).entries()) {
    const raw = record(input, `targets[${i}]`);
    const id = text(raw.id, "target.id");
    if (targets.has(id)) throw new PayloadError(`Duplicate target ID: ${id}`);
    if (raw.geometry_revision !== geometry_revision) throw new PayloadError(`Target ${id} belongs to a different geometry revision`);
    let target: Target;
    if (raw.kind === "faces") {
      target = { id, geometry_revision, kind: "faces", ids: numbers(raw.ids, `${id}.ids`, 1, 500_000, faceCount) };
      targetScalars += target.ids.length;
    } else if (raw.kind === "edges") {
      target = { id, geometry_revision, kind: "edges", indices: numbers(raw.indices, `${id}.indices`, 2, 3_000_000, vertexCount) };
      targetScalars += target.indices.length;
    } else if (raw.kind === "segments") {
      target = { id, geometry_revision, kind: "segments", positions: numbers(raw.positions, `${id}.positions`, 6, 3_000_000) };
      targetScalars += target.positions.length;
    } else throw new PayloadError(`Unknown target kind: ${String(raw.kind)}`);
    if (targetScalars > 6_000_000) throw new PayloadError("Combined targets exceed the inline budget");
    targets.set(id, target);
  }
  const metricIds = new Set<string>();
  const metrics: Metric[] = array(source.metrics ?? [], "metrics", 512).map((input, i) => {
    const raw = record(input, `metrics[${i}]`);
    const id = text(raw.id, "metric.id");
    if (metricIds.has(id)) throw new PayloadError(`Duplicate metric ID: ${id}`);
    metricIds.add(id);
    if (!statuses.has(raw.status as Status)) throw new PayloadError(`Unknown status for metric ${id}`);
    const v = raw.value;
    if (!(v === null || typeof v === "string" || (typeof v === "number" && Number.isFinite(v)))) throw new PayloadError(`Invalid value for metric ${id}`);
    const target_id = raw.target_id == null ? null : text(raw.target_id, "metric.target_id");
    if (target_id !== null && !targets.has(target_id)) throw new PayloadError(`Unknown target for metric ${id}`);
    const description = raw.description ?? "";
    if (typeof description !== "string" || description.length > 4096) throw new PayloadError(`Invalid description for metric ${id}`);
    return { id, label: text(raw.label, "metric.label"), value: v as number | string | null,
      status: raw.status as Status, target_id, description };
  });
  const payload: MeshPayload = {
    schema_version: "mesh-diagnostics/1", mesh_id, geometry_revision, diagnostic_revision,
    stage: text(source.stage ?? "unspecified", "stage"), units: text(source.units ?? "unspecified", "units"),
    positions, triangles, triangle_parent_faces, targets: [...targets.values()], metrics,
    notes: array(source.notes ?? [], "notes", 128).map((n) => text(n, "note", 4096)),
  };
  const frame = coordinateFrame(positions);
  return {
    payload, frame, positions: localPositions(positions, frame),
    triangles: vertexCount <= 65_536 ? new Uint16Array(triangles) : new Uint32Array(triangles), targets,
  };
}

export function decodePayload(value: unknown): { document: MeshDocument | null; error: string | null } {
  if (value == null) return { document: null, error: null };
  try { return { document: parsePayload(value), error: null }; }
  catch (error) { return { document: null, error: error instanceof Error ? error.message : "Invalid mesh payload" }; }
}
