"""Local phase measurements; no speedup or peak-memory claim."""
import json
from dataclasses import asdict
from statistics import median
from time import perf_counter

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere

from cad_integrity.brep import realize

results = {}
for name, maker in (("box", BRepPrimAPI_MakeBox(2, 3, 4)),
                    ("cylinder", BRepPrimAPI_MakeCylinder(2, 5)),
                    ("sphere", BRepPrimAPI_MakeSphere(2))):
    shape = maker.Shape()
    rows = []
    for _ in range(7):
        start = perf_counter()
        result = realize(shape)
        total = perf_counter() - start
        assert result.admitted is not None, result.diagnostics
        rows.append({**asdict(result.evidence), "total_seconds": total})
    mesh = result.admitted.surface
    results[name] = {"nodes": len(mesh.vertices), "triangles": len(mesh.triangles),
                     "seven_run_medians": {key: median(row[key] for row in rows) for key in rows[0]}}
print(json.dumps({"scope": "Local OCP copy/mesh/extraction and binding qualification; total also includes numeric conversion and immutable host projection. No native-only timing or peak RSS measurement.",
                  "cases": results}, indent=2))
