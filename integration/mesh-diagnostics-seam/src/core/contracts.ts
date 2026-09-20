/** Wire contract v1. Face IDs are offsets in THIS mesh revision's triangle array. */
export type Status = "info" | "pass" | "warn" | "fail" | "unknown";
export interface ScalarField {
  id: string; label: string; association: "face"; values: (number | null)[];
  domain: [number, number]; better: "higher" | "lower" | "neither"; unit: string | null;
}
export interface Trace {
  id: string; label: string; points: number[];
  status: "active" | "terminated" | "cycle_detected" | "iteration_limit" | "unknown";
  termination_reason: string | null;
  provenance: "computed" | "imported" | "synthetic_fixture";
}
export interface Selection {
  id: string; label: string; face_ids: number[]; edge_pairs: number[];
  segments: number[]; path_ids: string[];
}
export interface Metric {
  id: string; label: string; value: number | string | null; status: Status;
  selection_id: string | null; scope: string;
}
export interface MeshPayload {
  id: string; revision: string; label: string; frame_id: string; length_unit: string | null;
  positions: number[]; triangles: number[]; triangle_source_faces: number[] | null;
  fields: ScalarField[]; selections: Selection[]; metrics: Metric[]; paths: Trace[]; provenance: string;
}
export interface InspectorDocument { schema_version: 1; meshes: MeshPayload[]; linked_views: boolean }
export class PayloadError extends Error { override name = "PayloadError"; }
const MAX_V = 500_000, MAX_F = 250_000, MAX_PATH_POINTS = 500_000;
type RecordValue = Record<string, unknown>;
function fail(message: string): never { throw new PayloadError(message); }
function object(x: unknown, at: string): RecordValue {
  if (!x || typeof x !== "object" || Array.isArray(x)) fail(`${at}: expected object`);
  return x as RecordValue;
}
function text(x: unknown, at: string, max = 1024, min = 1): string {
  if (typeof x !== "string" || x.length < min || x.length > max * 2) fail(`${at}: invalid string`);
  // Python limits count Unicode code points, not UTF-16 code units.
  let length = 0;
  for (const _ of x) if (++length > max) fail(`${at}: invalid string`);
  return x;
}
function nullableText(x: unknown, at: string, max = 1024, min = 0): string | null { return x == null ? null : text(x, at, max, min); }
function finite(x: unknown, at: string): number {
  if (typeof x !== "number" || !Number.isFinite(x)) fail(`${at}: expected finite number`);
  return x;
}
function list(x: unknown, at: string, max: number): unknown[] {
  if (!Array.isArray(x) || x.length > max) fail(`${at}: expected bounded array (max ${max})`);
  return x;
}
function numbers(x: unknown, at: string, stride: number, max: number, integer = false): number[] {
  const a = list(x, at, max);
  if (a.length % stride) fail(`${at}: incomplete group of ${stride}`);
  return a.map((v, i) => {
    const n = finite(v, `${at}[${i}]`);
    if (integer && (!Number.isSafeInteger(n) || n < 0)) fail(`${at}[${i}]: expected nonnegative integer`);
    return n;
  });
}
function choice<T extends string>(x: unknown, choices: readonly T[], at: string): T {
  if (typeof x !== "string" || !choices.includes(x as T)) fail(`${at}: unsupported value`);
  return x as T;
}
function unique<T extends { id: string }>(a: T[], at: string): T[] {
  if (new Set(a.map(v => v.id)).size !== a.length) fail(`${at}: duplicate IDs`);
  return a;
}
function keys(x: RecordValue, allowed: string[], at: string): void {
  for (const key of Object.keys(x)) if (!allowed.includes(key)) fail(`${at}: unexpected key ${key}`);
}

function checkAggregateBudgets(o: RecordValue): void {
  // Inspect lengths only: no numeric array has been copied at this point.
  for (const [name, columns, itemLimit, totalLimit, message] of [
    ["paths", ["points"], 10_000, MAX_PATH_POINTS * 3, "Total path point budget exceeded"],
    ["selections", ["face_ids", "edge_pairs", "segments"], 256, 8_000_000, "Selection data budget exceeded"],
  ] as const) {
    const items = list(o[name] ?? [], name, itemLimit);
    let total = 0;
    for (const item of items) {
      const record = object(item, name);
      for (const column of columns) {
        const values = record[column];
        if (Array.isArray(values)) total += values.length;
        if (total > totalLimit) fail(message);
      }
    }
  }
}

