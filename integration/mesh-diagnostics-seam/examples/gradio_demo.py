"""Run with the installed wheel; serves only on loopback by default."""
import os
import time

import gradio as gr
from make_fixture import build
from gradio_meshdiagnostics import MeshDiagnostics


def make_display_document():
    return build().model_dump(mode="json")


def preview_loading(progress=gr.Progress()):
    """A labeled delay for exercising the host loading display, not computation."""
    progress(0, desc="Fixture loading preview")
    time.sleep(1)
    return make_display_document()


with gr.Blocks() as demo:
    gr.Markdown("### Mesh inspection — deterministic fixture")
    mounted = gr.Checkbox(value=True, label="Mount inspector")

    @gr.render(inputs=mounted)
    def render_inspector(is_mounted):
        if not is_mounted:
            return
        with gr.Row():
            run = gr.Button("Load illustrative comparison")
            loading = gr.Button("Preview loading state")
            clear = gr.Button("Clear document")
            hide = gr.Button("Hide inspector")
            show = gr.Button("Show inspector")
        viewer = MeshDiagnostics(elem_id="mesh-inspector")
        run.click(fn=make_display_document, inputs=[], outputs=[viewer])
        loading.click(fn=preview_loading, outputs=[viewer])
        clear.click(fn=lambda: None, inputs=[], outputs=[viewer])
        hide.click(fn=lambda: gr.update(visible=False), outputs=[viewer])
        show.click(fn=lambda: gr.update(visible=True), outputs=[viewer])

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=int(os.environ.get("GRADIO_SERVER_PORT", "7878")), share=False)
