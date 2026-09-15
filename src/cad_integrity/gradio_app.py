"""Local Gradio presentation helpers for CAD Integrity Lab evidence.

The geometry package remains responsible for diagnostics and repair.  This module
projects its typed evidence into a concise local-lab interface; it does not infer
CAD intent or turn a rejected operation into a candidate.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters.ocp import ExportReport, KernelPolicy, KernelReport
from .errors import IntegrityError, MissingOptionalDependency
from .models import PolyhedralBRep
from .pipeline import RepairPipeline, RepairPolicy
from .repair import WeldPolicy
from .serialization import dumps
from .visualization import mesh_figure, polygonal_audit_figure


@dataclass(frozen=True, slots=True)
class DecisionBrief:
    """Human-readable projection of a completed native operation."""

    outcome: str
    candidate_available: bool
    markdown: str


@dataclass(frozen=True, slots=True)
class StepWorkbenchOutcome:
    """Files and views released by one local native workbench request."""

    decision_brief: DecisionBrief
    original_figure: Any | None
    candidate_figure: Any | None
    candidate_step: Path | None
    markdown_path: Path
    json_path: Path


@dataclass(frozen=True, slots=True)
class PolygonalFixtureOutcome:
    """Evidence released by one checked-in polygonal fixture experiment."""

    decision_brief: DecisionBrief
    original_figure: Any
    candidate_figure: Any | None
    markdown_path: Path
    json_path: Path


class ArtifactStore:
    """Bounded local request-artifact storage; not a production evidence store."""

    def __init__(self, root: Path | None = None, *, retention_seconds: int = 3_600) -> None:
        if retention_seconds < 1:
            raise ValueError("Artifact retention must be positive")
        self.root = root or Path(tempfile.gettempdir()) / "cad-integrity-gradio"
        self.retention_seconds = retention_seconds

    def create_request_directory(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        cutoff = time.time()-self.retention_seconds
        for candidate in self.root.iterdir():
            if candidate.is_dir() and candidate.stat().st_mtime < cutoff:
                shutil.rmtree(candidate)
        return Path(tempfile.mkdtemp(prefix="request-", dir=self.root))


_FIXTURE_NAMES = (
    "00_clean_boss",
    "01_detached_reversed_cap",
    "01_welded_not_oriented",
    "01_repaired_cap",
    "02_pinched_vertex",
)


def _fixture_root() -> Path:
    return Path(__file__).resolve().parents[2] / "examples" / "pathological-mesh-fixtures"


def _load_qualified_fixture(name: str) -> PolyhedralBRep:
    if name not in _FIXTURE_NAMES:
        raise ValueError(f"Unknown qualified fixture {name!r}")
    import numpy as np

    with np.load(_fixture_root() / "meshes" / f"{name}.npz", allow_pickle=False) as data:
        vertices = data["vertices"].copy()
        triangles = data["triangles"].copy()
        length_unit = str(data["length_unit"].item())
    if length_unit != "mm":
        raise ValueError(f"Qualified fixture {name!r} is not measured in millimetres")
    return PolyhedralBRep.from_polygons(vertices, triangles, length_unit=length_unit)


def _qualified_fixture_policy() -> RepairPolicy:
    provenance = json.loads((_fixture_root() / "provenance" / "construction.json").read_text(encoding="utf-8"))
    return RepairPolicy(weld=WeldPolicy(
        tolerance=provenance["recommended_weld_tolerance_mm"],
        max_displacement=provenance["recommended_max_displacement_mm"],
    ))


def kernel_policy_from_controls(precision_mm: float, maximum_tolerance_mm: float,
                                expected_solids: float, run_self_interference_check: bool,
                                max_relative_area_change: float,
                                max_relative_volume_change: float,
                                allow_face_count_change: bool) -> KernelPolicy:
    """Validate UI scalar values through the native policy's public contract."""
    if not float(expected_solids).is_integer():
        raise ValueError("Expected solid count must be a whole number")
    return KernelPolicy(
        precision_mm=float(precision_mm),
        maximum_tolerance_mm=float(maximum_tolerance_mm),
        expected_solids=int(expected_solids),
        run_self_interference_check=bool(run_self_interference_check),
        max_relative_area_change=float(max_relative_area_change),
        max_relative_volume_change=float(max_relative_volume_change),
        allow_face_count_change=bool(allow_face_count_change),
    )


def _kernel_row(report: KernelReport) -> str:
    free_edges = len(report.free_edge_ids)
    nonmanifold_edges = len(report.nonmanifold_edge_ids)
    volume = sum(report.solid_volumes_mm3)
    return (
        f"| {report.solid_count} | {report.face_count} | {free_edges} | "
        f"{nonmanifold_edges} | {report.maximum_entity_tolerance_mm:.6g} | "
        f"{report.surface_area_mm2:,.6g} | {volume:,.6g} |"
    )


