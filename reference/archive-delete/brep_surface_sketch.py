"""Minimal in-memory B-rep vocabulary retained from the exploratory prototype.

This is a data sketch, not an exchange adapter or a replacement for OCP's
TopoDS model.  In particular, it cannot establish p-curve correctness, face
orientation, tolerances, or trim validity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Edge:
    start_vertex: int
    end_vertex: int
    curve_id: int
    pcurve_ids: dict[int, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Wire:
    edge_ids: tuple[int, ...]
    forward: tuple[bool, ...]

    def is_closed(self, edges: tuple[Edge, ...]) -> bool:
        """Check index connectivity only; geometry and p-curves remain unchecked."""
        if not self.edge_ids or len(self.edge_ids) != len(self.forward):
            return False
        if any(index < 0 or index >= len(edges) for index in self.edge_ids):
            return False
        ordered = [edges[index] for index in self.edge_ids]
        starts = [
            edge.start_vertex if direction else edge.end_vertex
            for edge, direction in zip(ordered, self.forward, strict=True)
        ]
        ends = [
            edge.end_vertex if direction else edge.start_vertex
            for edge, direction in zip(ordered, self.forward, strict=True)
        ]
        return all(end == starts[(index + 1) % len(starts)] for index, end in enumerate(ends))


@dataclass(frozen=True)
class Face:
    surface_id: int
    outer_wire_id: int
    inner_wire_ids: tuple[int, ...] = ()


@dataclass
class SurfaceRegistry:
    """Opaque geometry registry; evaluation belongs in a qualified NURBS module."""

    surfaces: dict[int, dict[str, Any]] = field(default_factory=dict)

    def add_nurbs(self, surface_id: int, definition: dict[str, Any]) -> None:
        if surface_id in self.surfaces:
            raise ValueError(f"surface {surface_id} is already registered")
        self.surfaces[surface_id] = {**definition, "kind": "NURBS"}
