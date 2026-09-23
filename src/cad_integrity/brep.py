"""Owned, topology-backed BRep realization using the installed OCP runtime.

The caller must not mutate the source during this synchronous operation. Native
admission establishes discrete conformity under supplied correspondence and sampled
geometry checks; it does not certify continuous error or global self-intersection.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Any
from uuid import uuid4

import numpy as np

from . import _native
from .adapters import ocp
from .arrays import IntArray
from .errors import ResourceLimitExceeded
from .surface import Surface, SurfaceLimits, _immutable, _project_surface


@dataclass(frozen=True, slots=True)
class RealizationPolicy:
    linear_deflection_mm: float = 0.05
    angular_deflection: float = 0.3
    agreement_tolerance_mm: float = 1e-7
    maximum_sampled_deviation_mm: float = 0.1

    def __post_init__(self) -> None:
        for value in (self.linear_deflection_mm, self.angular_deflection,
                      self.agreement_tolerance_mm, self.maximum_sampled_deviation_mm):
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError("Realization tolerances must be finite and positive")


@dataclass(frozen=True, slots=True)
class RealizationLimits:
    max_faces: int = 100_000
    max_edges: int = 300_000
    max_native_vertices: int = 300_000
    max_nodes: int = 1_000_000
    max_triangles: int = 1_000_000
    max_edge_samples: int = 2_000_000
    numerical: SurfaceLimits = SurfaceLimits()

    def __post_init__(self) -> None:
        for value in (self.max_faces, self.max_edges, self.max_native_vertices,
                      self.max_nodes, self.max_triangles, self.max_edge_samples):
            if type(value) is not int or not 0 <= value < 1 << 63:
                raise ValueError("Realization counts must be nonnegative int64 integers")


@dataclass(frozen=True, slots=True)
class RealizationDiagnostic:
    code: str
    face_id: int | None = None
    edge_id: int | None = None


@dataclass(frozen=True, slots=True)
class RealizationEvidence:
    source_face_count: int
    source_edge_count: int
    source_vertex_count: int
    maximum_sampled_deviation_mm: float
    copy_seconds: float
    mesh_seconds: float
    extraction_seconds: float
    qualification_seconds: float
    collapsed_pole_triangles: int = 0


@dataclass(frozen=True, slots=True)
class RealizedSurface:
    surface: Surface
    native_vertex_ids: IntArray  # -1 for derived edge/interior samples
    source_snapshot_id: str
    evidence: RealizationEvidence


@dataclass(frozen=True, slots=True)
class RealizationAssessment:
    diagnostics: tuple[RealizationDiagnostic, ...]
    admitted: RealizedSurface | None
    evidence: RealizationEvidence | None


class _Refused(Exception):
    def __init__(self, code: str, face: int | None = None, edge: int | None = None):
        self.diagnostic = RealizationDiagnostic(code, face, edge)


def _require(ok: bool, code: str, face: int | None = None, edge: int | None = None) -> None:
    if not ok:
        raise _Refused(code, face, edge)


def _limit(count: int, bound: int, name: str) -> None:
    if count > bound:
        raise ResourceLimitExceeded(f"Realization {name} budget exceeded")


def _extract(shape: Any, policy: RealizationPolicy, limits: RealizationLimits) -> tuple[Any, ...]:
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCP.gp import gp_Pnt, gp_Vec
    from OCP.TopAbs import TopAbs_FORWARD

    _require(not shape.IsNull(), "null_shape")
    start = perf_counter()
    kinds = (ocp.TopAbs_FACE, ocp.TopAbs_EDGE, ocp.TopAbs_VERTEX)
    source = [ocp._map(shape, kind) for kind in kinds]
    counts = tuple(m.Extent() for m in source)
    for count, bound, name in zip(counts, (limits.max_faces, limits.max_edges,
                                          limits.max_native_vertices), ("face", "edge", "vertex"), strict=True):
        _limit(count, bound, name)
    _require(counts[0] > 0, "no_faces")
    occurrences = ocp.TopExp_Explorer(shape, ocp.TopAbs_FACE)
    occurrence_count = 0
    while occurrences.More():
        occurrence_count += 1
        _require(occurrence_count <= counts[0], "repeated_face_occurrence")
        occurrences.Next()
    _require(occurrence_count == counts[0], "face_occurrence_count")
    copier = ocp.BRepBuilderAPI_Copy(shape, True, False)
    copied = copier.Shape()
    maps = [ocp._map(copied, kind) for kind in kinds]
    reverse: list[dict[int, int]] = []
    for original, mapping in zip(source, maps, strict=True):
        ids = [mapping.FindIndex(copier.ModifiedShape(original.FindKey(i)))
               for i in range(1, original.Extent() + 1)]
        _require(set(ids) == set(range(1, mapping.Extent() + 1))
                 and len(ids) == mapping.Extent(), "copy_correspondence")
        reverse.append({copied_id: source_id for source_id, copied_id in enumerate(ids)})
    _require(ocp.BRepCheck_Analyzer(copied).IsValid(), "invalid_brep")
    copy_seconds = perf_counter() - start
    start = perf_counter()
    mesher = ocp.BRepMesh_IncrementalMesh(copied, policy.linear_deflection_mm, False,
                                         policy.angular_deflection, False)
    _require(mesher.IsDone() and mesher.GetStatusFlags() == 0, "meshing_failed")
    mesh_seconds = perf_counter() - start
    start = perf_counter()
    nodes: list[tuple[float, float, float]] = []
    keys: list[tuple[int, int, int]] = []
    triangles: list[tuple[int, int, int]] = []
    faces: list[int] = []
    segments: list[tuple[int, int, int, int]] = []
    edge_uses = np.zeros(counts[1], dtype=np.int64)
    parameters: dict[int, np.ndarray[Any, Any]] = {}
    sampled = 0.0
    sample_count = 0
    collapsed_poles = 0
    seen_edges: set[int] = set()
    seen_vertices: set[int] = set()

    def deviation(a: Any, b: Any, face: int, edge: int | None = None) -> None:
        nonlocal sampled
        distance = math.dist(a, b)
        _require(math.isfinite(distance), "nonfinite_geometry", face, edge)
        sampled = max(sampled, distance)
        _require(distance <= policy.maximum_sampled_deviation_mm, "sampled_deviation", face, edge)

    def assign(index: int, key: tuple[int, int, int], face: int, edge: int) -> None:
        old = keys[index]
        _require(old[0] == 2 or old == key, "node_correspondence", face, edge)
        keys[index] = key

    for copied_face in range(1, maps[0].Extent() + 1):
        face_id = reverse[0][copied_face]
        face = ocp.TopoDS.Face_s(maps[0].FindKey(copied_face))
        _require(face.Orientation() in (TopAbs_FORWARD, ocp.TopAbs_REVERSED), "unsupported_orientation", face_id)
        location = ocp.TopLoc_Location()
        triangulation = ocp.BRep_Tool.Triangulation_s(face, location)
        _require(triangulation is not None and triangulation.NbTriangles() > 0
                 and triangulation.HasUVNodes(), "missing_triangulation", face_id)
        _limit(len(nodes) + triangulation.NbNodes(), limits.max_nodes, "node")
        _limit(len(triangles) + triangulation.NbTriangles(), limits.max_triangles, "triangle")
        # Bound numeric extraction before retaining this face. Python object overhead
        # and OCCT-owned data are outside this logical numeric reservation.
        _limit((len(nodes) + triangulation.NbNodes()) * 48
               + (len(triangles) + triangulation.NbTriangles()) * 32
               + len(segments) * 32 + counts[1] * 8,
               limits.numerical.max_input_bytes, "extracted input bytes")
        offset = len(nodes)
        transform = location.Transformation()
        for i in range(1, triangulation.NbNodes() + 1):
            p = triangulation.Node(i).Transformed(transform)
            xyz = (p.X(), p.Y(), p.Z())
            _require(all(math.isfinite(x) for x in xyz), "nonfinite_geometry", face_id)
            nodes.append(xyz)
            keys.append((2, face_id, i - 1))
        collapsed_sides: set[tuple[int, int]] = set()
        # Edge orientation relative to the underlying face selects the seam branch.
        forward_face = ocp.TopoDS.Face_s(face.Oriented(TopAbs_FORWARD))
        explorer = ocp.TopExp_Explorer(forward_face, ocp.TopAbs_EDGE)
        while explorer.More():
            edge = ocp.TopoDS.Edge_s(explorer.Current())
            edge_id = reverse[1][maps[1].FindIndex(edge)]
            seen_edges.add(edge_id)
            _require(edge.Orientation() in (TopAbs_FORWARD, ocp.TopAbs_REVERSED),
                     "unsupported_edge_orientation", face_id, edge_id)
            polygon = ocp.BRep_Tool.PolygonOnTriangulation_s(edge, triangulation, location)
            _require(polygon is not None and polygon.NbNodes() >= 2 and polygon.HasParameters(),
                     "missing_edge_samples", face_id, edge_id)
            sample_count += polygon.NbNodes()
            _limit(sample_count, limits.max_edge_samples, "edge sample")
            _limit(len(nodes)*48 + len(triangles)*32 + (len(segments)+polygon.NbNodes()-1)*32 + counts[1]*8,
                   limits.numerical.max_input_bytes, "extracted input bytes")
            local_nodes = [polygon.Node(j) for j in range(1, polygon.NbNodes() + 1)]
            _require(all(1 <= j <= triangulation.NbNodes() for j in local_nodes), "edge_node_index", face_id, edge_id)
            chain = [offset + j - 1 for j in local_nodes]
            canonical = ocp.TopoDS.Edge_s(edge.Oriented(TopAbs_FORWARD))
            endpoints = (ocp.TopExp.FirstVertex_s(canonical), ocp.TopExp.LastVertex_s(canonical))
            _require(all(not p.IsNull() for p in endpoints), "missing_edge_vertex", face_id, edge_id)
            vertex_ids = [reverse[2][maps[2].FindIndex(p)] for p in endpoints]
            seen_vertices.update(vertex_ids)
            if ocp.BRep_Tool.Degenerated_s(edge):
                _require(vertex_ids[0] == vertex_ids[1], "degenerate_edge_identity", face_id, edge_id)
                collapsed_sides.update(tuple(sorted((a, b))) for a, b in zip(chain, chain[1:], strict=False))
                for index in chain:
                    assign(index, (0, vertex_ids[0], 0), face_id, edge_id)
            else:
                params = np.array([polygon.Parameter(j) for j in range(1, polygon.NbNodes() + 1)])
                _require(bool(np.all(np.isfinite(params)) and np.all(np.diff(params) > 0)),
                         "edge_parameter_order", face_id, edge_id)
                if edge_id in parameters:
                    reference = parameters[edge_id]
                    _require(len(params) == len(reference) and bool(np.array_equal(params, reference)),
                             "edge_parameter_disagreement", face_id, edge_id)
                else:
                    parameters[edge_id] = params
                edge_uses[edge_id] += 1
                curve = ocp.BRepAdaptor_Curve(canonical)
                for j, index in enumerate(chain):
                    key = ((0, vertex_ids[0], 0) if j == 0 else
                           (0, vertex_ids[1], 0) if j == len(chain)-1 else (1, edge_id, j))
                    assign(index, key, face_id, edge_id)
                    p = curve.Value(float(params[j]))
                    deviation(nodes[index], (p.X(), p.Y(), p.Z()), face_id, edge_id)
                    if j:
                        midpoint = curve.Value(float(params[j-1]/2 + params[j]/2))
                        xyz = (np.array(nodes[chain[j-1]]) + nodes[index]) / 2
                        deviation(xyz, (midpoint.X(), midpoint.Y(), midpoint.Z()), face_id, edge_id)
                        segments.append((chain[j-1], index, edge_id, face_id))
            for index, vertex in ((chain[0], endpoints[0]), (chain[-1], endpoints[1])):
                p = ocp.BRep_Tool.Pnt_s(vertex)
                _require(math.dist(nodes[index], (p.X(), p.Y(), p.Z())) <= policy.agreement_tolerance_mm,
                         "vertex_coordinate_disagreement", face_id, edge_id)
            explorer.Next()
        adaptor = ocp.BRepAdaptor_Surface(face, True)
        support = ocp.BRep_Tool.Surface_s(face)
        for i in range(1, triangulation.NbTriangles() + 1):
            local = list(triangulation.Triangle(i).Get())
            _require(all(1 <= j <= triangulation.NbNodes() for j in local), "triangle_index", face_id)
            ids = [offset + j - 1 for j in local]
            if any(tuple(sorted((ids[j], ids[(j+1) % 3]))) in collapsed_sides for j in range(3)):
                collapsed_poles += 1
                continue
            triangle_xyz = np.array([nodes[j] for j in ids])
            centroid = triangle_xyz.mean(axis=0)
            projection = GeomAPI_ProjectPointOnSurf(gp_Pnt(*centroid), support,
                                                    policy.agreement_tolerance_mm)
            _require(projection.IsDone() and projection.NbPoints() > 0,
                     "surface_projection_failed", face_id)
            u, v = projection.LowerDistanceParameters()
            _require(math.isfinite(u) and math.isfinite(v), "nonfinite_geometry", face_id)
            point, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
            adaptor.D1(u, v, point, du, dv)
            deviation(centroid, (point.X(), point.Y(), point.Z()), face_id)
            cross = np.cross(triangle_xyz[1] - triangle_xyz[0], triangle_xyz[2] - triangle_xyz[0])
            normal = du.Crossed(dv)
            dot = float(np.dot(cross, (normal.X(), normal.Y(), normal.Z())))
            _require(math.isfinite(dot) and dot > 0, "triangle_surface_orientation", face_id)
            if face.Orientation() == ocp.TopAbs_REVERSED:
                ids[1], ids[2] = ids[2], ids[1]
            triangles.append((ids[0], ids[1], ids[2]))
            faces.append(face_id)
    _require(len(seen_edges) == counts[1] and len(seen_vertices) == counts[2], "unowned_native_entities")
    evidence = RealizationEvidence(counts[0], counts[1], counts[2], sampled, copy_seconds, mesh_seconds,
                                   perf_counter() - start, 0.0, collapsed_poles)
    return (np.asarray(nodes, dtype=np.float64), np.asarray(keys, dtype=np.int64),
            np.asarray(triangles, dtype=np.int64), np.asarray(faces, dtype=np.int64),
            np.asarray(segments, dtype=np.int64).reshape(-1, 4), edge_uses, evidence)


def realize(shape: Any, *, policy: RealizationPolicy = RealizationPolicy(),
            limits: RealizationLimits = RealizationLimits()) -> RealizationAssessment:
    """Assess a private millimetre shape copy and admit only conforming output."""
    try:
        nodes, keys, triangles, faces, segments, uses, evidence = _extract(shape, policy, limits)
    except _Refused as exc:
        return RealizationAssessment((exc.diagnostic,), None, None)
    except ResourceLimitExceeded:
        raise
    except (RuntimeError, ValueError) as exc:
        # OCP failures produce refusal; never an admitted partial tessellation.
        return RealizationAssessment((RealizationDiagnostic(f"kernel_failure:{type(exc).__name__}"),), None, None)
    start = perf_counter()
    try:
        result = _native.realize_brep(nodes, keys, triangles, faces, segments, uses, evidence.source_face_count,
                                      evidence.source_vertex_count,
                                      policy.agreement_tolerance_mm,
                                      limits.numerical._native_limits())
    except _native.BudgetExceeded as exc:
        raise ResourceLimitExceeded(str(exc)) from exc
    evidence = replace(evidence, qualification_seconds=perf_counter() - start)
    diagnostics = tuple(RealizationDiagnostic(code) for code in result["diagnostics"])
    admitted = None
    if result["surface"] is not None:
        admitted = RealizedSurface(_project_surface(result["surface"], "mm", limits.numerical),
                                   _immutable(result["native_vertex_ids"]), uuid4().hex, evidence)
    return RealizationAssessment(diagnostics, admitted, evidence)
