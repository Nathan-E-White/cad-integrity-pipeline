# Slice 7a: retained NURBS evaluation through an owned NumPy seam

Implemented from baseline `a28d451`. See [DESIGN.md](DESIGN.md) for the frozen
caller, numerical, error and accounting contracts.

## Result and ownership

`cad_integrity.nurbs.evaluate_surface` is the installed synchronous caller for
the retained `cad::nurbs` evaluator. It accepts independent parameter vectors and
returns their full Cartesian-product positions, oriented normals, algebraically
ordered curvatures and regularity mask. Python normalizes real arrays to native
float64 C layout. The private binding snapshots every input while holding the GIL,
releases the GIL only for evaluation and exports independent writable NumPy owners.

The existing standalone bundle exposes
`NURBSCoreEngine.evaluate_surface_native`. It preserves the bundle's result and
geometry/evaluation exception types and deliberately does not replace the Python
reference evaluator. The native path requires the parent Python 3.13 package;
there is no fallback or runtime backend registry. `batch_size` remains accepted
and validated for compatibility, but it does not control native traversal.

The binding compiles the retained C++ implementation rather than adding a second
kernel. `setup.py` and the sdist enumerate the binding, implementation and public
header explicitly. The maintained CMake target and standalone NURBS build remain
unchanged.

## Corrections and qualification cases

- Differential tests cover degrees 1 through 5, repeated interior knots, exact
  endpoints and rational weights uniformly scaled from `1e-100` through `1e100`.
  Analytic plane and quarter-cylinder fixtures check points, orientation and
  curvature; translated and small-scale planes check numerical conditioning.
- Shared differential qualification exposed an existing upper-endpoint span
  discrepancy. The retained basis evaluator now selects the last nonempty span
  to the left of a repeated closed upper endpoint while retaining right-hand
  selection at interior knots. A direct C++ regression and installed-host parity
  case cover the correction.
- Singular mask/reject behavior, empty grids, degree zero, malformed inputs,
  invalid weights and tolerances, private dtype/rank/layout refusal, output
  ownership, simultaneous calls and exact output-budget boundaries are covered.
- Final implementation review exposed one public error-classification gap:
  NumPy could leak `TypeError` for non-numeric array-like inputs even though the
  contract assigns invalid input to `ValueError`. A public-seam regression failed
  first; normalization now translates NumPy conversion failures to `ValueError`.
  The standalone adapter also verifies conversion to `GeometryValidationError`.

## Admission accounting

The binding checks all sums and products before input copies or native allocation.
It admits logical normalized input snapshots, the additional normalized native
control net, basis tables, conservative basis scratch, native and exported output
payloads, and a recurrence/contraction work score. Output accounting is 81 bytes
per grid sample: ten doubles and one validity byte. Shape dimensions must fit
`uint32`; degrees must fit the kernel's signed recurrence range.

These are logical payload and work bounds. They exclude Python normalization,
caller storage, allocator capacity/overhead, Python objects, process RSS and wall
time. Full output arrays and basis tables are retained; this is not a streaming or
peak-memory guarantee.

## Verification

- Installed NURBS caller: **43 passed**, no skips.
- Standalone professionalized bundle: **144 passed**, no skips, including the
  explicit native adapter.
- Native Release, Debug and ASan/UBSan workflows: **10/10 passed each**. The NURBS
  test runs in all three workflows with warnings treated as errors.
- Isolated CPython 3.13 sdist and wheel builds succeeded, with the wheel built from
  the extracted sdist. The archive contains the binding, retained C++ source,
  public header, installed caller, stub and test.
- The wheel was installed outside the checkout. **106 passed**, no skips across
  NURBS, surface, UV, BRep and quad installed-host suites. Module and extension
  paths resolved under the temporary environment's `site-packages`. This
  environment shares qualified Pixi dependencies through system site packages;
  it is not an independent dependency or platform qualification.
- Full root suite: **477 passed**, no skips, with 92% aggregate statement
  coverage.
- Changed Python sources and tests pass Ruff; `cad_integrity.nurbs` passes mypy.
  Root Ruff retains 7 pre-existing findings in `mesh_motorcycle.py`; root mypy
  retains its pre-existing undefined `_gen_synthetic_mpaths`. That file is
  unchanged, so root lint/typechecking are not claimed green.
- Bytecode compilation and artifact-manifest verification pass.
- Independent Standards review identified ordinal-coupled native error mapping
  and an anonymous endpoint regression. Error translation is now an exhaustive
  enum switch and the regression is named; re-review found no remaining findings.
- Independent Spec review identified nonnumeric tolerance classification plus
  missing analytic polynomial and private-rank cases. All were corrected and
  re-review found no remaining findings. Reviewers performed source review and
  focused rechecks, not independent execution of every qualification command.

## Measurement and limits

`benchmark.py` records seven-run medians after one warmup in `benchmark.json`.
For square grids of side 16, 128 and 256, recorded installed-host times were
0.038 ms, 1.532 ms and 6.503 ms. Private binding times, including input snapshot,
kernel and export, were 0.033 ms, 1.580 ms and 6.479 ms. The retained Python
reference took 0.503 ms, 7.295 ms and 28.122 ms respectively. These are local
phase measurements, not pure conversion timings, peak-memory measurements or a
cross-platform performance guarantee.

The result establishes the exercised CPU evaluator, binding ownership and caller
contracts. It does not establish global surface injectivity, smoothness across
repeated knots, trim correctness, STEP reconstruction, CAD repair, mesh quality,
simulation readiness, GPU parity or certification. Invalid mask entries remain
honest partial numerical output, not qualified surface samples.

## Continuation

Slice 7a is deliberately independent of Delaunay construction and chart-axis
tracing. Neither is activated by this work. A prepared-surface owner, streaming
API, alternate backend or automatic standalone fallback still requires a measured
caller and a separate contract.
