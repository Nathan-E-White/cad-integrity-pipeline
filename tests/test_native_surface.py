"""Owned surface contracts through the installed host interface."""
import numpy as np

from cad_integrity.models import PolyhedralBRep
from cad_integrity.surface import prepare_surface


def test_owned_surface_preserves_concave_face_and_diagonal():
    raw = PolyhedralBRep.from_polygons(
        np.array([[0., 0., 0.], [2., 0., 0.], [1., .5, 0.], [0., 2., 0.]]),
        [[0, 1, 2, 3]],
    )
    surface = prepare_surface(raw)
    np.testing.assert_array_equal(surface.triangles, [[0, 1, 2], [0, 2, 3]])
    np.testing.assert_array_equal(surface.triangle_faces, [0, 0])
    assert np.count_nonzero(surface.triangle_edges == -1) == 2
    assert not surface.vertices.flags.writeable


def test_harmonic_affine_solution_and_boundary_reuse():
    raw = PolyhedralBRep.from_polygons(
        [[0,0,0], [1,0,0], [1,1,0], [0,1,0], [.4,.6,0]],
        [[0,1,4], [1,2,4], [2,3,4], [3,0,4]],
    )
    surface = prepare_surface(raw)
    system = surface.prepare_harmonic_system([4], [0,1,2,3])
    uv = system.solve({i: raw.vertices[i,:2] for i in range(4)})
    np.testing.assert_allclose(uv[4], [.4,.6], atol=1e-14)
    assert system.last_chart_assessment.admitted is not None
    shifted = system.solve({i: raw.vertices[i,:2] + [2,3] for i in range(4)})
    np.testing.assert_allclose(shifted[4], [2.4,3.6], atol=1e-14)
    assert system.factorization_count == 1


def disk():
    return PolyhedralBRep.from_polygons(
        [[0,0,0], [1,0,0], [1,1,0], [0,1,0], [.4,.6,0]],
        [[0,1,4], [1,2,4], [2,3,4], [3,0,4]],
    )


def test_soft_updates_match_refactor_reuse_targets_and_remove_anchors():
    from cad_integrity.surface import SoftConstraint
    raw = disk()
    surface = prepare_surface(raw)
    system = surface.prepare_harmonic_system([4], [0,1,2,3])
    reference = surface.prepare_harmonic_system([4], [0,1,2,3], max_update_rank=0)
    b = {i: raw.vertices[i,:2] for i in range(4)}
    for target in ((.42,.58), (.45,.61)):
        anchors = {4: SoftConstraint(target, 2.)}
        np.testing.assert_allclose(system.solve(b, soft_constraints=anchors)[4],
                                   reference.solve(b, soft_constraints=anchors)[4], atol=1e-14)
    assert system.factorization_count == 1
    assert system.low_rank_update_count == 1
    assert reference.factorization_count == 2
    np.testing.assert_allclose(system.solve(b, soft_constraints={})[4], [.4,.6])
    np.testing.assert_allclose(system.solve(b, soft_constraints={4: SoftConstraint((90.,90.),0.)})[4], [.4,.6])
    assert system.last_relative_residual < 1e-12


def test_confidence_reuses_surface_but_rebuilds_solver_and_rejects_cuts():
    import pytest

    from cad_integrity.surface import ParameterizationError
    surface = prepare_surface(disk())
    system = surface.prepare_harmonic_system([4], [0,1,2,3])
    weighted = system.with_face_confidence({0: .25})
    assert weighted.surface is surface
    assert not np.allclose(weighted.operators.stiffness.toarray(), system.operators.stiffness.toarray())
    with pytest.raises(ParameterizationError, match="Unanchored"):
        system.with_face_confidence(dict.fromkeys(range(4), 0.))


def test_chart_failure_is_evidence_without_admission_and_orientation_is_explicit():
    import pytest

    from cad_integrity.surface import ChartPolicy, ParameterizationError
    surface = prepare_surface(PolyhedralBRep.from_polygons([[0,0,0],[1,0,0],[0,1,0]], [[0,1,2]]))
    flipped = {0:(0.,0.), 1:(0.,1.), 2:(1.,0.)}
    assessment = surface.qualify_chart(flipped)
    assert assessment.quality.flipped_triangles == (0,)
    assert assessment.admitted is None
    assert surface.qualify_chart(flipped, policy=ChartPolicy(-1)).admitted is not None
    collapsed = surface.qualify_chart({0:(0.,0.), 1:(1.,0.), 2:(2.,0.)})
    assert collapsed.quality.degenerate_triangles == (0,)
    assert np.isinf(collapsed.quality.maximum_conformal_distortion)
    system = surface.prepare_harmonic_system([], [0,1,2])
    with pytest.raises(ParameterizationError, match="flipped"):
        system.solve(flipped)
    assert system.solve(flipped, check_orientation=False) == flipped
    assert system.last_chart_assessment.admitted is None
    with pytest.raises(OverflowError, match="range"):
        surface.qualify_chart({0:(0.,0.), 1:(1e200,0.), 2:(0.,1e200)})


