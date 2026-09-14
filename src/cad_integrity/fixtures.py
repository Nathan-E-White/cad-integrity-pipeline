"""Deterministic synthetic fixtures. None are SGS output or measured product defects."""
from __future__ import annotations

import numpy as np

from .models import PolyhedralBRep, TriangleMesh

CUBE_POLYGONS = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                 (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


def cube(*, size: float = 10.0, missing_face: int | None = None,
         reversed_face: int | None = None) -> PolyhedralBRep:
    if not np.isfinite(size) or size <= 0:
        raise ValueError("size must be finite and positive")
    vertices = size*np.array(((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
                              (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)), dtype=float)
    polygons = [p[::-1] if f == reversed_face else p for f, p in enumerate(CUBE_POLYGONS)
                if f != missing_face]
    return PolyhedralBRep.from_polygons(vertices, polygons)


def cracked_cube(*, gap: float = 0.002, reverse_detached_face: bool = True) -> PolyhedralBRep:
    if not np.isfinite(gap) or gap < 0:
        raise ValueError("gap must be finite and nonnegative")
    intact = cube()
    vertices = np.vstack((intact.vertices, intact.vertices[4:8]+(0, 0, gap)))
    polygons = list(CUBE_POLYGONS)
    polygons[1] = (11, 10, 9, 8) if reverse_detached_face else (8, 9, 10, 11)
    return PolyhedralBRep.from_polygons(vertices, polygons)


def disk() -> PolyhedralBRep:
    return PolyhedralBRep.from_polygons(np.array(((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)),
                                                dtype=float), ((0, 1, 2, 3),))


def torus(*, major_samples: int = 12, minor_samples: int = 8,
          major_radius: float = 3.0, minor_radius: float = 1.0) -> TriangleMesh:
    if major_samples < 3 or minor_samples < 3 or not 0 < minor_radius < major_radius:
        raise ValueError("Need >=3 samples in each direction and 0 < r < R")
    u, v = np.meshgrid(np.arange(major_samples)*2*np.pi/major_samples,
                       np.arange(minor_samples)*2*np.pi/minor_samples, indexing="ij")
    vertices = np.column_stack(((major_radius+minor_radius*np.cos(v)).ravel()*np.cos(u).ravel(),
                                (major_radius+minor_radius*np.cos(v)).ravel()*np.sin(u).ravel(),
                                minor_radius*np.sin(v).ravel()))
    triangles: list[tuple[int, int, int]] = []
    for i in range(major_samples):
        for j in range(minor_samples):
            a = i*minor_samples+j
            b = ((i+1) % major_samples)*minor_samples+j
            c = ((i+1) % major_samples)*minor_samples+(j+1) % minor_samples
            d = i*minor_samples+(j+1) % minor_samples
            triangles.extend(((a, b, c), (a, c, d)))
    return TriangleMesh(vertices, np.asarray(triangles, dtype=np.int64))


def tetrahedron() -> TriangleMesh:
    vertices = np.array(((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)), dtype=float)
    return TriangleMesh(vertices, np.array(((0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)), dtype=np.int64))


def pinched_tetrahedra() -> TriangleMesh:
    first = tetrahedron()
    vertices = np.vstack((first.vertices, -first.vertices[1:]))
    mapping = np.array((0, 4, 5, 6), dtype=np.int64)
    return TriangleMesh(vertices, np.vstack((first.triangles, mapping[first.triangles[:, ::-1]])))
