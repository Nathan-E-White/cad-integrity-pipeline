"""Characterization tests for raw polygonal input and admissible cell complexes."""
from dataclasses import replace

import numpy as np
import pytest

from cad_integrity.errors import InvalidGeometry
from cad_integrity.fixtures import cube, disk, pinched_tetrahedra
from cad_integrity.models import PolyhedralBRep
from cad_integrity.topology import BRepHomologyStitchAnalyzer


def test_broken_wire_is_not_admitted_to_chain_construction() -> None:
    raw = disk()
    tokens = raw.face_coedges.copy()
    tokens[1] *= -1
    broken_wire = replace(raw, face_coedges=tokens)

    with pytest.raises(InvalidGeometry, match="continuous closed loop"):
        broken_wire.to_chain_complex()


def test_collapsed_edge_is_diagnosed_without_homology() -> None:
    raw = disk()
    vertices = raw.vertices.copy()
    vertices[1] = vertices[0]
    collapsed_edge = replace(raw, vertices=vertices)

    report = BRepHomologyStitchAnalyzer(collapsed_edge).evaluate_stitch_integrity()

    assert report.collapsed_edge_ids == (0,)
    assert report.homology is None
    assert report.homology_unavailable_reason == "Inadmissible polygonal cells: refusing a misleading homology result"


def test_pinched_vertex_is_diagnosed_without_homology() -> None:
    mesh = pinched_tetrahedra()
    raw = PolyhedralBRep.from_polygons(mesh.vertices, mesh.triangles)

    report = BRepHomologyStitchAnalyzer(raw).evaluate_stitch_integrity()

    assert report.nonmanifold_vertex_ids == (0,)
    assert report.homology is None


def test_unused_vertex_is_diagnosed_without_homology() -> None:
    raw = cube()
    unused_vertex = replace(raw, vertices=np.vstack((raw.vertices, (100.0, 100.0, 100.0))))

    report = BRepHomologyStitchAnalyzer(unused_vertex).evaluate_stitch_integrity()

    assert report.unused_vertex_ids == (8,)
    assert report.homology is None
