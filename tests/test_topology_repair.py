from dataclasses import replace

import numpy as np
import pytest

from cad_integrity import BRepHomologyStitchAnalyzer, RepairPipeline, RepairPolicy, WeldPolicy, analyze_mesh
from cad_integrity.errors import InvalidGeometry, RepairRejected, ResourceLimitExceeded
from cad_integrity.fixtures import cracked_cube, cube, disk, pinched_tetrahedra, torus
from cad_integrity.models import PolyhedralBRep, TriangleMesh
from cad_integrity.pipeline import fingerprint
from cad_integrity.repair import synchronize_orientations, weld_vertices


def report(brep):
    return BRepHomologyStitchAnalyzer(brep).evaluate_stitch_integrity()


@pytest.mark.parametrize("builder,betti,closed", [
    (cube, (1, 0, 1), True),
    (disk, (1, 0, 0), False),
    (lambda: cube(missing_face=1), (1, 0, 0), False),
    (cracked_cube, (2, 0, 0), False),
])
def test_basic_topology(builder, betti, closed):
    r = report(builder())
    assert r.homology.betti_numbers == betti
    assert r.is_closed_oriented_2manifold is closed


def test_torus_handle_is_not_a_leak():
    r = analyze_mesh(torus())
    assert r.homology.betti_numbers == (1, 2, 1)
    assert r.is_closed_oriented_2manifold
    assert not r.boundary_edge_ids


def test_vertex_link_detects_pinch_missed_by_edge_incidence():
    r = analyze_mesh(pinched_tetrahedra())
    assert not r.boundary_edge_ids
    assert not r.nonmanifold_edge_ids
    assert r.nonmanifold_vertex_ids == (0,)
    assert not r.is_closed_oriented_2manifold


def test_edge_zero_has_two_distinct_orientations():
    b = cube()
    assert 1 in b.face_coedges and -1 in b.face_coedges
    assert len(b.edges) == 12  # No dummy row.
    assert not np.any(b.face_coedges == 0)


def test_array_ownership_and_readonly():
    coordinates = disk().vertices.copy()
    b = PolyhedralBRep.from_polygons(coordinates, [(0, 1, 2, 3)])
    coordinates[:] = 99
    assert b.vertices[0, 0] == 0
    with pytest.raises(ValueError):
        b.vertices[0, 0] = 99


@pytest.mark.parametrize("which", ["nan", "fractional_indices", "bad_index", "zero_token", "bad_offsets"])
def test_malformed_input_rejected(which):
    b = disk()
    with pytest.raises(InvalidGeometry):
        if which == "nan":
            replace(b, vertices=np.full_like(b.vertices, np.nan))
        elif which == "fractional_indices":
            replace(b, edges=b.edges.astype(float)+0.2)
        elif which == "bad_index":
            replace(b, edges=b.edges+100)
        elif which == "zero_token":
            replace(b, face_coedges=np.zeros_like(b.face_coedges))
        else:
            replace(b, face_offsets=np.array([1, 4], dtype=np.int64))


def test_broken_wire_report_does_not_fabricate_betti():
    b = disk()
    tokens = b.face_coedges.copy()
    tokens[1] *= -1
    r = report(replace(b, face_coedges=tokens))
    assert r.invalid_face_ids == (0,)
    assert r.homology is None
    assert not r.is_closed_oriented_2manifold


def test_reversal_must_reverse_order_and_signs():
    b = cube(reversed_face=1)
    assert report(b).inconsistent_orientation_edge_ids
    corrected = synchronize_orientations(b)
    assert corrected.flipped_face_ids
    assert report(corrected.candidate).is_closed_oriented_2manifold
    for f in range(corrected.candidate.face_count):
        assert len(corrected.candidate.face_vertices(f)) == 4


def test_all_disconnected_components_oriented():
    left, right = cube(reversed_face=1), cube(reversed_face=3)
    points = np.vstack((left.vertices, right.vertices+(30, 0, 0)))
    polygons = [left.face_vertices(i) for i in range(left.face_count)]
    polygons += [tuple(v+8 for v in right.face_vertices(i)) for i in range(right.face_count)]
    combined = PolyhedralBRep.from_polygons(points, polygons)
    corrected = synchronize_orientations(combined)
    after = report(corrected.candidate)
    assert after.is_closed_oriented_2manifold
    assert after.homology.betti_numbers == (2, 0, 2)


def test_nonorientable_mobius_strip_rejected():
    n = 7
    points = []
    for i in range(n):
        theta = 2*np.pi*i/n
        for width in (-0.2, 0.2):
            points.append(((1+width*np.cos(theta/2))*np.cos(theta),
                           (1+width*np.cos(theta/2))*np.sin(theta), width*np.sin(theta/2)))
    polygons = []
    for i in range(n):
        a, b = 2*i, 2*i+1
        c, d = (2*(i+1), 2*(i+1)+1) if i < n-1 else (1, 0)
        polygons.extend(((a, c, b), (b, c, d)))
    strip = PolyhedralBRep.from_polygons(np.array(points), polygons)
    with pytest.raises(RepairRejected, match="inconsistent"):
        synchronize_orientations(strip)


