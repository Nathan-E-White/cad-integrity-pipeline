# Polygonal inspection — TDD case catalogue

Status: 141 behavioral acceptance cases; executable coverage and measurements are
tracked separately in [implementation evidence](evidence/polygonal-inspection/IMPLEMENTATION.md).
Based on [the implementation plan](POLYGONAL_INSPECTION_IMPLEMENTATION_PLAN.md),
[domain language](../CONTEXT.md), and [open decisions](OPEN_DESIGN_DECISIONS.md).
See [test contracts](POLYGONAL_INSPECTION_TEST_CONTRACTS.md) for types,
function signatures, executable-test recipes and the automation inventory.

The catalogue covers all six delivery slices. Each row describes an independent
behavioral case: arrange the stated input, perform the action, and observe the
specified result through the seam. Rows are a backlog for successive red → green
cycles, not instructions to write a bulk failing suite. Implementation was separately authorized with the implement skill. The catalogue
is broader than the current executable suite; a case ID is not a claim of a passing test.

## Confirmed implementation seams

| Seam | Public boundary and observation | Placement once confirmed |
| --- | --- | --- |
| S1 Snapshot | Proposed backend-owned inspection value construction/read access; owned geometry, identities, reports, frame, units | New parent Python inspection tests |
| S2 Projection | Proposed pure projection from `RepairResult` to inspection data; consume supplied reports | New parent Python projection tests |
| S3 Triangulation | Proposed per-face display API with emitted provenance and local issues; existing `PolyhedralBRep.triangulate_convex_faces` remains compatible | Parent polygonal geometry tests |
| S4 Adapter/targets | Versioned payload validation and public target resolution/picking; legacy adapter compatibility | Inspector Python adapter and TypeScript contract tests |
| S5 Workspace | Rendered viewport, MetricTable, EntityTable and user controls; public state API only if deliberately exposed | Workspace/browser tests |
| S6 Parent delivery | `run_polygonal_fixture`, `run_polygonal_upload`, `run_step_workbench`, `WorkbenchOutcome`, installed `build_app` routes and session behavior | Parent controller tests plus installed-parent browser tests |
| S7 Qualification | Installed parent on the target machine, measured through browser/platform instrumentation | Separately retained capacity and runtime evidence |

S1–S7 were accepted for implementation. Test public contracts and installed
`build_app` routes rather than private numerical helpers. Session admission
rejects overlapping requests before clearing, across all three parent routes.

## Independent fixtures and oracles

- **G1 Mixed faces:** disconnected triangle, square and convex pentagon, with
  source face IDs 0, 1 and 2. Use triangle coordinates `(0,0,0), (1,0,0), (0,1,0)`;
  square `(3,0,0), (4,0,0), (4,1,0), (3,1,0)`; pentagon
  `(6,0,0), (8,0,0), (9,1,0), (7,3,0), (6,1,0)`.
  Build connectivity explicitly. Expected display counts are 1, 2 and 3;
  expected areas are 0.5, 1 and 5.5. Do not assume triangle ordering or diagonals.
- **G2 Partial display:** a supported face beside each of a concave polygon, a
  nonplanar polygon, and a self-intersecting polygon. Fix coordinates and the
  intended display outcome when the triangulation contract is confirmed. The
  current convex-only path cannot fill these indiscriminately. A later supported
  triangulator may fill a concave face; inability to fill is never itself a defect.
- **G3 Malformed connectivity:** explicit missing edge/vertex references and a
  broken wire beside a valid triangle. Record exactly which points/segments can
  be resolved; do not derive the oracle using the production resolver.
- **G4 Degenerate/coincident:** two distinct coincident faces, an unused vertex,
  an unused edge, and a collapsed edge. Keep distinct source IDs. Use separate
  minimal fixtures where combining defects would obscure the expected report.
- **R1 Supplied report:** explicit category ID sets. For example, boundary edges
  `{0,2}`, winding conflicts `{2}`, unused edges `{7}` give category counts 2, 1,
  1 and three unique affected edges. Edge 2 retains both memberships. Construct
  a compatible raw carrier; this is a projection fixture, not analyzer evidence.
