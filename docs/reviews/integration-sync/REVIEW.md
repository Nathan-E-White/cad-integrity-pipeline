# Integration sync review and diagnostics reconciliation

Companion assessment: [Mesh-healing and NURBS integration review](GEOMETRY_REVIEW.md)
covers the other two substantive bundles, their host/native overlap, missing
integration contracts and freshly rerun standalone suites. It also records a current
native NURBS compile failure that must be resolved before numerical parity work.

Execution shortlist: [Low-effort repairs](LOW_EFFORT_REPAIRS.md) separates localized
repairs from package-dependent edits and larger integration work.

Reviewed September 20, 2026. Branch `integration/sync`, created from local `main`
at `075b2dd11f49e7781daa50dc26b8f2827c178f61`. Worktree:
`/private/tmp/cad-integrity-integration-sync`.

Cleanup scope: `git diff bc78be0...e9178bb`; 19 commits, 28 changed paths.
The starting commit itself is excluded, as requested by the handoff's range.
The subsequent `075b2dd` documentation update supplies the latest integration plan.
No remote refs or hosted CI were queried. This review makes no production changes.

Post-extraction update: 47 missing archive-relative files were subsequently copied
into the diagnostics directory without overwriting existing files. Original review
counts and `diagnostics-inventory.json` describe the pre-extraction snapshot. The
reassessment below records the current status of the seven missing-file/glue findings.

## Decision

The cleanup has no confirmed actionable regression in the requested range.
Proceed to a bounded diagnostics package reconstruction and contract agreement.
Neither diagnostics delivery can be adopted wholesale: the archive is a coherent
older package; the loose tree contains useful newer capabilities but is incomplete,
and its Gradio `Index.svelte` belongs to a third, incompatible payload contract.

Keep `src/cad_integrity` admission, topology/quality reports, check ledger, and release
semantics authoritative. Use loose host-report adapters and output-only Gradio
behavior as integration candidates. Retain the archive's identity/status safeguards
and unique tests. Select one versioned wire contract before assembling the UI.
The canonical-source recommendations below are decisions proposed by this review;
no files have been promoted, relocated, deleted, or wired into the app.

## Standards

No actionable Standards findings in `bc78be0...e9178bb`.

- Dependency ownership: root policy, portable constraints, component versions and
  child ranges agree. The repeated declarations are intentionally checked by tooling.
- Locks: the root Bun workspace/catalog replaces competing child locks. The final
  Pixi lock selects PythonOCC and OCCT `novtk` builds. `cadquery-ocp==7.9.3.1.1`
  requires PyPI `vtk==9.6.2`; no conda VTK package remains in that lock.
- Artifact manifests: Git tracked/unignored semantics preserve tracked source even
  when an ignore rule later matches it. Live bundle manifests are checked separately;
  immutable example provenance is verified, not regenerated.
- CI: explicit local component installation, portable constraints, frozen Bun install,
  dependency/CAD checks and component builds precede existing gates. The build flags
  suppress documentation regeneration.

No additional repository AGENTS/CONTRIBUTING/standards or issue-tracker configuration
was found. Standards were drawn from the supplied instructions, dependency policy,
integration plan and the code-review skill. Creating external tracker configuration
would exceed this local review's scope and was not done.

## Spec

No confirmed specification violation or scope creep in `bc78be0...e9178bb`.

- `docs/DEPENDENCIES.md:12–19` describes shared ranges, mirrors, versions, paths,
  catalogs and lock ownership. The checker implements those responsibilities.
- `docs/INTEGRATION_PLAN.md:22–24` requires that conda not also provide VTK. The
  reviewed resolved lock satisfies that requirement; no provider rollback is warranted.
- `docs/DEPENDENCIES.md:99–109` separates live inventory from immutable archives and
  fixture provenance. `scripts/verify_artifacts.py:42–108` preserves that separation.
