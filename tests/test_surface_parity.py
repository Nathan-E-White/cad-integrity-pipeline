"""Differential qualification against the retained integration reference.

This file needs the repository; installed-package qualification uses
 test_native_surface.py without importing the integration tree.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from cad_integrity.models import PolyhedralBRep
from cad_integrity.surface import ChartPolicy, prepare_surface


@pytest.fixture(scope="module")
def reference():
    path = Path(__file__).resolve().parents[1] / "integration/mesh_healing_extension/mesh_healing_engine.py"
    spec = importlib.util.spec_from_file_location("surface_reference", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("vertices", [
    [[0,0,0],[.2,.2,0],[1,0,0],[0,1,0]],
    [[0,0,0],[1,0,0],[1,1,.1],[0,1,0]],
    [[0,0,0],[2,0,0],[2,1,0],[1,.5,0],[0,1,0]],
    [[0,0,0],[1,0,0],[1.5,1,.1],[.5,1.5,0],[-.5,1,0]],
])
@pytest.mark.parametrize("reverse", [False, True])
def test_projected_triangulation_operator_and_chart_parity(reference, vertices, reverse):
    vertices = np.asarray(vertices, dtype=float)
    face = list(range(len(vertices)))
    if reverse:
        face = [face[0], *face[:0:-1]]
    engine = reference.MeshHealingEngine(vertices, [face])
    surface = prepare_surface(PolyhedralBRep.from_polygons(vertices, [face]))
    triangles, parents = engine.triangulated_faces()
    np.testing.assert_array_equal(surface.triangles, triangles)
    np.testing.assert_array_equal(surface.triangle_faces, parents)
    np.testing.assert_allclose(surface.assemble().stiffness.toarray(),
                               engine.compute_cotangent_laplacian().toarray(), rtol=1e-12, atol=1e-13)
    coordinates = {i:p[:2] for i,p in enumerate(vertices)}
    orientation = -1 if reverse else 1
    expected = engine.validate_uv(coordinates, orientation=orientation)
    got = surface.qualify_chart(coordinates, policy=ChartPolicy(orientation)).quality
    assert got.locally_valid == expected.locally_valid
    np.testing.assert_allclose(got.maximum_conformal_distortion, expected.maximum_conformal_distortion, rtol=1e-12)
    np.testing.assert_allclose(got.minimum_signed_double_area, expected.minimum_signed_double_area, rtol=1e-12)


@pytest.mark.parametrize("scale", [1e-200, 1e-9, 1., 1e9, 1e155])
def test_signed_cotangents_and_extreme_scale_parity(reference, scale):
    vertices = np.array([[0,0,0],[2,0,0],[.3,.1,0]]) * scale
    engine = reference.MeshHealingEngine(vertices, [[0,1,2]])
    surface = prepare_surface(PolyhedralBRep.from_polygons(vertices, [[0,1,2]]))
    matrix = surface.assemble().stiffness.toarray()
    np.testing.assert_allclose(matrix, engine.compute_cotangent_laplacian().toarray(), rtol=1e-12, atol=1e-13)
    assert matrix[0,1] > 0  # Negative cotangent retained in W, L off-diagonal = -W.
    np.testing.assert_allclose(matrix, matrix.T, atol=1e-14)
    np.testing.assert_allclose(matrix @ np.ones(3), 0, atol=1e-14)
    assert np.linalg.eigvalsh(matrix).min() >= -1e-12


def test_renumbered_warped_ngon_preserves_facets(reference):
    vertices = np.array([[0,0,0],[1,0,0],[1.5,1,.1],[.5,1.5,0],[-.5,1,0]], dtype=float)
    old = prepare_surface(PolyhedralBRep.from_polygons(vertices, [[0,1,2,3,4]]))
    perm = np.array([3,0,4,1,2])
    inverse = np.argsort(perm)
    new = prepare_surface(PolyhedralBRep.from_polygons(vertices[perm], [inverse.tolist()]))
    assert {frozenset(t) for t in old.triangles} == {frozenset(perm[t]) for t in new.triangles}


def test_affine_grid_confidence_and_soft_updates_match_reference(reference):
    from cad_integrity.surface import SoftConstraint
    n = 6
    vertices = np.array([[x,y,0.] for y in range(n) for x in range(n)])
    boundary = {y*n+x: vertices[y*n+x,:2].copy() for y in range(n) for x in range(n)
                if x in (0,n-1) or y in (0,n-1)}
    inside = sorted(set(range(n*n))-set(boundary))
    vertices[inside,:2] += np.random.default_rng(1729).uniform(-.2,.2,(len(inside),2))
    faces = [[y*n+x,y*n+x+1,(y+1)*n+x+1,(y+1)*n+x] for y in range(n-1) for x in range(n-1)]
    ref = reference.MeshHealingEngine(vertices, faces)
    surface = prepare_surface(PolyhedralBRep.from_polygons(vertices, faces))
    confidence = {0:.3,2:0.}
    got = surface.prepare_harmonic_system(inside,list(boundary),face_confidence=confidence)
    expected = ref.prepare_harmonic_system(inside,list(boundary),face_confidence=confidence)
    for targets in ({}, {inside[0]:(1.1,1.1)}, {inside[0]:(1.2,1.1)}, {}):
        uv = got.solve(boundary,soft_constraints={v:SoftConstraint(t,.4) for v,t in targets.items()})
        oracle = expected.solve(boundary,soft_constraints={v:reference.SoftConstraint(t,.4) for v,t in targets.items()})
        np.testing.assert_allclose(list(uv.values()),list(oracle.values()),rtol=1e-12,atol=1e-12)
        assert got.factorization_count == expected.factorization_count
        assert got.low_rank_update_count == expected.low_rank_update_count