- **R2 Two revisions:** Original and Candidate both contain entity index 0 but
  have distinct stage/revision namespaces. Include identical geometry and a
  separate changed-geometry example. Archive-byte hash and geometry revision
  remain distinct concepts; the exact revision algorithm is not prescribed.
- **P1 Release outcomes:** real small saved-example and restricted NPZ inputs for
  accepted, needs-review, refused, failed-source-stage and late-write-failure
  outcomes. Reuse the existing controller fixtures and temporary artifact stores.
- **B1 Browser comparison:** backend-produced small payload containing G1 and G4,
  a pane with an empty category, and an intentionally occluded defect. Use this
  for selection, camera, clipping, X-ray and table evidence.
- **C1 Capacity corpus:** accepted inputs at 250,000 vertices and 500,000 source
  triangles, plus admissible dense-diagnostic and two-pane workloads. Respect
  source-byte, expansion, topology and computation budgets too. A large synthetic
  frontend payload alone cannot establish parent admission or integration.

Expected IDs, category sets, simple areas, and release inventories must be literal
fixture facts or separately worked examples. Never compute the expected report
by invoking the analyzer under test. Backend-generated wire fixtures must still
be checked against independent expected identities and counts in the browser.

## Slice 1 — inspection model and additive outcome (S1, S6)

| ID | Given / action | Expected observable result |
| --- | --- | --- |
| M01 | Construct a snapshot from owned geometry and read every entity | Coordinates, connectivity, IDs, categories and mappings are available without backend retrieval |
| M02 | Mutate the caller's original vertex array after snapshot construction | Snapshot coordinates remain unchanged |
| M03 | Mutate caller-owned edge, face and triangle arrays after construction | Snapshot connectivity and display mapping remain unchanged |
| M04 | Mutate caller-owned category lists, issue lists and nested metadata | Snapshot memberships, issues and frame/unit metadata remain unchanged |
| M05 | Attempt mutation through each public snapshot collection or array access | Mutation is rejected or affects only a detached copy; subsequent reads are unchanged |
| M06 | Attempt to re-enable array writes through a publicly returned alias | No writable alias can change snapshot-owned data |
| M07 | Construct Original and Candidate with identical coordinates and IDs | Targets remain stage/revision-specific; identical geometry does not merge identities |
| M08 | Replace a result with a new geometry revision, retaining an old target | Old target does not resolve against the new revision |
| M09 | Project each currently supported input unit and a non-origin coordinate frame | Exact declared units/frame and coordinates survive without implicit conversion |
| M10 | Supply a source archive hash as provenance | It remains distinguishable from geometry revision; no target is resolved merely by archive hash |
| M11 | Construct an existing `WorkbenchOutcome` without inspection data | Existing construction and result fields remain usable; optional inspection is empty |
| M12 | Exercise completed, incomplete and failed controller result paths | Inspection is optional; completion, checks, diagnostics and actual release inventory remain coherent |
| M13 | Run the STEP controller after adding inspection to the outcome | Inspection stays empty; STEP checks, figures and downloads retain existing behavior |
| M14 | Change browser camera/filter/selection against a snapshot | Snapshot geometry, reports and revision are unchanged |

## Slice 2 — projection and partial display (S2, S3)

Run P01 separately for all nine categories: nonmanifold vertices, unused vertices,
boundary edges, nonmanifold edges, winding conflicts, unused edges, collapsed
edges, invalid faces and duplicate faces. The count is nine, across three entity kinds.