def test_vertex_weld_also_deduplicates_edges():
    b = cracked_cube()
    before = fingerprint(b)
    welded = weld_vertices(b, WeldPolicy(0.005, 0.005))
    assert welded.removed_vertex_count == 4
    assert welded.removed_edge_count == 4
    assert welded.maximum_displacement == pytest.approx(0.002)
    assert fingerprint(b) == before
    assert len(welded.old_to_new_vertex) == len(b.vertices)
    assert report(synchronize_orientations(welded.candidate).candidate).is_closed_oriented_2manifold


def test_welding_idempotent():
    policy = WeldPolicy(0.005, 0.005)
    first = weld_vertices(cracked_cube(), policy)
    second = weld_vertices(first.candidate, policy)
    assert second.removed_vertex_count == 0
    assert second.removed_edge_count == 0
    assert second.maximum_displacement == 0
    assert fingerprint(first.candidate) == fingerprint(second.candidate)


def test_distance_chain_does_not_transitively_collapse():
    # Three nearby vertices in three separate triangles. Pairwise neighborhoods overlap,
    # but vertex 2 is farther than tolerance from representative vertex 0.
    points = np.array(((0,0,0),(.75,0,0),(1.5,0,0),
                       (0,10,0),(0,10,3),(10,10,0),(10,10,3),(20,10,0),(20,10,3)), dtype=float)
    b = PolyhedralBRep.from_polygons(points, ((0,3,4),(1,5,6),(2,7,8)))
    # Joining only at a vertex would create a pinch, so the conservative repair rejects
    # this candidate rather than presenting a geometrically close but nonmanifold result.
    with pytest.raises(RepairRejected, match="nonmanifold"):
        weld_vertices(b, WeldPolicy(1.0, 1.0))


def test_welding_rejects_collapsed_edge():
    with pytest.raises(RepairRejected, match="collapse"):
        weld_vertices(disk(), WeldPolicy(2, 2))


def test_weld_resource_limit():
    with pytest.raises(ResourceLimitExceeded):
        weld_vertices(cracked_cube(), WeldPolicy(.005, .005, max_candidate_visits=1))


def test_duplicate_faces_not_accepted():
    b = cube()
    polygons = [b.face_vertices(i) for i in range(b.face_count)]
    polygons.append(polygons[0])
    r = report(PolyhedralBRep.from_polygons(b.vertices, polygons))
    assert r.duplicate_face_ids == (6,)
    assert r.nonmanifold_edge_ids
    assert r.homology is None


def test_unused_topology_is_not_silently_dropped():
    b = cube()
    extra = replace(b, vertices=np.vstack((b.vertices, (100, 100, 100))))
    r = report(extra)
    assert r.unused_vertex_ids == (8,)
    assert not r.is_closed_oriented_2manifold
    assert r.homology.betti_numbers == (2, 0, 1)


def test_pipeline_events_and_no_op_input_ownership():
    events = []
    b = cracked_cube()
    result = RepairPipeline(RepairPolicy(weld=WeldPolicy(.005, .005))).run(b, on_event=events.append)
    assert result.report.decision == "topology_checks_passed"
    assert [e.stage for e in events] == ["analyze", "weld", "orient", "verify", "complete"]
    assert result.original is b
    assert result.report.before.homology.betti_numbers == (2, 0, 0)
    assert result.report.after.homology.betti_numbers == (1, 0, 1)
    assert result.report.after.geometric_self_intersections_checked is False


def test_default_pipeline_does_not_weld():
    result = RepairPipeline().run(cracked_cube())
    assert result.report.decision == "needs_review"
    assert result.report.maximum_vertex_displacement == 0


def test_pipeline_failure_does_not_return_candidate():
    result = RepairPipeline(RepairPolicy(weld=WeldPolicy(2, 2))).run(disk())
    assert result.report.decision == "rejected"
    assert result.candidate is None
    assert result.report.after is None


def test_nonplanar_face_not_fan_triangulated():
    b = disk()
    points = b.vertices.copy()
    points[2, 2] = 0.2
    with pytest.raises(InvalidGeometry, match="nonplanar"):
        replace(b, vertices=points).triangulate_convex_faces()


def test_empty_boundary_does_not_pass():
    empty = PolyhedralBRep.from_polygons(np.empty((0, 3)), [])
    assert not report(empty).is_closed_oriented_2manifold


def test_mesh_does_not_silently_drop_duplicate_facets():
    mesh = TriangleMesh(np.array(((0,0,0),(1,0,0),(0,1,0)),dtype=float),
                        np.array(((0,1,2),(2,1,0)),dtype=np.int64))
    with pytest.raises(InvalidGeometry, match="Duplicate"):
        mesh.to_simplicial_complex()
