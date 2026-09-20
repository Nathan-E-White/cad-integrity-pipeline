from pathlib import Path

import pytest

from cad_integrity.adapters.ocp import ExportReport, KernelPolicy, KernelReport


def _artifact_path(outcome: object, role: str) -> Path:
    release = outcome.release
    assert release is not None
    artifacts = (release.source, *( () if release.candidate is None else (release.candidate,)), *release.derived)
    return next(artifact.path for artifact in artifacts if artifact.role == role)


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


def test_build_app_exposes_mesh_lab_before_the_step_workbench() -> None:
    from cad_integrity.gradio_app import build_app

    app = build_app()
    components = app.get_config_file()["components"]
    labels = {component.get("props", {}).get("label") for component in components}
    tab_labels = [
        component["props"]["label"]
        for component in components
        if component["type"] == "tabitem"
    ]

    assert tab_labels[0] == "Mesh Lab"
    assert tab_labels.index("Mesh Lab") < tab_labels.index("Local STEP workbench")
    assert tab_labels.index("Examples") < tab_labels.index("Upload your NPZ")
    assert "Local STEP workbench" in labels
    assert "Mesh Lab" in labels
    assert "Upload your NPZ" in labels
    assert "Examples" in labels
    assert "Choose an example" in labels
    assert "Advanced repair policy" in labels
    assert "Restricted polygonal NPZ" in labels
    assert "Weld tolerance (mm)" in labels
    assert "Polygonal fixture lab" not in labels
    example_picker = next(
        component for component in components
        if component.get("props", {}).get("label") == "Choose an example"
    )
    assert example_picker["props"]["choices"] == [
        ("Clean baseline", "00_clean_boss"),
        ("Detached reversed cap", "01_detached_reversed_cap"),
        ("Welded but unoriented", "01_welded_not_oriented"),
        ("Already repaired cap", "01_repaired_cap"),
        ("Pinched vertex", "02_pinched_vertex"),
    ]
    tab_groups = [component for component in components if component["type"] == "tabs"]
    assert tab_groups[0]["props"]["selected"] == 0


def test_main_uses_gradio_default_theme(monkeypatch: pytest.MonkeyPatch) -> None:
    from cad_integrity import gradio_app

    launch_arguments: dict[str, object] = {}

    class FakeApp:
        def launch(self, **kwargs: object) -> None:
            launch_arguments.update(kwargs)

    monkeypatch.setattr(gradio_app, "build_app", lambda: FakeApp())

    gradio_app.main()

    assert launch_arguments == {
        "server_name": "127.0.0.1",
        "share": False,
    }


def test_build_app_uses_full_width_focused_diagnostic_tabs() -> None:
    """Diagnostic plots need one useful viewport rather than a clipped pair."""
    from cad_integrity.gradio_app import build_app

    app = build_app()
    config = app.get_config_file()
    plot_labels = {
        component.get("props", {}).get("label")
        for component in config["components"]
        if component["type"] == "plot"
    }

    assert app.fill_width
    assert plot_labels == {
        "Original diagnostic view",
        "Candidate diagnostic view",
        "Original mesh view",
        "Candidate mesh view",
    }
    assert sum(
        component.get("props", {}).get("value")
        == "## No candidate published\nThe audit did not publish a candidate for review or download."
        for component in config["components"]
    ) == 2


def test_mesh_lab_projects_typed_audit_while_retained_brief_keeps_forensics(tmp_path: Path) -> None:
    from gradio_topologicaldeltaaudit import TopologicalDeltaAuditData
    from gradio_verificationgrid import VerificationGridData
    from cad_integrity.gradio_app import ArtifactStore, _polygonal_ui_projection, run_polygonal_fixture

    outcome = run_polygonal_fixture(
        "01_detached_reversed_cap", artifact_store=ArtifactStore(tmp_path / "artifacts")
    )
    audit, verification = _polygonal_ui_projection(outcome)[1:3]
    retained_brief = outcome.decision_brief.markdown

    assert isinstance(audit, TopologicalDeltaAuditData)
    assert any(row.entity == "Boundary edges" and row.delta == "−128" for row in audit.rows)
    assert isinstance(verification, VerificationGridData)
    assert verification.summary == "3 / 3 pass"
    for heading in ("## Evidence", "## Limitations", "## Completion", "## Availability"):
        assert heading in retained_brief
    assert "Input SHA-256" in retained_brief
    assert "Candidate canonical-array fingerprint" in retained_brief
    assert "Length unit" in retained_brief


