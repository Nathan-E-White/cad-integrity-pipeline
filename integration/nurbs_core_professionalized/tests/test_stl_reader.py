import struct

import numpy as np
import pytest

from STLReader import STLParseError, STLReader
from conftest import ascii_text, write_binary

TRIANGLES = np.array([
    [[0., 0., 0.], [1., 0., 0.], [1., 1., 0.]],
    [[0., 0., 0.], [1., 1., 0.], [0., 1., 0.]],
])


@pytest.mark.parametrize("header", [b"binary file", b"solid not really ASCII"])
def test_binary_records_and_winding(tmp_path, header):
    path = write_binary(tmp_path / "input.stl", TRIANGLES, header=header, attributes=[0xffff, 0x0102])
    mesh = STLReader.read(path)
    assert mesh.report.format == "binary"
    assert mesh.points.shape == (4, 3)
    assert mesh.faces.shape == (2, 3)
    np.testing.assert_allclose(mesh.points[mesh.faces], TRIANGLES)
    np.testing.assert_allclose(mesh.face_normals, [[0, 0, 1], [0, 0, 1]])
    np.testing.assert_allclose(mesh.vertex_normals(), np.tile([0, 0, 1], (4, 1)))
    assert len(STLReader.load_stl(path)) == 3


def test_ascii_matches_binary_and_multisolid(tmp_path):
    ascii_path = tmp_path / "ascii.stl"
    ascii_path.write_text("\ufeff\n  " + ascii_text(TRIANGLES[:1]) + ascii_text(TRIANGLES[1:]), encoding="utf-8")
    binary = STLReader.load_stl(write_binary(tmp_path / "binary.stl", TRIANGLES))
    ascii_mesh = STLReader.read(ascii_path)
    assert ascii_mesh.report.format == "ascii"
    for left, right in zip(binary, ascii_mesh.as_tuple(), strict=True):
        np.testing.assert_allclose(left, right)


@pytest.mark.parametrize("encoding", ["binary", "ascii"])
def test_empty_stl(tmp_path, encoding):
    path = tmp_path / "empty.stl"
    if encoding == "binary":
        write_binary(path, [])
    else:
        path.write_text("solid empty\nendsolid empty\n")
    points, normals, faces = STLReader.load_stl(path)
    assert points.shape == normals.shape == faces.shape == (0, 3)


@pytest.mark.parametrize("change", ["truncate", "extra", "count", "short"])
def test_binary_malformed_rejected(tmp_path, change):
    path = write_binary(tmp_path / "bad.stl", TRIANGLES)
    data = path.read_bytes()
    data = {"truncate": data[:-1], "extra": data + b"x", "count": data[:80] + struct.pack("<I", 3) + data[84:], "short": b"tiny"}[change]
    path.write_bytes(data)
    with pytest.raises(STLParseError):
        STLReader.read(path, format="binary")


@pytest.mark.parametrize("text", [
    "solid s\nfacet normal 0 0 1\n",
    "solid s\nvertex 0 0 0\nendsolid s\n",
    ascii_text(TRIANGLES).replace("vertex 1.0 0.0 0.0", "vertex bad 0 0"),
    ascii_text(TRIANGLES).replace("endloop", "vertex 2 2 2\nendloop", 1),
    ascii_text(TRIANGLES).replace("outer loop\n", "", 1),
    "solid s\n" + "x" * 17000,
])
def test_ascii_malformed_rejected(tmp_path, text):
    path = tmp_path / "bad.stl"
    path.write_text(text)
    with pytest.raises(STLParseError):
        STLReader.load_stl(path)


@pytest.mark.parametrize("encoding", ["ascii", "binary"])
def test_nonfinite_vertices_rejected(tmp_path, encoding):
    triangles = TRIANGLES.copy()
    triangles[0, 0, 0] = np.nan
    path = tmp_path / "bad.stl"
    if encoding == "binary":
        write_binary(path, triangles)
    else:
        path.write_text(ascii_text(triangles))
    with pytest.raises(STLParseError, match="NaN|infinity"):
        STLReader.load_stl(path)


def test_degenerate_policy_and_area_tolerance(tmp_path):
    triangles = np.concatenate((TRIANGLES, np.zeros((1, 3, 3))))
    path = write_binary(tmp_path / "input.stl", triangles)
    mesh = STLReader.read(path)
    assert mesh.report.dropped_degenerate_facets == 1
    assert len(mesh.faces) == 2
    with pytest.raises(STLParseError, match="degenerate"):
        STLReader.read(path, degenerate_policy="error")
    mesh = STLReader.read(path, area_tolerance=0.6)
    assert len(mesh.faces) == len(mesh.points) == 0


def test_limits_before_allocation_and_missing_file(tmp_path):
    path = write_binary(tmp_path / "input.stl", TRIANGLES)
    with pytest.raises(STLParseError, match="max_facets"):
        STLReader.read(path, max_facets=1)
    with pytest.raises(STLParseError, match="max_file_bytes"):
        STLReader.read(path, max_file_bytes=83)
    with pytest.raises(FileNotFoundError):
        STLReader.read(tmp_path / "absent.stl")


@pytest.mark.parametrize("kwargs", [{"format": "obj"}, {"area_tolerance": -1}, {"degenerate_policy": "ignore"}, {"max_facets": True}, {"max_file_bytes": 0}])
def test_reader_configuration_validation(tmp_path, kwargs):
    with pytest.raises(ValueError):
        STLReader.read(tmp_path / "not_needed.stl", **kwargs)
