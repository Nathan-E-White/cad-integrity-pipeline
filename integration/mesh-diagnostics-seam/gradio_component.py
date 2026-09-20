"""Backend seam for a BUILT custom Gradio component, not a drop-in gr.HTML hack.

The Gradio-generated package must include the compiled frontend and metadata.
See CURRENT_STATUS.md for the current integration guide and delivery boundaries.
This class alone does not install a custom frontend.
"""
from __future__ import annotations
from typing import Any
from gradio.components.base import Component
from gradio.data_classes import GradioModel
from .contracts import InspectorDocument, MeshPayload


class InspectorData(GradioModel):
    schema_version: int = 1
    meshes: list[MeshPayload]
    linked_views: bool = True


class MeshDiagnostics(Component):
    """Output-only surface inspector. Hover/camera/selection stay in the browser."""
    EVENTS = []
    data_model = InspectorData

    def __init__(self, value: InspectorDocument | dict | None = None, **kwargs: Any):
        super().__init__(value=value, **kwargs)

    def preprocess(self, payload: InspectorData | None) -> None:
        """No untrusted browser geometry is sent to an engineering operation."""
        return None

    def postprocess(self, value: InspectorDocument | dict | None) -> InspectorData | None:
        if value is None:
            return None
        # Revalidate even an existing mutable model; never silently turn errors
        # into a blank or green success frame.
        raw = value.model_dump() if isinstance(value, InspectorDocument) else value
        checked = InspectorDocument.model_validate(raw)
        return InspectorData(**checked.model_dump())

    def example_payload(self) -> dict:
        return InspectorDocument().model_dump(mode="json")

    def example_value(self) -> dict:
        return self.example_payload()
