# Mesh-healing and NURBS integration review

September 20, 2026. Reviewed in `/private/tmp/cad-integrity-integration-sync`, branch
`integration/sync`, based on local `main` at `075b2dd`. This supplements `REVIEW.md`:
the diagnostics reconciliation is no longer the only detailed bundle assessment.
No algorithms, dependencies, native code, controllers or UI were changed.

## Recommendation

Adopt capabilities in separate slices, with host-owned admission and evidence:

| Material | Role | First useful integration |
|---|---|---|
| Diagnostics | Read-only projection of existing engineering reports | One agreed document contract and a packaged Svelte composition owner |
| Mesh healing | Derived surface numerics and explicitly selected surface operations | Immutable surface admission and read-only seam evidence; later cotangent charts |
| Python NURBS evaluator | Numerical reference and potential parity counterpart | Shared analytic fixtures after repairing the current native build mismatch |
| STL features, segmentation and cards | Separate approximate reconstruction workflow | Bounded read-only feature/fit evidence with complete source provenance |
| Solid viewer | Optional source for a demonstrated display requirement | No additional adoption implied by this review |

Mesh healing and NURBS are substantially more complete as standalone packages than
the original loose diagnostics delivery. Their remaining integration work is mostly
policy, provenance, resource limits, result contracts and persistence, rather than
recovering missing source. Passing standalone tests does not qualify host integration.

The expected internal cleanup is correspondingly narrow: namespace adopted modules,
separate selected capabilities from their demo orchestration, and fix concrete
interface defects when encountered. A wholesale rewrite or decomposition of either
bundle is not a prerequisite. Most findings below concern how the host should admit,
invoke and retain results from otherwise working standalone capabilities.

## Current evidence and archive reconciliation

| Check | Result in this review |
|---|---|
| Mesh-healing supplied suite | **69 passed**, no skips, 15.11 seconds |
| NURBS supplied suite | **132 passed**, no skips, 6.88 seconds |
| Native NURBS syntax check | **Failed**, eight compiler diagnostics; primary cause is mismatched `SurfaceGeometry` declarations |
| Mesh-healing archive/live paths | 19 members: 16 identical, 3 changed, 0 missing |
| NURBS archive/live paths | 24 members: 24 identical, 0 missing |

Mesh-healing differences are only `pyproject.toml`, `requirements.txt`, and
`SHA256SUMS`, consistent with dependency alignment. Its numerical, export, example
and test source matches the archive. NURBS source, original snapshots and tests all
match its zip. There is no second divergent implementation hidden in either archive
that needs the diagnostics-style recovery procedure. Archives remain untouched.

Archive SHA-256 values:

- Mesh healing: `692aeb5c998cb3137a135136037d695e4021ffc98dc1f3e4086ea49dd8da014f`.
- NURBS: `b03e97e787bdd8d778c77cb8007ba60fe85d4f05038f27a3c1dba587dac2abef`.

`geometry-bundle-inventory.json` contains per-path hashes and Python class/function/
method/test declarations with line spans. Reproduce it with
`python3 -B docs/reviews/integration-sync/compare_geometry_bundles.py`. This parses
source and reads archive members without extraction or execution. Historical
generated examples, original files and old validation reports remain provenance,
not current acceptance evidence.

The supplied tests were inspected before execution and run from their respective
bundle directories using the existing environment's Python, with bytecode and plugin
autoload disabled. Test/temp paths were confined to this worktree. No new environment
was installed. The suites exercised local CAD round trips; no hosted CI, application
browser, representative scan accuracy, maximum-size resource envelope, or C++/Python
numerical parity was established. Commands/results are in `geometry-validation.txt`.

## Mesh healing: modules, overlap and disposition

Paths in this section are relative to `integration/mesh_healing_extension/` unless
explicitly prefixed with `src/`.

