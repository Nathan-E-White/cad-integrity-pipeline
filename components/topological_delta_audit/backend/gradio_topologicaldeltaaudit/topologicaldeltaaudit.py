"""Typed Gradio adapter for the topology and discretization audit projection."""
from __future__ import annotations

from typing import Any, Mapping

from gradio.components.base import Component
from gradio.events import Events

from .data import DeltaAuditRow, TopologicalDeltaAuditData


class TopologicalDeltaAudit(Component):
    """Render structured before/after mesh diagnostics as a dense audit grid."""

    FRONTEND_DIR = "../../frontend"
    EVENTS = [Events.change]

    def api_info(self) -> dict[str, Any]:
        """Describe the static JSON payload included in Gradio's app config."""
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "rows": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["title", "rows"],
        }

    def preprocess(self, payload: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
        return payload

    def postprocess(self, value: TopologicalDeltaAuditData | Mapping[str, Any] | None) -> dict[str, Any]:
        if value is None:
            return {"title": "Topological & Geometric Delta Audit", "rows": []}
        return value.to_json() if isinstance(value, TopologicalDeltaAuditData) else dict(value)

    def example_payload(self) -> dict[str, Any]:
        return self.example_value()

    def example_value(self) -> dict[str, Any]:
        return self.postprocess(TopologicalDeltaAuditData(
            "Topological & Geometric Delta Audit",
            (DeltaAuditRow("geometry", "Vertices", "320", "256", "−64"),),
        ))
