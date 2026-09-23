"""Measure owned quad admission, tracing and export separately; no speedup claim."""
from __future__ import annotations

import json
import platform
import statistics
import time
from pathlib import Path

import numpy as np

from cad_integrity import _native
from cad_integrity.models import PolyhedralBRep
from cad_integrity.quad import prepare_quad_patch


def l_patch(n: int) -> PolyhedralBRep:
    polygons = [(v, v+1, v+n+1, v+n)
                for y in range(n-1) for x in range(n-1)
                if x < n//2 or y < n//2 for v in [y*n+x]]
    used = sorted(set(v for polygon in polygons for v in polygon))
    ids = {v: i for i, v in enumerate(used)}
    return PolyhedralBRep.from_polygons(
        [(v % n, v // n, 0) for v in used],
        [[ids[v] for v in polygon] for polygon in polygons],
    )


def measure(n: int) -> dict[str, object]:
    mesh = l_patch(n)
    samples: dict[str, list[float]] = {k: [] for k in (
        "admission_and_projection_ms", "binding_trace_ms", "native_export_ms", "host_trace_ms",
    )}
    limits = _native.QuadLimits(512_000_000, 50_000_000, 256_000_000, 1_000_000, 1_000_000)
    for iteration in range(8):
        start = time.perf_counter()
        patch = prepare_quad_patch(mesh)
        prepared = time.perf_counter()
        seeds = np.asarray([(s.id, s.vertex, s.edge) for s in patch.canonical_seeds], dtype=np.int64)
        before_trace = time.perf_counter()
        handle = patch._handle.trace(seeds, limits)
        traced = time.perf_counter()
        handle.arrays()
        exported = time.perf_counter()
        result = patch.trace()
        projected = time.perf_counter()
        assert result.complete and result.canonical
        if iteration:
            samples["admission_and_projection_ms"].append((prepared-start)*1000)
            samples["binding_trace_ms"].append((traced-before_trace)*1000)
            samples["native_export_ms"].append((exported-traced)*1000)
            samples["host_trace_ms"].append((projected-exported)*1000)
    return {"vertices": len(mesh.vertices), "faces": mesh.face_count,
            "seeds": len(result.seeds), "segments": len(result.segments),
            "median_ms": {k: statistics.median(v) for k, v in samples.items()},
            "trace_usage": {"owned_bytes": result.usage.owned_bytes,
                            "work_steps": result.usage.work_steps,
                            "output_bytes": result.usage.output_bytes}}


if __name__ == "__main__":
    data = {"platform": platform.platform(), "python": platform.python_version(),
            "repeats": 7, "warmups": 1, "cases": [measure(n) for n in (5, 33, 129)],
            "limits": "Logical accounting, not measured RSS. No reference speedup or independent platform qualification."}
    Path(__file__).with_name("benchmark.json").write_text(json.dumps(data, indent=2) + "\n")
