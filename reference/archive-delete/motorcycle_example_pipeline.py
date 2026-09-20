"""Runnable extension of the supplied nine-vertex example.

    python example_pipeline.py --output generated
    python example_pipeline.py --output generated --step

The default path needs only NumPy/SciPy. --step adds CadQuery/OpenCascade.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
import json
import numpy as np

from mesh_healing_engine import (
    MeshHealingEngine, SoftConstraint, MotorcycleGraphTracer, CrossFieldOptimizer,
    solve_igm_quantization, prune_motorcycle_graph, parameterize_macro_patch,
)
from mesh_export import export_step, export_frontend_json, UVSurfaceMap


def original_example():
    vertices = np.array([
        [0., 0., .01], [1., 0., -.01], [2., 0., 0.],
        [0., 1., 0.], [1., 1., .02], [2., 1., 0.],
        [0., 2., -.02], [1., 2., 0.], [2., 2., .01],
    ])
    faces = [[0, 1, 4, 3], [1, 2, 5, 4], [3, 4, 7, 6], [4, 5, 8, 7]]
    boundaries = {0: (0., 0.), 1: (1., 0.), 2: (2., 0.), 5: (2., 1.),
                  8: (2., 2.), 7: (1., 2.), 6: (0., 2.), 3: (0., 1.)}
    return vertices, faces, boundaries


def seam_example():
    eps = 2e-7
    v = np.array([[0., 0., 0.], [1., 0., 0.], [1., 1., 0.], [0., 1., 0.],
                  [1.+eps, 0., 0.], [2., 0., 0.], [2., 1., 0.], [1.+eps, 1., 0.]])
    return MeshHealingEngine(v, [[0, 1, 2, 3], [4, 5, 6, 7]])


def run(output: Path, write_step: bool = False) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    vertices, faces, old_boundary = original_example()
    # Raw geometry is retained independently before any repair.
    np.savez(output / 'raw_mesh.npz', vertices=vertices, quads=np.asarray(faces))
    engine = MeshHealingEngine(vertices, faces)

    # Mesh preprocessing is now actually part of the graph-pruner path.
    # With no pre-existing tracks, there are no stale half-edge IDs to remap.
    pruning = prune_motorcycle_graph({}, 0., {}, mesh_engine=engine, return_report=True)
    report = pruning.preprocessing
    boundary = report.remap_constraints(old_boundary)
    internal = sorted(set(range(engine.num_vertices)) - set(boundary))
    system = engine.prepare_harmonic_system(internal, list(boundary))
    uv = system.solve(boundary)
    print('Center UV:', uv[internal[0]])

    # Affine boundary update: same A, same sparse factorization, two new RHSs.
    transform = np.array([[1.1, .08], [0., .9]])
    offset = np.array([.2, -.1])
    shifted_boundary = {v: tuple(transform @ value + offset) for v, value in boundary.items()}
    affine_uv = system.solve(shifted_boundary)
    expected = {v: transform @ value + offset for v, value in uv.items()}
    affine_error = max(float(np.linalg.norm(np.asarray(affine_uv[v]) - expected[v])) for v in uv)

    # Low-confidence observation: a weak soft anchor, never a forced boundary.
    soft_uv = system.solve(boundary, soft_constraints={internal[0]: SoftConstraint((1.12, .94), .1)})
    soft_method = system.last_update_method
    # Drop the contaminated observation entirely: no lingering constraint state.
    recovered = system.solve(boundary, soft_constraints={})
    assert np.allclose(recovered[internal[0]], uv[internal[0]])

    # Explicit local contamination repair freezes all trusted coordinates.
    contaminated = dict(uv)
    contaminated[internal[0]] = (9., -8.)
    repaired = engine.repair_contaminated_coordinates(contaminated, internal)

    # Face confidence changes the stiffness, so explicitly get a new system.
    weighted_system = system.with_face_confidence({0: .25})
    weighted_uv = weighted_system.solve(boundary)

    # Retain the legacy helper name; the geometry path now uses cotangents.
    helper_uv = parameterize_macro_patch(internal, boundary, engine.adjacency, mesh_engine=engine)
    assert np.allclose(helper_uv[internal[0]], uv[internal[0]])

    # Preserved integer quantization example.
    lengths = [3.2, 4.9, 7.8, 5.1, 5.3]
    patches = [{'horizontal_top': [0, 1], 'horizontal_bottom': [2],
                'vertical_left': [3], 'vertical_right': [4]}]
    integers = solve_igm_quantization(lengths, patches)
    print('Integer segment lengths:', integers.tolist())

    # Explicit seam repair fixture with IDs already used by a tracer.
    seam = seam_example()
    tracer = MotorcycleGraphTracer.from_mesh(seam)
    edge_map = tracer.edge_vertex_map()
    tracks = {
        0: tracer.trace_single_motorcycle(tracer.faces[0].half_edges[3]),
        1: tracer.trace_single_motorcycle(tracer.faces[1].half_edges[3]),
    }
    seam_prune = prune_motorcycle_graph(tracks, 0., {}, mesh_engine=seam,
                                        edge_vertices=edge_map, return_report=True)
    print('Boundary seam vertices stitched:', seam_prune.preprocessing.stitched_vertices)
    assert seam.num_vertices == 6
    # Old tracer is stale now; rebuild instead of using its old connectivity.
    tracer = MotorcycleGraphTracer.from_mesh(seam)

    # Complete the original cross-field solve, including the missing return.
    centroids = np.array([engine.v3d[f].mean(axis=0) for f in engine.faces])
    normals = np.array([np.cross(engine.v3d[f[1]] - engine.v3d[f[0]],
                                engine.v3d[f[2]] - engine.v3d[f[0]]) for f in engine.faces])
    face_adj = {i: set() for i in range(len(faces))}
    for incident in engine.edge_faces.values():
        if len(incident) == 2:
            i, j = incident[0][0], incident[1][0]
            face_adj[i].add(j)
            face_adj[j].add(i)
    field_values = CrossFieldOptimizer(centroids, normals, face_adj).optimize_field()

    # Keep parameter coordinates and 3D surface positions together for the UI.
    export_frontend_json(engine, output / 'patch.mesh.json', uv, units='mm')
    evaluator = UVSurfaceMap(engine, uv)
    queries = np.array([[.25, .25], [.75, 1.25], [1.75, 1.75]])
    sampled = evaluator.sample(queries)
    summary = {
        'center_uv': uv[internal[0]],
        'base_factorization_count': system.base_factorization_count,
        'total_factorization_count': system.factorization_count,
        'soft_update_method': soft_method,
        'soft_center_uv': soft_uv[internal[0]],
        'repaired_center_uv': repaired[internal[0]],
        'weighted_center_uv': weighted_uv[internal[0]],
        'affine_equivariance_error': affine_error,
        'relative_residual': system.last_relative_residual,
        'uv_quality': asdict(system.last_quality),
        'integer_lengths': integers.tolist(),
        'stitched_vertices': seam_prune.preprocessing.stitched_vertices,
        'sample_uv': queries.tolist(), 'sample_xyz': sampled.tolist(),
        'cross_field': [[float(z.real), float(z.imag)] for z in field_values],
        'step_exports': [],
    }
    if write_step:
        for space in ('uv', 'xyz'):
            result = export_step(engine, output / f'patch_{space}.step', coords_2d=uv,
                                 space=space, units='mm', uv_scale=1.0)
            record = asdict(result)
            record['path'] = result.path.name
            summary['step_exports'].append(record)
            print(f'STEP round-trip verified: {result.path.name} ({result.imported_faces} faces)')
    (output / 'run_summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('generated'))
    parser.add_argument('--step', action='store_true', help='Export and reimport real UV and XYZ STEP files')
    args = parser.parse_args()
    run(args.output, write_step=args.step)


if __name__ == '__main__':
    main()
