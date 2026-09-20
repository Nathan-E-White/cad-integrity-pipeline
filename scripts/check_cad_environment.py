"""Fail closed when the shared CadQuery/OCP/VTK runtime is unavailable."""
from __future__ import annotations

import math
from importlib.metadata import version


def main() -> None:
    import cadquery as cq
    from vtkmodules.vtkCommonCore import vtkVersion

    shape = cq.Workplane("XY").box(1, 2, 3).val()
    if not shape.isValid() or not math.isclose(shape.Volume(), 6.0, rel_tol=1e-10):
        raise RuntimeError("CadQuery box construction failed its validity/volume smoke check")
    print(f"CadQuery {version('cadquery')}; OCP {version('cadquery-ocp')}; "
          f"VTK {vtkVersion.GetVTKVersion()}: CAD environment verified.")


if __name__ == "__main__":
    main()
