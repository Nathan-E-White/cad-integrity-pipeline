"""Local timings; run with the qualified host Python from the repository root."""
from __future__ import annotations

import cProfile
import pstats
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import time

import numpy as np

from cad_integrity import _native
from cad_integrity.models import PolyhedralBRep
from cad_integrity.surface import SurfaceLimits, prepare_surface


def measure(call, repeats=7):
    values = []
    for _ in range(repeats):
        start = time.perf_counter()
        call()
        values.append(1000 * (time.perf_counter() - start))
    return statistics.median(values)


def main():
    n = 25
    vertices = np.array([[x,y,0.] for y in range(n) for x in range(n)])
    faces = [[y*n+x,y*n+x+1,(y+1)*n+x+1,(y+1)*n+x]
             for y in range(n-1) for x in range(n-1)]
    raw = PolyhedralBRep.from_polygons(vertices, faces)
    surface = prepare_surface(raw)
    limits = SurfaceLimits()._native_limits()
    ids = np.arange(len(faces),dtype=np.int64)
    native = lambda: _native.prepare_surface(raw.vertices,raw.edges,raw.face_offsets,
                                             raw.face_coedges,"mm",ids,1e-12,limits)
    handle = native()
    exported = handle.arrays()
    boundary = {y*n+x:vertices[y*n+x,:2] for y in range(n) for x in range(n)
                if x in (0,n-1) or y in (0,n-1)}
    inside = sorted(set(range(n*n))-set(boundary))
    system = surface.prepare_harmonic_system(inside,list(boundary))
    uv = system.solve(boundary)
    reference_path = Path(__file__).resolve().parents[3] / "integration/mesh_healing_extension/mesh_healing_engine.py"
    spec = importlib.util.spec_from_file_location("surface_benchmark_reference",reference_path)
    reference = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = reference
    spec.loader.exec_module(reference)
    engine = reference.MeshHealingEngine(vertices,faces)
    refsys = engine.prepare_harmonic_system(inside,list(boundary))
    # Profile public solve and qualification to separate solve-exclusive cost without
    # replacing numerical work. Profiler overhead is included and reported separately.
    first, repeated, first_total = [], [], []
    for _ in range(7):
        fresh = surface.prepare_harmonic_system(inside,list(boundary))
        for run, samples in ((0,first),(1,repeated)):
            profiler = cProfile.Profile()
            profiler.runcall(fresh.solve,boundary)
            stats = pstats.Stats(profiler).stats
            solve_time = next(v[3] for key,v in stats.items() if key[2] == "solve" and key[0].endswith("surface.py"))
            chart_time = next(v[3] for key,v in stats.items() if key[2] == "qualify_chart" and key[0].endswith("surface.py"))
            samples.append(1000*(solve_time-chart_time))
            if run == 0:
                first_total.append(1000*solve_time)
    op = _native.assemble_surface(handle,np.empty(0,dtype=np.int64),np.empty(0,dtype=float),limits)
    timing = {
        "profiled_initial_solve_excluding_chart": statistics.median(first),
        "profiled_repeated_solve_excluding_chart": statistics.median(repeated),
        "profiled_initial_solve_including_chart": statistics.median(first_total),
        "operator_array_export_copy": measure(op.arrays),
        "binding_prepare_including_input_copy": measure(native),
        "export_native_arrays_copy": measure(handle.arrays),
        "immutable_python_projection_copy": measure(lambda: [np.frombuffer(a.tobytes(),dtype=a.dtype).reshape(a.shape)
                                                      for a in exported.values() if isinstance(a,np.ndarray)]),
        "host_prepare_including_projection": measure(lambda: prepare_surface(raw)),
        "assembly_binding_including_csr_export": measure(lambda: surface.assemble().stiffness),
        "prepare_solver_including_assembly_factorization": measure(lambda: surface.prepare_harmonic_system(inside,list(boundary))),
        "reused_solve_including_chart_qualification": measure(lambda: system.solve(boundary)),
        "chart_qualification_host": measure(lambda: surface.qualify_chart(uv)),
        "end_to_end": measure(lambda: prepare_surface(raw).prepare_harmonic_system(inside,list(boundary)).solve(boundary)),
        "reference_assembly": measure(engine.compute_cotangent_laplacian),
        "reference_reused_solve": measure(lambda: refsys.solve(boundary)),
        "reference_end_to_end": measure(lambda: reference.MeshHealingEngine(vertices,faces).compute_harmonic_map(inside,boundary)),
    }
    print(json.dumps({"grid_side":n,"vertices":len(vertices),"faces":len(faces),
                      "triangles":len(surface.triangles),"repetitions":7,"median_ms":timing,
                      "native_preparation_usage":exported["usage"],
                      "limits":"Local sequential microbenchmark, no process RSS cap or general speed guarantee."},indent=2))


if __name__ == "__main__":
    main()
