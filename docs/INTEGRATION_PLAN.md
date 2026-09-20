# Integration assessment and proposed delivery plan

Status: initial source review and targeted local verification; implementation not started.
Baseline: working tree at `eee81ff`, inspected September 19–20, 2026. The tree contains
substantial staged, unstaged, and untracked work. This assessment includes the current
Gradio changes and local display packages, not just committed HEAD.

## Recommendation

Integrate by capability, with one authority for each engineering result and one
renderer owning each viewport. First reconcile the deliveries and qualify their
packaging. Then integrate read-only diagnostic presentation. Add surface processing
through explicit controllers after its geometry, policy, and persistence contracts
are qualified. Keep native STEP repair, polygonal repair, derived UV/faceted surfaces,
and approximate STL reconstruction distinct.

Do not bulk-copy these bundles into the app. Do not delete archives merely because
their names resemble extracted directories. This plan does not authorize or perform
source deletion, application changes, dependency updates, or commits.

## Inventory and disposition

| Material | Useful capability | Proposed disposition |
|---|---|---|
| `integration/solid-cad-viewer` | Revision-scoped display documents, assemblies, picking, clipping, source adapters, Three.js renderer | Exclude Solid UI/query/Nitro application integration; retain framework-independent code as optional reference or selective reuse, subject to demonstrated need |
| `integration/mesh-diagnostics-seam` | Diagnostic payloads, host-report adapters, metric targets, overlays, scalar presentation | Reconcile divergent deliveries; port contracts/tests and diagnostic layers; avoid adopting a second complete viewport |
| `integration/mesh_healing_extension` | Cotangent assembly, harmonic systems, explicit seam operations, UV validation/interpolation, quad-strip tracing, derived STEP export | Extract coherent surface-workflow modules in stages; retain numerical regression tests; keep broad preprocessing out of existing repair defaults |
| `integration/nurbs_core_professionalized` | Python NURBS evaluator, bounded STL reader, local features, plane/cylinder extraction, geometry cards | Keep evaluator as a reference/parity candidate for native NURBS; qualify STL reconstruction as a separate approximate workflow; block STEP integration pending local crash diagnosis |
| `components/topological_delta_audit`, `components/verification_grid` | Existing Gradio display packages already used by the dirty app | Reuse their packaging experience and existing display responsibilities; decide ownership of overlapping metric panels |
| `src/cad_integrity/mesh_motorcycle.py` | Unused prototype helper | Exclude from integration; replace with qualified trace-result projection only if needed |
| `reference/archive-delete`, bundle `originals/`, generated examples | Historical originals and evidence | Preserve provenance; not runtime dependencies or proof of current qualification |

## Deduplication findings

Archive comparisons read members without extracting or executing them. After stripping
the archive root directory, every file member matches its extracted counterpart at
the same relative path for mesh healing (19/19), NURBS (24/24), and the general viewer
(39/39). Supplied checksum manifests also match: mesh healing 18/18, NURBS 23/23.
These archives are redundant runtime material but useful provenance snapshots.
Choose one archival location after recording archive hashes and canonical source paths.

The diagnostics archive is a different delivery. Of its 50 file members, only five
have a same-basename byte match in the loose tree; it contains a `mesh_diagnostics`
package and structured frontend while loose files expect `cad_mesh_inspector` and
different contracts. Do a path-aware semantic comparison before choosing a base;
neither delivery can be discarded on the evidence collected here.

Behavioral overlap requires more care than byte deduplication:

| Overlap | Authority and consolidation rule |
|---|---|
| Mesh topology and quality in host, diagnostics, and healing | Existing host audit remains authoritative for existing workflows. Compare definitions, tolerances, units, admissible cells, and source indexing before porting improvements or deleting alternatives. Internal surface-solver checks may remain scoped preconditions. |
| Aspect metrics | Host uses longest-edge / `(2 sqrt(3) inradius)`; diagnostics also offers circumradius / `(2 inradius)`. These are different quantities; preserve explicit names and independent reference tests. |
| Three.js scenes, cameras, picking, clipping, normalization, disposal | Start with the reconciled Svelte diagnostics display. Compare framework-independent viewer algorithms only where they fill an identified gap; choose one camera/resource lifecycle. |
| Python/native NURBS evaluation | Compare `native/nurbs` and Python evaluator using shared analytic/parity fixtures. Two languages are not evidence that either implementation should be deleted. No Python binding is established by this review. |
| STEP export in host and two bundles | Share process-global translator coordination where appropriate, while retaining different construction and acceptance policies for repaired native shapes, faceted charts, and fitted fragments. |
| Verification and metric panels | Preserve the host check ledger; diagnostics panels add geometry selection and quantitative fields. Do not independently compute competing overall verdicts. |

## Confirmed gaps and conflicts

1. **Diagnostics loose delivery is incomplete as packaged.** `pyproject.toml` expects
   `python/` and `tests/`; TypeScript configs expect `src/core` and `src/render`;
   `index.html` references `/src/main.ts`. These layouts are absent. `__init__.py`
   imports missing `npz_io.py`. `Demo.svelte` imports missing
   `components/MeshInspector.svelte`; relative imports still target an earlier tree.
   Collection currently fails with five package-import errors. Moving files alone
   cannot recover every missing module.
2. **Diagnostics frontend/backend contracts disagree.** Loose `Index.svelte` expects
   `{vertices, faces, error_edges, metrics}`; `gradio_component.py` produces
   `{schema_version, meshes, linked_views}`. It is not a working frontend for that
   backend. The supplied verification document describes paths and checks that cannot
   be reproduced from this loose delivery as-is.
3. **NURBS STEP export crashes locally.** Running the supplied suite from its own
   directory exits 139 during `test_schema_roundtrip_and_setting_restoration`, with
   the top Python frame at `NURBSCoreEngine.py:1085`. Earlier Linux validation is
   provenance, not evidence that this local OCP runtime works. Root cause is unresolved;
   isolate reproduction before deciding whether code, schema settings, or runtime
   compatibility is responsible. Do not expose it in the Gradio process yet.
4. **Mesh-healing STEP path is unqualified here.** CadQuery is absent although OCP is
   available for the host. Six supplied STEP tests skip. Decide whether to keep the
   added CadQuery dependency or implement a separately tested OCP adapter.
5. **Frontend qualification is incomplete.** The viewer's delivery report explicitly
   excludes full dependency-aware typechecking, build, browser/GPU checks and actual
   STEP ingestion. Diagnostics has similar exclusions. Supplied frontend projects
   have no lockfiles. Three.js versions differ (`0.180.0` versus `~0.186.0`), as do
   framework/build dependencies. Resolve one tested graph in the actual scaffold.
6. **Preprocessing changes the policy.** `MeshHealingEngine.preprocess` defaults to
   stitching and bow-tie splitting; it also removes faces and reorients. Its seam
   discovery uses geometric heuristics when no pairs are supplied. These are not
   equivalent to the host's bounded admission and configured repair. Present discovery
   read-only first; any later application must use explicit plans and recorded maps.
7. **Admission contracts conflict.** Host upload accepts exactly `vertices`,
   `triangles`, and `length_unit` under byte/count budgets with pickle disabled.
   Viewer defaults use `positions`, `triangles`, and caller-declared units; STL reader
   merges exact vertices and drops degenerates by default. Rendering and reconstruction
   adapters must not silently replace the authoritative upload path or source identity.
8. **Independent translator locks do not coordinate.** Host `_TRANSLATOR_LOCK` and
   each bundle's `_STEP_LOCK` are distinct objects. Cross-workflow calls can therefore
   overlap process-global OCCT settings despite each module's internal serialization.
   Qualify shared coordination or process isolation before concurrent export.
