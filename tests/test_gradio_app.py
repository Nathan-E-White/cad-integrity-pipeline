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
        "Original fixture view",
        "Candidate fixture view",
    }
    assert sum(
        component.get("props", {}).get("value")
        == "## No candidate published\nThe audit did not publish a candidate for review or download."
        for component in config["components"]
    ) == 2


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
    assert outcome.candidate_step is not None
    assert outcome.original_figure is None
    assert outcome.candidate_figure is None
    assert "## Display" in outcome.decision_brief.markdown
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
    assert "Input SHA-256" in outcome.decision_brief.markdown
    assert "Weld tolerance" in outcome.decision_brief.markdown
    assert "Candidate canonical-array fingerprint" in outcome.decision_brief.markdown


def test_fixture_ui_action_returns_file_paths_gradio_can_serialize(tmp_path: Path) -> None:
    """The browser callback must return strings for Gradio's File components."""
    import gradio as gr

    from cad_integrity.gradio_app import ArtifactStore, _fixture_ui_action

    result = _fixture_ui_action(
        "01_detached_reversed_cap", artifact_store=ArtifactStore(tmp_path / "artifacts")
    )

    assert all(isinstance(value, str) for value in result[-2:])
    assert all(gr.File().postprocess(value) is not None for value in result[-2:])
