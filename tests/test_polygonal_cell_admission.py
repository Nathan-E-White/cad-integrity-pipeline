"""Characterization tests for raw polygonal input and admissible cell complexes."""
from dataclasses import replace

import numpy as np
import pytest

from cad_integrity.errors import InvalidGeometry
from cad_integrity.f2_reduction import ReductionBudget
from cad_integrity.fixtures import cube, disk, pinched_tetrahedra
from cad_integrity.models import PolyhedralBRep
from cad_integrity.pipeline import RepairPipeline, RepairPolicy
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


def test_unused_edge_is_diagnosed_without_homology() -> None:
    raw = cube()
    unused_edge = replace(raw, edges=np.vstack((raw.edges, (0, 1))))

    report = BRepHomologyStitchAnalyzer(unused_edge).evaluate_stitch_integrity()

    assert report.unused_edge_ids == (12,)
    assert report.homology is None


def test_repair_refuses_an_inadmissible_raw_carrier_without_a_candidate() -> None:
    mesh = pinched_tetrahedra()
    raw = PolyhedralBRep.from_polygons(mesh.vertices, mesh.triangles)

    result = RepairPipeline().run(raw)

    assert result.original is raw
    assert result.candidate is None
    assert result.report.decision == "rejected"


def test_repair_preserves_a_valid_carrier_when_a_configured_audit_budget_is_exhausted() -> None:
    policy = RepairPolicy(reduction_budget=ReductionBudget(max_columns=1))

    result = RepairPipeline(policy).run(cube())

    assert result.original is not None
    assert result.candidate is not None
    assert result.report.decision == "needs_review"
    assert result.report.before.homology is None
    assert result.report.before.has_admissible_polygonal_cells
    assert result.report.before.homology_unavailable_reason == (
        "F_2 input exceeds the configured reduction budget"
    )
    assert result.report.after is not None
    assert result.report.after.homology_unavailable_reason == (
        "F_2 input exceeds the configured reduction budget"
    )
