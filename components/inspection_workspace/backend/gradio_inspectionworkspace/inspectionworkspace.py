"""Installed Gradio delivery for browser-local polygonal inspection."""

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

from gradio.components.base import Component
from gradio.data_classes import FileData, GradioModel
from gradio.events import Events


class InspectionDelivery(GradioModel):
    file: FileData | None = None
    error: str | None = None


class InspectionWorkspace(Component):
    """Deliver a bounded cache file; interaction never calls the backend."""

    FRONTEND_DIR = "../../frontend"
    EVENTS = [Events.change]
    data_model = InspectionDelivery

    def preprocess(self, payload: InspectionDelivery | None) -> None:
        return None

    def postprocess(self, value: dict[str, Any] | None) -> InspectionDelivery:
        try:
            return InspectionDelivery(file=self._cache_document(value))
        except (OSError, ValueError) as exc:
            return InspectionDelivery(error=f"Inspection delivery unavailable: {exc}")

    def _cache_document(self, value: dict[str, Any] | None) -> FileData | None:
        if value is None or not value.get("meshes"):
            return None
        document = json.dumps(value, separators=(",", ":"), allow_nan=False).encode()
        digest = hashlib.sha256(document).hexdigest()
        directory = Path(self.GRADIO_CACHE) / "inspection" / digest
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "inspection.json.gz"
        if not path.exists():
            # Content addressed and identical across concurrent deliveries.
            # Gradio serves/cache-manages this transport, not the artifact release.
            import os
            import tempfile

            descriptor, temporary = tempfile.mkstemp(dir=directory)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(gzip.compress(document, compresslevel=1, mtime=0))
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return FileData(
            path=str(path), orig_name="inspection.json.gz", mime_type="application/gzip"
        )

    def example_payload(self) -> None:
        return None

    def example_value(self) -> None:
        return None