- `docs/DEPENDENCIES.md:118–121` describes the CI sequence implemented in
  `.github/workflows/tests.yml:19–35`.

Nonblocking coverage limitation: `scripts/check_dependencies.py:41–45` checks direct
conda declarations, not transitive providers in `pixi.lock`. A passing declaration
check alone does not establish one VTK owner. Current lock inspection supplies that
evidence. A resolved-provider regression check would help future dependency changes.

Standards: 0 actionable findings. Spec: 0 confirmed violations; 1 nonblocking
coverage limitation. Existing lint/type and diagnostics failures remain open and
are not cleanup regressions.

## Evidence reproduced here

| Check | Result and boundary |
|---|---|
| Dependency declaration checker | Passed; no `--environment`, installation or resolver run |
| Artifact verification before review files | Passed, including live bundle and fixture checks |
| `tests/test_repository_manifests.py` | 7 passed, no skips; output in `validation.txt` |
| Diagnostics archive internal manifest | 49 entries verified directly against archive member bytes |
| Path/hash/symbol inventory | 50 archive files; 47 loose files excluding the archive |

The focused tests used the existing environment's Python executable read-only,
with bytecode and pytest plugin autoload disabled. Temp files were directed to this
worktree's ignored `outputs/integration-sync/` directory. They exercise checkout-local
scripts, not application imports from the original checkout. No CAD suites, frontend
builds, browser/GPU behavior, fresh installation or hosted CI were rerun. Previously
recorded broad suite results are not presented as fresh evidence.

## Path-aware provenance

Archive: `integration/mesh-diagnostics-seam/mesh-diagnostics-seams.tar.gz`.
SHA-256: `807c46906790dd2bad568f56cb48607c86bc31a4e789a0a90a176d3fc0f94b1f`.

Only three archive files share an exact relative path with the loose tree after
removing the archive's root directory: `README.md`, `CODEX_INTEGRATION.md`, and
`pyproject.toml`. The first two match; the project manifest differs. A secondary
basename comparison finds five equal files, all documentation: those first two plus
`docs/ACCEPTANCE.md`, `docs/MATHEMATICS.md`, and `docs/VERIFICATION.md` against their
flattened loose counterparts. No same-basename Python, TypeScript or Svelte source
is byte-identical. Shared names are not evidence of equivalent behavior.

`diagnostics-inventory.json` records every member's original relative path, size,
hash, Python class/function/method names and line numbers, imports, and lexical
TypeScript declarations/tests. `compare_diagnostics.py` reproduces it without
extracting or executing archive code. Lexical TS entries are not a complete AST.
The inventory is deliberately exhaustive; the following tables group semantic peers.

Below, `A/` means a path within archive root `mesh-diagnostics-seams/`, while `L/`
means a path in the loose `integration/mesh-diagnostics-seam/` directory.

## Canonical candidates by capability