| Module/interface | Actual capability | Host overlap and proposed disposition |
|---|---|---|
| `MeshHealingEngine` (`mesh_healing_engine.py:270`) | Owned but publicly mutable XYZ arrays and polygon lists; topology and cached-system fingerprints | New internal surface carrier only. Do not replace host `TriangleMesh`, `PolyhedralBRep` or native STEP shapes. |
| `topology_report`, `_triangulate_face`, `triangulated_faces` | Edge/fan/orientation checks; projected ear clipping with triangle-to-parent IDs, including concave polygons | Host topology remains authoritative for existing workflows. Bundle checks may be solver preconditions. Declare the selected triangulation as derived geometry. |
| `compute_cotangent_weights`, `compute_cotangent_laplacian` (616–657) | Sparse W and L, signed cotangents, optional face confidence | Useful numerical module; no equivalent cotangent solver was found in the host. Preserve W/L distinction and selected-face ordering. |
| `HarmonicSystem` (747–931) | Cached Dirichlet solve, soft anchors, Woodbury/refactor fallback, residual and stale-engine checks | Adopt behind a small chart-solving interface; use independent systems for concurrent requests. |
| `validate_uv` (689–721) | Per-triangle flips/collapse and maximum Jacobian singular-value ratio | Derived chart evidence, not the host triangle shape-quality verdict and not global injectivity. |
| `non_manifold_stitching` (398–523), `preprocess` (525–614) | Selected or heuristic boundary welds; cleanup, fan splitting, orientation and compaction | Overlaps host repair in purpose but differs in admissible topology and policy. Require separate selected surface-operation plans; do not invoke as host repair defaults. |
| `PreprocessReport.remap_constraints` (147–172) | Zero/one/many vertex provenance, surviving face maps, conflicting welded constraints rejected | Retain as evidence for explicit operations, with source/revision/units added by the host. |
| `UVSurfaceMap` (`mesh_export.py:215–288`) | Single-chart barycentric UV-to-XYZ evaluation; optional O(Q×T) location and ambiguous-XYZ rejection | Useful derived evaluation module; caller-supplied triangle IDs or bounded queries. Not NURBS evaluation. |
| `export_frontend_json`, `export_step` (`mesh_export.py:44–212`) | Indexed UV/XYZ sidecar and real planar triangular CAD faces with local round-trip checks | Derived artifacts through host persistence. Keep tested CadQuery adapter pending a measured reason to replace it. |
| `MotorcycleGraphTracer` (957–1068) | Deterministic, order-dependent opposite-edge walks on pure quads | Optional trace evidence only; no general triangle/cross-field motorcycle claim. Does not justify reusing host `mesh_motorcycle.py`. |
| `prune_motorcycle_graph` (1155–1240) | Track-length filtering and optional transactional mesh preprocessing/remapping | Keep graph filtering separate from mutation in the host. It does not merge macro-patch cells. |
| `solve_igm_quantization` (1071–1142) | L1 MILP for supplied segment lengths and opposite-chain sums, verified integrality | Defer until explicit patch/segment incidence and bounded solver policy exist. Not a complete IGM pipeline. |
| `CrossFieldOptimizer` (1306–1446) | Face-based relaxed 4-RoSy smoothing with transport and component gauges | Defer; does not implement global singularity placement, seamless chart transitions or full parameterization. |

The host's `src/cad_integrity/repair.py` provides configured weld/orientation
operations over its polygonal carrier, and `pipeline.py` owns policy and before/after
reports. Native selected sewing in `adapters/ocp.py` operates on classifier-backed
native shape evidence. A mesh vertex-pair weld is not the same operation as sewing
selected native boundary wires.

### Missing integration work and material conflicts

1. **Read-only seam discovery is not a public operation.** Candidate search occurs
   inside the mutating `non_manifold_stitching`; there is no revision-bound candidate
   document or selected plan. Extract discovery into a read-only interface before UI
   exposure. Selected pairs must carry the source revision and explicit tolerance.
2. **Default preprocessing exceeds current host policy.** `preprocess` defaults
   `stitch=True`, `split_bowties=True`, removes faces, reorients and compacts. Even
   `stitch=False` still performs the other edits. `prune_motorcycle_graph` calls full
   `work.preprocess(stitch_tolerance)` when given an engine (1182). Avoid presenting
   that path as a harmless graph filter or read-only diagnostic.
3. **Admission, identity and budgets are missing at the host seam.** Engine
   construction validates shape/indices but has no upload-byte, polygon-valence,
   candidate-pair, factorization-memory or query-work budget. Fingerprints detect
   stale caches but omit units and are not persisted source identities. KD-tree
   pair enumeration can still produce quadratically many candidates; sparse LU can
   have substantial fill. The IGM time limit is optional. Host limits must precede
   allocation and expensive operations.
