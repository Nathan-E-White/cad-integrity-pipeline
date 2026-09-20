"""A small, evidence-preserving skeletal-graph pruning experiment.

The graph, radii, and boundary contacts are supplied by the caller.  This file
does not construct or validate a medial graph; its score is only a pruning
heuristic, not a geometric or manufacturing significance measure.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np


def contact_separation_scores(
    radii: Sequence[float], contacts: Sequence[tuple[Sequence[float], Sequence[float]]],
) -> np.ndarray:
    """Return clipped contact-distance/(2*radius) scores for supplied nodes."""
    if len(radii) != len(contacts):
        raise ValueError("radii and contacts must describe the same nodes")
    if not np.isfinite(radii).all():
        raise ValueError("radii must be finite")
    scores = np.zeros(len(radii), dtype=float)
    for index, (radius, pair) in enumerate(zip(radii, contacts, strict=True)):
        if radius <= 0:
            continue
        first, second = (np.asarray(point, dtype=float) for point in pair)
        if first.shape != (3,) or second.shape != (3,) or not np.isfinite((first, second)).all():
            raise ValueError("each contact pair must contain two finite 3D points")
        scores[index] = min(1.0, float(np.linalg.norm(first - second) / (2.0 * radius)))
    return scores


def prune_low_significance_leaves(
    adjacency: Mapping[int, Sequence[int]], scores: Sequence[float], *, threshold: float = 0.35,
) -> tuple[frozenset[int], dict[int, tuple[int, ...]]]:
    """Iteratively remove low-score degree-one nodes from an undirected graph.

    This has no error bound and does not preserve a proven medial topology.  It
    should be used only after a qualified graph construction has retained node
    radius and boundary-contact provenance.
    """
    score_array = np.asarray(scores, dtype=float)
    if not np.isfinite(score_array).all() or not np.isfinite(threshold):
        raise ValueError("scores and threshold must be finite")
    graph = {node: set(neighbors) for node, neighbors in adjacency.items()}
    if any(node < 0 or node >= len(score_array) for node in graph):
        raise ValueError("adjacency node IDs must index scores")
    if any(neighbor not in graph or node not in graph[neighbor]
           for node, neighbors in graph.items() for neighbor in neighbors):
        raise ValueError("adjacency must be symmetric and refer only to known nodes")
    active = set(graph)
    while True:
        removable = [node for node in active if len(graph[node] & active) == 1 and score_array[node] < threshold]
        if not removable:
            break
        active.difference_update(removable)
    return frozenset(active), {node: tuple(sorted(neighbors & active)) for node, neighbors in graph.items()}
