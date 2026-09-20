from dataclasses import asdict
from pathlib import Path
import importlib.util
import json

import numpy as np
import pytest
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from mesh_healing_engine import (
    MeshError, TopologyError, ParameterizationError, StaleSystemError,
    MeshHealingEngine, SoftConstraint, MotorcycleGraphTracer, CrossFieldOptimizer,
    solve_igm_quantization, prune_motorcycle_graph, parameterize_macro_patch,
)
from mesh_export import export_frontend_json, export_step, UVSurfaceMap
from example_pipeline import original_example, seam_example, run


@pytest.fixture
def grid():
    v, f, b = original_example()
    return MeshHealingEngine(v, f), b


def planar_grid(n=5, perturb=False):
    v = np.array([[float(x), float(y), 0.] for y in range(n) for x in range(n)])
    if perturb:
        rng = np.random.default_rng(1729)
        for y in range(1, n - 1):
            for x in range(1, n - 1):
                v[y * n + x, :2] += rng.uniform(-.3, .3, 2)
    f = [[y*n+x, y*n+x+1, (y+1)*n+x+1, (y+1)*n+x]
         for y in range(n-1) for x in range(n-1)]
    b = {y*n+x: tuple(v[y*n+x, :2]) for y in range(n) for x in range(n)
         if x in (0, n-1) or y in (0, n-1)}
    internal = sorted(set(range(len(v))) - set(b))
    return MeshHealingEngine(v, f), internal, b


def test_cotangent_matrix_return_symmetry_constant_kernel_and_psd(grid):
    e, _ = grid
    W = e.compute_cotangent_weights()
    assert sp.isspmatrix_csr(W)
    np.testing.assert_allclose(W.toarray(), W.T.toarray(), atol=1e-14)
    L = e.compute_cotangent_laplacian()
    np.testing.assert_allclose(L @ np.ones(e.num_vertices), 0., atol=1e-14)
    assert np.linalg.eigvalsh(L.toarray()).min() >= -1e-12


def test_single_right_triangle_weights():
    e = MeshHealingEngine(np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]]), [[0,1,2]])
    W = e.compute_cotangent_weights().toarray()
    np.testing.assert_allclose(W, [[0,.5,.5],[.5,0,0],[.5,0,0]])


def test_negative_cotangent_not_clamped():
    e = MeshHealingEngine(np.array([[0.,0.,0.],[2.,0.,0.],[.3,.1,0.]]), [[0,1,2]])
    W = e.compute_cotangent_weights().toarray()
    assert W[0,1] < 0
    assert np.linalg.eigvalsh(e.compute_cotangent_laplacian().toarray()).min() >= -1e-12


def test_quad_diagonal_is_in_matrix_but_not_polygon_adjacency():
    e = MeshHealingEngine(np.array([[0.,0.,0.],[2.,0.,0.],[1.5,1.,0.],[0.,1.,0.]]), [[0,1,2,3]])
    assert 2 not in e.adjacency[0]
    assert abs(e.compute_cotangent_weights()[0,2]) > 1e-8


@pytest.mark.parametrize('scale', [1e-9, 1., 1e9])
def test_cotangents_are_scale_invariant(scale):
    e, _, _ = planar_grid(4, perturb=True)
    baseline = e.compute_cotangent_weights().toarray()
    e.v3d *= scale
    np.testing.assert_allclose(e.compute_cotangent_weights().toarray(), baseline, rtol=1e-11, atol=1e-11)


def test_planar_affine_precision_on_irregular_grid():
    e, internal, b = planar_grid(5, perturb=True)
    T = np.array([[1.4,.2],[-.1,.8]])
    offset = np.array([3.,-2.])
    b = {v: tuple(T @ q + offset) for v,q in b.items()}
    uv = e.compute_harmonic_map(internal, b)
    expected = e.v3d[:,:2] @ T.T + offset
    np.testing.assert_allclose([uv[i] for i in range(len(e.v3d))], expected, atol=1e-12)


def test_original_example_values(grid):
    e, b = grid
    uv = e.compute_harmonic_map([4], b)
    np.testing.assert_allclose(uv[4], [0.9999563025210634, 1.0000686696947936], atol=1e-13)
    assert all(uv[v] == b[v] for v in b)
    assert e.last_uv_quality.locally_valid


