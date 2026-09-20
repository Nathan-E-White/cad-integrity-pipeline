"""Run AFTER integrating/building the adapter as a Gradio custom component."""
import logging
import gradio as gr
from mesh_diagnostics import MeshValidationError
# Replace with the import name created by the mother's Gradio component scaffold.
from gradio_meshdiagnostics import MeshDiagnostics
from pipeline import process_and_audit_mesh

logger = logging.getLogger(__name__)


def audit_upload(path: str | None):
    if path is None:
        return None
    try:
        return process_and_audit_mesh(path)
    except MeshValidationError as exc:
        logger.warning("Mesh audit rejected: %s", exc)
        raise gr.Error("The mesh could not be audited. Check array shapes, indices, and archive limits.") from exc


with gr.Blocks() as demo:
    gr.Markdown("### Mesh diagnostics — inspection, not automatic certification")
    source = gr.File(label="Numeric triangle NPZ", file_types=[".npz"], type="filepath")
    run = gr.Button("Audit mesh")
    viewer = MeshDiagnostics()
    run.click(audit_upload, inputs=[source], outputs=[viewer])

if __name__ == "__main__":
    demo.launch()