| ID | Given / action | Expected observable result |
| --- | --- | --- |
| P01 | Project a supplied report containing known IDs in one category | Exact entity kind, IDs and count survive; no category is silently omitted |
| P02 | Project R1 with edge 2 in two categories | Both memberships remain; combined highlighting counts three unique edges |
| P03 | Give a vertex, edge and face the same numeric ID | Combined selection retains three distinct entities, deduplicating only full entity identities |
| P04 | Project Original and Candidate reports with different category counts | Each pane receives its own supplied counts and memberships |
| P05 | Project zero memberships in a reported category | Category has count zero and no invented targets |
| P06 | Project an available original without a candidate | Original is complete; candidate is absent, not copied from Original |
| P07 | Project an in-memory needs-review candidate | Projection preserves its inspectable data; publication/exposure is decided separately |
| P08 | Project the same input twice | Equivalent geometry, memberships, mappings and issues; source arrays/reports unchanged |
| P09 | Project supplied reports whose independent fixture facts differ from a fresh audit | Output follows supplied facts; projection does not substitute recomputed analysis |
| P10 | Project in a process without artifact destinations or backend services | Projection completes from supplied values; no files or backend selection requests are needed |
| P11 | Inspect G1's emitted triangles and emitted source-face map | Counts per face are 1, 2, 3; every triangle maps to its actual owning source face |
| P12 | Verify G1 display geometry against its worked areas and boundaries | Per-face areas are 0.5, 1, 5.5; triangles stay within their source faces and cover them |
| P13 | Reverse one G1 face's orientation and triangulate | Face identity survives; emitted triangle winding reflects the input orientation |
| P14 | Rotate a face's starting vertex without changing its boundary | Face identity and coverage survive; no expected triangle-order assertion |
| P15 | Place an unsupported face before, between and after supported faces | Supported neighbors still render; source IDs do not shift to fill gaps |
| P16 | Triangulate a currently unsupported concave face beside a valid triangle | Triangle remains filled; unsupported interior is unfilled with resolvable boundary and a display issue |
| P17 | Triangulate a nonplanar face beside a valid triangle | Local failure does not erase the neighbor or manufacture a replacement planar surface |
| P18 | Triangulate a self-intersecting face beside a valid triangle | Unsupported interior remains unfilled; source entity and reported classification remain inspectable |
| P19 | Project G3 with invalid references | Only independently resolvable geometry is shown; no fabricated closing segment; unresolved data has an issue |
| P20 | Project a face with no resolvable display points | Face ID and reported category remain in the table, with explicit display unavailability |
| P21 | Project a collapsed edge with coincident endpoints | Distinct selectable edge target remains; source coordinates are unchanged |
| P22 | Project unused vertices and unused edges | They remain individually addressable even though no rendered face uses them |
| P23 | Project coincident duplicate faces | Both source IDs remain addressable; one face is not deduplicated out of inspection |
| P24 | Produce a display issue for a supplied defect-free face | Topology counts and verification states remain unchanged; issue is separately represented |
| P25 | Call the existing convex-face triangulation interface on its supported fixtures | Existing return contract and numerical coverage remain compatible |
| P26 | Call the legacy triangulator on its existing unsupported fixtures | Preserve documented legacy failure semantics; partial success belongs to the new seam |
| P27 | Supply geometry/payload counts exactly at each agreed allocation limit | Accepted data remains complete, with no entity truncation |
| P28 | Supply counts just beyond each limit or beyond representable indexing | Explicit bounded failure before a flattened-copy memory spike; no wrapped indices or partial success claim |
| P29 | Expand polygonal faces into more display triangles than source-face count | Preflight accounts for display geometry and mapping sizes, not just input face count |
| P30 | Project data with no available homology result | Existing unavailable/not-run evidence remains such; display success does not invent homology |

P09 is a supplied-data contract test, not an internal analyzer-call-count test.
P10 can use OS/filesystem boundary tracing or a constrained subprocess. P28 needs
an agreed count/preflight API and a bounded process memory measurement, not a
deliberate host OOM. Architectural dependency checks supplement these cases; they
do not replace behavioral evidence or require mocks of internal collaborators.

## Slice 3 — wire adapter and rendering targets (S4)

| ID | Given / action | Expected observable result |
| --- | --- | --- |
| A01 | Serialize a backend-produced G1/R1 snapshot and validate in the frontend | Version, geometry, units, memberships and identities agree with fixture literals |
| A02 | Deliver an unsupported wire version | Explicit unsupported-version result; no silent reinterpretation as legacy triangles |
| A03 | Deliver truncated geometry, bad mapping indices or malformed identity fields | Payload is rejected explicitly; no partially trusted entity targets |
| A04 | Resolve a valid vertex target | Exactly that revision's vertex is selected |
| A05 | Resolve a valid edge target | Exactly that revision's edge and its resolvable representation are selected |
| A06 | Pick each display triangle of G1's square and pentagon | Each pick selects its source polygonal face and emphasizes all of that face's triangles |
| A07 | Resolve a boundary-only face target from the table | Source face is selected despite having no filled display triangles |
| A08 | Resolve a collapsed edge or a coincident duplicate face by ID | Requested entity remains distinct and addressable |
| A09 | Resolve a target with the wrong mesh, revision, kind or nonexistent ID | Target does not resolve; it is never redirected to a numerically equal entity |
| A10 | Pass an existing v1 triangle target through its compatibility interface | It retains triangle semantics; it is not silently relabeled a source-face target |
| A11 | Resolve a category containing overlapping memberships | Every intended entity is highlighted once while category counts remain separate |
| A12 | Read adapter output after plotting fields or artifact paths are unavailable | Snapshot data suffices; geometry/provenance are not recovered from Plotly or NPZ |
| A13 | Load old supported package clients through compatibility adapters | Existing public contract fixtures still pass with their original meanings |
| A14 | Exercise the error overlay while replacing and disposing a viewport | Overlay participates in the viewport resource lifecycle; no duplicate scene/canvas or orphan resources |