4. **Triangulation changes the declared surface.** The host convex/planar display
   triangulator and this projected polygon triangulator are not interchangeable.
   Admit a qualified polygon class explicitly; preserve triangle order and parent
   maps across solve, display, picking and export. No holes or arbitrary warped/
   self-intersecting polygon acceptance should be inferred from ear clipping.
5. **Local UV validity is insufficient for an overlap claim.** The solve can disable
   orientation rejection; exports independently require positive local orientation.
   There is no global chart-overlap/boundary self-intersection certificate. The
   evaluator rejects queried overlaps only when they disagree on XYZ; it is not an
   exhaustive overlap audit. Keep result scope explicit, and reject empty chart
   requests at admission rather than relying on absence of failed triangles.
6. **Diagnostics adapters are absent.** `UVQuality` triangle IDs are local to the
   selected triangulation, not source polygon or native face IDs. Trace results are
   edge-ID lists without explicit stop-reason/provenance records; the diagnostic
   path contract cannot infer cycle/collision/termination from list length.
7. **Exports do not satisfy host release ownership.** JSON schema
   `mesh-healing-uv/1.0` contains nested arrays, local vertex IDs and parent polygon
   IDs, but no source revision or run/check ledger. Both JSON and STEP writers replace
   existing destinations. Route to per-run artifact paths and record successful
   files in `ReleaseDraft.derived`; do not classify a faceted STEP as native repair.
8. **Translator serialization is local to this module.** Its `_STEP_LOCK` is distinct
   from host `_TRANSLATOR_LOCK` and NURBS `_STEP_LOCK`. Standalone round-trip tests
   do not establish safe mixed-workflow concurrency or global settings restoration.
   Qualify shared coordination or process isolation before exposing concurrent export.

The export supports mm/cm/m/in/ft/um; sewing tolerance uses declared physical units.
NURBS export instead accepts mm/cm/m/in and a tolerance in millimetres. Their defaults
must not be forwarded through one ambiguous tolerance parameter.

### Mesh-healing tests to retain and tests still needed

Retain the supplied tests through any extraction, particularly:

- W symmetry, constant kernel, PSD, negative cotangents, triangulation diagonal,
  scale invariance and affine precision (`tests/test_mesh_healing.py:41–94`).
- Factorization reuse; Woodbury/direct parity; target-only updates; zero confidence,
  disconnected components, stale in-place edits and explicit patch coverage (96–236).
- Actual Euclidean seam tolerance, vertex-only contacts, overlapping-sheet refusal,
  transactional rollback, fan-split provenance, conflicting constraints and concave
  triangulation (238–422).
- Quad-only trace behavior, integer constraints/infeasibility, cross-field transport
  and component gauges (435–516).
- UV/XYZ sidecar correspondence, interpolation and ambiguous overlap, STEP units/
  scale/round trips and end-to-end fixtures (518–end).

Required host tests are additional: immutable input/source retention, stale selected
plans, independent operation selection, identity mapping across edits, bounded
discovery/solve/query work, mixed STEP workflow coordination and partial persistence.
These are absent integration contracts, not claims that the standalone tests failed.

## NURBS bundle: separate evaluation from reconstruction

Paths in this section are relative to `integration/nurbs_core_professionalized/`.

| Module/interface | Actual capability | Proposed disposition |
|---|---|---|
| `NURBSCoreEngine.evaluate_surface` (317–410) | Rational tensor-product points, oriented normals, principal/mean/Gaussian curvature and validity mask over a Cartesian sample grid | Python reference/parity candidate for `native/nurbs`; not a surface fitter or STL reconstruction stage. |
| `find_span_vectorized`, `basis_derivatives_vectorized`, `to_homogeneous` | Closed-domain B-spline basis derivatives and positive homogeneous control points | Preserve analytic/SciPy tests; compare actual numeric conventions with native before any replacement. |
| `STLReader.read` (`STLReader.py:142–212`) | Bounded ASCII/binary parsing, degeneracy policy, exact vertex deduplication and winding-derived normals | Separate STL admission workflow. Never replace restricted polygonal NPZ upload. |
| `PointCloudGeometryEstimator.estimate` (380–500) | Batched KD-tree neighborhoods, local quadratic fitting, oriented curvature and validity/error diagnostics | Read-only approximate feature evidence; invalid fits remain invalid, not planes. |
| `RANSACPrimitiveClassifier.segment` (`NURBSCoreEngine.py:722–773`) | Seeded plane/cylinder extraction with exclusive support and unassigned indices | Separate approximate reconstruction module with explicit physical tolerances and budgets. |
| `CADGeometryCardEngine.compute_cards` (796–907) | Full-precision fit parameters, rounded display fields, source sample IDs and declared bounding approximations | Derived JSON evidence; preserve bounds method and source index space. |
| `STEPGeometryExportEngine.export` (932–1106) | OCP construction of bounded plane/cylinder fragments, validity/transfer checks and STEP serialization | Optional fitted-fragment export after coordination and release integration. No shell/solid repair claim. |
| `main.run_pipeline` (68–143) | STL → features → segmentation → cards → optional STEP; per-file atomic publication | Reference orchestration, not the host controller. Reuse modules and write a host-owned outcome/persistence projection. |

