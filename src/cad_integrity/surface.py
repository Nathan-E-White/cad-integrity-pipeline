"""Owned polygonal surfaces; native geometry and Python constrained sparse solves.

Prepared surfaces are immutable snapshots. Local chart admission does not establish
absence of global overlap. SciPy allocations are outside native logical budgets.
"""
from __future__ import annotations

import numbers
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import scipy.linalg as la
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from numpy.typing import NDArray
from scipy.sparse.csgraph import connected_components

from . import _native
from .arrays import FloatArray, IntArray, integers
from .errors import InvalidGeometry, ResourceLimitExceeded
from .models import PolyhedralBRep


@dataclass(frozen=True, slots=True)
class SurfaceLimits:
    max_input_bytes: int = 256_000_000
    max_owned_bytes: int = 512_000_000
    max_work_steps: int = 50_000_000
    max_output_bytes: int = 256_000_000

    def __post_init__(self) -> None:
        for value in (self.max_input_bytes, self.max_owned_bytes,
                      self.max_work_steps, self.max_output_bytes):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 1 << 64:
                raise ValueError("Surface limits must be nonnegative uint64 integers")

    def _native_limits(self) -> _native.SurfaceLimits:
        return _native.SurfaceLimits(self.max_input_bytes, self.max_owned_bytes,
                                     self.max_work_steps, self.max_output_bytes)


@dataclass(frozen=True, slots=True)
class TriangulationPolicy:
    relative_tolerance: float = 1e-12

    def __post_init__(self) -> None:
        if not np.isfinite(self.relative_tolerance) or self.relative_tolerance < 0:
            raise ValueError("Triangulation tolerance must be finite and nonnegative")


@dataclass(frozen=True, slots=True)
class SurfaceUsage:
    input_bytes: int
    owned_bytes: int
    work_steps: int
    output_bytes: int


def _immutable(value: Any) -> Any:
    """Bytes backing prevents reopening writeability on a retained projection."""
    return np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)


class ParameterizationError(InvalidGeometry):
    """Constraints or numerical solve cannot supply the requested chart."""


@dataclass(frozen=True, slots=True)
class ChartPolicy:
    orientation: int = 1
    relative_tolerance: float = 1e-12

    def __post_init__(self) -> None:
        if isinstance(self.orientation, bool) or self.orientation not in (-1, 1):
            raise ValueError("Orientation must be +1 or -1")
        if not np.isfinite(self.relative_tolerance) or self.relative_tolerance < 0:
            raise ValueError("Chart tolerance must be finite and nonnegative")


@dataclass(frozen=True, slots=True)
class UVQuality:
    triangle_count: int
    flipped_triangles: tuple[int, ...]
    degenerate_triangles: tuple[int, ...]
    minimum_signed_double_area: float
    maximum_conformal_distortion: float

    @property
    def locally_valid(self) -> bool:
        return not (self.flipped_triangles or self.degenerate_triangles)


@dataclass(frozen=True, slots=True)
class AdmittedChart:
    surface: Surface
    _handle: _native.AdmittedChart

    @property
    def uv(self) -> FloatArray:
        return _immutable(self._handle.uv())


@dataclass(frozen=True, slots=True)
class ChartAssessment:
    quality: UVQuality
    admitted: AdmittedChart | None
    usage: SurfaceUsage


@dataclass(frozen=True, slots=True)
class SurfaceOperators:
    surface: Surface
    _handle: _native.SurfaceOperators

    @property
    def stiffness(self) -> sp.csr_matrix:
        data = self._handle.arrays()
        return sp.csr_matrix((data["values"], data["columns"], data["offsets"]),
                             shape=(data["dimension"], data["dimension"]), copy=True)

    @property
    def usage(self) -> SurfaceUsage:
        return SurfaceUsage(**self._handle.arrays()["usage"])


def _index(value: object, size: int, name: str = "index") -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Integral):
        raise InvalidGeometry(f"{name} must be an integer")
    result = int(value)
    if not 0 <= result < size:
        raise InvalidGeometry(f"{name} {result} is outside [0, {size})")
    return result


def _finite_array(value: Any, shape: tuple[int, ...], name: str) -> FloatArray:
    result = np.asarray(value, dtype=np.float64)
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise InvalidGeometry(f"{name} must have shape {shape} and finite values")
    return result


