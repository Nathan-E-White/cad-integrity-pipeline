"""Optional Plotly views. Building a figure does not display it or start a server."""
from __future__ import annotations

from typing import Any

import numpy as np

from .errors import MissingOptionalDependency
from .models import PolyhedralBRep, TriangleMesh
from .topology import TopologyReport

_DIAGNOSTIC_CAMERA = {
    "eye": {"x": 1.6, "y": -1.6, "z": 1.2},
    "up": {"x": 0, "y": 0, "z": 1},
    "center": {"x": 0, "y": 0, "z": 0},
    "projection": {"type": "orthographic"},
}
_DIAGNOSTIC_HEIGHT = 520


def _go() -> Any:
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise MissingOptionalDependency("Install cad-integrity-lab[notebook] for Plotly figures") from exc
    return go


def mesh_figure(mesh: TriangleMesh, *, title: str = "Surface diagnostic",
                color: str = "lightgray", edge_polylines: tuple[np.ndarray[Any, Any], ...] = (),
                edge_color: str = "crimson") -> Any:
    """Render actual edge polylines; edge IDs are never mistaken for vertex IDs."""
    go = _go()
    xyz = mesh.vertices
    triangles = mesh.triangles
    figure = go.Figure(go.Mesh3d(x=xyz[:, 0], y=xyz[:, 1], z=xyz[:, 2],
                                 i=triangles[:, 0], j=triangles[:, 1], k=triangles[:, 2],
                                 color=color, opacity=0.85, flatshading=True, name="Surface",
                                 hovertemplate="Surface triangle<extra></extra>"))
    if edge_polylines:
        coordinates = []
        for points in edge_polylines:
            coordinates.extend(points.tolist())
            coordinates.append([None, None, None])
        x, y, z = zip(*coordinates, strict=True)
        figure.add_trace(go.Scatter3d(x=x, y=y, z=z, mode="lines",
                                      line={"color": edge_color, "width": 7},
                                      name=f"Flagged edges ({len(edge_polylines)})",
                                      hovertemplate="Flagged edge<extra></extra>"))
    overlay_summary = (
        f"{len(edge_polylines)} flagged edge{'s' if len(edge_polylines) != 1 else ''} highlighted"
        if edge_polylines else "No flagged edges in this audit"
    )
    figure.update_layout(
        title={"text": title, "x": 0.02, "xanchor": "left"},
        height=_DIAGNOSTIC_HEIGHT,
        autosize=True,
        paper_bgcolor="#ffffff",
        font={"color": "#23344d"},
        legend={"orientation": "h", "x": 0.02, "xanchor": "left", "y": 1.0, "yanchor": "bottom"},
        annotations=[{
            "text": overlay_summary,
            "x": 0.98,
            "xanchor": "right",
            "xref": "paper",
            "y": 1.0,
            "yanchor": "bottom",
            "yref": "paper",
            "showarrow": False,
            "font": {"size": 12, "color": "#53657d"},
        }],
        scene={"aspectmode": "data",
        "bgcolor": "#f6f8fb", "camera": _DIAGNOSTIC_CAMERA,
        "xaxis_title": f"x [{mesh.length_unit}]", "yaxis_title": f"y [{mesh.length_unit}]",
        "zaxis_title": f"z [{mesh.length_unit}]"},
        margin={"l": 0, "r": 0, "b": 0, "t": 72},
    )
    return figure


def polygonal_audit_figure(brep: PolyhedralBRep, report: TopologyReport, *, title: str) -> Any:
    flagged = sorted(set(report.boundary_edge_ids + report.nonmanifold_edge_ids
                          + report.inconsistent_orientation_edge_ids))
    polylines = tuple(brep.vertices[brep.edges[edge_id]] for edge_id in flagged)
    color = "seagreen" if report.is_closed_oriented_2manifold else "lightgray"
    return mesh_figure(brep.triangulate_convex_faces(), title=title, color=color,
                       edge_polylines=polylines)