The dedicated overlay module and one-renderer-owner rule also require code review
of ownership/dependencies. Avoid turning module filenames or constructor call
counts into behavioral acceptance assertions.

## Slice 4 — browser workspace (S5)

Use real browser input and observable rows, labels, selection emphasis and camera
behavior. Screenshots complement identity assertions; a glowing pixel alone does
not establish which source entity was selected.

| ID | Given / action | Expected observable result |
| --- | --- | --- |
| W01 | Load a comparison result | Two side-by-side panes; Original initially active; tables explicitly identify Original |
| W02 | Load a result without Candidate | Candidate pane is vacant; Original width is unchanged; no automatic maximize |
| W03 | Explicitly maximize either available viewport, then restore | Chosen viewport expands; comparison layout restores with its inspection state intact |
| W04 | Click Candidate's viewport, then Original's | Shared entity and metric tables follow the active mesh and label it correctly |
| W05 | Orbit, pan and zoom one comparison camera | Other camera remains linked in the common frame |
| W06 | Select or hover a row | Neither camera moves automatically |
| W07 | Invoke Focus selection for a visible face | Camera frames the selected geometry only as an explicit action |
| W08 | Focus a collapsed edge or a boundary-only face | Camera remains finite and usable; resolvable selected geometry can be inspected |
| W09 | Adjust clipping in either pane with default settings | Corresponding clipping is linked in the common frame |
| W10 | Unlink clipping and adjust one pane, then relink | Unlinked change remains local; relinking follows a documented synchronization rule |
| W11 | Clip a selected defect entirely out of view | Rows/counts and pinned selection remain; clipping planes are not moved by selection |
| W12 | Select an obscured defect with normal depth visibility | Overlay respects depth; selection remains identified by the table |
| W13 | Enable X-ray for the same obscured defect, then disable it | Overlay becomes inspectable through occluders, then returns to normal depth behavior |
| W14 | Load a report containing all nine categories | All category overlays start visible at restrained intensity; selected item/category receives emphasis |
| W15 | Hide a category overlay | Overlay clutter reduces; category and metric counts do not change |
| W16 | Load a result and inspect the entity table | Defects only is enabled initially |
| W17 | Disable Defects only and navigate all entity kinds | Healthy and defective vertices, edges and faces are all reachable |
| W18 | Choose Vertex, Edge and Face picking modes in turn | Subsequent viewport picks use the explicit mode in both panes |
| W19 | Change picking mode with a pinned selection | Existing selection is preserved |
| W20 | Use the table to select a face while viewport mode is Vertex | Face is selected; table selection is not restricted by picking mode |
| W21 | Select entity A, then entity B in the same pane | B replaces A; no unintended multi-selection |
| W22 | Select a category after an entity, then an entity after a category | One whole category or one individual entity occupies the pane's selection |
| W23 | Pin different selections in Original and Candidate and switch panes | Both selections persist independently; equal indices do not synchronize them |
| W24 | Choose a category and switch to a pane where its count is zero | Category filter persists; count is zero; no fallback to another category |
| W25 | Filter out the selected entity | Selection persists with muted emphasis and a pinned row above the filtered table |
| W26 | Clear the pinned selected-entity row | That pane's selection clears; the other pane's selection remains |
| W27 | Hover B while A is pinned, then leave the row | B previews temporarily; leaving restores A |
| W28 | Click B during its hover preview | B replaces A as the pinned selection |
| W29 | Hover and leave a row with no pinned selection | Preview disappears; no entity becomes pinned implicitly |
| W30 | Select each coincident face and collapsed edge through the table | Every reported entity is individually selectable despite ambiguous viewport positions |
| W31 | Scroll/page a large entity table to its last entity, then select it | Last entity remains reachable and selects correctly; virtualization is not a permanent cap |
| W32 | Change filter/mode while hovering another row | Temporary hover cannot overwrite pinned selection or leave a stale highlighted entity |
| W33 | Perform hover, selection, camera, clipping and filter changes with network tracing | No Gradio computation/selection callback or numerical recomputation is triggered |
| W34 | Repeat hover/selection with a moved camera and clipping planes | Geometry uploads remain stable; camera, clipping and viewport state do not reset |
| W35 | Read metric/entity fields and captions | Names, values, units, statuses and IDs are present; explanatory prose is in evidence/metadata |
| W36 | Load an actual unavailable/error result | Unavailability is explicit; it is not shown as zero defects or a successful empty mesh |