| Capability | Archive paths / API | Loose paths / API | Proposed source and disposition |
|---|---|---|---|
| Host engineering result | Standalone `python/mesh_diagnostics/audit.py` | Standalone `diagnostics.py` and `payload.py:inspect_triangles` | Existing host remains canonical. Neither standalone audit replaces it. |
| Host projection | `python/mesh_diagnostics/payload.py:assemble_payload` accepts prepared reports | `adapters.py:from_triangle_reports`, `from_polygonal_report` | Loose adapters, qualified against actual host reports and selected document contract. Preserve polygon-row mapping. |
| Geometry carrier | `python/mesh_diagnostics/model.py:TriangleMesh`, `MeshLimits`, `_matrix` | `arrays.py:mesh_arrays` | Host admission first; archive owned snapshot/hash semantics as identity reference. Loose arrays are validation helpers, not identity carriers. |
| Edge evidence | `python/mesh_diagnostics/topology.py:EdgeTopology`, `edge_topology` | `diagnostics.py:EdgeIncidence`, `edge_incidence` | Host authority; archive CSR `offsets`/`incident_faces` only if required by a concrete projection. |
| Quality reference | `python/mesh_diagnostics/quality.py:triangle_quality` | `diagnostics.py:triangle_quality` | Preserve separate named definitions and fixtures; do not consolidate by function name. |
| Wire validation | `python/mesh_diagnostics/contract.py`, `frontend/src/model/types.ts`, `parse.ts` | `contracts.py`, `contracts.ts:parseDocument` | Loose paired/scalar/path shape is the richer candidate; add explicit geometry/diagnostic revisions and archive conservative validation before adoption. A new contract version is required if semantics change. |
| Assembly/policy | `audit.py:AuditPolicy`, `audit_mesh`; `payload.py:assemble_payload`, `payload_from_audit` | `payload.py:mesh_payload`, `inspect_triangles`, `document` | Loose report projection/composition with archive identity/status rules; standalone policy remains separate. |
| NPZ reference | `python/mesh_diagnostics/io.py:ArchiveLimits`, `load_npz_arrays`, `load_triangle_mesh` | Missing `npz_io.py:load_numeric_npz` | Archive implementation is a reference, not a drop-in replacement. Production upload retains host admission. |
| Legacy/path import | `python/mesh_diagnostics/legacy.py:mesh_from_mapping`, `adapt_legacy_payload` | `legacy.py:upgrade_legacy_payload`, `traces.py:traces_from_offsets` | Loose conservative telemetry/path conversion; preserve archive malformed/alias tests. Do not infer engineering success from legacy labels. |
| Gradio backend | `gradio_adapter/meshdiagnostics.py` | `gradio_component.py:MeshDiagnostics` | Loose output-only semantics; package in the existing Gradio scaffold only after choosing the frontend contract. |
| Svelte composition | `frontend/Index.svelte`, `src/components/MeshDiagnosticsView.svelte`, `MetricsPanel.svelte` | `Index.svelte`, `Demo.svelte`, `MetricPanel.svelte`, `InspectorToolbar.svelte`, `ScalarLegend.svelte` | Archive is a complete composition reference. Loose advanced components need the absent `MeshInspector.svelte`; simple loose Index is not a compatible substitute. |
| Renderer | `frontend/src/render/ThreeMeshViewport.ts`, `DiagnosticsLayer.ts`, `resources.ts` | `Viewport.ts`, `SurfaceLayer.ts`, `DiagnosticLayer.ts`, `CameraLink.ts`, `ResourceScope.ts`, `picking.ts`, `shaders.ts` | Loose renderer is the advanced candidate for paired views, clipping, scalar display and picking. Archive lifecycle/tests are reference coverage. Adopt one renderer only after browser acceptance. |
| Pure display helpers | `frontend/src/model/frame.ts`, `buffers.ts` | `math.ts`, `geometry.ts`, `colors.ts`, `selection.ts`, `state.ts`, `scheduler.ts` | Preserve identity, precision and disposal tests across the chosen implementation; helpers are not interchangeable APIs. |
| Packaging/docs/examples | Structured archive frontend/python/tests/tools/examples | Flat loose files, root-catalog package manifest, torus fixture | Keep current root dependency ownership. Recover layout deliberately; retain original docs as delivery provenance and write accurate live documentation. |

## Missing files, methods and integration glue

The numbered findings below describe the original, pre-extraction state; see the
status table immediately after them for what the extraction resolved.

1. `L/pyproject.toml:17–22` searches `python/` and `tests/`; neither exists. Sources
   and all five test modules are flat, while imports expect `cad_mesh_inspector`.
2. `L/__init__.py:4` and `test_io.py:5` require `npz_io.load_numeric_npz`. Neither
   module nor function exists in the loose delivery. Archive names and error/output
   behavior differ, so restoring a directory cannot fix this.
3. `L/Demo.svelte:2` requires absent `components/MeshInspector.svelte`. This missing
   composition layer must parse the document, create/dispose one or two viewports,
   compute shared display frames, link cameras, route selections and present errors.
   Individual viewport methods exist; their Svelte owner does not.
