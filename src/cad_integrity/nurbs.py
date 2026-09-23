"""Synchronous owned CPU NURBS evaluation; full Cartesian-grid outputs."""
from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from . import _native


@dataclass(frozen=True)
class EvaluationLimits:
    """Logical native payload and work admission, excluding Python normalization."""

    max_input_bytes: int = 256_000_000
    max_owned_bytes: int = 512_000_000
    max_output_bytes: int = 256_000_000
    max_work_steps: int = 100_000_000

    def __post_init__(self) -> None:
        for value in vars(self).values():
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**64:
                raise ValueError("NURBS limits must be uint64 integers")


@dataclass(frozen=True)
class SurfaceGeometry:
    """Caller-owned writable arrays, u-major grid; masked curvature is NaN."""

    points: NDArray[np.float64]
    normals: NDArray[np.float64]
    principal_max: NDArray[np.float64]
    principal_min: NDArray[np.float64]
    mean: NDArray[np.float64]
    gaussian: NDArray[np.float64]
    valid_mask: NDArray[np.bool_]


def evaluate_surface(
    degree_u: int, degree_v: int, knots_u: ArrayLike, knots_v: ArrayLike,
    control_points: ArrayLike, u_vec: ArrayLike, v_vec: ArrayLike, *,
    singular_policy: Literal["mask", "raise"] = "mask",
    regularity_tolerance: float = 1e-10,
    limits: EvaluationLimits = EvaluationLimits(),
) -> SurfaceGeometry:
    """Evaluate positions, oriented normals and algebraically ordered curvatures.

    Control points have shape (Nu,Nv,3) for Cartesian unit-weight data or
    (Nu,Nv,4) for homogeneous (x*w,y*w,z*w,w) data. Parameters are independent
    vectors, with closed domains and right-hand interior-knot derivatives.
    Inputs are explicitly normalized to native float64 C layout. Native code
    snapshots those arrays before releasing the GIL. No input is retained.
    """
    for degree in (degree_u, degree_v):
        if isinstance(degree, (bool, np.bool_)) or not isinstance(degree, (int, np.integer)):
            raise ValueError("NURBS degrees must be integers")
        if not 0 <= degree <= 2**31 - 1:
            raise ValueError("NURBS degree outside signed recurrence range")
    if singular_policy not in ("mask", "raise"):
        raise ValueError("singular_policy must be 'mask' or 'raise'")
    if (isinstance(regularity_tolerance, (bool, np.bool_)) or
            not isinstance(regularity_tolerance, Real)):
        raise ValueError("regularity_tolerance must be a real number")
    tolerance = float(regularity_tolerance)
    if not np.isfinite(tolerance) or not 0 < tolerance < 1:
        raise ValueError("regularity_tolerance must lie in (0, 1)")

    def normalize(value: ArrayLike) -> NDArray[np.float64]:
        if np.iscomplexobj(value):
            raise ValueError("NURBS inputs must be real")
        try:
            raw = np.asarray(value, dtype=np.float64)
        except (TypeError, ValueError) as exc:
            raise ValueError("NURBS inputs must be numeric") from exc
        if raw.ndim == 0:
            raise ValueError("NURBS inputs must be arrays")
        return np.ascontiguousarray(raw)

    cp = normalize(control_points)
    if cp.ndim != 3 or cp.shape[2] not in (3, 4):
        raise ValueError("NURBS control net requires (Nu,Nv,3|4)")
    if cp.shape[2] == 3:
        cp = np.concatenate((cp, np.ones((*cp.shape[:2], 1))), axis=2)
    arrays = _native.evaluate_nurbs(
        int(degree_u), int(degree_v), normalize(knots_u), normalize(knots_v), cp,
        normalize(u_vec), normalize(v_vec), tolerance, singular_policy == "raise",
        limits.max_input_bytes, limits.max_owned_bytes, limits.max_output_bytes,
        limits.max_work_steps,
    )
    return SurfaceGeometry(**arrays)
