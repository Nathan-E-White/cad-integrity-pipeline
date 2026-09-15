"""Characterization tests for raw polygonal input and admissible cell complexes."""
from dataclasses import replace

import pytest

from cad_integrity.errors import InvalidGeometry
from cad_integrity.fixtures import disk
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
    assert report.homology_unavailable_reason == (
        "Invalid, duplicate, or collapsed face cells: refusing a misleading homology result"
    )
