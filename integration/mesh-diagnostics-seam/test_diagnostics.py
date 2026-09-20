import numpy as np
import pytest
from cad_mesh_inspector.arrays import mesh_arrays
from cad_mesh_inspector.diagnostics import edge_incidence, triangle_quality
from cad_mesh_inspector import inspect_triangles

V = np.array([[0.,0.,0.], [1.,0.,0.], [.5,np.sqrt(3)/2,0.], [0.,0.,1.]])
F = np.array([[0,1,2]])

@pytest.mark.parametrize("scale", [1e-100, 1e-4, 1., 1e4, 1e100])
def test_equilateral_scale_invariance(scale):
    q = triangle_quality(V * scale, F)
    np.testing.assert_allclose(q.mean_ratios, 1., rtol=1e-12)
    np.testing.assert_allclose(q.radius_ratios, 1., rtol=1e-12)
    assert not q.degenerate_face_ids.size


def test_reversing_winding_does_not_make_mean_ratio_signed():
    np.testing.assert_array_equal(triangle_quality(V,F).mean_ratios, triangle_quality(V,F[:,::-1]).mean_ratios)


def test_sliver_and_degenerate_are_not_given_fake_area():
    v=np.array([[0.,0.,0.],[1.,0.,0.],[1.,1e-8,0.],[2.,0.,0.]])
    q=triangle_quality(v,np.array([[0,1,2],[0,1,3],[0,0,1]]))
    assert 0 < q.mean_ratios[0] < 1e-6
    assert list(q.degenerate_face_ids) == [1,2]
    assert list(q.areas[1:]) == [0.,0.]
    assert np.isinf(q.radius_ratios[1:]).all()


def test_triangle_boundary_edges_are_not_three_loops():
    r=edge_incidence(V,F)
    assert r.boundary_edges.shape == (3,2)
    assert r.nonmanifold_edges.shape == (0,2)


def test_nonmanifold_three_faces_share_one_edge():
    v=np.vstack([V,[0.,0.,-1.]])
    r=edge_incidence(v,np.array([[0,1,2],[1,0,3],[0,1,4]]))
    assert r.nonmanifold_edges.tolist()==[[0,1]]


def test_winding_conflicts_distinct_from_edge_degree():
    bad=edge_incidence(V,np.array([[0,1,2],[0,1,3]]))
    good=edge_incidence(V,np.array([[0,1,2],[1,0,3]]))
    assert bad.winding_conflict_edges.tolist()==[[0,1]]
    assert not good.winding_conflict_edges.size
    assert not bad.nonmanifold_edges.size


def test_closed_tetrahedron_incidence():
    f=np.array([[0,2,1],[0,1,3],[1,2,3],[2,0,3]])
    r=edge_incidence(V,f)
    assert not r.boundary_edges.size and not r.winding_conflict_edges.size
    assert np.all(r.counts==2)


def test_duplicate_rows_and_repeated_vertices_preserved():
    r=edge_incidence(V,np.array([[0,1,2],[2,1,0],[0,0,1]]))
    assert r.duplicate_face_ids.tolist()==[0,1]
    assert r.repeated_vertex_face_ids.tolist()==[2]
    assert not np.any(r.edges[:,0]==r.edges[:,1])


def test_empty_arrays_work():
    assert triangle_quality([],[]).mean_ratios.size==0
    assert edge_incidence([],[]).edges.shape==(0,2)

@pytest.mark.parametrize("faces", [np.array([[-1,1,2]]), np.array([[0,1,4]]), np.array([[0.,1.,2.]]), np.array([[True,False,True]]), np.array([[0,1,2,3]])])
def test_invalid_connectivity_rejected_before_unsigned_cast(faces):
    with pytest.raises(ValueError): mesh_arrays(V,faces)

@pytest.mark.parametrize("bad", [np.nan,np.inf,-np.inf])
def test_nonfinite_coordinates_rejected(bad):
    v=V.copy();v[0,0]=bad
    with pytest.raises(ValueError): mesh_arrays(v,F)


def test_flat_inputs_count_entities_not_coordinates():
    p=inspect_triangles(V.ravel(),F.ravel(),mesh_id="m",revision="1",frame_id="world")
    assert next(m.value for m in p.metrics if m.id=="vertices")==4
    assert next(m.value for m in p.metrics if m.id=="triangles")==1


def test_boundaries_are_policy_not_automatic_failure():
    a=inspect_triangles(V,F,mesh_id="m",revision="1",frame_id="world")
    b=inspect_triangles(V,F,mesh_id="m",revision="1",frame_id="world",require_closed=True)
    assert next(m.status for m in a.metrics if m.id=="boundary")=="info"
    assert next(m.status for m in b.metrics if m.id=="boundary")=="fail"


def test_no_mutation_and_tolerance_units():
    v=V.copy();f=F.copy()
    q=triangle_quality(v,f,area_tolerance=.5)
    assert q.degenerate_face_ids.tolist()==[0]
    np.testing.assert_array_equal(v,V);np.testing.assert_array_equal(f,F)

@pytest.mark.parametrize("threshold", [-1,1.1,np.nan,np.inf])
def test_bad_threshold(threshold):
    with pytest.raises(ValueError): inspect_triangles(V,F,mesh_id="m",revision="1",frame_id="world",minimum_mean_ratio=threshold)
