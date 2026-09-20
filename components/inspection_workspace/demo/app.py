"""Package smoke demo; the installed parent preview exercises real controller data."""
import gradio as gr
from gradio_inspectionworkspace import InspectionWorkspace

with gr.Blocks() as demo:
    InspectionWorkspace()

if __name__ == '__main__':
    demo.launch()
