import numpy as np
import pytest

import STLReader as reader_module
from STLReader import PointCloudGeometryEstimator
from conftest import cylinder_cloud, plane_grid


@pytest.mark.parametrize("scale", [1e-6, 1., 1e5])
def test_plane_curvature_and_normal(scale):
    points = plane_grid() * scale
    result = PointCloudGeometryEstimator(k_neighbors=20, batch_size=7).estimate(points)
    assert result.valid_mask.all()
    np.testing.assert_allclose(result.principal_max, 0., atol=1e-11)
    np.testing.assert_allclose(result.principal_min, 0., atol=1e-11)
    np.testing.assert_allclose(result.normals, np.tile([0, 0, 1], (len(points), 1)), atol=1e-12)
    assert (result.neighbor_count == 20).all()


def test_normal_reversal_also_reverses_curvature_order():
    points, normal, _ = cylinder_cloud(radius=2, na=40, nz=25)
    estimator = PointCloudGeometryEstimator(k_neighbors=25)
    outward = estimator.estimate(points, reference_normals=normal)
    inward = estimator.estimate(points, reference_normals=-normal)
    assert outward.valid_mask.mean() > 0.95
    np.testing.assert_allclose(outward.normals, -inward.normals, atol=1e-12)
    np.testing.assert_allclose(outward.principal_max, -inward.principal_min, atol=1e-12)
    np.testing.assert_allclose(outward.principal_min, -inward.principal_max, atol=1e-12)
    assert abs(np.nanmedian(outward.principal_min) + 0.5) < 0.03
    assert abs(np.nanmedian(outward.principal_max)) < 0.01


def test_sphere_and_scale_invariance():
    count, radius = 700, 3.0
    j = np.arange(count)
    z = 1 - 2 * (j + 0.5) / count
    theta = np.pi * (3 - np.sqrt(5)) * j
    normal = np.c_[np.sqrt(1 - z*z) * np.cos(theta), np.sqrt(1 - z*z) * np.sin(theta), z]
    estimator = PointCloudGeometryEstimator(k_neighbors=20)
    original = estimator.estimate(radius * normal, reference_normals=normal)
    scaled = estimator.estimate(radius * normal * 0.001, reference_normals=normal)
    assert original.valid_mask.all()
    np.testing.assert_allclose(np.median(original.principal_min), -1 / radius, rtol=0.05)
    np.testing.assert_allclose(np.median(original.principal_max), -1 / radius, rtol=0.05)
    np.testing.assert_allclose(scaled.principal_max * 0.001, original.principal_max, atol=1e-10)


@pytest.mark.parametrize("points", [np.empty((0, 3)), np.zeros((2, 3)), np.zeros((12, 3)), np.c_[np.arange(15), np.zeros((15, 2))]])
def test_degenerate_clouds_not_reported_as_planes(points):
    result = PointCloudGeometryEstimator().estimate(points)
    assert result.normals.shape == points.shape
    assert not result.valid_mask.any()
    assert np.isnan(result.principal_max).all()


def test_radius_limit_and_fit_error_gate():
    points = plane_grid()
    result = PointCloudGeometryEstimator(max_radius=0.01).estimate(points)
    assert not result.valid_mask.any()
    noisy = points.copy()
    noisy[:, 2] = np.random.default_rng(42).normal(0, 0.02, len(noisy))
    result = PointCloudGeometryEstimator(max_fit_rmse=1e-8).estimate(noisy)
    assert not result.valid_mask.any()


def test_query_batches_are_bounded(monkeypatch):
    real_tree = reader_module.cKDTree
    batches = []
    class TreeSpy:
        def __init__(self, points):
            self.tree = real_tree(points)
        def query(self, points, **kwargs):
            batches.append(len(points))
            return self.tree.query(points, **kwargs)
    monkeypatch.setattr(reader_module, "cKDTree", TreeSpy)
    PointCloudGeometryEstimator(batch_size=17).estimate(plane_grid())
    assert max(batches) == 17
    assert sum(batches) == 144


def test_viewpoint_and_conflicting_orientation_inputs():
    points = plane_grid()
    estimator = PointCloudGeometryEstimator()
    normals, curvature = estimator.estimate_features(points, viewpoint=[0, 0, -10])
    np.testing.assert_allclose(normals[:, 2], -1)
    assert curvature["Valid"].all()
    with pytest.raises(ValueError):
        estimator.estimate(points, reference_normals=np.ones_like(points), viewpoint=[0, 0, 10])


@pytest.mark.parametrize("kwargs", [{"k_neighbors": 5}, {"workers": 0}, {"batch_size": -1}, {"max_condition": 1}, {"max_radius": -1}, {"orientation": "guess"}])
def test_estimator_config_errors(kwargs):
    with pytest.raises(ValueError):
        PointCloudGeometryEstimator(**kwargs)


@pytest.mark.parametrize("points", [np.zeros((3, 2)), [[0, 0, np.nan]]])
def test_invalid_point_arrays(points):
    with pytest.raises(ValueError):
        PointCloudGeometryEstimator().estimate(points)
