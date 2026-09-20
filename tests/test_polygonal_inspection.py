"""Public inspection contracts; catalogue IDs identify independent behavior oracles."""

import pytest

from cad_integrity.workbench_results import failed_outcome


def test_failed_outcome_has_optional_empty_inspection():
    """M11/M12: additive data does not change existing failure construction."""
    assert failed_outcome("admission", "invalid input").inspection is None


def test_projected_snapshot_owns_arrays_and_stage_identities():
    """M02/M06/M07: immutable data survives source mutation and identical stages."""
    import numpy as np

    from cad_integrity import inspection
    from cad_integrity.fixtures import cube
    from cad_integrity.pipeline import RepairPipeline

    result = RepairPipeline().run(cube())
    snapshot = inspection.project_polygonal_inspection(result)
    before = snapshot.original.vertices.copy()
    result.original.vertices.setflags(write=True)
    result.original.vertices[0] = (99, 98, 97)
    np.testing.assert_array_equal(snapshot.original.vertices, before)
    with pytest.raises(ValueError):
        snapshot.original.vertices.setflags(write=True)
    assert snapshot.candidate is not None
    assert snapshot.original.scope != snapshot.candidate.scope
    assert snapshot.original.length_unit == "mm"


def test_projection_preserves_supplied_memberships_without_audit():
    """P01/P02/P09: literal supplied facts, deliberately independent of an audit."""
    from dataclasses import replace

    from cad_integrity.fixtures import cube
    from cad_integrity.inspection import project_polygonal_inspection
    from cad_integrity.pipeline import RepairPipeline

    result = RepairPipeline().run(cube())
    before = replace(
        result.report.before,
        boundary_edge_ids=(0, 2),
        inconsistent_orientation_edge_ids=(2,),
        unused_edge_ids=(7,),
        nonmanifold_vertex_ids=(1,),
        unused_vertex_ids=(6,),
        nonmanifold_edge_ids=(3,),
        collapsed_edge_ids=(9,),
        invalid_face_ids=(1,),
        duplicate_face_ids=(2,),
    )
    snapshot = project_polygonal_inspection(
        replace(result, report=replace(result.report, before=before))
    )
    assert {(c.category, c.kind, c.entity_ids) for c in snapshot.original.categories} == {
        ("boundary_edges", "edge", (0, 2)),
        ("winding_conflicts", "edge", (2,)),
        ("unused_edges", "edge", (7,)),
        ("nonmanifold_vertices", "vertex", (1,)),
        ("unused_vertices", "vertex", (6,)),
        ("nonmanifold_edges", "edge", (3,)),
        ("collapsed_edges", "edge", (9,)),
        ("invalid_faces", "polygonal_face", (1,)),
        ("duplicate_faces", "polygonal_face", (2,)),
    }


def test_partial_triangulation_preserves_face_ids_and_resolvable_boundaries():
    """P11/P15/P16: one concave face cannot remove supported neighbors."""
    import numpy as np

    from cad_integrity import inspection
    from cad_integrity.models import PolyhedralBRep

    mesh = PolyhedralBRep.from_polygons(
        [
            (0, 0, 0),
            (1, 0, 0),
            (0, 1, 0),
            (3, 0, 0),
            (5, 0, 0),
            (4, 0.5, 0),
            (5, 2, 0),
            (3, 2, 0),
            (6, 0, 0),
            (7, 0, 0),
            (7, 1, 0),
            (6, 1, 0),
        ],
        [(0, 1, 2), (3, 4, 5, 6, 7), (8, 9, 10, 11)],
    )
    display = inspection.triangulate_for_inspection(mesh)
    assert display.triangle_source_faces.tolist() == [0, 2, 2]
    assert [(i.face_id, i.code) for i in display.issues] == [(1, "unsupported_face")]
    assert display.boundary_source_faces.tolist().count(1) == 5
    np.testing.assert_array_equal(display.triangles[0], (0, 1, 2))


