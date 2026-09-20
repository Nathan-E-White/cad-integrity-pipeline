"""Validate before casting; never wrap negative or fractional indices to uint32."""
from __future__ import annotations
import numpy as np
from numpy.typing import ArrayLike, NDArray
from .contracts import MAX_TRIANGLES, MAX_VERTICES


def mesh_arrays(vertices: ArrayLike, triangles: ArrayLike) -> tuple[NDArray, NDArray]:
    v, f = np.asarray(vertices), np.asarray(triangles)
    if v.dtype.kind not in "fiu" or f.dtype.kind not in "iu":
        # [] is a useful empty mesh; NumPy infers a float dtype for that literal.
        if not (f.size == 0 and v.dtype.kind in "fiu"):
            raise ValueError("Coordinates must be numeric; connectivity must use integer dtype")
    if v.ndim == 1 and v.size % 3 == 0:
        v = v.reshape(-1, 3)
    if f.ndim == 1 and f.size % 3 == 0:
        f = f.reshape(-1, 3)
    if v.ndim != 2 or v.shape[1] != 3 or f.ndim != 2 or f.shape[1] != 3:
        raise ValueError("Expected (N,3) positions and (M,3) triangles; triangulate polygons explicitly")
    if len(v) > MAX_VERTICES or len(f) > MAX_TRIANGLES:
        raise ValueError("Mesh display budget exceeded")
    if not np.all(np.isfinite(v)):
        raise ValueError("Coordinates must be finite")
    if f.size and (np.any(f < 0) or np.any(f >= len(v))):
        raise ValueError("Connectivity index out of range")
    v = np.array(v, dtype=np.float64, copy=True, order="C")
    f = np.array(f, dtype=np.int64, copy=True, order="C")
    v.setflags(write=False)
    f.setflags(write=False)
    return v, f
