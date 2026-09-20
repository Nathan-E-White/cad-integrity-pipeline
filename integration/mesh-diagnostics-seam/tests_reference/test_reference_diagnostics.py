from __future__ import annotations
from dataclasses import replace
from io import BytesIO
import importlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile
import numpy as np
import pytest
from pydantic import ValidationError
from mesh_diagnostics import (
    TriangleMesh, MeshLimits, MeshValidationError, triangle_quality, edge_topology,
    AuditPolicy, audit_mesh, payload_from_audit, adapt_legacy_payload, mesh_from_mapping,
    MeshPayload, FaceTarget, EdgeTarget, Metric, assemble_payload,
    load_npz_arrays, load_triangle_mesh, ArchiveLimits,
)


def equilateral(scale=1.0):
    return TriangleMesh(np.array([[0,0,0], [1,0,0], [.5,np.sqrt(3)/2,0]]) * scale, [[0,1,2]])


def tetra():
    return TriangleMesh([[0,0,0], [1,0,0], [0,1,0], [0,0,1]],
                        [[0,2,1], [0,1,3], [1,2,3], [2,0,3]])


def test_equilateral_reference_values():
    q = triangle_quality(equilateral())
    np.testing.assert_allclose(q.mean_ratio, 1)
    np.testing.assert_allclose(q.radius_aspect, 1)
    assert not q.degenerate.any()


@pytest.mark.parametrize("scale", [1e-150, 1e-12, 1, 1e12, 1e150])
def test_quality_is_scale_invariant(scale):
    q = triangle_quality(equilateral(scale))
    np.testing.assert_allclose(q.mean_ratio, 1, atol=1e-14)
    np.testing.assert_allclose(q.radius_aspect, 1, atol=1e-14)


def test_right_triangle_values():
    q = triangle_quality(TriangleMesh([[0,0,0],[1,0,0],[0,1,0]], [[0,1,2]]))
    np.testing.assert_allclose(q.mean_ratio, np.sqrt(3)/2)
    np.testing.assert_allclose(q.radius_aspect, (1+np.sqrt(2))/2)


def test_rotation_and_translation():
    m = equilateral()
    rotated = m.positions @ np.array([[0,-1,0],[1,0,0],[0,0,1]]) + [10,-20,30]
    np.testing.assert_allclose(triangle_quality(TriangleMesh(rotated, m.triangles)).mean_ratio, 1)


def test_reversing_triangle_does_not_sign_unsigned_quality():
    m = equilateral()
    forward = triangle_quality(m, reference_normals=np.array([[0,0,1]]))
    reverse = triangle_quality(TriangleMesh(m.positions, [[0,2,1]]), reference_normals=np.array([[0,0,1]]))
    np.testing.assert_allclose(forward.mean_ratio, reverse.mean_ratio)
    np.testing.assert_allclose(forward.reference_alignment, 1)
    np.testing.assert_allclose(reverse.reference_alignment, -1)


@pytest.mark.parametrize("normals", [np.array([[0,0,0]]), np.array([[np.nan,0,1]]), np.ones((3,3))])
def test_invalid_reference_normals(normals):
    with pytest.raises(MeshValidationError): triangle_quality(equilateral(), reference_normals=normals)


def test_degenerate_quality_is_explicit_and_json_is_finite():
    m = TriangleMesh([[0,0,0], [1,0,0], [2,0,0]], [[0,1,2]])
    q = triangle_quality(m)
    assert q.degenerate.all() and np.isinf(q.radius_aspect).all()
    payload = payload_from_audit(audit_mesh(m))
    json.dumps(payload.model_dump(), allow_nan=False)
    metric = next(x for x in payload.metrics if x.id == "maximum_radius_aspect")
    assert metric.value is None and metric.status == "fail"


def test_degenerate_is_failure_even_with_zero_quality_threshold():
    m = TriangleMesh([[0,0,0]], [[0,0,0]])
    payload = payload_from_audit(audit_mesh(m, AuditPolicy(min_mean_ratio=0)))
    assert next(x for x in payload.metrics if x.id == "low_shape_quality").value == 1


def test_closed_tetrahedron_edge_incidence():
    t = edge_topology(tetra())
    assert len(t.edges) == 6 and (t.counts == 2).all()
    assert not len(t.boundary_edges) and not len(t.nonmanifold_edges) and not len(t.winding_conflict_edges)
    assert t.offsets[-1] == 12


def test_single_triangle_has_three_boundary_edges_not_three_loops():
    t = edge_topology(equilateral())
    assert len(t.boundary_edges) == 3


