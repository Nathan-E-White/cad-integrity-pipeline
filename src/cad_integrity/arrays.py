"""Owned, read-only numeric arrays at public data boundaries."""
from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .errors import InvalidGeometry

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


def floats(value: ArrayLike, *, name: str, width: int | None = None) -> FloatArray:
    try:
        array = np.array(value, dtype=np.float64, order="C", copy=True)
    except (TypeError, ValueError, OverflowError) as exc:
        raise InvalidGeometry(f"{name} must contain real numbers") from exc
    if width is not None and (array.ndim != 2 or array.shape[1] != width):
        raise InvalidGeometry(f"{name} must have shape (N, {width}); got {array.shape}")
    if not np.all(np.isfinite(array)):
        raise InvalidGeometry(f"{name} contains NaN or infinity")
    array.flags.writeable = False
    return array


def integers(value: ArrayLike, *, name: str, width: int | None = None) -> IntArray:
    raw = np.asarray(value)
    # Do not silently truncate floating-point connectivity or accept boolean indices.
    if raw.dtype.kind not in "iu":
        raise InvalidGeometry(f"{name} must contain integer indices, not {raw.dtype}")
    if raw.size and raw.dtype.kind == "u" and int(raw.max()) > np.iinfo(np.int64).max:
        raise InvalidGeometry(f"{name} exceeds int64 range")
    array = np.array(raw, dtype=np.int64, order="C", copy=True)
    if width is None and array.ndim != 1:
        raise InvalidGeometry(f"{name} must be one-dimensional")
    if width is not None and (array.ndim != 2 or array.shape[1] != width):
        raise InvalidGeometry(f"{name} must have shape (N, {width}); got {array.shape}")
    array.flags.writeable = False
    return array


def require_indices(array: IntArray, size: int, name: str) -> None:
    if array.size and (np.any(array < 0) or np.any(array >= size)):
        raise InvalidGeometry(f"{name} contains indices outside [0, {size})")


def positive(value: float, name: str, *, allow_zero: bool = False) -> float:
    if isinstance(value, bool) or not np.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{name} must be {'nonnegative' if allow_zero else 'positive'}")
    return float(value)


def readonly(array: NDArray[Any]) -> NDArray[Any]:
    result = array.copy()
    result.flags.writeable = False
    return result