W10 needs the relink synchronization rule specified before its executable oracle
is finalized. W07/W08 need observable focus behavior, not a fixed camera algorithm.
W14 needs visual review of emphasis; do not invent numeric glow thresholds.

## Slice 5 — parent delivery, release and admission (S6)

Use the actual installed component assets for browser cases. Controller tests can
use real small inputs and temporary directories. Inject file-write failures only
at the filesystem/system boundary, not by mocking the internal release pipeline.

| ID | Given / action | Expected observable result |
| --- | --- | --- |
| I01 | Run a saved example through the installed parent | Its controller snapshot reaches the workspace with correct geometry and diagnostic IDs |
| I02 | Run an admitted restricted NPZ through the installed parent | Upload snapshot reaches the same workspace contract with units and source provenance retained |
| I03 | Run equivalent example/upload geometry | Both routes provide consistent inspection semantics without merging their source provenance |
| I04 | Run a case with known Before / After / Δ and verification values | Existing Delta Audit and Verification Grid retain those exact values/states |
| I05 | Complete a run with retained source, candidate and evidence | Download controls contain usable string paths to exactly the retained files |
| I06 | Produce a coherent candidate needing review | Failed check remains visible; candidate is not hidden solely because a check failed |
| I07 | Refuse repair and produce no candidate | Original/evidence remain as allowed; no invented candidate inspection or download |
| I08 | Fail source staging for either polygonal route | Failed outcome with no release; no claimed retained source or candidate |
| I09 | Fail a later evidence write after source retention | Incomplete outcome preserves source and every already-retained file |
| I10 | Fail JSON after Markdown was retained | Markdown remains available; failed JSON is absent from retained inventory |
| I11 | Fail evidence persistence after candidate was retained | Candidate download and permissible inspection remain available; later failure does not undo retained files |
| I12 | Fail candidate-file persistence after computing a candidate | Common invariant: incomplete release has no candidate download; runtime candidate remains inspectable under D-001 |
| I13 | With old results visible, admit a new computation and hold it at a deterministic execution barrier | Geometry, overlays, rows, reporting values, selections and download references clear before completion |
| I14 | Admit a replacement run, then fail it | Old results do not return; current error state is explicit |
| I15 | Clear displayed results at admitted start | Previously retained files still exist until ordinary retention cleanup; clearing does not delete them |
| I16 | Start a computation while the session is idle | Computation-start controls are disabled while the admitted run is active |
| I17 | Bypass disabled UI controls and submit an overlapping request in the same session | Request admission still enforces one active computation |
| I18 | Submit a duplicate while a run is active | A non-admitted request does not clear/change active-run state; exact response follows the agreed duplicate policy |
| I19 | Switch from examples to uploads or STEP while a run is active and attempt a start | Same-session guard applies across workflows and tabs |
| I20 | Finish a run successfully, then submit another | Guard and controls are released; next request can be admitted |
| I21 | Fail an admitted run during execution, then submit another | Guard and controls recover on failure; no permanently busy session |
| I22 | Fail admitted source staging or result delivery, then retry | Failure paths also release admission; prior displayed result is not resurrected |
| I23 | Submit requests from two independent browser sessions | Session admission does not impose a global single-run lock; broader resource scheduling is not qualified here |
| I24 | Submit two starts at the same admission barrier | At most one is admitted in that session; no timing-dependent double start |
| I25 | Load the installed parent without source-path injection | Packaged workspace assets load and execute; standalone Vite success is insufficient |
| I26 | Run STEP after polygonal integration | Existing STEP display/numerics and release behavior remain compatible; only shared admission behavior changes |
| I27 | Submit a malformed/oversized NPZ | Existing restricted admission policy remains enforced; no broadened format support or lowered limits |
| I28 | Fail frontend initialization after a valid controller result | Explicit display error; completion/checks and retained download facts are not rewritten as numerical failure |

