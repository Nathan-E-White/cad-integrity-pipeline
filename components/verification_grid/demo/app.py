
import gradio as gr
from gradio_verificationgrid import VerificationCheck, VerificationGrid, VerificationGridData, VerificationGroup


with gr.Blocks() as demo:
    VerificationGrid(value=VerificationGridData(
        "Verification", "2 / 2 pass", (
            VerificationGroup("Topology", (VerificationCheck("closed_2_manifold", "", "passed"),)),
            VerificationGroup("Artifact integrity", (VerificationCheck("candidate_retained", "", "passed"),)),
        ),
    ))


if __name__ == "__main__":
    demo.launch()