### Current native NURBS blocker and parity contract

The current `native/nurbs/include/cad_mat/nurbs.hpp:102–154` templates
`SurfaceGeometry<Fp>` and declares `evaluate_surface` returning
`SurfaceGeometry<float>`. Its curvature accessors still return `span<const double>`.
`native/nurbs/src/nurbs.cpp:304,340` still uses the unparameterized `SurfaceGeometry`.
A direct C++26 syntax check fails, beginning with “use of class template
'SurfaceGeometry' requires template arguments.” The earlier successful native
baseline does not establish that this checkout builds. No native code was repaired.

Repair and qualify that interface in a separate small change before treating native
as an executable parity reference. Do not silently adopt float curvature storage:
precision, accessors, implementation and tolerances must agree. No Python binding or
accelerator is required to compare numerical fixtures.

The intended overlapping contract is clear enough to prepare fixtures: positive
homogeneous `(x*w,y*w,z*w,w)` control points; closed parameter domains and exact upper
endpoints; repeated-knot convention; u-major Cartesian-product sampling; normals
from `S_u × S_v`; algebraically ordered principal curvatures; singular mask/reject
semantics. Python accepts XYZ controls and promotes unit weights; native takes an
explicit homogeneous flat carrier. Python returns multidimensional writable NumPy
arrays and exceptions; native intends value-owned arrays with typed errors. These
representation differences need an explicit comparison adapter, not a shared name.

### Missing integration work and material conflicts

1. **Total work remains unbounded by the host.** NURBS tiles temporary gathers but
   allocates all requested output arrays (`NURBSCoreEngine.py:350–355`). Batch size
   is not a total grid budget. STL has byte/facet limits, but the downstream KD-tree,
   features, RANSAC support and card arrays need total memory/time/cancellation
   policy. Direct estimator and classifier interfaces accept already materialized
   arrays; a bounded file parser alone cannot qualify the whole workflow.
2. **STL source correspondence is incomplete.** `STLReader.read:190–212` drops
   degenerate facets by default and sorts/deduplicates exact vertices using
   `np.unique`. `MeshData` retains the resulting faces, normals and count report,
   but not retained/dropped original facet IDs or a source-corner-to-vertex mapping.
   Cards' source IDs refer to this deduplicated vertex table, not original STL
   records. Retain original bytes and these maps before exposing source selections.
3. **The pipeline discards useful unresolved evidence.** `segment` returns
   `unassigned_indices`, labels and fit support. `run_pipeline:110–143` keeps only
   the unassigned count/fraction in cards/result, not the index list or full feature
   masks/residuals. A host result should retain that evidence for display/download.
4. **Fit geometry is not recovered topology.** Plane convex hulls can bridge holes,
   concavities and disconnected support. Cylinder sampled angular/axial envelopes
   are not original trim boundaries or full-cylinder proof. The legacy
   `cylinder_fillet` tag does not prove a fillet. Unassigned areas are not converted
   to freeform NURBS patches. Keep these outputs in a distinct approximation workflow.
5. **Units affect several different quantities.** Spatial tolerance and neighborhood
   radius use input length units; curvature thresholds use inverse length; STEP
   tolerance is in millimetres. Units are not supplied by STL. Require one explicit
   input declaration and dimension-aware policy rather than copying defaults across
   models/scales. JSON may allow `unspecified`; STEP correctly rejects it.
6. **Payloads are not diagnostics documents.** Cards use `schema_version: "1.0"`,
   `operations`, `source_point_indices`, parameters, bounds method and fit diagnostics.
   Features contain NaN/Inf for invalid values; JSON rejects them. Projection must
   keep execution/validity state while serializing unavailable values safely. Sample
   IDs are not triangle IDs; no direct card-to-mesh selection adapter exists.
