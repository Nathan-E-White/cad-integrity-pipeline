# Codex integration handoff

## Goal

Integrate the supplied diagnostic and presentation seams into the existing project without introducing a second repair pipeline, metric authority, STEP adapter, or general-purpose viewer. This bundle was built from the supplied snippets and prior architectural context; the current repository was not inspected or modified.

## Existing architecture to inspect first

Prior project discussions identified `repair_transition.py` (`RepairPipeline.run`), `metrics.py`, `numerics.py`, `adapters/ocp.py` (`run_step_pipeline`, checked STEP export, tessellation and edge sampling), plus `integration/` and the Gradio application. They also identified the framework-independent chain `ModelDocument → RenderModel → ThreeCadViewer`, with `model.ts`, `selection.ts`, `RenderModel.ts`, `ThreeCadViewer.ts` and a `ViewerLayer.mount(context)` extension boundary. Verify these against the checkout before editing; the names are contextual guidance, not a repository audit.

The request switches this frontend thread to Svelte. It does **not** require rewriting reusable Three.js code merely because the previous wrapper was SolidJS.

## Recommended merge order

1. Compare the existing topology and quality metrics against `docs/MATHEMATICS.md`. Reuse the existing implementations when definitions, triangle ordering, tolerances and orientation conventions match. Otherwise improve the authoritative implementation and port the regression tests. Do not register two copies of the same audit in separate pipeline stages.
2. Add the versioned diagnostic payload and target mapping at the existing presentation/export boundary. Prefer `assemble_payload` when authoritative audit results already exist. Do not make a Gradio postprocessor recompute them.
3. Extract or adapt `DiagnosticsLayer` into the existing `ViewerLayer.mount(context)` lifecycle. Use the mother's coordinate conversion, camera, scene, invalidation and resource ownership. **Do not double-normalize positions.** The standalone `ThreeMeshViewport` should be omitted when the existing renderer already supplies these responsibilities.
4. Add the Svelte `MeshDiagnosticsView`/`MetricsPanel` host with a small adapter around the mother's viewport methods. Keep Svelte state, GPU state and network events distinct. Preserve the existing general viewer for SolidJS clients if still used.
5. Copy `MeshDiagnostics` and the minimal frontend exports into the project's generated Gradio custom-component scaffold. Preserve its actual package names, build metadata, component registration, Block/StatusTracker integration and pinned dependency graph. Do not mistake the adapter file for a built distributable wheel.
6. Exercise the standalone and actual Gradio acceptance cases in `docs/ACCEPTANCE.md`, then resolve/commit the application's lockfiles.

## Invariants that must survive integration

The geometry revision changes whenever coordinates, connectivity or source triangle ordering changes. The diagnostic revision changes with thresholds or diagnostic results. Face/edge selections belong to their exact geometry revision. Original-mesh errors must not be indexed against a repaired mesh just because both have a face 17. A correspondence or explicit source-stage view is required.

Triangulation, welding, decimation, CAD tessellation and polygon conversion must supply identity maps rather than silently reinterpret IDs. Native OCP face IDs are local to the audited shape unless the existing project has a stronger naming mechanism. Preserve `triangle_parent_faces` or replace it with the mother's explicit identity scheme.

Keep analysis coordinates and units authoritative. Rendering normalization is a display transform. Do not return display-normalized coordinates as engineering output.

Treat `pass`, `fail`, `warn`, `info`, and `not_checked` as different states. Boundary presence is policy-dependent. Vertex count is information, not a validation pass. No diagnostics is not proof of a valid mesh. Legacy producer assertions must remain labeled as legacy.

Selection changes must not rebuild the base mesh or recompute its normals. Small active face overlays may be reconstructed, while edge overlays are batched per category. Camera fitting is an independent command and should not be triggered by hover/pin/unpin.

Do not open a browser-supplied filesystem path in `postprocess`. Do not enable `allow_pickle=True` to recover old object-array metadata. Migrate structured metadata to JSON. Upload authorization, job ordering, session isolation, process resource limits and cancellation belong to the existing orchestrator.

## Intentional exclusions

No repair algorithm, new mesher, signed high-order FEM Jacobian evaluator, CAD validity engine, boundary-loop tracer, homology engine, scalar heatmap framework, distributed job service, binary asset server, or collaboration state store is introduced here. Those can feed the typed payload/target seam without rewriting the metric panel.

## Delivery verification boundary

The numerical tests, serialization tests, pure TypeScript tests, strict type checking of pure model/resource modules and Svelte client/server compilation were run. Full dependency resolution, Three.js renderer type checking, Vite build, GPU/browser acceptance and a compiled Gradio custom-component installation were not run in this environment. Do not remove this distinction from the integration report until those checks actually pass.
