"""Explicitly restricted polygonal carriers; these are NOT a general CAD kernel.

PolyhedralBRep supports one simple polygonal disk per face and straight edges.
Curved surfaces, p-curves, periodic seams and inner trimming wires stay in OCP.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike
from scipy.sparse import csr_matrix

from .algebra import ChainComplex
from .arrays import FloatArray, IntArray, floats, integers, require_indices
from .errors import InvalidGeometry
from .simplicial import SimplicialComplex

UNITS = {"mm", "cm", "m", "in"}


@dataclass(frozen=True, slots=True, eq=False)
class TriangleMesh:
    vertices: FloatArray
    triangles: IntArray
    length_unit: str = "mm"

    def __post_init__(self) -> None:
        object.__setattr__(self, "vertices", floats(self.vertices, name="vertices", width=3))
        object.__setattr__(self, "triangles", integers(self.triangles, name="triangles", width=3))
        require_indices(self.triangles, len(self.vertices), "triangles")
        if self.length_unit not in UNITS:
            raise InvalidGeometry(f"Unsupported length unit {self.length_unit!r}")

    def to_simplicial_complex(self, *, max_simplices: int = 50_000) -> SimplicialComplex:
        # Include isolated vertices. Reject duplicate facets instead of silently discarding them.
        canonical = np.sort(self.triangles, axis=1)
        if len(np.unique(canonical, axis=0)) != len(canonical):
            raise InvalidGeometry("Duplicate triangles cannot be silently collapsed for homology")
        if canonical.size and np.any(np.diff(canonical, axis=1) == 0):
            raise InvalidGeometry("Repeated vertices in a triangle")
        from itertools import chain
        return SimplicialComplex(chain(((i,) for i in range(len(self.vertices))), self.triangles),
                                 max_simplices=max_simplices)


@dataclass(frozen=True, slots=True, eq=False)
class PolyhedralBRep:
    """Struct-of-arrays polygonal boundary data with zero-based entity IDs.

    coedge tokens use sign*(edge_id+1). Thus edge 0 can be represented as +1 or
    -1, there is no padding row, and token 0 is always invalid. A face loop is
    face_coedges[face_offsets[f]:face_offsets[f+1]]. Reversal is -loop[::-1].
    Arrays are defensively copied and made read-only (not a security boundary).
    """
    vertices: FloatArray
    edges: IntArray
    face_offsets: IntArray
    face_coedges: IntArray
    length_unit: str = "mm"

    def __post_init__(self) -> None:
        object.__setattr__(self, "vertices", floats(self.vertices, name="vertices", width=3))
        object.__setattr__(self, "edges", integers(self.edges, name="edges", width=2))
        object.__setattr__(self, "face_offsets", integers(self.face_offsets, name="face_offsets"))
        object.__setattr__(self, "face_coedges", integers(self.face_coedges, name="face_coedges"))
        require_indices(self.edges, len(self.vertices), "edges")
        offsets = self.face_offsets
        if not len(offsets) or offsets[0] != 0 or offsets[-1] != len(self.face_coedges):
            raise InvalidGeometry("Offsets must begin at 0 and end at the coedge count")
        if np.any(np.diff(offsets) < 3):
            raise InvalidGeometry("Each supported polygonal face needs at least three coedges")
        if self.face_coedges.size and (np.any(self.face_coedges == 0)
                or any(abs(int(t)) > len(self.edges) for t in self.face_coedges)):
            raise InvalidGeometry("Invalid coedge token; use sign*(edge_id+1)")
        if self.length_unit not in UNITS:
            raise InvalidGeometry(f"Unsupported length unit {self.length_unit!r}")

    @property
    def face_count(self) -> int:
        return len(self.face_offsets)-1

    def face_loop(self, face_id: int) -> IntArray:
        if not 0 <= face_id < self.face_count:
            raise IndexError(face_id)
        a, b = self.face_offsets[face_id:face_id+2]
        return self.face_coedges[a:b]

    def directed_endpoints(self, face_id: int) -> IntArray:
        tokens = self.face_loop(face_id)
        endpoints = self.edges[np.abs(tokens)-1].copy()
        reverse = tokens < 0
        endpoints[reverse] = endpoints[reverse, ::-1]
        return endpoints

    def face_vertices(self, face_id: int) -> tuple[int, ...]:
        endpoints = self.directed_endpoints(face_id)
        if not np.array_equal(endpoints[:, 1], np.roll(endpoints[:, 0], -1)):
            raise InvalidGeometry(f"Face {face_id} does not form a continuous closed loop")
        vertices = tuple(int(v) for v in endpoints[:, 0])
        if len(set(vertices)) != len(vertices):
            raise InvalidGeometry(f"Face {face_id} is not a simple polygonal disk boundary")
        return vertices

    def to_chain_complex(self) -> ChainComplex:
        for face_id in range(self.face_count):
            self.face_vertices(face_id)
        nv, ne, nf = len(self.vertices), len(self.edges), self.face_count
        rows = self.edges.ravel()
        cols = np.repeat(np.arange(ne), 2)
        values = np.tile(np.array([-1, 1], dtype=np.int64), ne)
        d1 = csr_matrix((values, (rows, cols)), shape=(nv, ne), dtype=np.int64)
        rows2 = np.abs(self.face_coedges)-1
        cols2 = np.repeat(np.arange(nf), np.diff(self.face_offsets))
        d2 = csr_matrix((np.sign(self.face_coedges), (rows2, cols2)),
                        shape=(ne, nf), dtype=np.int64)
        return ChainComplex((csr_matrix((0, nv), dtype=np.int64), d1, d2))

    @classmethod
    def from_polygons(cls, vertices: ArrayLike, polygons: Iterable[Iterable[int]],
                      *, length_unit: str = "mm", share_edges: bool = True) -> PolyhedralBRep:
        points = floats(vertices, name="vertices", width=3)
        edges: list[tuple[int, int]] = []
        lookup: dict[tuple[int, int], int] = {}
        offsets = [0]
        tokens = []
        for polygon in polygons:
            ids = integers(tuple(polygon), name="polygon")
            require_indices(ids, len(points), "polygon")
            if len(ids) < 3 or len(set(int(v) for v in ids)) != len(ids):
                raise InvalidGeometry("A polygon requires at least three distinct vertices")
            for u_, v_ in zip(ids, np.roll(ids, -1), strict=True):
                u, v = int(u_), int(v_)
                key = (min(u, v), max(u, v))
                if not share_edges or key not in lookup:
                    lookup[key] = len(edges)
                    edges.append(key)
                token = lookup[key]+1
                tokens.append(token if u < v else -token)
            offsets.append(len(tokens))
        return cls(points, np.asarray(edges, dtype=np.int64).reshape(-1, 2),
                   np.asarray(offsets, dtype=np.int64), np.asarray(tokens, dtype=np.int64), length_unit)

    def triangulate_convex_faces(self, *, planarity_tolerance: float = 1e-8) -> TriangleMesh:
        """Visualization-only fan triangulation; reject nonplanar or nonconvex polygons."""
        from .arrays import positive
        positive(planarity_tolerance, "planarity_tolerance", allow_zero=True)
        triangles: list[tuple[int, int, int]] = []
        for f in range(self.face_count):
            ids = self.face_vertices(f)
            xyz = self.vertices[list(ids)]
            relative = xyz - xyz[0]
            normal = np.cross(relative[1], relative[2])
            norm = np.linalg.norm(normal)
            if norm == 0:
                raise InvalidGeometry(f"Face {f}: degenerate initial triangle")
            normal /= norm
            if np.max(np.abs(relative @ normal)) > planarity_tolerance:
                raise InvalidGeometry(f"Face {f}: nonplanar; fan triangulation is unsupported")
            # Every directed edge must see all remaining points on its inward side.
            for k in range(len(ids)):
                edge = xyz[(k+1) % len(ids)] - xyz[k]
                sides = np.cross(edge, xyz-xyz[k]) @ normal
                if np.any(sides < -planarity_tolerance * max(1.0, np.linalg.norm(edge))):
                    raise InvalidGeometry(f"Face {f}: nonconvex or self-intersecting polygon")
            triangles.extend((ids[0], ids[i], ids[i+1]) for i in range(1, len(ids)-1))
        return TriangleMesh(self.vertices, np.asarray(triangles, dtype=np.int64).reshape(-1, 3),
                            self.length_unit)
