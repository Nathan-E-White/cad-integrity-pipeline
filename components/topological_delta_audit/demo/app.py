
import gradio as gr
from gradio_topologicaldeltaaudit import DeltaAuditRow, TopologicalDeltaAudit, TopologicalDeltaAuditData


with gr.Blocks() as demo:
    TopologicalDeltaAudit(value=TopologicalDeltaAuditData(
        "Topological & Geometric Delta Audit",
        (
            DeltaAuditRow("geometry", "Vertices", "320", "256", "−64"),
            DeltaAuditRow("topology", "Betti tuple (β₀, β₁, β₂)", "(2, 0, 0)", "(1, 0, 1)", "verified"),
        ),
    ))


if __name__ == "__main__":
    demo.launch()