def _policy_lines(policy: KernelPolicy) -> list[str]:
    return [
        f"- Precision: `{policy.precision_mm:g} mm`",
        f"- Maximum entity tolerance: `{policy.maximum_tolerance_mm:g} mm`",
        f"- Expected solids: `{policy.expected_solids}`",
        f"- Self-interference check: `{'enabled' if policy.run_self_interference_check else 'disabled'}`",
        f"- Maximum relative area change: `{policy.max_relative_area_change:g}`",
        f"- Maximum relative volume change: `{policy.max_relative_volume_change:g}`",
        f"- Face-count changes: `{'allowed' if policy.allow_face_count_change else 'rejected'}`",
    ]


def project_step_evidence(result: dict[str, Any]) -> DecisionBrief:
    """Project a successful ``run_step_pipeline`` result without parsing JSON."""
    before = result["before"]
    policy = result["policy"]
    export = result["export"]
    if not isinstance(before, KernelReport) or not isinstance(policy, KernelPolicy):
        raise TypeError("STEP evidence needs typed KernelReport and KernelPolicy values")
    if not isinstance(export, ExportReport):
        raise TypeError("A completed STEP evidence projection needs an ExportReport")
    after = export.after_roundtrip
    operations = result["operations"]
    limitations = result["limitations"]
    markdown = "\n".join([
        "## Decision",
        "Candidate passed configured kernel checks.",
        "",
        "## Before / after",
        "| | Solids | Faces | Free edges | Nonmanifold edges | Max tolerance (mm) | Area (mm²) | Volume (mm³) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| Before | {_kernel_row(before)[2:]}",
        f"| After round trip | {_kernel_row(after)[2:]}",
        "",
        "## What happened",
        *(f"- {operation}" for operation in operations),
        "",
        "## Configured policy",
        *_policy_lines(policy),
        "",
        "## Evidence",
        f"- Input SHA-256: `{result['source_sha256']}`",
        f"- Output SHA-256: `{export.output_sha256}`",
        f"- Normalized length unit: `{result['normalized_length_unit']}`",
        "",
        "## Limitations",
        *(f"- {limitation}" for limitation in limitations),
    ])
    return DecisionBrief("Candidate passed configured kernel checks", True, markdown)


def project_step_refusal(before: KernelReport, policy: KernelPolicy, source_sha256: str,
                         reason: str) -> DecisionBrief:
    """Make a refusal useful without turning it into a candidate claim."""
    reasons = before.acceptance_reasons or ("The configured repair did not produce a publishable candidate",)
    markdown = "\n".join([
        "## Decision",
        "Repair rejected — no checked STEP candidate was published.",
        "",
        "## Why",
        f"- {reason}",
        *(f"- {item}" for item in reasons),
        "",
        "## Original audit",
        "| Solids | Faces | Free edges | Nonmanifold edges | Max tolerance (mm) | Area (mm²) | Volume (mm³) |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        _kernel_row(before),
        "",
        "## Configured policy",
        *_policy_lines(policy),
        "",
        "## Evidence",
        f"- Input SHA-256: `{source_sha256}`",
        "- No candidate artifact is available.",
        "",
        "## Limitations",
        "- This outcome does not infer intended mates, feature history, or a safe repair.",
    ])
    return DecisionBrief("Repair rejected", False, markdown)


def _native_figure(shape: Any, report: KernelReport, *, title: str) -> Any:
    from .adapters.ocp import sample_edge_polylines, tessellate_for_display

    flagged_ids = tuple(sorted(set(report.free_edge_ids + report.nonmanifold_edge_ids)))
    lines = sample_edge_polylines(shape, flagged_ids) if flagged_ids else ()
    display = tessellate_for_display(shape, max_triangles=250_000)
    color = "seagreen" if report.accepted_under_policy else "lightgray"
    return mesh_figure(display.mesh, title=title, color=color, edge_polylines=lines)


