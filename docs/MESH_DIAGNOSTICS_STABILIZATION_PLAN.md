# Mesh diagnostics stabilization before parent integration

Status: approved implementation plan, September 20, 2026. Baseline inspection at
`7ea74c9`. Implementation and current qualification are recorded in
`integration/mesh-diagnostics-seam/VERIFICATION.md`; the sections below retain the
agreed scope and gates.

## Relevant handoffs

1. [INTEGRATION_PLAN.md](INTEGRATION_PLAN.md) is the repository-level integration
   assessment. Its slices 0–3 establish provenance, packaging, diagnostic contracts,
   and the Gradio display. Its broader surface-processing sequence remains separate.
   Its baseline and reported test counts are historical, not current qualification.
2. [CODEX_INTEGRATION.md](../integration/mesh-diagnostics-seam/CODEX_INTEGRATION.md)
   records useful invariants: one metric authority, revision-bound selection,
   display-only normalization, explicit status, and a thin Gradio boundary. It was
   written without inspecting this repository and names the archived delivery's APIs.
3. [ACCEPTANCE.md](../integration/mesh-diagnostics-seam/ACCEPTANCE.md) supplies browser
   and lifecycle acceptance scenarios. [VERIFICATION.md](../integration/mesh-diagnostics-seam/VERIFICATION.md)
   records delivery-environment checks, not evidence that the loose package builds.
4. [GRADIO_HANDOFF.md](GRADIO_HANDOFF.md) preserves the earlier local geometry and
   source/candidate identity rationale. It predates the current app and is background.

## Decision and scope

Stabilize the loose `cad_mesh_inspector` / `InspectorDocument` implementation as the
working base. It already supplies the toolbar, scalar legend, metric panel, renderer,
selection model, and Python report adapters needed by the requested inspector.
Use the archive as a separately identified source of algorithms and regression cases;
do not extract it over the loose files or mix its `mesh_diagnostics` contract into v1.
Record a path-aware comparison and provenance for each adopted module before moving it.

The four deliverables are a working standalone entry point, reusable inspector,
Gradio wrapper, and optional numeric NPZ loader. Parent controller changes and the
other intermediate packages follow their own qualification gates afterwards.

`main.ts` already exists and mounts `Demo.svelte`. The missing work is a coherent
entry-point location and build configuration. `Demo.svelte` imports an absent
`MeshInspector.svelte` and an absent fixture path. Current `Index.svelte` consumes
`vertices/faces/error_edges`, whereas Python emits `schema_version/meshes/linked_views`.
It also removes objects without disposing their geometry/materials during updates.
Replace that renderer with composition of the existing `Viewport` lifecycle.

## Stable interfaces

Keep `InspectorDocument` v1 as the single prepared display input for both entry
points. `MeshInspector` accepts `value: unknown` at its public boundary and uses
`parseDocument` once per incoming value. Python retains `InspectorDocument` validation.
Use cross-language fixture tests to prevent those validators drifting apart.

Preserve `mesh_payload`, `document`, host-report adapters, `Target`, and `InspectionState`
unless a demonstrated defect requires a narrow change. `inspect_triangles` remains
a standalone reference/demo path. The parent continues to own engineering results.
Retain v1 `unknown` status explicitly; the archived `not_checked` vocabulary needs an
explicit adapter if adopted. Neither empty nor unchecked diagnostics implies success.

Proposed ownership:

| Surface | Owns | Receives / delegates |
|---|---|---|
| `src/main.ts` + `Demo.svelte` | Standalone mounting, labeled fixture | `MeshInspector` |
| `src/components/MeshInspector.svelte` | Document validation, pane composition, camera-link lifetime | Prepared document; existing core/render modules |
| Private per-mesh pane, if needed | One viewport, controls, preview/pinned target, local errors | Typed mesh and stable display frame |
| `Index.svelte` | Gradio props, Block/loading/visibility integration | Delegates value to the same inspector |
| `python/cad_mesh_inspector/npz_io.py` | Bounded local numeric archive admission | Arrays passed explicitly to payload/report adapters |

Keep WebGL creation inside mounted browser lifecycle. Keep hover, selection, and
camera state local; the output-only backend still has no geometry mutation events.
No new generic renderer abstraction is needed for these four deliverables.

## Implementation sequence and gates

### 0. Restore one package layout and dependency graph

Restore the structure already expected by imports and build metadata:
`python/cad_mesh_inspector/`, `tests/`, `src/core/`, `src/render/`,
`src/components/`, `src/main.ts`, and `src/Demo.svelte`. Put the fixture in a single
documented examples location and fix its import. Keep `Index.svelte` at the Gradio
frontend entry. Record old-to-new paths; preserve the archive unchanged.

Add the missing Vite/Svelte configuration, align TypeScript includes with every
adopted source, and restore real test scripts. Current scripts reference absent
frontend test files. Use the existing Svelte 5 host scaffold as the compatibility
target; remove the unverified Svelte 4 claim unless separately qualified. Resolve
and lock one dependency graph without updating sibling packages as a side effect.

Gate: installed Python package imports from outside the source tree; numerical,
contract, and adapter tests collect and execute. Full renderer/Svelte checking sees
the actual files. Finish this gate with the NPZ slice below, since `__init__.py`
already imports that missing module. Do not hide the missing import or skip its tests.

### 1. Implement optional NPZ input against the existing Python tests

