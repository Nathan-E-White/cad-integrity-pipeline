"""Geometric measurements with explicit limits on what their evidence establishes."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike
from scipy.spatial import cKDTree

from .arrays import FloatArray, IntArray, floats, positive, readonly
from .errors import InvalidGeometry
from .models import TriangleMesh


@dataclass(frozen=True, slots=True, eq=False)
class MeshQualityReport:
    areas: FloatArray
    aspect_ratios: FloatArray
    mean_ratios: FloatArray
    skewness: FloatArray
    degenerate_triangle_ids: IntArray

    @property
    def worst_skewness(self) -> float | None:
        return float(self.skewness.max()) if self.skewness.size else None


def triangle_areas(mesh: TriangleMesh) -> FloatArray:
    xyz = mesh.vertices[mesh.triangles]
    return 0.5 * np.linalg.norm(np.cross(xyz[:, 1]-xyz[:, 0], xyz[:, 2]-xyz[:, 0]), axis=1)


def mesh_quality(mesh: TriangleMesh, *, area_tolerance: float = 0.0) -> MeshQualityReport:
    """Aspect ratio >=1 (best=1); mean ratio in [0,1] (best=1); skewness best=0.

    Zero-area triangles remain degenerate; no positive area is invented by clipping.
    Area tolerance uses the square of mesh.length_unit.
    """
    positive(area_tolerance, "area_tolerance", allow_zero=True)
    xyz = mesh.vertices[mesh.triangles]
    lengths = np.stack((np.linalg.norm(xyz[:, 1]-xyz[:, 2], axis=1),
                        np.linalg.norm(xyz[:, 0]-xyz[:, 2], axis=1),
                        np.linalg.norm(xyz[:, 0]-xyz[:, 1], axis=1)), axis=1)
    areas = triangle_areas(mesh)
    semiperimeter = lengths.sum(axis=1)/2
    valid = (areas > area_tolerance) & np.all(lengths > 0, axis=1)
    aspect = np.full(len(areas), np.inf)
    mean_ratio = np.zeros(len(areas))
    skewness = np.ones(len(areas))
    if np.any(valid):
        sides = lengths[valid]
        a, b, c = sides.T
        radius = areas[valid]/semiperimeter[valid]
        aspect[valid] = np.max(sides, axis=1)/(2*np.sqrt(3)*radius)
        mean_ratio[valid] = 4*np.sqrt(3)*areas[valid]/np.sum(sides*sides, axis=1)
        cosines = np.column_stack(((b*b+c*c-a*a)/(2*b*c),
                                   (a*a+c*c-b*b)/(2*a*c),
                                   (a*a+b*b-c*c)/(2*a*b)))
        angles = np.arccos(np.clip(cosines, -1, 1))
        optimum = np.pi/3
        skewness[valid] = np.maximum((angles.max(axis=1)-optimum)/(np.pi-optimum),
                                     (optimum-angles.min(axis=1))/optimum)
    return MeshQualityReport(readonly(areas), readonly(aspect), readonly(mean_ratio),
                             readonly(skewness), readonly(np.flatnonzero(~valid)))


@dataclass(frozen=True, slots=True)
class SampledHausdorffReport:
    a_to_b: float
    b_to_a: float
    symmetric: float
    samples_a: int
    samples_b: int
    length_unit: str
    scope: str = "finite_point_sets_only"


def sampled_hausdorff(a: ArrayLike, b: ArrayLike, *, length_unit: str = "mm"
                      ) -> SampledHausdorffReport:
    """Exact nearest-neighbor Hausdorff for the supplied points, not continuous surfaces."""
    a_ = floats(a, name="points_a", width=3)
    b_ = floats(b, name="points_b", width=3)
    if not len(a_) or not len(b_):
        raise InvalidGeometry("Hausdorff distance requires two nonempty point sets")
    # No N x M x 3 broadcast tensor. eps=0 is an exact query for these samples.
    ab_distances = np.asarray(cKDTree(b_).query(a_, k=1, eps=0, workers=1)[0])
    ba_distances = np.asarray(cKDTree(a_).query(b_, k=1, eps=0, workers=1)[0])
    ab = float(ab_distances.max())
    ba = float(ba_distances.max())
    return SampledHausdorffReport(ab, ba, max(ab, ba), len(a_), len(b_), length_unit)


def area_distortion(initial: TriangleMesh, deformed: TriangleMesh) -> FloatArray:
    """Area ratios, NOT stress/crack-tip predictions. Requires matching connectivity/units."""
    if initial.length_unit != deformed.length_unit or not np.array_equal(initial.triangles, deformed.triangles):
        raise InvalidGeometry("Area distortion requires matching connectivity and units")
    baseline = triangle_areas(initial)
    if np.any(baseline <= 0):
        raise InvalidGeometry("Area ratios are undefined for a degenerate baseline")
    return readonly(triangle_areas(deformed)/baseline)
