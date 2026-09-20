import pytest
pytest.importorskip("gradio")
from cad_mesh_inspector.gradio_component import MeshDiagnostics
from cad_mesh_inspector import document, inspect_triangles


def test_gradio_output_validation_and_no_browser_geometry_input():
    component=MeshDiagnostics(render=False)
    value=document(inspect_triangles([[0,0,0],[1,0,0],[0,1,0]],[[0,1,2]],mesh_id="m",revision="1",frame_id="world"))
    result=component.postprocess(value.model_dump(mode="json"))
    assert result.meshes[0].triangles==[0,1,2]
    assert component.preprocess(result) is None
    assert component.postprocess(None) is None


def test_gradio_rejects_error_instead_of_blank_fallback():
    component=MeshDiagnostics(render=False)
    with pytest.raises(ValueError): component.postprocess({"schema_version":1,"meshes":[{}]})