def test_three_face_edge_is_distinct_from_boundary():
    m = TriangleMesh([[0,0,0],[1,0,0],[0,1,0],[0,-1,0],[0,0,1]], [[0,1,2],[1,0,3],[0,1,4]])
    t = edge_topology(m)
    np.testing.assert_array_equal(t.nonmanifold_edges, [[0,1]])
    assert len(t.boundary_edges) == 6 and len(t.winding_conflict_edges) == 0


def test_winding_conflict_detected_separately():
    m = TriangleMesh([[0,0,0],[1,0,0],[0,1,0],[0,-1,0]], [[0,1,2],[0,1,3]])
    np.testing.assert_array_equal(edge_topology(m).winding_conflict_edges, [[0,1]])


def test_duplicates_all_members_and_repeated_indices():
    m = TriangleMesh([[0,0,0],[1,0,0],[0,1,0]], [[0,1,2],[2,1,0],[0,0,1]])
    t = edge_topology(m)
    np.testing.assert_array_equal(t.duplicate_faces, [0,1])
    np.testing.assert_array_equal(t.repeated_vertex_faces, [2])
    assert (t.counts == 2).all()  # repeated-index face excluded; no fabricated manifold pass
    payload = payload_from_audit(audit_mesh(m))
    assert next(x for x in payload.metrics if x.id == "boundary_edges").status == "not_checked"


def test_edge_manifold_does_not_imply_vertex_manifold():
    first = tetra()
    positions = np.vstack([first.positions, -first.positions[1:]])
    mapping = np.array([0,4,5,6])
    triangles = np.vstack([first.triangles, mapping[first.triangles]])
    m = TriangleMesh(positions, triangles)
    t = edge_topology(m)
    assert (t.counts == 2).all()  # Two tetrahedral shells touch at one vertex.
    p = payload_from_audit(audit_mesh(m))
    assert next(x for x in p.metrics if x.id == "full_validation").status == "not_checked"


def test_open_surface_policy_changes_status_not_geometry():
    m = equilateral()
    closed = payload_from_audit(audit_mesh(m))
    opened = payload_from_audit(audit_mesh(m, AuditPolicy(require_closed_surface=False)))
    assert next(x for x in closed.metrics if x.id == "boundary_edges").status == "fail"
    assert next(x for x in opened.metrics if x.id == "boundary_edges").status == "info"
    assert closed.geometry_revision == opened.geometry_revision
    assert closed.diagnostic_revision != opened.diagnostic_revision


@pytest.mark.parametrize("v,f", [([], []), ([[0,0,0]], [])])
def test_empty_mesh_has_no_false_overall_pass(v,f):
    p = payload_from_audit(audit_mesh(TriangleMesh(v,f)))
    json.dumps(p.model_dump(), allow_nan=False)
    assert next(x for x in p.metrics if x.id == "minimum_mean_ratio").status == "not_checked"


@pytest.mark.parametrize("vertices,faces", [
    ([[0,0,0]], [[-1,0,0]]), ([[0,0,0]], [[1,0,0]]),
    ([[0,0,0]], [[0.,0.,0.]]), ([[0,0,0]], [[True,False,True]]),
    ([[np.nan,0,0]], []), ([[np.inf,0,0]], []), ([[0,0]], []),
    ([[0,0,0]], [[0,0,0,0]]), ([[0,0,0]], [0,0]),
])
def test_bad_input_rejected_before_unsigned_cast(vertices,faces):
    with pytest.raises(MeshValidationError): TriangleMesh(vertices,faces)


def test_flat_input_and_owned_readonly_snapshot():
    v = np.array([0.,0.,0.,1.,0.,0.,0.,1.,0.])
    m = TriangleMesh(v,[0,1,2])
    v[0] = 17
    assert m.positions[0,0] == 0 and not m.positions.flags.writeable
    assert m.positions.shape == (3,3)


def test_geometry_hash_changes_when_triangle_order_changes():
    m = tetra()
    assert m.geometry_revision != TriangleMesh(m.positions, m.triangles[::-1]).geometry_revision


def test_limits():
    with pytest.raises(MeshValidationError): TriangleMesh([[0,0,0]], [], limits=MeshLimits(max_vertices=0))


@pytest.mark.parametrize("policy", [{"min_mean_ratio": -1}, {"max_radius_aspect": 0},
                                   {"relative_area_tolerance": np.nan}, {"require_closed_surface": 1}])
def test_invalid_policy(policy):
    with pytest.raises(ValueError): AuditPolicy(**policy)


