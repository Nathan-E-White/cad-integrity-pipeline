"""Fixed-seed analytic, metamorphic, and independent numerical sea trials."""

from __future__ import annotations

import numpy as np
import pytest

from cad_integrity.errors import InvalidGeometry, ResourceLimitExceeded
from cad_integrity.metrics import area_distortion, mesh_quality, sampled_hausdorff
from cad_integrity.models import TriangleMesh
from cad_integrity.numerics import (
    ParametricCurve,
    ParametricSurface,
    intersect_curve_surface,
    mesh_parametric_patch,
    uniform_refine,
)


def _plane() -> ParametricSurface:
    return ParametricSurface(lambda u, v: (u, v, 0.0), (0.0, 1.0), (0.0, 1.0))


def test_planar_patch_has_the_known_area() -> None:
    mesh = mesh_parametric_patch(_plane(), u_samples=3, v_samples=4)
    assert mesh_quality(mesh).areas.sum() == pytest.approx(1.0)


def test_parametric_evaluation_broadcasts_analytic_plane_and_curved_patch() -> None:
    curve = ParametricCurve(lambda t: (np.cos(t), np.sin(t), 0.0), (0.0, np.pi))
    hemisphere = ParametricSurface(
        lambda u, v: (np.cos(u) * np.sin(v), np.sin(u) * np.sin(v), np.cos(v)),
        (0.0, 2.0 * np.pi),
        (0.0, np.pi / 2.0),
    )

    assert curve.evaluate(np.array([0.0, np.pi / 2.0, np.pi])).shape == (3, 3)
    assert curve.evaluate(0.0).shape == (3,)
    samples = hemisphere.evaluate(np.array([0.0, np.pi / 2.0]), np.pi / 2.0)
    np.testing.assert_allclose(np.linalg.norm(samples, axis=1), 1.0)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: ParametricCurve(lambda t: (t, t, t), (1.0, 1.0)),
        lambda: ParametricCurve(lambda t: (t, t, t), (0.0, np.inf)),
        lambda: ParametricSurface(lambda u, v: (u, v, np.inf), (0.0, 1.0), (0.0, 1.0)).evaluate(0.0, 0.0),
        lambda: ParametricCurve(lambda t: (t, t), (0.0, 1.0)).evaluate(0.0),
    ],
)
def test_parametric_seams_reject_invalid_bounds_and_coordinates(factory: object) -> None:
    with pytest.raises((InvalidGeometry, ValueError)):
        factory()  # type: ignore[operator]


def test_uniform_refinement_preserves_planar_area_and_shared_midpoints() -> None:
    original = mesh_parametric_patch(_plane(), u_samples=4, v_samples=3)
    refined = uniform_refine(original)

    assert len(refined.triangles) == 4 * len(original.triangles)
    assert mesh_quality(refined).areas.sum() == pytest.approx(mesh_quality(original).areas.sum())
    original_edges = {
        tuple(sorted((int(a), int(b))))
        for triangle in original.triangles
        for a, b in zip(triangle, np.roll(triangle, -1), strict=True)
    }
    for a, b in original_edges:
        midpoint = (original.vertices[a] + original.vertices[b]) / 2.0
        assert sum(np.allclose(vertex, midpoint) for vertex in refined.vertices) == 1


def test_rigid_transform_and_scaling_follow_quality_and_distance_relations() -> None:
    mesh = mesh_parametric_patch(_plane(), u_samples=3, v_samples=3)
    rotation = np.array(((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)))
    rigid = TriangleMesh(mesh.vertices @ rotation.T + np.array((4.0, -2.0, 7.0)), mesh.triangles)
    scaled = TriangleMesh(mesh.vertices * 3.0, mesh.triangles)

    np.testing.assert_allclose(mesh_quality(rigid).mean_ratios, mesh_quality(mesh).mean_ratios)
    np.testing.assert_allclose(mesh_quality(rigid).skewness, mesh_quality(mesh).skewness)
    np.testing.assert_allclose(area_distortion(mesh, scaled), 9.0)
    distances = sampled_hausdorff(mesh.vertices, mesh.vertices + np.array((1.0, 0.0, 0.0)))
    scaled_distances = sampled_hausdorff(
        3.0 * mesh.vertices, 3.0 * (mesh.vertices + np.array((1.0, 0.0, 0.0)))
    )
    assert scaled_distances.symmetric == pytest.approx(3.0 * distances.symmetric)
    assert sampled_hausdorff(mesh.vertices, mesh.vertices, length_unit="cm").length_unit == "cm"


def _brute_force_directed_maximum(source: np.ndarray, target: np.ndarray) -> float:
    return float(np.linalg.norm(source[:, None, :] - target[None, :, :], axis=2).min(axis=1).max())


@pytest.mark.parametrize("seed", range(8))
def test_sampled_hausdorff_matches_independent_brute_force_oracle(seed: int) -> None:
    generator = np.random.default_rng(seed)
    left = generator.normal(size=(2 + seed % 4, 3))
    right = generator.normal(size=(3 + seed % 5, 3))
    report = sampled_hausdorff(left, right)

    assert report.a_to_b == pytest.approx(_brute_force_directed_maximum(left, right))
    assert report.b_to_a == pytest.approx(_brute_force_directed_maximum(right, left))
    assert report.symmetric == pytest.approx(max(report.a_to_b, report.b_to_a))


