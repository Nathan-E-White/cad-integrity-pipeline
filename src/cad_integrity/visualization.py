"""Optional Plotly views. Building a figure does not display it or start a server."""
from __future__ import annotations

from typing import Any

import numpy as np

from .errors import MissingOptionalDependency
from .models import PolyhedralBRep, TriangleMesh
from .topology import TopologyReport


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
                                 color=color, opacity=0.85, flatshading=True, name="Surface"))
    if edge_polylines:
        coordinates = []
        for points in edge_polylines:
            coordinates.extend(points.tolist())
            coordinates.append([None, None, None])
        x, y, z = zip(*coordinates, strict=True)
        figure.add_trace(go.Scatter3d(x=x, y=y, z=z, mode="lines",
                                      line={"color": edge_color, "width": 7}, name="Flagged edges"))
    figure.update_layout(title=title, scene={"aspectmode": "data",
        "xaxis_title": f"x [{mesh.length_unit}]", "yaxis_title": f"y [{mesh.length_unit}]",
        "zaxis_title": f"z [{mesh.length_unit}]"}, margin={"l": 0, "r": 0, "b": 0, "t": 45})
    return figure


def polygonal_audit_figure(brep: PolyhedralBRep, report: TopologyReport, *, title: str) -> Any:
    flagged = sorted(set(report.boundary_edge_ids + report.nonmanifold_edge_ids
                          + report.inconsistent_orientation_edge_ids))
    polylines = tuple(brep.vertices[brep.edges[edge_id]] for edge_id in flagged)
    color = "seagreen" if report.is_closed_oriented_2manifold else "lightgray"
    return mesh_figure(brep.triangulate_convex_faces(), title=title, color=color,
                       edge_polylines=polylines)