4. `L/index.html` references `/src/main.ts`; actual `main.ts` is at the root. Renderer
   imports reference absent `../core/`; component imports assume their intended
   directories. `Demo.svelte` references `../../examples/torus-comparison.json`
   while that fixture is also flat. These are path mismatches, not missing algorithms.
5. `L/tsconfig.core.json` expects `src/core/**`, `src/render/CameraLink.ts` and
   `ResourceScope.ts`; its package scripts require missing `tests/*.test.mjs` and
   `tests/compile-svelte.mjs`. No loose frontend tests, Svelte config or Vite config
   are delivered. Archive has differently named test/tool/config files, which target
   its own APIs and older independent dependency declarations.
6. `L/gradio_demo.py` imports a future generated `gradio_meshdiagnostics` package;
   `gradio_component.py` alone does not supply its packaged frontend.
   `gradio_component.py:4` references absent `CODEX_HANDOFF.md`.
7. Archive-only capabilities include `AuditPolicy`, reference-normal alignment,
   incident-face CSR, separate diagnostic revision hashing and typed revision-bound
   targets. Loose-only capabilities include host adapters, paired frame/unit checks,
   scalar fields, traces, direct face/path targets and linked camera/picking methods.
   These are capability differences, not all mandatory missing implementation.

The five identical documentation files describe the archive APIs and its historical
test results. Their presence beside loose code does not validate that different code.

### Reassessment after copying the 47 archive files

**Of the seven numbered findings: one is resolved for source availability only,
two are partially resolved, and four remain unresolved.** Finding 7 was a capability
inventory rather than a broken integration requirement. None of findings 1–6 is
fully resolved as an integration issue merely by copying files.

| Finding | Current status | What changed and what remains |
|---|---|---|
| 1. Python package/test layout | Partially resolved | `python/` and `tests/` now exist, with `python/mesh_diagnostics` and the archive's tests importing that package. The original five flat tests still import `cad_mesh_inspector`, which is absent. The preserved project manifest still names the distribution `cad-mesh-inspector`; a distribution name need not equal its import name, but restoring `mesh_diagnostics` does not restore the missing `cad_mesh_inspector` API. Default test discovery now points to archive tests, not those five flat tests. |
| 2. `npz_io.load_numeric_npz` | Unresolved | No `npz_io.py` or `load_numeric_npz` implementation exists anywhere in this delivery. Restored `python/mesh_diagnostics/io.py` provides `load_npz_arrays` and `load_triangle_mesh`, with the different alias/output/error behavior already documented. |
| 3. `MeshInspector.svelte` composition | Unresolved | `frontend/src/components/MeshDiagnosticsView.svelte` is now present and composes the archive's single-mesh renderer. The original `Demo.svelte` still imports absent `components/MeshInspector.svelte`; the paired/scalar/path document has no restored composition owner. |
| 4. Loose frontend imports/entrypoint | Unresolved | The archive's nested `frontend/` has its own valid-looking relative structure, but the original root `index.html` still points to absent `/src/main.ts`; `src/core/` and `src/render/` remain absent. The original Demo fixture import also remains unchanged. No entrypoint or import was redirected by extraction. |
| 5. Frontend tests/configuration | Partially resolved | `frontend/test/model.test.ts`, `frontend/svelte.config.js`, `frontend/vite.config.ts` and `tools/compile_svelte.mjs` now exist for the archive implementation. The root package still requires absent `tests/*.test.mjs` and `tests/compile-svelte.mjs`, and its core TS config still references absent `src/` paths. The restored files do not satisfy those commands. |
| 6. Generated Gradio package/handoff | Unresolved | `gradio_adapter/meshdiagnostics.py` and archive examples now exist. They do not create the generated `gradio_meshdiagnostics` distribution, compiled component assets, or missing `CODEX_HANDOFF.md`. The original demo import remains unsatisfied by this source tree. |
| 7. Archive-only capability availability | Resolved for source availability | `AuditPolicy`, reference-normal quality, CSR incidence, diagnostic revision hashing and typed revision-bound targets are now ordinary files under `python/mesh_diagnostics/`. Loose host adapters, paired documents, fields and traces also remain. These implementations still use different contracts; no semantic reconciliation or host adoption has occurred. |