Use deterministic barriers at a declared execution/system boundary for I13 and
I17–I24, rather than sleeps or internal collaborator mocks. The distinction between
an invalid request and a newly admitted run needs an explicit admission contract;
do not assume every button press must clear a result.

### D-001 decision — in-memory inspection selected

| ID | If this option is selected | Acceptance case to finalize |
| --- | --- | --- |
| D01 | Suppress candidate inspection on candidate-write failure | I12 leaves Candidate vacant and provides no candidate target, selection or download; Original remains available |
| D02 | Permit in-memory candidate inspection on candidate-write failure | I12 exposes the computed candidate with inspection availability separate from absent download availability and incomplete release |
| D03 | In-memory inspection is chosen | Session loss/expiry behavior follows the newly recorded lifetime decision; no promise of reopenable retained snapshots |

D02 is selected; D01 is superseded. D03 uses runtime lifetime: a new admitted run
or page reload clears the snapshot. Retained snapshot export/reopen is deferred.

## Slice 6 — capacity, stability and switch gate (S7)

Before execution, record machine/OS, browser/GPU, package versions, input hashes,
admission budgets, workload sizes, warm/cold conditions, repetition count, and
agreed thresholds for payload bytes, peak CPU/GPU memory where measurable,
load/update latency, interaction latency/frame behavior, and retained-resource
growth. Report unsupported measurements explicitly. No timing number is agreed
by the plan, so this catalogue invents none.

| ID | Workload / action | Required observation |
| --- | --- | --- |
| Q01 | Load admitted input at the 250,000-vertex boundary | Complete entity reachability and recorded resource/interaction measurements within agreed bounds |
| Q02 | Load admitted input at the 500,000-triangle boundary | Full display/inspection succeeds; no old 250,000-triangle display cutoff |
| Q03 | Load an admitted workload exercising both maximum input counts | Combined payload/geometry behavior is measured, not inferred from two isolated runs |
| Q04 | Display Original and Candidate simultaneously at demanding admitted sizes | Aggregate resource use and both panes' interaction satisfy agreed bounds |
| Q05 | Use dense memberships across all defect categories | Counts remain exact; overlaps are deduplicated for highlighting; tables/picking remain usable |
| Q06 | Select first, middle and last entities of every kind in a large table | No permanent cap, dropped entities or diagnostic-identity decimation |
| Q07 | Replace results repeatedly using the agreed repetition count | Resource growth stabilizes within agreed bounds; stale geometry, IDs and selections do not survive replacement |
| Q08 | Repeatedly resize and maximize/restore during inspection | Layout, camera, clipping, selection and picking remain correct; resources stay bounded |
| Q09 | Lose and restore the WebGL context | Explicit unavailable state while lost; recovery restores usable inspection without corrupting the snapshot |
| Q10 | Fail WebGL initialization | Explicit display error and usable reporting/download controls; no stuck admission guard |
| Q11 | Mount/dispose viewports repeatedly or leave the workspace | Owned GPU/browser resources are released within measured bounds; no residual canvases or duplicate interaction handlers |
| Q12 | Hover/select rapidly over a large mesh | No geometry reconstruction/upload churn or camera/clipping reset; measure interaction behavior separately from load time |
| Q13 | Change filters and clipping on dense diagnostics | Counts and selection stay correct, with measurements inside agreed interaction limits |
| Q14 | Exercise the legacy and proposed display on the same accepted corpus before switching | Existing path remains available until coverage and capacity gates pass |
| Q15 | Deliberately fail a capacity/coverage gate | Switch is withheld; no reduced upload limit, silent truncation, diagnostic decimation or success claim |
| Q16 | Complete qualification and switch polygonal display | Installed-parent examples/uploads pass; STEP regression evidence is reported separately |

