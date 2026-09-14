"""Regression checks for the shipped fixtures, not a general mesh certification suite."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pytest
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from case_fixtures import CASES, load_arrays, load_brep, repair_policy, saved_report
from cad_integrity import BRepHomologyStitchAnalyzer, RepairPipeline

EXPECTED = {
    '00_clean_boss': ((1, 0, 1), 0, 0, 0),
    '01_detached_reversed_cap': ((2, 0, 0), 128, 0, 0),
    '01_welded_not_oriented': ((1, 0, 1), 0, 64, 0),
    '01_repaired_cap': ((1, 0, 1), 0, 0, 0),
    '02_pinched_vertex': ((1, 0, 2), 0, 0, 1),
}


@pytest.mark.parametrize('case', CASES)
def test_actual_diagnostics(case):
    r = BRepHomologyStitchAnalyzer(load_brep(case)).evaluate_stitch_integrity()
    assert (r.homology.betti_numbers, len(r.boundary_edge_ids),
            len(r.inconsistent_orientation_edge_ids), len(r.nonmanifold_vertex_ids)) == EXPECTED[case]
    assert not r.geometric_self_intersections_checked
    v, f, _ = load_arrays(case)
    assert np.array_equal(np.unique(f), np.arange(len(v)))
    area2 = np.linalg.norm(np.cross(v[f[:, 1]]-v[f[:, 0]], v[f[:, 2]]-v[f[:, 0]]), axis=1)
    assert np.all(area2 > 1e-8)
    assert len(np.unique(np.sort(f, axis=1), axis=0)) == len(f)


@pytest.mark.parametrize('case', CASES)
def test_glb_preserves_indexed_topology_and_units(case):
    v, f, _ = load_arrays(case)
    # Disable importer processing. This reads the actual saved GLB through an independent library.
    scene = trimesh.load(ROOT / 'meshes' / f'{case}.glb', process=False)
    assert isinstance(scene, trimesh.Scene)
    assert len(scene.geometry) == 1
    imported = next(iter(scene.geometry.values()))
    assert np.array_equal(imported.faces, f)
    assert len(imported.vertices) == len(v)
    assert np.allclose(imported.vertices * 1000, v, atol=4e-6, rtol=0)


@pytest.mark.parametrize('case', CASES)
def test_obj_roundtrip_exact(case):
    # OBJ canonical text order, no topology-changing importer heuristic.
    v, f, _ = load_arrays(case)
    lines = (ROOT / 'meshes' / f'{case}.obj').read_text().splitlines()
    vv = np.array([[float(x) for x in line.split()[1:]] for line in lines if line.startswith('v ')])
    ff = np.array([[int(x)-1 for x in line.split()[1:]] for line in lines if line.startswith('f ')])
    assert np.array_equal(vv, v)
    assert np.array_equal(ff, f)


def canonical_oriented(f):
    return [tuple(np.roll(t, -int(np.argmin(t)))) for t in f]


def test_repair_restores_reference_and_does_not_modify_input():
    before = load_brep('01_detached_reversed_cap')
    v0 = before.vertices.copy()
    f0 = before.face_coedges.copy()
    result = RepairPipeline(repair_policy()).run(before)
    v, f, _ = load_arrays('00_clean_boss')
    assert result.report.decision == 'topology_checks_passed'
    assert np.array_equal(result.candidate.vertices, v)
    actual_faces = np.array([result.candidate.face_vertices(i) for i in range(result.candidate.face_count)])
    assert canonical_oriented(actual_faces) == canonical_oriented(f)
    assert np.array_equal(before.vertices, v0) and np.array_equal(before.face_coedges, f0)
    rec = json.loads((ROOT / 'provenance' / 'construction.json').read_text())
    assert abs(result.report.maximum_vertex_displacement-rec['gap_mm']) < 1e-12


def test_pinched_refusal_and_supporting_plane():
    b = load_brep('02_pinched_vertex')
    r = RepairPipeline(repair_policy()).run(b)
    assert r.report.decision == 'rejected' and r.candidate is None
    assert not r.report.before.boundary_edge_ids
    assert not r.report.before.nonmanifold_edge_ids
    assert r.report.before.nonmanifold_vertex_ids == (4,)
    rec = json.loads((ROOT / 'provenance' / 'construction.json').read_text())
    v, _, _ = load_arrays('00_clean_boss')
    p = v[rec['pinched_vertex_id']]
    n = np.array(rec['support_direction'])
    distances = (v-p) @ n
    assert np.count_nonzero(np.abs(distances) < 1e-12) == 1
    assert np.all(np.delete(distances, rec['pinched_vertex_id']) < -1e-8)


def test_too_small_weld_budget_does_not_claim_success():
    from cad_integrity import RepairPolicy, WeldPolicy
    r = RepairPipeline(RepairPolicy(weld=WeldPolicy(0.001, 0.001))).run(
        load_brep('01_detached_reversed_cap'))
    assert r.report.decision == 'needs_review'
    assert len(r.report.after.boundary_edge_ids) == 128


def test_closed_reference_noop():
    b = load_brep('00_clean_boss')
    r = RepairPipeline(repair_policy()).run(b)
    assert r.report.decision == 'topology_checks_passed'
    assert np.array_equal(b.vertices, r.candidate.vertices)
    assert np.array_equal(b.face_coedges, r.candidate.face_coedges)
    assert r.report.maximum_vertex_displacement == 0
