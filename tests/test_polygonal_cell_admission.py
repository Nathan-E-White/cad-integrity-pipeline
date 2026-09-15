"""Characterization tests for raw polygonal input and admissible cell complexes."""
from dataclasses import replace

import numpy as np
import pytest

from cad_integrity.errors import InvalidGeometry
from cad_integrity.f2_reduction import ReductionBudget
from cad_integrity.fixtures import cube, disk, pinched_tetrahedra, torus
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


def test_repeated_face_vertex_is_diagnosed_without_homology() -> None:
    raw = disk()
    repeated_vertex = PolyhedralBRep(
        raw.vertices,
        np.array(((0, 1), (0, 1), (0, 2), (0, 2)), dtype=np.int64),
        np.array((0, 4), dtype=np.int64),
        np.array((1, -2, 3, -4), dtype=np.int64),
    )

    report = BRepHomologyStitchAnalyzer(repeated_vertex).evaluate_stitch_integrity()

    assert report.invalid_face_ids == (0,)
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


@pytest.mark.parametrize("raw, expected_betti", [
    (disk(), (1, 0, 0)),
    (cube(), (1, 0, 1)),
    (PolyhedralBRep.from_polygons(torus().vertices, torus().triangles), (1, 2, 1)),
])
def test_valid_polygonal_cells_construct_chains_and_report_expected_homology(
        raw: PolyhedralBRep, expected_betti: tuple[int, int, int]) -> None:
    chain = raw.to_chain_complex()
    report = BRepHomologyStitchAnalyzer(raw).evaluate_stitch_integrity()

    assert chain.dimensions == (len(raw.vertices), len(raw.edges), raw.face_count)
    assert report.has_admissible_polygonal_cells
    assert report.homology is not None
    assert report.homology.betti_numbers == expected_betti


def test_face_identity_is_invariant_under_rotation_or_complete_reversal() -> None:
    raw = disk()
    first_loop = raw.face_coedges
    rotated = np.roll(first_loop, -1)
    reversed_loop = -first_loop[::-1]

    for equivalent in (rotated, reversed_loop):
        candidate = replace(raw, face_offsets=np.array((0, 4, 8), dtype=np.int64),
                            face_coedges=np.concatenate((first_loop, equivalent)))
        report = BRepHomologyStitchAnalyzer(candidate).evaluate_stitch_integrity()
        assert report.duplicate_face_ids == (1,)
        assert report.invalid_face_ids == ()
        assert report.homology is None


def test_sign_only_reversal_is_not_a_complete_face_reversal() -> None:
    raw = disk()
    candidate = replace(raw, face_offsets=np.array((0, 4, 8), dtype=np.int64),
                        face_coedges=np.concatenate((raw.face_coedges, -raw.face_coedges)))

    report = BRepHomologyStitchAnalyzer(candidate).evaluate_stitch_integrity()

    assert report.invalid_face_ids == (1,)
    assert report.duplicate_face_ids == ()
    assert report.homology is None


def test_generated_valid_cells_preserve_chain_identity_under_entity_renumbering() -> None:
    raw = cube()
    original_chain = raw.to_chain_complex()
    original_report = BRepHomologyStitchAnalyzer(raw).evaluate_stitch_integrity()
    rng = np.random.default_rng(20260915)

    for _ in range(8):
        new_to_old = rng.permutation(len(raw.vertices))
        old_to_new = np.empty(len(new_to_old), dtype=np.int64)
        old_to_new[new_to_old] = np.arange(len(new_to_old))
        face_order = rng.permutation(raw.face_count)
        polygons = []
        for old_face in face_order:
            vertices = tuple(int(old_to_new[v]) for v in raw.face_vertices(int(old_face)))
            rotation = int(rng.integers(len(vertices)))
            polygons.append(vertices[rotation:] + vertices[:rotation])
        renumbered = PolyhedralBRep.from_polygons(raw.vertices[new_to_old], polygons)
        renumbered_chain = renumbered.to_chain_complex()

        edge_by_endpoints = {
            tuple(sorted((int(u), int(v)))): edge for edge, (u, v) in enumerate(renumbered.edges)
        }
        edge_old_to_new = np.empty(len(raw.edges), dtype=np.int64)
        edge_signs = np.empty(len(raw.edges), dtype=np.int64)
        for old_edge, (u, v) in enumerate(raw.edges):
            nu, nv = int(old_to_new[u]), int(old_to_new[v])
            edge_old_to_new[old_edge] = edge_by_endpoints[tuple(sorted((nu, nv)))]
            edge_signs[old_edge] = 1 if nu < nv else -1
        face_old_to_new = np.empty(raw.face_count, dtype=np.int64)
        face_old_to_new[face_order] = np.arange(raw.face_count)

        expected_d1 = np.zeros_like(renumbered_chain.boundary(1).toarray())
        for old_edge, new_edge in enumerate(edge_old_to_new):
            expected_d1[old_to_new, new_edge] = (
                original_chain.boundary(1).toarray()[:, old_edge] * edge_signs[old_edge]
            )
        expected_d2 = np.zeros_like(renumbered_chain.boundary(2).toarray())
        for old_edge, new_edge in enumerate(edge_old_to_new):
            expected_d2[new_edge, face_old_to_new] = (
                original_chain.boundary(2).toarray()[old_edge] * edge_signs[old_edge]
            )

        assert np.array_equal(renumbered_chain.boundary(1).toarray(), expected_d1)
        assert np.array_equal(renumbered_chain.boundary(2).toarray(), expected_d2)
        renumbered_report = BRepHomologyStitchAnalyzer(renumbered).evaluate_stitch_integrity()
        assert original_report.homology is not None
        assert renumbered_report.homology is not None
        assert original_report.homology.betti_numbers == renumbered_report.homology.betti_numbers