def test_projection_preflights_counts_before_triangulation():
    """P28/P29: display budgets include polygon expansion, with an exact boundary."""

    from cad_integrity import inspection
    from cad_integrity.errors import ResourceLimitExceeded
    from cad_integrity.fixtures import cube
    from cad_integrity.pipeline import RepairPipeline

    result = RepairPipeline().run(cube())
    with pytest.raises(ResourceLimitExceeded, match="display triangles"):
        inspection.project_polygonal_inspection(
            result, limits=inspection.ProjectionLimits(max_display_triangles=11)
        )
    snapshot = inspection.project_polygonal_inspection(
        result, limits=inspection.ProjectionLimits(max_display_triangles=12)
    )
    assert len(snapshot.original.display.triangles) == 12


def test_saved_example_delivers_snapshot_alongside_retained_artifacts(tmp_path):
    """I01/I04/I06: real controller carries inspection without changing checks."""
    from cad_integrity.gradio_app import run_polygonal_fixture
    from cad_integrity.workbench_results import ArtifactStore

    outcome = run_polygonal_fixture(
        "01_detached_reversed_cap", artifact_store=ArtifactStore(tmp_path)
    )
    assert outcome.inspection is not None
    assert outcome.inspection.candidate is not None
    assert len(outcome.inspection.original.categories) == 9
    assert outcome.release.candidate.path.is_file()


def test_wire_payload_retains_source_faces_units_and_stage_scopes():
    """A01/A12: JSON projection consumes the snapshot, not figures or files."""
    from cad_integrity import inspection
    from cad_integrity.fixtures import cube
    from cad_integrity.pipeline import RepairPipeline

    payload = inspection.encode_inspection(
        inspection.project_polygonal_inspection(RepairPipeline().run(cube()))
    )
    assert payload["schema_version"] == 2
    original, candidate = payload["meshes"]
    assert original["id"] != candidate["id"]
    assert original["length_unit"] == "mm"
    assert original["face_count"] == 6
    assert original["triangle_source_faces"] == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
    original["positions"][0] = 700
    assert candidate["positions"][0] != 700


def test_broken_wire_keeps_only_resolvable_segments_and_reported_face():
    """P19/P24: no invented closure or topology reclassification."""

    import numpy as np

    from cad_integrity.inspection import project_polygonal_inspection
    from cad_integrity.models import PolyhedralBRep
    from cad_integrity.pipeline import RepairPipeline

    mesh = PolyhedralBRep(
        np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [2, 2, 0.0]]),
        np.array([[0, 1], [1, 2], [2, 3]]),
        np.array([0, 3]),
        np.array([1, 2, 3]),
    )
    result = RepairPipeline().run(mesh)
    snapshot = project_polygonal_inspection(result)
    assert snapshot.original.display.triangles.shape == (0, 3)
    assert snapshot.original.display.boundary_segments.tolist() == [[0, 1], [1, 2], [2, 3]]
    assert next(
        c for c in snapshot.original.categories if c.category == "invalid_faces"
    ).entity_ids == (0,)
    assert result.report.before.invalid_face_ids == (0,)


def test_all_owned_connectivity_and_nested_memberships_resist_mutation():
    from dataclasses import FrozenInstanceError

    from cad_integrity.fixtures import cube
    from cad_integrity.inspection import project_polygonal_inspection
    from cad_integrity.pipeline import RepairPipeline

    mesh = project_polygonal_inspection(RepairPipeline().run(cube())).original
    for array in [
        mesh.vertices,
        mesh.edges,
        mesh.face_offsets,
        mesh.face_coedges,
        mesh.display.triangles,
        mesh.display.triangle_source_faces,
        mesh.display.boundary_segments,
        mesh.display.boundary_source_faces,
    ]:
        with pytest.raises(ValueError):
            array.setflags(write=True)
    with pytest.raises(FrozenInstanceError):
        mesh.categories[0].entity_ids = (3,)


