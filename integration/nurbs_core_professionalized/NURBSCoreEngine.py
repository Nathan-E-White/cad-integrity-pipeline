#!/usr/bin/env python3
"""NURBS differential geometry, primitive segmentation, and bounded STEP export.

Author: Nathan White
License: MIT

Existing class names and tuple/dictionary entry points are preserved. New result
objects expose validity and unassigned samples. STEP export uses optional OCP;
this module never fabricates unbounded ADVANCED_FACE records or claims to have
reconstructed a watertight solid from surface samples.
"""

from __future__ import annotations

import io
import json
import logging
import os
import tempfile
import threading
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import least_squares
from scipy.spatial import ConvexHull, QhullError

__all__ = [
    "NURBSCoreEngine", "SurfaceGeometry", "RANSACPrimitiveClassifier",
    "SegmentationResult", "CADGeometryCardEngine", "STEPGeometryExportEngine",
    "GeometryValidationError", "SurfaceEvaluationError", "STEPExportError",
    "OptionalDependencyError", "write_text_atomic",
]

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())
FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
BoolArray = NDArray[np.bool_]
Primitive = dict[str, Any]
CylinderGeometry = tuple[FloatArray, FloatArray, float]
_UNIT_TO_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4}
_STEP_LOCK = threading.RLock()


class GeometryValidationError(ValueError):
    """An input violates a geometry, shape, units, or parameter contract."""


class SurfaceEvaluationError(ArithmeticError):
    """A rational denominator or requested regular surface is undefined."""


class STEPExportError(RuntimeError):
    """A bounded face could not be constructed, validated, or exchanged."""


class OptionalDependencyError(ImportError):
    """An explicitly requested optional backend is not installed."""


def _integer(value: int, name: str, minimum: int = 0) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise GeometryValidationError(f"{name} must be an integer")
    if value < minimum:
        raise GeometryValidationError(f"{name} must be >= {minimum}")
    return int(value)


def _positive(value: float, name: str) -> float:
    if not np.isfinite(value) or value <= 0:
        raise GeometryValidationError(f"{name} must be finite and positive")
    return float(value)


def _array(value: ArrayLike, name: str, *, finite: bool = True) -> FloatArray:
    if np.iscomplexobj(value):
        raise GeometryValidationError(f"{name} must be real-valued")
    try:
        result = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise GeometryValidationError(f"{name} must be numeric") from exc
    if finite and not np.isfinite(result).all():
        raise GeometryValidationError(f"{name} must contain only finite values")
    return result


def _vectors(value: ArrayLike, name: str) -> FloatArray:
    result = _array(value, name)
    if result.ndim != 2 or result.shape[1] != 3:
        raise GeometryValidationError(f"{name} must have shape (N, 3); got {result.shape}")
    return result


def _vector(value: ArrayLike, name: str) -> FloatArray:
    result = _array(value, name)
    if result.shape != (3,):
        raise GeometryValidationError(f"{name} must have shape (3,)")
    return result


def _unit(value: ArrayLike, name: str) -> FloatArray:
    vector = _vector(value, name)
    length = np.linalg.norm(vector)
    if not np.isfinite(length) or length == 0:
        raise GeometryValidationError(f"{name} must have a finite, nonzero norm")
    return vector / length


def _canonical(vector: FloatArray) -> FloatArray:
    return -vector if vector[np.argmax(np.abs(vector))] < 0 else vector


def _frame(axis: FloatArray) -> tuple[FloatArray, FloatArray]:
    seed = np.eye(3)[np.argmin(np.abs(axis))]
    first = seed - np.dot(seed, axis) * axis
    first /= np.linalg.norm(first)
    return first, np.cross(axis, first)


def _divide(numerator: FloatArray, denominator: FloatArray) -> FloatArray:
    """Zero-support B-spline terms at repeated knots contribute zero."""
    return np.divide(
        numerator, denominator, out=np.zeros_like(numerator), where=denominator != 0,
    )