Use browser/GPU instrumentation at the platform boundary for geometry uploads,
context loss and disposal. A source-code search, increased limit constant, tiny
fixture or mocked browser is not evidence for Q01–Q13.

## Existing coverage and migration discipline

These files provide starting points, not proof that the proposed cases pass:

| Existing coverage | Reuse / extend |
| --- | --- |
| `tests/test_polygonal_cell_admission.py` | Collapsed/unused entities, pinched vertices, invalid faces, orientation and admission facts; retain numerical assertions independently of display |
| `tests/test_topology_repair.py`, `tests/test_repair_policy_propagation.py` | Existing repair/policy invariants; inspection must not change computation |
| `tests/test_gradio_app.py` | Both polygonal entry paths, needs-review candidate publication, source staging, partial persistence, restricted upload and STEP behavior |
| `tests/test_workbench_results.py`, `tests/test_projection_components.py` | Shared verification ledger, report projections and result compatibility |
| `integration/mesh-diagnostics-seam/tests/source-face-ids.test.mjs` | Existing source identity tests; extend using backend-produced mixed polygon fixtures |
| `integration/mesh-diagnostics-seam/tests/document.test.mjs` | Existing document/target contracts; preserve v1 meaning through compatibility coverage |
| Inspector browser and Gradio-browser suites | Useful renderer integration evidence; add installed-parent flows rather than relying only on standalone demonstrations |

Existing tests may assert renderer-specific layout or figure details that migration
changes. Replace only the obsolete presentation assertion with its agreed behavior
case; retain underlying numerical, release, identity and admission assertions.
Do not rewrite old tests wholesale merely to make a new renderer green.

## Suggested red → green progression

1. Confirm S1–S7 responsibilities and the first concrete public signatures.
2. Start with M11 (additive outcome compatibility), then M02 (owned coordinates).
   Finish each red → green cycle before starting the next.
3. Use one P01 category as the first projection tracer; extend categories and
   overlapping membership only after it passes.
4. Implement P11 source-face provenance, then P15 local display failure, each
   through the agreed triangulation/projection boundaries.
5. Carry that small backend result through A01 and I01 into the installed parent.
   This establishes a vertical path before expanding the workspace behaviors.
6. Grow picking, table selection and the W-series one behavior at a time. Add
   upload delivery and release cases through the same public pipeline.
7. Implement admitted-start clearing and deterministic session exclusion before
   claiming lifecycle integration. Resolve D-001 before its visibility slice.
8. Agree performance thresholds, run the Q-series, and switch only after evidence
   supports the full admission range. Update integration docs and artifact hashes.

For each implemented case record: case ID, confirmed seam, fixture/oracle, observed
red failure, minimal implementation, green command/result, and evidence location.
A missing dependency, skipped test or uncollected test is not the intended red
behavior. If a case already passes, record existing coverage rather than claiming
a new red → green cycle. Keep Python numerical/controller, frontend contract,
installed-parent browser and machine-specific capacity results separate.

## Coverage boundaries and open test-design choices

All six delivery slices and every row in the plan's verification matrix have cases
above: projection M/P; provenance M/P/A; partial geometry P; entity inspection
P/A/W; browser state W; runtime stability Q; parent lifecycle I; release semantics
I/D; capacity Q; regression M/I plus the existing suites.

Before affected executable cases, settle exact snapshot construction, versioned
wire validation/errors, preflight limits, clipping relink semantics, session
admission/duplicate response, D-001 and quantitative capacity thresholds. These
are narrow test-oracle gaps, not a reason to defer all independent work.

Scope checks during review: no automatic Original/Candidate correspondence
(F-001); no snapshot export/reopen (F-002); no cancellation, supersession or broad
lifecycle/concurrency layer (F-003/F-004); no arbitrary multi-selection (F-005);
no keyboard picking shortcuts (F-006). Triangle-quality/scalar computation,
ScalarControls, ScalarLegend, UVViewport, TraceTable, PrimitiveTree and unrelated
operations remain outside this cut. Their placeholders are not missing test cases
for authorized work.
