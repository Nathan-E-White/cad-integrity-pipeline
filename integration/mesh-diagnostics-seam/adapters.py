"""Adapters over existing cad_integrity reports: NO duplicate topology/quality run.

Duck-typed inputs avoid making the host package a dependency. Source polygon IDs
are explicitly mapped to display triangle rows when triangulation is necessary.
"""
from __future__ import annotations
from typing import Any
import numpy as np
from .contracts import Metric, ScalarField, Selection
from .payload import mesh_payload


def from_triangle_reports(mesh: Any, *, quality: Any | None = None,
                          mesh_id: str, revision: str, frame_id: str,
                          label: str = "Triangle mesh"):
    fields = []
    selections = []
    metrics = []
    if quality is not None:
        fields.append(ScalarField(id="mean-ratio", label="Triangle mean ratio (unsigned)",
                                  values=np.asarray(quality.mean_ratios).astype(float).tolist(), better="higher"))
        # Existing aspect_ratios is longest-edge/(2 sqrt(3) r), not R/(2r).
        aspects = np.asarray(quality.aspect_ratios, dtype=float)
        values = [float(x) if np.isfinite(x) else None for x in aspects]
        finite = aspects[np.isfinite(aspects)]
        fields.append(ScalarField(id="longest-edge-inradius", label="Longest-edge / inradius aspect ratio",
                                  values=values, domain=[1.0, max(2.0, float(finite.max()) if finite.size else 2.0)], better="lower"))
        ids = np.asarray(quality.degenerate_triangle_ids, dtype=int).tolist()
        selections.append(Selection(id="degenerate", label="Degenerate triangles", face_ids=ids))
        metrics.append(Metric(id="degenerate", label="Degenerate triangles", value=len(ids),
                              status="fail" if ids else "pass", selection_id="degenerate",
                              scope="Existing cad_integrity.metrics.mesh_quality report"))
    return mesh_payload(mesh.vertices, mesh.triangles, mesh_id=mesh_id, revision=revision,
                        frame_id=frame_id, label=label, length_unit=mesh.length_unit,
                        fields=fields, selections=selections, metrics=metrics,
                        provenance="Adapted existing triangle report; diagnostics not recomputed")


def from_polygonal_report(brep: Any, report: Any, *, mesh_id: str, revision: str,
                          frame_id: str, label: str = "Polygonal audit"):
    # Reuse the host's guarded convex/planar display triangulator. Arbitrary native
    # trimmed B-Rep requires the host kernel tessellator, not a new fan algorithm.
    mesh = brep.triangulate_convex_faces()
    source_ids = [face_id for face_id in range(brep.face_count)
                  for _ in range(len(brep.face_vertices(face_id)) - 2)]
    selections, metrics = [], []
    for key, title, ids in (
        ("boundary", "Boundary edges", report.boundary_edge_ids),
        ("nonmanifold", "Nonmanifold edges", report.nonmanifold_edge_ids),
        ("winding", "Winding conflicts", report.inconsistent_orientation_edge_ids),
    ):
        coords = brep.vertices[brep.edges[list(ids)]] if ids else np.empty((0, 2, 3))
        selections.append(Selection(id=key, label=title, segments=coords.astype(float).ravel().tolist()))
        metrics.append(Metric(id=key, label=title, value=len(ids), status="info", selection_id=key,
                              scope="Existing polygonal TopologyReport; edge count, not loop count"))
    metrics.append(Metric(id="configured-check", label="Closed oriented 2-manifold (combinatorial)",
                          value=1 if report.is_closed_oriented_2manifold else 0,
                          status="pass" if report.is_closed_oriented_2manifold else "fail",
                          scope="Existing report only; not embedded CAD solid or solver certification"))
    result = mesh_payload(mesh.vertices, mesh.triangles, mesh_id=mesh_id, revision=revision,
                          frame_id=frame_id, length_unit=brep.length_unit, label=label,
                          selections=selections, metrics=metrics,
                          provenance="Existing polygonal audit + guarded display triangulation")
    return type(result).model_validate({**result.model_dump(), "triangle_source_faces": source_ids})
