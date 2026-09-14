"""Combinatorial boundary diagnostics. No claim of CAD/physical certification."""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass

import numpy as np

from .algebra import HomologyReport, ReductionBudget, compute_homology
from .errors import InvalidGeometry, ResourceLimitExceeded
from .models import PolyhedralBRep, TriangleMesh


@dataclass(frozen=True, slots=True)
class TopologyReport:
    vertex_count: int
    edge_count: int
    face_count: int
    boundary_edge_ids: tuple[int, ...]
    nonmanifold_edge_ids: tuple[int, ...]
    inconsistent_orientation_edge_ids: tuple[int, ...]
    nonmanifold_vertex_ids: tuple[int, ...]
    unused_vertex_ids: tuple[int, ...]
    unused_edge_ids: tuple[int, ...]
    invalid_face_ids: tuple[int, ...]
    duplicate_face_ids: tuple[int, ...]
    collapsed_edge_ids: tuple[int, ...]
    homology: HomologyReport | None
    homology_unavailable_reason: str | None
    geometric_self_intersections_checked: bool = False

    @property
    def is_closed_oriented_2manifold(self) -> bool:
        """Purely combinatorial condition; does NOT establish an embedded CAD solid."""
        return bool(self.face_count) and not any((self.boundary_edge_ids,
            self.nonmanifold_edge_ids, self.inconsistent_orientation_edge_ids,
            self.nonmanifold_vertex_ids, self.unused_vertex_ids, self.unused_edge_ids,
            self.invalid_face_ids, self.duplicate_face_ids, self.collapsed_edge_ids))


def edge_uses(brep: PolyhedralBRep) -> dict[int, list[tuple[int, int]]]:
    uses: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for face in range(brep.face_count):
        for token in brep.face_loop(face):
            uses[abs(int(token))-1].append((face, 1 if token > 0 else -1))
    return dict(uses)


def _canonical_cycle(loop: tuple[int, ...]) -> tuple[int, ...]:
    # An unoriented face identity, modulo cyclic shifts and reversal.
    i = loop.index(min(loop))
    forward = loop[i:] + loop[:i]
    return min(forward, (forward[0],) + forward[:0:-1])


def _connected(adjacency: dict[int, list[int]]) -> bool:
    if not adjacency:
        return False
    seen = {next(iter(adjacency))}
    todo = list(seen)
    while todo:
        for neighbor in adjacency[todo.pop()]:
            if neighbor not in seen:
                seen.add(neighbor)
                todo.append(neighbor)
    return len(seen) == len(adjacency)


def orientation_solution(brep: PolyhedralBRep) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Face multipliers +/-1 for ALL components; return conflicting edge IDs.

    This establishes coherent orientations, never inward/outward or cavity nesting.
    Nonmanifold edge incidence is rejected, rather than choosing an arbitrary neighbor.
    """
    uses = edge_uses(brep)
    adjacency: dict[int, list[tuple[int, int, int]]] = defaultdict(list)
    for edge, incidents in uses.items():
        if len(incidents) > 2:
            raise InvalidGeometry(f"Cannot orient nonmanifold edge {edge}")
        if len(incidents) == 2:
            (f, s), (g, t) = incidents
            relation = -s*t
            adjacency[f].append((g, relation, edge))
            adjacency[g].append((f, relation, edge))
    multipliers = [0] * brep.face_count
    conflicts: set[int] = set()
    for seed in range(brep.face_count):
        if multipliers[seed]:
            continue
        multipliers[seed] = 1
        queue = deque([seed])
        while queue:
            face = queue.popleft()
            for other, relation, edge in adjacency[face]:
                expected = multipliers[face] * relation
                if multipliers[other] == 0:
                    multipliers[other] = expected
                    queue.append(other)
                elif multipliers[other] != expected:
                    conflicts.add(edge)
    return tuple(multipliers), tuple(sorted(conflicts))


class BRepHomologyStitchAnalyzer:
    """Analyze a restricted polygonal cell complex, NOT arbitrary native CAD faces."""

    def __init__(self, brep: PolyhedralBRep, *, coefficients: str = "F2",
                 budget: ReductionBudget = ReductionBudget()) -> None:
        self.brep, self.coefficients, self.budget = brep, coefficients, budget

    def evaluate_stitch_integrity(self) -> TopologyReport:
        b = self.brep
        uses = edge_uses(b)
        invalid: list[int] = []
        duplicates: list[int] = []
        seen_faces: set[tuple[int, ...]] = set()
        # Link of a vertex: incident edges are nodes; face corners connect them.
        links: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for f in range(b.face_count):
            try:
                vertices = b.face_vertices(f)
            except InvalidGeometry:
                invalid.append(f)
                continue
            canonical = _canonical_cycle(vertices)
            if canonical in seen_faces:
                duplicates.append(f)
            seen_faces.add(canonical)
            edge_ids = np.abs(b.face_loop(f))-1
            for k, vertex in enumerate(vertices):
                links[vertex].append((int(edge_ids[k-1]), int(edge_ids[k])))
        bad_vertices = []
        for vertex, pairs in links.items():
            neighbors: dict[int, list[int]] = defaultdict(list)
            for e1, e2 in pairs:
                neighbors[e1].append(e2)
                neighbors[e2].append(e1)
            degrees = Counter(len(v) for v in neighbors.values())
            path_or_cycle = ((set(degrees) <= {1, 2} and degrees.get(1, 0) == 2)
                             or set(degrees) == {2})
            if not path_or_cycle or not _connected(dict(neighbors)):
                bad_vertices.append(vertex)
        active_vertices = set(int(v) for e in uses for v in b.edges[e])
        collapsed = tuple(int(i) for i, (u, v) in enumerate(b.edges)
                          if u == v or np.array_equal(b.vertices[u], b.vertices[v]))
        homology = None
        reason = None
        if invalid or duplicates:
            reason = "Invalid or duplicate face cells: refusing a misleading homology result"
        else:
            try:
                homology = compute_homology(b.to_chain_complex(), coefficients=self.coefficients,
                                            budget=self.budget)
            except ResourceLimitExceeded as exc:
                reason = str(exc)
        return TopologyReport(
            len(b.vertices), len(b.edges), b.face_count,
            tuple(e for e in sorted(uses) if len(uses[e]) == 1),
            tuple(e for e in sorted(uses) if len(uses[e]) > 2),
            tuple(e for e in sorted(uses) if len(uses[e]) == 2
                  and sum(sign for _, sign in uses[e]) != 0),
            tuple(sorted(bad_vertices)),
            tuple(sorted(set(range(len(b.vertices)))-active_vertices)),
            tuple(sorted(set(range(len(b.edges)))-uses.keys())),
            tuple(invalid), tuple(duplicates), collapsed, homology, reason,
        )


def analyze_mesh(mesh: TriangleMesh, *, coefficients: str = "F2",
                 budget: ReductionBudget = ReductionBudget()) -> TopologyReport:
    boundary = PolyhedralBRep.from_polygons(mesh.vertices, mesh.triangles,
                                            length_unit=mesh.length_unit)
    return BRepHomologyStitchAnalyzer(boundary, coefficients=coefficients,
                                     budget=budget).evaluate_stitch_integrity()