def test_boundary_update_reuses_factorization(grid):
    e, b = grid
    s = e.prepare_harmonic_system([4], list(b))
    base = s.solve(b)
    T = np.array([[1.2,.1],[0.,.9]])
    t = np.array([.2,-.3])
    moved = s.solve({v: tuple(T @ q + t) for v,q in b.items()})
    np.testing.assert_allclose(moved[4], T @ base[4] + t, atol=1e-13)
    assert s.factorization_count == 1
    assert s.last_relative_residual < 1e-12


def test_woodbury_matches_full_refactor_and_target_changes_reuse():
    e, internal, b = planar_grid(6, perturb=True)
    s = e.prepare_harmonic_system(internal, list(b))
    ids = internal[:3]
    anchors = {v: SoftConstraint(tuple(e.v3d[v,:2] + [.04,-.03]), 1.5) for v in ids}
    uv = s.solve(b, soft_constraints=anchors)
    expected_rhs = -s.L_IB @ np.array([b[v] for v in s.boundary])
    d = np.zeros(len(internal))
    for v,a in anchors.items():
        k = s._internal_index[v]
        d[k] = a.weight
        expected_rhs[k] += a.weight * np.array(a.target)
    expected = spla.splu(s.A + sp.diags(d, format='csc')).solve(expected_rhs)
    np.testing.assert_allclose([uv[v] for v in internal], expected, atol=1e-12)
    assert s.last_update_method == 'woodbury'
    anchors2 = {v: SoftConstraint(tuple(np.array(a.target) + [.01,.01]), a.weight) for v,a in anchors.items()}
    s.solve(b, soft_constraints=anchors2)
    assert s.factorization_count == 1
    assert s.low_rank_update_count == 1
    # Removing all soft observations must recover the original harmonic solution.
    restored = s.solve(b, soft_constraints={})
    np.testing.assert_allclose([restored[v] for v in internal], e.v3d[internal,:2], atol=1e-12)


def test_high_rank_soft_constraints_refactor():
    e, internal, b = planar_grid(4)
    s = e.prepare_harmonic_system(internal, list(b), max_update_rank=1)
    s.solve(b, soft_constraints={v: SoftConstraint(tuple(e.v3d[v,:2]), .2) for v in internal})
    assert s.last_update_method == 'refactor'
    assert s.factorization_count == 2


def test_zero_weight_soft_anchor_has_no_effect(grid):
    e, b = grid
    s = e.prepare_harmonic_system([4], list(b))
    baseline = s.solve(b)
    other = s.solve(b, soft_constraints={4: SoftConstraint((100.,100.),0.)})
    np.testing.assert_allclose(other[4], baseline[4])


def test_soft_anchor_on_boundary_rejected(grid):
    e,b = grid
    s = e.prepare_harmonic_system([4],list(b))
    with pytest.raises(MeshError):
        s.solve(b,soft_constraints={0:SoftConstraint((1.,1.),1.)})


def test_face_confidence_preserves_psd_and_rebuilds(grid):
    e,b = grid
    L = e.compute_cotangent_laplacian(face_confidence={0:.2,1:0.})
    assert np.linalg.eigvalsh(L.toarray()).min() >= -1e-12
    s = e.prepare_harmonic_system([4],list(b))
    weighted = s.with_face_confidence({0:.25})
    assert weighted is not s
    assert not np.allclose(weighted.A.toarray(),s.A.toarray())
    weighted.solve(b)


def test_zero_confidence_disconnection_is_not_silently_pinned(grid):
    e,b = grid
    with pytest.raises(ParameterizationError, match='Unanchored'):
        e.prepare_harmonic_system([4],list(b),face_confidence={i:0. for i in range(4)})


def test_masked_contamination_repair_keeps_trusted_values(grid):
    e,b = grid
    uv = e.compute_harmonic_map([4],b)
    bad = dict(uv)
    bad[4] = (100.,-90.)
    repaired = e.repair_contaminated_coordinates(bad,[4])
    np.testing.assert_allclose(repaired[4],uv[4])
    assert all(repaired[v] == uv[v] for v in b)