def test_g1_mixed_polygons_have_worked_areas_and_correct_winding():
    import numpy as np

    from cad_integrity.inspection import triangulate_for_inspection
    from cad_integrity.models import PolyhedralBRep

    mesh = PolyhedralBRep.from_polygons(
        [
            (0, 0, 0),
            (1, 0, 0),
            (0, 1, 0),
            (3, 0, 0),
            (4, 0, 0),
            (4, 1, 0),
            (3, 1, 0),
            (6, 0, 0),
            (8, 0, 0),
            (9, 1, 0),
            (7, 3, 0),
            (6, 1, 0),
        ],
        [(0, 1, 2), (3, 4, 5, 6), (7, 8, 9, 10, 11)],
    )
    display = triangulate_for_inspection(mesh)
    for face, expected in enumerate([0.5, 1, 5.5]):
        xyz = mesh.vertices[display.triangles[display.triangle_source_faces == face]]
        signed = np.cross(xyz[:, 1] - xyz[:, 0], xyz[:, 2] - xyz[:, 0])[:, 2] / 2
        assert np.all(signed > 0)
        assert signed.sum() == pytest.approx(expected)
    reverse = PolyhedralBRep.from_polygons(
        mesh.vertices, [(2, 1, 0), (6, 5, 4, 3), (11, 10, 9, 8, 7)]
    )
    shown = triangulate_for_inspection(reverse)
    xyz = reverse.vertices[shown.triangles]
    assert np.all(np.cross(xyz[:, 1] - xyz[:, 0], xyz[:, 2] - xyz[:, 0])[:, 2] < 0)


def test_installed_inspection_component_exposes_valid_parent_api_schema():
    from cad_integrity.gradio_app import build_app

    app = build_app(inspection_enabled=True)
    assert "run_example" in str(app.get_api_info())


def test_candidate_write_failure_keeps_runtime_inspection_without_download(tmp_path, monkeypatch):
    """D02/I12: exercise the NumPy filesystem boundary, not internal release code."""
    import numpy as np

    from cad_integrity.gradio_app import run_polygonal_fixture
    from cad_integrity.workbench_results import ArtifactStore, Completion

    write = np.savez

    def fail_candidate(file, *args, **kwargs):
        if str(file).endswith("candidate.npz"):
            raise OSError("disk write failed")
        return write(file, *args, **kwargs)

    monkeypatch.setattr(np, "savez", fail_candidate)
    outcome = run_polygonal_fixture(
        "01_detached_reversed_cap", artifact_store=ArtifactStore(tmp_path)
    )
    assert outcome.completion is Completion.INCOMPLETE
    assert outcome.release.candidate is None
    assert not outcome.decision_brief.candidate_available
    assert outcome.inspection.candidate is not None
    assert outcome.release.source.path.is_file()


def test_inspection_delivery_can_omit_legacy_figures_without_changing_release(tmp_path):
    from cad_integrity.gradio_app import run_polygonal_fixture
    from cad_integrity.workbench_results import ArtifactStore

    outcome = run_polygonal_fixture(
        "01_detached_reversed_cap",
        artifact_store=ArtifactStore(tmp_path),
        include_legacy_figures=False,
    )
    assert outcome.original_figure is None and outcome.candidate_figure is None
    assert outcome.inspection.original.display.triangles.shape[1] == 3
    assert outcome.release.candidate.path.is_file()


def test_raw_display_input_preserves_valid_neighbor_and_omits_invalid_references():
    """P19/P20: display admission is distinct from numerical carrier admission."""
    import numpy as np

    from cad_integrity import inspection

    raw = inspection.InspectionGeometryInput(
        np.array([[0.0, 0, 0], [1, 0, 0], [0, 1, 0]]),
        np.array([[0, 1], [1, 2], [2, 0], [2, 99]]),
        np.array([0, 3, 6]),
        np.array([1, 2, 3, 1, 4, 999]),
    )
    display = inspection.triangulate_for_inspection(raw)
    assert display.triangles.tolist() == [[0, 1, 2]]
    assert display.triangle_source_faces.tolist() == [0]
    assert display.boundary_segments[display.boundary_source_faces == 1].tolist() == [[0, 1]]
    assert [(i.face_id, i.code) for i in display.issues] == [(1, "unresolved_reference")]