def run_step_workbench(upload: str | Path, policy: KernelPolicy, *,
                       artifact_store: ArtifactStore | None = None) -> StepWorkbenchOutcome:
    """Execute one local STEP audit/repair request and retain honest artifacts."""
    from .adapters.ocp import audit_shape, read_step, run_step_pipeline

    supplied = Path(upload)
    if supplied.suffix.lower() not in {".step", ".stp"}:
        raise ValueError("Upload a STEP file with a .step or .stp extension")
    if not supplied.is_file():
        raise FileNotFoundError(supplied)
    if supplied.stat().st_size > policy.max_input_bytes:
        raise ValueError(f"STEP upload exceeds the {policy.max_input_bytes} byte policy limit")
    store = artifact_store or ArtifactStore()
    request = store.create_request_directory()
    source = request / f"input{supplied.suffix.lower()}"
    shutil.copyfile(supplied, source)
    document = read_step(source, max_bytes=policy.max_input_bytes)
    before = audit_shape(document.shape, policy)
    original_figure = _native_figure(document.shape, before, title="Original audit")
    target = request / "checked.step"
    try:
        result = run_step_pipeline(source, target, policy)
        brief = project_step_evidence(result)
        candidate_document = read_step(target, max_bytes=policy.max_input_bytes)
        candidate_figure = _native_figure(
            candidate_document.shape, result["export"].after_roundtrip, title="Checked candidate"
        )
        payload: dict[str, Any] = result
        candidate_step: Path | None = target
    except (IntegrityError, ValueError, OSError) as exc:
        brief = project_step_refusal(before, policy, document.source_sha256, str(exc))
        candidate_figure = None
        candidate_step = None
        payload = {
            "schema_version": "1.0",
            "source_sha256": document.source_sha256,
            "policy": policy,
            "before": before,
            "decision": "repair_rejected",
            "reason": str(exc),
        }
    markdown_path = request / "decision-brief.md"
    json_path = request / "evidence.json"
    markdown_path.write_text(brief.markdown + "\n", encoding="utf-8")
    json_path.write_text(dumps(payload) + "\n", encoding="utf-8")
    return StepWorkbenchOutcome(
        brief, original_figure, candidate_figure, candidate_step, markdown_path, json_path
    )


def _topology_row(report: Any) -> str:
    homology = report.homology.betti_numbers if report.homology is not None else "not computed"
    return (
        f"| {report.vertex_count} | {report.edge_count} | {report.face_count} | "
        f"{len(report.boundary_edge_ids)} | {len(report.nonmanifold_edge_ids)} | "
        f"{len(report.inconsistent_orientation_edge_ids)} | `{homology}` |"
    )


def project_polygonal_evidence(result: Any, fixture_name: str) -> DecisionBrief:
    """Describe fixture results without presenting a combinatorial pass as CAD proof."""
    report = result.report
    passed = report.decision == "topology_checks_passed"
    outcome = "Candidate passed configured combinatorial checks" if passed else "Fixture requires review"
    after_rows = _topology_row(report.after) if report.after is not None else "| — | — | — | — | — | — | `—` |"
    markdown = "\n".join([
        "## Decision",
        f"{outcome}.",
        "",
        f"Qualified fixture: `{fixture_name}`.",
        "",
        "## Before / after",
        "| | Vertices | Edges | Faces | Boundary edges | Nonmanifold edges | Winding conflicts | Betti numbers over F₂ |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        f"| Before | {_topology_row(report.before)[2:]}",
        f"| After | {after_rows[2:]}",
        "",
        "## What happened",
        *((tuple(f"- {change}" for change in report.changes))
          if report.changes else ("- No repair operations were applied.",)),
        *(f"- {error}" for error in report.errors),
        "",
        "## Limitations",
        "- These are bounded combinatorial diagnostics for a qualified polygonal fixture.",
        "- A passing result is not native CAD validity, design-intent recovery, or engineering certification.",
    ])
    return DecisionBrief(outcome, passed, markdown)


def run_polygonal_fixture(name: str, *, artifact_store: ArtifactStore | None = None) -> PolygonalFixtureOutcome:
    """Run one checked-in fixture through its recorded conservative policy."""
    source = _load_qualified_fixture(name)
    result = RepairPipeline(_qualified_fixture_policy()).run(source)
    brief = project_polygonal_evidence(result, name)
    original_figure = polygonal_audit_figure(result.original, result.report.before, title="Original fixture")
    candidate_figure = (
        polygonal_audit_figure(result.candidate, result.report.after, title="Candidate fixture")
        if result.candidate is not None and result.report.after is not None else None
    )
    request = (artifact_store or ArtifactStore()).create_request_directory()
    markdown_path = request / "decision-brief.md"
    json_path = request / "evidence.json"
    markdown_path.write_text(brief.markdown + "\n", encoding="utf-8")
    json_path.write_text(dumps(result.report) + "\n", encoding="utf-8")
    return PolygonalFixtureOutcome(brief, original_figure, candidate_figure, markdown_path, json_path)


