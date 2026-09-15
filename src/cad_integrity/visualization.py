"""Optional Plotly views. Building a figure does not display it or start a server."""
from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class EdgeOverlay:
    """A named, colour-coded class of diagnostic edges."""

    label: str
    polylines: tuple[np.ndarray[Any, Any], ...]
    color: str


def _go() -> Any:
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise MissingOptionalDependency("Install cad-integrity-lab[notebook] for Plotly figures") from exc
    return go


def mesh_figure(mesh: TriangleMesh, *, title: str = "Surface diagnostic",
                color: str = "lightgray", edge_polylines: tuple[np.ndarray[Any, Any], ...] = (),
                edge_color: str = "crimson",
                edge_overlays: tuple[EdgeOverlay, ...] = ()) -> Any:
    """Render actual edge polylines; edge IDs are never mistaken for vertex IDs."""
    go = _go()
    xyz = mesh.vertices
    triangles = mesh.triangles
    figure = go.Figure(go.Mesh3d(
        x=xyz[:, 0], y=xyz[:, 1], z=xyz[:, 2], i=triangles[:, 0], j=triangles[:, 1],
        k=triangles[:, 2], color=color, opacity=0.85, flatshading=True, name="Surface",
        lighting={"ambient": 0.55, "diffuse": 0.75, "roughness": 0.85, "specular": 0.1},
        hovertemplate="Surface triangle<extra></extra>",
    ))
    if edge_polylines and edge_overlays:
        raise ValueError("Use either generic edge polylines or named edge overlays, not both")
    overlays = edge_overlays or ((EdgeOverlay("Flagged edges", edge_polylines, edge_color),)
                                 if edge_polylines else ())
    for overlay in overlays:
        coordinates = []
        for points in overlay.polylines:
            coordinates.extend(points.tolist())
            coordinates.append([None, None, None])
        x, y, z = zip(*coordinates, strict=True)
        figure.add_trace(go.Scatter3d(x=x, y=y, z=z, mode="lines",
                                      line={"color": overlay.color, "width": 7},
                                      name=f"{overlay.label} ({len(overlay.polylines)})",
                                      hovertemplate="Flagged edge<extra></extra>"))
    flagged_edge_count = sum(len(overlay.polylines) for overlay in overlays)
    overlay_summary = (
        f"{len(triangles):,} triangles · {flagged_edge_count} flagged edge"
        f"{'s' if flagged_edge_count != 1 else ''} highlighted"
        if overlays else f"{len(triangles):,} triangles · No flagged edges in this audit"
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
    overlays = tuple(
        EdgeOverlay(label, tuple(brep.vertices[brep.edges[edge_id]] for edge_id in edge_ids), color)
        for label, edge_ids, color in (
            ("Boundary edges", report.boundary_edge_ids, "#d1495b"),
            ("Nonmanifold edges", report.nonmanifold_edge_ids, "#e58f2a"),
            ("Winding conflicts", report.inconsistent_orientation_edge_ids, "#6950a1"),
        ) if edge_ids
    )
    color = "seagreen" if report.is_closed_oriented_2manifold else "lightgray"
    return mesh_figure(brep.triangulate_convex_faces(), title=title, color=color,
                       edge_overlays=overlays)
