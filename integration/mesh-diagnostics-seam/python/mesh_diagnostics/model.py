"""Validated triangle-surface input. No UI, I/O, topology repair, or silent coercion."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

import numpy as np
from numpy.typing import NDArray


class MeshValidationError(ValueError):
    """The input does not satisfy the triangle-surface contract."""


@dataclass(frozen=True, slots=True)
class MeshLimits:
    max_vertices: int = 250_000
    max_triangles: int = 500_000


def _matrix(value: Any, width: int, name: str) -> NDArray:
    try:
        arr = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise MeshValidationError(f"{name} must be a rectangular numeric array") from exc
    if arr.ndim == 1:
        if arr.size % width:
            raise MeshValidationError(f"flat {name} length must be divisible by {width}")
        arr = arr.reshape(-1, width)
    if arr.ndim != 2 or arr.shape[1] != width:
        raise MeshValidationError(f"{name} must have shape (N, {width}); got {arr.shape}")
    return arr


@dataclass(frozen=True, slots=True, init=False)
class TriangleMesh:
    positions: NDArray[np.float64]
    triangles: NDArray[np.int64]
    mesh_id: str
    geometry_revision: str
    stage: str
    units: str

    def __init__(
        self, positions: Any, triangles: Any, *, mesh_id: str = "mesh",
        geometry_revision: str | None = None, stage: str = "unspecified",
        units: str = "unspecified", limits: MeshLimits = MeshLimits(),
    ) -> None:
        v = _matrix(positions, 3, "positions")
        f = _matrix(triangles, 3, "triangles")
        if len(v) > limits.max_vertices or len(f) > limits.max_triangles:
            raise MeshValidationError("mesh exceeds configured inline-viewer limits")
        if v.dtype.kind not in "fiu" or (f.size and f.dtype.kind not in "iu"):
            raise MeshValidationError("positions must be real numbers and triangles must be integers")
        # Validate BEFORE casting: -1 must never become a large unsigned index.
        if f.size and (np.min(f) < 0 or np.max(f) >= len(v)):
            raise MeshValidationError("triangle index is outside [0, vertex_count)")
        with np.errstate(over="ignore", invalid="ignore"):
            vc = np.array(v, dtype=np.float64, order="C", copy=True)
        if not np.isfinite(vc).all():
            raise MeshValidationError("positions contain non-finite or unrepresentable coordinates")
        fc = np.array(f, dtype=np.int64, order="C", copy=True)
        for name, text in (("mesh_id", mesh_id), ("stage", stage), ("units", units)):
            if not isinstance(text, str) or not text or len(text) > 256:
                raise MeshValidationError(f"{name} must be a nonempty string of at most 256 characters")
        if geometry_revision is not None and (
            not isinstance(geometry_revision, str) or not geometry_revision or len(geometry_revision) > 256
        ):
            raise MeshValidationError("geometry_revision must be a nonempty string of at most 256 characters")
        if geometry_revision is None:
            digest = sha256()
            digest.update(b"triangle-surface-v1\0")
            digest.update(np.asarray([len(vc), len(fc)], dtype="<i8").tobytes())
            digest.update(vc.astype("<f8", copy=False).tobytes())
            digest.update(fc.astype("<i8", copy=False).tobytes())
            digest.update(units.encode("utf-8"))
            geometry_revision = digest.hexdigest()
        vc.flags.writeable = False
        fc.flags.writeable = False
        for key, value in dict(positions=vc, triangles=fc, mesh_id=mesh_id,
                               geometry_revision=geometry_revision, stage=stage, units=units).items():
            object.__setattr__(self, key, value)
