"""Generate a pathological synthetic inspection fixture, not an alleged repair."""
from pathlib import Path
import json
import numpy as np
from mesh_diagnostics import TriangleMesh, audit_mesh, payload_from_audit


def synthetic_fixture():
    v = np.array([
        [-1,-1,-1], [1,-1,-1], [1,1,-1], [-1,1,-1],
        [-1,-1,1], [1,-1,1], [1,1,1], [-1,1,1],
        [0,-.7,.2], [1.6,-.8,0], [2.8,-.8,0], [2.2,-.799,0], [0,0,1.6],
    ], dtype=float)
    f = np.array([
        [0,2,1], [0,3,2], # bottom
        [0,1,5], [0,5,4], # front
        [1,2,6], [1,6,5], # right
        [2,3,7], [2,7,6], # back
        [3,4,0], [3,7,4], # left; one deliberately reversed face
        [0,1,8],          # third incident face on edge (0,1)
        [9,10,11],        # sliver
        [12,12,12],       # collapsed/repeated-index face
    ], dtype=np.int64)
    return payload_from_audit(audit_mesh(TriangleMesh(v, f, mesh_id="Synthetic inspection fixture",
                                                     stage="synthetic-original", units="arbitrary")))


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    payload = synthetic_fixture().model_dump()
    for relative in ("examples/fixture.json", "frontend/demo/fixture.json"):
        (root / relative).write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    from mesh_diagnostics import MeshPayload
    (root / "docs/mesh-diagnostics.schema.json").write_text(json.dumps(MeshPayload.model_json_schema(), indent=2) + "\n")