Verification was static: checked the exact expected paths, parsed Python declarations
without importing modules, inspected package/test entrypoints, and compared every
archive file against disk. All 50 archive-relative file paths now exist; 49 match
archive bytes. The sole difference is the deliberately preserved `pyproject.toml`.
No suites, builds or Gradio runtime were executed for this reassessment.

The restored `frontend/package.json` also retains the archive's older independent
dependency versions. It is not the catalog-based root diagnostics package and is
not separately listed in the root workspace. File recovery therefore does not
establish dependency qualification for that nested frontend. Keep this distinction
when selecting which package and test entrypoint to reconcile next.

## Payload incompatibilities

| Concern | Archive contract | Loose advanced contract | Loose `Index.svelte` |
|---|---|---|---|
| Envelope | Single mesh, `schema_version: "mesh-diagnostics/1"` | Numeric version `1`, up to two `meshes`, `linked_views` | Unversioned `vertices`, `faces`, `error_edges`, `metrics` |
| Identity | `mesh_id`, `geometry_revision`, `diagnostic_revision`, `stage` | `id`, one `revision`, `frame_id` per mesh | No revision/stage identity |
| Units | `units` string | Nullable `length_unit`; linked views require equality | Not represented |
| Selection | Revision-bound face/edge/segment `targets`; `target_id` | Grouped `selections`; `selection_id`; face/path browser targets | Coordinate error segments only |
| Status | `info/pass/warn/fail/not_checked` | `info/pass/warn/fail/unknown` | `pass/fail`; any non-pass branch renders a failure mark |
| Parent mapping | `triangle_parent_faces`, revision-local upstream IDs | `triangle_source_faces`, explicitly source polygon rows | None |
| Extra data | `description`, `notes` | `scope`, `provenance`, scalar `fields`, `paths` | Simple labels/values |
| Gradio input | Archive adapter validates/returns client payload; select event | Output-only, no events; `preprocess` returns `None` | Props do not match the loose backend output |

Passing `InspectorDocument` to the loose Index supplies neither `vertices` nor
`faces`; `buildGeometry` returns without a mesh. Passing either advanced payload to
the other validator is likewise not a supported conversion. Renaming keys is
insufficient: revision semantics, targets, units, limits and status meanings differ.

Limits differ too: archive defaults allow 250,000 vertices / 500,000 triangles;
loose allows 500,000 / 250,000. Archive caps 128 targets, 512 metrics and six million
target scalars; loose caps 256 selections, 256 metrics and eight million selection
scalars, plus path limits. Choose aggregate budgets deliberately.

## Behavioral blockers before adoption

These are existing delivery findings, not defects introduced by the cleanup range.
They are source-derived unless a reproduced check is explicitly listed above.

- **Empty/partial checks can pass in the loose convenience audit.**
  `L/payload.py:43` bases status on zero defect count, even when there are no
  triangles or repeated-index faces were excluded from incidence. Archive
  `A/python/mesh_diagnostics/payload.py:58–59` emits `not_checked` for empty/partial
  evidence. Port the conservative rule and define host status aggregation explicitly.
- **Threshold zero changes the meaning of low quality.** `L/payload.py:45` uses only
  `mean_ratio < threshold`; zero-quality degenerate faces pass that metric when the
  threshold is zero, although the separate degeneracy metric fails. Archive
  `payload.py:85` explicitly includes degeneracy. Preserve the distinction in labels
  or use the intended union with a regression fixture.
