"""One vectorized edge-incidence table, reused by all edge diagnostics.

O(F log F) time / O(F) temporary storage; not an O(F) or out-of-core algorithm.
No vertex welding, repair, loop counting, or global manifold certification.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray
from .model import TriangleMesh


@dataclass(frozen=True, slots=True)
class EdgeTopology:
    edges: NDArray[np.int64]          # unique undirected vertex-index pairs
    counts: NDArray[np.int64]         # incident face records per edge
    offsets: NDArray[np.int64]        # CSR offsets into incident_faces
    incident_faces: NDArray[np.int64] # source triangle IDs, grouped by edge
    boundary_edges: NDArray[np.int64]
    nonmanifold_edges: NDArray[np.int64]
    winding_conflict_edges: NDArray[np.int64]
    repeated_vertex_faces: NDArray[np.int64]
    duplicate_faces: NDArray[np.int64] # ALL members of duplicate groups


def edge_topology(mesh: TriangleMesh) -> EdgeTopology:
    f = mesh.triangles
    repeated = (f[:, 0] == f[:, 1]) | (f[:, 1] == f[:, 2]) | (f[:, 2] == f[:, 0])
    _, inverse, duplicate_counts = np.unique(np.sort(f, axis=1), axis=0,
                                            return_inverse=True, return_counts=True)
    duplicate_ids = np.flatnonzero(duplicate_counts[inverse] > 1)
    valid_ids = np.flatnonzero(~repeated)
    clean = f[valid_ids]
    directed = np.concatenate((clean[:, [0, 1]], clean[:, [1, 2]], clean[:, [2, 0]]))
    source_ids = np.tile(valid_ids, 3)
    undirected = np.sort(directed, axis=1)
    if not len(undirected):
        edges = np.empty((0, 2), dtype=np.int64)
        counts = np.empty(0, dtype=np.int64)
        offsets = np.array([0], dtype=np.int64)
        incident = np.empty(0, dtype=np.int64)
        conflicts = edges.copy()
    else:
        order = np.lexsort((undirected[:, 1], undirected[:, 0]))
        ordered = undirected[order]
        starts = np.r_[0, 1 + np.flatnonzero(np.any(ordered[1:] != ordered[:-1], axis=1))]
        offsets = np.r_[starts, len(ordered)]
        edges = ordered[starts]
        counts = np.diff(offsets)
        incident = source_ids[order]
        signs = np.where(directed[:, 0] < directed[:, 1], 1, -1)
        direction_sum = np.add.reduceat(signs[order], starts)
        conflicts = edges[(counts == 2) & (np.abs(direction_sum) == 2)]
    result = EdgeTopology(edges, counts, offsets, incident, edges[counts == 1],
                          edges[counts > 2], conflicts, np.flatnonzero(repeated), duplicate_ids)
    for name in result.__dataclass_fields__:
        getattr(result, name).flags.writeable = False
    return result