@dataclass(frozen=True, slots=True)
class Surface:
    _handle: _native.Surface
    vertices: FloatArray
    triangles: IntArray
    triangle_edges: IntArray
    source_vertices: IntArray
    selected_faces: IntArray
    triangle_faces: IntArray
    boundary_vertices: IntArray
    source_face_count: int
    length_unit: str
    usage: SurfaceUsage
    limits: SurfaceLimits


    def assemble(self, face_confidence: Mapping[int, float] | None = None,
                 *, limits: SurfaceLimits | None = None) -> SurfaceOperators:
        confidence = {} if face_confidence is None else dict(face_confidence)
        ids = np.array([_index(k, self.source_face_count, "confidence face") for k in confidence], dtype=np.int64)
        weights = np.array(list(confidence.values()), dtype=np.float64)
        try:
            handle = _native.assemble_surface(self._handle, ids, weights,
                                              (limits or self.limits)._native_limits())
        except _native.BudgetExceeded as exc:
            raise ResourceLimitExceeded(str(exc)) from exc
        except ValueError as exc:
            raise InvalidGeometry(str(exc)) from exc
        return SurfaceOperators(self, handle)

    def qualify_chart(self, coordinates: Mapping[int, Sequence[float]], *,
                      policy: ChartPolicy = ChartPolicy(),
                      limits: SurfaceLimits | None = None) -> ChartAssessment:
        for vertex in coordinates:
            if isinstance(vertex, (bool, np.bool_)) or not isinstance(vertex, numbers.Integral):
                raise InvalidGeometry("UV keys must be source vertex integers")
        if set(coordinates) != set(self.source_vertices.tolist()):
            raise InvalidGeometry("UV keys must equal the selected patch vertex set")
        uv = np.array([_finite_array(coordinates[int(v)], (2,), "UV") for v in self.source_vertices])
        try:
            result = _native.qualify_surface_chart(self._handle, uv, policy.orientation,
                                                   policy.relative_tolerance,
                                                   (limits or self.limits)._native_limits())
        except _native.BudgetExceeded as exc:
            raise ResourceLimitExceeded(str(exc)) from exc
        except ValueError as exc:
            raise InvalidGeometry(str(exc)) from exc
        quality = UVQuality(result["triangle_count"], tuple(map(int, result["flipped_triangles"])),
                            tuple(map(int, result["degenerate_triangles"])),
                            result["minimum_signed_double_area"], result["maximum_conformal_distortion"])
        admitted = None if result["admitted"] is None else AdmittedChart(self, result["admitted"])
        return ChartAssessment(quality, admitted, SurfaceUsage(**result["usage"]))

    def prepare_harmonic_system(self, internal_nodes: Sequence[int], boundary_nodes: Sequence[int], *,
                                face_confidence: Mapping[int, float] | None = None,
                                require_full_boundary: bool = True, max_update_rank: int = 32) -> HarmonicSystem:
        return HarmonicSystem(self, internal_nodes, boundary_nodes, face_confidence=face_confidence,
                              require_full_boundary=require_full_boundary, max_update_rank=max_update_rank)


def prepare_surface(
    raw: PolyhedralBRep, *, face_ids: Sequence[int] | None = None,
    policy: TriangulationPolicy = TriangulationPolicy(), limits: SurfaceLimits = SurfaceLimits(),
) -> Surface:
    """Admit an explicitly selected oriented patch and retain its triangulation."""
    ids = np.arange(raw.face_count, dtype=np.int64) if face_ids is None else integers(face_ids, name="face_ids")
    try:
        handle = _native.prepare_surface(raw.vertices, raw.edges, raw.face_offsets,
                                         raw.face_coedges, raw.length_unit, ids,
                                         policy.relative_tolerance, limits._native_limits())
    except _native.BudgetExceeded as exc:
        raise ResourceLimitExceeded(str(exc)) from exc
    except ValueError as exc:
        raise InvalidGeometry(str(exc)) from exc
    data = handle.arrays()
    return Surface(handle, _immutable(data["vertices"]), _immutable(data["triangles"]),
                   _immutable(data["triangle_edges"]), _immutable(data["source_vertices"]),
                   _immutable(data["selected_faces"]), _immutable(data["triangle_faces"]),
                   _immutable(data["boundary_vertices"]), data["source_face_count"], raw.length_unit,
                   SurfaceUsage(**data["usage"]), limits)


UVMap = dict[int, tuple[float, float]]


