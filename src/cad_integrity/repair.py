"""Opt-in, conservative repairs for polygonal experiments, never arbitrary CAD curves."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

from .arrays import IntArray, positive, readonly
from .errors import InvalidGeometry, RepairRejected, ResourceLimitExceeded
from .models import PolyhedralBRep
from .topology import BRepHomologyStitchAnalyzer, orientation_solution


@dataclass(frozen=True, slots=True)
class WeldPolicy:
    tolerance: float
    max_displacement: float
    boundary_vertices_only: bool = True
    max_candidate_visits: int = 2_000_000

    def __post_init__(self) -> None:
        positive(self.tolerance, "tolerance")
        positive(self.max_displacement, "max_displacement", allow_zero=True)
        if self.max_displacement > self.tolerance:
            raise ValueError("max_displacement must not exceed tolerance")
        if self.max_candidate_visits < 1:
            raise ValueError("max_candidate_visits must be positive")


@dataclass(frozen=True, slots=True, eq=False)
class WeldResult:
    candidate: PolyhedralBRep
    old_to_new_vertex: IntArray
    old_to_new_edge: IntArray
    removed_vertex_count: int
    removed_edge_count: int
    maximum_displacement: float
    length_unit: str


def weld_vertices(brep: PolyhedralBRep, policy: WeldPolicy) -> WeldResult:
    """Radius-to-representative clustering; deterministic for fixed input ordering.

    Not transitive single-linkage: a chain of near neighbors cannot drift arbitrarily.
    Straight edges are deduplicated after rewiring, including their orientation signs.
    Refuse collapsed faces/edges and newly introduced nonmanifold/duplicate topology.
    The caller, not this function, decides whether nearby surfaces SHOULD be joined.
    """
    before = BRepHomologyStitchAnalyzer(brep).evaluate_stitch_integrity()
    if (before.invalid_face_ids or before.collapsed_edge_ids or before.duplicate_face_ids
            or before.nonmanifold_edge_ids or before.nonmanifold_vertex_ids):
        raise RepairRejected("Resolve invalid/duplicate/collapsed or nonmanifold input cells before welding")
    eligible = np.arange(len(brep.vertices), dtype=np.int64)
    if policy.boundary_vertices_only:
        ids = before.boundary_edge_ids
        eligible = np.unique(brep.edges[list(ids)]) if ids else np.empty(0, dtype=np.int64)
    representatives = np.arange(len(brep.vertices), dtype=np.int64)
    assigned = np.zeros(len(eligible), dtype=bool)
    visits = 0
    if len(eligible):
        tree = cKDTree(brep.vertices[eligible])
        radius = min(policy.tolerance, policy.max_displacement)
        for local, vertex in enumerate(eligible):
            if assigned[local]:
                continue
            count = int(tree.query_ball_point(brep.vertices[vertex], radius, return_length=True))
            visits += count
            if visits > policy.max_candidate_visits:
                raise ResourceLimitExceeded("Weld neighborhood search exceeds the candidate budget")
            close = sorted(tree.query_ball_point(brep.vertices[vertex], radius))
            for other in close:
                if not assigned[other]:
                    representatives[eligible[other]] = vertex
                    assigned[other] = True
    unique, inverse = np.unique(representatives, return_inverse=True)
    new_vertices = brep.vertices[unique]
    movement = np.linalg.norm(brep.vertices - new_vertices[inverse], axis=1)
    max_move = float(movement.max()) if len(movement) else 0.0
    if max_move > policy.max_displacement:
        raise RepairRejected("Vertex displacement exceeds the explicit repair budget")
    mapped_edges = inverse[brep.edges]
    if mapped_edges.size and np.any(mapped_edges[:, 0] == mapped_edges[:, 1]):
        raise RepairRejected("Welding would collapse an edge; candidate was not applied")
    new_edges: list[tuple[int, int]] = []
    lookup: dict[tuple[int, int], int] = {}
    edge_map = np.empty(len(mapped_edges), dtype=np.int64)
    edge_directions = np.empty(len(mapped_edges), dtype=np.int64)
    for i, (u_, v_) in enumerate(mapped_edges):
        u, v = int(u_), int(v_)
        key = (min(u, v), max(u, v))
        if key not in lookup:
            lookup[key] = len(new_edges)
            new_edges.append(key)
        edge_map[i] = lookup[key]
        edge_directions[i] = 1 if u < v else -1
    old_ids = np.abs(brep.face_coedges)-1
    tokens = np.sign(brep.face_coedges) * edge_directions[old_ids] * (edge_map[old_ids]+1)
    candidate = PolyhedralBRep(new_vertices, np.asarray(new_edges, dtype=np.int64).reshape(-1, 2),
                               brep.face_offsets, tokens, brep.length_unit)
    after = BRepHomologyStitchAnalyzer(candidate).evaluate_stitch_integrity()
    if after.invalid_face_ids or after.duplicate_face_ids or after.collapsed_edge_ids:
        raise RepairRejected("Welding would create an invalid or duplicate face/edge")
    # Edge/vertex IDs may change: compare defect counts, not incomparable IDs.
    if (len(after.nonmanifold_edge_ids) > len(before.nonmanifold_edge_ids)
            or len(after.nonmanifold_vertex_ids) > len(before.nonmanifold_vertex_ids)):
        raise RepairRejected("Welding would introduce additional nonmanifold topology")
    return WeldResult(candidate, readonly(inverse.astype(np.int64)), readonly(edge_map),
                      len(brep.vertices)-len(new_vertices), len(brep.edges)-len(new_edges),
                      max_move, brep.length_unit)


@dataclass(frozen=True, slots=True)
class OrientationResult:
    candidate: PolyhedralBRep
    flipped_face_ids: tuple[int, ...]
    guarantee: str = "coherent_only_not_outward"


def synchronize_orientations(brep: PolyhedralBRep) -> OrientationResult:
    for f in range(brep.face_count):
        brep.face_vertices(f)
    try:
        multipliers, conflicts = orientation_solution(brep)
    except InvalidGeometry as exc:
        raise RepairRejected(str(exc)) from exc
    if conflicts:
        raise RepairRejected(f"Orientation constraints are inconsistent at edges {conflicts}")
    tokens = brep.face_coedges.copy()
    flipped = []
    for face, multiplier in enumerate(multipliers):
        if multiplier == -1:
            a, b = brep.face_offsets[face:face+2]
            tokens[a:b] = -tokens[a:b][::-1]
            flipped.append(face)
    candidate = PolyhedralBRep(brep.vertices, brep.edges, brep.face_offsets, tokens, brep.length_unit)
    return OrientationResult(candidate, tuple(flipped))
