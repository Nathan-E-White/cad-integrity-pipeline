import numpy as np
import pytest
from scipy.interpolate import BSpline

from NURBSCoreEngine import GeometryValidationError, NURBSCoreEngine, SurfaceEvaluationError


@pytest.mark.parametrize("degree", range(6))
@pytest.mark.parametrize("scale,shift", [(1., 0.), (1e-8, 0.), (4., 1e8)])
def test_basis_matches_scipy(degree, scale, shift):
    interior = [0.2, 0.5, 0.7] if degree == 0 else [0.2, 0.5, 0.5, 0.7]
    knots = (np.r_[np.zeros(degree + 1), interior, np.ones(degree + 1)] * scale + shift)
    u = np.r_[0., 0.1, 0.2, 0.4, 0.5, 0.7, 0.9, 1.] * scale + shift
    n = len(knots) - degree - 1
    spans, local = NURBSCoreEngine.basis_derivatives_vectorized(degree, u, knots, 4)
    full = np.zeros((5, len(u), n))
    for i, span in enumerate(spans):
        full[:, i, span - degree:span + 1] = local[:, i]
    scipy_basis = BSpline(knots, np.eye(n), degree)
    for order in range(5):
        expected = scipy_basis(u, nu=order) if order <= degree else np.zeros((len(u), n))
        np.testing.assert_allclose(full[order] * scale**order, expected * scale**order, atol=1e-10, rtol=1e-10)
    np.testing.assert_allclose(full[0].sum(axis=1), 1.0, atol=1e-12)
    assert spans[-1] == n - 1


@pytest.mark.parametrize("bad", [
    dict(p=-1, u=[0.5], knot_vector=[0, 0, 1, 1]),
    dict(p=1, u=[-0.1], knot_vector=[0, 0, 1, 1]),
    dict(p=1, u=[1.1], knot_vector=[0, 0, 1, 1]),
    dict(p=1, u=[np.nan], knot_vector=[0, 0, 1, 1]),
    dict(p=1, u=[0.5], knot_vector=[0, 1, 0, 1]),
    dict(p=1, u=[0.5], knot_vector=[0, 0, 0, 1, 1]),
    dict(p=1, u=[[0.5]], knot_vector=[0, 0, 1, 1]),
    dict(p=1, u=[0.5], knot_vector=[0, 0, 1, 1], max_deriv=-1),
])
def test_invalid_spline_inputs(bad):
    with pytest.raises(GeometryValidationError):
        NURBSCoreEngine.basis_derivatives_vectorized(**bad)


@pytest.mark.parametrize("scale", [1e-9, 1., 1e6])
def test_plane_tensor_grid_scale_and_tiles(scale):
    cp = scale * np.array([[[0, 0, 0], [0, 4, 0]], [[3, 0, 0], [3, 4, 0]]], dtype=float)
    u, v = np.linspace(0, 1, 11), np.linspace(0, 1, 7)
    result = NURBSCoreEngine.evaluate_surface(1, 1, [0, 0, 1, 1], [0, 0, 1, 1], cp, u, v, batch_size=3)
    assert result.points.shape == (11, 7, 3)
    assert result.valid_mask.all()
    np.testing.assert_allclose(result.points[..., 0], np.broadcast_to(3 * scale * u[:, None], (11, 7)), atol=1e-8 * scale)
    np.testing.assert_allclose(result.points[..., 1], np.broadcast_to(4 * scale * v[None, :], (11, 7)), atol=1e-8 * scale)
    np.testing.assert_allclose(result.normals, np.broadcast_to([0., 0., 1.], (11, 7, 3)), atol=1e-12)
    np.testing.assert_allclose(result.principal_max, 0., atol=1e-12)
    other = NURBSCoreEngine.evaluate_surface_geometry(1, 1, [0, 0, 1, 1], [0, 0, 1, 1], cp, u, v)
    np.testing.assert_allclose(other[0], result.points)


