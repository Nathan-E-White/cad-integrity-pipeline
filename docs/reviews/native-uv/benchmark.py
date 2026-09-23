"""Sequential local UV timings; run with the qualified host interpreter."""
from __future__ import annotations

import importlib.util
import json
import platform
import statistics
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from cad_integrity.models import PolyhedralBRep
from cad_integrity.surface import prepare_surface
from cad_integrity.uv import LocationLimits, prepare_locator


def measure(call):
    samples = []
    for _ in range(7):
        start = time.perf_counter()
        call()
        samples.append(1000 * (time.perf_counter() - start))
    return statistics.median(samples)


def reference_modules():
    root = Path(__file__).resolve().parents[3] / 'integration/mesh_healing_extension'
    modules = {}
    for name in ('mesh_healing_engine', 'mesh_export'):
        spec = importlib.util.spec_from_file_location(name, root / f'{name}.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        modules[name] = module
    return modules


def workload(vertices, faces, queries, modules):
    coords = dict(enumerate(vertices[:, :2]))
    surface = prepare_surface(PolyhedralBRep.from_polygons(vertices, faces))
    chart = surface.qualify_chart(coords).admitted
    locator = prepare_locator(chart)
    limits = LocationLimits()._native_limits()
    native = locator._handle.locate(queries, limits)
    exports = native.arrays()
    legacy = modules['mesh_export'].UVSurfaceMap(
        modules['mesh_healing_engine'].MeshHealingEngine(vertices, faces), coords)

    def exhaustive():
        # Same complete candidate payload, with ordered groups. Retain all evidence.
        results = []
        for query in queries:
            b12 = np.einsum('ti,tij->tj', query-legacy.origins, legacy.inverse_edges)
            bc = np.column_stack((1-b12.sum(axis=1), b12))
            ids = np.flatnonzero(np.all(bc >= -1e-9, axis=1) & np.all(bc <= 1+1e-9, axis=1))
            xyz = np.einsum('ti,tij->tj', bc[ids], legacy.xyz[ids])
            discrepancy = 0 if len(xyz) < 2 else np.max(np.linalg.norm(xyz-xyz[0], axis=1))
            results.append((ids, legacy.parent_faces[ids], bc[ids], xyz, discrepancy))
        return results

    result = locator.locate(queries)
    timings = {
        'host_index_create': measure(lambda: prepare_locator(chart)),
        'query_buffer_copy_numpy_proxy': measure(queries.copy),
        'binding_query_including_input_copy': measure(lambda: locator._handle.locate(queries, limits)),
        'native_result_export_copy': measure(native.arrays),
        'immutable_array_projection_copy': measure(lambda: [np.frombuffer(a.tobytes(), dtype=a.dtype).reshape(a.shape)
            for a in exports.values() if isinstance(a, np.ndarray)]),
        'host_locate_including_projection': measure(lambda: locator.locate(queries)),
        'index_plus_host_locate': measure(lambda: prepare_locator(chart).locate(queries)),
        'exhaustive_all_candidate_reference': measure(exhaustive),
    }
    if all(record.resolved is not None for record in result.records):
        timings['host_sample'] = measure(lambda: locator.sample(queries))
        timings['legacy_sample'] = measure(lambda: legacy.sample(queries))
    return {'vertices': len(vertices), 'triangles': len(surface.triangles), 'queries': len(queries),
            'candidates': len(result.triangles), 'index_usage': asdict(locator.usage),
            'query_usage': asdict(result.usage), 'median_ms': timings}


def main():
    modules = reference_modules()
    output = {}
    for side in (10, 25, 50):
        vertices = np.array([[x, y, 0.] for y in range(side) for x in range(side)])
        faces = [[y*side+x, y*side+x+1, (y+1)*side+x+1, (y+1)*side+x]
                 for y in range(side-1) for x in range(side-1)]
        queries = np.random.default_rng(7).uniform(0, side-1, (400, 2))
        output[f'grid_{side}'] = workload(vertices, faces, queries, modules)
        if side == 25:
            output['grid_25_one_query'] = workload(vertices, faces, queries[:1], modules)
            edge = np.array([[float(x), y+.5e-9] for y in range(20) for x in range(20)])
            output['grid_25_near_edges'] = workload(vertices, faces, edge, modules)
    for conflict in (False, True):
        vertices = np.array([[x, y, float(i) if conflict else 0.] for i in range(32)
                             for x, y in ((0, 0), (1, 0), (0, 1))])
        faces = [[3*i, 3*i+1, 3*i+2] for i in range(32)]
        queries = np.tile([[.2, .3]], (100, 1))
        output['overlap_conflicting' if conflict else 'overlap_agreeing'] = workload(vertices, faces, queries, modules)
    print(json.dumps({'platform': platform.platform(), 'repetitions': 7, 'workloads': output,
                      'limits': 'Sequential local measurements. Overlapping timing labels are not additive. NumPy copy is a proxy, not the binding memcpy cost. No RSS or universal speed claim.'}, indent=2))


if __name__ == '__main__':
    main()
