import builtins
import copy
import json
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from NURBSCoreEngine import (
    CADGeometryCardEngine,
    GeometryValidationError,
    OptionalDependencyError,
    STEPGeometryExportEngine,
    write_text_atomic,
)
from conftest import cylinder_cloud


def test_cards_preserve_precision_and_small_radius():
    points, _, _ = cylinder_cloud(radius=1e-6)
    primitive = {"type": "cylinder_fillet", "geometry": {"origin": [0, 0, 0], "axis": [0, 0, 4], "radius": 1e-6}, "point_indices": np.arange(len(points))}
    engine = CADGeometryCardEngine(precision=4, length_unit="m")
    card = engine.compute_cards([primitive], points)
    op = card["operations"][0]
    assert op["parameters"]["radius"] == 1e-6
    assert op["display_parameters"]["radius"] == 0.0
    np.testing.assert_allclose(op["parameters"]["axis_direction"], [0, 0, 1])
    assert json.loads(engine.to_json(card)) == card
    assert card["length_unit"] == "m"
    assert card["bounds_are_reconstructed_topology"] is False


def test_cylinder_angular_seam_not_full_circle():
    points, _, _ = cylinder_cloud(start=6.1, stop=6.5)
    primitive = {"type": "cylinder_fillet", "geometry": {"origin": [0, 0, 0], "axis": [0, 0, 1], "radius": 3}, "point_indices": np.arange(len(points))}
    op = CADGeometryCardEngine().compute_cards([primitive], points)["operations"][0]
    start, stop = op["parameters"]["angular_bounds"]
    assert stop - start == pytest.approx(0.4)
    assert op["parameters"]["length"] == pytest.approx(4)


def test_plane_bounds_projected_to_fitted_plane():
    points = np.array([[0, 0, 0.001], [1, 0, -0.001], [1, 1, 0.002], [0, 1, 0.]])
    primitive = {"type": "plane", "geometry": {"plane_equation": [0, 0, 2, 0]}, "point_indices": np.arange(4)}
    op = CADGeometryCardEngine().compute_cards([primitive], points)["operations"][0]
    np.testing.assert_allclose(np.array(op["parameters"]["boundary_vertices"])[:, 2], 0)
    assert op["parameters"]["reference_centroid"][2] == 0


@pytest.mark.parametrize("indices", [[-1, 1, 2], [0., 1., 2.], [0, 1, 10], [0, 0, 1], [0, 1]])
def test_bad_point_indices(indices):
    primitive = {"type": "plane", "geometry": {"plane_equation": [0, 0, 1, 0]}, "point_indices": indices}
    with pytest.raises(GeometryValidationError):
        CADGeometryCardEngine().compute_cards([primitive], np.zeros((4, 3)))


def test_collinear_plane_and_unsupported_primitive_rejected():
    points = np.c_[np.arange(4), np.zeros((4, 2))]
    primitive = {"type": "plane", "geometry": {"plane_equation": [0, 0, 1, 0]}, "point_indices": np.arange(4)}
    with pytest.raises(GeometryValidationError, match="finite area"):
        CADGeometryCardEngine().compute_cards([primitive], points)
    primitive["type"] = "sphere"
    with pytest.raises(GeometryValidationError, match="unsupported"):
        CADGeometryCardEngine().compute_cards([primitive], points)


def test_no_nan_json():
    with pytest.raises(GeometryValidationError):
        CADGeometryCardEngine.to_json({"bad": np.nan})


def test_step_units_empty_cards_and_conflicts(plane_card):
    with pytest.raises(GeometryValidationError, match="at least one"):
        STEPGeometryExportEngine().export({"total_primitives": 0, "operations": []})
    card = copy.deepcopy(plane_card)
    card["length_unit"] = "unspecified"
    with pytest.raises(GeometryValidationError, match="explicit source units"):
        STEPGeometryExportEngine().export(card)
    with pytest.raises(GeometryValidationError, match="conflict"):
        STEPGeometryExportEngine(length_unit="m").export(plane_card)
    card["total_primitives"] = 4
    with pytest.raises(GeometryValidationError, match="disagrees"):
        STEPGeometryExportEngine().export(card)


def test_optional_backend_error_is_explicit(monkeypatch, plane_card):
    original = builtins.__import__
    def block(name, *args, **kwargs):
        if name == "OCP" or name.startswith("OCP."):
            raise ImportError("test: backend intentionally unavailable")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", block)
    with pytest.raises(OptionalDependencyError, match="cadquery-ocp"):
        STEPGeometryExportEngine().export(plane_card)


def test_atomic_output_no_clobber_and_cleanup(tmp_path):
    path = tmp_path / "result.json"
    write_text_atomic(path, "first\n")
    with pytest.raises(FileExistsError):
        write_text_atomic(path, "second\n")
    assert path.read_text() == "first\n"
    write_text_atomic(path, "second\n", overwrite=True)
    assert path.read_text() == "second\n"
    assert not list(tmp_path.glob(".*.tmp"))


def test_concurrent_publication_has_one_winner(tmp_path):
    path = tmp_path / "result.txt"
    texts = [str(i) * 10000 for i in range(8)]
    def publish(text):
        try:
            write_text_atomic(path, text)
            return True
        except FileExistsError:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        won = list(pool.map(publish, texts))
    assert sum(won) == 1
    assert path.read_text() == texts[won.index(True)]
    assert not list(tmp_path.glob(".*.tmp"))