function parseMesh(value: unknown, index: number): MeshPayload {
  const at = `meshes[${index}]`, o = object(value, at);
  keys(o, ["id", "revision", "label", "frame_id", "length_unit", "positions", "triangles", "triangle_source_faces", "fields", "selections", "metrics", "paths", "provenance"], at);
  checkAggregateBudgets(o);
  const positions = numbers(o.positions, `${at}.positions`, 3, MAX_V * 3);
  const triangles = numbers(o.triangles, `${at}.triangles`, 3, MAX_F * 3, true);
  const nv = positions.length / 3, nf = triangles.length / 3;
  if (triangles.some(i => i >= nv)) fail(`${at}: triangle index out of range`);
  const fields = unique(list(o.fields ?? [], `${at}.fields`, 32).map(v => {
    const f = object(v, "field");
    keys(f, ["id", "label", "association", "values", "domain", "better", "unit"], "field");
    const values = list(f.values, "field.values", MAX_F).map(v => v === null ? null : finite(v, "field.value"));
    if (values.length !== nf) fail("Field length does not match triangle count");
    const domain = numbers(f.domain ?? [0, 1], "field.domain", 2, 2) as [number, number];
    if (domain.length !== 2 || domain[0] >= domain[1] || !Number.isFinite(domain[1] - domain[0])) fail("Scalar domain must be increasing");
    return { id: text(f.id, "field.id", 128), label: text(f.label, "field.label", 256),
      association: choice(f.association ?? "face", ["face"], "association"), values, domain,
      better: choice(f.better ?? "neither", ["higher", "lower", "neither"], "better"), unit: nullableText(f.unit, "unit") };
  }), "fields");
  const paths = unique(list(o.paths ?? [], "paths", 10_000).map(v => {
    const p = object(v, "path");
    keys(p, ["id", "label", "points", "status", "termination_reason", "provenance"], "path");
    const points = numbers(p.points, "path.points", 3, MAX_PATH_POINTS * 3);
    if (points.length < 6) fail("Paths need at least two points");
    return { id: text(p.id, "path.id", 128), label: text(p.label, "path.label", 256), points,
      status: choice(p.status ?? "unknown", ["active", "terminated", "cycle_detected", "iteration_limit", "unknown"], "path.status"),
      termination_reason: nullableText(p.termination_reason, "termination_reason", 512),
      provenance: choice(p.provenance ?? "imported", ["computed", "imported", "synthetic_fixture"], "provenance") };
  }), "paths");
  const pathIds = new Set(paths.map(p => p.id));
  const selections = unique(list(o.selections ?? [], "selections", 256).map(v => {
    const s = object(v, "selection");
    keys(s, ["id", "label", "face_ids", "edge_pairs", "segments", "path_ids"], "selection");
    const face_ids = numbers(s.face_ids ?? [], "selection.face_ids", 1, MAX_F, true);
    const edge_pairs = numbers(s.edge_pairs ?? [], "selection.edge_pairs", 2, MAX_F * 6, true);
    const segments = numbers(s.segments ?? [], "selection.segments", 6, MAX_F * 18);
    const path_ids = list(s.path_ids ?? [], "selection.path_ids", 10_000).map(p => text(p, "path reference", 128));
    if (new Set(face_ids).size !== face_ids.length || face_ids.some(f => f >= nf)) fail("Invalid selection face IDs");
    if (edge_pairs.some(i => i >= nv) || path_ids.some(id => !pathIds.has(id))) fail("Invalid selection edge/path reference");
    return { id: text(s.id, "selection.id", 128), label: text(s.label, "selection.label", 256), face_ids, edge_pairs, segments, path_ids };
  }), "selections");
  const selectionIds = new Set(selections.map(s => s.id));
  const metrics = unique(list(o.metrics ?? [], "metrics", 256).map(v => {
    const m = object(v, "metric");
    keys(m, ["id", "label", "value", "status", "selection_id", "scope"], "metric");
    const selection_id = nullableText(m.selection_id, "selection_id", 128, 1);
    if (selection_id && !selectionIds.has(selection_id)) fail("Metric references missing selection");
    const val = m.value == null ? null : typeof m.value === "string" ? text(m.value, "metric.value", 1024, 0) : finite(m.value, "metric.value");
    return { id: text(m.id, "metric.id", 128), label: text(m.label, "metric.label", 256), value: val,
      status: choice(m.status ?? "info", ["info", "pass", "warn", "fail", "unknown"], "metric.status"),
      selection_id, scope: text(m.scope ?? "Display diagnostic; not solver/CAD certification", "scope", 1024, 0) };
  }), "metrics");
  const source = o.triangle_source_faces == null ? null : numbers(o.triangle_source_faces, "triangle_source_faces", 1, MAX_F, true);
  if (source && source.length !== nf) fail("Invalid triangle/source face mapping length");
  return { id: text(o.id, `${at}.id`, 128), revision: text(o.revision, "revision", 128), label: text(o.label, "label", 256),
    frame_id: text(o.frame_id, "frame_id", 128), length_unit: nullableText(o.length_unit, "length_unit", 32),
    positions, triangles, triangle_source_faces: source, fields, selections, metrics, paths,
    provenance: text(o.provenance ?? "Imported triangle display mesh", "provenance", 1024, 0) };
}

export function parseDocument(value: unknown): InspectorDocument {
  if (value == null) return { schema_version: 1, meshes: [], linked_views: true };
  const o = object(value, "document");
  keys(o, ["schema_version", "meshes", "linked_views"], "document");
  if (o.schema_version !== 1) fail("Unsupported or missing schema_version");
  const meshes = unique(list(o.meshes, "meshes", 2).map(parseMesh), "meshes");
  const linked = o.linked_views ?? true;
  if (typeof linked !== "boolean") fail("linked_views must be boolean");
  if (linked && meshes.length === 2 && (meshes[0].frame_id !== meshes[1].frame_id || meshes[0].length_unit !== meshes[1].length_unit)) {
    fail("Linked views require the same frame_id and length_unit; registration is not inferred");
  }
  if (linked && meshes.length === 2) {
    for (const field of meshes[0].fields) {
      const other = meshes[1].fields.find(f => f.id === field.id);
      if (other && (field.domain[0] !== other.domain[0] || field.domain[1] !== other.domain[1] || field.unit !== other.unit)) fail("Compared fields require a shared domain and unit");
    }
  }
  return { schema_version: 1, meshes, linked_views: linked };
}
