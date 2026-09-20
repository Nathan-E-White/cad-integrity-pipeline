"""Create deterministic synthetic display fixtures. This is NOT a repair algorithm."""
from pathlib import Path
import numpy as np
from cad_mesh_inspector import document, inspect_triangles, Metric, Selection, Trace


def build():
    n, m = 32, 12
    theta = np.arange(n) * 2 * np.pi / n
    phi = np.arange(m) * 2 * np.pi / m
    vertices = np.array([[(3 + np.cos(p)) * np.cos(t), (3 + np.cos(p)) * np.sin(t), np.sin(p)] for t in theta for p in phi])
    faces = []
    for i in range(n):
        for j in range(m):
            a, b, c, d = i*m+j, ((i+1)%n)*m+j, ((i+1)%n)*m+(j+1)%m, i*m+(j+1)%m
            faces.extend([[a,b,c],[a,c,d]])
    faces = np.asarray(faces, dtype=np.int64)
    malformed = vertices.copy()
    malformed[75] = 0.999 * vertices[76] + 0.001 * vertices[75]
    broken_faces = np.delete(faces, np.arange(20, 30), axis=0)
    broken_faces = np.vstack([broken_faces, faces[100], [200, 200, 201]])
    # Intentional visual fixture only. No cross-field or motorcycle computation.
    t = np.linspace(0.2, 4.5, 36)
    p = np.array([[(3.03 + np.cos(.6))*np.cos(a), (3.03 + np.cos(.6))*np.sin(a), np.sin(.6)] for a in t])
    trace = Trace(id="fixture-track", label="Synthetic path fixture", points=p.ravel().tolist(), status="terminated",
                  provenance="synthetic_fixture", termination_reason="Fixture endpoint, not an algorithm collision")
    before = inspect_triangles(malformed, broken_faces, mesh_id="before", revision="fixture-raw-1", frame_id="fixture-world", label="Original · artificial defects", length_unit="mm", require_closed=True, paths=[trace])
    after = inspect_triangles(vertices, faces, mesh_id="after", revision="fixture-reference-1", frame_id="fixture-world", label="Known reference · not a repair result", length_unit="mm", require_closed=True)
    after.selections.append(Selection(id="restored-region", label="Reference triangles omitted in original fixture", face_ids=list(range(20, 30))))
    after.metrics.append(Metric(id="restored-region", label="Reference triangles omitted in original fixture", value=10, status="info", selection_id="restored-region", scope="Fixture construction metadata, not proof that a repair recovered design intent"))
    return document(before, after)


if __name__ == "__main__":
    root = Path(__file__).parent
    data = build()
    (root / "torus-comparison.json").write_text(data.model_dump_json(indent=2), encoding="utf-8")
    print(root / "torus-comparison.json")
