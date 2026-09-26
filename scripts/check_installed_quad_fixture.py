"""Smoke the packaged pure-quad fixture through the installed controller path."""

from __future__ import annotations

import tempfile
from pathlib import Path

import cad_integrity
from cad_integrity.gradio_app import run_polygonal_fixture
from cad_integrity.inspection import encode_inspection
from cad_integrity.workbench_results import ArtifactStore


def main() -> int:
    origin = Path(cad_integrity.__file__).resolve()
    if "site-packages" not in origin.parts:
        raise RuntimeError(f"cad_integrity was not imported from an installed wheel: {origin}")
    with tempfile.TemporaryDirectory(prefix="cad-installed-quad-") as directory:
        outcome = run_polygonal_fixture(
            "03_canonical_quad_cube",
            artifact_store=ArtifactStore(Path(directory)),
            include_legacy_figures=False,
        )
        if outcome.inspection is None or encode_inspection(outcome.inspection)["schema_version"] != 4:
            raise RuntimeError("installed canonical quad fixture did not produce v4 evidence")
        if outcome.release is None or not outcome.release.source.path.is_file():
            raise RuntimeError("installed canonical quad fixture did not retain its source")
    print(f"Installed canonical quad fixture passed from {origin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