Interpret optional NPZ as `load_numeric_npz`, already imported by `__init__.py` and
`test_io.py`; no browser NPZ worker or binary streaming protocol is needed.
The feature is optional to callers, while the module is part of the installed package.

Start with geometry only: exactly one of `positions`/`vertices` and exactly one of
`triangles`/`faces`, returned as canonical `positions` and `triangles` arrays.
Reject ambiguous aliases and other members. Pass arrays through `mesh_arrays` so
shape, finite coordinates, integer/range validation, budgets, and source order stay
consistent. Units, IDs, revisions, and provenance are explicit caller metadata.
Do not infer them from filenames. Additional path arrays require a separate named
contract; the existence of `traces_from_offsets` does not authorize arbitrary NPZ keys.

Adapt the archive's header-first reader, retaining compressed/expanded byte limits,
member/header limits, duplicate and unexpected-member rejection, encrypted-member
rejection, primitive numeric dtypes, header shape/byte checks before allocation,
and `allow_pickle=False`. Preserve or deliberately document the loose tests' exception
contract, including `BadZipFile` for malformed archives. Do not inherit the archive's
different error type accidentally.

Gate: existing `test_io.py` passes plus focused cases for byte/count limits,
duplicates, truncated array bodies, dtype rejection, bad indices, and alias parity.
Verify importing/using prepared JSON documents never reads a file. This loader does
not replace the parent's stricter `vertices/triangles/length_unit` upload admission.

### 2. Build `MeshInspector.svelte` around the supplied modules

Compose `Viewport`, `InspectorToolbar`, `MetricPanel`, and `ScalarLegend`. Support
zero, one, and two meshes. For linked panes, calculate one shared `frameFor(meshes)`
and connect cameras only after both panes are ready. For unlinked panes, use their
own frames. Disconnect camera links before disposing or replacing panes.

Keep preview and pinned targets separate: preview temporarily overrides the pin,
and leaving preview restores it. All targets retain mesh ID and geometry revision.
Clear stale targets on revision changes; never mirror face IDs between panes.
Reset missing scalar choices and invalid clipping ranges when inputs change.

Keep input parsing separate from view-state updates. Reuse the parsed mesh/frame
objects while changing controls; `Viewport.setMesh` currently rebuilds layers for
new object references. Hover/select must use `select`, controls use `applyState`,
and fit/focus remain explicit commands. A later optimization for diagnostics-only
updates should be isolated and justified by a measured need.

Handle null/empty input, invalid documents, WebGL construction failure, context
loss, resize, hidden tabs, and unmount explicitly. Invalid input must not leave an
old result appearing current. Keep metrics readable when WebGL is unavailable.
Include cleanup of partially initialized resources in the renderer review.

Gate: Python-produced fixtures accepted in TypeScript; stale selection and status
cases tested; full Svelte/Three.js typecheck; browser evidence for two-pane linking,
independent panes, selection, field changes, clipping, clear, and repeated disposal.

### 3. Complete `main.ts` and the standalone harness

Move/adapt the existing bootstrap to the path referenced by `index.html`. Mount the
demo only; keep fixture loading and labels in `Demo.svelte`. Preserve a useful error
for a missing mount node and clean up mounts during development reloads as needed.
Use this harness during slice 2 rather than waiting for Gradio packaging to debug
the renderer. Keep fixture assets out of the distributable component entry.

Gate: production build and served-build smoke test, with no unresolved imports;
initial fixture display, replacement, clear, and remount work in a real browser.

### 4. Replace `Index.svelte` and qualify the component package

Use the actual local Gradio scaffold conventions demonstrated by
`components/verification_grid/frontend/Index.svelte`: typed shared props, Block,
StatusTracker, visibility, and component exports. Route its value to `MeshInspector`.
Remove the old scene, animation loop, flat payload schema, and assumed utility CSS.
Keep component styles scoped and compatible with the host theme.

Prepare the generated backend/frontend packaging together so `MeshDiagnostics`
ships compiled assets and registration metadata. Do not modify the parent app yet.
Its `postprocess` continues to validate prepared values; `preprocess` remains
output-only. Add a minimal independent Gradio demo using the installed wheel.

Gate: installed wheel serves real assets; null clears; document replacement works;
loading/visibility and hidden-tab resize behave correctly; interactions remain local;
mount/unmount and context recovery pass. Standalone and Gradio must render the same
fixture through the same inspector.

## Completion and subsequent integration

Implement packaging/NPZ, reusable inspector/demo, and Gradio packaging as focused
reviewable slices. Finish with corrected README paths, public examples, license and
provenance notes for adopted archive code, current verification evidence, and scoped
artifact hashes. Avoid retaining two canonical copies after relocation.

Completion requires actual Python tests, full frontend checking, build, browser
acceptance, and an installed-component smoke test. A successful compiler invocation
with no source files, skipped tests, or a Python-only Gradio test is insufficient.

Only then begin parent integration: project authoritative reports into the prepared
document, preserve source/candidate visibility and units, retain the existing check
ledger, and verify equivalent display behavior before retiring Plotly. Geometry
revision, diagnostic revision, stage identity, and source-face mapping must be made
explicit at that boundary; v1 currently has only one mesh revision. If separate
diagnostic identity requires a schema change, version it deliberately then.

Mesh healing, NURBS reconstruction, and derived exports retain the separate gates
in `INTEGRATION_PLAN.md`. Their unresolved kernel/export issues need not delay this
read-only display package.
