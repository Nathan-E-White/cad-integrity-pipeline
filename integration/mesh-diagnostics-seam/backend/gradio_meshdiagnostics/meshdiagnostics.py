"""Installed Gradio component registration and frontend asset ownership."""
from cad_mesh_inspector.gradio_component import MeshDiagnostics as _MeshDiagnostics


class MeshDiagnostics(_MeshDiagnostics):
    FRONTEND_DIR = "../.."
    EVENTS = []
