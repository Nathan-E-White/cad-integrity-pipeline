from gradio_topologicaldeltaaudit import DeltaAuditRow, TopologicalDeltaAudit, TopologicalDeltaAuditData
from gradio_verificationgrid import (
    VerificationCheck,
    VerificationGrid,
    VerificationGridData,
    VerificationGroup,
)


def test_delta_audit_component_serializes_typed_rows() -> None:
    component = TopologicalDeltaAudit()
    payload = component.postprocess(TopologicalDeltaAuditData(
        "Topological & Geometric Delta Audit",
        (DeltaAuditRow("topology", "Betti tuple", "(2, 0, 0)", "(1, 0, 1)", "verified"),),
    ))

    assert payload == {
        "title": "Topological & Geometric Delta Audit",
        "rows": [{"category": "topology", "entity": "Betti tuple", "before": "(2, 0, 0)",
                  "after": "(1, 0, 1)", "delta": "verified"}],
    }
    assert component.preprocess(payload) == payload


def test_verification_grid_component_serializes_grouped_states() -> None:
    component = VerificationGrid()
    payload = component.postprocess(VerificationGridData(
        "Verification", "1 / 2 pass", (
            VerificationGroup("Topology", (VerificationCheck("homology_f2", "budget exceeded", "inconclusive"),)),
        ),
    ))

    assert payload["summary"] == "1 / 2 pass"
    assert payload["groups"][0]["checks"][0] == {
        "name": "homology_f2", "detail": "budget exceeded", "state": "inconclusive"
    }
    assert component.preprocess(payload) == payload
