import numpy as np
import pytest

from NURBSCoreEngine import GeometryValidationError, RANSACPrimitiveClassifier
from conftest import cylinder_cloud, plane_grid


def test_sign_invariant_topology_and_invalids():
    curvatures = {"Principal_Max": np.array([0, 0.5, 0, 0.5, np.nan, 0]), "Principal_Min": np.array([0, 0, -0.5, -0.2, 0, 0]), "Valid": np.array([True, True, True, True, True, False])}
    labels = RANSACPrimitiveClassifier().classify_local_topology(curvatures)
    np.testing.assert_array_equal(labels, [0, 1, 1, 2, 2, 2])


@pytest.mark.parametrize("count", [0, 1, 2])
def test_short_plane_fit_preserves_mask_length(count):
    equation, mask = RANSACPrimitiveClassifier(random_state=0).fit_plane_ransac(np.zeros((count, 3)), np.zeros((count, 3)))
    assert equation.shape == (4,)
    assert mask.shape == (count,)
    assert not mask.any()


@pytest.mark.parametrize("count", [0, 1])
def test_short_cylinder_fit_preserves_mask_length(count):
    geometry, mask = RANSACPrimitiveClassifier(random_state=0).fit_cylinder_ransac(np.zeros((count, 3)), np.zeros((count, 3)), 0.5)
    assert geometry is None
    assert mask.shape == (count,)


def test_seeded_plane_refinement_rejects_outliers_and_global_rng_is_untouched():
    rng = np.random.default_rng(10)
    plane = plane_grid()
    plane[:, 2] = 3.0 + rng.normal(0, 0.0002, len(plane))
    points = np.r_[plane, [[4, 5, 8], [3, 3, 9]]]
    normals = np.tile([0., 0., 7.], (len(points), 1))
    np.random.seed(123)
    before = np.random.get_state()
    classifier = RANSACPrimitiveClassifier(random_state=42, spatial_tol=0.003)
    eq, mask = classifier.fit_plane_ransac(points, normals)
    after = np.random.get_state()
    for x, y in zip(before, after, strict=True):
        np.testing.assert_equal(x, y)
    assert mask.sum() == len(plane)
    np.testing.assert_allclose(eq, [0, 0, 1, -3], atol=1e-4)
    eq2, mask2 = RANSACPrimitiveClassifier(random_state=42, spatial_tol=0.003).fit_plane_ransac(points, normals)
    np.testing.assert_array_equal(mask, mask2)
    np.testing.assert_array_equal(eq, eq2)


@pytest.mark.parametrize("radius", [0.2, 3., 40.])
@pytest.mark.parametrize("normal_sign", [-1., 1.])
def test_rotated_cylinder_and_normal_projection(radius, normal_sign):
    origin = np.array([4., -9., 7.])
    points, normals, axis = cylinder_cloud(radius, origin=origin, axis=(1., 2., 3.))
    normals *= normal_sign * 4.0
    geometry, mask = RANSACPrimitiveClassifier(random_state=14, spatial_tol=1e-5).fit_cylinder_ransac(points, normals, 1 / radius)
    assert geometry is not None
    assert mask.all()
    fit_origin, fit_axis, fit_radius = geometry
    np.testing.assert_allclose(fit_radius, radius, rtol=1e-10)
    np.testing.assert_allclose(abs(fit_axis @ axis), 1, atol=1e-10)
    delta = fit_origin - origin
    np.testing.assert_allclose(delta - (delta @ axis) * axis, 0, atol=1e-9)


def test_cylinder_handles_independently_flipped_normals():
    points, normals, _ = cylinder_cloud()
    normals[::2] *= -1
    geometry, mask = RANSACPrimitiveClassifier(random_state=5).fit_cylinder_ransac(points, normals)
    assert geometry is not None
    assert mask.all()


def test_multiple_planes_and_mixed_radii_no_reused_support():
    p1, n1, _ = cylinder_cloud(2., origin=(0, 0, 0))
    p2, n2, _ = cylinder_cloud(4., origin=(15, 0, 0))
    p3, p4 = plane_grid(z=-10), plane_grid(z=12)
    points = np.r_[p1, p2, p3, p4]
    normals = np.r_[n1, -n2, np.tile([0, 0, 1], (len(p3) + len(p4), 1))]
    maximum = np.r_[np.zeros(len(p1)), np.full(len(p2), .25), np.zeros(len(p3) + len(p4))]
    minimum = np.r_[np.full(len(p1), -.5), np.zeros(len(p2) + len(p3) + len(p4))]
    result = RANSACPrimitiveClassifier(random_state=42, spatial_tol=1e-4).segment(points, normals, {"Principal_Max": maximum, "Principal_Min": minimum})
    assert len(result.primitives) == 4
    assert len(result.unassigned_indices) == 0
    indices = np.concatenate([p["point_indices"] for p in result.primitives])
    assert len(np.unique(indices)) == len(points)
    radii = sorted(p["geometry"]["radius"] for p in result.primitives if p["type"] == "cylinder_fillet")
    np.testing.assert_allclose(radii, [2, 4], atol=1e-9)


def test_bad_curvature_shape_and_missing_fields():
    points = plane_grid()
    classifier = RANSACPrimitiveClassifier()
    with pytest.raises(GeometryValidationError):
        classifier.segment(points, np.ones_like(points), {"Principal_Max": [0], "Principal_Min": [0]})
    with pytest.raises(GeometryValidationError):
        classifier.classify_local_topology({"Principal_Max": [0]})


def test_zero_normals_cannot_be_inliers():
    points = plane_grid()
    curvatures = {"Principal_Max": np.zeros(len(points)), "Principal_Min": np.zeros(len(points))}
    result = RANSACPrimitiveClassifier().segment(points, np.zeros_like(points), curvatures)
    assert not result.primitives
    assert len(result.unassigned_indices) == len(points)


@pytest.mark.parametrize("kwargs", [{"spatial_tol": 0}, {"normal_tol_deg": 180}, {"max_primitives": 0}, {"min_plane_inliers": 2}, {"plane_iterations": 0}, {"planar_threshold": np.nan}])
def test_ransac_config_validation(kwargs):
    with pytest.raises(GeometryValidationError):
        RANSACPrimitiveClassifier(**kwargs)
