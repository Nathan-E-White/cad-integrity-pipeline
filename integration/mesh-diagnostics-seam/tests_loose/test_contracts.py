import json
from pathlib import Path
import numpy as np
import pytest
from pydantic import ValidationError
from cad_mesh_inspector import document, inspect_triangles, InspectorDocument
from cad_mesh_inspector.legacy import upgrade_legacy_payload


def payload():
    return document(inspect_triangles([[0,0,0],[1,0,0],[0,1,0]],[[0,1,2]],mesh_id="m",revision="r1",frame_id="world")).model_dump(mode="json")


def test_json_roundtrip():
    raw=payload()
    assert InspectorDocument.model_validate(json.loads(json.dumps(raw,allow_nan=False))).meshes[0].revision=="r1"

@pytest.mark.parametrize("change", [
    lambda m: m["triangles"].__setitem__(0,-1),
    lambda m: m["triangles"].__setitem__(0,1.2),
    lambda m: m["triangles"].__setitem__(0,True),
    lambda m: m["positions"].__setitem__(0,float("nan")),
    lambda m: m["fields"][0].__setitem__("values",[]),
    lambda m: m["fields"][0].__setitem__("domain",[1.,0.]),
    lambda m: m["selections"][0].__setitem__("face_ids",[10]),
    lambda m: m["selections"][0].__setitem__("edge_pairs",[0]),
    lambda m: m["metrics"][0].__setitem__("selection_id","absent"),
    lambda m: m["selections"].append(m["selections"][0]),
])
def test_bad_contract_references(change):
    raw=payload(); change(raw["meshes"][0])
    with pytest.raises(ValidationError): InspectorDocument.model_validate(raw)


def test_unknown_scalar_is_null_not_perfect_quality():
    raw=payload();raw["meshes"][0]["fields"][0]["values"]=[None]
    assert InspectorDocument.model_validate(raw).meshes[0].fields[0].values==[None]

@pytest.mark.parametrize("key,value",[("frame_id","another-frame"),("length_unit","m")])
def test_comparison_requires_matching_frame_and_units(key,value):
    raw=payload(); other=json.loads(json.dumps(raw["meshes"][0]));other["id"]="other";other[key]=value;raw["meshes"].append(other)
    with pytest.raises(ValidationError): InspectorDocument.model_validate(raw)
    raw["linked_views"]=False
    assert len(InspectorDocument.model_validate(raw).meshes)==2


def test_paired_scalar_domains_must_match():
    raw=payload(); other=json.loads(json.dumps(raw["meshes"][0]));other["id"]="other";other["fields"][0]["domain"]=[0.,2.];raw["meshes"].append(other)
    with pytest.raises(ValidationError): InspectorDocument.model_validate(raw)


def test_legacy_does_not_endorse_jacobian_or_manifold_claims():
    p=upgrade_legacy_payload({"vertices":[0,0,0,1,0,0,0,1,0],"faces":[0,1,2],"error_edges":[[0,0,0,1,0,0]],"failed_face_ids":[0],"face_qualities":[.2],
        "metrics":[{"id":"jacobian_failures","label":"Jacobian failures","value":1,"status":"pass"}]},mesh_id="m",revision="1",frame_id="world")
    assert p.fields[0].better=="neither"
    assert all(metric.status=="unknown" for metric in p.metrics)
    assert p.metrics[-1].selection_id=="legacy-faces"


def test_legacy_crashed_path_not_cycle_or_collision_proof():
    p=upgrade_legacy_payload({"vertices":[],"faces":[],"motorcycles":[{"id":1,"segments":[0,0,0,1,0,0,1,0,0,2,0,0],"status":"crashed"}]},mesh_id="m",revision="1",frame_id="world")
    assert p.paths[0].status=="terminated" and p.paths[0].provenance=="imported"


def test_no_synthetic_paths_on_missing_input():
    p=upgrade_legacy_payload({"vertices":[],"faces":[]},mesh_id="m",revision="1",frame_id="world")
    assert p.paths==[] and p.metrics==[]


@pytest.mark.parametrize("case", json.loads(
    (Path(__file__).parent / "source-face-id-cases.json").read_text()
)["cases"], ids=lambda case: case["name"])
def test_source_face_id_wire_limits(case):
    raw = json.loads((Path(__file__).parent / "source-face-id-cases.json").read_text())["document"]
    raw["meshes"][0]["triangle_source_faces"] = case["mapping"]
    if case["valid"]:
        parsed = InspectorDocument.model_validate(raw)
        assert parsed.meshes[0].triangle_source_faces == case["mapping"]
    else:
        with pytest.raises(ValidationError):
            InspectorDocument.model_validate(raw)
