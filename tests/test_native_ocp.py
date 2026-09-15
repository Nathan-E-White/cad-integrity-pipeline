"""Real OCCT checks: no mocked geometry kernel and no live SGS dependency."""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("OCP")
pytestmark = pytest.mark.cad

from OCP.BRep import BRep_Builder
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeVertex
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere, BRepPrimAPI_MakeTorus
from OCP.gp import gp_Pln, gp_Pnt
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopoDS import TopoDS, TopoDS_Compound, TopoDS_Shape

from cad_integrity.adapters import ocp
from cad_integrity.errors import ExportRejected, KernelOperationFailed, RepairRejected, ResourceLimitExceeded
from cad_integrity.serialization import dumps


def compound(shapes):
    result = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(result)
    for shape in shapes:
        builder.Add(result, shape)
    return result


def box():
    return BRepPrimAPI_MakeBox(10, 10, 10).Shape()


def disconnected_faces(shape):
    return compound([BRepBuilderAPI_Copy(face, True, False).Shape()
                     for face in ocp._shapes(shape, TopAbs_FACE)])


def selected_wire_pairs(report):
    wire_ids = tuple(wire.wire_id for wire in report.free_boundary_wires)
    assert len(wire_ids) % 2 == 0
    return tuple(zip(wire_ids[::2], wire_ids[1::2], strict=True))


@pytest.mark.parametrize("factory, surface_type, volume", [
    (box, "GeomAbs_Plane", 1000),
    (lambda: BRepPrimAPI_MakeCylinder(2, 5).Shape(), "GeomAbs_Cylinder", np.pi*20),
    (lambda: BRepPrimAPI_MakeSphere(2).Shape(), "GeomAbs_Sphere", 4*np.pi*8/3),
    (lambda: BRepPrimAPI_MakeTorus(4, 1).Shape(), "GeomAbs_Torus", 8*np.pi**2),
])
def test_analytic_roundtrip(factory, surface_type, volume, tmp_path):
    shape = factory()
    before = ocp.audit_shape(shape)
    assert before.accepted_under_policy, before.acceptance_reasons
    assert surface_type in dict(before.surface_types)
    assert before.solid_volumes_mm3 == pytest.approx((volume,))
    assert before.homology is None
    report = ocp.export_checked_step(shape, tmp_path / "part.step")
    assert report.after_roundtrip.accepted_under_policy
    assert report.before_serialization.surface_types == report.after_roundtrip.surface_types
    imported = ocp.read_step(report.output)
    assert imported.length_unit == "mm"
    assert imported.source_sha256 == report.output_sha256
    assert len(report.output_sha256) == 64
    assert imported.roots_transferred > 0
    assert "millimetre" in tuple(name.lower() for name in imported.source_unit_names)


def test_sphere_poles_and_periodic_seams_are_not_leaks():
    sphere = ocp.audit_shape(BRepPrimAPI_MakeSphere(2).Shape())
    cylinder = ocp.audit_shape(BRepPrimAPI_MakeCylinder(2, 5).Shape())
    torus = ocp.audit_shape(BRepPrimAPI_MakeTorus(4, 1).Shape())
    assert sphere.degenerate_edge_count == 2
    assert not sphere.free_edge_ids
    assert not cylinder.free_edge_ids
    assert not torus.free_edge_ids
    assert not torus.nonmanifold_edge_ids


def test_native_defect_classifier_reports_read_only_serializable_evidence():
    source = disconnected_faces(box())
    before = ocp.audit_shape(source)
    fingerprint_before = ocp._native_shape_fingerprint(source)

    report = ocp.classify_native_defects(source)

    assert report.audit == before
    assert len(report.free_boundary_wires) == 6
    assert {edge_id for wire in report.free_boundary_wires for edge_id in wire.edge_ids} == set(range(24))
    assert all(wire.scope == "derived_connected_free_edge_group_not_OCCT_wire_reconstruction"
               for wire in report.free_boundary_wires)
    assert all(len(edge.face_ids) == 1 for edge in report.edge_ownership)
    assert report.self_intersection.status == "not_established"
    assert report.candidate_pairs
    assert all(pair.minimum_distance_mm == pytest.approx(0) for pair in report.candidate_pairs)
    assert "not design intent" in report.candidate_pair_scope
    assert report.classification_confidence.level == "kernel_evidence_only"
    assert report.source_fingerprint_sha256 == fingerprint_before
    assert report == ocp.classify_native_defects(source)
    assert ocp._native_shape_fingerprint(source) == fingerprint_before
    assert ocp.audit_shape(source) == before
    assert '"free_boundary_wires"' in dumps(report)


