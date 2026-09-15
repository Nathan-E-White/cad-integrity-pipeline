import json
import subprocess
import sys

import numpy as np
import pytest

from cad_integrity.cli import main
from cad_integrity.errors import InvalidGeometry
from cad_integrity.metrics import area_distortion, mesh_quality, sampled_hausdorff
from cad_integrity.models import TriangleMesh
from cad_integrity.numerics import (
    ParametricCurve, ParametricSurface, intersect_curve_surface, mesh_parametric_patch, uniform_refine,
)
from cad_integrity.serialization import dumps
from cad_integrity.topology import analyze_mesh


def test_equilateral_quality():
    mesh = TriangleMesh(np.array(((0,0,0),(1,0,0),(.5,np.sqrt(3)/2,0))),
                        np.array(((0,1,2),), dtype=np.int64))
    q = mesh_quality(mesh)
    assert q.aspect_ratios[0] == pytest.approx(1)
    assert q.mean_ratios[0] == pytest.approx(1)
    assert q.skewness[0] == pytest.approx(0, abs=1e-14)


def test_scalene_triangle_angle_regression():
    mesh = TriangleMesh(np.array(((0,0,0),(3,0,0),(0,4,0)),dtype=float),
                        np.array(((0,1,2),),dtype=np.int64))
    q = mesh_quality(mesh)
    assert q.areas[0] == pytest.approx(6)
    angles = np.array((np.pi/2, np.arctan(4/3), np.arctan(3/4)))
    expected = max((angles.max()-np.pi/3)/(np.pi-np.pi/3), (np.pi/3-angles.min())/(np.pi/3))
    assert q.skewness[0] == pytest.approx(expected)


def test_degenerate_triangle_is_not_given_fake_area():
    mesh = TriangleMesh(np.array(((0,0,0),(1,0,0),(2,0,0)),dtype=float),
                        np.array(((0,1,2),),dtype=np.int64))
    q = mesh_quality(mesh)
    assert q.areas[0] == 0
    assert np.isinf(q.aspect_ratios[0])
    assert q.degenerate_triangle_ids.tolist() == [0]
    parsed = json.loads(dumps(q))
    assert parsed["aspect_ratios"] == [None]
    assert "Infinity" not in dumps(q)


def test_empty_quality():
    mesh = TriangleMesh(np.empty((0,3)),np.empty((0,3),dtype=np.int64))
    assert mesh_quality(mesh).worst_skewness is None
    assert uniform_refine(mesh).triangles.shape == (0,3)


def test_hausdorff_compares_both_directions():
    a = np.array(((0,0,0),(1,0,0)),dtype=float)
    b = np.array(((0,0,0),(1,0,0),(4,0,0)),dtype=float)
    h = sampled_hausdorff(a,b)
    assert h.a_to_b == 0
    assert h.b_to_a == 3
    assert h.symmetric == 3
    assert h.scope == "finite_point_sets_only"
    with pytest.raises(InvalidGeometry):
        sampled_hausdorff(np.empty((0,3)), b)


def test_parametric_constants_broadcast():
    curve = ParametricCurve(lambda t: (t,0.0,0.0), (0,1))
    surface = ParametricSurface(lambda u,v: (u,v,0.0), (0,1),(0,1))
    assert curve.evaluate(np.linspace(0,1,5)).shape == (5,3)
    assert curve.evaluate(0.5).shape == (3,)
    assert surface.evaluate(np.linspace(0,1,5),0.5).shape == (5,3)
    mesh = mesh_parametric_patch(surface,u_samples=5,v_samples=4)
    assert mesh.vertices.shape == (20,3)
    assert mesh.triangles.shape == (24,3)
    assert mesh_quality(mesh).areas.sum() == pytest.approx(1)


def test_bounded_local_intersection():
    curve = ParametricCurve(lambda t: (.5+0*t,.5+0*t,t),(-1,1))
    surface = ParametricSurface(lambda u,v:(u,v,0.0),(0,1),(0,1))
    root = intersect_curve_surface(curve,surface,(.2,.3,.4))
    assert root.point == pytest.approx((.5,.5,0),abs=1e-8)
    assert root.residual_norm < 1e-8
    with pytest.raises(ValueError):
        intersect_curve_surface(curve,surface,(2,.5,.5))


def test_no_intersection_reports_failure():
    curve = ParametricCurve(lambda t:(t,0.0,2.0),(0,1))
    surface = ParametricSurface(lambda u,v:(u,v,0.0),(0,1),(0,1))
    with pytest.raises(InvalidGeometry,match="intersection"):
        intersect_curve_surface(curve,surface,(.5,.5,.5))


def test_uniform_refinement_conforming_and_area_preserving():
    surface = ParametricSurface(lambda u,v:(u,v,0),(0,1),(0,1))
    original = mesh_parametric_patch(surface,u_samples=3,v_samples=3)
    refined = uniform_refine(original)
    assert len(refined.triangles) == 4*len(original.triangles)
    assert mesh_quality(refined).areas.sum() == pytest.approx(mesh_quality(original).areas.sum())
    assert not analyze_mesh(refined).nonmanifold_vertex_ids
    assert analyze_mesh(refined).homology.betti_numbers == (1,0,0)


def test_area_ratios_not_stress():
    surface = ParametricSurface(lambda u,v:(u,v,0),(0,1),(0,1))
    initial = mesh_parametric_patch(surface,u_samples=2,v_samples=2)
    deformed = TriangleMesh(initial.vertices*2,initial.triangles)
    np.testing.assert_allclose(area_distortion(initial,deformed),4)


def test_core_import_has_no_network_or_plotting_imports(tmp_path):
    code = "import cad_integrity,sys; assert 'OCP' not in sys.modules; assert 'gradio_client' not in sys.modules; assert 'plotly' not in sys.modules"
    completed = subprocess.run([sys.executable,"-c",code],cwd=tmp_path,capture_output=True,text=True,check=True)
    assert completed.stdout == ""
    assert list(tmp_path.iterdir()) == []


def test_cli_demo_and_existing_report_protection(tmp_path):
    report = tmp_path/"report.json"
    assert main(["demo","--report",str(report)]) == 0
    original = report.read_bytes()
    assert json.loads(original)["decision"] == "topology_checks_passed"
    assert main(["demo","--report",str(report)]) == 2
    assert report.read_bytes() == original


def test_visualization_uses_edge_endpoints():
    pytest.importorskip("plotly")
    from cad_integrity.fixtures import disk
    from cad_integrity.topology import BRepHomologyStitchAnalyzer
    from cad_integrity.visualization import polygonal_audit_figure
    b = disk()
    figure = polygonal_audit_figure(b,BRepHomologyStitchAnalyzer(b).evaluate_stitch_integrity(),title="test")
    assert len(figure.data) == 2
    assert len(figure.data[1].x) == 4*3  # Two endpoints and a None separator per edge.
    assert figure.data[1].name == "Boundary edges (4)"