def test_selected_patch_identity_and_snapshot_outlive_source_edits():
    raw = disk()
    surface = prepare_surface(raw, face_ids=[1,0])
    np.testing.assert_array_equal(surface.selected_faces, [1,0])
    np.testing.assert_array_equal(surface.triangle_faces, [1,0])
    np.testing.assert_array_equal(surface.source_vertices, [0,1,2,4])
    saved = surface.vertices.copy()
    raw.vertices.flags.writeable = True
    raw.vertices[:] = 100
    np.testing.assert_array_equal(surface.vertices, saved)
    import pytest
    with pytest.raises(ValueError):
        surface.vertices.flags.writeable = True
    system = surface.prepare_harmonic_system([], [0,1,2,4])
    uv = system.solve({0:(0.,0.),1:(1.,0.),2:(1.,1.),4:(.4,.6)})
    assert uv[4] == (.4,.6)
    chart = system.last_chart_assessment.admitted
    del system, surface, raw
    assert chart.uv.shape == (4,2)
    with pytest.raises(ValueError):
        chart.uv.flags.writeable = True


def test_stiffness_literal_and_output_copy_isolation():
    surface = prepare_surface(PolyhedralBRep.from_polygons([[0,0,0],[1,0,0],[0,1,0]], [[0,1,2]]))
    op = surface.assemble()
    expected = [[1.,-.5,-.5],[-.5,.5,0.],[-.5,0.,.5]]
    np.testing.assert_allclose(op.stiffness.toarray(), expected)
    changed = op.stiffness
    changed.data[:] = 99
    np.testing.assert_allclose(op.stiffness.toarray(), expected)


def test_limits_refuse_each_operation_without_partial_admission():
    from dataclasses import replace

    import pytest

    from cad_integrity.errors import ResourceLimitExceeded
    from cad_integrity.surface import SurfaceLimits
    raw = disk()
    surface = prepare_surface(raw)
    coords = {i: p[:2] for i,p in enumerate(raw.vertices)}
    for field in ("max_input_bytes", "max_owned_bytes", "max_work_steps", "max_output_bytes"):
        limits = replace(SurfaceLimits(), **{field: 0})
        with pytest.raises(ResourceLimitExceeded):
            prepare_surface(raw, limits=limits)
        with pytest.raises(ResourceLimitExceeded):
            surface.assemble({0: .5}, limits=limits)
        with pytest.raises(ResourceLimitExceeded):
            surface.qualify_chart(coords, limits=limits)
    usage = surface.usage
    exact = SurfaceLimits(usage.input_bytes, usage.owned_bytes, usage.work_steps, usage.output_bytes)
    assert prepare_surface(raw, limits=exact).usage == usage
    for field in ("max_owned_bytes", "max_work_steps", "max_output_bytes"):
        with pytest.raises(ResourceLimitExceeded):
            prepare_surface(raw, limits=replace(exact, **{field: getattr(exact,field)-1}))


def test_topology_and_geometry_refusal_is_scoped_to_selected_patch():
    import pytest

    from cad_integrity.errors import InvalidGeometry
    raw = PolyhedralBRep.from_polygons([[0,0,0],[1,0,0],[0,1,0],[1,1,0]], [[0,1,2],[1,2,3]])
    # Winding on the common edge disagrees, although cellular incidence is admitted.
    with pytest.raises(InvalidGeometry, match="topology"):
        prepare_surface(raw)
    assert len(prepare_surface(raw, face_ids=[0]).triangles) == 1
    with pytest.raises(InvalidGeometry):
        prepare_surface(raw, face_ids=[0,0])
    crossing = PolyhedralBRep.from_polygons([[0,0,0],[1,1,0],[0,1,0],[1,0,0]], [[0,1,2,3]])
    with pytest.raises(InvalidGeometry, match="geometry"):
        prepare_surface(crossing)
    with pytest.raises(InvalidGeometry, match="topology"):
        prepare_surface(disk(), face_ids=[0,2])