def test_native_defect_classifier_labels_periodic_and_degenerate_native_entities():
    sphere = ocp.classify_native_defects(BRepPrimAPI_MakeSphere(2).Shape())
    torus = ocp.classify_native_defects(BRepPrimAPI_MakeTorus(4, 1).Shape())

    sphere_face, = sphere.periodic_faces
    torus_face, = torus.periodic_faces
    assert sphere_face.surface_type == "GeomAbs_Sphere"
    assert sphere_face.u_periodic and not sphere_face.v_periodic
    assert sphere_face.degenerate_edge_ids == (0, 2)
    seam = sphere.edge_ownership[1]
    assert seam.face_ids == (0,)
    assert seam.face_occurrence_count == 2
    assert seam.closed_on_face_ids == (0,)
    assert torus_face.surface_type == "GeomAbs_Torus"
    assert torus_face.u_periodic and torus_face.v_periodic
    assert not torus_face.degenerate_edge_ids


def test_native_defect_classifier_bounds_proximity_work_without_selecting_a_repair():
    source = disconnected_faces(box())

    limited = ocp.classify_native_defects(source, max_candidate_pair_comparisons=0)

    assert limited.candidate_pairs == ()
    assert limited.candidate_pair_comparisons == 0
    assert limited.candidate_pair_comparison_limit_reached
    assert limited.audit == ocp.audit_shape(source)
    closed = ocp.classify_native_defects(box(), max_candidate_pair_comparisons=0)
    assert not closed.candidate_pair_comparison_limit_reached
    with pytest.raises(ValueError, match="nonnegative"):
        ocp.classify_native_defects(source, max_candidate_pair_comparisons=-1)


def test_native_defect_classifier_is_deterministic_across_stage_eight_fixture_classes():
    outer = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    inner = BRepPrimAPI_MakeBox(gp_Pnt(2, 2, 2), 6, 6, 6).Shape()
    fixtures = (
        (box(), ocp.KernelPolicy()),
        (BRepPrimAPI_MakeCylinder(2, 5).Shape(), ocp.KernelPolicy()),
        (disconnected_faces(box()), ocp.KernelPolicy()),
        (compound([box(), BRepPrimAPI_MakeBox(gp_Pnt(20, 0, 0), 5, 5, 5).Shape()]),
         ocp.KernelPolicy(expected_solids=2)),
        (BRepAlgoAPI_Cut(outer, inner).Shape(), ocp.KernelPolicy()),
    )
    for source, policy in fixtures:
        before = ocp.audit_shape(source, policy)
        first = ocp.classify_native_defects(source, policy)

        assert first == ocp.classify_native_defects(source, policy)
        assert first.audit == before
        assert ocp.audit_shape(source, policy) == before


def test_open_boundary_edges_retain_native_entity_provenance_without_filling():
    source = disconnected_faces(BRepPrimAPI_MakeBox(10, 20, 30).Shape())
    report = ocp.audit_shape(source)

    # Six independently copied quadrilateral faces expose 24 native boundary
    # edges.  These local report IDs are the public rendering provenance.
    assert report.free_edge_ids == tuple(range(24))
    selected_id = 5
    edge = TopoDS.Edge_s(ocp._shapes(source, TopAbs_EDGE)[selected_id])
    curve = BRepAdaptor_Curve(edge)
    expected_endpoints = np.array([
        curve.Value(curve.FirstParameter()).Coord(),
        curve.Value(curve.LastParameter()).Coord(),
    ])
    samples = ocp.sample_edge_polylines(source, (selected_id,), samples=2)
    assert len(samples) == 1
    np.testing.assert_allclose(samples[0], expected_endpoints)


def test_nearby_but_separate_valid_solids_are_not_auto_selected_for_repair():
    source = compound([box(), BRepPrimAPI_MakeBox(gp_Pnt(10.0001, 0, 0), 10, 10, 10).Shape()])
    policy = ocp.KernelPolicy(expected_solids=2, precision_mm=1e-3)
    before = ocp.audit_shape(source, policy)

    assert before.accepted_under_policy, before.acceptance_reasons
    result = ocp.repair_shape(source, policy)
    assert result.operations == ("No repair needed",)
    assert result.before == before
    assert result.after.accepted_under_policy