def test_installed_transport_compresses_losslessly_and_deterministically():
    import gzip
    import json
    from pathlib import Path

    from gradio_inspectionworkspace import InspectionWorkspace

    component = InspectionWorkspace()
    document = {"schema_version": 2, "meshes": [{"repeat": list(range(10000)) * 10}]}
    wire = component.postprocess(document)
    assert wire.file.path == component.postprocess(document).file.path
    assert json.loads(gzip.decompress(Path(wire.file.path).read_bytes())) == document
    assert Path(wire.file.path).stat().st_size < len(json.dumps(document)) / 2
    assert component.postprocess({"schema_version": 2, "meshes": []}).file is None


@pytest.mark.parametrize(
    "bad",
    [
        [(3, 0, 0), (4, 0, 0), (4, 1, 0.1), (3, 1, 0)],
        [(3, 0, 0), (4, 1, 0), (3, 1, 0), (4, 0, 0)],
        [(3, 0, 0), (4, 0, 0), (5, 0, 0)],
    ],
)
def test_unfillable_face_never_removes_its_supported_neighbor(bad):
    from cad_integrity.inspection import triangulate_for_inspection
    from cad_integrity.models import PolyhedralBRep

    mesh = PolyhedralBRep.from_polygons(
        [(0, 0, 0), (1, 0, 0), (0, 1, 0), *bad], [(0, 1, 2), tuple(range(3, 3 + len(bad)))]
    )
    display = triangulate_for_inspection(mesh)
    assert display.triangles.tolist() == [[0, 1, 2]]
    assert display.triangle_source_faces.tolist() == [0]
    assert len(display.issues) == 1 and display.issues[0].face_id == 1
    assert display.boundary_source_faces.tolist().count(1) == len(bad)


def test_supported_faces_do_not_duplicate_source_edges_in_fallback_geometry():
    from cad_integrity.fixtures import cube
    from cad_integrity.inspection import triangulate_for_inspection

    display = triangulate_for_inspection(cube())
    assert len(display.triangles) == 12
    assert display.boundary_segments.shape == (0, 2)
    assert len(display.boundary_source_faces) == 0


def test_transport_cache_failure_is_an_explicit_unavailable_result(monkeypatch, tmp_path):
    import os

    from gradio_inspectionworkspace import InspectionWorkspace

    component = InspectionWorkspace()
    component.GRADIO_CACHE = str(tmp_path)

    def deny(*args):
        raise OSError("cache write denied")

    monkeypatch.setattr(os, "replace", deny)
    result = component.postprocess({"schema_version": 2, "meshes": [{"id": "test"}]})
    assert result.file is None
    assert "cache write denied" in result.error
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]


def test_qualified_workspace_is_the_default_polygonal_display():
    from cad_integrity.gradio_app import build_app

    config = build_app().get_config_file()
    inspection = next(c for c in config["components"] if c["type"] == "inspectionworkspace")
    assert inspection["props"]["visible"] is True


def test_projection_failure_is_visible_and_retained_without_losing_release(monkeypatch, tmp_path):
    import json

    import gradio as gr

    import cad_integrity.gradio_app as parent
    from cad_integrity.errors import ResourceLimitExceeded
    from cad_integrity.workbench_results import ArtifactStore

    def unavailable(*args, **kwargs):
        raise ResourceLimitExceeded("display allocation limit")

    monkeypatch.setattr(parent, "project_polygonal_inspection", unavailable)
    outcome = parent.run_polygonal_fixture("00_clean_boss", artifact_store=ArtifactStore(tmp_path))
    assert outcome.inspection is None
    evidence = next(a.path for a in outcome.release.derived if a.path.name == "evidence.json")
    assert any(
        d["stage"] == "inspection"
        for d in json.loads(evidence.read_text())["outcome"]["diagnostics"]
    )
    app = parent.build_app()
    route = next(fn.fn for fn in app.fns.values() if fn.api_name == "run_example")
    stream = route("00_clean_boss", gr.Request(session_hash="projection-failure"))
    next(stream)
    delivered = next(stream)
    assert "Inspection unavailable" in delivered[0]
    assert "display allocation limit" in delivered[0]
    assert delivered[6] and delivered[7]
    assert all(control["interactive"] for control in next(stream)[-3:])
    stream.close()
