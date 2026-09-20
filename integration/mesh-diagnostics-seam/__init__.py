"""Optional diagnostic display extension; imports do not start a server."""
from .contracts import InspectorDocument, MeshPayload, Metric, ScalarField, Selection, Trace
from .payload import document, inspect_triangles, mesh_payload
from .npz_io import load_numeric_npz

__all__ = ["InspectorDocument", "MeshPayload", "Metric", "ScalarField", "Selection", "Trace",
           "document", "inspect_triangles", "mesh_payload", "load_numeric_npz"]
