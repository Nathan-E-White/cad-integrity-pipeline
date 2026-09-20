"""Set CAD_INTEGRITY_SOURCE_DIR to test the actual supplied host modules in place."""
import importlib
import os
from pathlib import Path
import sys
import types
import numpy as np
import pytest
from cad_mesh_inspector.adapters import from_polygonal_report,from_triangle_reports

@pytest.fixture(scope="module")
def host():
    path=os.getenv("CAD_INTEGRITY_SOURCE_DIR")
    if path:
        package=types.ModuleType("cad_integrity");package.__path__=[str(Path(path))];sys.modules.setdefault("cad_integrity",package)
    try:
        return tuple(importlib.import_module(f"cad_integrity.{name}") for name in ("models","metrics","topology"))
    except ImportError:
        pytest.skip("Install host cad_integrity or set CAD_INTEGRITY_SOURCE_DIR for integration tests")


def test_adapter_uses_existing_quality_definition(host):
    models,metrics,_=host
    mesh=models.TriangleMesh([[0,0,0],[3,0,0],[0,1,0]],[[0,1,2]],"mm")
    report=metrics.mesh_quality(mesh)
    payload=from_triangle_reports(mesh,quality=report,mesh_id="m",revision="r",frame_id="world")
    np.testing.assert_allclose(payload.fields[0].values,report.mean_ratios)
    np.testing.assert_allclose(payload.fields[1].values,report.aspect_ratios)


def test_adapter_maps_source_polygon_to_triangles(host):
    models,_,topology=host
    brep=models.PolyhedralBRep.from_polygons([[0,0,0],[1,0,0],[1,1,0],[0,1,0]],[[0,1,2,3]],length_unit="mm")
    report=topology.BRepHomologyStitchAnalyzer(brep).evaluate_stitch_integrity()
    payload=from_polygonal_report(brep,report,mesh_id="m",revision="r",frame_id="world")
    assert payload.triangle_source_faces==[0,0]
    assert len(payload.selections[0].segments)==24
