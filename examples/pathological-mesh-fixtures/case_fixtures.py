"""Load the supplied indexed fixtures without implicit repairs or vertex merging."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent
CASES = (
    '00_clean_boss', '01_detached_reversed_cap', '01_welded_not_oriented',
    '01_repaired_cap', '02_pinched_vertex',
)


def load_arrays(case: str) -> tuple[np.ndarray, np.ndarray, str]:
    if case not in CASES:
        raise ValueError(f'Unknown case {case!r}; choose one of {CASES}')
    with np.load(ROOT / 'meshes' / f'{case}.npz', allow_pickle=False) as data:
        vertices, faces = data['vertices'].copy(), data['triangles'].copy()
        unit = str(data['length_unit'].item())
    if vertices.ndim != 2 or vertices.shape[1] != 3 or not np.isfinite(vertices).all():
        raise ValueError('Invalid vertex array')
    if faces.ndim != 2 or faces.shape[1] != 3 or faces.dtype.kind not in 'iu':
        raise ValueError('Invalid triangle array')
    if faces.size and (faces.min() < 0 or faces.max() >= len(vertices)):
        raise ValueError('Triangle index out of range')
    if unit != 'mm':
        raise ValueError(f'Unexpected canonical unit {unit!r}')
    return vertices, faces, unit


def load_brep(case: str):
    from cad_integrity import PolyhedralBRep
    vertices, faces, unit = load_arrays(case)
    return PolyhedralBRep.from_polygons(vertices, faces, length_unit=unit)


def saved_report(case: str) -> dict[str, Any]:
    if case not in CASES:
        raise ValueError(case)
    return json.loads((ROOT / 'reports' / f'{case}.json').read_text(encoding='utf-8'))


def repair_policy():
    from cad_integrity import RepairPolicy, WeldPolicy
    record = json.loads((ROOT / 'provenance' / 'construction.json').read_text(encoding='utf-8'))
    return RepairPolicy(weld=WeldPolicy(
        tolerance=record['recommended_weld_tolerance_mm'],
        max_displacement=record['recommended_max_displacement_mm'],
    ))


def show_case(case: str):
    """Actual geometry, not an exploded view. Red marks known faults/diagnostics.

    A green surface only means that recorded combinatorial checks passed.
    There is no live geometry analysis in this display helper.
    """
    import plotly.graph_objects as go

    v, f, _ = load_arrays(case)
    report = saved_report(case)
    passed = report['is_closed_oriented_2manifold']
    color = '#259968' if passed else '#ABB3BF'
    face_colors = np.full(len(f), color, dtype=object)
    if case in ('01_detached_reversed_cap', '01_welded_not_oriented'):
        record = json.loads((ROOT / 'provenance' / 'construction.json').read_text(encoding='utf-8'))
        face_colors[record['cap_face_ids']] = '#DC143C'
    fig = go.Figure(go.Mesh3d(
        x=v[:, 0], y=v[:, 1], z=v[:, 2],
        i=f[:, 0], j=f[:, 1], k=f[:, 2],
        facecolor=face_colors.tolist(), flatshading=True,
        name=case, hoverinfo='name', showscale=False,
    ))
    directed = np.vstack((f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]))
    edges, inverse, counts = np.unique(np.sort(directed, axis=1), axis=0,
                                       return_inverse=True, return_counts=True)
    signs = np.where(directed[:, 0] < directed[:, 1], 1, -1)
    sums = np.bincount(inverse, weights=signs, minlength=len(edges))
    highlights = edges[(counts == 1) | ((counts == 2) & (sums != 0))]
    if len(highlights):
        xyz = np.full((3*len(highlights), 3), np.nan)
        xyz[0::3], xyz[1::3] = v[highlights[:, 0]], v[highlights[:, 1]]
        fig.add_trace(go.Scatter3d(x=xyz[:, 0], y=xyz[:, 1], z=xyz[:, 2], mode='lines',
                                  line=dict(color='#DC143C', width=7),
                                  name='Open seam / winding conflict', hoverinfo='name'))
    pinch = report['nonmanifold_vertex_ids']
    if pinch:
        p = v[pinch]
        fig.add_trace(go.Scatter3d(x=p[:, 0], y=p[:, 1], z=p[:, 2], mode='markers',
                                  marker=dict(color='#DC143C', size=8),
                                  name='Nonmanifold vertex', hoverinfo='name'))
    fig.update_layout(title=case.replace('_', ' '), height=480,
                      margin=dict(l=0, r=0, b=0, t=45),
                      scene=dict(aspectmode='data', xaxis_title='x (mm)',
                                 yaxis_title='y (mm)', zaxis_title='z (mm)',
                                 camera=dict(eye=dict(x=1.6, y=-1.7, z=1.35))),
                      showlegend=True)
    return fig
