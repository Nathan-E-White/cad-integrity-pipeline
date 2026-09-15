"""Combinatorial boundary diagnostics. No claim of CAD/physical certification."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from .algebra import HomologyReport, ReductionBudget, compute_homology
from .errors import InvalidGeometry, ResourceLimitExceeded
from .models import PolyhedralBRep, TriangleMesh
from .polygonal_cells import admit_polygonal_cells, edge_uses


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
    def has_admissible_polygonal_cells(self) -> bool:
        """Whether raw cells support the restricted polygonal topology path.

        Boundary and orientation are repairable/topological conditions; malformed,
        duplicate, collapsed, nonmanifold, or unused cells are not admissible.
        This does not claim embedded CAD validity.
        """
        return bool(self.face_count) and not any((
            self.nonmanifold_edge_ids, self.nonmanifold_vertex_ids,
            self.unused_vertex_ids, self.unused_edge_ids, self.invalid_face_ids,
            self.duplicate_face_ids, self.collapsed_edge_ids,
        ))

    @property
    def is_closed_oriented_2manifold(self) -> bool:
        """Purely combinatorial condition; does NOT establish an embedded CAD solid."""
        return bool(self.face_count) and not any(
            (
                self.boundary_edge_ids,
                self.nonmanifold_edge_ids,
                self.inconsistent_orientation_edge_ids,
                self.nonmanifold_vertex_ids,
                self.unused_vertex_ids,
                self.unused_edge_ids,
                self.invalid_face_ids,
                self.duplicate_face_ids,
                self.collapsed_edge_ids,
            )
        )


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
            relation = -s * t
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

    def __init__(
        self,
        brep: PolyhedralBRep,
        *,
        coefficients: str = "F2",
        budget: ReductionBudget = ReductionBudget(),
    ) -> None:
        self.brep, self.coefficients, self.budget = brep, coefficients, budget

    def evaluate_stitch_integrity(self) -> TopologyReport:
        b = self.brep
        uses = edge_uses(b)
        admission = admit_polygonal_cells(b)
        boundary_edges = tuple(e for e in sorted(uses) if len(uses[e]) == 1)
        inconsistent_edges = tuple(
            e for e in sorted(uses) if len(uses[e]) == 2 and sum(sign for _, sign in uses[e]) != 0
        )
        homology = None
        reason = admission.reason
        if admission.cells is not None:
            try:
                homology = compute_homology(
                    admission.cells.to_chain_complex(),
                    coefficients=self.coefficients,
                    budget=self.budget,
                )
            except ResourceLimitExceeded as exc:
                reason = str(exc)
        return TopologyReport(
            len(b.vertices),
            len(b.edges),
            b.face_count,
            boundary_edges,
            admission.nonmanifold_edge_ids,
            inconsistent_edges,
            admission.nonmanifold_vertex_ids,
            admission.unused_vertex_ids,
            admission.unused_edge_ids,
            admission.invalid_face_ids,
            admission.duplicate_face_ids,
            admission.collapsed_edge_ids,
            homology,
            reason,
        )


def analyze_mesh(
    mesh: TriangleMesh, *, coefficients: str = "F2", budget: ReductionBudget = ReductionBudget()
) -> TopologyReport:
    boundary = PolyhedralBRep.from_polygons(
        mesh.vertices, mesh.triangles, length_unit=mesh.length_unit
    )
    return BRepHomologyStitchAnalyzer(
        boundary, coefficients=coefficients, budget=budget
    ).evaluate_stitch_integrity()
