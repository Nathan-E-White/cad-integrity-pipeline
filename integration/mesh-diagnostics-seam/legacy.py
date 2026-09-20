"""Explicit migration boundary for the pasted prototype payloads.

Legacy classifications are preserved only as unverified imported telemetry. The
old 'Jacobian' label is not promoted into a signed-Jacobian claim. For recomputed
metrics use inspect_triangles; for production use adapters over host reports.
"""
from __future__ import annotations
from collections.abc import Mapping
from typing import Any
import numpy as np
from .contracts import Metric, ScalarField, Selection, Trace
from .payload import mesh_payload


def upgrade_legacy_payload(data: Mapping[str, Any], *, mesh_id: str, revision: str,
                           frame_id: str, length_unit: str | None = None,
                           label: str = "Imported prototype snapshot"):
    vertex_keys = {"vertices", "positions"} & data.keys()
    face_keys = {"faces", "indices", "triangles"} & data.keys()
    if len(vertex_keys) != 1 or len(face_keys) != 1:
        raise ValueError("Legacy input needs unambiguous vertex/connectivity keys")
    selections, metrics, fields, paths = [], [], [], []
    if "error_edges" in data:
        edges = np.asarray(data["error_edges"], dtype=float)
        if edges.size % 6:
            raise ValueError("error_edges must contain endpoint coordinate pairs")
        selections.append(Selection(id="legacy-edges", label="Imported flagged edges (unclassified)", segments=edges.ravel().tolist()))
        metrics.append(Metric(id="legacy-edge-count", label="Imported flagged segments (not loops)", value=edges.size // 6,
                              status="unknown", selection_id="legacy-edges", scope="The legacy payload does not distinguish boundaries from nonmanifold edges"))
    if "failed_face_ids" in data:
        ids = np.asarray(data["failed_face_ids"])
        if ids.size and (ids.dtype.kind not in "iu" or ids.ndim != 1):
            raise ValueError("failed_face_ids must be an integer vector")
        selections.append(Selection(id="legacy-faces", label="Imported flagged triangles", face_ids=ids.astype(int).tolist()))
        metrics.append(Metric(id="legacy-face-count", label="Imported flagged triangles", value=int(ids.size), status="unknown",
                              selection_id="legacy-faces", scope="Imported membership, not independently verified signed Jacobian failures"))
    if "face_qualities" in data:
        values = np.asarray(data["face_qualities"], dtype=float)
        if values.ndim != 1:
            raise ValueError("face_qualities must be a one-dimensional scalar array")
        fields.append(ScalarField(id="legacy-scalar", label="Imported scalar (definition unverified)",
                                  values=[float(v) if np.isfinite(v) else None for v in values], better="neither"))
    aliases = {"boundary_errors": "legacy-edges", "jacobian_failures": "legacy-faces"}
    present = {selection.id for selection in selections}
    for i, metric in enumerate(data.get("metrics", [])):
        selection_id = aliases.get(metric.get("id"))
        value = metric.get("value")
        if isinstance(value, np.generic):
            value = value.item()
        metrics.append(Metric(id=f"legacy-metric-{i}", label=str(metric["label"]), value=value, status="unknown",
                              selection_id=selection_id if selection_id in present else None,
                              scope=f"Unverified legacy label/value; caller status was {metric.get('status', 'unspecified')}. Not a new engineering assertion."))
    for i, path in enumerate(data.get("motorcycles", [])):
        segments = np.asarray(path["segments"], dtype=float)
        if segments.size == 0 or segments.size % 6:
            raise ValueError("Legacy path needs complete nonempty segments")
        pairs = segments.reshape(-1, 2, 3)
        if len(pairs) > 1 and not np.array_equal(pairs[:-1, 1], pairs[1:, 0]):
            raise ValueError("Disconnected legacy segments cannot be silently interpreted as one trajectory")
        points = np.vstack([pairs[0, 0], pairs[:, 1]])
        old_status = path.get("status", "unknown")
        status = "active" if old_status == "active" else "terminated" if old_status == "crashed" else "unknown"
        paths.append(Trace(id=str(path.get("id", i)), label=f"Imported trace {path.get('id', i)}", points=points.ravel().tolist(),
                           status=status, termination_reason="Legacy stopped/crashed flag; cause unverified" if status == "terminated" else None))
    return mesh_payload(data[next(iter(vertex_keys))], data[next(iter(face_keys))], mesh_id=mesh_id, revision=revision,
                        frame_id=frame_id, length_unit=length_unit, label=label, fields=fields, selections=selections,
                        metrics=metrics, paths=paths, provenance="Migrated prototype payload; imported telemetry is not validated by the adapter")