@pytest.mark.parametrize("radius", [0.001, 2., 100.])
def test_exact_rational_quarter_cylinder(radius):
    cp = np.array([[[radius, 0, 0], [radius, 0, 3]], [[radius, radius, 0], [radius, radius, 3]], [[0, radius, 0], [0, radius, 3]]], dtype=float)
    weights = np.array([[1., 1.], [np.sqrt(0.5), np.sqrt(0.5)], [1., 1.]])
    homogeneous = NURBSCoreEngine.to_homogeneous(cp, weights)
    result = NURBSCoreEngine.evaluate_surface(2, 1, [0, 0, 0, 1, 1, 1], [0, 0, 1, 1], homogeneous, np.linspace(0, 1, 17), np.linspace(0, 1, 8))
    assert result.valid_mask.all()
    np.testing.assert_allclose(np.linalg.norm(result.points[..., :2], axis=-1), radius, rtol=1e-12)
    np.testing.assert_allclose(result.principal_max, 0., atol=1e-9 / radius)
    np.testing.assert_allclose(result.principal_min, -1 / radius, rtol=1e-10)
    np.testing.assert_allclose(result.normals[..., :2], result.points[..., :2] / radius, atol=1e-10)
    # Uniform rescaling of homogeneous coordinates must not change geometry.
    rescaled = NURBSCoreEngine.evaluate_surface(2, 1, [0, 0, 0, 1, 1, 1], [0, 0, 1, 1], homogeneous * 1e100, np.linspace(0, 1, 17), np.linspace(0, 1, 8))
    np.testing.assert_allclose(rescaled.points, result.points, atol=1e-12 * max(radius, 3))


def test_singular_surface_and_bad_weight():
    cp = np.zeros((2, 2, 3))
    arguments = (1, 1, [0, 0, 1, 1], [0, 0, 1, 1], cp, [0.2, 0.8], [0.5])
    result = NURBSCoreEngine.evaluate_surface(*arguments)
    assert not result.valid_mask.any()
    assert np.isnan(result.principal_max).all()
    np.testing.assert_array_equal(result.normals, 0)
    with pytest.raises(SurfaceEvaluationError):
        NURBSCoreEngine.evaluate_surface(*arguments, singular_policy="raise")
    with pytest.raises(GeometryValidationError):
        NURBSCoreEngine.to_homogeneous(cp, np.zeros((2, 2)))


def test_empty_parameters_and_invalid_control_net():
    cp = np.zeros((2, 2, 3))
    result = NURBSCoreEngine.evaluate_surface(1, 1, [0, 0, 1, 1], [0, 0, 1, 1], cp, [], [0.5])
    assert result.points.shape == (0, 1, 3)
    with pytest.raises(GeometryValidationError):
        NURBSCoreEngine.evaluate_surface(1, 1, [0, 0, 1, 1], [0, 0, 1, 1], cp[:1], [0.5], [0.5])


@pytest.mark.parametrize("a,b,c", [(0.2, 0.4, 0.1), (0.3, -0.2, 0.2)])
def test_exact_polynomial_patch_fundamental_forms(a, b, c):
    d, e, f = 0.15, -0.12, 0.7
    linear = np.array([0., .5, 1.])
    quadratic = np.array([0., 0., 1.])
    cp = np.zeros((3, 3, 3))
    cp[..., 0] = linear[:, None]
    cp[..., 1] = linear[None, :]
    cp[..., 2] = (a * quadratic[:, None] + b * quadratic[None, :]
                  + c * linear[:, None] * linear[None, :]
                  + d * linear[:, None] + e * linear[None, :] + f)
    params = np.linspace(0, 1, 9)
    U, V = np.meshgrid(params, params, indexing="ij")
    result = NURBSCoreEngine.evaluate_surface(
        2, 2, [0, 0, 0, 1, 1, 1], [0, 0, 0, 1, 1, 1], cp, params, params,
    )
    du, dv = 2*a*U + c*V + d, 2*b*V + c*U + e
    determinant = 1 + du**2 + dv**2
    denominator = np.sqrt(determinant)
    E, F, G = 1 + du**2, du*dv, 1 + dv**2
    L, M, N = 2*a/denominator, c/denominator, 2*b/denominator
    K = (L*N - M*M)/determinant
    H = (E*N - 2*F*M + G*L)/(2*determinant)
    np.testing.assert_allclose(result.gaussian, K, atol=1e-12)
    np.testing.assert_allclose(result.mean, H, atol=1e-12)
    np.testing.assert_allclose(result.principal_max + result.principal_min, 2*H, atol=1e-12)
    np.testing.assert_allclose(result.principal_max * result.principal_min, K, atol=1e-12)


def test_translated_plane_does_not_acquire_spurious_curvature():
    cp = np.array([[[0, 0, 0], [0, 4, 0]], [[3, 0, 0], [3, 4, 0]]], dtype=float)
    shift = np.array([1e10, -2e10, 1e10])
    result = NURBSCoreEngine.evaluate_surface(
        1, 1, [0, 0, 1, 1], [0, 0, 1, 1], cp + shift,
        np.linspace(0, 1, 9), np.linspace(0, 1, 7),
    )
    assert result.valid_mask.all()
    np.testing.assert_allclose(result.mean, 0, atol=1e-15)
    np.testing.assert_allclose(result.normals[..., 2], 1, atol=1e-15)
