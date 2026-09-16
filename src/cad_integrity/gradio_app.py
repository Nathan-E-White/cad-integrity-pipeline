"""Local Gradio presentation helpers for CAD Integrity Lab evidence.

The geometry package remains responsible for diagnostics and repair.  This module
projects its typed evidence into a concise local-lab interface; it does not infer
CAD intent or turn a rejected operation into a candidate.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters.ocp import ExportReport, KernelPolicy, KernelReport
from .errors import IntegrityError, MissingOptionalDependency
from .models import PolyhedralBRep
from .pipeline import RepairPipeline, RepairPolicy, fingerprint
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
class PolygonalAnalysisOutcome:
    """Evidence released by one polygonal fixture or admitted upload."""

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
_NO_CANDIDATE_NOTICE = "## No candidate published\nThe audit did not publish a candidate for review or download."
_MAX_POLYGONAL_NPZ_BYTES = 50_000_000
_MAX_POLYGONAL_NPZ_EXPANDED_BYTES = 100_000_000
_MAX_POLYGONAL_NPZ_VERTICES = 250_000
_MAX_POLYGONAL_NPZ_TRIANGLES = 500_000
_POLYGONAL_NPZ_MEMBERS = frozenset({"vertices.npy", "triangles.npy", "length_unit.npy"})


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


def _load_restricted_polygonal_npz(path: Path) -> PolyhedralBRep:
    """Load the small, explicit NPZ polygonal contract without mesh processing."""
    import numpy as np

    _validate_restricted_polygonal_npz_source(path)
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if set(names) != _POLYGONAL_NPZ_MEMBERS or len(names) != len(_POLYGONAL_NPZ_MEMBERS):
                raise ValueError("Polygonal NPZ must contain only vertices, triangles, and length_unit arrays")
            if any(member.is_dir() or member.file_size < 0 for member in members):
                raise ValueError("Polygonal NPZ contains an invalid archive member")
            if sum(member.file_size for member in members) > _MAX_POLYGONAL_NPZ_EXPANDED_BYTES:
                raise ValueError("Polygonal NPZ exceeds the expanded-data budget")
        with np.load(path, allow_pickle=False) as arrays:
            vertices = arrays["vertices"]
            triangles = arrays["triangles"]
            length_unit = str(arrays["length_unit"].item())
            if len(vertices) > _MAX_POLYGONAL_NPZ_VERTICES:
                raise ValueError("Polygonal NPZ exceeds the vertex budget")
            if len(triangles) > _MAX_POLYGONAL_NPZ_TRIANGLES:
                raise ValueError("Polygonal NPZ exceeds the triangle budget")
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Invalid restricted polygonal NPZ: {exc}") from exc
    return PolyhedralBRep.from_polygons(vertices, triangles, length_unit=length_unit)


def _validate_restricted_polygonal_npz_source(path: Path) -> None:
    if path.suffix.lower() != ".npz":
        raise ValueError("Upload a polygonal NPZ file with a .npz extension")
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size > _MAX_POLYGONAL_NPZ_BYTES:
        raise ValueError(f"Polygonal NPZ upload exceeds {_MAX_POLYGONAL_NPZ_BYTES} bytes")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _write_evidence_artifacts(request: Path, markdown: str, payload: Any) -> tuple[Path, Path]:
    markdown_path = request / "decision-brief.md"
    json_path = request / "evidence.json"
    markdown_path.write_text(markdown + "\n", encoding="utf-8")
    json_path.write_text(dumps(payload) + "\n", encoding="utf-8")
    return markdown_path, json_path


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


def polygonal_policy_from_controls(enable_welding: bool, weld_tolerance_mm: float,
                                   max_displacement_mm: float,
                                   synchronize_orientation: bool) -> RepairPolicy:
    """Build the explicit policy for one restricted polygonal upload."""
    weld = (
        WeldPolicy(float(weld_tolerance_mm), float(max_displacement_mm))
        if enable_welding else None
    )
    return RepairPolicy(weld=weld, synchronize_orientation=bool(synchronize_orientation))


def _kernel_cells(report: KernelReport) -> tuple[str, ...]:
    free_edges = len(report.free_edge_ids)
    nonmanifold_edges = len(report.nonmanifold_edge_ids)
    volume = sum(report.solid_volumes_mm3)
    return (
        str(report.solid_count), str(report.face_count), str(free_edges), str(nonmanifold_edges),
        f"{report.maximum_entity_tolerance_mm:.6g}", f"{report.surface_area_mm2:,.6g}",
        f"{volume:,.6g}",
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
        f"| Before | {' | '.join(_kernel_cells(before))} |",
        f"| After round trip | {' | '.join(_kernel_cells(after))} |",
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
        f"| {' | '.join(_kernel_cells(before))} |",
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


def _render_native_figure(shape: Any, report: KernelReport, *, title: str) -> tuple[Any | None, str | None]:
    try:
        return _native_figure(shape, report, title=title), None
    except IntegrityError as exc:
        return None, str(exc)


def _with_display_notes(brief: DecisionBrief, notes: list[str]) -> DecisionBrief:
    if not notes:
        return brief
    markdown = brief.markdown + "\n\n## Display\n" + "\n".join(f"- {note}" for note in notes)
    return DecisionBrief(brief.outcome, brief.candidate_available, markdown)


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
    original_figure, original_display_error = _render_native_figure(
        document.shape, before, title="Original audit"
    )
    target = request / "checked.step"
    try:
        result = run_step_pipeline(source, target, policy)
        brief = project_step_evidence(result)
        candidate_document = read_step(target, max_bytes=policy.max_input_bytes)
        candidate_figure, candidate_display_error = _render_native_figure(
            candidate_document.shape, result["export"].after_roundtrip, title="Checked candidate"
        )
        display_notes = [
            f"Original diagnostic view unavailable: {original_display_error}"
            if original_display_error is not None else "",
            f"Candidate diagnostic view unavailable: {candidate_display_error}"
            if candidate_display_error is not None else "",
        ]
        display_notes = [note for note in display_notes if note]
        brief = _with_display_notes(brief, display_notes)
        payload: dict[str, Any] = {**result, "display_warnings": tuple(display_notes)}
        candidate_step: Path | None = target
    except (IntegrityError, ValueError, OSError) as exc:
        brief = project_step_refusal(before, policy, document.source_sha256, str(exc))
        candidate_figure = None
        candidate_step = None
        brief = _with_display_notes(
            brief,
            [f"Original diagnostic view unavailable: {original_display_error}"]
            if original_display_error is not None else [],
        )
        payload = {
            "schema_version": "1.0",
            "source_sha256": document.source_sha256,
            "policy": policy,
            "before": before,
            "decision": "repair_rejected",
            "reason": str(exc),
        }
    markdown_path, json_path = _write_evidence_artifacts(request, brief.markdown, payload)
    return StepWorkbenchOutcome(
        brief, original_figure, candidate_figure, candidate_step, markdown_path, json_path
    )


def _topology_cells(report: Any) -> tuple[str, ...]:
    homology = report.homology.betti_numbers if report.homology is not None else "not computed"
    return (
        str(report.vertex_count), str(report.edge_count), str(report.face_count),
        str(len(report.boundary_edge_ids)), str(len(report.nonmanifold_edge_ids)),
        str(len(report.inconsistent_orientation_edge_ids)), f"`{homology}`",
    )


def project_polygonal_evidence(result: Any, source_label: str, policy: RepairPolicy, *,
                               requires_review_outcome: str = "Fixture requires review",
                               limitations_scope: str = "qualified polygonal fixture") -> DecisionBrief:
    """Describe polygonal results without presenting a combinatorial pass as CAD proof."""
    report = result.report
    passed = report.decision == "topology_checks_passed"
    outcome = "Candidate passed configured combinatorial checks" if passed else requires_review_outcome
    after_cells = _topology_cells(report.after) if report.after is not None else ("—",) * 6 + ("`—`",)
    candidate_fingerprint = fingerprint(result.candidate) if passed and result.candidate is not None else None
    markdown = "\n".join([
        "## Decision",
        f"{outcome}.",
        "",
        source_label,
        "",
        "## Before / after",
        "| | Vertices | Edges | Faces | Boundary edges | Nonmanifold edges | Winding conflicts | Betti numbers over F₂ |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        f"| Before | {' | '.join(_topology_cells(report.before))} |",
        f"| After | {' | '.join(after_cells)} |",
        "",
        "## What happened",
        *((tuple(f"- {change}" for change in report.changes))
          if report.changes else ("- No repair operations were applied.",)),
        *(f"- {error}" for error in report.errors),
        "",
        "## Configured policy",
        f"- Weld tolerance: `{policy.weld.tolerance:g} mm`" if policy.weld is not None else "- Welding: disabled",
        f"- Maximum vertex displacement: `{policy.weld.max_displacement:g} mm`" if policy.weld is not None else "",
        f"- Orientation synchronization: `{'enabled' if policy.synchronize_orientation else 'disabled'}`",
        f"- Homology coefficient field: `{policy.coefficients}`",
        "",
        "## Evidence",
        f"- Input SHA-256: `{report.input_sha256}`",
        (f"- Candidate canonical-array fingerprint: `{candidate_fingerprint}`"
         if candidate_fingerprint is not None else "- No candidate artifact was produced."),
        f"- Length unit: `{report.length_unit}`",
        "",
        "## Limitations",
        f"- These are bounded combinatorial diagnostics for the {limitations_scope}.",
        "- A passing result is not native CAD validity, design-intent recovery, or engineering certification.",
    ])
    return DecisionBrief(outcome, passed, markdown)


def _polygonal_analysis_outcome(result: Any, source_label: str, policy: RepairPolicy, *,
                                request: Path, original_title: str, candidate_title: str,
                                requires_review_outcome: str = "Fixture requires review",
                                limitations_scope: str = "qualified polygonal fixture",
                                source_evidence: dict[str, str] | None = None
                                ) -> PolygonalAnalysisOutcome:
    brief = project_polygonal_evidence(
        result,
        source_label,
        policy,
        requires_review_outcome=requires_review_outcome,
        limitations_scope=limitations_scope,
    )
    original_figure = polygonal_audit_figure(result.original, result.report.before, title=original_title)
    candidate_figure = (
        polygonal_audit_figure(result.candidate, result.report.after, title=candidate_title)
        if brief.candidate_available and result.candidate is not None and result.report.after is not None else None
    )
    payload: Any = result.report if source_evidence is None else {
        "schema_version": "1.0", **source_evidence, "policy": policy, "repair": result.report,
    }
    markdown_path, json_path = _write_evidence_artifacts(request, brief.markdown, payload)
    return PolygonalAnalysisOutcome(brief, original_figure, candidate_figure, markdown_path, json_path)


def run_polygonal_fixture(name: str, *, artifact_store: ArtifactStore | None = None) -> PolygonalAnalysisOutcome:
    """Run one checked-in fixture through its recorded conservative policy."""
    source = _load_qualified_fixture(name)
    policy = _qualified_fixture_policy()
    result = RepairPipeline(policy).run(source)
    request = (artifact_store or ArtifactStore()).create_request_directory()
    return _polygonal_analysis_outcome(
        result, f"Qualified fixture: `{name}`.", policy, request=request,
        original_title="Original fixture", candidate_title="Candidate fixture",
    )


def run_polygonal_upload(upload: str | Path, policy: RepairPolicy, *,
                         artifact_store: ArtifactStore | None = None) -> PolygonalAnalysisOutcome:
    """Analyze and optionally stitch one restricted uploaded NPZ mesh."""
    supplied = Path(upload)
    _validate_restricted_polygonal_npz_source(supplied)
    store = artifact_store or ArtifactStore()
    request = store.create_request_directory()
    staged = request / "input.npz"
    shutil.copyfile(supplied, staged)
    source = _load_restricted_polygonal_npz(staged)
    result = RepairPipeline(policy).run(source)
    return _polygonal_analysis_outcome(
        result, "Uploaded NPZ — restricted array contract.", policy, request=request,
        original_title="Original upload", candidate_title="Candidate upload",
        requires_review_outcome="Uploaded polygonal input requires review",
        limitations_scope="uploaded NPZ array contract",
        source_evidence={
            "source_kind": "uploaded_restricted_npz",
            "source_sha256": _sha256_file(staged),
        },
    )


def _step_ui_action(upload: str | None, precision_mm: float, maximum_tolerance_mm: float,
                    expected_solids: float, run_self_interference_check: bool,
                    max_relative_area_change: float, max_relative_volume_change: float,
                    allow_face_count_change: bool, *, artifact_store: ArtifactStore
                    ) -> tuple[str, Any | None, Any, Any, str | None, str | None, str | None]:
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
            *candidate_display(outcome.candidate_figure),
            str(outcome.candidate_step) if outcome.candidate_step is not None else None,
            str(outcome.markdown_path),
            str(outcome.json_path),
        )
    except (IntegrityError, OSError, ValueError) as exc:
        return (f"## Decision\nRequest not run: {exc}", None, *candidate_display(None), None, None, None)


def _fixture_ui_action(name: str, *, artifact_store: ArtifactStore
                       ) -> tuple[str, Any | None, Any, Any, str | None, str | None]:
    try:
        outcome = run_polygonal_fixture(name, artifact_store=artifact_store)
        return (
            outcome.decision_brief.markdown,
            outcome.original_figure,
            *candidate_display(outcome.candidate_figure),
            str(outcome.markdown_path),
            str(outcome.json_path),
        )
    except (IntegrityError, OSError, ValueError) as exc:
        return (f"## Decision\nFixture not run: {exc}", None, *candidate_display(None), None, None)


def _polygonal_upload_ui_action(upload: str | None, enable_welding: bool,
                                weld_tolerance_mm: float, max_displacement_mm: float,
                                synchronize_orientation: bool, *, artifact_store: ArtifactStore
                                ) -> tuple[str, Any | None, Any, Any, str | None, str | None]:
    try:
        if upload is None:
            raise ValueError("Choose a restricted polygonal NPZ file before analysis")
        policy = polygonal_policy_from_controls(
            enable_welding, weld_tolerance_mm, max_displacement_mm, synchronize_orientation
        )
        outcome = run_polygonal_upload(upload, policy, artifact_store=artifact_store)
        return (
            outcome.decision_brief.markdown,
            outcome.original_figure,
            *candidate_display(outcome.candidate_figure),
            str(outcome.markdown_path),
            str(outcome.json_path),
        )
    except (IntegrityError, OSError, ValueError) as exc:
        return (f"## Decision\nUpload not analyzed: {exc}", None, *candidate_display(None), None, None)


def candidate_display(figure: Any | None) -> tuple[Any, Any]:
    """Return mutually exclusive Gradio components for published and absent candidates."""
    import gradio as gr

    return (
        gr.Plot(value=figure, visible=figure is not None),
        gr.Markdown(_NO_CANDIDATE_NOTICE, visible=figure is None),
    )


def build_app() -> Any:
    """Build the local UI without starting a server or touching geometry."""
    try:
        import gradio as gr
    except ImportError as exc:
        raise MissingOptionalDependency("Install cad-integrity-lab[ui] to use the Gradio app") from exc
    artifact_store = ArtifactStore()
    with gr.Blocks(title="CAD Integrity Lab", fill_width=True) as app:
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
            with gr.Tabs():
                with gr.Tab("Original"):
                    original_plot = gr.Plot(label="Original diagnostic view", min_width=320)
                with gr.Tab("Candidate"):
                    candidate_notice = gr.Markdown(_NO_CANDIDATE_NOTICE)
                    candidate_plot = gr.Plot(label="Candidate diagnostic view", min_width=320, visible=False)
            with gr.Row():
                checked_step = gr.File(label="Checked STEP download")
                step_markdown = gr.File(label="Decision brief download")
                step_json = gr.File(label="Raw JSON evidence")
            step_run.click(
                lambda *inputs: _step_ui_action(*inputs, artifact_store=artifact_store),
                inputs=[step_upload, precision, maximum_tolerance, expected_solids, self_interference,
                        area_change, volume_change, allow_face_count],
                outputs=[step_brief, original_plot, candidate_plot, candidate_notice,
                         checked_step, step_markdown, step_json],
            )
        with gr.Tab("Polygonal fixture lab"):
            fixture_name = gr.Dropdown(
                label="Qualified fixture",
                choices=list(_FIXTURE_NAMES),
                value="01_detached_reversed_cap",
            )
            fixture_run = gr.Button("Analyze fixture", variant="primary")
            fixture_brief = gr.Markdown(label="Fixture decision brief")
            with gr.Tabs():
                with gr.Tab("Original"):
                    fixture_original_plot = gr.Plot(label="Original fixture view", min_width=320)
                with gr.Tab("Candidate"):
                    fixture_candidate_notice = gr.Markdown(_NO_CANDIDATE_NOTICE)
                    fixture_candidate_plot = gr.Plot(
                        label="Candidate fixture view", min_width=320, visible=False
                    )
            with gr.Row():
                fixture_markdown = gr.File(label="Fixture decision brief download")
                fixture_json = gr.File(label="Fixture raw JSON evidence")
            fixture_run.click(
                lambda name: _fixture_ui_action(name, artifact_store=artifact_store),
                inputs=[fixture_name],
                outputs=[fixture_brief, fixture_original_plot, fixture_candidate_plot,
                         fixture_candidate_notice,
                         fixture_markdown, fixture_json],
            )
            gr.Markdown(
                "### Restricted NPZ upload\n"
                "Requires `vertices`, `triangles`, and `length_unit`; OBJ and GLB are deferred."
            )
            polygonal_upload = gr.File(
                label="Restricted polygonal NPZ", file_types=[".npz"], type="filepath"
            )
            with gr.Accordion("Upload stitching policy", open=False):
                upload_welding = gr.Checkbox(label="Weld nearby boundary vertices", value=True)
                upload_weld_tolerance = gr.Number(label="Weld tolerance (mm)", value=0.001, minimum=1e-12)
                upload_max_displacement = gr.Number(
                    label="Maximum vertex displacement (mm)", value=0.001, minimum=0
                )
                upload_orientation = gr.Checkbox(label="Synchronize face orientation", value=True)
            upload_run = gr.Button("Analyze and attempt configured stitching", variant="primary")
            upload_brief = gr.Markdown(label="Upload decision brief")
            with gr.Tabs():
                with gr.Tab("Original upload"):
                    upload_original_plot = gr.Plot(label="Original uploaded mesh", min_width=320)
                with gr.Tab("Candidate upload"):
                    upload_candidate_notice = gr.Markdown(_NO_CANDIDATE_NOTICE)
                    upload_candidate_plot = gr.Plot(
                        label="Candidate uploaded mesh", min_width=320, visible=False
                    )
            with gr.Row():
                upload_markdown = gr.File(label="Upload decision brief download")
                upload_json = gr.File(label="Upload raw JSON evidence")
            upload_run.click(
                lambda *inputs: _polygonal_upload_ui_action(*inputs, artifact_store=artifact_store),
                inputs=[polygonal_upload, upload_welding, upload_weld_tolerance,
                        upload_max_displacement, upload_orientation],
                outputs=[upload_brief, upload_original_plot, upload_candidate_plot,
                         upload_candidate_notice, upload_markdown, upload_json],
            )
    return app


def main() -> None:
    """Run a loopback-only local lab; public deployment needs worker isolation."""
    print("CAD Integrity Lab is serving at http://127.0.0.1:7860 — press Ctrl-C to stop.")
    build_app().launch(server_name="127.0.0.1", share=False)


if __name__ == "__main__":
    main()