- **Backend/frontend parent-ID acceptance differs.** `L/contracts.py:97–99` accepts
  arbitrarily large nonnegative parent IDs; `contracts.ts:53,123` requires JavaScript
  safe integers. Archive `contract.py:103–105` rejects values above `2**53-1`.
- **Geometry and diagnostic identity are conflated in loose data.** Archive assembly
  hashes policy/result descriptors separately; targets carry geometry revision.
  Loose browser `resolveTarget` checks mesh ID/revision, but supplied selection arrays
  have no independent revision binding. Define how changed reports invalidate targets.
- **Quality tolerances are not equivalent.** Archive uses normalized relative
  cross-product tolerance (default `1e-12`) and optional reference normals; loose uses
  absolute area tolerance (default zero) and returns world-space areas. Loose area
  reconstruction can overflow at extreme scales even when dimensionless quality is
  representable. Host longest-edge/inradius aspect is also different from `R/(2r)`.
- **NPZ API behavior differs.** Archive loader preserves aliases and wraps malformed
  ZIP errors in `MeshValidationError`; loose tests require normalized `positions` /
  `triangles`, ambiguity rejection, particular error matches and raw `BadZipFile`.
  An explicit adapter and retained negative tests are needed if this optional API remains.
- **The simple loose Index leaks replaced GPU resources.** `Index.svelte:94–96`
  removes scene children without disposing their geometries/materials; teardown only
  disposes controls/renderer. It also starts initialization only with an initial value.
  Use a qualified lifecycle owner, not this component as the advanced renderer wrapper.

## Tests that must survive reconciliation

There are 32 archive Python test functions and 35 loose Python test functions;
these are static function counts, not collected or passing case counts. Parametrized
tests expand further. Both suites cover basic triangle quality, edge incidence,
invalid connectivity and legacy conversion, but neither subsumes the other.

Archive-specific coverage worth retaining (`A/tests/test_diagnostics.py`): reference
normal alignment and invalid normals (55–66); degeneracy with zero threshold (79–82);
partial incidence status (109–116); edge-manifold shells touching at one vertex
without claiming full validity (119–128); unchanged geometry but changed policy/
diagnostic revision (131–138); conservative empty status (141–145); owned arrays and
triangle-order hashing (158–168); stale targets (181–184); duplicate NPZ members
(254–260). Archive `frontend/test/model.test.ts` additionally covers pre-float32
origin subtraction, extreme/coincident coordinates, source IDs, uint32 index width,
malformed payloads and deduplicated/idempotent resource disposal. No loose frontend
test-file equivalent was delivered.

Loose-specific coverage: unknown/null scalars and paired frames/units/domains
(`test_contracts.py:34–48`); conservative legacy claims/path provenance (51–66);
absolute area tolerance (`test_diagnostics.py:92–96`); alias normalization and trace
offset validation (`test_io.py`); output-only Gradio and invalid-output rejection
(`test_gradio.py`); host metric definitions and polygon-to-triangle mapping
(`test_host_adapters.py:22–37`). The host tests may skip when host imports fail;
that must fail qualification rather than count as a successful integration check.

The complete named test/symbol lists and line numbers are in the JSON inventory.
Preserve semantic fixtures while adapting API names; copying tests without adapting
their contract does not establish parity.

## Next bounded implementation

Agree the document identity/status/unit/budget contract, then restore a package
layout for the chosen loose capabilities under the existing dependency graph.
Recover or implement `load_numeric_npz` only if the optional standalone IO API is
still required; the host upload must not be replaced. Implement the missing Svelte
composition owner against that single contract, preserving archive regression cases
and both deliveries as immutable provenance. First acceptance is Python collection,
contract parity, required host adapter tests without skips, full frontend check/build
and a real Gradio lifecycle smoke test. Surface repair/export stays a later slice.

All review files and temporary test output were written inside this worktree. The
only outside-worktree writes authorized for this task were Git's branch/worktree
registration metadata. No commit, push, dependency installation or source cleanup
was performed.
