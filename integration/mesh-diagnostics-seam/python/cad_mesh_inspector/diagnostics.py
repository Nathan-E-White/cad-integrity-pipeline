"""Optional standalone triangle diagnostics, not a second polygonal validation authority.

Production cad_integrity integrations should use adapters.py with existing reports.
All original face rows survive. Edge counts are NOT loop counts or manifold proof.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from numpy.typing import ArrayLike, NDArray
from .arrays import mesh_arrays


@dataclass(frozen=True)
class EdgeIncidence:
    edges: NDArray
    counts: NDArray
    boundary_edges: NDArray
    nonmanifold_edges: NDArray
    winding_conflict_edges: NDArray
    repeated_vertex_face_ids: NDArray
    duplicate_face_ids: NDArray


def edge_incidence(vertices: ArrayLike, triangles: ArrayLike) -> EdgeIncidence:
    _, f = mesh_arrays(vertices, triangles)
    canonical = np.sort(f, axis=1)
    repeated = np.any(np.diff(canonical, axis=1) == 0, axis=1)
    _, inverse, multiplicity = np.unique(canonical, axis=0, return_inverse=True, return_counts=True)
    duplicate = np.flatnonzero(multiplicity[inverse] > 1)
    # A repeated vertex creates self-edges or multiple uses within one face. Keep
    # its row in the report, but do not misreport it as a valid face incidence.
    usable = f[~repeated]
    directed = usable[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2)
    undirected = np.sort(directed, axis=1)
    unique, inverse, counts = np.unique(undirected, axis=0, return_inverse=True, return_counts=True)
    signs = np.where(directed[:, 0] < directed[:, 1], 1, -1)
    balance = np.bincount(inverse, weights=signs, minlength=len(unique))
    return EdgeIncidence(unique, counts, unique[counts == 1], unique[counts > 2],
                         unique[(counts == 2) & (balance != 0)], np.flatnonzero(repeated), duplicate)


@dataclass(frozen=True)
class TriangleQuality:
    areas: NDArray
    mean_ratios: NDArray
    radius_ratios: NDArray
    degenerate_face_ids: NDArray


def triangle_quality(vertices: ArrayLike, triangles: ArrayLike, *, area_tolerance: float = 0.0) -> TriangleQuality:
    """q=4 sqrt(3) A/(a²+b²+c²), unsigned, q in [0,1].

    radius_ratio=R/(2r)=abc*s/(8 A²), ideal=1; undefined for degenerate faces.
    This is NOT the longest-edge/inradius aspect metric in cad_integrity.metrics.
    area_tolerance is explicit and has squared-coordinate units. No epsilon area
    is fabricated. Per-triangle scaling stabilizes dimensionless measurements.
    """
    if not np.isfinite(area_tolerance) or area_tolerance < 0:
        raise ValueError("area_tolerance must be finite and nonnegative")
    v, f = mesh_arrays(vertices, triangles)
    xyz = v[f]
    with np.errstate(over="raise", invalid="raise"):
        e = np.stack((xyz[:, 1] - xyz[:, 0], xyz[:, 2] - xyz[:, 1], xyz[:, 0] - xyz[:, 2]), axis=1)
    scale = np.max(np.abs(e), axis=(1, 2), initial=0.0)
    normalized = np.divide(e, scale[:, None, None], out=np.zeros_like(e), where=scale[:, None, None] > 0)
    lengths = np.linalg.norm(normalized, axis=2)
    normalized_area = 0.5 * np.linalg.norm(np.cross(normalized[:, 0], -normalized[:, 2]), axis=1)
    with np.errstate(over="raise", invalid="raise"):
        areas = (normalized_area * scale) * scale
    valid = (areas > area_tolerance) & (normalized_area > 0) & np.all(lengths > 0, axis=1)
    q = np.zeros(len(f), dtype=np.float64)
    ratio = np.full(len(f), np.inf)
    q[valid] = np.clip(4 * np.sqrt(3) * normalized_area[valid] / np.sum(lengths[valid] ** 2, axis=1), 0, 1)
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        sides = lengths[valid]
        ratio[valid] = np.prod(sides, axis=1) * sides.sum(axis=1) / (16 * normalized_area[valid] ** 2)
    return TriangleQuality(areas, q, ratio, np.flatnonzero(~valid))
