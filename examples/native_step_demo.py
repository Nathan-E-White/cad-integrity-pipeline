"""Create/audit/round-trip a native cylinder. Requires the [cad] extra; no remote service."""
from pathlib import Path
from tempfile import TemporaryDirectory

from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder

from cad_integrity.adapters.ocp import export_checked_step, run_step_pipeline
from cad_integrity.serialization import dumps


def main() -> None:
    # Temporary filenames avoid overwriting user files or leaving input/output clutter.
    with TemporaryDirectory(prefix="cad-integrity-demo-") as directory:
        root = Path(directory)
        export_checked_step(BRepPrimAPI_MakeCylinder(3, 12).Shape(), root / "input.step")
        report = run_step_pipeline(root / "input.step", root / "checked.step")
        print(dumps(report))
        print("Native analytic cylinder retained; already-valid input required no repair.")


if __name__ == "__main__":
    main()
