"""Characterization tests for raw polygonal input and admissible cell complexes."""

from dataclasses import replace

import numpy as np
import pytest

from cad_integrity.f2_reduction import ReductionBudget
from cad_integrity.fixtures import cube, disk, pinched_tetrahedra, torus
from cad_integrity.models import PolyhedralBRep
from cad_integrity.pipeline import RepairPipeline, RepairPolicy
from cad_integrity.polygonal_cells import ValidatedPolygonalCells, admit_polygonal_cells
from cad_integrity.topology import BRepHomologyStitchAnalyzer


def test_broken_wire_is_not_admitted_to_chain_construction() -> None:
    raw = disk()
    tokens = raw.face_coedges.copy()
    tokens[1] *= -1
    broken_wire = replace(raw, face_coedges=tokens)

    admission = admit_polygonal_cells(broken_wire)

    assert admission.cells is None
    assert admission.invalid_face_ids == (0,)
    assert admission.reason == "Inadmissible polygonal cells: refusing a misleading homology result"


@pytest.mark.parametrize(
    "raw", [disk(), cube(), PolyhedralBRep.from_polygons(torus().vertices, torus().triangles)]
)
def test_validated_cells_preserve_the_prior_chain_matrices(raw: PolyhedralBRep) -> None:
    cells = admit_polygonal_cells(raw).require_cells()

    chain = cells.to_chain_complex()

    assert chain.dimensions == (len(raw.vertices), len(raw.edges), raw.face_count)
    assert np.array_equal(chain.boundary(1).toarray(), _prior_d1(raw))
    assert np.array_equal(chain.boundary(2).toarray(), _prior_d2(raw))


def test_analyzer_and_repair_use_the_same_admission_facts() -> None:
    raw = disk()
    vertices = raw.vertices.copy()
    vertices[1] = vertices[0]
    invalid = replace(raw, vertices=vertices)

    admission = admit_polygonal_cells(invalid)
    report = BRepHomologyStitchAnalyzer(invalid).evaluate_stitch_integrity()
    result = RepairPipeline().run(invalid)

    assert admission.cells is None
    assert report.collapsed_edge_ids == admission.collapsed_edge_ids
    assert report.homology_unavailable_reason == admission.reason
    assert result.candidate is None
    assert result.report.errors == (admission.reason,)


def test_admission_reports_every_invalid_face_instead_of_stopping_at_the_first() -> None:
    raw = disk()
    tokens = np.concatenate((raw.face_coedges, raw.face_coedges))
    tokens[1] *= -1
    tokens[5] *= -1
    invalid = replace(raw, face_offsets=np.array((0, 4, 8), dtype=np.int64), face_coedges=tokens)

    admission = admit_polygonal_cells(invalid)

    assert admission.cells is None
    assert admission.invalid_face_ids == (0, 1)


def test_admission_retains_nonmanifold_edge_and_link_evidence() -> None:
    raw = PolyhedralBRep.from_polygons(
        np.array(((0, 0, 0), (1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0)), dtype=float),
        ((0, 1, 2), (0, 2, 3), (0, 3, 1), (0, 1, 4)),
    )

    admission = admit_polygonal_cells(raw)

    assert admission.cells is None
    assert admission.nonmanifold_edge_ids == (0,)
    assert admission.nonmanifold_vertex_ids == (0, 1)


def test_raw_duplicate_faces_cannot_bypass_admission_to_construct_a_chain() -> None:
    raw = disk()
    duplicate = replace(
        raw,
        face_offsets=np.array((0, 4, 8), dtype=np.int64),
        face_coedges=np.concatenate((raw.face_coedges, raw.face_coedges)),
    )

    assert admit_polygonal_cells(duplicate).cells is None
    with pytest.raises(TypeError, match="_admission_token"):
        ValidatedPolygonalCells(duplicate)


def _prior_d1(raw: PolyhedralBRep) -> np.ndarray:
    matrix = np.zeros((len(raw.vertices), len(raw.edges)), dtype=np.int64)
    for edge, (start, end) in enumerate(raw.edges):
        matrix[start, edge] = -1
        matrix[end, edge] = 1
    return matrix


