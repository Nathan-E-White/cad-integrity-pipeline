"""Bounded projection capacity experiment, separate from numerical qualification."""

from __future__ import annotations

import json
import resource
import time
from pathlib import Path

import numpy as np

from cad_integrity.inspection import encode_inspection, project_polygonal_inspection
from cad_integrity.models import PolyhedralBRep
from cad_integrity.pipeline import RepairReport, RepairResult
from cad_integrity.topology import TopologyReport


def main() -> None:
    n = 500
    u, v = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    a, b = 2 * np.pi * u / n, 2 * np.pi * v / n
    points = np.stack(
        ((3 + np.cos(b)) * np.cos(a), (3 + np.cos(b)) * np.sin(a), np.sin(b)), axis=-1
    ).reshape(-1, 3)
    i = (u * n + v).ravel()
    j = (((u + 1) % n) * n + v).ravel()
    k = (((u + 1) % n) * n + (v + 1) % n).ravel()
    next_v = (u * n + (v + 1) % n).ravel()
    faces = np.stack(
        (np.stack((i, j, k), axis=-1), np.stack((i, k, next_v), axis=-1)), axis=1
    ).reshape(-1, 3)
    source = Path("/private/tmp/polygonal-inspection-capacity.npz")
    np.savez(source, vertices=points, triangles=faces, length_unit=np.array("mm"))
    brep = PolyhedralBRep.from_polygons(points, faces)
    # Literal report memberships exercise display only, not a fabricated audit.
    report = TopologyReport(
        len(points),
        len(brep.edges),
        len(faces),
        (),
        (),
        (),
        (),
        (),
        (),
        (),
        (),
        (),
        None,
        "Synthetic display capacity fixture",
    )
    repair = RepairReport("1.0", "synthetic", report, report, "needs_review", (), 0.0, "mm", ())
    result = RepairResult(brep, brep, repair)
    started = time.perf_counter()
    try:
        snapshot = project_polygonal_inspection(result)
        encoded = json.dumps(encode_inspection(snapshot), separators=(",", ":"))
        elapsed = time.perf_counter() - started
        evidence = {
            "status": "passed" if elapsed <= 30 and len(encoded) <= 512_000_000 else "failed",
            "vertices": len(points),
            "triangles": len(faces),
            "projection_encoding_seconds": elapsed,
            "json_bytes": len(encoded),
            "backend_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "source": str(source),
            "scope": "synthetic projection; not parent/browser qualification",
        }
        Path("/private/tmp/polygonal-inspection-capacity.json").write_text(encoded)
    except Exception as exc:
        evidence = {
            "status": "failed",
            "error": str(exc),
            "vertices": len(points),
            "triangles": len(faces),
            "source": str(source),
        }
    print(json.dumps(evidence, indent=2), flush=True)
    Path("docs/evidence/polygonal-inspection/projection-capacity.json").write_text(
        json.dumps(evidence, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