def test_mesh_lab_verification_grid_keeps_failed_and_unavailable_checks_visible() -> None:
    from gradio_verificationgrid import VerificationGridData
    from cad_integrity.gradio_app import _polygonal_ui_projection
    from cad_integrity.workbench_results import (
        CheckResult,
        CheckState,
        Completion,
        DecisionBrief,
        WorkbenchOutcome,
    )

    outcome = WorkbenchOutcome(
        Completion.FAILED,
        (
            CheckResult("Polygonal-cell admission", CheckState.FAILED, "Rejected cells"),
            CheckResult("Homology evaluation", CheckState.UNAVAILABLE, "Budget exhausted"),
        ),
        (),
        DecisionBrief("Mesh requires review", False, "## Decision\nMesh requires review."),
        None,
        None,
        None,
    )

    verification = _polygonal_ui_projection(outcome)[2]

    assert isinstance(verification, VerificationGridData)
    checks = {check.name: check for group in verification.groups for check in group.checks}
    assert checks["polygonal-cell_admission"].state == "failed"
    assert checks["polygonal-cell_admission"].detail == "Rejected cells"
    assert checks["homology_evaluation"].state == "inconclusive"
    assert checks["homology_evaluation"].detail == "Budget exhausted"


def test_mesh_lab_and_retained_brief_share_one_verification_ledger(tmp_path: Path) -> None:
    from cad_integrity.gradio_app import ArtifactStore, _polygonal_ui_projection, run_polygonal_fixture
    from cad_integrity.workbench_results import verification_markdown

    outcome = run_polygonal_fixture(
        "02_pinched_vertex", artifact_store=ArtifactStore(tmp_path / "artifacts")
    )
    ledger = verification_markdown(outcome.checks)

    verification = _polygonal_ui_projection(outcome)[2]
    assert verification.summary == "0 / 1 pass"
    assert ledger in outcome.decision_brief.markdown


def test_mesh_lab_example_and_upload_actions_share_one_result_projection(tmp_path: Path) -> None:
    from gradio_topologicaldeltaaudit import TopologicalDeltaAuditData
    from gradio_verificationgrid import VerificationGridData
    from cad_integrity.gradio_app import (
        ArtifactStore,
        _fixture_ui_action,
        _polygonal_upload_ui_action,
    )

    source = (Path(__file__).resolve().parents[1] / "examples" / "pathological-mesh-fixtures"
              / "meshes" / "01_detached_reversed_cap.npz")
    example_result = _fixture_ui_action(
        "01_detached_reversed_cap", artifact_store=ArtifactStore(tmp_path / "example")
    )
    upload_result = _polygonal_upload_ui_action(
        str(source), True, 0.0738347, 0.0738347, True,
        artifact_store=ArtifactStore(tmp_path / "upload"),
    )

    for source_name, result in (("Example: Detached reversed cap", example_result), ("Uploaded NPZ", upload_result)):
        assert len(result) == 10
        assert source_name in result[0]
        assert isinstance(result[1], TopologicalDeltaAuditData)
        assert isinstance(result[2], VerificationGridData)
        assert all(isinstance(output, str) and Path(output).is_file() for output in result[-4:])


def test_mesh_lab_projects_typed_delta_audit_and_verification_grid(tmp_path: Path) -> None:
    """The live fixture action drives the two engineering projections, not Markdown."""
    from gradio_topologicaldeltaaudit import TopologicalDeltaAuditData
    from gradio_verificationgrid import VerificationGridData

    from cad_integrity.gradio_app import ArtifactStore, _fixture_ui_action, build_app

    result = _fixture_ui_action(
        "01_detached_reversed_cap", artifact_store=ArtifactStore(tmp_path / "artifacts")
    )
    audit, verification = result[1:3]

    assert isinstance(audit, TopologicalDeltaAuditData)
    assert any(row.entity == "Boundary edges" and row.delta == "−128" for row in audit.rows)
    assert isinstance(verification, VerificationGridData)
    assert verification.summary == "3 / 3 pass"
    component_types = {component["type"] for component in build_app().get_config_file()["components"]}
    assert {"topologicaldeltaaudit", "verificationgrid"} <= component_types