def test_stale_factorization_detects_in_place_geometry_edit(grid):
    e,b = grid
    s = e.prepare_harmonic_system([4],list(b))
    e.v3d[4,2] += .1
    with pytest.raises(StaleSystemError):
        s.solve(b)


def test_stale_factorization_detects_preprocess(grid):
    e,b = grid
    s = e.prepare_harmonic_system([4],list(b))
    e.preprocess()
    with pytest.raises(StaleSystemError):
        s.solve(b)


def test_partial_patch_requires_explicit_faces(grid):
    e,_ = grid
    b = {v:tuple(e.v3d[v,:2]) for v in [0,1,4,3]}
    with pytest.raises(MeshError):
        e.compute_harmonic_map([],b)
    assert e.compute_harmonic_map([],b,face_ids=[0]) == b


def test_missing_boundary_rejected(grid):
    e,b = grid
    b.pop(0)
    with pytest.raises(ParameterizationError,match='Boundary'):
        e.prepare_harmonic_system([0,4],list(b))


def test_unanchored_closed_component_rejected():
    v=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]])
    f=[[0,2,1],[0,1,3],[1,2,3],[2,0,3]]
    e=MeshHealingEngine(v,f)
    with pytest.raises(ParameterizationError,match='Unanchored'):
        e.prepare_harmonic_system([0,1,2,3],[])


def test_boundary_only_and_orientation_failures():
    e=MeshHealingEngine(np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]]),[[0,1,2]])
    good={0:(0.,0.),1:(1.,0.),2:(0.,1.)}
    assert e.compute_harmonic_map([],good)==good
    with pytest.raises(ParameterizationError,match='flipped'):
        e.compute_harmonic_map([],{0:(0.,0.),1:(0.,1.),2:(1.,0.)})
    with pytest.raises(ParameterizationError,match='collapsed'):
        e.compute_harmonic_map([],{0:(0.,0.),1:(1.,0.),2:(2.,0.)})


def test_disconnected_two_patches_each_anchored():
    v=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[3.,0.,0.],[4.,0.,0.],[3.,1.,0.]])
    e=MeshHealingEngine(v,[[0,1,2],[3,4,5]])
    b={i:tuple(p[:2]) for i,p in enumerate(v)}
    assert e.compute_harmonic_map([],b)==b


def test_stitch_preserves_representative_coordinates_and_resets_adjacency():
    e=seam_example()
    before=e.v3d.copy()
    count=e.non_manifold_stitching()
    assert count==2
    np.testing.assert_array_equal(e.v3d,before[[0,1,2,3,5,6]])
    assert e.faces==[[0,1,2,3],[1,4,5,2]]
    assert set(e.adjacency)==set(range(6))
    assert all(v<6 for ns in e.adjacency.values() for v in ns)
    assert e.topology_report().is_oriented_manifold
    assert len(e.topology_report().boundary_edges)==6
    assert e.non_manifold_stitching()==0


def test_real_distance_across_spatial_hash_bucket_boundary():
    e=seam_example()
    # A round(tolerance) binning algorithm would split these close endpoints.
    e.v3d[[1,2],0]=1.+.49e-5
    e.v3d[[4,7],0]=1.+.51e-5
    e._build_topology()
    assert e.non_manifold_stitching(1e-5)==2


def test_actual_distance_outside_tolerance_is_not_welded():
    e=seam_example()
    e.v3d[[4,7],0]=1.+2e-5
    assert e.non_manifold_stitching(1e-5)==0


def test_vertex_only_touch_not_welded():
    v=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,0.],[-1.,0.,0.],[0.,-1.,0.]])
    e=MeshHealingEngine(v,[[0,1,2],[3,4,5]])
    assert e.non_manifold_stitching()==0
    assert e.num_vertices==6


def test_overlapping_duplicate_sheets_not_auto_welded():
    v=np.array([[0.,0.,0.],[1.,0.,0.],[1.,1.,0.],[0.,1.,0.]]*2)
    e=MeshHealingEngine(v,[[0,1,2,3],[4,5,6,7]])
    assert e.non_manifold_stitching()==0
    assert e.num_vertices==8


