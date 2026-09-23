"""Conforming native realization through its owned host seam."""
import numpy as np
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

from cad_integrity.brep import realize


def test_box_has_shared_connectivity_native_identity_and_surface_operators():
    result = realize(BRepPrimAPI_MakeBox(2, 3, 4).Shape())
    assert result.diagnostics == ()
    assert result.admitted is not None
    mesh = result.admitted.surface
    assert mesh.vertices.shape == (8, 3)
    assert mesh.triangles.shape == (12, 3)
    assert mesh.source_domain == "native_face"
    assert set(mesh.triangle_faces) == set(range(6))
    assert set(result.admitted.native_vertex_ids) == set(range(8))
    assert len(mesh.boundary_vertices) == 0
    stiffness = mesh.assemble().stiffness
    np.testing.assert_allclose(stiffness @ np.ones(8), 0, atol=1e-14)
    p = mesh.vertices[mesh.triangles]
    volume = np.einsum("ij,ij->i", p[:, 0], np.cross(p[:, 1], p[:, 2])).sum() / 6
    assert abs(volume - 24) < 1e-12


def test_periodic_cylinder_and_sphere_poles_are_closed_oriented_surfaces():
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
    for shape, exact in ((BRepPrimAPI_MakeCylinder(2, 5).Shape(), 20*np.pi),
                         (BRepPrimAPI_MakeSphere(2).Shape(), 32*np.pi/3)):
        result = realize(shape)
        assert result.diagnostics == ()
        assert result.admitted is not None
        mesh = result.admitted.surface
        assert len(mesh.boundary_vertices) == 0
        assert len(mesh.vertices) - 3*len(mesh.triangles)//2 + len(mesh.triangles) == 2
        p = mesh.vertices[mesh.triangles]
        volume = np.einsum("ij,ij->i", p[:, 0], np.cross(p[:, 1], p[:, 2])).sum()/6
        assert 0.95*exact < volume < exact


def compound(shapes):
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    builder = BRep_Builder()
    result = TopoDS_Compound()
    builder.MakeCompound(result)
    for shape in shapes:
        builder.Add(result, shape)
    return result


def test_unowned_native_entities_prevent_admission():
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.gp import gp_Pnt
    shape = compound([BRepPrimAPI_MakeBox(2, 3, 4).Shape(),
                      BRepBuilderAPI_MakeVertex(gp_Pnt(9, 9, 9)).Shape()])
    result = realize(shape)
    assert result.admitted is None
    assert result.diagnostics


def test_coincident_independent_sheets_are_never_welded():
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
    a = BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(), gp_Dir(0, 0, 1)), 0, 2, 0, 3).Face()
    b = BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(), gp_Dir(0, 0, 1)), 0, 2, 0, 3).Face()
    result = realize(compound([a, b]))
    assert result.admitted is not None, result.diagnostics
    mesh = result.admitted.surface
    assert mesh.vertices.shape == (8, 3)
    assert mesh.triangles.shape == (4, 3)
    first = set(mesh.triangles[mesh.triangle_faces == 0].ravel())
    second = set(mesh.triangles[mesh.triangle_faces == 1].ravel())
    assert first.isdisjoint(second)
    assert len(mesh.boundary_vertices) == 8


