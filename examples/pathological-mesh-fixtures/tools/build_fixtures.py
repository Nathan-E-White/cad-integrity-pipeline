"""Regenerate the synthetic meshes. Not needed to open the already built files.

Requires NumPy and the cad_integrity package from CAD Integrity Lab 0.1.0.
Run with an explicit *new* --out directory; existing destinations are refused.
All canonical array coordinates are millimetres. GLB positions are metres.
"""
from __future__ import annotations

import argparse
import json
import struct
from dataclasses import asdict
from pathlib import Path

import numpy as np
from cad_integrity import (PolyhedralBRep, TriangleMesh, RepairPipeline,
                           RepairPolicy, WeldPolicy, analyze_mesh)
from cad_integrity.repair import weld_vertices


def json_write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def round_boss(n: int = 64) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Boundary of a 40 mm diameter, 5 mm thick base with an 18x12 mm boss.

    Four indexed rings. The top is a fan using only boundary vertices so
    welding restores the entire displaced cap, not just its boundary.
    """
    if n < 8:
        raise ValueError('At least 8 azimuthal samples are required')
    theta = 2 * np.pi * np.arange(n) / n
    points = np.vstack([
        np.column_stack((radius * np.cos(theta), radius * np.sin(theta),
                         np.full(n, z)))
        for radius, z in ((20, 0), (20, 5), (9, 5), (9, 17))
    ])
    faces: list[tuple[int, int, int]] = []
    # Outer base and boss walls, outward orientation.
    for lower, upper in ((0, n), (2*n, 3*n)):
        for i in range(n):
            j = (i + 1) % n
            faces.extend(((lower+i, lower+j, upper+j), (lower+i, upper+j, upper+i)))
    # Upward-facing annular shoulder.
    for i in range(n):
        j = (i + 1) % n
        faces.extend(((n+i, n+j, 2*n+j), (n+i, 2*n+j, 2*n+i)))
    # Downward base disk.
    faces.extend((0, j+1, j) for j in range(1, n-1))
    cap_start = len(faces)
    faces.extend((3*n, 3*n+j, 3*n+j+1) for j in range(1, n-1))
    return points, np.asarray(faces, dtype=np.int64), np.arange(cap_start, len(faces))


def glb_bytes(vertices_mm: np.ndarray, faces: np.ndarray, name: str) -> bytes:
    """One indexed triangle primitive, without splitting vertices for shading."""
    positions = np.asarray(vertices_mm / 1000.0, dtype='<f4')
    indices = np.asarray(faces, dtype='<u4')
    p_bytes, i_bytes = positions.tobytes(), indices.tobytes()
    payload = p_bytes + i_bytes
    doc = {
        'asset': {'version': '2.0', 'generator': 'Synthetic CAD Integrity Lab fixtures'},
        'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0, 'name': name}],
        'meshes': [{'name': name, 'primitives': [{'attributes': {'POSITION': 0},
                    'indices': 1, 'mode': 4, 'material': 0}]}],
        'materials': [{'name': 'neutral_double_sided', 'doubleSided': True,
                       'pbrMetallicRoughness': {'baseColorFactor': [0.65, 0.69, 0.73, 1],
                                              'metallicFactor': 0, 'roughnessFactor': 0.7}}],
        'buffers': [{'byteLength': len(payload)}],
        'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': len(p_bytes), 'target': 34962},
                        {'buffer': 0, 'byteOffset': len(p_bytes), 'byteLength': len(i_bytes), 'target': 34963}],
        'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': len(positions),
                       'type': 'VEC3', 'min': positions.min(axis=0).astype(float).tolist(),
                       'max': positions.max(axis=0).astype(float).tolist()},
                      {'bufferView': 1, 'componentType': 5125, 'count': indices.size, 'type': 'SCALAR'}],
        'extras': {'origin': 'synthetic_not_model_output', 'positions_unit': 'm',
                   'canonical_npz_unit': 'mm',
                   'warning': 'Preserve triangle indices; do not auto-weld or repair at import.'},
    }
    j = json.dumps(doc, separators=(',', ':'), allow_nan=False).encode()
    j += b' ' * (-len(j) % 4)
    payload += b'\x00' * (-len(payload) % 4)
    return (struct.pack('<4sII', b'glTF', 2, 12 + 8 + len(j) + 8 + len(payload))
            + struct.pack('<I4s', len(j), b'JSON') + j
            + struct.pack('<I4s', len(payload), b'BIN\x00') + payload)


def export_mesh(out: Path, name: str, vertices: np.ndarray, faces: np.ndarray) -> None:
    stem = out / 'meshes' / name
    np.savez_compressed(stem.with_suffix('.npz'), vertices=np.asarray(vertices, dtype=np.float64),
                        triangles=np.asarray(faces, dtype=np.int64), length_unit=np.array('mm'))
    lines = [f'# {name}; synthetic fixture; coordinates in millimetres',
             '# Preserve vertex IDs and triangle winding. Do not auto-process.']
    lines += ['v ' + ' '.join(format(float(x), '.17g') for x in v) for v in vertices]
    lines += ['f ' + ' '.join(str(int(i)+1) for i in f) for f in faces]
    stem.with_suffix('.obj').write_text('\n'.join(lines) + '\n', encoding='ascii')
    stem.with_suffix('.glb').write_bytes(glb_bytes(vertices, faces, name))


def mesh_from_brep(brep: PolyhedralBRep) -> tuple[np.ndarray, np.ndarray]:
    return brep.vertices.copy(), np.array([brep.face_vertices(i) for i in range(brep.face_count)])


def audit(vertices: np.ndarray, faces: np.ndarray) -> dict:
    report = analyze_mesh(TriangleMesh(vertices, faces, 'mm'))
    d = asdict(report)
    if report.homology is not None:
        d['homology']['betti_numbers'] = report.homology.betti_numbers
    d['is_closed_oriented_2manifold'] = report.is_closed_oriented_2manifold
    d['counts'] = {k.removesuffix('_ids'): len(v) for k, v in d.items() if k.endswith('_ids')}
    d['length_unit'] = 'mm'
    d['scope'] = 'combinatorial_diagnostics_not_native_CAD_or_engineering_certification'
    return d


def generate(out: Path) -> dict:
    for folder in ('meshes', 'reports', 'provenance'):
        (out / folder).mkdir(parents=True, exist_ok=True)
    v, f, cap_ids = round_boss()
    diagonal = float(np.linalg.norm(np.ptp(v, axis=0)))
    gap = 1e-3 * diagonal
    policy_value = 1.25 * gap
    cap_vertices = np.unique(f[cap_ids])
    # Exactly these boundary vertices are duplicated; no unused vertices are created.
    vd = np.vstack((v, v[cap_vertices] + [0, 0, gap]))
    remap = np.arange(len(v))
    remap[cap_vertices] = np.arange(len(v), len(vd))
    fd = f.copy()
    fd[cap_ids] = remap[fd[cap_ids, ::-1]]

    # Central reflection about a uniquely exposed supporting vertex.
    direction = np.array([0.91, 0.37, -0.21])
    direction /= np.linalg.norm(direction)
    projections = v @ direction
    pinch_id = int(np.argmax(projections))
    support_margin = float(projections[pinch_id] - np.max(np.delete(projections, pinch_id)))
    if support_margin <= 1e-8:
        raise ValueError('Supporting vertex is not unique')
    keep = np.arange(len(v)) != pinch_id
    vp = np.vstack((v, 2*v[pinch_id] - v[keep]))
    reflected_ids = np.empty(len(v), dtype=np.int64)
    reflected_ids[pinch_id] = pinch_id
    reflected_ids[keep] = np.arange(len(v), len(vp))
    fp = np.vstack((f, reflected_ids[f[:, ::-1]]))

    policy = RepairPolicy(weld=WeldPolicy(tolerance=policy_value,
                                         max_displacement=policy_value))
    detached_brep = PolyhedralBRep.from_polygons(vd, fd)
    result = RepairPipeline(policy).run(detached_brep)
    if result.candidate is None or result.report.decision != 'topology_checks_passed':
        raise AssertionError('The controlled detached-cap example did not repair')
    vr, fr = mesh_from_brep(result.candidate)
    welded = weld_vertices(detached_brep, policy.weld)
    vw, fw = mesh_from_brep(welded.candidate)
    pinched_result = RepairPipeline(policy).run(PolyhedralBRep.from_polygons(vp, fp))

    meshes = {
        '00_clean_boss': (v, f),
        '01_detached_reversed_cap': (vd, fd),
        '01_welded_not_oriented': (vw, fw),
        '01_repaired_cap': (vr, fr),
        '02_pinched_vertex': (vp, fp),
    }
    reports = {}
    for name, (verts, faces) in meshes.items():
        export_mesh(out, name, verts, faces)
        reports[name] = audit(verts, faces)
        json_write(out / 'reports' / (name + '.json'), reports[name])
    json_write(out / 'reports' / '01_repair_pipeline.json', asdict(result.report))
    json_write(out / 'reports' / '02_repair_pipeline.json', asdict(pinched_result.report))
    # The repaired triangles can be cyclically rotated by orientation correction.
    def oriented_rows(triangles):
        return [tuple(np.roll(t, -int(np.argmin(t)))) for t in triangles]
    if not np.array_equal(v, vr) or oriented_rows(f) != oriented_rows(fr):
        raise AssertionError('Repair does not exactly restore the synthetic reference')
    if pinched_result.report.decision != 'rejected' or pinched_result.candidate is not None:
        raise AssertionError('Nonmanifold example was not refused by welding policy')

    observations = {
        'schema_version': '1.0', 'source': 'synthetic_parametric_construction',
        'model_inference_used': False, 'third_party_geometry_used': False,
        'length_unit': 'mm', 'circumferential_segments': 64,
        'base_radius': 20.0, 'base_thickness': 5.0, 'boss_radius': 9.0, 'boss_height': 12.0,
        'bounding_box_diagonal_mm': diagonal, 'gap_mm': gap,
        'recommended_weld_tolerance_mm': policy_value,
        'recommended_max_displacement_mm': policy_value,
        'cap_face_ids': cap_ids.tolist(), 'duplicated_boundary_vertex_ids': cap_vertices.tolist(),
        'new_boundary_vertex_ids': remap[cap_vertices].tolist(),
        'pinched_vertex_id': pinch_id, 'pinched_vertex_xyz_mm': v[pinch_id].tolist(),
        'support_direction': direction.tolist(), 'support_margin_mm': support_margin,
        'pinch_transform': "x_prime = 2*p - x; reverse reflected face winding; identify only p",
        'reference_restored_exactly': True,
        'reference_comparison': 'exact float64 coordinates and oriented triangles modulo cyclic order',
        'observed_pinched_repair_decision': pinched_result.report.decision,
        'notes': [
            'A detached component has no intrinsic outward orientation; reversal is known from the fault-injection record.',
            'Weld-only intermediate has shared-edge orientation conflicts; final orientation stage removes them.',
            'Acceptance is combinatorial, not arbitrary-mesh self-intersection or native-CAD certification.',
            'Double-boss contact is a single point: a unique supporting plane separates the two constructed bodies.',
            'Automatic vertex splitting is not an approved repair for this example.',
        ],
    }
    json_write(out / 'provenance' / 'construction.json', observations)
    json_write(out / 'reports' / 'summary.json', {
        name: {'vertices': r['vertex_count'], 'edges': r['edge_count'], 'triangles': r['face_count'],
               'betti_F2': r['homology']['betti_numbers'],
               'boundary_edges': len(r['boundary_edge_ids']),
               'orientation_conflicts': len(r['inconsistent_orientation_edge_ids']),
               'nonmanifold_vertices': r['nonmanifold_vertex_ids'],
               'closed_oriented_2manifold': r['is_closed_oriented_2manifold']}
        for name, r in reports.items()
    })
    return observations


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    generate(args.out)
    print('Wrote synthetic fixtures to', args.out)
