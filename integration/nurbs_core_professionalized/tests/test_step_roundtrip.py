import copy

import numpy as np
import pytest

pytest.importorskip("OCP")
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_Controller, STEPControl_Reader
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer

from NURBSCoreEngine import CADGeometryCardEngine, GeometryValidationError, STEPGeometryExportEngine
from conftest import cylinder_cloud

pytestmark = pytest.mark.step


def read_shape(path):
    reader = STEPControl_Reader()
    assert reader.ReadFile(str(path)) == IFSelect_RetDone
    assert reader.TransferRoots() > 0
    result = reader.OneShape()
    assert not result.IsNull()
    assert BRepCheck_Analyzer(result).IsValid()
    return result


def count_shapes(shape, kind):
    explorer = TopExp_Explorer(shape, kind)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def area(shape):
    properties = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape, properties)
    return properties.Mass()


@pytest.mark.parametrize("unit,factor", [("mm", 1.), ("cm", 10.), ("m", 1000.), ("in", 25.4)])
def test_plane_roundtrip_and_unit_scale(tmp_path, plane_card, unit, factor):
    plane_card["length_unit"] = unit
    path = tmp_path / "plane.step"
    STEPGeometryExportEngine().write(plane_card, path)
    shape = read_shape(path)
    assert count_shapes(shape, TopAbs_FACE) == 1
    assert count_shapes(shape, TopAbs_SOLID) == 0
    assert area(shape) == pytest.approx(factor**2, rel=1e-9)


@pytest.mark.parametrize("schema", ["AP203", "AP214IS", "AP242DIS"])
def test_schema_roundtrip_and_setting_restoration(tmp_path, plane_card, schema):
    STEPControl_Controller.Init_s()
    prior_schema = Interface_Static.CVal_s("write.step.schema")
    prior_units = Interface_Static.CVal_s("write.step.unit")
    exporter = STEPGeometryExportEngine(schema=schema)
    for i in range(2):
        path = tmp_path / f"plane_{i}.step"
        exporter.write(plane_card, path)
        assert count_shapes(read_shape(path), TopAbs_FACE) == 1
    assert Interface_Static.CVal_s("write.step.schema") == prior_schema
    assert Interface_Static.CVal_s("write.step.unit") == prior_units


def test_bounded_cylinder_with_rotation_and_seam(tmp_path):
    points, _, axis = cylinder_cloud(3., origin=(4., 5., 6.), axis=(1., 2., 3.), start=6.1, stop=6.5)
    primitive = {"type": "cylinder_fillet", "geometry": {"origin": [4., 5., 6.], "axis": axis, "radius": 3.}, "point_indices": np.arange(len(points))}
    cards = CADGeometryCardEngine(length_unit="mm").compute_cards([primitive], points)
    path = tmp_path / "cylinder.step"
    STEPGeometryExportEngine().write(cards, path)
    shape = read_shape(path)
    assert count_shapes(shape, TopAbs_FACE) == 1
    assert count_shapes(shape, TopAbs_SOLID) == 0
    assert area(shape) == pytest.approx(3.0 * 0.4 * 4.0, rel=1e-8)


def test_unbounded_legacy_face_is_rejected(plane_card):
    del plane_card["operations"][0]["parameters"]["boundary_vertices"]
    with pytest.raises(GeometryValidationError, match="bounded-geometry"):
        STEPGeometryExportEngine().export(plane_card)


def test_noncoplanar_boundary_is_rejected(plane_card):
    card = copy.deepcopy(plane_card)
    card["operations"][0]["parameters"]["boundary_vertices"][0][2] = 1.0
    with pytest.raises(GeometryValidationError, match="coplanar"):
        STEPGeometryExportEngine().export(card)