def test_nearby_open_boundaries_are_refused_without_mutating_the_source():
    source = compound([
        disconnected_faces(box()),
        disconnected_faces(BRepPrimAPI_MakeBox(gp_Pnt(10.0001, 0, 0), 10, 10, 10).Shape()),
    ])
    policy = ocp.KernelPolicy(expected_solids=2, precision_mm=1e-3)
    before = ocp.audit_shape(source, policy)

    assert before.free_edge_ids
    with pytest.raises(RepairRejected, match="explicit classifier-backed selection"):
        ocp.repair_shape(source, policy)
    assert ocp.audit_shape(source, policy) == before


@pytest.mark.parametrize("factory", [box, lambda: BRepPrimAPI_MakeCylinder(2, 5).Shape()])
def test_selected_native_sewing_preserves_surfaces_and_input(factory, tmp_path):
    source = disconnected_faces(factory())
    before = ocp.audit_shape(source)
    fingerprint = ocp._native_shape_fingerprint(source)
    evidence = ocp.classify_native_defects(source)
    assert not before.accepted_under_policy
    assert before.free_edge_ids
    assert before.solid_count == 0
    result = ocp.sew_selected_native_boundaries(
        source, evidence, selected_wire_pairs(evidence),
    )
    assert result.after.accepted_under_policy
    assert result.after.surface_types == before.surface_types
    assert result.after.face_count == before.face_count
    assert result.after.surface_area_mm2 == pytest.approx(before.surface_area_mm2)
    assert result.source_fingerprint_sha256 == fingerprint
    assert result.selected_wire_pairs == selected_wire_pairs(evidence)
    assert result.selected_wire_ids == tuple(range(len(evidence.free_boundary_wires)))
    assert any("BRepBuilderAPI_Sewing" in operation for operation in result.operations)
    assert ocp._native_shape_fingerprint(source) == fingerprint
    exported = ocp.export_checked_step(result.candidate, tmp_path / "selected.step")
    assert exported.after_roundtrip.accepted_under_policy


def test_selected_native_sewing_refuses_partial_or_stale_evidence_without_mutation():
    source = disconnected_faces(box())
    report = ocp.classify_native_defects(source)
    fingerprint = ocp._native_shape_fingerprint(source)

    with pytest.raises(RepairRejected, match="every free-boundary wire"):
        ocp.sew_selected_native_boundaries(source, report, ((report.free_boundary_wires[0].wire_id,
                                                              report.free_boundary_wires[1].wire_id),))
    with pytest.raises(RepairRejected, match="does not match"):
        ocp.sew_selected_native_boundaries(box(), report, ((0, 1),))
    assert ocp._native_shape_fingerprint(source) == fingerprint


def test_selected_native_sewing_obeys_named_tolerance_policy_without_publishing_candidate():
    source = disconnected_faces(box())
    policy = ocp.KernelPolicy(precision_mm=1e-10, maximum_tolerance_mm=1e-9)
    report = ocp.classify_native_defects(source, policy)
    fingerprint = ocp._native_shape_fingerprint(source)

    with pytest.raises(RepairRejected, match="did not yield one unambiguous shell"):
        ocp.sew_selected_native_boundaries(
            source, report, selected_wire_pairs(report), policy,
        )
    assert ocp._native_shape_fingerprint(source) == fingerprint


def test_selected_native_sewing_preserves_unselected_nearby_solid():
    untouched = BRepPrimAPI_MakeBox(gp_Pnt(10.0001, 0, 0), 10, 10, 10).Shape()
    source = compound([disconnected_faces(box()), untouched])
    policy = ocp.KernelPolicy(expected_solids=2)
    report = ocp.classify_native_defects(source, policy)
    fingerprint = ocp._native_shape_fingerprint(source)

    result = ocp.sew_selected_native_boundaries(source, report, selected_wire_pairs(report), policy)

    assert result.after.accepted_under_policy
    assert result.after.solid_volumes_mm3 == pytest.approx((1000, 1000))
    assert result.after.surface_area_mm2 == pytest.approx(1200)
    assert ocp._native_shape_fingerprint(source) == fingerprint


