from pathlib import Path

import pytest

from cad_integrity.adapters.ocp import ExportReport, KernelPolicy, KernelReport


def _accepted_report() -> KernelReport:
    return KernelReport(
        kernel_binding_version="7.9.3",
        valid_by_brepcheck=True,
        self_interference_check_passed=True,
        vertex_count=8,
        edge_count=12,
        face_count=6,
        shell_count=1,
        solid_count=1,
        free_edge_ids=(),
        nonmanifold_edge_ids=(),
        unowned_edge_ids=(),
        unowned_vertex_ids=(),
        degenerate_edge_count=0,
        shells_closed_and_oriented=True,
        every_face_belongs_to_solid=True,
        solid_volumes_mm3=(1000.0,),
        surface_area_mm2=600.0,
        maximum_entity_tolerance_mm=1e-6,
        surface_types=(("GeomAbs_Plane", 6),),
        acceptance_reasons=(),
        accepted_under_policy=True,
    )


def test_step_decision_brief_projects_accepted_evidence_for_people(tmp_path: Path) -> None:
    from cad_integrity.gradio_app import project_step_evidence

    before = _accepted_report()
    export = ExportReport(tmp_path / "checked.step", "a" * 64, before, before)
    result = {
        "source_sha256": "b" * 64,
        "source_unit_names": ("millimetre",),
        "normalized_length_unit": "mm",
        "import_scope": "OCCT_imported_shape_not_unmodified_generator_internal_state",
        "policy": KernelPolicy(),
        "before": before,
        "operations": ("No repair needed",),
        "export": export,
        "limitations": ("No manufacturing/structural certification",),
    }

    brief = project_step_evidence(result)

    assert brief.outcome == "Candidate passed configured kernel checks"
    assert brief.candidate_available
    assert "Before / after" in brief.markdown
    assert "1,000" in brief.markdown
    assert "No manufacturing/structural certification" in brief.markdown


def test_build_app_exposes_native_and_polygonal_labs() -> None:
    from cad_integrity.gradio_app import build_app

    app = build_app()
    labels = {
        component.get("props", {}).get("label")
        for component in app.get_config_file()["components"]
    }

    assert "Local STEP workbench" in labels
    assert "Polygonal fixture lab" in labels
    assert "Advanced repair policy" in labels


def test_advanced_controls_build_a_validated_kernel_policy() -> None:
    from cad_integrity.gradio_app import kernel_policy_from_controls

    policy = kernel_policy_from_controls(1e-5, 1e-3, 2, False, 0.02, 0.03, True)

    assert policy == KernelPolicy(
        precision_mm=1e-5,
        maximum_tolerance_mm=1e-3,
        expected_solids=2,
        run_self_interference_check=False,
        max_relative_area_change=0.02,
        max_relative_volume_change=0.03,
        allow_face_count_change=True,
    )
    with pytest.raises(ValueError, match="cannot exceed"):
        kernel_policy_from_controls(1e-2, 1e-3, 1, True, 1e-4, 1e-4, False)


def test_step_workbench_returns_a_checked_download_and_human_brief(tmp_path: Path) -> None:
    pytest.importorskip("OCP")
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    from cad_integrity.adapters.ocp import export_checked_step
    from cad_integrity.gradio_app import ArtifactStore, run_step_workbench

    source = tmp_path / "original.step"
    export_checked_step(BRepPrimAPI_MakeBox(10, 10, 10).Shape(), source)
    original_bytes = source.read_bytes()

    outcome = run_step_workbench(source, KernelPolicy(), artifact_store=ArtifactStore(tmp_path / "artifacts"))

    assert source.read_bytes() == original_bytes
    assert outcome.candidate_step is not None and outcome.candidate_step.is_file()
    assert outcome.decision_brief.candidate_available
    assert outcome.original_figure is not None
    assert outcome.candidate_figure is not None
    assert outcome.markdown_path.is_file()
    assert outcome.json_path.is_file()


def test_step_workbench_withholds_candidate_after_policy_refusal(tmp_path: Path) -> None:
    pytest.importorskip("OCP")
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    from cad_integrity.adapters.ocp import export_checked_step
    from cad_integrity.gradio_app import ArtifactStore, run_step_workbench

    source = tmp_path / "one-solid.step"
    export_checked_step(BRepPrimAPI_MakeBox(10, 10, 10).Shape(), source)

    outcome = run_step_workbench(
        source,
        KernelPolicy(expected_solids=2),
        artifact_store=ArtifactStore(tmp_path / "artifacts"),
    )

    assert outcome.decision_brief.outcome == "Repair rejected"
    assert not outcome.decision_brief.candidate_available
    assert outcome.candidate_step is None
    assert outcome.candidate_figure is None
    assert outcome.markdown_path.is_file()
    assert outcome.json_path.is_file()


def test_polygonal_fixture_lab_repairs_the_qualified_detached_cap(tmp_path: Path) -> None:
    from cad_integrity.gradio_app import ArtifactStore, run_polygonal_fixture

    outcome = run_polygonal_fixture(
        "01_detached_reversed_cap", artifact_store=ArtifactStore(tmp_path / "artifacts")
    )

    assert outcome.decision_brief.outcome == "Candidate passed configured combinatorial checks"
    assert outcome.candidate_figure is not None
    assert outcome.markdown_path.is_file()
    assert outcome.json_path.is_file()