def test_contract_validates_targets_and_metric_links():
    p = payload_from_audit(audit_mesh(equilateral())).model_dump()
    p["targets"][0]["geometry_revision"] = "another-revision"
    with pytest.raises(ValidationError): MeshPayload.model_validate(p)
    p = payload_from_audit(audit_mesh(equilateral())).model_dump()
    p["metrics"][0]["target_id"] = "absent"
    with pytest.raises(ValidationError): MeshPayload.model_validate(p)


@pytest.mark.parametrize("mutator", [
    lambda p: p["triangles"].__setitem__(0,-1),
    lambda p: p["triangles"].__setitem__(0,True),
    lambda p: p["positions"].__setitem__(0,float("nan")),
    lambda p: p["metrics"].append(p["metrics"][0]),
    lambda p: p["targets"].append(p["targets"][0]),
    lambda p: p.update(triangle_parent_faces=[1,2]),
])
def test_bad_wire_contract(mutator):
    p = payload_from_audit(audit_mesh(equilateral())).model_dump()
    mutator(p)
    with pytest.raises(ValidationError): MeshPayload.model_validate(p)


def test_legacy_counts_flat_inputs_without_claiming_pass():
    m = equilateral()
    p = adapt_legacy_payload({"vertices": m.positions.ravel(), "indices": m.triangles.ravel()})
    assert [x.value for x in p.metrics] == [3,1]
    assert all(x.status == "info" for x in p.metrics)


def test_legacy_diagnostics_remain_reachable_without_ids():
    m = equilateral()
    p = adapt_legacy_payload({"vertices":m.positions, "faces":m.triangles,
        "error_edges":m.positions[[[0,1]]], "failed_face_ids":[0],
        "metrics":[{"label":"Something", "value":1, "status":"fail"}]})
    assert len(p.targets) == 2
    assert {m.target_id for m in p.metrics if m.target_id} == {t.id for t in p.targets}


def test_ambiguous_aliases_rejected():
    with pytest.raises(MeshValidationError): mesh_from_mapping({"positions":[],"vertices":[],"faces":[]})


def test_safe_npz_roundtrip(tmp_path):
    m = equilateral()
    path = tmp_path / "triangle.npz"
    np.savez_compressed(path, vertices=m.positions, faces=m.triangles)
    loaded = load_triangle_mesh(path)
    np.testing.assert_allclose(loaded.positions,m.positions)
    np.testing.assert_array_equal(loaded.triangles,m.triangles)


def test_pickled_npz_is_rejected(tmp_path):
    path = tmp_path / "object.npz"
    np.savez(path, vertices=np.array([{"malicious":"object"}], dtype=object), faces=np.empty((0,3),dtype=int))
    with pytest.raises(MeshValidationError): load_npz_arrays(path)


def test_npz_unknown_member_and_budget(tmp_path):
    path = tmp_path / "metadata.npz"
    np.savez(path, vertices=[], faces=[], metrics=np.array(["not supported"]))
    with pytest.raises(MeshValidationError): load_npz_arrays(path)
    with pytest.raises(MeshValidationError): load_npz_arrays(path, ArchiveLimits(max_compressed_bytes=1))


def test_npz_lying_npy_header_rejected_before_allocation(tmp_path):
    buffer = BytesIO()
    np.lib.format.write_array_header_1_0(buffer, {"descr":"<f8", "fortran_order":False, "shape":(10**12,3)})
    path = tmp_path / "oversized.npz"
    with ZipFile(path,"w") as archive: archive.writestr("vertices.npy", buffer.getvalue())
    with pytest.raises(MeshValidationError): load_npz_arrays(path)


def test_npz_duplicate_members_rejected(tmp_path):
    buffer=BytesIO(); np.save(buffer,np.zeros((0,3)))
    path=tmp_path/"duplicate.npz"
    with ZipFile(path,"w") as archive:
        archive.writestr("vertices.npy",buffer.getvalue())
        with pytest.warns(UserWarning): archive.writestr("vertices.npy",buffer.getvalue())
    with pytest.raises(MeshValidationError): load_npz_arrays(path)


def test_gradio_adapter_serialization_and_schema():
    pytest.importorskip("gradio")
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"gradio_adapter"))
    adapter=importlib.import_module("meshdiagnostics")
    component=adapter.MeshDiagnostics(render=False)
    p=component.postprocess(component.example_value())
    assert p.schema_version == "mesh-diagnostics/1"
    assert component.postprocess(None) is None
    assert component.preprocess(p)["triangles"] == [0,1,2]
    assert "properties" in component.api_info()
    with pytest.raises(TypeError): component.postprocess("/arbitrary/server/path.npz")