def test_local_intersection_labels_guess_dependent_multiple_roots_and_limits() -> None:
    surface = ParametricSurface(lambda u, v: (u, v, 0.0), (-1.0, 1.0), (-1.0, 1.0))
    multiple_roots = ParametricCurve(lambda t: (t, 0.0 * t, t * t - 0.25), (-1.0, 1.0))
    positive = intersect_curve_surface(multiple_roots, surface, (0.8, 0.0, 0.0))
    negative = intersect_curve_surface(multiple_roots, surface, (-0.8, 0.0, 0.0))

    assert positive.parameters[0] == pytest.approx(0.5, abs=1e-7)
    assert negative.parameters[0] == pytest.approx(-0.5, abs=1e-7)
    assert positive.parameters[0] != negative.parameters[0]  # This fixture has two local roots.
    assert "one_local" in positive.scope
    with pytest.raises(ValueError, match="declared bounds"):
        intersect_curve_surface(multiple_roots, surface, (-1.1, 0.0, 0.0))
    vertical = ParametricCurve(lambda t: (0.5 + 0.0 * t, 0.5 + 0.0 * t, t), (-1.0, 1.0))
    unique = intersect_curve_surface(vertical, surface, (0.2, 0.3, 0.4))
    assert unique.point == pytest.approx((0.5, 0.5, 0.0), abs=1e-8)
    assert unique.parameters == pytest.approx((0.0, 0.5, 0.5), abs=1e-8)
    with pytest.raises(InvalidGeometry, match="intersection"):
        intersect_curve_surface(vertical, surface, (0.2, 0.3, 0.4), max_evaluations=1)
    with pytest.raises(InvalidGeometry, match="intersection"):
        intersect_curve_surface(
            ParametricCurve(lambda t: (t, 0.0 * t, 2.0 + 0.0 * t), (0.0, 1.0)),
            surface,
            (0.5, 0.0, 0.0),
        )
    near_miss = ParametricCurve(
        lambda t: (0.5 + 0.0 * t, 0.5 + 0.0 * t, 1.000000005e-8 + 0.0 * t),
        (-1.0, 1.0),
    )
    with pytest.raises(InvalidGeometry, match="intersection"):
        intersect_curve_surface(near_miss, surface, (0.0, 0.5, 0.5))
    assert intersect_curve_surface(
        near_miss, surface, (0.0, 0.5, 0.5), tolerance=1.1e-8
    ).residual_norm == pytest.approx(1.000000005e-8)


def test_degenerate_nonfinite_empty_budget_and_connectivity_limits_fail_closed() -> None:
    degenerate = TriangleMesh(
        np.array(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0))),
        np.array(((0, 1, 2),)),
    )
    assert mesh_quality(degenerate).degenerate_triangle_ids.tolist() == [0]
    mixed = TriangleMesh(
        np.array(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (2.0, 0.0, 0.0))),
        np.array(((0, 1, 2), (0, 1, 3))),
    )
    mixed_report = mesh_quality(mixed)
    assert mixed_report.degenerate_triangle_ids.tolist() == [1]
    assert mixed_report.areas[0] == pytest.approx(0.5)
    nearly_degenerate = TriangleMesh(
        np.array(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1e-12, 0.0))),
        np.array(((0, 1, 2),)),
    )
    assert mesh_quality(nearly_degenerate, area_tolerance=1e-10).degenerate_triangle_ids.tolist() == [0]
    empty = TriangleMesh(np.empty((0, 3)), np.empty((0, 3), dtype=np.int64))
    assert uniform_refine(empty).triangles.shape == (0, 3)
    with pytest.raises(ResourceLimitExceeded):
        mesh_parametric_patch(_plane(), u_samples=2, v_samples=2, max_vertices=3)
    with pytest.raises(ResourceLimitExceeded):
        uniform_refine(mesh_parametric_patch(_plane(), u_samples=2, v_samples=2), max_triangles=3)
    with pytest.raises(InvalidGeometry):
        sampled_hausdorff(np.array(((np.nan, 0.0, 0.0),)), np.zeros((1, 3)))
    with pytest.raises(InvalidGeometry, match="matching connectivity"):
        area_distortion(
            mesh_parametric_patch(_plane(), u_samples=2, v_samples=2),
            mesh_parametric_patch(_plane(), u_samples=3, v_samples=2),
        )
    with pytest.raises(InvalidGeometry, match="degenerate baseline"):
        area_distortion(degenerate, degenerate)
    centimetre_mesh = TriangleMesh(
        mesh_parametric_patch(_plane(), u_samples=2, v_samples=2).vertices,
        mesh_parametric_patch(_plane(), u_samples=2, v_samples=2).triangles,
        "cm",
    )
    assert uniform_refine(centimetre_mesh).length_unit == "cm"
