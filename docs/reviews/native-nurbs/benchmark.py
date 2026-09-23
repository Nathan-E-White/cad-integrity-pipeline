"""Run with the installed parent package; retain Python reference phase separately."""
import importlib.util
import json
import platform
import statistics
import sys
import time
from pathlib import Path

import numpy as np

from cad_integrity import _native
from cad_integrity.nurbs import evaluate_surface

root = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "nurbs_benchmark_reference", root / "integration/nurbs_core_professionalized/NURBSCoreEngine.py",
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
knots = np.array([0, 0, 0, 1, 1, 1], dtype=float)
cp = np.array([[[i / 2, j / 2, .1 * i * j, 1] for j in range(3)] for i in range(3)])


def median_ms(call):
    call()
    measurements = []
    for _ in range(7):
        start = time.perf_counter()
        call()
        measurements.append((time.perf_counter() - start) * 1000)
    return statistics.median(measurements)


rows = []
for n in [16, 128, 256]:
    u = np.linspace(0, 1, n)
    args = (2, 2, knots, knots, cp, u, u)
    rows.append({
        "grid_side": n,
        "logical_output_bytes": 81 * n * n,
        "native_host_ms": median_ms(lambda args=args: evaluate_surface(*args)),
        "binding_including_snapshot_kernel_export_ms": median_ms(
            lambda args=args: _native.evaluate_nurbs(*args, 1e-10, False,
                                          256_000_000, 512_000_000, 256_000_000, 100_000_000)),
        "python_reference_ms": median_ms(lambda args=args: module.NURBSCoreEngine.evaluate_surface(*args)),
    })
print(json.dumps({"platform": platform.platform(), "python": platform.python_version(),
                  "repeats": 7, "warmups": 1, "measurements": rows}, indent=2))
