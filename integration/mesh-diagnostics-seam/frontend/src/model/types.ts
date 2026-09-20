/** Wire IDs are revision-local. A triangle ID is NOT automatically a B-Rep face ID. */
export type Status = "info" | "pass" | "warn" | "fail" | "not_checked";
export interface Metric {
  id: string;
  label: string;
  value: number | string | null;
  status: Status;
  description: string;
  target_id: string | null;
}
interface TargetBase { id: string; geometry_revision: string }
export type Target =
  | (TargetBase & { kind: "faces"; ids: number[] })
  | (TargetBase & { kind: "edges"; indices: number[] })
  | (TargetBase & { kind: "segments"; positions: number[] });
export interface MeshPayload {
  schema_version: "mesh-diagnostics/1";
  mesh_id: string;
  geometry_revision: string;
  diagnostic_revision: string;
  stage: string;
  units: string;
  positions: number[];
  triangles: number[];
  triangle_parent_faces: number[] | null;
  targets: Target[];
  metrics: Metric[];
  notes: string[];
}
export interface CoordinateFrame {
  /** world = origin + local * scale; normalization is for rendering only. */
  origin: readonly [number, number, number];
  scale: number;
}
export interface MeshDocument {
  payload: MeshPayload;
  frame: CoordinateFrame;
  positions: Float32Array;
  triangles: Uint16Array | Uint32Array;
  targets: ReadonlyMap<string, Target>;
}
export interface MetricSelection {
  mesh_id: string;
  geometry_revision: string;
  diagnostic_revision: string;
  metric_id: string;
  target_id: string;
  metric_index: number;
  selected: boolean;
}