@dataclass(frozen=True)
class SoftConstraint:
    target: tuple[float, float]
    weight: float = 1.0

    def __post_init__(self) -> None:
        target = _finite_array(self.target, (2,), "soft target")
        if not np.isfinite(self.weight) or self.weight < 0:
            raise InvalidGeometry("Soft-constraint weight must be finite and nonnegative")
        object.__setattr__(self, "target", tuple(map(float, target)))
        object.__setattr__(self, "weight", float(self.weight))


@dataclass(frozen=True)
class _WoodburyUpdate:
    U: NDArray[np.float64]
    Z: NDArray[np.float64]
    factor: tuple[NDArray[np.float64], bool]


@dataclass(frozen=True)
class _RefactorUpdate:
    lu: spla.SuperLU


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
    def __init__(self, surface: Surface, internal_nodes: Sequence[int],
                 boundary_nodes: Sequence[int], *, face_confidence: Mapping[int, float] | None = None,
                 require_full_boundary: bool = True, max_update_rank: int = 32) -> None:
        self.surface = surface
        self._source_size = int(surface.source_vertices.max()) + 1
        self.internal = tuple(_index(v, self._source_size) for v in internal_nodes)
        self.boundary = tuple(_index(v, self._source_size) for v in boundary_nodes)
        ordered = self.internal + self.boundary
        if len(ordered) != len(set(ordered)) or set(ordered) != set(surface.source_vertices.tolist()):
            raise InvalidGeometry("Internal and boundary IDs must be disjoint and cover the patch")
        if require_full_boundary and not set(surface.boundary_vertices.tolist()) <= set(self.boundary):
            raise ParameterizationError("Boundary vertices lack Dirichlet values")
        self.require_full_boundary = require_full_boundary
        self.max_update_rank = _index(max_update_rank, 1_000_001, "max_update_rank")
        self.face_confidence = {} if face_confidence is None else dict(face_confidence)
        self.operators = surface.assemble(self.face_confidence)
        positions = {int(v): i for i, v in enumerate(surface.source_vertices)}
        order = [positions[v] for v in ordered]
        self.L = self.operators.stiffness[order, :][:, order].tocsr()
        n = len(self.internal)
        self.A = self.L[:n, :n].tocsc()
        self.L_IB = self.L[:n, n:].tocsr()
        self._internal_index = {v: i for i, v in enumerate(self.internal)}
        graph = abs(self.L).tocsr()
        graph.setdiag(0)
        graph.eliminate_zeros()
        _, labels = connected_components(graph, directed=False)
        for component in np.unique(labels[:n]):
            if not np.any(labels[n:] == component):
                raise ParameterizationError("Unanchored component; zero confidence may disconnect it")
        self.last_chart_assessment: ChartAssessment | None = None
        self.factorization_count = 0
        self.base_factorization_count = 0
        self.low_rank_update_count = 0
        self.last_update_method = "none"
        self.last_relative_residual = float('nan')
        self.last_quality: UVQuality | None = None
        self._update_key: tuple[tuple[int, float], ...] | None = None
        self._update_cache: _WoodburyUpdate | _RefactorUpdate | None = None
        self._lu: spla.SuperLU | None = None
        if n:
            try:
                self._lu = spla.splu(self.A)
            except RuntimeError as exc:
                raise ParameterizationError("Singular Dirichlet matrix; inspect components and degenerate faces") from exc
            self.factorization_count = self.base_factorization_count = 1
        else:
            self._lu = None

    def with_face_confidence(self, face_confidence: Mapping[int, float]) -> HarmonicSystem:
        """Reuse geometry, rebuild operators and factorization for changed coefficients."""
        return HarmonicSystem(self.surface, self.internal, self.boundary,
                              face_confidence=face_confidence,
                              require_full_boundary=self.require_full_boundary,
                              max_update_rank=self.max_update_rank)

    def solve(self, boundary_constraints: Mapping[int, Sequence[float]], *,
              soft_constraints: Mapping[int, SoftConstraint] | None = None,
              check_orientation: bool = True, orientation: int = 1) -> UVMap:
        self.last_chart_assessment = None
        self.last_quality = None
        for v in boundary_constraints:
            _index(v, self._source_size, "boundary vertex")
        if set(boundary_constraints) != set(self.boundary):
            raise InvalidGeometry("A reused system requires the same boundary ID set (values may change)")
        B = np.array([_finite_array(boundary_constraints[v], (2,), "boundary UV")
                      for v in self.boundary], dtype=float).reshape(-1, 2)
        anchors = {} if soft_constraints is None else dict(soft_constraints)
        for v, anchor in anchors.items():
            _index(v, self._source_size, "soft-anchor vertex")
            if v not in self._internal_index:
                raise InvalidGeometry(f"Soft anchor {v} must be an internal vertex, not a Dirichlet vertex")
            if not isinstance(anchor, SoftConstraint):
                raise InvalidGeometry("Use SoftConstraint(target=(u,v), weight=...) for each soft anchor")
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
        base_lu = self._lu
        X: FloatArray
        if not n:
            X = np.empty((0, 2))
            self.last_update_method = "boundary-only"
        elif base_lu is None:
            raise ParameterizationError("Internal vertices require a Dirichlet factorization")
        elif not ids:
            X = base_lu.solve(rhs)
            self.last_update_method = "base-factorization"
        else:
            key = tuple((v, anchors[v].weight) for v in ids)
            if self._update_key != key:
                cache: _WoodburyUpdate | _RefactorUpdate | None = None
                if len(ids) <= self.max_update_rank:
                    U = np.zeros((n, len(ids)))
                    U[rows, np.arange(len(ids))] = np.sqrt(weights)
                    Z = base_lu.solve(U)
                    small = np.eye(len(ids)) + U.T @ Z
                    if np.all(np.isfinite(small)) and np.linalg.cond(small) < 1e12:
                        try:
                            factor = la.cho_factor(0.5 * (small + small.T), lower=True)
                            cache = _WoodburyUpdate(U, Z, (factor[0], bool(factor[1])))
                            self.low_rank_update_count += 1
                        except la.LinAlgError:
                            cache = None
                if cache is None:
                    try:
                        lu = spla.splu(effective)
                    except RuntimeError as exc:
                        raise ParameterizationError("Soft-update factorization failed") from exc
                    cache = _RefactorUpdate(lu)
                    self.factorization_count += 1
                self._update_key, self._update_cache = key, cache
            cache = self._update_cache
            if cache is None:
                raise ParameterizationError("Soft-update cache is unavailable")
            if isinstance(cache, _WoodburyUpdate):
                self.last_update_method = "woodbury"
                base = base_lu.solve(rhs)
                with np.errstate(over="ignore", invalid="ignore"):
                    correction_rhs = cache.U.T @ base
                    if np.all(np.isfinite(correction_rhs)):
                        X = base - cache.Z @ la.cho_solve(cache.factor, correction_rhs)
                    else:
                        X = np.full((n, 2), np.nan)  # Force the qualified refactor fallback.
            else:
                self.last_update_method = "refactor"
                X = cache.lu.solve(rhs)
        # Check backward error; do not silently return a poor Woodbury update.
        def residual(x: NDArray[np.float64]) -> float:
            if not n:
                return 0.0
            if not np.all(np.isfinite(x)):
                return float("inf")
            norm_a = float(np.max(np.asarray(abs(effective).sum(axis=1))))
            denom = norm_a * np.linalg.norm(x, ord=np.inf) + np.linalg.norm(rhs, ord=np.inf)
            if not np.isfinite(norm_a) or not np.isfinite(denom):
                return float("inf")
            return float(np.linalg.norm(effective @ x - rhs, ord=np.inf) / max(denom, np.finfo(float).tiny))
        error = residual(X)
        if (not np.all(np.isfinite(X)) or (not np.isfinite(error) or error > 1e-10)) and n and self.last_update_method == "woodbury":
            lu = spla.splu(effective)
            self._update_cache = _RefactorUpdate(lu)
            self.factorization_count += 1
            X = lu.solve(rhs)
            self.last_update_method = "refactor-after-residual-check"
            error = residual(X)
        if not np.all(np.isfinite(X)) or (not np.isfinite(error) or error > 1e-10):
            raise ParameterizationError(f"Unacceptable linear-system residual: {error:g}")
        self.last_relative_residual = error
        coords = {v: (float(X[i, 0]), float(X[i, 1])) for i, v in enumerate(self.internal)}
        coords.update({v: (float(B[i, 0]), float(B[i, 1])) for i, v in enumerate(self.boundary)})
        assessment = self.surface.qualify_chart(coords, policy=ChartPolicy(orientation=orientation))
        self.last_chart_assessment = assessment
        quality = assessment.quality
        self.last_quality = quality
        if check_orientation and not quality.locally_valid:
            raise ParameterizationError(f"UV validation failed: {len(quality.flipped_triangles)} flipped and "
                                        f"{len(quality.degenerate_triangles)} collapsed triangles. "
                                        "Revise the boundary or triangulation; harmonic maps are not always injective.")
        return coords

