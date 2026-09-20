"""Import trajectories. Computing a motorcycle graph belongs to the meshing engine."""
from __future__ import annotations
from collections.abc import Sequence
import numpy as np
from .contracts import Trace


def traces_from_offsets(points: np.ndarray, offsets: np.ndarray, *, ids: Sequence[str] | None = None) -> list[Trace]:
    p, offsets = np.asarray(points), np.asarray(offsets)
    if p.ndim != 2 or p.shape[1] != 3 or p.dtype.kind not in "fiu" or not np.isfinite(p).all():
        raise ValueError("Path points require a finite real (P,3) array")
    if offsets.ndim != 1 or offsets.dtype.kind not in "iu" or not len(offsets):
        raise ValueError("Path offsets require a nonempty integer vector")
    if offsets[0] != 0 or offsets[-1] != len(p) or np.any(np.diff(offsets.astype(np.int64)) < 2):
        raise ValueError("Offsets must span the point array; each path needs at least two points")
    count = len(offsets) - 1
    if ids is not None and len(ids) != count:
        raise ValueError("One trace ID is required per path")
    return [Trace(id=ids[i] if ids is not None else f"path-{i}", label=f"Imported path {i}",
                  points=p[int(offsets[i]):int(offsets[i + 1])].astype(float).ravel().tolist())
            for i in range(count)]
