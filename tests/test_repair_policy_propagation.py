"""Public-seam characterization of polygonal repair policy propagation."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from cad_integrity.algebra import ReductionBudget
from cad_integrity.fixtures import cracked_cube, cube, disk
from cad_integrity.models import PolyhedralBRep
from cad_integrity.pipeline import RepairPipeline, RepairPolicy, fingerprint
from cad_integrity.repair import WeldPolicy, synchronize_orientations, weld_vertices


def test_tiny_reduction_budget_is_reported_at_every_pipeline_audit_point() -> None:
    """A configured limit is not silently replaced by the default audit budget."""
    limited = RepairPipeline(
        RepairPolicy(
            weld=WeldPolicy(0.005, 0.005),
            reduction_budget=ReductionBudget(max_columns=1),
        )
    ).run(cracked_cube())

    assert limited.candidate is not None
    assert limited.report.before.homology is None
    assert limited.report.after is not None
    assert limited.report.after.homology is None
    assert limited.report.before.homology_unavailable_reason == (
        "F_2 input exceeds the configured reduction budget"
    )
    assert limited.report.after.homology_unavailable_reason == (
        "F_2 input exceeds the configured reduction budget"
    )


def real_projective_plane() -> PolyhedralBRep:
    """The six-vertex, ten-face triangulation has Z/2 first homology over Z."""
    facets = (
        (0, 1, 2), (0, 1, 3), (0, 2, 4), (0, 3, 5), (0, 4, 5),
        (1, 2, 5), (1, 3, 4), (1, 4, 5), (2, 3, 4), (2, 3, 5),
    )
    return PolyhedralBRep.from_polygons(
        np.column_stack((np.arange(6), np.zeros(6), np.zeros(6))), facets
    )


@pytest.mark.parametrize(
    ("coefficients", "betti", "torsion"),
    [("F2", (1, 1, 1), ()), ("Z", (1, 0, 0), (2,))],
)
def test_pipeline_propagates_coefficients_to_torsion_bearing_before_and_after_evidence(
    coefficients: str, betti: tuple[int, ...], torsion: tuple[int, ...]
) -> None:
    result = RepairPipeline(
        RepairPolicy(coefficients=coefficients, synchronize_orientation=False)
    ).run(real_projective_plane())

    assert result.report.before.homology is not None
    assert result.report.after is not None
    assert result.report.after.homology is not None
    assert result.report.before.homology.coefficients == coefficients
    assert result.report.after.homology.coefficients == coefficients
    assert result.report.before.homology.betti_numbers == betti
    assert result.report.after.homology.betti_numbers == betti
    assert result.report.before.homology.groups[1].torsion == torsion
    assert result.report.after.homology.groups[1].torsion == torsion


def test_direct_operations_and_pipeline_share_policy_bound_audit_evidence() -> None:
    source = cracked_cube()
    source_hash = fingerprint(source)
    policy = RepairPolicy(weld=WeldPolicy(0.005, 0.005))
    welded = weld_vertices(source, WeldPolicy(0.005, 0.005), repair_policy=policy)
    welded_hash = fingerprint(welded.candidate)
    oriented = synchronize_orientations(welded.candidate, repair_policy=policy)
    result = RepairPipeline(policy).run(source)

    assert fingerprint(source) == source_hash
    assert fingerprint(welded.candidate) == welded_hash
    assert welded.maximum_displacement == pytest.approx(0.002)
    assert oriented.candidate is not source
    assert welded.before.homology == result.report.before.homology
    assert welded.after.homology is not None
    assert oriented.before == welded.after
    assert oriented.after == result.report.after
    assert result.report.input_sha256 == source_hash
    assert result.report.changes == (
        "Merged 4 vertices and 4 straight edges",
        "Reversed complete loops on 1 faces",
    )


def test_rejected_weld_returns_no_candidate_or_after_evidence() -> None:
    result = RepairPipeline(RepairPolicy(weld=WeldPolicy(2, 2))).run(disk())

    assert result.report.decision == "rejected"
    assert result.candidate is None
    assert result.report.after is None


def test_direct_weld_requires_the_same_policy_and_preserves_audit_limit_evidence() -> None:
    """Stage 6 removes the direct helper's hidden default-audit detour."""
    policy = RepairPolicy(reduction_budget=ReductionBudget(max_columns=1))
    direct = weld_vertices(cracked_cube(), WeldPolicy(0.005, 0.005), repair_policy=policy)

    assert direct.before.homology is None
    assert direct.after.homology is None
    assert direct.before.homology_unavailable_reason == (
        "F_2 input exceeds the configured reduction budget"
    )
    assert direct.after.homology_unavailable_reason == (
        "F_2 input exceeds the configured reduction budget"
    )


