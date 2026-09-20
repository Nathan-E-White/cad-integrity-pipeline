"""Presentation assembly: metrics and typed targets, not renderer instructions."""
from __future__ import annotations
from hashlib import sha256
import json
from collections.abc import Iterable
import numpy as np
from .audit import AuditResult
from .contract import EdgeTarget, FaceTarget, MeshPayload, Metric, Target
from .model import TriangleMesh


def assemble_payload(
    mesh: TriangleMesh, *, metrics: Iterable[Metric], targets: Iterable[Target],
    notes: Iterable[str] = (), triangle_parent_faces: list[int] | None = None,
) -> MeshPayload:
    """Primary integration seam when the mother project already computed diagnostics.

    Callers supply authoritative geometry revisions, metric definitions and
    correctly mapped triangle IDs. Nothing here reruns repair or analysis.
    """
    ms, ts, ns = list(metrics), list(targets), list(notes)
    descriptor = {
        "geometry_revision": mesh.geometry_revision, "stage": mesh.stage,
        "metrics": [m.model_dump() for m in ms], "targets": [t.model_dump() for t in ts],
        "notes": ns, "triangle_parent_faces": triangle_parent_faces,
    }
    diagnostic_revision = sha256(json.dumps(descriptor, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return MeshPayload(mesh_id=mesh.mesh_id, geometry_revision=mesh.geometry_revision,
        diagnostic_revision=diagnostic_revision, stage=mesh.stage, units=mesh.units,
        positions=mesh.positions.ravel().tolist(), triangles=mesh.triangles.ravel().tolist(),
        triangle_parent_faces=triangle_parent_faces, metrics=ms, targets=ts, notes=ns)


def payload_from_audit(result: AuditResult) -> MeshPayload:
    mesh, t, q, p = result.mesh, result.topology, result.quality, result.policy
    targets: list[Target] = []
    metrics: list[Metric] = []
    rev = mesh.geometry_revision
    has_faces = len(mesh.triangles) > 0

    def faces(name: str, ids: np.ndarray) -> str | None:
        if not len(ids):
            return None
        targets.append(FaceTarget(id=name, geometry_revision=rev, ids=ids.tolist()))
        return name

    def edges(name: str, pairs: np.ndarray) -> str | None:
        if not len(pairs):
            return None
        targets.append(EdgeTarget(id=name, geometry_revision=rev, indices=pairs.ravel().tolist()))
        return name

    def metric(id: str, label: str, value, status: str, description: str = "", target=None) -> None:
        metrics.append(Metric(id=id, label=label, value=value, status=status,
                              description=description, target_id=target))

    def check(count: int, *, partial: bool = False) -> str:
        return "fail" if count else ("not_checked" if not has_faces or partial else "pass")

    metric("vertex_count", "Vertices", len(mesh.positions), "info")
    metric("triangle_count", "Triangles", len(mesh.triangles), "info")
    partial = bool(len(t.repeated_vertex_faces))
    edge_scope = "Edge incidence only; repeated-index triangles are excluded. No implicit vertex welding."
    n = len(t.boundary_edges)
    metric("boundary_edges", "Boundary edges", n,
           check(n, partial=partial) if p.require_closed_surface else "info",
           edge_scope + (" Closed surface required by this audit policy." if p.require_closed_surface
                         else " Open surfaces allowed by this audit policy."),
           edges("boundary_edges", t.boundary_edges))
    metric("nonmanifold_edges", "Edges with >2 incident faces", len(t.nonmanifold_edges),
           check(len(t.nonmanifold_edges), partial=partial), edge_scope,
           edges("nonmanifold_edges", t.nonmanifold_edges))
    metric("winding_conflicts", "Two-face winding conflicts", len(t.winding_conflict_edges),
           check(len(t.winding_conflict_edges), partial=partial),
           "Two incident faces traverse the shared edge in the same direction. This is local consistency, not outward orientation.",
           edges("winding_conflicts", t.winding_conflict_edges))
    metric("repeated_vertices", "Repeated-index triangles", len(t.repeated_vertex_faces),
           check(len(t.repeated_vertex_faces)), "A triangle references the same vertex more than once.",
           faces("repeated_vertices", t.repeated_vertex_faces))
    metric("duplicate_faces", "Triangles in duplicate groups", len(t.duplicate_faces),
           check(len(t.duplicate_faces)), "Counts ALL members, ignoring triangle winding; not just excess copies.",
           faces("duplicate_faces", t.duplicate_faces))
    bad_degenerate = np.flatnonzero(q.degenerate)
    low = np.flatnonzero(q.degenerate | (q.mean_ratio < p.min_mean_ratio))
    bad_aspect = np.flatnonzero(q.degenerate | (q.radius_aspect > p.max_radius_aspect))
    metric("degenerate_faces", "Degenerate / nearly collapsed triangles", len(bad_degenerate),
           check(len(bad_degenerate)), f"Relative cross-product tolerance: {p.relative_area_tolerance:g}.",
           faces("degenerate_faces", bad_degenerate))
    low_target = faces("low_shape_quality", low)
    metric("low_shape_quality", "Low mean-ratio quality triangles", len(low), check(len(low)),
           f"q < {p.min_mean_ratio:g} OR degenerate. q = 4√3 A/(a²+b²+c²).", low_target)
    metric("minimum_mean_ratio", "Minimum mean-ratio quality", float(q.mean_ratio.min()) if has_faces else None,
           check(len(low)), "Unsigned, dimensionless; equilateral = 1. Not a signed Jacobian.", low_target)
    metric("maximum_radius_aspect", "Maximum radius aspect R/(2r)",
           float(q.radius_aspect.max()) if has_faces and np.isfinite(q.radius_aspect).all() else None,
           check(len(bad_aspect)),
           f"Equilateral = 1; limit {p.max_radius_aspect:g}. Undefined/unbounded when any triangle is degenerate.",
           faces("poor_radius_aspect", bad_aspect))
    finite = q.radius_aspect[np.isfinite(q.radius_aspect)]
    metric("mean_finite_radius_aspect", "Mean radius aspect (finite triangles)",
           float(finite.mean()) if len(finite) else None, "info",
           "Excludes degenerate triangles; not an overall mesh acceptance criterion.")
    if q.reference_alignment is None:
        metric("reference_orientation", "Orientation against reference normals", None, "not_checked",
               "No per-triangle reference normals were supplied. Unsigned quality cannot detect flipped faces.")
    else:
        reversed_ids = np.flatnonzero(q.reference_alignment < 0)
        undefined = int(np.count_nonzero(~np.isfinite(q.reference_alignment)))
        tangent = int(np.count_nonzero(np.abs(q.reference_alignment) <= 1e-12))
        status = "fail" if len(reversed_ids) else ("not_checked" if not has_faces or undefined or tangent else "pass")
        metric("reference_orientation", "Opposed to reference normals", len(reversed_ids), status,
               f"Negative normal dot product; {undefined} degenerate and {tangent} near-orthogonal alignments are unresolved. Not a signed FEM Jacobian.",
               faces("reference_orientation", reversed_ids))
    metric("full_validation", "Full surface / FEM validity", None, "not_checked",
           "Vertex-link manifoldness, self-intersections, global outwardness, boundary-loop counts, Betti numbers and FEM Jacobians are not computed by this audit.")
    return assemble_payload(mesh, metrics=metrics, targets=targets, notes=[
        "Diagnostics are for this exact triangle mesh and geometry revision, not automatically for a native B-Rep or volume mesh.",
        f"Policy: require_closed_surface={p.require_closed_surface}; min_mean_ratio={p.min_mean_ratio:g}; max_radius_aspect={p.max_radius_aspect:g}; relative_area_tolerance={p.relative_area_tolerance:g}.",
        "Boundary segments are not connected-loop counts. Edge incidence alone does not certify a 2-manifold.",
    ])
