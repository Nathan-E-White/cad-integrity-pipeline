"""Explicit migration adapter for the supplied vertices/faces/error_edges snippets.

Legacy metric definitions are NOT re-certified. No display-label heuristics.
"""
from __future__ import annotations
from collections.abc import Mapping
from typing import Any
import numpy as np
from .model import TriangleMesh, MeshValidationError, _matrix
from .contract import FaceTarget, SegmentTarget, Metric, MeshPayload
from .payload import assemble_payload


def _alias(data: Mapping[str, Any], names: tuple[str, ...]) -> Any:
    found = [name for name in names if name in data]
    if len(found) != 1:
        raise MeshValidationError(f"provide exactly one of {names}; found {found}")
    return data[found[0]]


def mesh_from_mapping(data: Mapping[str, Any], **metadata: Any) -> TriangleMesh:
    return TriangleMesh(_alias(data, ("positions", "vertices")),
                        _alias(data, ("triangles", "faces", "indices")), **metadata)


def adapt_legacy_payload(data: Mapping[str, Any]) -> MeshPayload:
    mesh = mesh_from_mapping(data, mesh_id=str(data.get("mesh_id", "legacy-mesh")),
        geometry_revision=data.get("geometry_revision"), stage=str(data.get("stage", "unspecified")),
        units=str(data.get("units", "unspecified")))
    targets = []
    known = {}
    if "error_edges" in data:
        raw = np.asarray(data["error_edges"])
        if raw.ndim == 3 and raw.shape[1:] == (2, 3):
            raw = raw.reshape(-1, 6)
        arr = _matrix(raw, 6, "error_edges")
        if arr.dtype.kind not in "fiu" or not np.isfinite(arr).all():
            raise MeshValidationError("error_edges must contain finite real coordinates")
        if len(arr):
            targets.append(SegmentTarget(id="legacy_error_segments", geometry_revision=mesh.geometry_revision,
                                         positions=arr.ravel().tolist()))
            known["boundary_errors"] = "legacy_error_segments"
    if "failed_face_ids" in data:
        raw = np.asarray(data["failed_face_ids"])
        if raw.ndim != 1 or (raw.size and raw.dtype.kind not in "iu"):
            raise MeshValidationError("failed_face_ids must be a flat integer array")
        if raw.size and (raw.min() < 0 or raw.max() >= len(mesh.triangles)):
            raise MeshValidationError("failed_face_ids must reference this exact triangle ordering")
        if raw.size:
            targets.append(FaceTarget(id="legacy_quality_failures", geometry_revision=mesh.geometry_revision,
                                      ids=raw.tolist()))
            known["jacobian_failures"] = "legacy_quality_failures"
    metrics = []
    for i, raw in enumerate(data.get("metrics", [])):
        if not isinstance(raw, Mapping):
            raise MeshValidationError("metrics must be dictionaries, not NumPy object arrays")
        id = raw.get("id", f"legacy_metric_{i}")
        val = raw.get("value")
        if isinstance(val, np.generic):
            val = val.item()
        metrics.append(Metric(id=id, label=raw["label"], value=val,
            status=raw.get("status", "info"), target_id=known.get(id),
            description="Legacy producer-supplied metric; semantics and status were not recomputed."))
    if not metrics:
        metrics = [Metric(id="vertex_count", label="Vertices", value=len(mesh.positions), status="info"),
                   Metric(id="triangle_count", label="Triangles", value=len(mesh.triangles), status="info")]
    # Make legacy diagnostics reachable even when the old metrics have no IDs.
    linked = {m.target_id for m in metrics}
    for target in targets:
        if target.id not in linked:
            count = len(target.ids) if isinstance(target, FaceTarget) else len(target.positions)//6
            metrics.append(Metric(id=target.id, label="Legacy flagged triangles" if isinstance(target, FaceTarget)
                else "Legacy unclassified error segments", value=count, status="warn", target_id=target.id,
                description="Supplied by the legacy producer; not a boundary-loop or manifold classification."))
    return assemble_payload(mesh, targets=targets, metrics=metrics, notes=[
        "Legacy values and pass/fail assertions were preserved, not scientifically revalidated.",
        "The old jacobian_failures ID maps to legacy-quality-failures without asserting signed Jacobian semantics.",
    ])