def test_explicit_duplicate_face_weld_rejected():
    v=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]]*2)
    e=MeshHealingEngine(v,[[0,1,2],[3,4,5]])
    e.non_manifold_stitching(seam_pairs=[((0,1),(3,4)),((1,2),(4,5)),((0,2),(3,5))])
    assert e.topology_report().is_oriented_manifold
    assert e.num_vertices>=4 # Must not become two identical triangles on three IDs.
    assert e.last_stitch_report.rejected


def test_bowtie_split_and_one_to_many_provenance():
    v=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[-1.,0.,0.],[0.,-1.,0.]])
    e=MeshHealingEngine(v,[[0,1,2],[0,3,4]])
    assert e.topology_report().nonmanifold_vertices==[0]
    p=e.preprocess()
    assert p.split_vertices==1
    assert len(p.old_to_new_vertices[0])==2
    assert e.topology_report().is_oriented_manifold
    b=p.remap_constraints({0:(0.,0.)})
    assert len(b)==2


def test_two_bowtie_vertices_split_without_stale_incidence():
    v=np.array([[0.,0.,0.],[2.,0.,0.],[1.,1.,0.],[-1.,0.,0.],[0.,-1.,0.],
                [3.,0.,0.],[2.,-1.,0.]])
    e=MeshHealingEngine(v,[[0,1,2],[0,3,4],[1,5,6]])
    p=e.preprocess(stitch=False)
    assert p.split_vertices==2
    assert e.topology_report().is_oriented_manifold


def test_multi_sheet_edge_rejected_transactionally():
    v=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,-1.,0.],[0.,0.,1.]])
    e=MeshHealingEngine(v,[[0,1,2],[1,0,3],[0,1,4]])
    signature=e._fingerprint()
    with pytest.raises(TopologyError,match='Three-plus'):
        e.preprocess()
    assert e._fingerprint()==signature


def test_degenerate_duplicate_and_unused_pruning(grid):
    e,_=grid
    e.v3d=np.vstack((e.v3d,[[100.,100.,100.]]))
    e.faces += [e.faces[0][::-1],[0,0,0]]
    e._build_topology()
    p=e.preprocess()
    assert p.removed_faces==[4,5]
    assert p.old_to_new_vertices[9]==()
    assert e.num_vertices==9


def test_inconsistent_winding_repaired():
    e=seam_example()
    e.preprocess()
    e.faces[1].reverse()
    e._build_topology()
    assert e.topology_report().inconsistent_winding_edges
    e.preprocess()
    assert e.topology_report().is_oriented_manifold