7. **Persistence lacks the host outcome inventory.** `run_pipeline` renders both
   outputs first, then publishes JSON and STEP separately. If the latter publication
   fails, JSON can remain but the function raises without returning a `PipelineResult`.
   That behavior is documented and tested as standalone output safety, but the host
   requires `incomplete` and an honest retained-file inventory. Use `ReleaseDraft` and
   preserve source before processing. Do not make the two-file transaction claim.
8. **Export qualification differs from mesh healing.** NURBS constructs valid faces
   and checks writer status, but its exporter does not reimport on every call; its
   tests perform round trips. Mesh healing reimports before publishing each export.
   Choose the host acceptance contract explicitly. Its local lock and setting restore
   cover only its own exports, not host/CadQuery calls in another module.
9. **Packaging is standalone.** Top-level modules `NURBSCoreEngine`, `STLReader`,
   `main` and the CLI are intentionally separate. Copying imports into Gradio risks
   loose-module naming collisions and mixes orchestration with projection. Establish
   a namespaced module seam when adopting a capability; preserve originals/archive.

### NURBS tests to retain and tests still needed

- `tests/test_nurbs.py`: SciPy basis oracle, repeated knots/endpoints and invalid
  inputs; planes across scale/tile sizes; exact rational quarter-cylinder; singular
  masks/weights; empty grids; polynomial fundamental forms and large translations.
- `tests/test_features.py`: plane/sphere curvature, normal reversal/order, invalid
  clouds, radius/RMSE gates and bounded neighbor-query batches.
- `tests/test_ransac.py`: invalid/sign-invariant classification, insufficient-support
  mask lengths, seeded refits without global RNG mutation, rotated cylinders with
  mixed normal signs, multiple planes/radii and exclusive support.
- `tests/test_stl_reader.py`: binary headers beginning with `solid`, ASCII multisolid,
  malformed/truncated/trailing data, nonfinite coordinates, degeneracy policy and
  preallocation size limits.
- `tests/test_cards_export.py`, `test_step_roundtrip.py`: precision, cylinder angular
  seam, projected bounds, invalid indices/units, no-NaN JSON, atomic no-clobber and
  concurrent publication, schema/settings restoration, unit scale and real CAD faces.
- `tests/test_pipeline.py`: no import-time processing, missing-unit/CLI failures,
  output-path protection, JSON and STEP end-to-end behavior.

Add host tests for source facet/vertex provenance, actual unassigned selections,
dimension-aware tolerances, total resource envelopes, mixed-translator concurrency,
source staging and partial publication, and native/Python analytic parity. Existing
same-module STEP tests and concurrent file-publication tests do not cover mixed
exporter concurrency. No representative noisy scan qualification was established.

## Proposed order for material changes

1. **Diagnostic contract and package:** resolve the already identified identity,
   status, payload budget and renderer ownership questions. The restored archive is
   source material, not an instruction to install its independent dependency graph.
2. **Read-only surface admission:** retain source bytes, units, declared polygons/
   triangulation and IDs; produce host checks and candidate seam evidence without
   calling `preprocess`. This is the first mesh-healing integration slice.
3. **Selected operations and chart solve:** source-bound plans, explicit edit policy,
   retained maps, cotangent solve diagnostics and scoped UV validity. Add derived
   exports only after translator coordination and release accounting are qualified.
4. **Independent NURBS qualification:** fix the native interface/build mismatch and
   run shared analytic parity fixtures. This need not delay diagnostics or surface
   admission; no accelerator or binding work is justified by this review.
5. **Optional STL reconstruction:** only as its own bounded workflow, beginning with
   source mappings and read-only feature/fit evidence. Later add approximate fragment
   exports. Defer advanced cross-field/IGM work until its domain contracts exist.

Common engineering results remain host-owned. `WorkbenchOutcome`, `CheckResult`,
`ReleaseDraft` and `ArtifactStore` can carry outcomes/files, but their existence is
not an implemented surface/STL controller. The host empty/NOT_RUN aggregation issue
in `workbench_results.py:33–39` also remains a prerequisite for honest new checks.

This review does not authorize bulk copying modules into the app, changing native
repair defaults, deleting provenance, or adopting Solid application infrastructure.