9. **Motorcycle helper is not an implementation to reuse.** Static inspection finds
   `allow_pickle=True`, undefined `_gen_synthetic_mpaths`, `.toList()` calls,
   float-cast triangle indices, discarded processed paths, and arbitrary pass/fail
   thresholds. No caller was found in the searched Python/Svelte/TypeScript tree.
   Synthetic traces must remain clearly labeled fixtures, never engineering results.
10. **Verification summaries need an explicit empty/unchecked rule.** Current
    `verification_summary` returns `Passed` when no failed/unavailable check is found,
    including an empty ledger or only `NOT_RUN` checks. Before adding diagnostics,
    define aggregation so missing evidence cannot become success. The incoming
    `pass/fail/warn/info/not_checked` states cannot be losslessly collapsed into a
    boolean; preserve severity and execution state separately where needed.

The mesh bundle's IGM routine solves supplied integer length constraints; its
cross-field routine is a relaxed smoother; its motorcycle tracer follows pure-quad
strips. These do not establish a general triangle-mesh motorcycle algorithm or a
complete seamless parameterization pipeline. NURBS reconstruction yields bounded
plane/cylinder fragments, with convex-hull/envelope approximations, not recovered
trim topology or a repaired solid.

## Proposed interfaces and integration sequence

The existing public controllers remain `run_step_workbench`, `run_polygonal_fixture`,
and `run_polygonal_upload`. They retain admission, policy, and evidence ownership.
`WorkbenchOutcome`, `DecisionBrief`, and `ReleaseDraft` continue to describe results
and actual retained files. New controller names below are proposals, not implemented
interfaces.

| Slice | Concrete work | Acceptance gate |
|---|---|---|
| 0. Freeze delivery provenance | Capture dirty-tree inputs and hashes; reconcile diagnostics archive/loose files; map originals, canonical files, fixtures, and generated evidence; preserve unrelated work | Every adopted module/test has a known source; no unique content deleted; reproducible package layout |
| 1. Qualify baselines | Repair packaging in an isolated checkout; establish local dependency graph; reproduce NURBS crash in a bounded subprocess; restore all applicable tests and full frontend build | No unexplained required skips, collection errors, or process crashes; reports distinguish pure tests, kernel tests, and browser evidence |
| 2. Diagnostic result seam | Project existing reports into revisioned geometry/diagnostic documents; define status mapping, units, source-stage identity, triangle-to-source maps, bounds and payload budgets | Same host outcomes/checks; stale targets rejected; source/candidate IDs cannot cross; empty/unchecked diagnostics never pass by default |
| 3. Read-only Gradio viewer | Build the reconciled Svelte diagnostics display in the existing Gradio scaffold; selectively reuse framework-independent code only where justified; decide metric-panel ownership; retain Plotly until equivalent behavior is verified | Packaged assets load in real app; picking/clipping/camera behavior, hidden tabs, resize, disposal and context loss tested; source/candidate visibility unchanged |
| 4. Surface admission and seam discovery | Proposed `run_surface_analysis`; immutable admitted carrier, explicit triangulation and provenance; reuse authoritative checks; report candidate seam pairs without mutation | Source bytes retained; bounded work; invalid/ambiguous inputs fail clearly; no candidate repair or derived export implied |
| 5. Selected surface operations and UV charts | Explicit source-revision-bound seam plans; selected edits with before/after maps; cotangent/harmonic module, constraints, residuals, flip/collapse/distortion evidence | Stale plans rejected; numerical reference/invariance tests; undefined or folded UV results withheld from export; separate local validity from global injectivity |
| 6. Derived exports | UV JSON and optional faceted STEP under `release.derived`; explicit UV scale/units; coordinate native translator access; independent persistence accounting | Real kernel round-trip checks; source retained; partial writes yield `incomplete` with honest inventory; derived geometry never appears as native repair candidate |
| 7. Optional reconstruction and advanced geometry | Separate bounded STL workflow and approximate geometry cards; NURBS native/Python parity; quad traces; later field/IGM contracts | Each capability has its own admission, numerical, provenance, and output gates; STEP crash resolved before fitted export; no blanket healing claim |

