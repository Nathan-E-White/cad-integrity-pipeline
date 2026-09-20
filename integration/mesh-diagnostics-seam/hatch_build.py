"""Refuse distributable wheels without the generated Gradio frontend."""
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        if self.target_name != "wheel" or version == "editable":
            return
        templates = Path(self.root) / "backend/gradio_meshdiagnostics/templates"
        required = [templates / kind / name
                    for kind in ("component", "example")
                    for name in ("index.js", "style.css", "svelte_runtime_entry.js")]
        missing = [str(path.relative_to(self.root)) for path in required
                   if not path.is_file() or path.stat().st_size == 0]
        if missing:
            raise RuntimeError(
                "Missing built Gradio frontend: " + ", ".join(missing)
                + ". Install editable with the Gradio extra, run bun install --frozen-lockfile at the repository root, then "
                "python scripts/build_component.py before building a distributable wheel."
            )
