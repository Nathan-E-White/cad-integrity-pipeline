from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest


def write_binary(path: Path, triangles, *, header=b"test STL", attributes=None) -> Path:
    triangles = np.asarray(triangles, dtype=float).reshape(-1, 3, 3)
    with path.open("wb") as stream:
        stream.write(header[:80].ljust(80, b" "))
        stream.write(struct.pack("<I", len(triangles)))
        for i, triangle in enumerate(triangles):
            attribute = (100 + i) if attributes is None else attributes[i]
            # Intentionally incorrect normals: both parsers must use winding.
            stream.write(struct.pack("<12fH", 9.0, 1.0, -7.0, *triangle.ravel(), attribute))
    return path


def ascii_text(triangles) -> str:
    lines = ["solid fixture"]
    for triangle in triangles:
        lines.extend(["facet normal 0 0 -1", "outer loop"])
        lines.extend("vertex " + " ".join(map(str, point)) for point in triangle)
        lines.extend(["endloop", "endfacet"])
    lines.append("endsolid fixture")
    return "\n".join(lines) + "\n"


def plane_grid(n=12, *, extent=2.0, z=0.0):
    x, y = np.meshgrid(np.linspace(-extent, extent, n), np.linspace(-extent, extent, n), indexing="ij")
    return np.c_[x.ravel(), y.ravel(), np.full(x.size, z)]


def plane_triangles(n=12):
    points = plane_grid(n)
    faces = []
    for i in range(n - 1):
        for j in range(n - 1):
            a = i * n + j
            faces.extend([[a, a + n, a + n + 1], [a, a + n + 1, a + 1]])
    return points[np.asarray(faces)]


def cylinder_cloud(radius=3.0, *, origin=(0.0, 0.0, 0.0), axis=(0.0, 0.0, 1.0), start=0.1, stop=1.8, na=20, nz=8):
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    seed = np.eye(3)[np.argmin(np.abs(axis))]
    x = seed - (seed @ axis) * axis
    x /= np.linalg.norm(x)
    y = np.cross(axis, x)
    theta, height = np.meshgrid(np.linspace(start, stop, na), np.linspace(-2.0, 2.0, nz))
    radial = np.cos(theta.ravel())[:, None] * x + np.sin(theta.ravel())[:, None] * y
    points = np.asarray(origin) + radius * radial + height.ravel()[:, None] * axis
    return points, radial, axis


@pytest.fixture
def plane_stl(tmp_path):
    return write_binary(tmp_path / "plane.stl", plane_triangles())


@pytest.fixture
def plane_card():
    from NURBSCoreEngine import CADGeometryCardEngine
    points = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=float)
    primitive = {"type": "plane", "geometry": {"plane_equation": [0, 0, 1, 0]}, "point_indices": np.arange(4)}
    return CADGeometryCardEngine(length_unit="mm").compute_cards([primitive], points)
