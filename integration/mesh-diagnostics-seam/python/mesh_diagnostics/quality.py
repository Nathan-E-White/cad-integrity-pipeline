"""Dimensionless quality of linear triangles embedded in R^3.

These are NOT signed FEM Jacobian determinants. Orientation requires a reference.
Per-element rescaling avoids ordinary underflow/overflow from model units.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray
from .model import TriangleMesh, MeshValidationError


@dataclass(frozen=True, slots=True)
class TriangleQuality:
    mean_ratio: NDArray[np.float64]
    radius_aspect: NDArray[np.float64]
    degenerate: NDArray[np.bool_]
    reference_alignment: NDArray[np.float64] | None


def triangle_quality(
    mesh: TriangleMesh, *, relative_area_tolerance: float = 1e-12,
    reference_normals: NDArray | None = None,
) -> TriangleQuality:
    """q=4√3 A/(a²+b²+c²); radius_aspect=R/(2r)=abc s/(8 A²).

    Degeneracy uses |AB×AC| / L∞² <= tolerance, where L∞ is the largest
    absolute edge-vector component for that triangle. Degenerate aspect ratios
    are +inf internally; transport summaries must not emit JSON Infinity.
    Optional unit-normal alignment is a cosine, not a Jacobian or proof of
    outwardness. Reference normals must belong to this exact triangle ordering.
    """
    if not np.isfinite(relative_area_tolerance) or not 0 <= relative_area_tolerance < 1:
        raise ValueError("relative_area_tolerance must be finite and in [0, 1)")
    v, f = mesh.positions, mesh.triangles
    with np.errstate(over="ignore", invalid="ignore"):
        ab = v[f[:, 1]] - v[f[:, 0]]
        ac = v[f[:, 2]] - v[f[:, 0]]
        bc = v[f[:, 2]] - v[f[:, 1]]
    if not all(np.isfinite(x).all() for x in (ab, ac, bc)):
        raise MeshValidationError("coordinate differences overflow float64; rebase/rescale upstream")
    scale = np.maximum.reduce([np.max(np.abs(e), axis=1) for e in (ab, ac, bc)])
    scale_safe = np.where(scale > 0, scale, 1.0)
    ab, ac, bc = (e / scale_safe[:, None] for e in (ab, ac, bc))
    cross = np.cross(ab, ac)
    twice_area = np.linalg.norm(cross, axis=1)
    a, b, c = (np.linalg.norm(e, axis=1) for e in (ab, bc, ac))
    degenerate = (scale == 0) | (twice_area <= relative_area_tolerance)
    sum_sq = a*a + b*b + c*c
    q = np.zeros(len(f), dtype=np.float64)
    np.divide(2*np.sqrt(3)*twice_area, sum_sq, out=q, where=sum_sq > 0)
    q = np.clip(q, 0.0, 1.0)
    q[degenerate] = 0.0
    aspect = np.full(len(f), np.inf, dtype=np.float64)
    # All lengths and area above use the SAME per-triangle scale.
    np.divide(a*b*c*(a+b+c)/2, 2*twice_area**2,
              out=aspect, where=~degenerate)
    aspect[~degenerate] = np.maximum(aspect[~degenerate], 1.0)
    alignment = None
    if reference_normals is not None:
        normals = np.asarray(reference_normals)
        if normals.shape != (len(f), 3) or normals.dtype.kind not in "fiu":
            raise MeshValidationError("reference_normals must be numeric with shape (triangle_count, 3)")
        normals = normals.astype(np.float64)
        if not np.isfinite(normals).all():
            raise MeshValidationError("reference_normals must be finite")
        nscale = np.max(np.abs(normals), axis=1)
        if (nscale == 0).any():
            raise MeshValidationError("reference_normals must be nonzero")
        normals = normals / nscale[:, None]
        normals /= np.linalg.norm(normals, axis=1)[:, None]
        alignment = np.full(len(f), np.nan)
        np.divide(np.einsum("ij,ij->i", cross, normals), twice_area,
                  out=alignment, where=~degenerate)
        alignment = np.clip(alignment, -1, 1)
    for array in (q, aspect, degenerate, alignment):
        if array is not None:
            array.flags.writeable = False
    return TriangleQuality(q, aspect, degenerate, alignment)