def test_winding_repair_preserves_warped_quad_surface():
    vertices = np.array([[0., 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                         [2, 0, 0], [2, 1, .1]])
    engine = MeshHealingEngine(vertices, [[0, 1, 2, 3], [1, 2, 5, 4]])
    triangles, _ = engine.triangulated_faces()
    surface = {frozenset(t) for t in triangles}
    weights = engine.compute_cotangent_weights().toarray()
    engine.preprocess(stitch=False)
    repaired, _ = engine.triangulated_faces()
    assert {frozenset(t) for t in repaired} == surface
    np.testing.assert_allclose(engine.compute_cotangent_weights().toarray(), weights)
    assert engine.topology_report().is_oriented_manifold


def test_winding_repair_preserves_warped_polygon_surface():
    vertices = np.array([[0., 0, 0], [1, 0, 0], [1.5, 1, .1],
                         [.5, 1.5, 0], [-.5, 1, 0], [.5, -1, 0]])
    engine = MeshHealingEngine(vertices, [[0, 1, 5], [0, 1, 2, 3, 4]])
    triangles, _ = engine.triangulated_faces()
    surface = {frozenset(t) for t in triangles}
    weights = engine.compute_cotangent_weights().toarray()
    engine.preprocess(stitch=False)
    repaired, _ = engine.triangulated_faces()
    assert {frozenset(t) for t in repaired} == surface
    np.testing.assert_allclose(engine.compute_cotangent_weights().toarray(), weights)
    assert engine.topology_report().is_oriented_manifold


def test_fan_split_preserves_warped_polygon_surface():
    vertices = np.array([[0., 0, 0], [1, 0, 0], [1.5, 1, .1],
                         [.5, 1.5, 0], [-.5, 1, 0], [-1, -1, 0], [0, -1, 0]])
    engine = MeshHealingEngine(vertices, [[0, 5, 6], [0, 1, 2, 3, 4]])
    before, _ = engine.triangulated_faces()
    surface = {frozenset(tuple(engine.v3d[v]) for v in tri) for tri in before}
    report = engine.preprocess(stitch=False)
    after, _ = engine.triangulated_faces()
    assert report.split_vertices == 1
    assert {frozenset(tuple(engine.v3d[v]) for v in tri) for tri in after} == surface


def test_preprocess_retains_finite_large_nondegenerate_face():
    small = np.array([[0., 0, 0], [1, 0, 0], [0, 1, 0]])
    large = small * 1e155
    large[:, 2] = 1e155
    engine = MeshHealingEngine(np.vstack((small, large)), [[0, 1, 2], [3, 4, 5]])
    report = engine.preprocess(stitch=False)
    assert report.removed_faces == []
    assert len(engine.faces) == 2


@pytest.mark.parametrize('scale', [1e-200, 1e155])
def test_cotangent_weights_are_finite_at_extreme_uniform_scales(scale):
    vertices = np.array([[0., 0, 0], [scale, 0, 0], [0, scale, 0]])
    engine = MeshHealingEngine(vertices, [[0, 1, 2]])
    with np.errstate(all='raise'):
        weights = engine.compute_cotangent_weights().toarray()
    # Right isosceles triangle: cot(45 degrees)/2 on the two legs,
    # cot(90 degrees)/2 on the hypotenuse, independent of physical scale.
    np.testing.assert_allclose(weights, [[0., .5, .5], [.5, 0., 0.], [.5, 0., 0.]])


def test_preprocess_numeric_range_failure_rolls_back():
    vertices = np.array([[0., 0, 0], [1, 0, 0], [0, 1, 0],
                         [-1e308, 0, 0], [1e308, 0, 0], [0, 1e308, 0]])
    engine = MeshHealingEngine(vertices, [[0, 1, 2], [3, 4, 5]])
    before = engine._fingerprint()
    with pytest.raises(MeshError, match='range'):
        engine.preprocess(stitch=False)
    assert engine._fingerprint() == before


@pytest.mark.parametrize('uv', [
    {0: (0., 0.), 1: (1e200, 1e200), 2: (2e200, 2e200)},
    {0: (0., 0.), 1: (1e200, 0.), 2: (0., 1e200)},
])
def test_uv_overflow_cannot_validate_or_publish(tmp_path, uv):
    engine = MeshHealingEngine(np.array([[0., 0, 0], [1, 0, 0], [0, 1, 0]]), [[0, 1, 2]])
    destination = tmp_path / 'chart.json'
    destination.write_text('existing artifact')
    with pytest.raises(MeshError, match='range'):
        engine.validate_uv(uv)
    with pytest.raises(MeshError, match='range'):
        export_frontend_json(engine, destination, uv)
    assert destination.read_text() == 'existing artifact'


def test_json_export_accepts_numpy_face_selection(tmp_path, grid):
    engine, boundary = grid
    uv = engine.compute_harmonic_map([4], boundary)
    path = export_frontend_json(engine, tmp_path / 'subset.json', uv,
                                face_ids=np.array([2, 0], dtype=np.int64))
    value = json.loads(path.read_text())
    assert value['polygon_ids'] == [2, 0]
    assert value['triangle_parent_faces'] == [2, 2, 0, 0]


@pytest.mark.parametrize('scale', [1e200, 1e-200])
def test_cross_field_normal_scale_does_not_change_transport(scale):
    centroids = np.array([[0., 0, 0], [1., 0, 0]])
    normals = np.array([[0., 0, 1], [0., 1, 1]])
    reference = CrossFieldOptimizer(centroids, normals, {0: [1]})
    scaled = CrossFieldOptimizer(centroids, normals * scale, {0: [1]})
    np.testing.assert_allclose(scaled.normals, reference.normals)
    np.testing.assert_allclose(scaled.optimize_field(), reference.optimize_field())


def test_constraints_conflicting_at_weld_fail():
    e=seam_example()
    p=e.preprocess()
    with pytest.raises(MeshError,match='Conflicting'):
        p.remap_constraints({1:(1.,0.),4:(9.,0.)})
    mapped=p.remap_constraints({1:(1.,0.),4:(1.,0.)})
    assert len(mapped)==1


def test_preprocess_preserves_real_open_boundary(grid):
    e,_=grid
    before=len(e.topology_report().boundary_edges)
    p=e.preprocess()
    assert p.stitched_vertices==0
    assert len(e.topology_report().boundary_edges)==before==8


def test_concave_quad_uses_valid_alternate_diagonal():
    e=MeshHealingEngine(np.array([[0.,0.,0.],[.2,.2,0.],[1.,0.,0.],[0.,1.,0.]]),[[0,1,2,3]])
    tris,_=e.triangulated_faces()
    assert len(tris)==2
    assert any(set([1,3]) <= set(t) for t in tris)
    uv={v:tuple(p[:2]) for v,p in enumerate(e.v3d)}
    assert e.validate_uv(uv).locally_valid


def test_simple_ngon_ear_clipping():
    v=np.array([[0.,0.,0.],[2.,0.,0.],[2.,1.,0.],[1.,.5,0.],[0.,1.,0.]])
    e=MeshHealingEngine(v,[[0,1,2,3,4]])
    tris,_=e.triangulated_faces()
    assert len(tris)==3
    assert e.validate_uv({i:tuple(p[:2]) for i,p in enumerate(v)}).locally_valid


def test_self_intersecting_quad_rejected():
    v=np.array([[0.,0.,0.],[1.,1.,0.],[0.,1.,0.],[1.,0.,0.]])
    e=MeshHealingEngine(v,[[0,1,2,3]])
    with pytest.raises(MeshError):
        e.compute_cotangent_weights()


@pytest.mark.parametrize('tolerance',[0.,-1.,float('nan'),float('inf')])
def test_bad_stitch_tolerance(tolerance):
    with pytest.raises(MeshError):
        seam_example().non_manifold_stitching(tolerance)


def test_pruner_integrates_stitching_and_edge_id_remapping():
    e=seam_example()
    tracer=MotorcycleGraphTracer.from_mesh(e)
    ends=tracer.edge_vertex_map()
    result=prune_motorcycle_graph({0:list(ends)},0.,{},mesh_engine=e,edge_vertices=ends,return_report=True)
    assert result.preprocessing.stitched_vertices==2
    assert len(set(result.old_to_new_edges.values()))==7
    assert e.num_vertices==6
    with pytest.raises(StaleSystemError):
        tracer.compute_graph()
    assert all(v<6 for pair in result.edge_vertices.values() for v in pair)


def test_pruner_refuses_missing_endpoint_map_before_mutating():
    e=seam_example()
    signature=e._fingerprint()
    with pytest.raises(MeshError,match='edge_vertices'):
        prune_motorcycle_graph({0:[1]},0.,{1:1.},mesh_engine=e)
    assert e._fingerprint()==signature


def test_pruner_missing_lengths_and_protected_tracks():
    with pytest.raises(MeshError,match='length'):
        prune_motorcycle_graph({0:[4]},.5,{})
    assert prune_motorcycle_graph({0:[4],1:[5]},.5,{4:.1,5:1.})=={1:[5]}
    assert prune_motorcycle_graph({0:[4]},.5,{4:.1},protected_tracks=[0])=={0:[4]}


def test_pruner_late_error_rolls_back():
    e=seam_example()
    before=e._fingerprint()
    with pytest.raises(MeshError):
        prune_motorcycle_graph({0:[999]},0.,{},mesh_engine=e,edge_vertices={0:(0,1)})
    assert before==e._fingerprint()


def test_legacy_uniform_helper_and_geometry_route(grid):
    e,b=grid
    with pytest.warns(FutureWarning,match='uniform'):
        uniform=parameterize_macro_patch([4],b,e.adjacency)
    np.testing.assert_allclose(uniform[4],[1.,1.])
    cotan=parameterize_macro_patch([4],b,e.adjacency,mesh_engine=e)
    assert not np.allclose(cotan[4],uniform[4],atol=1e-6)
    with pytest.raises(MeshError,match='angles'):
        parameterize_macro_patch([4],b,e.adjacency,weighting='cotangent')


@pytest.mark.parametrize('broken_next', [None, 999])
def test_halfedge_operations_reject_broken_connectivity(grid, broken_next):
    engine, _ = grid
    tracer = MotorcycleGraphTracer.from_mesh(engine)
    tracer.half_edges[0].next_he = broken_next
    with pytest.raises(TopologyError, match='next_he'):
        tracer.edge_vertex_map()
    with pytest.raises(TopologyError, match='next_he'):
        tracer.find_straight_ahead_opposite(0)


def test_halfedge_tracer_records_exit_boundary_and_repeatable_graph(grid):
    e,_=grid
    t=MotorcycleGraphTracer.from_mesh(e)
    path=t.trace_single_motorcycle(0)
    assert len(path)==3
    assert len(path)==len(set(path))
    t.vertices[4].is_singularity=True
    assert t.compute_graph()==t.compute_graph()


def test_halfedge_builder_rejects_triangle():
    e=MeshHealingEngine(np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]]),[[0,1,2]])
    with pytest.raises(TopologyError,match='all-quad'):
        MotorcycleGraphTracer.from_mesh(e)


