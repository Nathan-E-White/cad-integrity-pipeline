"""Bounded numerical demonstrations retained from the prototype.

These do not claim trimmed-face meshing, exact CAD intersection, or BEM adequacy.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike
from scipy.optimize import least_squares

from .arrays import FloatArray, positive
from .errors import InvalidGeometry, ResourceLimitExceeded
from .models import TriangleMesh


def _bounds(bounds: tuple[float, float]) -> tuple[float, float]:
    if len(bounds) != 2 or not np.all(np.isfinite(bounds)) or bounds[0] >= bounds[1]:
        raise ValueError("Parameter bounds must be finite and increasing")
    return float(bounds[0]), float(bounds[1])


def _xyz(value: Any, shape: tuple[int, ...]) -> FloatArray:
    if len(value) != 3:
        raise InvalidGeometry("Parametric functions must return a tuple (x, y, z)")
    coordinates = [np.broadcast_to(np.asarray(part, dtype=float), shape) for part in value]
    result = np.stack(coordinates, axis=-1)
    if not np.all(np.isfinite(result)):
        raise InvalidGeometry("Parametric evaluation produced nonfinite coordinates")
    return result


@dataclass(frozen=True, slots=True)
class ParametricCurve:
    function: Callable[[FloatArray], Any]
    bounds: tuple[float, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "bounds", _bounds(self.bounds))

    def evaluate(self, parameter: ArrayLike) -> FloatArray:
        t = np.asarray(parameter, dtype=np.float64)
        return _xyz(self.function(t), t.shape)


@dataclass(frozen=True, slots=True)
class ParametricSurface:
    function: Callable[[FloatArray, FloatArray], Any]
    u_bounds: tuple[float, float]
    v_bounds: tuple[float, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "u_bounds", _bounds(self.u_bounds))
        object.__setattr__(self, "v_bounds", _bounds(self.v_bounds))

    def evaluate(self, u: ArrayLike, v: ArrayLike) -> FloatArray:
        u_, v_ = np.broadcast_arrays(np.asarray(u, dtype=float), np.asarray(v, dtype=float))
        return _xyz(self.function(u_, v_), u_.shape)


@dataclass(frozen=True, slots=True)
class IntersectionResult:
    point: tuple[float, float, float]
    parameters: tuple[float, float, float]
    residual_norm: float
    function_evaluations: int
    scope: str = "one_local_numerical_root_no_uniqueness_guarantee"


def intersect_curve_surface(curve: ParametricCurve, surface: ParametricSurface,
                            guess: tuple[float, float, float], *, tolerance: float = 1e-8,
                            max_evaluations: int = 200) -> IntersectionResult:
    positive(tolerance, "tolerance")
    if max_evaluations < 1:
        raise ValueError("max_evaluations must be positive")
    bounds = np.array((curve.bounds, surface.u_bounds, surface.v_bounds)).T
    x0 = np.asarray(guess, dtype=float)
    if x0.shape != (3,) or not np.all(np.isfinite(x0)) or np.any(x0 < bounds[0]) or np.any(x0 > bounds[1]):
        raise ValueError("Initial parameters must lie within the declared bounds")

    def residual(p: FloatArray) -> FloatArray:
        return curve.evaluate(p[0])-surface.evaluate(p[1], p[2])

    fit = least_squares(residual, x0, bounds=(bounds[0], bounds[1]), max_nfev=max_evaluations,
                        ftol=1e-12, xtol=1e-12, gtol=1e-12)
    norm = float(np.linalg.norm(fit.fun))
    if not fit.success or norm > tolerance:
        raise InvalidGeometry(f"No verified local intersection: residual={norm:.6g}; {fit.message}")
    point = tuple(float(v) for v in curve.evaluate(fit.x[0]))
    parameters = tuple(float(v) for v in fit.x)
    return IntersectionResult(point, parameters, norm, int(fit.nfev))  # type: ignore[arg-type]


def mesh_parametric_patch(surface: ParametricSurface, *, u_samples: int = 10,
                          v_samples: int = 10, length_unit: str = "mm",
                          max_vertices: int = 1_000_000) -> TriangleMesh:
    """Mesh an untrimmed rectangular parameter domain; counts are samples, not divisions."""
    if any(isinstance(n, bool) or not isinstance(n, int) or n < 2 for n in (u_samples, v_samples)):
        raise ValueError("Sample counts must be integers >= 2")
    if u_samples*v_samples > max_vertices:
        raise ResourceLimitExceeded("Parametric patch exceeds the vertex budget")
    u, v = np.meshgrid(np.linspace(*surface.u_bounds, u_samples),
                       np.linspace(*surface.v_bounds, v_samples))
    nodes = surface.evaluate(u.ravel(), v.ravel())
    j, i = np.meshgrid(np.arange(v_samples-1), np.arange(u_samples-1), indexing="ij")
    a = (j*u_samples+i).ravel()
    triangles = np.stack((np.column_stack((a, a+1, a+u_samples)),
                           np.column_stack((a+1, a+u_samples+1, a+u_samples))), axis=1).reshape(-1, 3)
    return TriangleMesh(nodes, triangles, length_unit)


def uniform_refine(mesh: TriangleMesh, *, max_triangles: int = 1_000_000) -> TriangleMesh:
    """Conforming global 1-to-4 subdivision. No curve projection or adaptive accuracy claim."""
    if len(mesh.triangles)*4 > max_triangles:
        raise ResourceLimitExceeded("Refinement exceeds the triangle budget")
    vertices: list[list[float]] = mesh.vertices.tolist()
    midpoint: dict[tuple[int, int], int] = {}
    triangles: list[tuple[int, int, int]] = []
    for a_, b_, c_ in mesh.triangles:
        a, b, c = int(a_), int(b_), int(c_)
        indices = []
        for u, v in ((a, b), (b, c), (c, a)):
            key = (min(u, v), max(u, v))
            if key not in midpoint:
                midpoint[key] = len(vertices)
                vertices.append(((mesh.vertices[u]+mesh.vertices[v])/2).tolist())
            indices.append(midpoint[key])
        ab, bc, ca = indices
        triangles.extend(((a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)))
    return TriangleMesh(np.asarray(vertices, dtype=float).reshape(-1, 3),
                        np.asarray(triangles, dtype=np.int64).reshape(-1, 3), mesh.length_unit)
