"""Extensions to the supplied mesh-healing / quad-strip pipeline.

Core dependency: NumPy and SciPy. CAD/ONNX dependencies are loaded by exporters.
Cotangent stiffness uses L = diag(W @ 1) - W (positive-semidefinite sign).
This is a geometry-aware harmonic map, NOT a general injectivity guarantee.
See README.md for the contracts, limitations, and mathematical references.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional, Mapping, Sequence, Iterable
import hashlib
import json
import logging
import math
import numbers
import warnings

import numpy as np
import scipy.linalg as la
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

LOG = logging.getLogger(__name__)
Edge = Tuple[int, int]
UVMap = Dict[int, Tuple[float, float]]


class MeshError(ValueError):
    """An input mesh or requested operation violates its declared contract."""


class TopologyError(MeshError):
    pass


class ParameterizationError(MeshError):
    pass


class StaleSystemError(RuntimeError):
    pass


def _edge(a: int, b: int) -> Edge:
    return (min(a, b), max(a, b))


def _index(value, size: int, name: str = "index") -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Integral):
        raise MeshError(f"{name} must be an integer, got {value!r}")
    value = int(value)
    if not 0 <= value < size:
        raise MeshError(f"{name} {value} is outside [0, {size})")
    return value


def _finite_array(value, shape, name: str) -> np.ndarray:
    result = np.asarray(value, dtype=np.float64)
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise MeshError(f"{name} must have shape {shape} and finite values")
    return result


def _cross2(a, b) -> float:
    return float(a[0] * b[1] - a[1] * b[0])


def _canonical_face(f: Sequence[int]) -> tuple:
    f = tuple(f)
    candidates = [f[i:] + f[:i] for i in range(len(f))]
    r = f[::-1]
    candidates.extend(r[i:] + r[:i] for i in range(len(r)))
    return min(candidates)


def _incidence(faces: Sequence[Sequence[int]]):
    edges = defaultdict(list)
    incident = defaultdict(list)
    for fid, f in enumerate(faces):
        for i, u in enumerate(f):
            v = f[(i + 1) % len(f)]
            edges[_edge(u, v)].append((fid, u, v))
            incident[u].append(fid)
    return edges, incident


def _face_fans(v: int, faces, edges, incident) -> List[List[int]]:
    """Connected incident-face fans, connected ONLY through an edge at v."""
    remaining = set(incident[v])
    graph = {f: set() for f in remaining}
    for fid in remaining:
        f = faces[fid]
        k = f.index(v)
        for other in (f[k - 1], f[(k + 1) % len(f)]):
            for g, _, _ in edges[_edge(v, other)]:
                if g != fid:
                    graph[fid].add(g)
    groups = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        group, queue = [start], [start]
        while queue:
            for g in graph[queue.pop()]:
                if g in remaining:
                    remaining.remove(g)
                    queue.append(g)
                    group.append(g)
        groups.append(sorted(group))
    return groups


@dataclass
class TopologyReport:
    boundary_edges: List[Edge]
    nonmanifold_edges: List[Edge]
    nonmanifold_vertices: List[int]
    inconsistent_winding_edges: List[Edge]
    duplicate_faces: List[int]
    unused_vertices: List[int]

    @property
    def is_manifold(self) -> bool:
        return not (self.nonmanifold_edges or self.nonmanifold_vertices
                    or self.duplicate_faces)

    @property
    def is_oriented_manifold(self) -> bool:
        return self.is_manifold and not self.inconsistent_winding_edges


@dataclass
class StitchReport:
    stitched_vertices: int
    accepted_edge_pairs: int
    rejected: List[str]
    old_to_new: np.ndarray


@dataclass
class PreprocessReport:
    removed_faces: List[int]
    split_vertices: int
    stitched_vertices: int
    old_to_new_vertices: Dict[int, Tuple[int, ...]]
    old_to_new_faces: Dict[int, int]
    stitch: StitchReport
    topology: TopologyReport

    def remap_constraints(self, constraints: Mapping[int, Sequence[float]],
                          atol: float = 1e-10) -> UVMap:
        """Fan-split vertices duplicate the constraint; conflicting welds fail."""
        if not np.isfinite(atol) or atol < 0:
            raise MeshError("atol must be finite and nonnegative")
        out = {}
        for old, value in constraints.items():
            old = _index(old, len(self.old_to_new_vertices), "old vertex")
            uv = _finite_array(value, (2,), "boundary UV")
            targets = self.old_to_new_vertices[old]
            if not targets:
                raise MeshError(f"Constraint references removed vertex {old}")
            for new in targets:
                if new in out and not np.allclose(out[new], uv, atol=atol, rtol=0):
                    raise MeshError(f"Conflicting constraints were welded at vertex {new}")
                out[new] = tuple(map(float, uv))
        return out


@dataclass
class UVQuality:
    triangle_count: int
    flipped_triangles: List[int]
    degenerate_triangles: List[int]
    minimum_signed_double_area: float
    maximum_conformal_distortion: float

    @property
    def locally_valid(self) -> bool:
        return not (self.flipped_triangles or self.degenerate_triangles)


def _triangulate_face(vertices: np.ndarray, face: Sequence[int],
                      relative_tol: float = 1e-12) -> List[List[int]]:
    """Projected ear clipping, preserving polygon winding and original IDs.

    Triangles and simple mildly nonplanar quads are supported. For larger
    polygons, projection must be simple; no holes or self-intersections.
    Triangular geometry is the actual piecewise-linear surface being solved.
    """
    f = list(face)
    if len(f) < 3 or len(set(f)) != len(f):
        raise MeshError("A face needs at least three distinct, nonrepeated vertices")
    p = vertices[f] - vertices[f[0]]
    scale = np.max(np.linalg.norm(p, axis=1))
    if not np.isfinite(scale) or scale <= 0:
        raise MeshError("Collapsed face")
    p = p / scale
    normal = sum((np.cross(p[i], p[(i + 1) % len(f)])
                  for i in range(len(f))), start=np.zeros(3))
    if np.linalg.norm(normal) <= relative_tol:
        raise MeshError("Degenerate or self-intersecting face")
    axis = int(np.argmax(np.abs(normal)))
    q = np.delete(p, axis, axis=1)
    area = sum(_cross2(q[i], q[(i + 1) % len(f)]) for i in range(len(f)))
    sign = 1.0 if area > 0 else -1.0

    def on_segment(a, b, x):
        return (abs(_cross2(b - a, x - a)) <= relative_tol
                and np.all(x >= np.minimum(a, b) - relative_tol)
                and np.all(x <= np.maximum(a, b) + relative_tol))

    def intersects(a, b, c, d):
        s1, s2 = _cross2(b - a, c - a), _cross2(b - a, d - a)
        s3, s4 = _cross2(d - c, a - c), _cross2(d - c, b - c)
        if s1 * s2 < 0 and s3 * s4 < 0:
            return True
        return (on_segment(a, b, c) or on_segment(a, b, d)
                or on_segment(c, d, a) or on_segment(c, d, b))

    n = len(f)
    for i in range(n):
        for j in range(i + 1, n):
            if j in (i, (i + 1) % n) or (j + 1) % n == i:
                continue
            if intersects(q[i], q[(i + 1) % n], q[j], q[(j + 1) % n]):
                raise MeshError("Self-intersecting projected polygon")
    if n == 3:
        return [f]
    # Preserve the supplied quad's original 0--2 diagonal when valid.
    if n == 4:
        for tri_ids in (((0, 1, 2), (0, 2, 3)), ((0, 1, 3), (1, 2, 3))):
            if all(sign * _cross2(q[b] - q[a], q[c] - q[a]) > relative_tol
                   for a, b, c in tri_ids):
                return [[f[a], f[b], f[c]] for a, b, c in tri_ids]
        raise MeshError("No valid nondegenerate diagonal for quad")
    remaining, triangles = list(range(n)), []
    while len(remaining) > 3:
        for k, b in enumerate(remaining):
            a, c = remaining[k - 1], remaining[(k + 1) % len(remaining)]
            if sign * _cross2(q[b] - q[a], q[c] - q[a]) <= relative_tol:
                continue
            inside = False
            for x in remaining:
                if x in (a, b, c):
                    continue
                if min(sign * _cross2(q[b] - q[a], q[x] - q[a]),
                       sign * _cross2(q[c] - q[b], q[x] - q[b]),
                       sign * _cross2(q[a] - q[c], q[x] - q[c])) >= -relative_tol:
                    inside = True
                    break
            if not inside:
                triangles.append([f[a], f[b], f[c]])
                remaining.pop(k)
                break
        else:
            raise MeshError("Cannot triangulate polygon without degenerate ears")
    a, b, c = remaining
    if sign * _cross2(q[b] - q[a], q[c] - q[a]) <= relative_tol:
        raise MeshError("Degenerate final polygon triangle")
    triangles.append([f[a], f[b], f[c]])
    return triangles


class MeshHealingEngine:
    def __init__(self, vertices: np.ndarray, faces: List[List[int]]):
        """Keep owned copies; vertices are (N,3), faces may be triangles/quads.

        Structural corruption (invalid indices/nonfinite coordinates) fails on
        input. Degenerate/duplicate faces can be cleaned by preprocess().
        """
        vertices = np.asarray(vertices, dtype=float)
        if vertices.ndim != 2 or vertices.shape[1] != 3 or not np.all(np.isfinite(vertices)):
            raise MeshError("vertices must be a finite (N,3) array")
        self.v3d = vertices.copy()
        self.faces = [[_index(v, len(vertices), "face vertex") for v in f] for f in faces]
        self.num_vertices = len(vertices)
        self._revision = 0
        self.last_stitch_report: Optional[StitchReport] = None
        self.last_preprocess_report: Optional[PreprocessReport] = None
        self.last_uv_quality: Optional[UVQuality] = None
        self._build_topology()

    def _build_topology(self):
        """Reset, rather than append to, all connectivity after edits."""
        self.num_vertices = len(self.v3d)
        self.adjacency = {i: set() for i in range(self.num_vertices)}
        self.edge_faces, self.vertex_faces = _incidence(self.faces)
        for u, v in self.edge_faces:
            self.adjacency[u].add(v)
            self.adjacency[v].add(u)

    def _fingerprint(self) -> bytes:
        # Also catches direct mutation of the public arrays kept for compatibility.
        h = hashlib.blake2b(digest_size=20)
        h.update(np.asarray(self.v3d, dtype='<f8').tobytes())
        h.update(repr(self.faces).encode())
        return h.digest()

    def topology_report(self) -> TopologyReport:
        edges, incident = _incidence(self.faces)
        invalid_vertices = []
        for v, fs in incident.items():
            link = defaultdict(list)
            bad = False
            for fid in fs:
                f = self.faces[fid]
                if f.count(v) != 1 or len(f) < 3:
                    bad = True
                    break
                i = f.index(v)
                a, b = f[i - 1], f[(i + 1) % len(f)]
                link[a].append(b)
                link[b].append(a)
            if not bad:
                unseen = set(link)
                if unseen:
                    stack = [unseen.pop()]
                    while stack:
                        for x in link[stack.pop()]:
                            if x in unseen:
                                unseen.remove(x)
                                stack.append(x)
                ends = sum(len(ns) == 1 for ns in link.values())
                bad = (bool(unseen) or any(len(ns) > 2 for ns in link.values())
                       or ends not in (0, 2))
            if bad:
                invalid_vertices.append(v)
        seen, duplicate_faces = set(), []
        for i, f in enumerate(self.faces):
            if not f:
                duplicate_faces.append(i)
                continue
            key = _canonical_face(f)
            if key in seen:
                duplicate_faces.append(i)
            seen.add(key)
        return TopologyReport(
            sorted(e for e, fs in edges.items() if len(fs) == 1),
            sorted(e for e, fs in edges.items() if len(fs) > 2),
            sorted(invalid_vertices),
            sorted(e for e, fs in edges.items()
                   if len(fs) == 2 and fs[0][1:] == fs[1][1:]),
            duplicate_faces,
            sorted(set(range(self.num_vertices)) - set(incident)),
        )

    def triangulated_faces(self, face_ids: Optional[Sequence[int]] = None):
        ids = list(range(len(self.faces))) if face_ids is None else list(face_ids)
        if len(ids) != len(set(ids)):
            raise MeshError("face_ids contains duplicates")
        triangles, parents = [], []
        for fid in ids:
            fid = _index(fid, len(self.faces), "face")
            try:
                ts = _triangulate_face(self.v3d, self.faces[fid])
            except MeshError as exc:
                raise MeshError(f"Face {fid}: {exc}; run preprocess() or repair the input") from exc
            triangles.extend(ts)
            parents.extend([fid] * len(ts))
        return (np.asarray(triangles, dtype=np.int64).reshape(-1, 3),
                np.asarray(parents, dtype=np.int64))

    def _orient_faces(self):
        edges, _ = _incidence(self.faces)
        if any(len(fs) > 2 for fs in edges.values()):
            raise TopologyError("An edge has more than two incident faces; sheet ownership is ambiguous")
        graph = defaultdict(list)
        for fs in edges.values():
            if len(fs) == 2:
                (a, u, v), (b, x, y) = fs
                same = (u, v) == (x, y)
                graph[a].append((b, same))
                graph[b].append((a, same))
        flips = {}
        for seed in range(len(self.faces)):
            if seed in flips:
                continue
            flips[seed] = False
            queue = deque([seed])
            while queue:
                a = queue.popleft()
                for b, toggle in graph[a]:
                    wanted = flips[a] ^ toggle
                    if b in flips and flips[b] != wanted:
                        raise TopologyError("Mesh is not consistently orientable")
                    if b not in flips:
                        flips[b] = wanted
                        queue.append(b)
        self.faces = [f[::-1] if flips[i] else f[:] for i, f in enumerate(self.faces)]
        self._build_topology()

    def non_manifold_stitching(self, tolerance: float = 1e-5, *,
                              seam_pairs: Optional[Sequence[Tuple[Edge, Edge]]] = None) -> int:
        """Conservatively stitch matching boundary EDGES, not all nearby vertices.

        Each seam joins both endpoints atomically. Automatic matching requires
        an unambiguous edge partner, actual Euclidean endpoint distances <= tol,
        a cluster-diameter bound, and a valid oriented manifold after each edit.
        It rejects likely overlapping sheets via an inward-direction check.
        Explicit seam_pairs bypass only that geometric heuristic/partner search.
        Does not close genuine holes, split T-junction edges, or choose among
        three-plus sheets sharing one edge. Returns the old integer weld count.
        """
        if not np.isfinite(tolerance) or tolerance <= 0:
            raise MeshError("stitch tolerance must be finite and strictly positive")
        if not self.topology_report().is_manifold:
            raise TopologyError("Run preprocess() before stitching degenerate/nonmanifold input")
        n = self.num_vertices
        parent = np.arange(n)
        boundary = sorted(e for e, fs in self.edge_faces.items() if len(fs) == 1)
        rejected = []

        def root(a, p=parent):
            while p[a] != a:
                a = int(p[a])
            return a

        def endpoints(e, f):
            choices = [((e[0], f[0]), (e[1], f[1])),
                       ((e[0], f[1]), (e[1], f[0]))]
            scores = [max(np.linalg.norm(self.v3d[a] - self.v3d[b]) for a, b in choice)
                      for choice in choices]
            k = int(np.argmin(scores))
            return choices[k] if scores[k] <= tolerance else None

        candidates = []
        if seam_pairs is None and len(boundary) > 1:
            mid = np.array([0.5 * (self.v3d[a] + self.v3d[b]) for a, b in boundary])
            for i, j in sorted(cKDTree(mid).query_pairs(tolerance)):
                e, f = boundary[i], boundary[j]
                pairing = endpoints(e, f)
                if pairing is None or self.edge_faces[e][0][0] == self.edge_faces[f][0][0]:
                    continue
                direction = self.v3d[e[1]] - self.v3d[e[0]]
                length = np.linalg.norm(direction)
                if length <= tolerance:
                    rejected.append(f"{e}/{f}: edge too short relative to tolerance")
                    continue
                direction /= length
                center = mid[i]
                a = self.v3d[self.faces[self.edge_faces[e][0][0]]].mean(axis=0) - center
                b = self.v3d[self.faces[self.edge_faces[f][0][0]]].mean(axis=0) - mid[j]
                a -= np.dot(a, direction) * direction
                b -= np.dot(b, direction) * direction
                norm = np.linalg.norm(a) * np.linalg.norm(b)
                if norm == 0 or np.dot(a, b) / norm > math.cos(math.radians(30)):
                    rejected.append(f"{e}/{f}: likely overlapping sheets or a sharp ambiguous fold")
                    continue
                candidates.append((e, f, pairing))
            counts = defaultdict(int)
            for e, f, _ in candidates:
                counts[e] += 1
                counts[f] += 1
            safe = []
            for e, f, pairing in candidates:
                if counts[e] == counts[f] == 1:
                    safe.append((e, f, pairing))
                else:
                    rejected.append(f"{e}/{f}: multiple possible seam partners")
            candidates = safe
        elif seam_pairs is not None:
            used = set()
            for e, f in seam_pairs:
                e = _edge(*(_index(v, n) for v in e))
                f = _edge(*(_index(v, n) for v in f))
                if e not in boundary or f not in boundary or e == f or e in used or f in used:
                    raise MeshError("Explicit seam pairs must be distinct, uniquely paired boundary edges")
                if self.edge_faces[e][0][0] == self.edge_faces[f][0][0]:
                    raise MeshError("Cannot stitch two edges of the same face")
                pairing = endpoints(e, f)
                if pairing is None:
                    raise MeshError("Explicit seam endpoints exceed the Euclidean tolerance")
                candidates.append((e, f, pairing))
                used.update((e, f))

        accepted = 0
        for e, f, pairing in candidates:
            trial = parent.copy()
            for a, b in pairing:
                a, b = root(a, trial), root(b, trial)
                trial[max(a, b)] = min(a, b)
            reps = np.array([root(i, trial) for i in range(n)], dtype=int)
            changed_roots = {int(reps[a]) for pair in pairing for a in pair}
            diameter_ok = True
            for r in changed_roots:
                points = self.v3d[reps == r]
                for p in points:
                    if np.any(np.linalg.norm(points - p, axis=1) > tolerance):
                        diameter_ok = False
                        break
            if not diameter_ok:
                rejected.append(f"{e}/{f}: transitive weld exceeds tolerance")
                continue
            trial_faces = [[int(reps[v]) for v in face] for face in self.faces]
            test = MeshHealingEngine(self.v3d, trial_faces)
            try:
                test.triangulated_faces()
                if not test.topology_report().is_manifold:
                    raise TopologyError("weld would create duplicate/nonmanifold cells")
                test._orient_faces()
            except MeshError as exc:
                rejected.append(f"{e}/{f}: {exc}")
                continue
            parent[:] = trial
            accepted += 1
        representatives = np.array([root(i) for i in range(n)], dtype=int)
        unique, inverse = np.unique(representatives, return_inverse=True)
        count = n - len(unique)
        if count:
            # Coordinates MUST use the same representatives as face remapping.
            self.v3d = self.v3d[unique].copy()
            self.faces = [[int(inverse[v]) for v in f] for f in self.faces]
            self._orient_faces()
            self._revision += 1
        self._build_topology()
        self.last_stitch_report = StitchReport(count, accepted, rejected, inverse)
        return count

    def preprocess(self, stitch_tolerance: float = 1e-5, *,
                   stitch: bool = True, split_bowties: bool = True,
                   seam_pairs=None) -> PreprocessReport:
        """Transactional pre-pruner: clean -> split fans -> orient -> stitch.

        Preserves a mapping from each original vertex to zero/one/multiple new
        vertices. Arbitrary multi-sheet edges fail without changing the engine.
        Removed face IDs and provenance are returned, not silently discarded.
        """
        work = MeshHealingEngine(self.v3d, self.faces)
        old_n = self.num_vertices
        origins = list(range(old_n))
        clean, source_faces, removed, seen = [], [], [], set()
        for fid, face in enumerate(work.faces):
            f = []
            for v in face:
                if not f or f[-1] != v:
                    f.append(v)
            if len(f) > 1 and f[0] == f[-1]:
                f.pop()
            try:
                _triangulate_face(work.v3d, f)
                key = _canonical_face(f)
                if key in seen:
                    raise MeshError("Duplicate face")
            except MeshError:
                removed.append(fid)
                continue
            seen.add(key)
            clean.append(f)
            source_faces.append(fid)
        if not clean:
            raise TopologyError("Preprocessing would remove every face")
        work.faces = clean
        work._build_topology()
        if work.topology_report().nonmanifold_edges:
            raise TopologyError("Three-plus incident faces on an edge require explicit sheet separation")
        added = 0
        if split_bowties:
            edges, incident = _incidence(work.faces)
            coords = work.v3d.tolist()
            all_fans = {v: _face_fans(v, work.faces, edges, incident) for v in sorted(incident)}
            for v, groups in all_fans.items():
                for group in groups[1:]:
                    new = len(coords)
                    coords.append(work.v3d[v].tolist())
                    origins.append(v)
                    added += 1
                    for fid in group:
                        work.faces[fid] = [new if x == v else x for x in work.faces[fid]]
            work.v3d = np.asarray(coords, dtype=float)
            work._build_topology()
        if seam_pairs is not None and added:
            split_originals = set(origins[old_n:])
            if any(v in split_originals for pair in seam_pairs for edge in pair for v in edge):
                raise TopologyError("Explicit seam IDs became ambiguous after fan splitting; "
                                    "preprocess with stitch=False, then select the new boundary edges")
        work._orient_faces()
        if not work.topology_report().is_oriented_manifold:
            raise TopologyError("Unresolved nonmanifold vertex fan")
        if stitch:
            work.non_manifold_stitching(stitch_tolerance, seam_pairs=seam_pairs)
            stitch_report = work.last_stitch_report
        else:
            stitch_report = StitchReport(0, 0, [], np.arange(len(work.v3d)))
        assert stitch_report is not None
        active = sorted({v for f in work.faces for v in f})
        compact = {v: i for i, v in enumerate(active)}
        provenance = {i: set() for i in range(old_n)}
        for expanded, original in enumerate(origins):
            welded = int(stitch_report.old_to_new[expanded])
            if welded in compact:
                provenance[original].add(compact[welded])
        work.v3d = work.v3d[active].copy()
        work.faces = [[compact[v] for v in f] for f in work.faces]
        work._build_topology()
        work.triangulated_faces()
        final = work.topology_report()
        if not final.is_oriented_manifold:
            raise TopologyError("Post-repair topology verification failed")
        report = PreprocessReport(removed, added, stitch_report.stitched_vertices,
                                  {k: tuple(sorted(v)) for k, v in provenance.items()},
                                  {old: new for new, old in enumerate(source_faces)},
                                  stitch_report, final)
        self.v3d, self.faces = work.v3d, work.faces
        self._revision += 1
        self._build_topology()
        self.last_preprocess_report = report
        self.last_stitch_report = stitch_report
        return report

    def compute_cotangent_weights(self, *, face_ids=None,
                                  face_confidence: Optional[Mapping[int, float]] = None) -> sp.csr_matrix:
        """Symmetric off-diagonal W; L=diag(W.sum(axis=1))-W.

        Each triangle contributes half the cotangent opposite an edge. Boundary
        edges have one contribution, interior edges two. Signed cotangents are
        retained. Confidence multiplies a whole triangle's FEM stiffness, not
        arbitrarily selected edge weights, preserving positive semidefiniteness.
        """
        triangles, parents = self.triangulated_faces(face_ids)
        confidence = {} if face_confidence is None else dict(face_confidence)
        for fid, c in confidence.items():
            _index(fid, len(self.faces), "confidence face")
            if not np.isfinite(c) or not 0 <= c <= 1:
                raise MeshError("Face confidence must be finite and in [0,1]")
        rows, cols, values = [], [], []
        for tri, fid in zip(triangles, parents):
            c = float(confidence.get(int(fid), 1.0))
            if c == 0:
                continue
            p = self.v3d[tri]
            scale = max(np.linalg.norm(p[1] - p[0]), np.linalg.norm(p[2] - p[0]),
                        np.linalg.norm(p[2] - p[1]))
            q = (p - p[0]) / scale
            double_area = np.linalg.norm(np.cross(q[1], q[2]))
            if double_area <= 1e-12:
                raise MeshError(f"Near-degenerate triangle in face {fid}")
            for k in range(3):
                i, j = (k + 1) % 3, (k + 2) % 3
                w = 0.5 * c * float(np.dot(q[i] - q[k], q[j] - q[k])) / double_area
                a, b = int(tri[i]), int(tri[j])
                rows.extend((a, b))
                cols.extend((b, a))
                values.extend((w, w))
        W = sp.coo_matrix((values, (rows, cols)), shape=(self.num_vertices, self.num_vertices)).tocsr()
        W.sum_duplicates()
        W.eliminate_zeros()
        return W

    def compute_cotangent_laplacian(self, **kwargs) -> sp.csr_matrix:
        W = self.compute_cotangent_weights(**kwargs)
        return (sp.diags(np.asarray(W.sum(axis=1)).ravel()) - W).tocsr()

    def prepare_harmonic_system(self, internal_nodes: List[int], boundary_nodes: Sequence[int],
                                **kwargs) -> 'HarmonicSystem':
        return HarmonicSystem(self, internal_nodes, boundary_nodes, **kwargs)

    def compute_harmonic_map(self, internal_nodes: List[int],
                             boundary_constraints: Dict[int, Tuple[float, float]], *,
                             face_ids=None, face_confidence=None,
                             soft_constraints=None, check_orientation=True) -> UVMap:
        system = self.prepare_harmonic_system(internal_nodes, list(boundary_constraints),
                                              face_ids=face_ids, face_confidence=face_confidence)
        return system.solve(boundary_constraints, soft_constraints=soft_constraints,
                            check_orientation=check_orientation)

    def repair_contaminated_coordinates(self, coords_2d: Mapping[int, Sequence[float]],
                                        contaminated_vertices: Iterable[int], *,
                                        face_ids=None, check_orientation=True) -> UVMap:
        """Recompute flagged UV values while keeping EVERY unflagged value exact.

        This uses an explicit caller-supplied mask, not a contamination detector.
        It repairs UV data, not damaged 3D geometry. Invalid retained data can
        still make a fold-free solution impossible.
        """
        bad = sorted(set(contaminated_vertices))
        trusted = {v: uv for v, uv in coords_2d.items() if v not in bad}
        if not set(bad) <= set(coords_2d):
            raise MeshError("Contaminated vertices must belong to coords_2d")
        system = self.prepare_harmonic_system(bad, list(trusted), face_ids=face_ids,
                                              require_full_boundary=False)
        return system.solve(trusted, check_orientation=check_orientation)

    def validate_uv(self, coords_2d: Mapping[int, Sequence[float]], *,
                    face_ids=None, orientation: int = 1) -> UVQuality:
        if orientation not in (-1, 1):
            raise MeshError("orientation must be +1 or -1")
        triangles, _ = self.triangulated_faces(face_ids)
        flipped, degenerate, areas, distortion = [], [], [], []
        for tid, tri in enumerate(triangles):
            try:
                q = np.array([_finite_array(coords_2d[int(v)], (2,), "UV") for v in tri])
            except KeyError as exc:
                raise MeshError(f"Missing UV for vertex {exc.args[0]}") from exc
            dq = q[1:] - q[0]
            a = orientation * _cross2(dq[0], dq[1])
            areas.append(a)
            scale2 = max(float(np.dot(x, x)) for x in (dq[0], dq[1], q[2] - q[1]))
            if abs(a) <= 1e-12 * scale2 or scale2 == 0:
                degenerate.append(tid)
                distortion.append(float('inf'))
                continue
            if a < 0:
                flipped.append(tid)
            p = self.v3d[tri]
            e1, e2 = p[1] - p[0], p[2] - p[0]
            x = np.linalg.norm(e1)
            tangent = e1 / x
            y = float(np.dot(e2, tangent))
            z = np.linalg.norm(e2 - y * tangent)
            intrinsic = np.array([[x, y], [0.0, z]])
            J = np.linalg.solve(intrinsic.T, dq).T
            singular = np.linalg.svd(J, compute_uv=False)
            distortion.append(float(singular[0] / singular[-1]))
        return UVQuality(len(triangles), flipped, degenerate,
                         min(areas, default=float('nan')), max(distortion, default=float('nan')))

    def export_step(self, filename: str, coords_2d=None, **kwargs):
        from mesh_export import export_step
        return export_step(self, filename, coords_2d=coords_2d, **kwargs)

    def export_mock_step_structure(self, filename: str, coords_2d: UVMap):
        """Compatibility entry point; now produces real planar STEP faces."""
        warnings.warn("export_mock_step_structure now writes real faceted STEP; use export_step",
                      DeprecationWarning, stacklevel=2)
        return self.export_step(filename, coords_2d, space="uv")


@dataclass(frozen=True)
class SoftConstraint:
    target: Tuple[float, float]
    weight: float = 1.0

    def __post_init__(self):
        target = _finite_array(self.target, (2,), "soft target")
        if not np.isfinite(self.weight) or self.weight < 0:
            raise MeshError("Soft-constraint weight must be finite and nonnegative")
        object.__setattr__(self, "target", tuple(map(float, target)))
        object.__setattr__(self, "weight", float(self.weight))


class HarmonicSystem:
    """Reusable Dirichlet factorization, with bounded-rank soft updates.

        A X = -L_IB B
        (A + S C S.T) X = -L_IB B + S C Y

    A is factored once. Boundary changes and target-only changes only change
    the RHS. Up to max_update_rank soft anchors use the Woodbury identity;
    larger/ill-conditioned updates get a separate sparse factorization.
    Each solve's soft_constraints describes the COMPLETE current anchor set,
    not a delta, so removing an anchor cannot leave residual state behind.
    Not thread-safe: give concurrent workers independent system objects.
    """
    def __init__(self, engine: MeshHealingEngine, internal_nodes: Sequence[int],
                 boundary_nodes: Sequence[int], *, face_ids=None, face_confidence=None,
                 require_full_boundary: bool = True, max_update_rank: int = 32):
        self.engine = engine
        self.internal = tuple(_index(v, engine.num_vertices) for v in internal_nodes)
        self.boundary = tuple(_index(v, engine.num_vertices) for v in boundary_nodes)
        ordered = self.internal + self.boundary
        if len(ordered) != len(set(ordered)):
            raise MeshError("Internal and boundary vertex sets must be disjoint and duplicate-free")
        self.face_ids = (tuple(range(len(engine.faces))) if face_ids is None else tuple(face_ids))
        if len(self.face_ids) != len(set(self.face_ids)):
            raise MeshError("face_ids contains duplicates")
        for fid in self.face_ids:
            _index(fid, len(engine.faces), "face")
        if not self.face_ids:
            raise ParameterizationError("A harmonic patch needs at least one face")
        selected_faces = [engine.faces[fid] for fid in self.face_ids]
        active = {v for f in selected_faces for v in f}
        if set(ordered) != active:
            raise MeshError("Internal plus boundary IDs must equal the selected patch's vertex set; "
                            "pass face_ids for a macro-patch within a larger mesh")
        local_topology = MeshHealingEngine(engine.v3d, selected_faces).topology_report()
        if not local_topology.is_oriented_manifold:
            raise TopologyError("Harmonic map requires an oriented manifold patch; run preprocess()")
        if require_full_boundary:
            boundary_vertices = {v for e in local_topology.boundary_edges for v in e}
            missing = boundary_vertices - set(self.boundary)
            if missing:
                raise ParameterizationError(f"Boundary vertices lack Dirichlet values: {sorted(missing)}")
        self.require_full_boundary = require_full_boundary
        self.max_update_rank = _index(max_update_rank, 1_000_001, "max_update_rank")
        self.face_confidence = {} if face_confidence is None else dict(face_confidence)
        self._revision = engine._revision
        self._signature = engine._fingerprint()
        L = engine.compute_cotangent_laplacian(face_ids=self.face_ids,
                                               face_confidence=self.face_confidence)
        self.L = L[list(ordered), :][:, list(ordered)].tocsr()
        n = len(self.internal)
        self.A = self.L[:n, :n].tocsc()
        self.L_IB = self.L[:n, n:].tocsr()
        self._internal_index = {v: i for i, v in enumerate(self.internal)}
        # Connectivity is checked on assembled support, including confidence=0 cuts.
        graph = abs(self.L).tocsr()
        graph.setdiag(0)
        graph.eliminate_zeros()
        _, labels = connected_components(graph, directed=False)
        for component in np.unique(labels[:n]):
            if not np.any(labels[n:] == component):
                vertices = [ordered[k] for k in np.flatnonzero(labels == component)]
                raise ParameterizationError(f"Unanchored component {vertices}; zero confidence may disconnect it")
        self.factorization_count = 0
        self.base_factorization_count = 0
        self.low_rank_update_count = 0
        self.last_update_method = "none"
        self.last_relative_residual = float('nan')
        self.last_quality: Optional[UVQuality] = None
        self._update_key = None
        self._update_cache = None
        if n:
            try:
                self._lu = spla.splu(self.A)
            except RuntimeError as exc:
                raise ParameterizationError("Singular Dirichlet matrix; inspect components and degenerate faces") from exc
            self.factorization_count = self.base_factorization_count = 1
        else:
            self._lu = None

    def _check_fresh(self):
        if self.engine._revision != self._revision or self.engine._fingerprint() != self._signature:
            raise StaleSystemError("Geometry/topology changed: remap constraints and prepare a new harmonic system")

    def with_face_confidence(self, face_confidence: Mapping[int, float]) -> 'HarmonicSystem':
        """Explicitly rebuild: FEM coefficients changed, not merely the RHS."""
        self._check_fresh()
        return HarmonicSystem(self.engine, self.internal, self.boundary,
                              face_ids=self.face_ids, face_confidence=face_confidence,
                              require_full_boundary=self.require_full_boundary,
                              max_update_rank=self.max_update_rank)

    def solve(self, boundary_constraints: Mapping[int, Sequence[float]], *,
              soft_constraints: Optional[Mapping[int, SoftConstraint]] = None,
              check_orientation: bool = True, orientation: int = 1) -> UVMap:
        self._check_fresh()
        for v in boundary_constraints:
            _index(v, self.engine.num_vertices, "boundary vertex")
        if set(boundary_constraints) != set(self.boundary):
            raise MeshError("A reused system requires the same boundary ID set (values may change)")
        B = np.array([_finite_array(boundary_constraints[v], (2,), "boundary UV")
                      for v in self.boundary], dtype=float).reshape(-1, 2)
        anchors = {} if soft_constraints is None else dict(soft_constraints)
        for v, anchor in anchors.items():
            _index(v, self.engine.num_vertices, "soft-anchor vertex")
            if v not in self._internal_index:
                raise MeshError(f"Soft anchor {v} must be an internal vertex, not a Dirichlet vertex")
            if not isinstance(anchor, SoftConstraint):
                raise MeshError("Use SoftConstraint(target=(u,v), weight=...) for each soft anchor")
        anchors = {v: a for v, a in anchors.items() if a.weight > 0}
        n = len(self.internal)
        rhs = np.asarray(-self.L_IB @ B)
        ids = sorted(anchors)
        rows = np.array([self._internal_index[v] for v in ids], dtype=int)
        weights = np.array([anchors[v].weight for v in ids])
        diagonal = np.zeros(n)
        diagonal[rows] = weights
        if ids:
            rhs[rows] += weights[:, None] * np.array([anchors[v].target for v in ids])
        effective = self.A + sp.diags(diagonal, format='csc')
        if not n:
            X = np.empty((0, 2))
            self.last_update_method = "boundary-only"
        elif not ids:
            X = self._lu.solve(rhs)
            self.last_update_method = "base-factorization"
        else:
            key = tuple((v, anchors[v].weight) for v in ids)
            if self._update_key != key:
                cache = None
                if len(ids) <= self.max_update_rank:
                    U = np.zeros((n, len(ids)))
                    U[rows, np.arange(len(ids))] = np.sqrt(weights)
                    Z = self._lu.solve(U)
                    small = np.eye(len(ids)) + U.T @ Z
                    if np.all(np.isfinite(small)) and np.linalg.cond(small) < 1e12:
                        try:
                            factor = la.cho_factor(0.5 * (small + small.T), lower=True)
                            cache = ("woodbury", U, Z, factor)
                            self.low_rank_update_count += 1
                        except la.LinAlgError:
                            cache = None
                if cache is None:
                    try:
                        lu = spla.splu(effective)
                    except RuntimeError as exc:
                        raise ParameterizationError("Soft-update factorization failed") from exc
                    cache = ("refactor", lu)
                    self.factorization_count += 1
                self._update_key, self._update_cache = key, cache
            cache = self._update_cache
            self.last_update_method = cache[0]
            if cache[0] == "woodbury":
                _, U, Z, factor = cache
                base = self._lu.solve(rhs)
                X = base - Z @ la.cho_solve(factor, U.T @ base)
            else:
                X = cache[1].solve(rhs)
        # Check backward error; do not silently return a poor Woodbury update.
        def residual(x):
            if not n:
                return 0.0
            norm_a = float(np.max(np.asarray(abs(effective).sum(axis=1))))
            denom = norm_a * np.linalg.norm(x, ord=np.inf) + np.linalg.norm(rhs, ord=np.inf)
            return float(np.linalg.norm(effective @ x - rhs, ord=np.inf) / max(denom, np.finfo(float).tiny))
        error = residual(X)
        if (not np.all(np.isfinite(X)) or error > 1e-10) and n and self.last_update_method == "woodbury":
            lu = spla.splu(effective)
            self._update_cache = ("refactor", lu)
            self.factorization_count += 1
            X = lu.solve(rhs)
            self.last_update_method = "refactor-after-residual-check"
            error = residual(X)
        if not np.all(np.isfinite(X)) or error > 1e-10:
            raise ParameterizationError(f"Unacceptable linear-system residual: {error:g}")
        self.last_relative_residual = error
        coords = {v: tuple(map(float, X[i])) for i, v in enumerate(self.internal)}
        coords.update({v: tuple(map(float, B[i])) for i, v in enumerate(self.boundary)})
        quality = self.engine.validate_uv(coords, face_ids=self.face_ids, orientation=orientation)
        self.last_quality = self.engine.last_uv_quality = quality
        if check_orientation and not quality.locally_valid:
            raise ParameterizationError(f"UV validation failed: {len(quality.flipped_triangles)} flipped and "
                                        f"{len(quality.degenerate_triangles)} collapsed triangles. "
                                        "Revise the boundary or triangulation; harmonic maps are not always injective.")
        return coords


@dataclass
class Vertex:
    id: int
    valence: int = 4
    is_singularity: bool = False
    outgoing_halfedges: List[int] = field(default_factory=list)


@dataclass
class HalfEdge:
    id: int
    origin: int
    twin: Optional[int] = None
    next_he: Optional[int] = None
    face: Optional[int] = None


@dataclass
class Face:
    id: int
    half_edges: List[int] = field(default_factory=list)


class MotorcycleGraphTracer:
    """Preserved discrete QUAD-STRIP tracer, with a usable half-edge builder.

    This follows opposite edges through quads. It is NOT a continuous
    cross-field motorcycle algorithm or a geodesic-time event scheduler.
    Sequential collisions are deterministic and order-dependent. Face occupancy
    also detects crossings through a quad, not only previously visited edges.
    """
    def __init__(self):
        self.vertices: Dict[int, Vertex] = {}
        self.half_edges: Dict[int, HalfEdge] = {}
        self.faces: Dict[int, Face] = {}
        self.occupied_edges: Set[int] = set()
        self._occupied_faces: Set[int] = set()
        self._engine = None
        self._signature = None
        self._revision = None

    @classmethod
    def from_mesh(cls, engine: MeshHealingEngine) -> 'MotorcycleGraphTracer':
        if any(len(f) != 4 for f in engine.faces):
            raise TopologyError("Opposite-edge motorcycle tracing requires all-quad faces")
        if not engine.topology_report().is_oriented_manifold:
            raise TopologyError("Half-edge builder requires an oriented manifold; preprocess first")
        tracer = cls()
        tracer._engine = engine
        tracer._signature = engine._fingerprint()
        tracer._revision = engine._revision
        boundary = {v for e in engine.topology_report().boundary_edges for v in e}
        for v, neighbors in engine.adjacency.items():
            tracer.vertices[v] = Vertex(v, len(neighbors), v not in boundary and len(neighbors) != 4)
        directed = {}
        for fid, face in enumerate(engine.faces):
            first = len(tracer.half_edges)
            ids = list(range(first, first + 4))
            tracer.faces[fid] = Face(fid, ids)
            for i, u in enumerate(face):
                v = face[(i + 1) % 4]
                hid = ids[i]
                tracer.half_edges[hid] = HalfEdge(hid, u, None, ids[(i + 1) % 4], fid)
                tracer.vertices[u].outgoing_halfedges.append(hid)
                directed[(u, v)] = hid
        for (u, v), hid in directed.items():
            tracer.half_edges[hid].twin = directed.get((v, u))
        return tracer

    def _check_fresh(self):
        if self._engine is not None and (self._engine._revision != self._revision
                                        or self._engine._fingerprint() != self._signature):
            raise StaleSystemError("Mesh changed; rebuild the half-edge tracer")

    def get_undirected_edge_id(self, he_id: int) -> int:
        he = self.half_edges[he_id]
        return he_id if he.twin is None else min(he.id, he.twin)

    def edge_vertex_map(self) -> Dict[int, Edge]:
        self._check_fresh()
        return {self.get_undirected_edge_id(hid): _edge(he.origin, self.half_edges[he.next_he].origin)
                for hid, he in self.half_edges.items()}

    def find_straight_ahead_opposite(self, entry_he_id: int) -> int:
        he0 = self.half_edges[entry_he_id]
        loop, cur = [], entry_he_id
        for _ in range(4):
            if cur not in self.half_edges:
                raise TopologyError("Broken next_he pointer")
            loop.append(cur)
            cur = self.half_edges[cur].next_he
        if cur != entry_he_id or len(set(loop)) != 4:
            raise TopologyError("Opposite-edge traversal requires a four-half-edge loop")
        return loop[2]

    def trace_single_motorcycle(self, start_he_id: int) -> List[int]:
        self._check_fresh()
        if start_he_id not in self.half_edges:
            raise MeshError("Unknown starting half-edge")
        track, current = [], start_he_id
        while current is not None:
            he = self.half_edges[current]
            edge = self.get_undirected_edge_id(current)
            if edge in self.occupied_edges:
                break
            self.occupied_edges.add(edge)
            if not track or track[-1] != edge:
                track.append(edge)
            if he.face is not None and he.face in self._occupied_faces:
                break
            if he.face is not None:
                self._occupied_faces.add(he.face)
            exit_id = self.find_straight_ahead_opposite(current)
            exit_he = self.half_edges[exit_id]
            if exit_he.twin is None:
                edge = self.get_undirected_edge_id(exit_id)
                if edge not in self.occupied_edges:
                    track.append(edge)
                    self.occupied_edges.add(edge)
                break
            current = exit_he.twin
        return track

    def compute_graph(self, *, reset: bool = True) -> Dict[int, List[int]]:
        self._check_fresh()
        if reset:
            self.occupied_edges.clear()
            self._occupied_faces.clear()
        trajectories = {}
        for v in sorted(self.vertices):
            vertex = self.vertices[v]
            if vertex.is_singularity:
                for start_he in sorted(vertex.outgoing_halfedges):
                    trajectories[len(trajectories)] = self.trace_single_motorcycle(start_he)
        return trajectories


def solve_igm_quantization(initial_lengths: list, patches: list, *,
                           weights=None, min_length: int = 1,
                           max_length: Optional[int] = None,
                           time_limit: Optional[float] = None) -> np.ndarray:
    """Preserved L1 MILP for integer segment lengths and opposite-side sums.

    This enforces the supplied linear patch constraints. It does NOT prove
    global watertightness, UV injectivity, or that the supplied T-mesh is valid.
    Repeated IDs accumulate coefficients. Results are rounded and verified,
    never truncated with astype(int) before checking integrality.
    """
    targets = np.asarray(initial_lengths, dtype=float)
    if targets.ndim != 1 or not np.all(np.isfinite(targets)) or np.any(targets < 0):
        raise MeshError("initial_lengths must be a finite nonnegative vector")
    n = len(targets)
    if not n:
        if patches:
            raise MeshError("Patches reference an empty segment array")
        return np.empty(0, dtype=np.int64)
    min_length = _index(min_length, 2**53, "min_length")
    if min_length < 1:
        raise MeshError("min_length must be at least 1")
    if max_length is not None:
        max_length = _index(max_length, 2**53, "max_length")
        if max_length < min_length:
            raise MeshError("max_length is smaller than min_length")
    if np.max(targets) >= 2**52:
        raise MeshError("Length scale exceeds exact floating-point integer safety")
    w = np.ones(n) if weights is None else _finite_array(weights, (n,), "weights")
    if np.any(w <= 0):
        raise MeshError("Objective weights must be strictly positive")
    rows, cols, data = [], [], []
    row_count = 0
    for patch in patches:
        for left, right in (("horizontal_top", "horizontal_bottom"), ("vertical_left", "vertical_right")):
            for side, sign in ((left, 1), (right, -1)):
                if side not in patch or len(patch[side]) == 0:
                    raise MeshError(f"Patch requires a nonempty {side} chain")
                for segment in patch[side]:
                    rows.append(row_count)
                    cols.append(_index(segment, n, "segment"))
                    data.append(sign)
            row_count += 1
    eq = sp.coo_matrix((data, (rows, cols)), shape=(row_count, n)).tocsr()
    I = sp.eye(n, format='csr')
    deviation = sp.vstack((sp.hstack((I, -I)), sp.hstack((I, I))), format='csr')
    constraints = [LinearConstraint(deviation,
                                   np.r_[np.full(n, -np.inf), targets],
                                   np.r_[targets, np.full(n, np.inf)])]
    if row_count:
        constraints.append(LinearConstraint(sp.hstack((eq, sp.csr_matrix((row_count, n))), format='csr'),
                                            np.zeros(row_count), np.zeros(row_count)))
    options = {"mip_rel_gap": 0.0}
    if time_limit is not None:
        if not np.isfinite(time_limit) or time_limit <= 0:
            raise MeshError("time_limit must be positive and finite")
        options["time_limit"] = float(time_limit)
    res = milp(c=np.r_[np.zeros(n), w], integrality=np.r_[np.ones(n), np.zeros(n)],
               bounds=Bounds(np.r_[np.full(n, min_length), np.zeros(n)],
                             np.r_[np.full(n, np.inf if max_length is None else max_length), np.full(n, np.inf)]),
               constraints=constraints, options=options)
    if not res.success or res.x is None:
        raise RuntimeError(f"IGM MILP did not certify an optimum: {res.message}")
    rounded = np.rint(res.x[:n])
    if (not np.all(np.isfinite(rounded)) or np.max(np.abs(rounded)) >= 2**52
            or not np.allclose(rounded, res.x[:n], rtol=0, atol=1e-6)):
        raise RuntimeError("IGM backend returned invalid/nonintegral lengths")
    lengths = rounded.astype(np.int64)
    if (np.any(lengths < min_length) or (max_length is not None and np.any(lengths > max_length))
            or np.any(np.abs(eq @ lengths) > 1e-9)):
        raise RuntimeError("Rounded IGM result violates domain or patch equalities")
    return lengths


@dataclass
class PruneReport:
    trajectories: Dict[int, List[int]]
    removed_tracks: List[int]
    edge_vertices: Dict[int, Edge]
    old_to_new_edges: Dict[int, Optional[int]]
    edge_lengths: Dict[int, float]
    preprocessing: Optional[PreprocessReport]


def prune_motorcycle_graph(trajectories: dict, length_threshold: float,
                           initial_lengths: dict, *,
                           mesh_engine: Optional[MeshHealingEngine] = None,
                           edge_vertices: Optional[Mapping[int, Edge]] = None,
                           stitch_tolerance: float = 1e-5,
                           protected_tracks: Iterable[int] = (),
                           return_report: bool = False):
    """Extend the existing threshold pruner with actual mesh preprocessing.

    With mesh_engine: transactionally clean/split/stitch BEFORE filtering tracks,
    then remap caller-supplied edge endpoint IDs and recompute their 3D lengths.
    Existing half-edge IDs alone are insufficient to remap: provide edge_vertices.
    Bowtie splitting makes some old edge IDs ambiguous and requires retracing;
    this is detected before committing changes to the caller's mesh.

    Removing a trajectory removes a graph feature, not the underlying fine mesh.
    No macro-patch merge is invented without a patch-to-track incidence model.
    protected_tracks lets callers retain boundaries/seams needed by that model.
    """
    if not np.isfinite(length_threshold) or length_threshold < 0:
        raise MeshError("length_threshold must be finite and nonnegative")
    tracks = {k: list(v) for k, v in trajectories.items()}
    lengths = dict(initial_lengths)
    endpoints = {} if edge_vertices is None else dict(edge_vertices)
    mapping = {e: e for path in tracks.values() for e in path}
    prep, work = None, None
    if mesh_engine is not None:
        if any(tracks.values()) and edge_vertices is None:
            raise MeshError("Pass edge_vertices=tracer.edge_vertex_map() or preprocess before tracing")
        work = MeshHealingEngine(mesh_engine.v3d, mesh_engine.faces)
        prep = work.preprocess(stitch_tolerance)
        new_edges, by_pair, mapping, lengths = {}, {}, {}, {}
        for eid in sorted(endpoints):
            u, v = endpoints[eid]
            u = _index(u, mesh_engine.num_vertices, "edge endpoint")
            v = _index(v, mesh_engine.num_vertices, "edge endpoint")
            us, vs = prep.old_to_new_vertices[u], prep.old_to_new_vertices[v]
            if len(us) != 1 or len(vs) != 1:
                raise TopologyError("An edge endpoint was removed/split; preprocess first, then retrace")
            a, b = us[0], vs[0]
            if a == b:
                mapping[eid] = None
                continue
            pair = _edge(a, b)
            if pair not in work.edge_faces:
                raise TopologyError(f"Remapped track edge {eid} is not a mesh edge; retrace")
            new_id = by_pair.setdefault(pair, eid)
            mapping[eid] = new_id
            new_edges[new_id] = pair
            lengths[new_id] = float(np.linalg.norm(work.v3d[a] - work.v3d[b]))
        endpoints = new_edges
        remapped = {}
        for tid, path in tracks.items():
            out = []
            for e in path:
                if e not in mapping:
                    raise MeshError(f"Track {tid} lacks endpoint data for edge {e}")
                e = mapping[e]
                if e is not None and (not out or out[-1] != e):
                    out.append(e)
            remapped[tid] = out
        tracks = remapped
    protected = set(protected_tracks)
    if not protected <= set(tracks):
        raise MeshError("protected_tracks contains an unknown track")
    kept, removed = {}, []
    for tid, path in tracks.items():
        for eid in path:
            if eid not in lengths or not np.isfinite(lengths[eid]) or lengths[eid] < 0:
                raise MeshError(f"Missing/invalid length for edge {eid}; missing values are not zero")
        total = math.fsum(float(lengths[e]) for e in path)
        if path and (total >= length_threshold or tid in protected):
            kept[tid] = path
        elif tid in protected:
            raise TopologyError(f"Protected track {tid} collapsed; refusing to remove it")
        else:
            removed.append(tid)
            LOG.info("Topological pruning: removed track %s (length %.6g)", tid, total)
    if work is not None:
        mesh_engine.v3d, mesh_engine.faces = work.v3d, work.faces
        mesh_engine._revision += 1
        mesh_engine._build_topology()
        mesh_engine.last_preprocess_report = prep
        mesh_engine.last_stitch_report = prep.stitch
    report = PruneReport(kept, removed, endpoints, mapping, lengths, prep)
    return report if return_report else kept


def parameterize_macro_patch(internal_vertices: list, boundary_mapping: dict,
                              adjacency: dict, *, mesh_engine=None,
                              vertices=None, faces=None, face_ids=None,
                              weighting: str = "auto", face_confidence=None,
                              check_orientation: bool = True) -> dict:
    """Preserve the old three-argument API, prefer cotangents with geometry.

    New calls should pass mesh_engine=..., or vertices=... and faces=....
    Graph-only legacy calls cannot infer angles; they explicitly warn and keep
    the original uniform/Tutte behavior. weighting='cotangent' requires geometry.
    """
    if weighting not in ("auto", "cotangent", "uniform"):
        raise MeshError("weighting must be auto, cotangent, or uniform")
    if mesh_engine is not None and (vertices is not None or faces is not None):
        raise MeshError("Supply either mesh_engine or vertices/faces, not both")
    if (vertices is None) != (faces is None):
        raise MeshError("vertices and faces must be supplied together")
    if mesh_engine is None and vertices is not None:
        mesh_engine = MeshHealingEngine(vertices, faces)
    if mesh_engine is not None and weighting != "uniform":
        return mesh_engine.compute_harmonic_map(internal_vertices, boundary_mapping,
                                                face_ids=face_ids, face_confidence=face_confidence,
                                                check_orientation=check_orientation)
    if weighting == "cotangent":
        raise MeshError("Cotangent angles require 3D vertices and faces, not adjacency alone")
    if weighting == "auto":
        warnings.warn("Geometry was not provided: retaining legacy uniform/Tutte weights. "
                      "Pass mesh_engine=... for cotangent harmonic mapping.", FutureWarning, stacklevel=2)
    if face_confidence is not None:
        raise MeshError("Face confidence requires the cotangent geometry path")
    internal = list(internal_vertices)
    boundary = list(boundary_mapping)
    ids = internal + boundary
    if len(ids) != len(set(ids)):
        raise MeshError("Internal/boundary IDs overlap or contain duplicates")
    lookup = {v: i for i, v in enumerate(ids)}
    n, m = len(internal), len(ids)
    rows, cols = [], []
    for u in ids:
        for v in set(adjacency.get(u, ())):
            if v in lookup and v != u:
                if u not in adjacency.get(v, ()):
                    raise MeshError("Uniform adjacency must be symmetric within the selected patch")
                rows.append(lookup[u])
                cols.append(lookup[v])
    W = sp.coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(m, m)).tocsr()
    L = sp.diags(np.asarray(W.sum(axis=1)).ravel()) - W
    L = L.tocsr()
    _, labels = connected_components(W, directed=False)
    for c in np.unique(labels[:n]):
        if not np.any(labels[n:] == c):
            raise ParameterizationError("Uniform patch has an unanchored component")
    B = np.array([_finite_array(boundary_mapping[v], (2,), "boundary UV") for v in boundary]).reshape(-1, 2)
    X = spla.splu(L[:n, :n].tocsc()).solve(-L[:n, n:] @ B) if n else np.empty((0, 2))
    result = {v: tuple(map(float, X[i])) for i, v in enumerate(internal)}
    result.update({v: tuple(map(float, B[i])) for i, v in enumerate(boundary)})
    if mesh_engine is not None and check_orientation:
        quality = mesh_engine.validate_uv(result, face_ids=face_ids)
        if not quality.locally_valid:
            raise ParameterizationError("Uniform map has flipped/collapsed triangles")
    return result


class CrossFieldOptimizer:
    """Extend the supplied face-based 4-RoSy smoother.

    Normalizes normals, transports local frames, anchors every connected
    component, and returns the complex field. This remains a linear relaxed
    field solve, not a full singularity-placement or seamless-IGM optimizer.
    Near-zero values are retained as undefined directions, not normalized to NaN.
    """
    def __init__(self, face_centroids: np.ndarray, face_normals: np.ndarray, adjacency: dict):
        centroids = np.asarray(face_centroids, dtype=float)
        if centroids.ndim != 2 or centroids.shape[1] != 3 or not np.all(np.isfinite(centroids)):
            raise MeshError("face_centroids must be a finite (N,3) array")
        self.centroids = centroids.copy()
        self.num_faces = len(centroids)
        normals = _finite_array(face_normals, centroids.shape, "face_normals").copy()
        norm = np.linalg.norm(normals, axis=1)
        if np.any(norm <= np.finfo(float).tiny):
            raise MeshError("Face normals must be nonzero")
        self.normals = normals / norm[:, None]
        self.adjacency = {i: set() for i in range(self.num_faces)}
        for i, ns in adjacency.items():
            i = _index(i, self.num_faces, "face")
            for j in ns:
                j = _index(j, self.num_faces, "neighbor face")
                if i != j:
                    self.adjacency[i].add(j)
                    self.adjacency[j].add(i)
        self.last_undefined_faces: List[int] = []
        self.last_gauge_faces: List[int] = []

    def compute_dihedral_angles(self, face_i: int, face_j: int) -> float:
        i, j = _index(face_i, self.num_faces), _index(face_j, self.num_faces)
        return float(np.degrees(np.arccos(np.clip(np.dot(self.normals[i], self.normals[j]), -1, 1))))

    def compute_local_basis(self, face_idx: int) -> Tuple[np.ndarray, np.ndarray]:
        i = _index(face_idx, self.num_faces)
        normal = self.normals[i]
        ref = np.eye(3)[int(np.argmin(np.abs(normal)))]
        u = np.cross(normal, ref)
        u /= np.linalg.norm(u)
        return u, np.cross(normal, u)

    def estimate_feature_tangent(self, face_idx: int, neighbors: list) -> np.ndarray:
        if not neighbors:
            return self.compute_local_basis(face_idx)[0]
        j = max(neighbors, key=lambda j: (self.compute_dihedral_angles(face_idx, j), -j))
        # Two face planes intersect along n_i x n_j, not the centroid-to-centroid direction.
        tangent = np.cross(self.normals[face_idx], self.normals[j])
        if np.linalg.norm(tangent) < 1e-10:
            tangent = self.centroids[j] - self.centroids[face_idx]
            tangent -= np.dot(tangent, self.normals[face_idx]) * self.normals[face_idx]
        if np.linalg.norm(tangent) < 1e-10:
            return self.compute_local_basis(face_idx)[0]
        return tangent / np.linalg.norm(tangent)

    def _transport(self, i: int, j: int) -> complex:
        """Map the j frame into the i frame by minimal normal-aligning rotation."""
        ui, vi = self.compute_local_basis(i)
        uj, _ = self.compute_local_basis(j)
        a, b = self.normals[j], self.normals[i]
        c = float(np.dot(a, b))
        if c < -1 + 1e-10:
            raise MeshError("Antiparallel adjacent normals have ambiguous transport; repair orientation")
        axis = np.cross(a, b)
        K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
        rotated = (np.eye(3) + K + K @ K / (1 + c)) @ uj
        angle = np.arctan2(np.dot(rotated, vi), np.dot(rotated, ui))
        return complex(np.exp(4j * angle))

    def optimize_field(self, sharp_threshold_degrees: float = 30.0, *,
                       fixed_directions: Optional[Mapping[int, Sequence[float]]] = None,
                       face_confidence: Optional[Mapping[int, float]] = None,
                       normalize: bool = True) -> np.ndarray:
        if not np.isfinite(sharp_threshold_degrees) or not 0 <= sharp_threshold_degrees <= 180:
            raise MeshError("Sharp threshold must be in [0,180] degrees")
        n = self.num_faces
        if not n:
            return np.empty(0, dtype=complex)
        confidence = np.ones(n)
        for i, c in (face_confidence or {}).items():
            i = _index(i, n, "confidence face")
            if not np.isfinite(c) or not 0 <= c <= 1:
                raise MeshError("Face confidence must be in [0,1]")
            confidence[i] = c
        A = sp.lil_matrix((n, n), dtype=complex)
        graph_rows, graph_cols = [], []
        for i in range(n):
            for j in sorted(self.adjacency[i]):
                if i >= j:
                    continue
                w = min(confidence[i], confidence[j])
                if w == 0:
                    continue
                transport = self._transport(i, j)
                A[i, i] += w
                A[j, j] += w
                A[i, j] -= w * transport
                A[j, i] -= w * transport.conjugate()
                graph_rows.extend((i, j))
                graph_cols.extend((j, i))
        fixed = {}

        def encode(i, vector):
            t = _finite_array(vector, (3,), "feature tangent")
            u, v = self.compute_local_basis(i)
            xy = np.array([np.dot(t, u), np.dot(t, v)])
            if np.linalg.norm(xy) <= 1e-12 * max(np.linalg.norm(t), np.finfo(float).tiny):
                raise MeshError("Fixed feature direction has no nonzero tangent component")
            return complex(np.exp(4j * np.arctan2(xy[1], xy[0])))

        for i in range(n):
            neighbors = sorted(j for j in self.adjacency[i] if min(confidence[i], confidence[j]) > 0)
            if any(self.compute_dihedral_angles(i, j) > sharp_threshold_degrees for j in neighbors):
                fixed[i] = encode(i, self.estimate_feature_tangent(i, neighbors))
        for i, tangent in (fixed_directions or {}).items():
            i = _index(i, n, "fixed face")
            fixed[i] = encode(i, tangent)
        graph = sp.coo_matrix((np.ones(len(graph_rows)), (graph_rows, graph_cols)), shape=(n, n)).tocsr()
        _, labels = connected_components(graph, directed=False)
        self.last_gauge_faces = []
        for c in np.unique(labels):
            members = np.flatnonzero(labels == c).tolist()
            if not any(i in fixed for i in members):
                fixed[members[0]] = 1 + 0j
                self.last_gauge_faces.append(members[0])
        free = [i for i in range(n) if i not in fixed]
        known = sorted(fixed)
        field_values = np.zeros(n, dtype=complex)
        field_values[known] = [fixed[i] for i in known]
        A = A.tocsr()
        if free:
            rhs = -A[free, :][:, known] @ field_values[known]
            field_values[free] = spla.splu(A[free, :][:, free].tocsc()).solve(rhs)
        if not np.all(np.isfinite(field_values)):
            raise ParameterizationError("Nonfinite cross-field solution")
        magnitude = np.abs(field_values)
        self.last_undefined_faces = np.flatnonzero(magnitude <= 1e-10).tolist()
        if normalize:
            valid = magnitude > 1e-10
            field_values[valid] /= magnitude[valid]
        return field_values


if __name__ == '__main__':
    from example_pipeline import main
    main()