def test_igm_original_constraints_and_integrality():
    p=[{'horizontal_top':[0,1],'horizontal_bottom':[2],'vertical_left':[3],'vertical_right':[4]}]
    x=solve_igm_quantization([3.2,4.9,7.8,5.1,5.3],p)
    assert np.issubdtype(x.dtype,np.integer)
    assert x[0]+x[1]==x[2]
    assert x[3]==x[4]
    assert np.sum(abs(x-np.array([3.2,4.9,7.8,5.1,5.3])))==pytest.approx(.9)


def test_igm_repeated_segment_coefficients_accumulate():
    p=[{'horizontal_top':[0,0],'horizontal_bottom':[1],'vertical_left':[2],'vertical_right':[2]}]
    x=solve_igm_quantization([2.,4.,3.],p)
    assert 2*x[0]==x[1]
    np.testing.assert_array_equal(x,[2,4,3])


def test_igm_infeasible_and_bad_segment_id():
    p=[{'horizontal_top':[0,0],'horizontal_bottom':[0],'vertical_left':[0],'vertical_right':[0]}]
    with pytest.raises(RuntimeError):
        solve_igm_quantization([1.],p)
    p[0]['horizontal_bottom']=[999]
    with pytest.raises(MeshError):
        solve_igm_quantization([1.],p)


