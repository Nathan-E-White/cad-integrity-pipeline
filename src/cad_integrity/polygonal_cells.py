"""Admission of raw polygonal carriers to the restricted cellular topology path.

This module establishes combinatorial cell facts only.  It neither validates an
embedded CAD model nor establishes geometry, outwardness, or material volume.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix

from .algebra import ChainComplex
from .errors import InvalidGeometry
from .models import PolyhedralBRep

INADMISSIBLE_REASON = "Inadmissible polygonal cells: refusing a misleading homology result"
_ADMISSION_TOKEN = object()


@dataclass(frozen=True, slots=True, init=False)
class ValidatedPolygonalCells:
    """Authorized simple-disk cell view over one immutable raw carrier."""

    raw: PolyhedralBRep

    def __init__(self, raw: PolyhedralBRep, *, _admission_token: object) -> None:
        if _admission_token is not _ADMISSION_TOKEN:
            raise InvalidGeometry("Polygonal cells require successful admission")
        object.__setattr__(self, "raw", raw)

    def to_chain_complex(self) -> ChainComplex:
        """Build the cellular chain complex authorized by this admission."""
        nv, ne, nf = len(self.raw.vertices), len(self.raw.edges), self.raw.face_count
        rows = self.raw.edges.ravel()
        columns = np.repeat(np.arange(ne), 2)
        d1 = csr_matrix(
            (np.tile(np.array([-1, 1], dtype=np.int64), ne), (rows, columns)),
            shape=(nv, ne),
            dtype=np.int64,
        )
        d2 = csr_matrix(
            (
                np.sign(self.raw.face_coedges),
                (
                    np.abs(self.raw.face_coedges) - 1,
                    np.repeat(np.arange(nf), np.diff(self.raw.face_offsets)),
                ),
            ),
            shape=(ne, nf),
            dtype=np.int64,
        )
        return ChainComplex((csr_matrix((0, nv), dtype=np.int64), d1, d2))


@dataclass(frozen=True, slots=True)
class PolygonalCellAdmission:
    """Complete admission evidence; invalid raw carriers intentionally have no view."""

    cells: ValidatedPolygonalCells | None
    nonmanifold_edge_ids: tuple[int, ...]
    nonmanifold_vertex_ids: tuple[int, ...]
    unused_vertex_ids: tuple[int, ...]
    unused_edge_ids: tuple[int, ...]
    invalid_face_ids: tuple[int, ...]
    duplicate_face_ids: tuple[int, ...]
    collapsed_edge_ids: tuple[int, ...]

    @property
    def reason(self) -> str | None:
        return None if self.cells is not None else INADMISSIBLE_REASON

    def require_cells(self) -> ValidatedPolygonalCells:
        if self.cells is None:
            raise InvalidGeometry(self.reason)
        return self.cells


def edge_uses(brep: PolyhedralBRep) -> dict[int, list[tuple[int, int]]]:
    """Return each raw edge's signed face uses without asserting cell admission."""
    uses: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for face in range(brep.face_count):
        for token in brep.face_loop(face):
            uses[abs(int(token)) - 1].append((face, 1 if token > 0 else -1))
    return dict(uses)


def _canonical_cycle(loop: tuple[int, ...]) -> tuple[int, ...]:
    index = loop.index(min(loop))
    forward = loop[index:] + loop[:index]
    return min(forward, (forward[0],) + forward[:0:-1])


def _connected(adjacency: dict[int, list[int]]) -> bool:
    if not adjacency:
        return False
    seen = {next(iter(adjacency))}
    pending = list(seen)
    while pending:
        for neighbor in adjacency[pending.pop()]:
            if neighbor not in seen:
                seen.add(neighbor)
                pending.append(neighbor)
    return len(seen) == len(adjacency)


def admit_polygonal_cells(raw: PolyhedralBRep) -> PolygonalCellAdmission:
    """Classify a raw carrier and return a chain-authorized view only if admissible."""
    uses = edge_uses(raw)
    invalid: list[int] = []
    duplicates: list[int] = []
    seen_faces: set[tuple[int, ...]] = set()
    links: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for face in range(raw.face_count):
        try:
            vertices = raw.face_vertices(face)
        except InvalidGeometry:
            invalid.append(face)
            continue
        canonical = _canonical_cycle(vertices)
        if canonical in seen_faces:
            duplicates.append(face)
        seen_faces.add(canonical)
        edge_ids = np.abs(raw.face_loop(face)) - 1
        for index, vertex in enumerate(vertices):
            links[vertex].append((int(edge_ids[index - 1]), int(edge_ids[index])))
    bad_vertices: list[int] = []
    for vertex, pairs in links.items():
        neighbors: dict[int, list[int]] = defaultdict(list)
        for first, second in pairs:
            neighbors[first].append(second)
            neighbors[second].append(first)
        degrees = Counter(len(values) for values in neighbors.values())
        path_or_cycle = (set(degrees) <= {1, 2} and degrees.get(1, 0) == 2) or set(degrees) == {2}
        if not path_or_cycle or not _connected(dict(neighbors)):
            bad_vertices.append(vertex)
    active_vertices = set(int(vertex) for edge in uses for vertex in raw.edges[edge])
    collapsed = tuple(
        int(index)
        for index, (start, end) in enumerate(raw.edges)
        if start == end or np.array_equal(raw.vertices[start], raw.vertices[end])
    )
    nonmanifold_edges = tuple(edge for edge in sorted(uses) if len(uses[edge]) > 2)
    unused_vertices = tuple(sorted(set(range(len(raw.vertices))) - active_vertices))
    unused_edges = tuple(sorted(set(range(len(raw.edges))) - uses.keys()))
    admissible = bool(raw.face_count) and not any(
        (
            invalid,
            duplicates,
            collapsed,
            nonmanifold_edges,
            bad_vertices,
            unused_vertices,
            unused_edges,
        )
    )
    return PolygonalCellAdmission(
        ValidatedPolygonalCells(raw, _admission_token=_ADMISSION_TOKEN) if admissible else None,
        nonmanifold_edges,
        tuple(sorted(bad_vertices)),
        unused_vertices,
        unused_edges,
        tuple(invalid),
        tuple(duplicates),
        collapsed,
    )
