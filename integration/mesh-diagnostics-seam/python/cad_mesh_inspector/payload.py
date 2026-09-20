"""Assemble explicit diagnostic display data; do not repair or mutate the mesh."""
from __future__ import annotations
from collections.abc import Sequence
import numpy as np
from numpy.typing import ArrayLike
from .arrays import mesh_arrays
from .contracts import InspectorDocument, MeshPayload, Metric, ScalarField, Selection, Trace
from .diagnostics import edge_incidence, triangle_quality


def mesh_payload(vertices: ArrayLike, triangles: ArrayLike, *, mesh_id: str, revision: str,
                 frame_id: str, length_unit: str | None = None, label: str = "Mesh",
                 fields: Sequence[ScalarField] = (), selections: Sequence[Selection] = (),
                 metrics: Sequence[Metric] = (), paths: Sequence[Trace] = (),
                 provenance: str = "Imported triangle display mesh") -> MeshPayload:
    v, f = mesh_arrays(vertices, triangles)
    return MeshPayload(id=mesh_id, revision=revision, frame_id=frame_id, length_unit=length_unit,
                       label=label, positions=v.ravel().tolist(), triangles=f.ravel().tolist(),
                       fields=list(fields), selections=list(selections), metrics=list(metrics),
                       paths=list(paths), provenance=provenance)


def inspect_triangles(vertices: ArrayLike, triangles: ArrayLike, *, mesh_id: str, revision: str,
                      frame_id: str, length_unit: str | None = None, label: str = "Mesh",
                      minimum_mean_ratio: float = 0.15, require_closed: bool = False,
                      area_tolerance: float = 0.0, paths: Sequence[Trace] = ()) -> MeshPayload:
    """Standalone demo/reference path. Production integrations should adapt reports."""
    if not np.isfinite(minimum_mean_ratio) or not 0 <= minimum_mean_ratio <= 1:
        raise ValueError("minimum_mean_ratio must lie in [0,1]")
    v, f = mesh_arrays(vertices, triangles)
    incidence = edge_incidence(v, f)
    quality = triangle_quality(v, f, area_tolerance=area_tolerance)
    incidence_complete = len(f) > 0 and len(incidence.repeated_vertex_face_ids) == 0
    selections: list[Selection] = []
    metrics: list[Metric] = [Metric(id="vertices", label="Vertices", value=len(v)),
                             Metric(id="triangles", label="Triangle elements", value=len(f))]
    for key, title, edges, failure in (
        ("boundary", "Boundary edges", incidence.boundary_edges, require_closed),
        ("nonmanifold", "Edges with more than two face uses", incidence.nonmanifold_edges, True),
        ("winding", "Adjacent winding conflicts", incidence.winding_conflict_edges, True),
    ):
        selections.append(Selection(id=key, label=title, edge_pairs=edges.ravel().tolist()))
        metrics.append(Metric(id=key, label=title, value=len(edges), selection_id=key,
                              status=("fail" if len(edges) else "pass" if incidence_complete else "unknown") if failure else "info",
                              scope="Edge incidence only; repeated-vertex faces excluded; not a manifold certificate"))
    failed = np.union1d(
        np.flatnonzero(quality.mean_ratios < minimum_mean_ratio), quality.degenerate_face_ids
    )
    for key, title, ids in (
        ("quality", f"Mean ratio below {minimum_mean_ratio:g} or degenerate", failed),
        ("degenerate", "Degenerate / area-tolerance faces", quality.degenerate_face_ids),
        ("repeated", "Faces with repeated vertex indices", incidence.repeated_vertex_face_ids),
        ("duplicate", "All faces in duplicate groups", incidence.duplicate_face_ids),
    ):
        selections.append(Selection(id=key, label=title, face_ids=ids.tolist()))
        metrics.append(Metric(id=key, label=title, value=len(ids), selection_id=key,
                              status="fail" if len(ids) else "pass" if len(f) else "unknown", scope="Triangle display diagnostic"))
    metrics.append(Metric(id="minimum-quality", label="Minimum unsigned mean ratio",
                          value=float(quality.mean_ratios.min()) if len(f) else None,
                          status="info" if len(f) else "unknown"))
    metrics.append(Metric(id="scope", label="Vertex links / self-intersections / FEM validity",
                          value="Not checked", status="unknown"))
    if paths:
        metrics.append(Metric(id="paths", label="Imported/computed paths", value=len(paths),
                              scope="No cycle, collision, or cross-field quality inference from path count"))
    field = ScalarField(id="mean-ratio", label="Triangle mean ratio (unsigned)", values=quality.mean_ratios.tolist(), better="higher")
    return mesh_payload(v, f, mesh_id=mesh_id, revision=revision, frame_id=frame_id,
                        length_unit=length_unit, label=label, fields=[field], selections=selections,
                        metrics=metrics, paths=paths, provenance="Standalone triangle diagnostics; no repair or CAD certification")


def document(*meshes: MeshPayload, linked_views: bool = True) -> InspectorDocument:
    return InspectorDocument(meshes=list(meshes), linked_views=linked_views)