Slices 0–1 establish the baseline. Slices 2–3 form the first user-visible delivery.
Slices 4–6 form a separate surface workflow. Slice 7 should be split by actual use
case; it need not delay the display integration.

The user questioned the relevance of the SolidJS bundle. The plan therefore starts
with the Svelte diagnostics display and excludes integrating the Solid application.
`CadViewer.tsx`, `ViewerPanel.tsx`, `RemoteCadViewer.tsx`, Solid Query, and the Nitro
example are not prerequisites for the Gradio work.

The useful distinction is implementation dependency: `ThreeCadViewer.ts`,
`RenderModel.ts`, and model/math/selection code do not import Solid. They could be
hosted by Svelte, but that still requires lifecycle, reactive updates, event routing,
coordinate/identity mapping, and Gradio packaging work. The diagnostics and general
viewer contracts also differ. This is feasible reuse, not a drop-in integration.

Prefer selective reuse of tested identity, picking, coordinate precision, or resource
management behavior when it addresses a concrete gap. Only consider adopting the
whole framework-independent renderer if requirements such as assemblies or native
face/edge selection justify its broader interface. Preserve the bundle as reference
pending that decision; do not let it delay the Svelte delivery.

Rendering documents carry immutable snapshot identity, units, original triangle
order, source/candidate/derived role, and explicit semantic mappings. Diagnostics
also carry their own revision for threshold/result changes. Approximate display
coordinates never become engineering outputs. The host's source staging failure
remains `failed` with no release; later artifact failures remain `incomplete` and
retain successfully written files. This preserves locality of evidence and release
rules while giving each geometry module a small, testable interface.

## Local evidence and limitations

Commands used the existing `.pixi/envs/default/bin/python`, without installing or
updating dependencies. Targeted tests do not constitute full repository qualification.

| Check | Current result |
|---|---|
| `tests/test_gradio_app.py` + `tests/test_projection_components.py` | 37 passed |
| Mesh-healing supplied suite | 63 passed, 6 skipped because CadQuery is absent |
| Diagnostics loose Python collection | Five errors: `cad_mesh_inspector` unavailable; missing layout/modules confirmed separately |
| NURBS suite from repository root | Seven import errors due to standalone module layout; rerun from bundle directory |
| NURBS suite from bundle directory | Process crash during STEP schema/settings round-trip; exit 139; no completed suite result |
| General viewer core tests | 47 passed in a temporary copy using the existing verification-grid component TypeScript compiler; initial global shim was broken. This excludes Three.js renderer/browser qualification. |
| NURBS numerical/STL subset | 104 passed across `test_nurbs.py`, `test_features.py`, `test_ransac.py`, `test_stl_reader.py`; does not qualify the crashing STEP path |
| Archive/checksum comparisons | Exact matches for three extracted archives and both manifests; diagnostics is divergent |

No live browser, GPU lifetime, full frontend build, hosted CI, native NURBS build,
performance envelope, or arbitrary-model qualification was established here. Existing
test reports remain attached to their original environments. A complete algorithm
audit, license/provenance inventory for adopted files, and resource-budget testing
remain work in the proposed slices.

## Decisions to settle before implementation

The recommended defaults are: use the reconciled Svelte diagnostics display, with optional selective reuse of framework-independent viewer code; retain the
current admission path; integrate diagnostic presentation first; treat UV/faceted and
STL-fitted outputs as separately named derived artifacts; defer IGM/cross-field UI
until their input contracts exist. Confirm the canonical diagnostics delivery during
provenance reconciliation. Decide CadQuery versus a direct OCP adapter only after
measuring the required export behavior and resolving local kernel compatibility.