def test_generic_native_repair_never_auto_selects_sewing_candidates():
    source = disconnected_faces(box())
    fingerprint = ocp._native_shape_fingerprint(source)

    with pytest.raises(RepairRejected, match="explicit classifier-backed selection"):
        ocp.repair_shape(source)
    assert ocp._native_shape_fingerprint(source) == fingerprint


def test_valid_part_is_not_needlessly_healed():
    source = box()
    result = ocp.repair_shape(source)
    assert result.operations == ("No repair needed",)
    assert not result.candidate.IsSame(source)
    assert result.after == result.before


def test_existing_cavity_is_preserved(tmp_path):
    outer = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    inner = BRepPrimAPI_MakeBox(gp_Pnt(2, 2, 2), 6, 6, 6).Shape()
    shape = BRepAlgoAPI_Cut(outer, inner).Shape()
    audit = ocp.audit_shape(shape)
    assert audit.accepted_under_policy, audit.acceptance_reasons
    assert audit.shell_count == 2
    assert audit.solid_count == 1
    assert audit.solid_volumes_mm3 == pytest.approx((784,))
    result = ocp.repair_shape(shape)
    exported = ocp.export_checked_step(result.candidate, tmp_path / "cavity.stp")
    assert exported.after_roundtrip.shell_count == 2
    assert exported.after_roundtrip.solid_volumes_mm3 == pytest.approx((784,))


def test_multiple_solids_need_explicit_policy():
    shape = compound([box(), BRepPrimAPI_MakeBox(gp_Pnt(20, 0, 0), 5, 5, 5).Shape()])
    assert not ocp.audit_shape(shape).accepted_under_policy
    report = ocp.audit_shape(shape, ocp.KernelPolicy(expected_solids=2))
    assert report.accepted_under_policy, report.acceptance_reasons


def test_ambiguous_disconnected_shells_not_auto_grouped():
    parts = [box(), BRepPrimAPI_MakeBox(gp_Pnt(20, 0, 0), 5, 5, 5).Shape()]
    source = compound([disconnected_faces(part) for part in parts])
    with pytest.raises(RepairRejected, match="explicit classifier-backed selection"):
        ocp.repair_shape(source, ocp.KernelPolicy(expected_solids=2))


def test_missing_face_not_silently_capped(tmp_path):
    shape = compound(ocp._shapes(box(), TopAbs_FACE)[:-1])
    with pytest.raises(RepairRejected, match="explicit classifier-backed selection"):
        ocp.repair_shape(shape)
    target = tmp_path / "not-certified.step"
    with pytest.raises(ExportRejected):
        ocp.export_checked_step(shape, target)
    assert not target.exists()
    assert not list(tmp_path.glob(".cad-integrity-*"))


def test_unowned_vertex_is_not_discarded():
    stray = BRepBuilderAPI_MakeVertex(gp_Pnt(30, 0, 0)).Shape()
    shape = compound([disconnected_faces(box()), stray])
    assert ocp.audit_shape(shape).unowned_vertex_ids
    with pytest.raises(RepairRejected, match="unowned"):
        ocp.repair_shape(shape)


def test_disabled_interference_check_cannot_pass_gate():
    report = ocp.audit_shape(box(), ocp.KernelPolicy(run_self_interference_check=False))
    assert report.self_interference_check_passed is None
    assert not report.accepted_under_policy


def test_tolerance_budget_enforced():
    report = ocp.audit_shape(box(), ocp.KernelPolicy(precision_mm=1e-10, maximum_tolerance_mm=1e-9))
    assert report.maximum_entity_tolerance_mm > 1e-9
    assert not report.accepted_under_policy


def test_export_does_not_overwrite(tmp_path):
    target = tmp_path / "existing.step"
    target.write_text("Keep me")
    with pytest.raises(FileExistsError):
        ocp.export_checked_step(box(), target)
    assert target.read_text() == "Keep me"


def test_bad_roundtrip_never_publishes(tmp_path, monkeypatch):
    def corrupt_writer(shape, target):
        target.write_text("This is not a STEP file")
    monkeypatch.setattr(ocp, "_write_native", corrupt_writer)
    target = tmp_path / "bad.step"
    with pytest.raises(KernelOperationFailed):
        ocp.export_checked_step(box(), target)
    assert not target.exists()
    assert not list(tmp_path.glob(".cad-integrity-*"))


