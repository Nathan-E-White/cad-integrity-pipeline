"""Build Gradio assets with its installed tooling, then an installable wheel.

Run after installing this project editable in a build environment with Gradio,
Hatchling and build installed, and running npm ci in the component directory.
"""
from pathlib import Path
import subprocess
import shutil
import inspect
import sys

import gradio
from gradio_meshdiagnostics import MeshDiagnostics

root = Path(__file__).resolve().parents[1]
preview = root / "node_modules/@gradio/preview/dist/index.js"
backend = root / "backend/gradio_meshdiagnostics"
if Path(inspect.getfile(MeshDiagnostics)).resolve().parent != backend:
    raise RuntimeError("Build requires this checkout installed editable, not an older wheel")
# Only these generated build directories are disposable. Removing them ensures
# a successful no-op discovery cannot qualify stale assets from an earlier build.
for kind in ("component", "example"):
    generated = backend / "templates" / kind
    if generated.exists():
        shutil.rmtree(generated)
subprocess.run([
    "node", str(preview), "--component-directory", str(root),
    "--root", str(Path(gradio.__file__).parent / "templates/frontend"),
    "--mode", "build", "--python-path", sys.executable,
], cwd=root, check=True)
assets = root / "backend/gradio_meshdiagnostics/templates/component"
for name in ("index.js", "style.css", "svelte_runtime_entry.js"):
    if not (assets / name).is_file():
        raise RuntimeError(f"Gradio build did not emit {name}")
subprocess.run([sys.executable, "-m", "build", "--no-isolation", "--wheel", str(root)], check=True)
