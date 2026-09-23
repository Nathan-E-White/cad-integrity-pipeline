"""Public caller qualification against analytic geometry and the retained reference."""
import gc
import importlib.util
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pytest

from cad_integrity import _native
from cad_integrity.nurbs import EvaluationLimits, evaluate_surface

FIELDS = ("points", "normals", "principal_max", "principal_min", "mean", "gaussian", "valid_mask")


@pytest.fixture(scope="module")
def reference():
    path = Path(__file__).resolve().parents[1] / "integration/nurbs_core_professionalized/NURBSCoreEngine.py"
    spec = importlib.util.spec_from_file_location("nurbs_qualification_reference", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.NURBSCoreEngine.evaluate_surface


def plane():
    cp = np.array([[[0., 0, 0], [0, 4, 0]], [[3, 0, 0], [3, 4, 0]]])
    return [1, 1, [0, 0, 1, 1], [0, 0, 1, 1], cp, [0, .2, 1], [1, .7, 0, .2]]


def compare(a, b):
    for field in FIELDS:
        np.testing.assert_allclose(getattr(a, field), getattr(b, field), rtol=2e-9, atol=2e-10)


@pytest.mark.parametrize("degree", range(1, 6))
@pytest.mark.parametrize("weight_scale", [1e-100, 1., 1e100])
def test_rational_and_repeated_knot_parity(reference, degree, weight_scale):
    rng = np.random.default_rng(100 + degree)
    knots = np.r_[np.zeros(degree+1), .4, .4, np.ones(degree+1)]
    n = len(knots) - degree - 1
    cp = rng.normal(size=(n, n, 4))
    cp[..., 3] = rng.uniform(.5, 2, size=(n, n))
    cp[..., :3] *= cp[..., 3, None]
    cp *= weight_scale
    args = (degree, degree, knots, knots, cp, [0, .4, .9, 1], [1, .4, 0])
    compare(evaluate_surface(*args), reference(*args))


@pytest.mark.parametrize("scale,shift", [(1e-9, 0), (1., 0), (4., 1e10)])
def test_plane_orientation_scale_translation(scale, shift):
    args = plane()
    args[4] = args[4] * scale + shift
    r = evaluate_surface(*args)
    assert r.points.shape == (3, 4, 3)
    assert r.valid_mask.all()
    np.testing.assert_allclose(r.normals, np.broadcast_to([0, 0, 1], r.normals.shape))
    np.testing.assert_allclose(r.mean, 0, atol=1e-15)
    expected = np.zeros((3, 4, 3))
    expected[..., 0] = 3 * np.array(args[5])[:, None]
    expected[..., 1] = 4 * np.array(args[6])[None, :]
    np.testing.assert_allclose(r.points, expected * scale + shift)
    args[4] = args[4][:, ::-1]
    r = evaluate_surface(*args)
    np.testing.assert_allclose(r.normals[..., 2], -1)


def test_rational_cylinder():
    cp = np.array([[[2., 0, 0], [2, 0, 3]], [[2, 2, 0], [2, 2, 3]], [[0, 2, 0], [0, 2, 3]]])
    w = np.broadcast_to([[1.], [np.sqrt(.5)], [1.]], (3, 2))
    cp = np.concatenate((cp * w[..., None], w[..., None]), axis=2)
    r = evaluate_surface(2, 1, [0, 0, 0, 1, 1, 1], [0, 0, 1, 1], cp,
                         np.linspace(0, 1, 15), [0, .5, 1])
    np.testing.assert_allclose(np.linalg.norm(r.points[..., :2], axis=2), 2)
    np.testing.assert_allclose(r.principal_max, 0, atol=1e-14)
    np.testing.assert_allclose(r.principal_min, -.5, atol=1e-14)
    np.testing.assert_allclose(r.mean, -.25, atol=1e-14)
    np.testing.assert_allclose(r.gaussian, 0, atol=1e-14)


def test_quadratic_paraboloid_geometry():
    coefficients = np.array([0., 0, 1])
    cp = np.array([
        [[i / 2, j / 2, coefficients[i] + coefficients[j]] for j in range(3)]
        for i in range(3)
    ])
    knots = [0, 0, 0, 1, 1, 1]
    u = np.array([0., .25, 1])
    v = np.array([.1, .5, 1])

    result = evaluate_surface(2, 2, knots, knots, cp, u, v)

    uu, vv = np.meshgrid(u, v, indexing="ij")
    expected_points = np.stack((uu, vv, uu**2 + vv**2), axis=-1)
    normal_scale = np.sqrt(1 + 4 * uu**2 + 4 * vv**2)
    expected_normals = np.stack((-2 * uu, -2 * vv, np.ones_like(uu)), axis=-1)
    expected_normals /= normal_scale[..., None]
    expected_mean = (2 + 4 * uu**2 + 4 * vv**2) / normal_scale**3
    expected_gaussian = 4 / normal_scale**4
    curvature_delta = np.sqrt(expected_mean**2 - expected_gaussian)

    np.testing.assert_allclose(result.points, expected_points, atol=2e-15)
    np.testing.assert_allclose(result.normals, expected_normals, atol=2e-15)
    np.testing.assert_allclose(result.mean, expected_mean, atol=2e-14)
    np.testing.assert_allclose(result.gaussian, expected_gaussian, atol=2e-14)
    np.testing.assert_allclose(result.principal_max, expected_mean + curvature_delta, atol=2e-14)
    np.testing.assert_allclose(result.principal_min, expected_mean - curvature_delta, atol=2e-14)


def test_repeated_upper_endpoint(reference):
    knots = [0, 1, 2, 3, 3, 3, 4, 5]
    cp = np.array([[[i, j, 0] for j in range(5)] for i in range(5)])
    args = (2, 2, knots, knots, cp, [2, 3, 2.5], [3, 2.5])
    compare(evaluate_surface(*args), reference(*args))


def test_singular_empty_and_degree_zero(reference):
    args = plane()
    args[4][:] = 0
    r = evaluate_surface(*args)
    assert not r.valid_mask.any()
    assert np.isnan(r.mean).all()
    assert (r.normals == 0).all()
    with pytest.raises(ArithmeticError, match="singular_surface"):
        evaluate_surface(*args, singular_policy="raise")
    args[5] = []
    assert evaluate_surface(*args).points.shape == (0, 4, 3)
    args = (0, 0, [0, 1], [0, 1], [[[1, 2, 3]]], [0, 1], [0, .5, 1])
    compare(evaluate_surface(*args), reference(*args))


@pytest.mark.parametrize("slot,value", [(0, True), (0, -1), (0, 2**32),
    (2, [0, 1, 0, 1]), (2, [0, 0, 0, 1, 1]), (5, [-.1]), (5, [np.nan]),
    (5, [[.1]]), (4, [[[1, 2, 3]]]), (4, np.ones((2, 2, 3), dtype=complex)),
    (4, object())])
def test_invalid_input(slot, value):
    args = plane()
    args[slot] = value
    with pytest.raises(ValueError):
        evaluate_surface(*args)


def test_bad_weights_and_policy():
    args = plane()
    args[4] = np.concatenate((args[4], np.zeros((2, 2, 1))), axis=2)
    with pytest.raises(ValueError, match="nonpositive_weight"):
        evaluate_surface(*args)
    for tolerance in [0, 1, np.nan, np.inf, "bad", object()]:
        with pytest.raises(ValueError):
            evaluate_surface(*plane(), regularity_tolerance=tolerance)
    with pytest.raises(ValueError):
        evaluate_surface(*plane(), singular_policy="guess")


@pytest.mark.parametrize("field", EvaluationLimits.__dataclass_fields__)
def test_budget_refusal(field):
    with pytest.raises(_native.BudgetExceeded):
        evaluate_surface(*plane(), limits=EvaluationLimits(**{field: 0}))
    with pytest.raises(ValueError):
        EvaluationLimits(**{field: -1})


def test_owned_outputs_and_concurrent_calls():
    args = plane()
    original = args[4].copy()
    r = evaluate_surface(*args)
    args[4][:] = 77
    gc.collect()
    np.testing.assert_array_equal(r.points[0, 0], [0, 4, 0])
    for name in FIELDS:
        a = getattr(r, name)
        assert a.flags.owndata and a.flags.c_contiguous and a.flags.writeable
    r.points[:] = 99
    args[4] = original
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: evaluate_surface(*args), range(12)))
    for result in results:
        np.testing.assert_array_equal(result.points[0, 0], [0, 4, 0])