def test_igm_without_structural_constraints():
    np.testing.assert_array_equal(solve_igm_quantization([1.2,2.8,0.],[]),[1,3,1])
    assert solve_igm_quantization([],[]).shape==(0,)


def test_cross_field_returns_finite_unit_values_and_anchors_components():
    c=np.array([[0.,0.,0.],[1.,0.,0.],[3.,0.,0.]])
    n=np.array([[0.,0.,2.]]*3)
    o=CrossFieldOptimizer(c,n,{0:[1],1:[0],2:[]})
    z=o.optimize_field()
    assert z.shape==(3,)
    np.testing.assert_allclose(abs(z),1.)
    assert o.last_gauge_faces==[0,2]


def test_cross_field_transport_is_reciprocal():
    c=np.array([[0.,0.,0.],[1.,0.,0.]])
    n=np.array([[0.,0.,1.],[.2,.3,1.]])
    o=CrossFieldOptimizer(c,n,{0:[1]})
    assert o._transport(0,1)==pytest.approx(o._transport(1,0).conjugate())
    z=o.optimize_field(sharp_threshold_degrees=180)
    assert z[0]==pytest.approx(o._transport(0,1)*z[1])


def test_cross_field_feature_tangent_is_plane_intersection():
    o=CrossFieldOptimizer(np.array([[0.,0.,0.],[1.,1.,0.]]),
                         np.array([[0.,0.,1.],[0.,1.,0.]]),{0:[1]})
    tangent=o.estimate_feature_tangent(0,[1])
    assert abs(tangent[0])==pytest.approx(1.)
    assert o.optimize_field().shape==(2,)


