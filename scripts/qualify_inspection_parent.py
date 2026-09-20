"""Measure a real admitted maximum-size upload independently of synthetic reports."""

from __future__ import annotations

import json
import resource
import time
from pathlib import Path

from cad_integrity.gradio_app import run_polygonal_upload
from cad_integrity.inspection import encode_inspection
from cad_integrity.pipeline import RepairPolicy

if __name__ == "__main__":
    started = time.perf_counter()
    outcome = run_polygonal_upload(
        "/private/tmp/polygonal-inspection-capacity.npz",
        RepairPolicy(synchronize_orientation=False),
        include_legacy_figures=False,
    )
    elapsed = time.perf_counter() - started
    payload = encode_inspection(outcome.inspection)
    evidence = {
        "controller_seconds": elapsed,
        "completion": outcome.completion.value,
        "checks": [{"name": c.name, "status": c.status.value} for c in outcome.checks],
        "inspection_meshes": len(payload["meshes"]),
        "backend_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "candidate_retained": outcome.release is not None and outcome.release.candidate is not None,
        "diagnostics": [d.message for d in outcome.diagnostics],
    }
    Path("/private/tmp/polygonal-inspection-parent.json").write_text(
        json.dumps(payload, separators=(",", ":"))
    )
    Path("docs/evidence/polygonal-inspection/parent-capacity.json").write_text(
        json.dumps(evidence, indent=2) + "\n"
    )
    print(json.dumps(evidence, indent=2), flush=True)