def _step_ui_action(upload: str | None, precision_mm: float, maximum_tolerance_mm: float,
                    expected_solids: float, run_self_interference_check: bool,
                    max_relative_area_change: float, max_relative_volume_change: float,
                    allow_face_count_change: bool, *, artifact_store: ArtifactStore
                    ) -> tuple[str, Any | None, Any | None, Path | None, Path | None, Path | None]:
    try:
        if upload is None:
            raise ValueError("Choose a local STEP file before running the workbench")
        policy = kernel_policy_from_controls(
            precision_mm, maximum_tolerance_mm, expected_solids, run_self_interference_check,
            max_relative_area_change, max_relative_volume_change, allow_face_count_change,
        )
        outcome = run_step_workbench(upload, policy, artifact_store=artifact_store)
        return (
            outcome.decision_brief.markdown,
            outcome.original_figure,
            outcome.candidate_figure,
            outcome.candidate_step,
            outcome.markdown_path,
            outcome.json_path,
        )
    except (IntegrityError, OSError, ValueError) as exc:
        return (f"## Decision\nRequest not run: {exc}", None, None, None, None, None)


def _fixture_ui_action(name: str, *, artifact_store: ArtifactStore
                       ) -> tuple[str, Any | None, Any | None, Path | None, Path | None]:
    try:
        outcome = run_polygonal_fixture(name, artifact_store=artifact_store)
        return (
            outcome.decision_brief.markdown,
            outcome.original_figure,
            outcome.candidate_figure,
            outcome.markdown_path,
            outcome.json_path,
        )
    except (IntegrityError, OSError, ValueError) as exc:
        return (f"## Decision\nFixture not run: {exc}", None, None, None, None)


def build_app() -> Any:
    """Build the local UI without starting a server or touching geometry."""
    try:
        import gradio as gr
    except ImportError as exc:
        raise MissingOptionalDependency("Install cad-integrity-lab[ui] to use the Gradio app") from exc
    artifact_store = ArtifactStore()
    with gr.Blocks(title="CAD Integrity Lab") as app:
        gr.Markdown(
            "# CAD Integrity Lab\n"
            "Local diagnostics and conservative repair experiments. Results are not engineering certification."
        )
        with gr.Tab("Local STEP workbench"):
            step_upload = gr.File(label="Local STEP file", file_types=[".step", ".stp"], type="filepath")
            with gr.Accordion("Advanced repair policy", open=False):
                precision = gr.Number(label="Precision (mm)", value=1e-6, minimum=1e-12)
                maximum_tolerance = gr.Number(label="Maximum entity tolerance (mm)", value=1e-3, minimum=1e-12)
                expected_solids = gr.Number(label="Expected solids", value=1, minimum=1, precision=0)
                self_interference = gr.Checkbox(label="Run self-interference check", value=True)
                area_change = gr.Number(label="Maximum relative area change", value=1e-4, minimum=0)
                volume_change = gr.Number(label="Maximum relative volume change", value=1e-4, minimum=0)
                allow_face_count = gr.Checkbox(label="Allow face-count changes", value=False)
            step_run = gr.Button("Audit and attempt configured repair", variant="primary")
            step_brief = gr.Markdown(label="Decision brief")
            with gr.Row():
                original_plot = gr.Plot(label="Original diagnostic view")
                candidate_plot = gr.Plot(label="Candidate diagnostic view")
            with gr.Row():
                checked_step = gr.File(label="Checked STEP download")
                step_markdown = gr.File(label="Decision brief download")
                step_json = gr.File(label="Raw JSON evidence")
            step_run.click(
                lambda *inputs: _step_ui_action(*inputs, artifact_store=artifact_store),
                inputs=[step_upload, precision, maximum_tolerance, expected_solids, self_interference,
                        area_change, volume_change, allow_face_count],
                outputs=[step_brief, original_plot, candidate_plot, checked_step, step_markdown, step_json],
            )
        with gr.Tab("Polygonal fixture lab"):
            fixture_name = gr.Dropdown(
                label="Qualified fixture",
                choices=[
                    "00_clean_boss",
                    "01_detached_reversed_cap",
                    "01_welded_not_oriented",
                    "01_repaired_cap",
                    "02_pinched_vertex",
                ],
                value="01_detached_reversed_cap",
            )
            fixture_run = gr.Button("Analyze fixture", variant="primary")
            fixture_brief = gr.Markdown(label="Fixture decision brief")
            with gr.Row():
                fixture_original_plot = gr.Plot(label="Original fixture view")
                fixture_candidate_plot = gr.Plot(label="Candidate fixture view")
            with gr.Row():
                fixture_markdown = gr.File(label="Fixture decision brief download")
                fixture_json = gr.File(label="Fixture raw JSON evidence")
            fixture_run.click(
                lambda name: _fixture_ui_action(name, artifact_store=artifact_store),
                inputs=[fixture_name],
                outputs=[fixture_brief, fixture_original_plot, fixture_candidate_plot,
                         fixture_markdown, fixture_json],
            )
    return app


def main() -> None:
    """Run a loopback-only local lab; public deployment needs worker isolation."""
    build_app().launch(server_name="127.0.0.1", share=False)


if __name__ == "__main__":
    main()
