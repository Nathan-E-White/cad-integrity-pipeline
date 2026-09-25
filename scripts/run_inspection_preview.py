"""Run the installed parent with the inspection workspace for qualification."""
import os

from cad_integrity.gradio_app import build_app

if __name__ == "__main__":
    build_app().launch(
        server_name="127.0.0.1",
        server_port=int(os.environ.get("CAD_INTEGRITY_PREVIEW_PORT", "7863")),
        share=False,
    )