def test_native_binding_rejects_layout_and_keeps_opaque_ownership():
    import pytest

    from cad_integrity import _native
    raw = disk()
    lim = _native.SurfaceLimits(1000000, 1000000, 1000000, 1000000)
    args = [raw.vertices,raw.edges,raw.face_offsets,raw.face_coedges,"mm",np.arange(4,dtype=np.int64),1e-12,lim]
    for bad in (raw.vertices.astype(np.float32),raw.vertices[:,::-1],raw.vertices.astype(">f8")):
        with pytest.raises(ValueError, match="layout"):
            _native.prepare_surface(bad,*args[1:])
    with pytest.raises(TypeError):
        _native.Surface()
    owner = _native.prepare_surface(*args)
    exported = owner.arrays()
    exported["vertices"][:] = 99
    np.testing.assert_array_equal(owner.arrays()["vertices"], raw.vertices)
    invalid = raw.face_coedges.copy()
    invalid[0] = np.iinfo(np.int64).min
    with pytest.raises(ValueError):
        _native.prepare_surface(*args[:3],invalid,*args[4:])


def test_constraints_must_cover_patch_and_anchor_every_component():
    import pytest

    from cad_integrity.errors import InvalidGeometry
    from cad_integrity.surface import ParameterizationError, SoftConstraint
    surface = prepare_surface(disk())
    with pytest.raises(InvalidGeometry):
        surface.prepare_harmonic_system([4], [0,1,2])
    with pytest.raises(ParameterizationError, match="Boundary"):
        surface.prepare_harmonic_system([0,4], [1,2,3])
    system = surface.prepare_harmonic_system([4], [0,1,2,3])
    with pytest.raises(InvalidGeometry):
        system.solve({0:(0.,0.),1:(1.,0.),2:(1.,1.)})
    with pytest.raises(InvalidGeometry):
        system.solve({0:(0.,0.),1:(1.,0.),2:(1.,1.),3:(0.,1.)},
                     soft_constraints={0:SoftConstraint((0.,0.))})
    tetra = prepare_surface(PolyhedralBRep.from_polygons(
        [[0,0,0],[1,0,0],[0,1,0],[0,0,1]], [[0,2,1],[0,1,3],[1,2,3],[2,0,3]]))
    with pytest.raises(ParameterizationError, match="Unanchored"):
        tetra.prepare_harmonic_system([0,1,2,3], [])


def test_locally_valid_overlapping_sheets_do_not_claim_global_injectivity():
    raw = PolyhedralBRep.from_polygons([[0,0,0],[1,0,0],[0,1,0],[0,0,1],[1,0,1],[0,1,1]], [[0,1,2],[3,4,5]])
    surface = prepare_surface(raw)
    chart = surface.qualify_chart({i:p[:2] for i,p in enumerate(raw.vertices)})
    assert chart.admitted is not None  # Complete ambiguity resolution belongs to slice 5.


def test_woodbury_residual_and_nonfinite_intermediate_fall_back_to_refactor():
    from cad_integrity.surface import SoftConstraint
    raw = disk()
    surface = prepare_surface(raw)
    boundary = {i: raw.vertices[i,:2] for i in range(4)}
    for weight in (1e12, 1e300):
        system = surface.prepare_harmonic_system([4],[0,1,2,3])
        answer = system.solve(boundary, soft_constraints={4:SoftConstraint((.41,.59),weight)})
        np.testing.assert_allclose(answer[4], [.41,.59], atol=1e-12)
        assert system.last_update_method == "refactor-after-residual-check"
        assert np.isfinite(system.last_relative_residual)
        assert system.last_relative_residual <= 1e-10


def test_native_confidence_accepts_unaligned_contiguous_buffers():
    from cad_integrity import _native
    raw = disk()
    limits = _native.SurfaceLimits(1000000,1000000,1000000,1000000)
    handle = _native.prepare_surface(raw.vertices,raw.edges,raw.face_offsets,raw.face_coedges,
                                     "mm",np.arange(4,dtype=np.int64),1e-12,limits)
    faces = np.ndarray((1,),dtype=np.int64,buffer=bytearray(9),offset=1)
    weights = np.ndarray((1,),dtype=np.float64,buffer=bytearray(9),offset=1)
    faces[:] = 0
    weights[:] = .5
    assert faces.flags.c_contiguous and not faces.flags.aligned
    result = _native.assemble_surface(handle,faces,weights,limits).arrays()
    expected = _native.assemble_surface(handle,faces.copy(),weights.copy(),limits).arrays()
    np.testing.assert_array_equal(result["values"],expected["values"])


def test_unrepresentable_residual_normalization_cannot_pass_acceptance():
    import pytest

    from cad_integrity.surface import ParameterizationError, SoftConstraint
    raw = disk()
    system = prepare_surface(raw).prepare_harmonic_system([4],[0,1,2,3])
    with np.errstate(over="ignore",invalid="ignore"):
        with pytest.raises(ParameterizationError, match="residual"):
            system.solve({i:raw.vertices[i,:2] for i in range(4)},
                         soft_constraints={4:SoftConstraint((.6,.6),1.5e308)})
    assert system.last_chart_assessment is None
