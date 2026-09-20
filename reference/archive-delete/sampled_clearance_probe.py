"""Unqualified, read-only sampled-clearance evidence.

This is deliberately not called a medial-axis transform.  It compares supplied
interior probes with supplied boundary samples and records close, separated
nearest witnesses.  Neither the caller's inside/outside classification nor the
sampling coverage is verified here, so a result may support review only.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ClearanceWitness:
    probe_index: int
    radius: float
    boundary_indices: tuple[int, ...]
    is_small_clearance: bool


def probe_sampled_clearance(
    boundary_samples: np.ndarray,
    interior_probes: np.ndarray,
    *,
    small_clearance: float,
    tie_tolerance: float = 1e-4,
    minimum_witness_separation: float = 0.5,
) -> tuple[ClearanceWitness, ...]:
    """Return close-boundary observations for caller-supplied probe points.

    ``minimum_witness_separation`` is expressed as a multiple of the observed
    radius.  The implementation avoids the archived prototype's dense M-by-N
    distance matrix, but is still O(M*N).  It does not establish mediality,
    maximal balls, units, topology, or permission to delete/heal geometry.
    """
    boundary = np.asarray(boundary_samples, dtype=float)
    probes = np.asarray(interior_probes, dtype=float)
    if boundary.ndim != 2 or boundary.shape[1:] != (3,) or not len(boundary):
        raise ValueError("boundary_samples must be a non-empty (N, 3) array")
    if probes.ndim != 2 or probes.shape[1:] != (3,):
        raise ValueError("interior_probes must be an (M, 3) array")
    if not np.isfinite(boundary).all() or not np.isfinite(probes).all():
        raise ValueError("samples and probes must be finite")
    if small_clearance < 0 or tie_tolerance < 0 or minimum_witness_separation < 0:
        raise ValueError("clearance and tolerances must be non-negative")

    observations: list[ClearanceWitness] = []
    for probe_index, probe in enumerate(probes):
        distances = np.linalg.norm(boundary - probe, axis=1)
        radius = float(distances.min())
        # Coincident samples make the relative witness-separation rule meaningless.
        if radius <= 0.0:
            continue
        nearest = np.flatnonzero(np.abs(distances - radius) <= tie_tolerance)
        if len(nearest) < 2:
            continue
        witnesses = boundary[nearest]
        separation = np.linalg.norm(witnesses[:, None] - witnesses[None, :], axis=2).max()
        if separation < radius * minimum_witness_separation:
            continue
        observations.append(ClearanceWitness(
            probe_index, radius, tuple(int(index) for index in nearest), radius < small_clearance,
        ))
    return tuple(observations)