def write_text_atomic(
    file_path: str | os.PathLike[str], text: str, *, overwrite: bool = False,
) -> Path:
    """Publish UTF-8/LF text without exposing a partially written destination.

    A same-directory temporary file is fsynced before publication. By default a
    hard-link publication is atomic and refuses an existing destination (including
    a concurrent creator). ``overwrite=True`` uses ``os.replace``. These are
    per-file guarantees, not a multi-output transaction or power-loss guarantee.
    """
    path = Path(file_path)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary_path, path)
        else:
            os.link(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return path


@dataclass(frozen=True, slots=True)
class SurfaceGeometry:
    """Tensor-grid result. Arrays are caller-owned and remain writable.

    Normal orientation is ``S_u cross S_v``. Principal_Max/Min are algebraically
    ordered, NOT sorted by magnitude. Invalid normals are zero and invalid
    curvatures are NaN. ``valid_mask`` denotes a regular parameterization, not
    smoothness across repeated knots.
    """

    points: FloatArray
    normals: FloatArray
    principal_max: FloatArray
    principal_min: FloatArray
    mean: FloatArray
    gaussian: FloatArray
    valid_mask: BoolArray

    @property
    def curvatures(self) -> dict[str, NDArray]:
        return {
            "Principal_Max": self.principal_max, "Principal_Min": self.principal_min,
            "Mean": self.mean, "Gaussian": self.gaussian, "Valid": self.valid_mask,
        }

    def as_tuple(self) -> tuple[FloatArray, FloatArray, dict[str, NDArray]]:
        return self.points, self.normals, self.curvatures


class NURBSCoreEngine:
    """Local-support vectorized B-spline derivatives and rational surface geometry.

    Four-component control points use HOMOGENEOUS ``(x*w, y*w, z*w, w)`` storage,
    matching the original evaluator. Three-component nets use unit weights.
    Use ``to_homogeneous`` to convert Cartesian points plus positive weights.
    Parameter arrays are independent 1-D vectors: evaluation returns their
    Cartesian product, not pairwise samples. No extrapolation is performed.
    """

    @staticmethod
    def _validate_knots(p: int, knot_vector: ArrayLike) -> tuple[int, FloatArray]:
        p = _integer(p, "degree")
        knots = _array(knot_vector, "knot_vector")
        if knots.ndim != 1:
            raise GeometryValidationError("knot_vector must be one-dimensional")
        n = len(knots) - p - 2
        if n < p or np.any(np.diff(knots) < 0):
            raise GeometryValidationError("knot vector is too short or is not nondecreasing")
        if knots[p] >= knots[n + 1]:
            raise GeometryValidationError("active knot domain must have positive width")
        _, counts = np.unique(knots, return_counts=True)
        if np.any(counts > p + 1):
            raise GeometryValidationError("knot multiplicity exceeds degree + 1")
        return n, knots

    @staticmethod
    def find_span_vectorized(
        n: int, p: int, u: ArrayLike, knot_vector: ArrayLike,
    ) -> IntArray:
        actual_n, knots = NURBSCoreEngine._validate_knots(p, knot_vector)
        if _integer(n, "n") != actual_n:
            raise GeometryValidationError("n must equal the final control-point index")
        parameters = _array(u, "u")
        if parameters.ndim != 1:
            raise GeometryValidationError("u must be a one-dimensional parameter vector")
        if np.any(parameters < knots[p]) or np.any(parameters > knots[n + 1]):
            raise GeometryValidationError(f"parameters must lie in [{knots[p]}, {knots[n + 1]}]")
        # The exact upper endpoint belongs to the last active span. No epsilon
        # is subtracted: subtraction fails on large or tiny knot scales.
        return np.clip(np.searchsorted(knots, parameters, side="right") - 1, p, n).astype(np.int64)

    @staticmethod
    def basis_derivatives_vectorized(
        p: int, u: ArrayLike, knot_vector: ArrayLike, max_deriv: int = 2,
    ) -> tuple[IntArray, FloatArray]:
        """Return spans and local derivatives ``(order+1, samples, degree+1)``.

        Implements the local triangular derivative recurrence. Orders above the
        degree are exactly zero. At an interior knot, the right-hand polynomial
        piece is selected; at the upper endpoint, the left-hand piece is used.
        Classical two-sided derivatives need not exist at repeated knots.
        """
        max_deriv = _integer(max_deriv, "max_deriv")
        n, knots = NURBSCoreEngine._validate_knots(p, knot_vector)
        parameters = _array(u, "u")
        spans = NURBSCoreEngine.find_span_vectorized(n, p, parameters, knots)
        count = len(parameters)
        order = min(max_deriv, p)
        ders = np.zeros((max_deriv + 1, count, p + 1))
        ndu = np.zeros((count, p + 1, p + 1))
        ndu[:, 0, 0] = 1.0
        left = np.zeros((count, p + 1))
        right = np.zeros_like(left)
        for j in range(1, p + 1):
            left[:, j] = parameters - knots[spans - j + 1]
            right[:, j] = knots[spans + j] - parameters
            saved = np.zeros(count)
            for r in range(j):
                ndu[:, j, r] = right[:, r + 1] + left[:, j - r]
                temp = _divide(ndu[:, r, j - 1], ndu[:, j, r])
                ndu[:, r, j] = saved + right[:, r + 1] * temp
                saved = left[:, j - r] * temp
            ndu[:, j, j] = saved
        ders[0] = ndu[:, :, p]
        for r in range(p + 1):
            a = np.zeros((count, 2, p + 1))
            s1, s2 = 0, 1
            a[:, 0, 0] = 1.0
            for k in range(1, order + 1):
                a[:, s2, :] = 0.0
                derivative = np.zeros(count)
                rk, pk = r - k, p - k
                if r >= k:
                    a[:, s2, 0] = _divide(a[:, s1, 0], ndu[:, pk + 1, rk])
                    derivative = a[:, s2, 0] * ndu[:, rk, pk]
                j1 = 1 if rk >= -1 else -rk
                j2 = k - 1 if r - 1 <= pk else p - r
                for j in range(j1, j2 + 1):
                    a[:, s2, j] = _divide(
                        a[:, s1, j] - a[:, s1, j - 1], ndu[:, pk + 1, rk + j],
                    )
                    derivative += a[:, s2, j] * ndu[:, rk + j, pk]
                if r <= pk:
                    a[:, s2, k] = _divide(-a[:, s1, k - 1], ndu[:, pk + 1, r])
                    derivative += a[:, s2, k] * ndu[:, r, pk]
                ders[k, :, r] = derivative
                s1, s2 = s2, s1
        factor = float(p)
        for k in range(1, order + 1):
            ders[k] *= factor
            factor *= p - k
        return spans, ders

    @staticmethod
    def to_homogeneous(control_points: ArrayLike, weights: ArrayLike) -> FloatArray:
        points = _array(control_points, "control_points")
        weight = _array(weights, "weights")
        if points.ndim != 3 or points.shape[-1] != 3 or weight.shape != points.shape[:2]:
            raise GeometryValidationError("expected control_points (Nu,Nv,3) and weights (Nu,Nv)")
        if np.any(weight <= 0):
            raise GeometryValidationError("weights must be strictly positive")
        return np.concatenate((points * weight[..., None], weight[..., None]), axis=-1)

    @staticmethod
    def evaluate_surface_geometry(
        degree_u: int, degree_v: int, knots_u: ArrayLike, knots_v: ArrayLike,
        control_points: ArrayLike, u_vec: ArrayLike, v_vec: ArrayLike,
        *, batch_size: int = 64, singular_policy: Literal["mask", "raise"] = "mask",
        regularity_tolerance: float = 1e-10,
    ) -> tuple[FloatArray, FloatArray, dict[str, NDArray]]:
        """Compatibility tuple interface; see ``evaluate_surface`` for diagnostics."""
        return NURBSCoreEngine.evaluate_surface(
            degree_u, degree_v, knots_u, knots_v, control_points, u_vec, v_vec,
            batch_size=batch_size, singular_policy=singular_policy,
            regularity_tolerance=regularity_tolerance,
        ).as_tuple()

    @staticmethod
    def evaluate_surface(
        degree_u: int, degree_v: int, knots_u: ArrayLike, knots_v: ArrayLike,
        control_points: ArrayLike, u_vec: ArrayLike, v_vec: ArrayLike,
        *, batch_size: int = 64, singular_policy: Literal["mask", "raise"] = "mask",
        regularity_tolerance: float = 1e-10,
    ) -> SurfaceGeometry:
        """Evaluate in bounded tiles while retaining the full requested output.

        ``batch_size`` limits each parameter tile's side, not total output
        storage. ``regularity_tolerance`` bounds the sine of the tangent angle
        and is dimensionless; small models are not invalidated by a fixed area
        epsilon. Only positive rational weights are supported.
        """
        batch_size = _integer(batch_size, "batch_size", 1)
        if singular_policy not in ("mask", "raise"):
            raise GeometryValidationError("singular_policy must be 'mask' or 'raise'")
        if not 0 < regularity_tolerance < 1:
            raise GeometryValidationError("regularity_tolerance must lie in (0, 1)")
        nu, ku = NURBSCoreEngine._validate_knots(degree_u, knots_u)
        nv, kv = NURBSCoreEngine._validate_knots(degree_v, knots_v)
        cp = _array(control_points, "control_points")
        if cp.shape not in ((nu + 1, nv + 1, 3), (nu + 1, nv + 1, 4)):
            raise GeometryValidationError("control net shape disagrees with knots and degrees")
        if cp.shape[-1] == 3:
            cp = NURBSCoreEngine.to_homogeneous(cp, np.ones(cp.shape[:2]))
        if np.any(cp[..., 3] <= 0):
            raise GeometryValidationError("homogeneous control weights must be strictly positive")
        # Uniform rescaling does not change the rational surface.
        cp = cp / np.max(cp[..., 3])
        # Translate the weighted net before differentiation to avoid subtracting
        # large world coordinates in the rational quotient rule.
        world_origin = cp[0, 0, :3] / cp[0, 0, 3]
        cp[..., :3] -= cp[..., 3, None] * world_origin
        su, du = NURBSCoreEngine.basis_derivatives_vectorized(degree_u, u_vec, ku)
        sv, dv = NURBSCoreEngine.basis_derivatives_vectorized(degree_v, v_vec, kv)
        shape = (len(su), len(sv))
        points = np.empty((*shape, 3))
        normals = np.zeros_like(points)
        maximum, minimum, mean, gaussian = (np.full(shape, np.nan) for _ in range(4))
        valid = np.zeros(shape, dtype=bool)
        iu = su[:, None] - degree_u + np.arange(degree_u + 1)
        iv = sv[:, None] - degree_v + np.arange(degree_v + 1)
        for first_u in range(0, len(su), batch_size):
            us = slice(first_u, first_u + batch_size)
            for first_v in range(0, len(sv), batch_size):
                vs = slice(first_v, first_v + batch_size)
                window = cp[iu[us, :, None, None], iv[None, None, vs, :]]
                # Local-support contraction from the original evaluator, now
                # tiled so the 5-D control-point gather is not whole-grid sized.
                A = np.einsum("kui,lvh,uivhd->kluvd", du[:, us], dv[:, vs], window, optimize=True)
                weight = A[0, 0, ..., 3, None]
                if np.any(weight <= np.finfo(float).tiny) or not np.isfinite(A).all():
                    raise SurfaceEvaluationError(
                        "non-finite homogeneous derivatives or tiny weight"
                    )
                wu, wv = A[1, 0, ..., 3, None], A[0, 1, ..., 3, None]
                pt = A[0, 0, ..., :3] / weight
                U = (A[1, 0, ..., :3] - wu * pt) / weight
                V = (A[0, 1, ..., :3] - wv * pt) / weight
                UU = (A[2, 0, ..., :3] - 2 * wu * U - A[2, 0, ..., 3, None] * pt) / weight
                VV = (A[0, 2, ..., :3] - 2 * wv * V - A[0, 2, ..., 3, None] * pt) / weight
                UV = (A[1, 1, ..., :3] - wu * V - wv * U - A[1, 1, ..., 3, None] * pt) / weight
                if not all(np.isfinite(a).all() for a in (pt, U, V, UU, VV, UV)):
                    raise SurfaceEvaluationError("Cartesian derivative overflow; rescale the model")
                lu, lv = np.linalg.norm(U, axis=-1), np.linalg.norm(V, axis=-1)
                safe_u, safe_v = np.where(lu > 0, lu, 1), np.where(lv > 0, lv, 1)
                tu, tv = U / safe_u[..., None], V / safe_v[..., None]
                cross = np.cross(tu, tv)
                sine = np.linalg.norm(cross, axis=-1)
                good = (lu > 0) & (lv > 0) & (sine > regularity_tolerance)
                normal = cross / np.where(good, sine, 1)[..., None]
                normal[~good] = 0
                cosine = np.einsum("...i,...i->...", tu, tv)
                b11 = np.einsum("...i,...i->...", UU, normal) / safe_u / safe_u
                b12 = np.einsum("...i,...i->...", UV, normal) / safe_u / safe_v
                b22 = np.einsum("...i,...i->...", VV, normal) / safe_v / safe_v
                determinant = np.where(good, sine * sine, 1)
                K = (b11 * b22 - b12 * b12) / determinant
                H = (b11 + b22 - 2 * cosine * b12) / (2 * determinant)
                root = np.sqrt(np.maximum(0, H * H - K))
                good &= np.isfinite(H) & np.isfinite(K) & np.isfinite(root)
                normal[~good] = 0
                points[us, vs] = pt + world_origin
                normals[us, vs], valid[us, vs] = normal, good
                maximum[us, vs] = np.where(good, H + root, np.nan)
                minimum[us, vs] = np.where(good, H - root, np.nan)
                mean[us, vs], gaussian[us, vs] = (
                    np.where(good, H, np.nan), np.where(good, K, np.nan),
                )
        if singular_policy == "raise" and not valid.all():
            raise SurfaceEvaluationError(
                f"{np.count_nonzero(~valid)} samples are singular/ill-conditioned"
            )
        return SurfaceGeometry(points, normals, maximum, minimum, mean, gaussian, valid)


@dataclass(frozen=True, slots=True)
class SegmentationResult:
    """Greedy analytic support sets, with original flattened sample indices.

    Coplanar/disconnected supports may form one primitive. This is not a mesh
    connectivity, trimming, or fillet-adjacency reconstruction result.
    """

    primitives: list[Primitive]
    unassigned_indices: IntArray
    topology_labels: IntArray


@dataclass(slots=True)
class _Fit:
    model: Any
    inliers: BoolArray
    rmse: float = np.inf
    iterations: int = 0


def _score(mask: BoolArray, residual: FloatArray) -> tuple[int, float]:
    count = int(np.count_nonzero(mask))
    return count, -float(np.mean(residual[mask] ** 2)) if count else -np.inf


class RANSACPrimitiveClassifier:
    """Normal-constrained plane/cylinder RANSAC, with reproducible local RNG.

    Spatial tolerance uses input length units; planar_threshold uses inverse
    input length units. Normals are normalized internally and their signs do not
    affect membership. A seeded instance advances its RNG across calls; create
    separate seeded instances for repeated runs or concurrent workers.
    """

    def __init__(
        self, spatial_tol: float = 0.005, normal_tol_deg: float = 3.0,
        *, random_state: int | np.random.Generator | None = None,
        planar_threshold: float = 0.05, min_plane_inliers: int = 6,
        min_cylinder_inliers: int = 12, max_primitives: int = 100,
        plane_iterations: int = 150, cylinder_iterations: int = 300,
        radius_relative_tolerance: float = 0.35, refine: bool = True,
    ) -> None:
        self.spatial_tol = _positive(spatial_tol, "spatial_tol")
        if not np.isfinite(normal_tol_deg) or not 0 < normal_tol_deg <= 90:
            raise GeometryValidationError("normal_tol_deg must lie in (0, 90]")
        self.normal_tol_rad = float(np.radians(normal_tol_deg))
        self._cos_tol = float(np.cos(self.normal_tol_rad))
        self.planar_threshold = _positive(planar_threshold, "planar_threshold")
        self.min_plane_inliers = _integer(min_plane_inliers, "min_plane_inliers", 3)
        self.min_cylinder_inliers = _integer(min_cylinder_inliers, "min_cylinder_inliers", 3)
        self.max_primitives = _integer(max_primitives, "max_primitives", 1)
        self.plane_iterations = _integer(plane_iterations, "plane_iterations", 1)
        self.cylinder_iterations = _integer(cylinder_iterations, "cylinder_iterations", 1)
        self.radius_relative_tolerance = _positive(
            radius_relative_tolerance, "radius_relative_tolerance",
        )
        self.refine = bool(refine)
        self._rng = (
            random_state
            if isinstance(random_state, np.random.Generator)
            else np.random.default_rng(random_state)
        )

    def classify_local_topology(
        self, curvatures: Mapping[str, ArrayLike], planar_threshold: float | None = None,
    ) -> IntArray:
        """Labels: 0 planar, 1 cylinder-like, 2 other/invalid.

        The near-zero principal curvature can be either algebraic eigenvalue.
        This is important when normals reverse the signs of both eigenvalues.
        """
        threshold = (
            self.planar_threshold
            if planar_threshold is None
            else _positive(planar_threshold, "planar_threshold")
        )
        try:
            k1 = _array(curvatures["Principal_Max"], "Principal_Max", finite=False)
            k2 = _array(curvatures["Principal_Min"], "Principal_Min", finite=False)
        except KeyError as exc:
            raise GeometryValidationError(f"missing curvature field {exc.args[0]}") from exc
        if k1.shape != k2.shape:
            raise GeometryValidationError("principal curvature arrays must have the same shape")
        valid = np.isfinite(k1) & np.isfinite(k2)
        if "Valid" in curvatures:
            supplied = np.asarray(curvatures["Valid"])
            if supplied.shape != k1.shape or supplied.dtype.kind != "b":
                raise GeometryValidationError(
                    "Valid must be a boolean array with the curvature shape"
                )
            valid &= supplied
        high, low = np.maximum(np.abs(k1), np.abs(k2)), np.minimum(np.abs(k1), np.abs(k2))
        labels = np.full(k1.shape, 2, dtype=np.int64)
        labels[valid & (high < threshold)] = 0
        labels[valid & (high >= threshold) & (low < threshold)] = 1
        return labels

    @staticmethod
    def _prepare(points: ArrayLike, normals: ArrayLike) -> tuple[FloatArray, FloatArray, BoolArray]:
        pts, normal = _vectors(points, "points"), _vectors(normals, "normals")
        if pts.shape != normal.shape:
            raise GeometryValidationError("points and normals must have the same shape")
        lengths = np.linalg.norm(normal, axis=1)
        usable = (lengths > 0) & np.isfinite(lengths)
        normal = normal / np.where(usable, lengths, 1)[:, None]
        return pts, normal, usable

    def _plane_fit(self, points: ArrayLike, normals: ArrayLike, max_iter: int) -> _Fit:
        max_iter = _integer(max_iter, "max_iter", 1)
        pts, normal, usable = self._prepare(points, normals)
        candidates = np.flatnonzero(usable)
        best = _Fit(None, np.zeros(len(pts), dtype=bool))
        best_score = (0, -np.inf)
        if len(candidates) < 3:
            return best
        for iteration in range(max_iter):
            best.iterations = iteration + 1
            sample = pts[self._rng.choice(candidates, 3, replace=False)]
            e1, e2 = sample[1] - sample[0], sample[2] - sample[0]
            raw = np.cross(e1, e2)
            length = np.linalg.norm(raw)
            if length <= 1e-12 * np.linalg.norm(e1) * np.linalg.norm(e2) or length == 0:
                continue
            axis = _canonical(raw / length)
            residual = np.abs((pts - sample[0]) @ axis)
            mask = (
                usable & (residual <= self.spatial_tol)
                & (np.abs(normal @ axis) >= self._cos_tol)
            )
            score = _score(mask, residual)
            if score > best_score:
                best_score = score
                best.model = np.r_[axis, -np.dot(axis, sample[0])]
                best.inliers, best.rmse = mask, float(np.sqrt(-score[1]))
            if score[0] == len(candidates):
                break
        if self.refine and best.model is not None and np.count_nonzero(best.inliers) >= 3:
            support = pts[best.inliers]
            center = np.mean(support, axis=0)
            try:
                _, singular, vh = np.linalg.svd(support - center, full_matrices=False)
                if singular[1] > 1e-12 * singular[0]:
                    axis = _canonical(vh[-1])
                    residual = np.abs((pts - center) @ axis)
                    mask = (
                        usable & (residual <= self.spatial_tol)
                        & (np.abs(normal @ axis) >= self._cos_tol)
                    )
                    score = _score(mask, residual)
                    if score >= best_score:
                        best.model = np.r_[axis, -np.dot(axis, center)]
                        best.inliers, best.rmse = mask, float(np.sqrt(-score[1]))
            except np.linalg.LinAlgError:
                LOGGER.debug("Plane refinement failed; retaining RANSAC hypothesis", exc_info=True)
        return best

    def fit_plane_ransac(
        self, points: ArrayLike, normals: ArrayLike, max_iter: int = 150,
    ) -> tuple[FloatArray, BoolArray]:
        """Return plane equation and an N-element mask; zero equation means no fit."""
        result = self._plane_fit(points, normals, max_iter)
        return np.zeros(4) if result.model is None else result.model, result.inliers

    def _cylinder_membership(
        self, points: FloatArray, normals: FloatArray, usable: BoolArray,
        geometry: CylinderGeometry,
    ) -> tuple[BoolArray, FloatArray]:
        origin, axis, radius = geometry
        vectors = points - origin
        # Projection requires the axial scalar AND axis direction (outer product).
        radial = vectors - (vectors @ axis)[:, None] * axis
        lengths = np.linalg.norm(radial, axis=1)
        expected = radial / np.where(lengths > 0, lengths, 1)[:, None]
        residual = np.abs(lengths - radius)
        aligned = np.abs(np.einsum("ij,ij->i", normals, expected)) >= self._cos_tol
        return usable & (lengths > 0) & (residual <= self.spatial_tol) & aligned, residual

    def _refine_cylinder(
        self, points: FloatArray, normals: FloatArray, geometry: CylinderGeometry,
    ) -> CylinderGeometry:
        origin, axis, radius = geometry
        if len(points) > 4096:
            selection = np.linspace(0, len(points) - 1, 4096, dtype=np.int64)
            points, normals = points[selection], normals[selection]
        anchor = np.mean(points, axis=0)
        e1, e2 = _frame(axis)
        offset = origin - anchor
        initial = np.array([offset @ e1, offset @ e2, 0.0, 0.0, np.log(radius)])

        def unpack(parameters: FloatArray) -> CylinderGeometry:
            center = anchor + parameters[0] * e1 + parameters[1] * e2
            direction = axis + parameters[2] * e1 + parameters[3] * e2
            direction /= np.linalg.norm(direction)
            return center, direction, float(np.exp(parameters[4]))

        normal_scale = self.spatial_tol / max(np.sin(self.normal_tol_rad), 0.01)

        def residuals(parameters: FloatArray) -> FloatArray:
            center, direction, rad = unpack(parameters)
            vec = points - center
            radial = vec - (vec @ direction)[:, None] * direction
            lengths = np.linalg.norm(radial, axis=1)
            radial /= np.where(lengths > 0, lengths, 1)[:, None]
            angular = np.cross(normals, radial) * normal_scale
            return np.r_[lengths - rad, angular.ravel()]

        result = least_squares(
            residuals, initial, loss="soft_l1", f_scale=self.spatial_tol,
            max_nfev=100, x_scale="jac",
            bounds=(
                [-np.inf, -np.inf, -1.0, -1.0, np.log(radius) - np.log(10.0)],
                [np.inf, np.inf, 1.0, 1.0, np.log(radius) + np.log(10.0)],
            ),
        )
        return unpack(result.x) if result.success else geometry

    def _cylinder_fit(
        self, points: ArrayLike, normals: ArrayLike,
        target_curvature: float | None, max_iter: int,
    ) -> _Fit:
        max_iter = _integer(max_iter, "max_iter", 1)
        prior_radius = None
        if target_curvature is not None:
            prior_radius = 1.0 / _positive(abs(target_curvature), "abs(target_curvature)")
        pts, normal, usable = self._prepare(points, normals)
        candidates = np.flatnonzero(usable)
        best = _Fit(None, np.zeros(len(pts), dtype=bool))
        best_score = (0, -np.inf)
        if len(candidates) < 2:
            return best
        anchor = np.mean(pts[candidates], axis=0)
        for iteration in range(max_iter):
            best.iterations = iteration + 1
            indices = self._rng.choice(candidates, 2, replace=False)
            n1, n2 = normal[indices]
            axis = np.cross(n1, n2)
            length = np.linalg.norm(axis)
            if length < 1e-6:
                # Parallel normals do not identify a unique cylinder axis.
                continue
            axis = _canonical(axis / length)
            pair = pts[indices] - anchor
            pair -= (pair @ axis)[:, None] * axis
            # Both relative normal signs are considered. A signed radius then
            # handles inward and outward normals without moving to the wrong axis.
            for sign in (1.0, -1.0):
                delta_normal = n1 - sign * n2
                denominator = np.dot(delta_normal, delta_normal)
                if denominator < 1e-12:
                    continue
                signed_radius = float(np.dot(pair[0] - pair[1], delta_normal) / denominator)
                radius = abs(signed_radius)
                if not np.isfinite(radius) or radius <= np.finfo(float).tiny:
                    continue
                if (
                    prior_radius is not None
                    and abs(radius - prior_radius) > self.radius_relative_tolerance * prior_radius
                ):
                    continue
                center = anchor + 0.5 * (
                    pair[0] - signed_radius * n1 + pair[1] - signed_radius * sign * n2
                )
                geometry = (center, axis, radius)
                mask, residual = self._cylinder_membership(pts, normal, usable, geometry)
                score = _score(mask, residual)
                if score > best_score:
                    best_score = score
                    best.model, best.inliers, best.rmse = geometry, mask, float(np.sqrt(-score[1]))
            if best_score[0] == len(candidates):
                break
        if self.refine and best.model is not None and np.count_nonzero(best.inliers) >= 6:
            try:
                geometry = self._refine_cylinder(
                    pts[best.inliers], normal[best.inliers], best.model,
                )
                radius_ok = (
                    prior_radius is None
                    or abs(geometry[2] - prior_radius)
                    <= self.radius_relative_tolerance * prior_radius
                )
                mask, residual = self._cylinder_membership(pts, normal, usable, geometry)
                score = _score(mask, residual)
                if radius_ok and score >= best_score:
                    best.model, best.inliers, best.rmse = geometry, mask, float(np.sqrt(-score[1]))
            except (np.linalg.LinAlgError, ValueError, FloatingPointError):
                LOGGER.debug(
                    "Cylinder refinement failed; retaining RANSAC hypothesis", exc_info=True,
                )
        return best

    def fit_cylinder_ransac(
        self, points: ArrayLike, normals: ArrayLike,
        target_curvature: float | None = None, max_iter: int = 300,
    ) -> tuple[CylinderGeometry | None, BoolArray]:
        """Estimate axis and radius; optional curvature is a radius prior, not a constant fit.

        Two point/normal samples identify a hypothesis. Radius is estimated from
        those samples and optionally refined. Mixed radii should use no global
        prior; segmentation deliberately does not use a single median radius.
        """
        result = self._cylinder_fit(points, normals, target_curvature, max_iter)
        return result.model, result.inliers

    def segment_primitives(
        self, points: ArrayLike, normals: ArrayLike, curvatures: Mapping[str, ArrayLike],
    ) -> list[Primitive]:
        return self.segment(points, normals, curvatures).primitives

    def segment(
        self, points: ArrayLike, normals: ArrayLike, curvatures: Mapping[str, ArrayLike],
    ) -> SegmentationResult:
        pts = _array(points, "points")
        normal = _array(normals, "normals")
        if pts.ndim < 2 or pts.shape[-1] != 3 or pts.shape != normal.shape:
            raise GeometryValidationError("points/normals must have matching (...,3) shapes")
        labels = self.classify_local_topology(curvatures)
        if labels.shape != pts.shape[:-1]:
            raise GeometryValidationError("curvature grid must match points.shape[:-1]")
        pts, normal = pts.reshape(-1, 3), normal.reshape(-1, 3)
        labels = labels.reshape(-1)
        _, _, usable = self._prepare(pts, normal)
        labels[~usable] = 2
        remaining = np.ones(len(pts), dtype=bool)
        primitives: list[Primitive] = []
        for label, minimum in ((1, self.min_cylinder_inliers), (0, self.min_plane_inliers)):
            while len(primitives) < self.max_primitives:
                indices = np.flatnonzero(remaining & (labels == label))
                if len(indices) < minimum:
                    break
                result = (
                    self._cylinder_fit(
                        pts[indices], normal[indices], None, self.cylinder_iterations,
                    )
                    if label == 1
                    else self._plane_fit(pts[indices], normal[indices], self.plane_iterations)
                )
                support = indices[result.inliers]
                if result.model is None or len(support) < minimum:
                    break
                primitive: Primitive
                if label == 1:
                    origin, axis, radius = result.model
                    primitive = {
                        "type": "cylinder_fillet",  # Legacy key: does NOT prove a fillet.
                        "geometry": {"origin": origin, "axis": axis, "radius": radius},
                    }
                else:
                    primitive = {"type": "plane", "geometry": {"plane_equation": result.model}}
                primitive.update({
                    "point_indices": support,
                    "diagnostics": {"inlier_count": len(support), "rmse": result.rmse,
                                    "iterations": result.iterations},
                })
                primitives.append(primitive)
                remaining[support] = False
        LOGGER.info(
            "Extracted %d primitives; %d/%d samples unassigned",
            len(primitives), np.count_nonzero(remaining), len(pts),
        )
        return SegmentationResult(primitives, np.flatnonzero(remaining), labels)


class CADGeometryCardEngine:
    """Versioned, JSON-safe analytic surface cards with explicit approximate bounds.

    Machine parameters retain full precision. ``precision`` applies only to the
    optional display_parameters, so rounding cannot silently destroy small parts.
    Plane bounds are projected convex hulls: holes, concavities, and disconnected
    support are NOT reconstructed. Cylinders use the minimum sampled angular
    envelope and axial extent, not a manufactured full cylinder or closed solid.
    """

    def __init__(self, precision: int | None = 4, *, length_unit: str = "unspecified") -> None:
        if precision is not None:
            precision = _integer(precision, "precision")
            if precision > 15:
                raise GeometryValidationError("precision must be <= 15 or None")
        if length_unit not in (*_UNIT_TO_MM, "unspecified"):
            raise GeometryValidationError("length_unit must be mm, cm, m, in, or unspecified")
        self.prec = precision
        self.length_unit = length_unit

    def compute_cards(
        self, primitives: Sequence[Primitive], flattened_pts: ArrayLike,
    ) -> dict[str, Any]:
        points = _vectors(flattened_pts, "flattened_pts")
        operations: list[dict[str, Any]] = []
        for index, primitive in enumerate(primitives):
            try:
                indices = np.asarray(primitive["point_indices"])
                kind, geometry = primitive["type"], primitive["geometry"]
            except (KeyError, TypeError) as exc:
                raise GeometryValidationError(
                    f"primitive {index} is missing required fields"
                ) from exc
            if indices.ndim != 1 or indices.dtype.kind not in "iu" or len(indices) < 3:
                raise GeometryValidationError(
                    f"primitive {index}: expected at least 3 integer point_indices"
                )
            if (
                np.any(indices < 0)
                or np.any(indices >= len(points))
                or len(np.unique(indices)) != len(indices)
            ):
                raise GeometryValidationError(
                    f"primitive {index}: invalid or duplicate point_indices"
                )
            subset = points[indices]
            parameters: dict[str, Any]
            operation: dict[str, Any]
            try:
                if kind == "plane":
                    equation = _array(geometry["plane_equation"], "plane_equation")
                    if equation.shape != (4,):
                        raise GeometryValidationError("plane_equation must have shape (4,)")
                    normal = _unit(equation[:3], "plane normal")
                    intercept = float(equation[3] / np.linalg.norm(equation[:3]))
                    center = np.mean(subset, axis=0)
                    center -= (center @ normal + intercept) * normal
                    x_axis, y_axis = _frame(normal)
                    uv = np.column_stack(((subset - center) @ x_axis, (subset - center) @ y_axis))
                    try:
                        hull = ConvexHull(uv)
                    except QhullError as exc:
                        raise GeometryValidationError(
                            f"primitive {index}: planar support has no finite area"
                        ) from exc
                    boundary = (
                        center + uv[hull.vertices, :1] * x_axis
                        + uv[hull.vertices, 1:] * y_axis
                    )
                    parameters = {
                        "normal": normal.tolist(),
                        "intercept": intercept,
                        "reference_centroid": center.tolist(),
                        "boundary_vertices": boundary.tolist(),
                    }
                    operation = {
                        "op_index": index,
                        "primitive": "PLANE",
                        "parameters": parameters,
                        "bounds_method": "projected_convex_hull",
                    }
                elif kind in ("cylinder_fillet", "cylinder"):
                    origin = _vector(geometry["origin"], "origin")
                    axis = _unit(geometry["axis"], "axis")
                    radius = _positive(geometry["radius"], "radius")
                    vectors = subset - origin
                    t = vectors @ axis
                    length = _positive(float(np.ptp(t)), "cylinder axial extent")
                    x_axis, y_axis = _frame(axis)
                    angles = np.unique(
                        np.mod(np.arctan2(vectors @ y_axis, vectors @ x_axis), 2 * np.pi),
                    )
                    if len(angles) < 2:
                        raise GeometryValidationError("cylinder samples have no angular extent")
                    gaps = np.diff(np.r_[angles, angles[0] + 2 * np.pi])
                    gap_index = int(np.argmax(gaps))
                    start = float(angles[(gap_index + 1) % len(angles)])
                    sweep = _positive(float(2 * np.pi - gaps[gap_index]), "cylinder angular extent")
                    parameters = {
                        "axis_origin": (origin + np.min(t) * axis).tolist(),
                        "axis_direction": axis.tolist(), "reference_direction": x_axis.tolist(),
                        "radius": radius,
                        "length": length,
                        "angular_bounds": [start, start + sweep],
                    }
                    operation = {
                        "op_index": index,
                        "primitive": "CYLINDER",
                        "parameters": parameters,
                        "bounds_method": "sample_angular_envelope_and_axial_range",
                    }
                else:
                    raise GeometryValidationError(f"unsupported primitive type: {kind!r}")
            except KeyError as exc:
                raise GeometryValidationError(
                    f"primitive {index}: missing geometry field {exc.args[0]}"
                ) from exc
            operation["source_point_indices"] = indices.tolist()
            if self.prec is not None:
                operation["display_parameters"] = self._rounded(parameters)
            if "diagnostics" in primitive:
                operation["fit_diagnostics"] = dict(primitive["diagnostics"])
            operations.append(operation)
        card = {
            "schema_version": "1.0", "length_unit": self.length_unit,
            "representation": "bounded_analytic_surface_fragments",
            "bounds_are_reconstructed_topology": False,
            "total_primitives": len(operations), "operations": operations,
        }
        # Check the exact interchange boundary, not only NumPy arrays upstream.
        self.to_json(card)
        return card

    def _rounded(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._rounded(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._rounded(item) for item in value]
        if isinstance(value, float) and self.prec is not None:
            return round(value, self.prec)
        return value

    @staticmethod
    def to_json(card_data: Mapping[str, Any], *, indent: int = 2) -> str:
        try:
            return json.dumps(card_data, indent=indent, allow_nan=False, sort_keys=True) + "\n"
        except (TypeError, ValueError) as exc:
            raise GeometryValidationError(f"card is not finite JSON data: {exc}") from exc

    def write_json(
        self, card_data: Mapping[str, Any], file_path: str | os.PathLike[str],
        *, overwrite: bool = False,
    ) -> Path:
        return write_text_atomic(file_path, self.to_json(card_data), overwrite=overwrite)


class STEPGeometryExportEngine:
    """Construct actual bounded faces and exchange them through Open CASCADE.

    Requires optional ``cadquery-ocp`` (OCP 7.9.x tested). The file contains a
    compound of surface fragments, NOT a sewn shell or watertight solid. Source
    units must be explicit; geometry is converted to millimetres for exchange.
    Entity IDs and STEP headers are kernel-managed, not hand-authored. Repeated
    calls use fresh writers; byte-identical timestamps/headers are not promised.
    Native OCCT transfer diagnostics may be written to the process console.
    """

    def __init__(
        self, start_id: int = 10, *, length_unit: str | None = None,
        schema: Literal["AP203", "AP214IS", "AP242DIS"] = "AP214IS", tolerance: float = 1e-7,
    ) -> None:
        _integer(start_id, "start_id", 1)
        if start_id != 10:
            warnings.warn(
                "start_id is deprecated; Open CASCADE owns STEP entity numbering",
                DeprecationWarning, stacklevel=2,
            )
        if length_unit is not None and length_unit not in _UNIT_TO_MM:
            raise GeometryValidationError("length_unit must be mm, cm, m, or in")
        if schema not in ("AP203", "AP214IS", "AP242DIS"):
            raise GeometryValidationError("unsupported STEP schema")
        self.length_unit = length_unit
        self.schema = schema
        self.tolerance = _positive(tolerance, "tolerance (mm)")

    def export(self, card_data: Mapping[str, Any]) -> str:
        """Return STEP text. Missing units/bounds or a missing backend are errors."""
        if not isinstance(card_data, Mapping):
            raise GeometryValidationError("card_data must be a mapping")
        operations = card_data.get("operations")
        if not isinstance(operations, list) or not operations:
            raise GeometryValidationError("STEP export requires at least one bounded operation")
        if card_data.get("total_primitives") != len(operations):
            raise GeometryValidationError("total_primitives disagrees with operations")
        declared = card_data.get("length_unit", "unspecified")
        if self.length_unit is not None and declared not in ("unspecified", self.length_unit):
            raise GeometryValidationError("exporter units conflict with the card's declared units")
        units = self.length_unit or declared
        if units not in _UNIT_TO_MM:
            raise GeometryValidationError("STEP requires explicit source units: mm, cm, m, or in")
        CADGeometryCardEngine.to_json(card_data)
        try:
            from OCP.BRep import BRep_Builder
            from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
            from OCP.BRepCheck import BRepCheck_Analyzer
            from OCP.IFSelect import IFSelect_RetDone
            from OCP.Interface import Interface_Static
            from OCP.STEPControl import STEPControl_AsIs, STEPControl_Controller, STEPControl_Writer
            from OCP.TopoDS import TopoDS_Compound
            from OCP.gp import gp_Ax3, gp_Cylinder, gp_Dir, gp_Pln, gp_Pnt
        except ImportError as exc:
            raise OptionalDependencyError(
                "STEP export requires OCP: install 'cadquery-ocp>=7.9,<8' "
                "or this project's [step] extra"
            ) from exc
        scale = _UNIT_TO_MM[units]
        # OCCT exposes process-global exchange settings. Serialize this module's
        # writers and restore all settings. External OCCT code must coordinate
        # separately; this is not a global thread-safety guarantee for OCP.
        with _STEP_LOCK:
            try:
                compound = TopoDS_Compound()
                builder = BRep_Builder()
                builder.MakeCompound(compound)
                for index, op in enumerate(operations):
                    try:
                        parameters = op["parameters"]
                        if op["primitive"] == "PLANE":
                            normal = _unit(parameters["normal"], "plane normal")
                            center = _vector(
                                parameters["reference_centroid"], "reference_centroid",
                            ) * scale
                            boundary = _vectors(
                                parameters["boundary_vertices"], "boundary_vertices",
                            ) * scale
                            if (
                                len(boundary) < 3
                                or np.any(np.abs((boundary - center) @ normal) > self.tolerance)
                            ):
                                raise GeometryValidationError(
                                    "plane boundary must have >=3 coplanar vertices"
                                )
                            polygon = BRepBuilderAPI_MakePolygon()
                            for vertex in boundary:
                                polygon.Add(gp_Pnt(*map(float, vertex)))
                            polygon.Close()
                            if not polygon.IsDone():
                                raise STEPExportError(
                                    f"operation {index}: could not construct boundary wire"
                                )
                            plane = gp_Pln(gp_Pnt(*map(float, center)), gp_Dir(*map(float, normal)))
                            face_builder = BRepBuilderAPI_MakeFace(plane, polygon.Wire(), True)
                        elif op["primitive"] == "CYLINDER":
                            origin = _vector(parameters["axis_origin"], "axis_origin") * scale
                            axis = _unit(parameters["axis_direction"], "axis_direction")
                            reference = _unit(
                                parameters["reference_direction"], "reference_direction",
                            )
                            if abs(reference @ axis) > 1e-8:
                                raise GeometryValidationError(
                                    "cylinder reference_direction must be perpendicular to its axis"
                                )
                            radius = _positive(parameters["radius"], "radius") * scale
                            length = _positive(parameters["length"], "length") * scale
                            angles = _array(parameters["angular_bounds"], "angular_bounds")
                            if (
                                angles.shape != (2,)
                                or not 0 < angles[1] - angles[0] <= 2 * np.pi + 1e-12
                            ):
                                raise GeometryValidationError(
                                    "cylinder angular_bounds must span (0, 2*pi]"
                                )
                            placement = gp_Ax3(
                                gp_Pnt(*map(float, origin)), gp_Dir(*map(float, axis)),
                                gp_Dir(*map(float, reference)),
                            )
                            face_builder = BRepBuilderAPI_MakeFace(
                                gp_Cylinder(placement, radius),
                                float(angles[0]), float(angles[1]), 0.0, length,
                            )
                        else:
                            raise GeometryValidationError(
                                f"unsupported STEP primitive {op['primitive']!r}"
                            )
                    except (KeyError, TypeError) as exc:
                        raise GeometryValidationError(
                            f"operation {index} lacks required bounded-geometry fields"
                        ) from exc
                    if not face_builder.IsDone():
                        raise STEPExportError(
                            f"operation {index}: face builder failed: {face_builder.Error()}"
                        )
                    face = face_builder.Face()
                    if not BRepCheck_Analyzer(face).IsValid():
                        raise STEPExportError(
                            f"operation {index}: Open CASCADE reports an invalid face"
                        )
                    builder.Add(compound, face)
                STEPControl_Controller.Init_s()
                settings = {"write.step.schema": self.schema, "write.step.unit": "MM"}
                previous = {key: Interface_Static.CVal_s(key) for key in settings}
                try:
                    for key, value in settings.items():
                        if not Interface_Static.SetCVal_s(key, value):
                            raise STEPExportError(f"Open CASCADE rejected setting {key}={value}")
                    writer = STEPControl_Writer()
                    writer.Model().SetLocalLengthUnit(1.0)
                    writer.Model().SetWriteLengthUnit(1.0)
                    writer.SetTolerance(self.tolerance)
                    if writer.Transfer(compound, STEPControl_AsIs) != IFSelect_RetDone:
                        raise STEPExportError("Open CASCADE STEP transfer failed")
                    stream = io.BytesIO()
                    if writer.WriteStream(stream) != IFSelect_RetDone:
                        raise STEPExportError("Open CASCADE STEP serialization failed")
                    text = stream.getvalue().decode("utf-8")
                finally:
                    for key, value in previous.items():
                        Interface_Static.SetCVal_s(key, value)
            except (GeometryValidationError, STEPExportError):
                raise
            except Exception as exc:
                # Foreign C++ boundary: retain the cause, do not swallow failures.
                raise STEPExportError(f"Open CASCADE export failed: {exc}") from exc
        LOGGER.info("Exported %d bounded surface fragments in millimetres", len(operations))
        return text

    def write(
        self, card_data: Mapping[str, Any], file_path: str | os.PathLike[str],
        *, overwrite: bool = False,
    ) -> Path:
        return write_text_atomic(file_path, self.export(card_data), overwrite=overwrite)


def main() -> None:
    """Small deterministic primitive demo; JSON needs no STEP backend or input file."""
    grid = np.linspace(-2.0, 2.0, 12)
    x, y = np.meshgrid(grid, grid, indexing="ij")
    points = np.column_stack((x.ravel(), y.ravel(), np.zeros(x.size)))
    normals = np.tile([0.0, 0.0, 1.0], (len(points), 1))
    curvature = {"Principal_Max": np.zeros(len(points)), "Principal_Min": np.zeros(len(points))}
    primitives = RANSACPrimitiveClassifier(random_state=42).segment_primitives(
        points, normals, curvature,
    )
    engine = CADGeometryCardEngine(length_unit="mm")
    print(engine.to_json(engine.compute_cards(primitives, points)), end="")


if __name__ == "__main__":
    main()
