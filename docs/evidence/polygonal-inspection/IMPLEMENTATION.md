# Polygonal inspection implementation evidence

Implementation is the default polygonal workspace after local qualification. The 141-case catalogue is a
behavioral specification, not a claim that 141 executable tests have passed.

## Public seams and executed coverage

| Area | Executable coverage |
| --- | --- |
| Snapshot/projection | `tests/test_polygonal_inspection.py`: owned arrays, nested immutability, supplied nine-category memberships, independent stage identities, units, mixed polygon area/winding, local concave/nonplanar/self-intersecting/degenerate failures, raw unresolved references, display budgets, versioned encoding |
| Controller/release | Same module: real saved controller, retained paths, candidate-write failure with in-memory candidate, optional legacy figures, installed API schema; existing `tests/test_gradio_app.py` retains upload/STEP/release failure coverage |
| Admission | `tests/test_session_admission.py`: simultaneous contenders, cross-session independence, release after exception/stream close, missing session, all three installed routes sharing one guard, delivery-failure recovery |
| Browser contracts | `frontend/tests/{inspection,state,wire}.test.ts`: scoped targets, polygon-to-triangle mapping, invalid payload rejection, independent pinned selections, clipping linkage, filters, transport round-trip and decoding limit |
| Installed browser | `frontend/tests/browser/workspace.spec.ts`: example/upload delivery, selection and pane/mode persistence, replacement clearing, local hover/clipping, stable geometry buffers, context recovery, absent candidate and invalid start |
| Real maximum input | `frontend/tests/capacity/capacity.spec.ts`: restricted 250,000-vertex / 500,000-triangle upload, both panes, last source face reachable |
| Dense display stress | `frontend/tests/replay/replacement.spec.ts`: captured real geometry, deliberately synthetic dense memberships, all entity kinds, resize/maximize, ten replacements, measured resource gates |
| Compatibility | Original inspector v1 core suite retained unchanged: 28 passing tests |

The catalogue also describes finer combinations and fault-injection cases beyond
these executable checks. Those rows remain specifications; no skipped test stubs
are used to present them as coverage.

## Local environment and limits

2026-09-20: macOS 26.6.2 (25G83), MacBookPro17,1, Apple M1, 8 GiB RAM.
Chrome version is recorded in browser evidence. GPU-memory accounting is unavailable.
The bounds in `QUALIFICATION.md` were chosen before measurements.

`projection-capacity.json` measures geometry projection with supplied synthetic
reports; it does not claim numerical evaluation. `parent-capacity.json` records a
real admitted controller run; its existing homology budget yields unavailable
homology at this size. The separate browser upload tests use the same existing
admission limits. The current controller measurement excludes obsolete Plotly
figure construction; public controller callers may still request those figures. Display qualification does not turn unavailable homology into a
pass.

## Failures found and fixed during red–green work

- Frozen outer objects were insufficient: snapshot arrays now own immutable byte storage.
- Whole-model triangulation erased supported neighbors: independent face results retain provenance and local issues.
- Missing candidate-file persistence incorrectly coupled download and runtime inspection: D-001 now keeps the candidate in memory.
- Full JSON delivery through the Gradio stream caused browser memory failure. Bounded gzip documents now use Gradio-managed file delivery; numerical arrays do not travel through repeated event values.
- Hovering a last-page entity reset pagination before clicking. Page resets now depend on mesh revision/filter/kind, not unrelated hover updates.
- Result-delivery exceptions left computation controls disabled. Installed routes restore controls and release admission; inspection encoding failure retains existing report values and download paths.

## Reproduction

Build: `pixi run build-inspection-component`.
Generate maximum input: `.pixi/envs/default/bin/python scripts/qualify_inspection_projection.py`.
Record real controller result: `.pixi/envs/default/bin/python scripts/qualify_inspection_parent.py`.
Run the frontend's `check`, `test`, and `test:browser` scripts. The capacity and
replay checks use `--config playwright.capacity.config.ts` and
`--config playwright.replay.config.ts`, respectively. They start loopback parent
servers, use installed frontend assets, and write the evidence files here.

The replay changes only the qualification adapter, explicitly substituting dense
synthetic memberships over captured real geometry. It is separate from numerical
and real-controller evidence. It is not a production route or a new diagnostic.

## Local results

- Projection/encoding of both maximum-size panes: 1.46 seconds, 75,126,955 JSON bytes.
- Real admitted controller: 59.49 seconds, candidate retained, two inspection stages.
- Installed dense replay: 250,000 vertices, 750,000 edges and 500,000 faces per pane;
  all nine categories populated deliberately. Ten replacement cycles passed.
- Source entities remain complete. Only redundant fallback segments for supported
  faces were removed; unsupported faces retain resolvable boundaries.
- Final dense replay: 4.98–6.52 second loads; 33.5–92.9 ms measured interactions;
  sampled combined browser resident increase 455,344,128 bytes (one-second samples),
  no retained growth after ten replacements and comparable garbage collection.
- Final real maximum upload browser run: 52.24 seconds including computation and
  delivery, 203 ms for the selection sequence, zero page errors.
- Python regression suite before review: 308 passed, no skips. Installed browser behavior: 5 passed.
  Real maximum upload and dense replacement: one passing scenario each.
- Frontend contracts: 14 tests; original inspector v1: 28 tests. Svelte checks: no
  errors or warnings. Changed Python modules: mypy and Ruff pass.
- Global mypy/Ruff remain blocked by the pre-existing `mesh_motorcycle.py` undefined
  `_gen_synthetic_mpaths` reference and import/type-style issues. That file is
  unchanged from baseline `e744379`; unrelated native/research work is excluded.

Review found and resolved one low-priority route-typing concern and one unavailable-state
reporting gap. [The two-axis review](REVIEW.md) records both findings and independent
rechecks. The added regression verifies visible and retained projection diagnostics
without losing downloads. Final regression results are recorded below.

No hosted CI result or hardware-independent performance guarantee is claimed.

Final review-fix verification: **309 Python tests passed** (18.51 seconds),
**5 installed-parent browser tests passed** (14.0 seconds), changed-module mypy and
Ruff passed, and Svelte reported zero errors/warnings. The committed artifact
inventory is verified independently of the concurrent native/research additions
in this shared working tree. Those additions are not part of this implementation.