@pytest.mark.parametrize(
    ("source", "policy", "expected_events", "expected_decision"),
    [
        (cube, RepairPolicy(synchronize_orientation=False), (
            ("analyze", "Analyzing the input polygonal boundary"),
            ("verify", "Re-running diagnostics on the candidate"),
            ("complete", "topology_checks_passed")),
         "topology_checks_passed"),
        (cracked_cube, RepairPolicy(weld=WeldPolicy(.005, .005), synchronize_orientation=False),
         (("analyze", "Analyzing the input polygonal boundary"),
          ("weld", "Attempting explicitly authorized boundary-vertex welding"),
          ("verify", "Re-running diagnostics on the candidate"), ("complete", "needs_review")),
         "needs_review"),
        (lambda: cube(reversed_face=1), RepairPolicy(), (
            ("analyze", "Analyzing the input polygonal boundary"),
            ("orient", "Solving orientation constraints across every component"),
            ("verify", "Re-running diagnostics on the candidate"),
            ("complete", "topology_checks_passed")),
         "topology_checks_passed"),
        (cracked_cube, RepairPolicy(weld=WeldPolicy(.005, .005)),
         (("analyze", "Analyzing the input polygonal boundary"),
          ("weld", "Attempting explicitly authorized boundary-vertex welding"),
          ("orient", "Solving orientation constraints across every component"),
          ("verify", "Re-running diagnostics on the candidate"),
          ("complete", "topology_checks_passed")), "topology_checks_passed"),
        (cracked_cube, RepairPolicy(weld=WeldPolicy(.005, .005, max_candidate_visits=1)),
         (("analyze", "Analyzing the input polygonal boundary"),
          ("weld", "Attempting explicitly authorized boundary-vertex welding"),
          ("rejected", "Weld neighborhood search exceeds the candidate budget")), "rejected"),
        (disk, RepairPolicy(weld=WeldPolicy(2, 2)), (
            ("analyze", "Analyzing the input polygonal boundary"),
            ("weld", "Attempting explicitly authorized boundary-vertex welding"),
            ("rejected", "Welding would collapse an edge; candidate was not applied")), "rejected"),
    ],
    ids=["noop", "weld-only", "orientation-only", "compound", "resource-limit", "rejection"],
)
def test_transition_emits_complete_ordered_stage_trace_and_payloads(
    source: Callable[[], PolyhedralBRep],
    policy: RepairPolicy,
    expected_events: tuple[tuple[str, str], ...],
    expected_decision: str,
) -> None:
    events = []
    result = RepairPipeline(policy).run(source(), on_event=events.append)

    assert result.report.decision == expected_decision
    assert tuple((event.stage, event.message) for event in events) == expected_events


def test_compound_transition_has_deterministic_hash_displacement_report_and_trace() -> None:
    policy = RepairPolicy(weld=WeldPolicy(.005, .005))
    traces = []
    first = RepairPipeline(policy).run(cracked_cube(), on_event=traces.append)
    second_events = []
    second = RepairPipeline(policy).run(cracked_cube(), on_event=second_events.append)

    assert first.candidate is not None and second.candidate is not None
    assert first.report.input_sha256 == second.report.input_sha256
    assert fingerprint(first.candidate) == fingerprint(second.candidate)
    assert first.report.maximum_vertex_displacement == second.report.maximum_vertex_displacement
    assert first.report == second.report
    assert traces == second_events


def test_pipeline_rejects_a_nearby_but_distinct_weld_that_would_create_a_pinch() -> None:
    points = np.array(
        (
            (0, 0, 0), (0.75, 0, 0), (1.5, 0, 0),
            (0, 10, 0), (0, 10, 3), (10, 10, 0), (10, 10, 3),
            (20, 10, 0), (20, 10, 3),
        ),
        dtype=float,
    )
    distinct = PolyhedralBRep.from_polygons(points, ((0, 3, 4), (1, 5, 6), (2, 7, 8)))

    result = RepairPipeline(RepairPolicy(weld=WeldPolicy(1, 1))).run(distinct)

    assert result.report.decision == "rejected"
    assert result.candidate is None
    assert result.report.after is None
    assert "nonmanifold" in result.report.errors[0]


def test_pipeline_orients_multiple_components_then_is_idempotent() -> None:
    left, right = cube(reversed_face=1), cube(reversed_face=3)
    points = np.vstack((left.vertices, right.vertices + (30, 0, 0)))
    polygons = [left.face_vertices(face) for face in range(left.face_count)]
    polygons += [tuple(vertex + 8 for vertex in right.face_vertices(face))
                 for face in range(right.face_count)]
    source = PolyhedralBRep.from_polygons(points, polygons)
    policy = RepairPolicy(synchronize_orientation=True)
    events = []

    first = RepairPipeline(policy).run(source, on_event=events.append)
    assert first.candidate is not None
    assert [event.stage for event in events] == ["analyze", "orient", "verify", "complete"]
    assert first.report.after is not None
    assert first.report.after.is_closed_oriented_2manifold

    second = RepairPipeline(policy).run(first.candidate)
    assert second.candidate is not None
    assert second.report.changes == ("Reversed complete loops on 0 faces",)
    assert fingerprint(first.candidate) == fingerprint(second.candidate)