def test_private_binding_strict_layout():
    args = plane()
    args[4] = np.concatenate((args[4], np.ones((2, 2, 1))), axis=2)
    arrays = [np.ascontiguousarray(a, dtype=float) for a in args[2:]]
    def call(values):
        return _native.evaluate_nurbs(1, 1, *values, 1e-10, False,
                                     100000, 100000, 100000, 100000)
    for index in range(5):
        bad = arrays.copy()
        bad[index] = bad[index].astype(np.float32)
        with pytest.raises(ValueError, match="float64"):
            call(bad)
    bad = arrays.copy()
    bad[-1] = bad[-1][::-1]
    with pytest.raises(ValueError):
        call(bad)
    bad = arrays.copy()
    bad[-1] = bad[-1][:, None]
    with pytest.raises(ValueError):
        call(bad)


def test_exact_output_budget_boundary():
    args = plane()
    size = 81 * len(args[5]) * len(args[6])
    with pytest.raises(_native.BudgetExceeded):
        evaluate_surface(*args, limits=EvaluationLimits(max_output_bytes=size - 1))
    assert evaluate_surface(*args, limits=EvaluationLimits(max_output_bytes=size)).valid_mask.all()


def test_scalar_parameter_and_nonfinite_control_refusal():
    args = plane()
    args[5] = .5
    with pytest.raises(ValueError):
        evaluate_surface(*args)
    args = plane()
    args[4][0, 0, 0] = np.inf
    with pytest.raises(ValueError):
        evaluate_surface(*args)


def test_checked_budget_arithmetic_before_copy():
    args = plane()
    args[0] = args[1] = 2**31 - 1
    with pytest.raises(OverflowError):
        evaluate_surface(*args)