def test_holed_face_preserves_boundary_loops_and_area():
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.gp import gp_Pnt
    def wire(points):
        builder = BRepBuilderAPI_MakePolygon()
        for x, y in points:
            builder.Add(gp_Pnt(x, y, 0))
        builder.Close()
        return builder.Wire()
    builder = BRepBuilderAPI_MakeFace(wire([(0,0), (4,0), (4,4), (0,4)]))
    builder.Add(wire([(1,1), (1,3), (3,3), (3,1)]))
    result = realize(builder.Face())
    assert result.admitted is not None, result.diagnostics
    mesh = result.admitted.surface
    p = mesh.vertices[mesh.triangles]
    area = np.linalg.norm(np.cross(p[:,1]-p[:,0], p[:,2]-p[:,0]), axis=1).sum()/2
    assert abs(area-12) < 1e-12
    assert len(mesh.boundary_vertices) == 8
    assert len(mesh.vertices)-((3*len(mesh.triangles)+8)//2)+len(mesh.triangles) == 0


def test_copy_orientation_location_and_owned_lifetime():
    import gc

    from OCP.BRep import BRep_Tool
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt, gp_Trsf, gp_Vec
    from OCP.TopLoc import TopLoc_Location
    face = BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(), gp_Dir(0,0,1)), 0,2,0,3).Face()
    move = gp_Trsf()
    move.SetTranslation(gp_Vec(10,20,30))
    shape = face.Moved(TopLoc_Location(move)).Reversed()
    assert BRep_Tool.Triangulation_s(face, TopLoc_Location()) is None
    result = realize(shape)
    assert result.admitted is not None, result.diagnostics
    assert BRep_Tool.Triangulation_s(face, TopLoc_Location()) is None
    mesh = result.admitted.surface
    np.testing.assert_allclose(mesh.vertices.min(axis=0), [10,20,30])
    p = mesh.vertices[mesh.triangles]
    assert np.all(np.cross(p[:,1]-p[:,0], p[:,2]-p[:,0])[:,2] < 0)
    del shape, face, result
    gc.collect()
    assert mesh.assemble().stiffness.shape == (4,4)
    import pytest
    with pytest.raises(ValueError):
        mesh.vertices.setflags(write=True)


def test_resource_limits_and_sampled_deviation_refuse_explicitly():
    import pytest
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder

    from cad_integrity.brep import RealizationLimits, RealizationPolicy
    from cad_integrity.errors import ResourceLimitExceeded
    from cad_integrity.surface import SurfaceLimits
    shape = BRepPrimAPI_MakeBox(2,3,4).Shape()
    for kwargs in ({"max_faces": 0}, {"max_edges": 0}, {"max_native_vertices": 0},
                   {"max_nodes": 0}, {"max_triangles": 0}, {"max_edge_samples": 0},
                   {"numerical": SurfaceLimits(max_input_bytes=0)},
                   {"numerical": SurfaceLimits(max_owned_bytes=0)},
                   {"numerical": SurfaceLimits(max_work_steps=0)},
                   {"numerical": SurfaceLimits(max_output_bytes=0)}):
        with pytest.raises(ResourceLimitExceeded):
            realize(shape, limits=RealizationLimits(**kwargs))
    refused = realize(BRepPrimAPI_MakeCylinder(2,5).Shape(),
                      policy=RealizationPolicy(maximum_sampled_deviation_mm=1e-9))
    assert refused.admitted is None
    assert refused.diagnostics[0].code == "sampled_deviation"


def test_repeated_native_face_occurrence_is_not_silently_deduplicated():
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
    face = BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(), gp_Dir(0,0,1)),0,2,0,3).Face()
    result = realize(compound([face, face.Reversed()]))
    assert result.admitted is None
    assert result.diagnostics


def test_torus_double_periodicity_preserves_genus_and_edge_correspondence():
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus
    result = realize(BRepPrimAPI_MakeTorus(4, 1).Shape())
    assert result.admitted is not None, result.diagnostics
    mesh = result.admitted.surface
    assert len(mesh.boundary_vertices) == 0
    assert len(mesh.vertices)-3*len(mesh.triangles)//2+len(mesh.triangles) == 0
    assert set(mesh.triangle_edges[mesh.triangle_edges >= 0]) == {0, 1}
    p = mesh.vertices[mesh.triangles]
    volume = np.einsum("ij,ij->i", p[:,0], np.cross(p[:,1],p[:,2])).sum()/6
    assert .95*8*np.pi**2 < volume < 8*np.pi**2