def test_roundtrip_geometry_drift_is_rejected(tmp_path, monkeypatch):
    original_reader = ocp.read_step
    def different_solid(path, **kwargs):
        document = original_reader(path, **kwargs)
        return replace(document, shape=BRepPrimAPI_MakeBox(20, 10, 10).Shape())
    monkeypatch.setattr(ocp, "read_step", different_solid)
    target = tmp_path / "bad.step"
    with pytest.raises(ExportRejected, match="area"):
        ocp.export_checked_step(box(), target)
    assert not target.exists()


def test_input_validation(tmp_path):
    with pytest.raises(FileNotFoundError):
        ocp.read_step(tmp_path / "absent.step")
    wrong = tmp_path / "wrong.txt"
    wrong.write_text("no")
    with pytest.raises(ValueError):
        ocp.read_step(wrong)
    bad = tmp_path / "bad.step"
    bad.write_text("not STEP")
    with pytest.raises(ResourceLimitExceeded):
        ocp.read_step(bad, max_bytes=2)
    with pytest.raises(KernelOperationFailed):
        ocp.read_step(bad)
    with pytest.raises(KernelOperationFailed):
        ocp.audit_shape(TopoDS_Shape())


def test_display_mesh_keeps_face_provenance_and_orients_triangles():
    display = ocp.tessellate_for_display(box())
    assert len(display.mesh.triangles) == 12
    assert len(display.triangle_face_ids) == 12
    assert set(display.triangle_face_ids) == set(range(6))
    assert len(display.mesh.vertices) == 24  # per-face vertices: intentionally NOT stitched
    assert not display.triangle_face_ids.flags.writeable
    p = display.mesh.vertices[display.mesh.triangles]
    cross = np.cross(p[:, 1]-p[:, 0], p[:, 2]-p[:, 0])
    assert np.all(np.einsum("ij,ij->i", cross, p.mean(axis=1)-np.array((5,5,5))) > 0)
    with pytest.raises(ResourceLimitExceeded):
        ocp.tessellate_for_display(box(), max_triangles=1)


def test_edge_overlay_samples_actual_curves():
    shape = disconnected_faces(BRepPrimAPI_MakeCylinder(2, 5).Shape())
    report = ocp.audit_shape(shape)
    lines = ocp.sample_edge_polylines(shape, report.free_edge_ids, samples=10)
    assert len(lines) == len(report.free_edge_ids)
    assert all(line.shape == (10, 3) for line in lines)
    with pytest.raises(IndexError):
        ocp.sample_edge_polylines(shape, (1000,))


def test_local_pipeline_preserves_source_and_reports_hash(tmp_path):
    source = tmp_path / "original.step"
    ocp.export_checked_step(box(), source)
    original_bytes = source.read_bytes()
    target = tmp_path / "checked.step"
    events = []
    result = ocp.run_step_pipeline(source, target, on_event=events.append)
    assert source.read_bytes() == original_bytes
    assert result["export"].after_roundtrip.accepted_under_policy
    assert result["before"].accepted_under_policy
    assert result["normalized_length_unit"] == "mm"
    assert result["import_scope"].startswith("OCCT_imported_shape")
    with pytest.raises(ValueError, match="differ"):
        ocp.run_step_pipeline(source, source)


def test_import_converts_metres_to_millimetres(tmp_path):
    path = tmp_path / "metres.step"
    ocp.export_checked_step(box(), path)
    text = path.read_text()
    assert "SI_UNIT(.MILLI.,.METRE.)" in text
    # Same numeric coordinates, now declared in metres by the STEP unit entity.
    path.write_text(text.replace("SI_UNIT(.MILLI.,.METRE.)", "SI_UNIT($,.METRE.)"))
    document = ocp.read_step(path)
    report = ocp.audit_shape(document.shape)
    assert report.solid_volumes_mm3 == pytest.approx((1e12,))
    assert report.surface_area_mm2 == pytest.approx(6e8)
    assert document.source_unit_names == ("metre",)


def test_overlapping_solids_fail_interference_gate():
    shape = compound([box(), BRepPrimAPI_MakeBox(gp_Pnt(5, 5, 5), 10, 10, 10).Shape()])
    report = ocp.audit_shape(shape, ocp.KernelPolicy(expected_solids=2))
    assert not report.accepted_under_policy
    assert report.self_interference_check_passed is False
