"""Native identity through the public STEP controller and inspection delivery."""
from pathlib import Path

import numpy as np
import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

from cad_integrity.adapters.ocp import KernelPolicy, export_checked_step
from cad_integrity.gradio_app import ArtifactStore, run_step_workbench
from cad_integrity.inspection import encode_inspection


def test_step_faces_retain_distinct_owned_identity_in_inspection(tmp_path: Path) -> None:
    source = tmp_path / "source.step"
    export_checked_step(BRepPrimAPI_MakeBox(2, 3, 5).Shape(), source)
    outcome = run_step_workbench(source, KernelPolicy(), artifact_store=ArtifactStore(tmp_path / "results"))
    assert outcome.inspection is not None
    wire = encode_inspection(outcome.inspection)
    assert wire["schema_version"] == 3
    original, candidate = wire["meshes"]
    assert original["face_kind"] == candidate["face_kind"] == "native_face"
    assert original["id"] != candidate["id"]
    assert original["projection_id"] != candidate["projection_id"]
    assert original["face_count"] == candidate["face_count"] == 6
    assert np.bincount(original["triangle_source_faces"]).tolist() == [2]*6
    assert original["edges"] == []  # no invented native edges from display triangles
    for mesh in (outcome.inspection.original, outcome.inspection.candidate):
        with pytest.raises(ValueError):
            mesh.vertices.setflags(write=True)
        with pytest.raises(ValueError):
            mesh.display.triangle_source_faces.setflags(write=True)
    repeat = run_step_workbench(source, KernelPolicy(), artifact_store=ArtifactStore(tmp_path / "again"))
    assert encode_inspection(repeat.inspection)["meshes"][0]["id"] != original["id"]


def test_refused_step_retains_only_original_native_scope(tmp_path: Path) -> None:
    source = tmp_path / "source.step"
    export_checked_step(BRepPrimAPI_MakeBox(2, 3, 5).Shape(), source)
    outcome = run_step_workbench(
        source, KernelPolicy(expected_solids=2), artifact_store=ArtifactStore(tmp_path / "results"),
        include_legacy_figures=False,
    )
    assert outcome.release is not None and outcome.release.candidate is None
    assert outcome.inspection.original is not None
    assert outcome.inspection.candidate is None
    assert outcome.original_figure is None
    assert [m["stage"] for m in encode_inspection(outcome.inspection)["meshes"]] == ["original"]


def test_native_projection_keeps_missing_faces_and_checks_limits() -> None:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

    from cad_integrity.adapters.ocp import tessellate_for_display
    from cad_integrity.errors import ResourceLimitExceeded
    from cad_integrity.inspection import (
        NativeInspectionSnapshot,
        ProjectionLimits,
        project_native_inspection,
    )

    face = BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))).Face()
    display = tessellate_for_display(face)
    projection = project_native_inspection(display, stage="original", revision="fixture")
    wire = encode_inspection(NativeInspectionSnapshot(projection, None))["meshes"][0]
    assert wire["face_count"] == 1
    assert wire["triangles"] == []
    assert wire["issues"] == [{"face_id": 0, "code": "missing_triangulation", "detail": "Native face interior unavailable"}]
    with pytest.raises(ResourceLimitExceeded):
        project_native_inspection(display, stage="original", revision="fixture", limits=ProjectionLimits(max_payload_bytes=1))


def test_projection_failure_preserves_step_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from cad_integrity.adapters import ocp

    source = tmp_path / "source.step"
    export_checked_step(BRepPrimAPI_MakeBox(2, 3, 5).Shape(), source)

    def mesh_failure(*args: object, **kwargs: object) -> None:
        raise RuntimeError("OCCT display mesher unavailable")

    # Fail the external kernel mesher, not a private projector or controller.
    monkeypatch.setattr(ocp, "BRepMesh_IncrementalMesh", mesh_failure)
    outcome = run_step_workbench(source, KernelPolicy(), artifact_store=ArtifactStore(tmp_path / "results"), include_legacy_figures=False)
    assert outcome.release.candidate.path.is_file()
    assert outcome.decision_brief.candidate_available
    assert outcome.inspection.original is None and outcome.inspection.candidate is None
    assert "OCCT display mesher unavailable" in outcome.decision_brief.markdown
    assert any(d.stage == "display" for d in outcome.diagnostics)
    assert encode_inspection(outcome.inspection) == {"schema_version": 3, "meshes": []}
