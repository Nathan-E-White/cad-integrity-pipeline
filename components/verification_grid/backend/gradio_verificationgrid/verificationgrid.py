"""Typed Gradio adapter for the grouped verification projection."""
from __future__ import annotations

from typing import Any, Mapping

from gradio.components.base import Component
from gradio.events import Events

from .data import VerificationCheck, VerificationGridData, VerificationGroup


class VerificationGrid(Component):
    """Render grouped static checks with pass/fail/inconclusive status dots."""

    FRONTEND_DIR = "../../frontend"
    EVENTS = [Events.change]

    def api_info(self) -> dict[str, Any]:
        """Describe the static JSON payload included in Gradio's app config."""
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "groups": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["title", "summary", "groups"],
        }

    def preprocess(self, payload: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
        return payload

    def postprocess(self, value: VerificationGridData | Mapping[str, Any] | None) -> dict[str, Any]:
        if value is None:
            return {"title": "Verification", "summary": "0 / 0", "groups": []}
        return value.to_json() if isinstance(value, VerificationGridData) else dict(value)

    def example_payload(self) -> dict[str, Any]:
        return self.example_value()

    def example_value(self) -> dict[str, Any]:
        return self.postprocess(VerificationGridData(
            "Verification", "1 / 1 pass",
            (VerificationGroup("Topology", (VerificationCheck("closed_2_manifold", "", "passed"),)),),
        ))