def _prior_d2(raw: PolyhedralBRep) -> np.ndarray:
    matrix = np.zeros((len(raw.edges), raw.face_count), dtype=np.int64)
    for face in range(raw.face_count):
        for token in raw.face_loop(face):
            matrix[abs(token) - 1, face] = np.sign(token)
    return matrix


def test_collapsed_edge_is_diagnosed_without_homology() -> None:
    raw = disk()
    vertices = raw.vertices.copy()
    vertices[1] = vertices[0]
    collapsed_edge = replace(raw, vertices=vertices)

    report = BRepHomologyStitchAnalyzer(collapsed_edge).evaluate_stitch_integrity()

    assert report.collapsed_edge_ids == (0,)
    assert report.homology is None
    assert (
        report.homology_unavailable_reason
        == "Inadmissible polygonal cells: refusing a misleading homology result"
    )


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


@pytest.mark.parametrize(
    "raw, expected_betti",
    [
        (disk(), (1, 0, 0)),
        (cube(), (1, 0, 1)),
        (PolyhedralBRep.from_polygons(torus().vertices, torus().triangles), (1, 2, 1)),
    ],
)
def test_valid_polygonal_cells_construct_chains_and_report_expected_homology(
    raw: PolyhedralBRep, expected_betti: tuple[int, int, int]
) -> None:
    chain = admit_polygonal_cells(raw).require_cells().to_chain_complex()
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
        candidate = replace(
            raw,
            face_offsets=np.array((0, 4, 8), dtype=np.int64),
            face_coedges=np.concatenate((first_loop, equivalent)),
        )
        report = BRepHomologyStitchAnalyzer(candidate).evaluate_stitch_integrity()
        assert report.duplicate_face_ids == (1,)
        assert report.invalid_face_ids == ()
        assert report.homology is None


def test_sign_only_reversal_is_not_a_complete_face_reversal() -> None:
    raw = disk()
    candidate = replace(
        raw,
        face_offsets=np.array((0, 4, 8), dtype=np.int64),
        face_coedges=np.concatenate((raw.face_coedges, -raw.face_coedges)),
    )

    report = BRepHomologyStitchAnalyzer(candidate).evaluate_stitch_integrity()

    assert report.invalid_face_ids == (1,)
    assert report.duplicate_face_ids == ()
    assert report.homology is None


def test_generated_valid_cells_preserve_chain_identity_under_entity_renumbering() -> None:
    raw = cube()
    original_chain = admit_polygonal_cells(raw).require_cells().to_chain_complex()
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
        renumbered_chain = admit_polygonal_cells(renumbered).require_cells().to_chain_complex()

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


def test_admitted_chain_retains_the_assessed_snapshot_after_raw_alias_mutation() -> None:
    raw = disk()
    cells = admit_polygonal_cells(raw).require_cells()
    raw.face_coedges.setflags(write=True)
    raw.face_coedges[0] *= -1
    chain = cells.to_chain_complex()
    assert chain.boundary(2).toarray().ravel().tolist() == [1, 1, 1, -1]


def test_topology_resource_failure_is_not_reported_as_invalid_geometry() -> None:
    from cad_integrity.errors import ResourceLimitExceeded
    from cad_integrity.polygonal_cells import PolygonalLimits
    from cad_integrity.topology import orientation_solution

    limits = PolygonalLimits(max_work_steps=0)
    with pytest.raises(ResourceLimitExceeded, match="work budget"):
        admit_polygonal_cells(disk(), limits=limits)
    with pytest.raises(ResourceLimitExceeded, match="work budget"):
        BRepHomologyStitchAnalyzer(disk(), topology_limits=limits).evaluate_stitch_integrity()
    with pytest.raises(ResourceLimitExceeded, match="work budget"):
        orientation_solution(disk(), limits=limits)


def test_orientation_preserves_nonmanifold_edge_exception() -> None:
    from cad_integrity.errors import InvalidGeometry
    from cad_integrity.topology import orientation_solution

    raw = disk()
    triple = replace(raw, face_offsets=np.array((0, 4, 8, 12), dtype=np.int64),
                     face_coedges=np.tile(raw.face_coedges, 3))
    with pytest.raises(InvalidGeometry, match="^Cannot orient nonmanifold edge 0$"):
        orientation_solution(triple)
