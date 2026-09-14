# CAD Integrity Lab

**Topology diagnostics, conservative repairs, and auditable STEP export.**

An independent computational-geometry work sample inspired by a CAD-foundation-model engineering role. It is not Spectral software, an SGS implementation, or an engineering certification service.

This project refactors the supplied `simplex.py` prototype into two deliberately separate paths:

| Path | Authoritative representation | What it establishes |
| --- | --- | --- |
| Polygonal research | Immutable array-backed polygonal cell complex | Exact small-complex homology, combinatorial manifold checks, explicit vertex welding and coherent orientation |
| Native CAD | Open CASCADE `TopoDS_Shape`, accessed through OCP | Kernel validity checks, conservative native healing, STEP write/read verification, preservation checks |

A triangle display mesh is **not** substituted for native CAD. Arbitrary trimmed CAD faces are **not** treated as disk cells to manufacture Betti numbers. A successful check is **not** proof of design intent, manufacturability, structural safety, or dimensional fidelity.

## Start with Pixi, PyCharm, or Jupyter

The checked-in Pixi configuration creates the full local lab on Apple Silicon: Python 3.13,
algebra, OCP, notebook, and developer tools.

```bash
pixi install
pixi run test
pixi run cad-integrity demo
```

For PyCharm, install the Pixi integration supplied by `pixi-pycharm`, then select
`.pixi/envs/default/bin/python` as the project interpreter. Keep the generated `.idea/` local.
Open `notebooks/01_integrity_lab.ipynb` using that same interpreter. The notebook includes
executed results and interactive Plotly figures; 3D rendering requires a WebGL-capable frontend.
Its computational cells run without network access. Optional native CAD cells skip explicitly
when OCP is unavailable.

For a non-Pixi Python environment, a smaller installation is sufficient for the polygonal
experiments:

```bash
python -m pip install -e .
python examples/offline_demo.py
```

`.[algebra]` adds exact integer Smith normal form through SymPy. `.[cad]` adds OCP. `.[notebook]` adds Jupyter and Plotly. CAD wheels are platform-dependent; the included native tests were executed on Linux, not macOS or Windows. See `docs/VALIDATION.md` for the actual environment and checks run.

Run `pixi run check-artifacts` to verify the package delivery and the two fixture provenance
manifests. Run `python scripts/verify_artifacts.py --write` only after intentionally changing
versioned artifacts.

## The offline experiment

The fixture is a **synthetic** 10 mm cube whose top face is detached by 0.002 mm and reversed. It is not represented as an SGS-generated defect.

```python
from cad_integrity import RepairPipeline, RepairPolicy, WeldPolicy
from cad_integrity.fixtures import cracked_cube

pipeline = RepairPipeline(
    RepairPolicy(weld=WeldPolicy(tolerance=0.005, max_displacement=0.005))
)
result = pipeline.run(cracked_cube())

print(result.report.before.homology.betti_numbers)  # (2, 0, 0)
print(result.report.after.homology.betti_numbers)   # (1, 0, 1)
print(result.report.decision)                      # topology_checks_passed
```

| Quantity | Before | After |
| --- | ---: | ---: |
| Vertices | 12 | 8 |
| Edges | 16 | 12 |
| Faces | 6 | 6 |
| Free boundary edges | 8 | 0 |
| Betti numbers over F₂ | (2, 0, 0) | (1, 0, 1) |

Four vertex pairs and four duplicate straight edges merge; one complete face loop reverses. Maximum vertex movement is 0.002 mm. The original arrays remain unchanged. Neither report certifies an embedded CAD solid.

For notebook visualization:

```python
from cad_integrity.visualization import polygonal_audit_figure

polygonal_audit_figure(result.original, result.report.before, title="Before: flagged boundaries").show()
polygonal_audit_figure(result.candidate, result.report.after, title="After: combinatorial checks passed").show()
```

Red overlays identify actual flagged edges, not incorrectly interpreted vertex IDs. Green means the specified combinatorial checks passed, not “approved engineering design.”

## Work with a real local STEP file

```bash
# Audit only; never edits the source.
cad-integrity audit-step input.step --report initial-audit.json

# Repair a private copy, apply policy, export temporarily, re-import, re-check,
# then publish a new STEP file. Existing destination/report files are refused.
cad-integrity repair-step input.step checked.step --report repair-audit.json
```