def test_cross_field_zero_confidence_and_normal_validation():
    o=CrossFieldOptimizer(np.array([[0.,0.,0.],[1.,0.,0.]]),
                         np.array([[0.,0.,1.],[0.,0.,1.]]),{0:[1]})
    z=o.optimize_field(face_confidence={0:0.})
    assert len(o.last_gauge_faces)==2
    np.testing.assert_allclose(abs(z),1.)
    with pytest.raises(MeshError,match='nonzero'):
        CrossFieldOptimizer(np.zeros((1,3)),np.zeros((1,3)),{})


def test_frontend_json_contains_both_coordinate_sets(tmp_path,grid):
    e,b=grid
    uv=e.compute_harmonic_map([4],b)
    path=export_frontend_json(e,tmp_path/'nested'/'patch.json',uv)
    doc=json.loads(path.read_text())
    assert doc['schema']=='mesh-healing-uv/1.0'
    assert len(doc['triangles'])==8
    assert len(doc['polygons'])==4
    np.testing.assert_allclose(doc['positions'],e.v3d)
    np.testing.assert_allclose(doc['uv'],[uv[i] for i in range(9)])
    assert doc['uv_bounds']['max']==[2.,2.]


def test_uv_evaluator_reproduces_vertices_centroids_and_outside_rejection(grid):
    e,b=grid
    uv=e.compute_harmonic_map([4],b)
    m=UVSurfaceMap(e,uv)
    queries=m.uv.mean(axis=1)
    actual=m.evaluate(queries,np.arange(len(m.triangles),dtype=int))
    np.testing.assert_allclose(actual,m.xyz.mean(axis=1),atol=1e-12)
    np.testing.assert_allclose(m.sample(np.array([uv[i] for i in range(9)])),e.v3d,atol=1e-12)
    with pytest.raises(MeshError,match='outside'):
        m.sample([[99.,99.]])
    with pytest.raises(MeshError,match='integer'):
        m.evaluate([[.5,.5]],[0.5])
    e.v3d[0,2]+=.1
    with pytest.raises(StaleSystemError):
        m.sample([[.5,.5]])


def test_uv_evaluator_detects_overlapping_charts():
    v=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.],[1.,0.,1.],[0.,1.,1.]])
    e=MeshHealingEngine(v,[[0,1,2],[3,4,5]])
    uv={i:tuple(p[:2]) for i,p in enumerate(v)}
    m=UVSurfaceMap(e,uv)
    with pytest.raises(ParameterizationError,match='overlapping'):
        m.sample([[.2,.2]])


@pytest.mark.step
@pytest.mark.parametrize('space',['uv','xyz'])
def test_real_step_roundtrip(tmp_path,grid,space):
    pytest.importorskip('cadquery')
    e,b=grid
    uv=e.compute_harmonic_map([4],b)
    result=export_step(e,tmp_path/f'{space}.step',coords_2d=uv,space=space)
    assert result.roundtrip_valid
    assert result.imported_faces==8
    assert result.imported_solids==0
    assert result.area_relative_error<1e-10
    assert 'ISO-10303-21' in result.path.read_text()
    assert 'ADVANCED_FACE' in result.path.read_text()
    assert 'FILE_SCHEMA' in result.path.read_text()


@pytest.mark.step
@pytest.mark.parametrize('units',['mm','m','in'])
def test_step_units_and_uv_scale(tmp_path,grid,units):
    pytest.importorskip('cadquery')
    e,b=grid
    uv=e.compute_harmonic_map([4],b)
    result=export_step(e,tmp_path/f'{units}.step',coords_2d=uv,space='uv',units=units,uv_scale=3.)
    assert result.roundtrip_valid
    assert result.bounds_absolute_error<1e-6


@pytest.mark.step
def test_compatibility_step_name_now_real(tmp_path,grid):
    pytest.importorskip('cadquery')
    e,b=grid
    uv=e.compute_harmonic_map([4],b)
    with pytest.warns(DeprecationWarning):
        result=e.export_mock_step_structure(str(tmp_path/'old_api.stp'),uv)
    assert result.roundtrip_valid


def test_end_to_end_original_and_seam_examples(tmp_path):
    result=run(tmp_path,write_step=False)
    assert result['base_factorization_count']==1
    assert result['total_factorization_count']==1
    assert result['soft_update_method']=='woodbury'
    assert result['affine_equivariance_error']<1e-12
    assert result['stitched_vertices']==2
    assert (tmp_path/'raw_mesh.npz').exists()
