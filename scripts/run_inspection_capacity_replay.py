"""Installed parent display stress replay; synthetic memberships, no numerical claim.

First generate the captured admitted result with qualify_inspection_parent.py.
This harness replaces only the delivery adapter; the regular example still owns
admission, clearing, reporting and release. The browser receives every captured
entity with deliberately dense diagnostic memberships in both panes.
"""

import json
from pathlib import Path

import cad_integrity.gradio_app as parent

payload = json.loads(Path("/private/tmp/polygonal-inspection-parent.json").read_text())
for mesh in payload["meshes"]:
    counts = {
        "vertex": len(mesh["positions"]) // 3,
        "edge": len(mesh["edges"]) // 2,
        "polygonal_face": mesh["face_count"],
    }
    for category in mesh["categories"]:
        category["entity_ids"] = list(range(counts[category["kind"]]))
encode = parent.encode_inspection
parent.encode_inspection = lambda snapshot: payload if snapshot is not None else encode(None)
parent.build_app(inspection_enabled=True).launch(
    server_name="127.0.0.1", server_port=7863, share=False
)