All native lengths are normalized to **millimetres**. Default precision is `1e-6 mm`; maximum allowed entity tolerance is `1e-3 mm`. These defaults are not universal engineering tolerances. Select limits appropriate to the source's units and required accuracy; increasing the tolerance is not automatically a legitimate repair.

```bash
cad-integrity repair-step input.step checked.step --report repair-audit.json \
  --precision-mm 0.000001 --max-tolerance-mm 0.001 --expected-solids 1
```

The native export gate requires valid topology/geometry under `BRepCheck_Analyzer`, the enabled `BRepAlgoAPI_Check` result, closed/coherently oriented shells, the expected solid count, faces owned by solids, no inappropriate free/nonmanifold/unowned topology, positive solid volumes, and entity tolerances within policy. It rechecks the serialized STEP and compares solid/face counts, analytic surface-type counts, area, and volume before publishing.

Healing copies native topology **and geometry** before modifying them. It uses ShapeFix and, when the input has no solids, sewing plus single-shell solid construction. It refuses ambiguous shell grouping, open holes requiring filling, silent removal of detached faces or unowned edges/vertices, and policy failures. Existing valid solids—including a solid with an internal cavity—are not flattened into independently filled shells.

This is conservative by design: some repairable inputs are rejected for human review. It does not reconstruct feature histories, recover missing dimensions from an image, or prove the original design was recovered. STEP translator import can itself process geometry, so “before” means **the OCCT-imported shape**, not an untouched generator-internal state.

## What happened to the original code?

The original bytes are preserved in `reference/simplex_original.txt`, intentionally not an importable module. This is a deliberate API revision, not a drop-in replacement for a file that did not parse.

Read `docs/REVIEW.md` for the original defects and the replacement decisions. Read `docs/MATHEMATICS.md` for coefficient fields, cell-complex assumptions, periodic CAD seams, and why **b₁ is not a leak counter**.

```text
src/cad_integrity/
    algebra.py            Validated chain complexes; exact F₂ rank; integer reference SNF
    simplicial.py         Downward closure, filtrations, actual persistence pairings
    models.py             TriangleMesh and restricted PolyhedralBRep contracts
    topology.py           Incidence, vertex links, orientations, homology reports
    repair.py             Opt-in welding, edge remapping, coherent loop orientation
    numerics.py           Parametric evaluation, local intersection, conforming refinement
    metrics.py            Triangle quality, sampled distances, area distortion
    pipeline.py           Reports, hashes, policy, progress events; no UI dependencies
    adapters/ocp.py       Native STEP import/audit/healing/round-trip export
    visualization.py      Optional Plotly surfaces and edge overlays
    cli.py                Local commands and explicit evidence outputs
```

There are no implicit downloads, API calls, servers, model inference, or example runs at package import. Typed reports are JSON-serializable. Native handles remain mutable kernel objects; keep them confined to an individual worker. Array objects own their data and are read-only by default.

## Before adding Gradio

The intended seam is a synchronous core operation plus `on_event(StageEvent)` progress callbacks, returning a candidate and evidence. The UI should orchestrate per-request storage and render these results, not implement geometry algorithms.

**External dependency status checked September 13, 2026:** the official `spectral-labs/SGS-1` Space's current `app.py` says the research demo has ended and announces SGS-2 for Q3 2026. The current application is an announcement page, not the inference endpoint assumed by the prototype. No working SGS client is claimed or included. Use a local STEP upload initially; see `docs/GRADIO_HANDOFF.md`.

Official source: https://huggingface.co/spaces/spectral-labs/SGS-1/raw/main/app.py

## Limits and reproducibility

Exact algebra here is a bounded **reference implementation**, not a claim of billion-face throughput. F₂ reduction has input/work/fill-in budgets; integer SNF has a dense-entry cap and can still be expensive. KD-tree welding avoids allocating an N×N distance matrix, but dense neighborhoods remain potentially costly and are budgeted.

Native parsing and meshing are C++ operations and are **not sandboxed** by these Python budgets. A public service needs process isolation, wall-clock and memory limits, upload limits, cancellation, and evidence retention controls. A native STEP and its JSON report are separate artifacts, not an atomic two-file transaction.

The test suite includes deliberate counterexamples and real native-kernel fixtures. It has not been evaluated on an SGS output corpus, production assemblies, arbitrary malformed STEP files, or a production workload. Dependency ranges are compatibility declarations, not a complete transitive lockfile. The recorded environment is an execution manifest, not a cross-platform guarantee.

No distribution license has been selected. The original source and this refactor are provided for the user's project; choose the intended terms before publishing a public repository.