def test_mesh_figure_has_a_deterministic_diagnostic_presentation() -> None:
    pytest.importorskip("plotly")
    from cad_integrity.fixtures import tetrahedron
    from cad_integrity.visualization import mesh_figure

    figure = mesh_figure(tetrahedron(), title="Original fixture")
    repeated = mesh_figure(tetrahedron(), title="Original fixture")

    assert figure.layout.height == 520
    assert figure.layout.scene.camera.projection.type == "orthographic"
    assert figure.layout.scene.camera.eye.to_plotly_json() == repeated.layout.scene.camera.eye.to_plotly_json()
    assert figure.layout.scene.bgcolor == "#f6f8fb"
    assert figure.layout.annotations[0].text == "4 triangles · No flagged edges in this audit"
    assert figure.data[0].lighting.ambient == 0.55


def test_mesh_figure_expands_the_camera_for_an_elongated_bounding_box() -> None:
    pytest.importorskip("plotly")
    import numpy as np

    from cad_integrity.fixtures import tetrahedron
    from cad_integrity.models import TriangleMesh
    from cad_integrity.visualization import mesh_figure

    compact = tetrahedron()
    elongated = TriangleMesh(compact.vertices * np.array((10.0, 1.0, 1.0)), compact.triangles)

    compact_eye = mesh_figure(compact).layout.scene.camera.eye
    elongated_eye = mesh_figure(elongated).layout.scene.camera.eye

    assert elongated_eye.x > compact_eye.x


def test_candidate_display_replaces_an_absent_candidate_with_an_explicit_notice() -> None:
    import gradio as gr

    from cad_integrity.gradio_app import candidate_display

    plot, notice = candidate_display(None)

    assert isinstance(plot, gr.Plot)
    assert not plot.visible
    assert isinstance(notice, gr.Markdown)
    assert notice.visible
    assert "No candidate published" in notice.value


def test_main_announces_the_loopback_url_before_serving(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from cad_integrity import gradio_app

    calls: list[dict[str, object]] = []

    class FakeApp:
        def launch(self, **kwargs: object) -> None:
            calls.append(kwargs)

    monkeypatch.setattr(gradio_app, "build_app", FakeApp)

    gradio_app.main()

    assert "http://127.0.0.1:7860" in capsys.readouterr().out
    assert calls == [{"server_name": "127.0.0.1", "share": False}]


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


def test_polygonal_upload_controls_make_an_explicit_stitching_policy() -> None:
    from cad_integrity.gradio_app import polygonal_policy_from_controls
    from cad_integrity.repair import WeldPolicy

    policy = polygonal_policy_from_controls(True, 0.1, 0.05, False)

    assert policy.weld == WeldPolicy(0.1, 0.05)
    assert not policy.synchronize_orientation

    with pytest.raises(ValueError, match="max_displacement"):
        polygonal_policy_from_controls(True, 0.01, 0.02, True)


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
    assert _artifact_path(outcome, "candidate.step").is_file()
    assert outcome.decision_brief.candidate_available
    assert outcome.original_figure is not None
    assert outcome.candidate_figure is not None
    assert _artifact_path(outcome, "decision-brief.md").is_file()
    assert _artifact_path(outcome, "evidence.json").is_file()
    assert "Input SHA-256" in outcome.decision_brief.markdown


@pytest.mark.parametrize(
    ("fixture_name", "outcome_text", "candidate_expected"),
    [
        ("00_clean_boss", "Candidate passed configured combinatorial checks", True),
        ("01_welded_not_oriented", "Candidate passed configured combinatorial checks", True),
        ("02_pinched_vertex", "Fixture requires review", False),
    ],
)
def test_polygonal_fixture_lab_qualifies_each_distinct_fixture_outcome(
    tmp_path: Path, fixture_name: str, outcome_text: str, candidate_expected: bool
) -> None:
    from cad_integrity.gradio_app import ArtifactStore, run_polygonal_fixture

    outcome = run_polygonal_fixture(fixture_name, artifact_store=ArtifactStore(tmp_path / "artifacts"))

    assert outcome.decision_brief.outcome == outcome_text
    assert (outcome.candidate_figure is not None) is candidate_expected
    if candidate_expected:
        assert "Candidate canonical-array fingerprint" in outcome.decision_brief.markdown
    else:
        assert "No candidate artifact was produced" in outcome.decision_brief.markdown


def test_step_workbench_keeps_evidence_when_display_rendering_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("OCP")
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    from cad_integrity.adapters.ocp import export_checked_step
    from cad_integrity.errors import ResourceLimitExceeded
    from cad_integrity.gradio_app import ArtifactStore, run_step_workbench

    source = tmp_path / "original.step"
    export_checked_step(BRepPrimAPI_MakeBox(10, 10, 10).Shape(), source)

    def unavailable_display(*_args: object, **_kwargs: object) -> None:
        raise ResourceLimitExceeded("Display tessellation exceeds the triangle budget")

    monkeypatch.setattr("cad_integrity.gradio_app._native_figure", unavailable_display)
    outcome = run_step_workbench(source, KernelPolicy(), artifact_store=ArtifactStore(tmp_path / "artifacts"))

    assert outcome.decision_brief.candidate_available
    assert _artifact_path(outcome, "candidate.step").is_file()
    assert outcome.original_figure is None
    assert outcome.candidate_figure is None
    assert "## Display" in outcome.decision_brief.markdown
    assert _artifact_path(outcome, "decision-brief.md").is_file()
    assert _artifact_path(outcome, "evidence.json").is_file()


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
    assert outcome.release is not None and outcome.release.candidate is None
    assert outcome.candidate_figure is None
    assert _artifact_path(outcome, "decision-brief.md").is_file()
    assert _artifact_path(outcome, "evidence.json").is_file()


def test_polygonal_fixture_lab_repairs_the_qualified_detached_cap(tmp_path: Path) -> None:
    from cad_integrity.gradio_app import ArtifactStore, run_polygonal_fixture

    outcome = run_polygonal_fixture(
        "01_detached_reversed_cap", artifact_store=ArtifactStore(tmp_path / "artifacts")
    )

    assert outcome.decision_brief.outcome == "Candidate passed configured combinatorial checks"
    assert outcome.candidate_figure is not None
    assert _artifact_path(outcome, "decision-brief.md").is_file()
    assert _artifact_path(outcome, "evidence.json").is_file()
    assert "Input SHA-256" in outcome.decision_brief.markdown
    assert "Weld tolerance" in outcome.decision_brief.markdown
    assert "Candidate canonical-array fingerprint" in outcome.decision_brief.markdown


def test_polygonal_upload_replays_an_admitted_npz_through_the_stitching_policy(tmp_path: Path) -> None:
    import json

    from cad_integrity.gradio_app import ArtifactStore, run_polygonal_upload
    from cad_integrity.pipeline import RepairPolicy
    from cad_integrity.repair import WeldPolicy

    source = (Path(__file__).resolve().parents[1] / "examples" / "pathological-mesh-fixtures"
              / "meshes" / "01_detached_reversed_cap.npz")
    outcome = run_polygonal_upload(
        source,
        RepairPolicy(weld=WeldPolicy(0.0738346971281118, 0.0738346971281118)),
        artifact_store=ArtifactStore(tmp_path / "artifacts"),
    )

    assert outcome.decision_brief.outcome == "Candidate passed configured combinatorial checks"
    assert outcome.candidate_figure is not None
    assert _artifact_path(outcome, "decision-brief.md").is_file()
    assert _artifact_path(outcome, "evidence.json").is_file()
    assert "Uploaded NPZ" in outcome.decision_brief.markdown
    assert "uploaded NPZ array contract" in outcome.decision_brief.markdown
    payload = json.loads(_artifact_path(outcome, "evidence.json").read_text())
    assert payload["evidence"]["source_kind"] == "uploaded_restricted_npz"
    assert len(payload["evidence"]["source_sha256"]) == 64


def test_polygonal_upload_rejects_extra_npz_members_before_analysis(tmp_path: Path) -> None:
    import numpy as np

    from cad_integrity.gradio_app import ArtifactStore, run_polygonal_upload
    from cad_integrity.pipeline import RepairPolicy

    upload = tmp_path / "unexpected-member.npz"
    np.savez(
        upload,
        vertices=np.zeros((3, 3)),
        triangles=np.array(((0, 1, 2),), dtype=np.int64),
        length_unit=np.array("mm"),
        unexpected=np.array(1),
    )

    outcome = run_polygonal_upload(upload, RepairPolicy(), artifact_store=ArtifactStore(tmp_path / "artifacts"))

    assert outcome.completion == "failed"
    assert outcome.release is not None
    assert outcome.release.source.path.is_file()
    assert outcome.checks[0].status == "FAILED"
    assert "must contain only vertices" in outcome.diagnostics[0].message


def test_polygonal_upload_releases_a_coherent_candidate_that_requires_review(tmp_path: Path) -> None:
    from cad_integrity.gradio_app import ArtifactStore, run_polygonal_upload
    from cad_integrity.pipeline import RepairPolicy

    source = (Path(__file__).resolve().parents[1] / "examples" / "pathological-mesh-fixtures"
              / "meshes" / "01_detached_reversed_cap.npz")
    outcome = run_polygonal_upload(
        source,
        RepairPolicy(synchronize_orientation=False),
        artifact_store=ArtifactStore(tmp_path / "artifacts"),
    )

    assert outcome.decision_brief.outcome == "Uploaded polygonal input requires review"
    assert outcome.completion == "completed"
    assert outcome.candidate_figure is not None
    assert outcome.release is not None
    assert outcome.release.source.path.is_file()
    assert outcome.release.candidate is not None
    assert outcome.release.candidate.role == "candidate.npz"
    assert outcome.release.candidate.path.is_file()
    assert "Completion: Completed" in outcome.decision_brief.markdown
    assert "Needs review" in outcome.decision_brief.markdown


def test_polygonal_fixture_releases_source_and_retained_evidence(tmp_path: Path) -> None:
    from cad_integrity.gradio_app import ArtifactStore, run_polygonal_fixture

    outcome = run_polygonal_fixture(
        "01_detached_reversed_cap", artifact_store=ArtifactStore(tmp_path / "artifacts")
    )

    assert outcome.release is not None
    assert outcome.release.source.role == "source.npz"
    assert outcome.release.source.path.is_file()
    assert {artifact.role for artifact in outcome.release.derived} == {
        "decision-brief.md", "evidence.json"
    }
    assert "Link active until" in outcome.decision_brief.markdown


def test_polygonal_fixture_retains_source_when_evidence_persistence_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cad_integrity import gradio_app

    def disk_full(*args: object, **kwargs: object) -> Path:
        raise OSError("simulated disk full")

    monkeypatch.setattr(gradio_app, "_write_evidence_artifacts", disk_full)

    outcome = gradio_app.run_polygonal_fixture(
        "00_clean_boss", artifact_store=gradio_app.ArtifactStore(tmp_path / "artifacts")
    )

    assert outcome.completion == "incomplete"
    assert outcome.release is not None
    assert outcome.release.source.path.is_file()
    assert outcome.release.candidate is not None
    assert {artifact.role for artifact in outcome.release.derived} == set()
    assert outcome.diagnostics[-1].stage == "evidence persistence"
    assert "decision-brief.md" in outcome.diagnostics[-1].message


def test_polygonal_fixture_reports_source_staging_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cad_integrity import gradio_app

    def disk_full(*args: object, **kwargs: object) -> None:
        raise OSError("simulated disk full")

    monkeypatch.setattr(gradio_app.shutil, "copyfile", disk_full)

    outcome = gradio_app.run_polygonal_fixture(
        "00_clean_boss", artifact_store=gradio_app.ArtifactStore(tmp_path / "artifacts")
    )

    assert outcome.completion == "failed"
    assert outcome.release is None
    assert outcome.diagnostics[0].stage == "Fixture source staging"
    assert outcome.diagnostics[0].message == "simulated disk full"


def test_polygonal_fixture_retains_markdown_when_json_persistence_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cad_integrity import gradio_app

    write_artifact = gradio_app._write_evidence_artifacts
    calls = 0

    def fail_second_write(path: Path, content: str) -> Path:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated disk full")
        return write_artifact(path, content)

    monkeypatch.setattr(gradio_app, "_write_evidence_artifacts", fail_second_write)

    outcome = gradio_app.run_polygonal_fixture(
        "00_clean_boss", artifact_store=gradio_app.ArtifactStore(tmp_path / "artifacts")
    )

    assert outcome.completion == "incomplete"
    assert outcome.release is not None
    assert {artifact.role for artifact in outcome.release.derived} == {"decision-brief.md"}
    assert not (outcome.release.source.path.parent / "evidence.json").exists()
    assert "evidence.json" in outcome.diagnostics[-1].message


def test_polygonal_upload_reports_source_staging_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cad_integrity import gradio_app
    from cad_integrity.pipeline import RepairPolicy

    source = (Path(__file__).resolve().parents[1] / "examples" / "pathological-mesh-fixtures"
              / "meshes" / "00_clean_boss.npz")

    def disk_full(*args: object, **kwargs: object) -> None:
        raise OSError("simulated disk full")

    monkeypatch.setattr(gradio_app.shutil, "copyfile", disk_full)

    outcome = gradio_app.run_polygonal_upload(
        source, RepairPolicy(), artifact_store=gradio_app.ArtifactStore(tmp_path / "artifacts")
    )

    assert outcome.completion == "failed"
    assert outcome.release is None
    assert outcome.diagnostics[0].stage == "Polygonal source staging"


def test_step_workbench_reports_source_staging_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cad_integrity import gradio_app

    source = tmp_path / "source.step"
    source.write_text("ISO-10303-21;", encoding="utf-8")

    def disk_full(*args: object, **kwargs: object) -> None:
        raise OSError("simulated disk full")

    monkeypatch.setattr(gradio_app.shutil, "copyfile", disk_full)

    outcome = gradio_app.run_step_workbench(
        source, gradio_app.KernelPolicy(), artifact_store=gradio_app.ArtifactStore(tmp_path / "artifacts")
    )

    assert outcome.completion == "failed"
    assert outcome.release is None
    assert outcome.diagnostics[0].stage == "STEP source staging"


def test_step_workbench_retains_source_when_candidate_persistence_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("OCP")
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    from cad_integrity import gradio_app
    from cad_integrity.adapters.ocp import export_checked_step

    source = tmp_path / "source.step"
    export_checked_step(BRepPrimAPI_MakeBox(10, 10, 10).Shape(), source)

    def disk_full(*args: object, **kwargs: object) -> None:
        raise OSError("simulated disk full")

    monkeypatch.setattr("cad_integrity.adapters.ocp.run_step_pipeline", disk_full)

    outcome = gradio_app.run_step_workbench(
        source, gradio_app.KernelPolicy(), artifact_store=gradio_app.ArtifactStore(tmp_path / "artifacts")
    )

    assert outcome.completion == "incomplete"
    assert outcome.release is not None
    assert outcome.release.source.path.is_file()
    assert outcome.release.candidate is None
    assert "candidate.step" in outcome.diagnostics[-1].message


def test_polygonal_upload_rejects_oversized_source_before_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cad_integrity import gradio_app
    from cad_integrity.pipeline import RepairPolicy

    upload = tmp_path / "too-large.npz"
    upload.write_bytes(b"not an npz")
    monkeypatch.setattr(gradio_app, "_MAX_POLYGONAL_NPZ_BYTES", 1)
    store = gradio_app.ArtifactStore(tmp_path / "artifacts")

    outcome = gradio_app.run_polygonal_upload(upload, RepairPolicy(), artifact_store=store)

    assert outcome.completion == "failed"
    assert outcome.release is None
    assert not store.root.exists()


def test_polygonal_upload_rejects_a_vertex_count_over_its_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import numpy as np

    from cad_integrity import gradio_app
    from cad_integrity.pipeline import RepairPolicy

    upload = tmp_path / "too-many-vertices.npz"
    np.savez(
        upload,
        vertices=np.zeros((4, 3)),
        triangles=np.array(((0, 1, 2),), dtype=np.int64),
        length_unit=np.array("mm"),
    )
    monkeypatch.setattr(gradio_app, "_MAX_POLYGONAL_NPZ_VERTICES", 3)

    outcome = gradio_app.run_polygonal_upload(
        upload, RepairPolicy(), artifact_store=gradio_app.ArtifactStore(tmp_path / "artifacts")
    )

    assert outcome.completion == "failed"
    assert outcome.release is not None
    assert "vertex budget" in outcome.diagnostics[0].message


def test_fixture_ui_action_returns_file_paths_gradio_can_serialize(tmp_path: Path) -> None:
    """The browser callback must return strings for Gradio's File components."""
    import gradio as gr

    from cad_integrity.gradio_app import ArtifactStore, _fixture_ui_action

    result = _fixture_ui_action(
        "01_detached_reversed_cap", artifact_store=ArtifactStore(tmp_path / "artifacts")
    )

    assert all(isinstance(value, str) for value in result[-4:])
    assert all(gr.File().postprocess(value) is not None for value in result[-4:])
