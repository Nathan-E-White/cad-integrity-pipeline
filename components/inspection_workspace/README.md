# Geometry inspection workspace

Installed Gradio component for parent-owned V2 polygonal, V3 native-face, and V4
canonical quad-trace inspection snapshots. V2 field meanings remain unchanged. V3 requires
`face_kind: native_face` and a `projection_id` in each mesh record; native face
rows retain original/candidate geometry scopes, revisions and local face IDs.
Display triangle picks require the matching projection identity. Native display
vertices and segments are not native vertices or edges, so V3 offers face-only
picking. Faces without triangulation remain listed with an explicit issue.
V4 adds bounded, revision-scoped canonical trace rows and exact segment coordinates
to a polygonal snapshot. The browser rejects stale scopes, malformed ownership,
noncanonical results, and over-budget trace data. GeometryViewport, MetricTable,
EntityTable, TraceTable, and the trace overlay implement the current workspace.
Camera, clipping, selection, hover, filters, trace paging, and picking stay local.
Original and Candidate keep independent revision-scoped identities.

The installed layer-2 shell uses a dense model / viewport / validation / instrument
layout. Camera coupling is explicit and browser-local; view HUD controls, matte
depth treatment and a camera-following XYZ gnomon do not change the versioned wire
document. Diagnostic membership and display-issue summaries use only fields already
present in that document. Scalar gauges, histogram envelopes and solver histories
remain unimplemented until an authoritative versioned projection supplies them.

The existing report components remain separate. The installed workspace is the default polygonal and STEP display after local qualification.
`build_app(inspection_enabled=False)` retains the legacy display path. Run the installed-parent
preview from the repository root with `pixi run gradio`; this builds all three
custom components before running the checkout-aware launcher. It binds only to
`127.0.0.1:7863` unless `CAD_INTEGRITY_PREVIEW_PORT` selects another free port.
The internal `pixi run inspection-preview` task uses the same launcher without
rebuilding and is reserved for Playwright after an explicit component build.
The launcher reports repository identity in the terminal only, requires the
canonical `main` branch, verifies all four Python package origins, and refuses occupied ports. Set
`CAD_INTEGRITY_REQUIRE_CLEAN=1` for qualification runs that must reject tracked
changes.

Build with `pixi run build-inspection-component`. From the frontend directory,
`bun run check`, `bun run test`, and `bun run test:browser` perform type, public
contract/state, and installed-parent browser checks. Browser tests start and stop
the same checkout-aware parent launcher on port 7864 and require a clean checkout.

Geometry travels as a bounded gzip document through Gradio-managed file delivery;
interaction stays local after the initial fetch. This cache is distinct from
retained release artifacts and does not add snapshot export/reopen functionality.

The scalar, primitive, UV, and operation component files remain reserved placeholders.

| Component | Intended responsibility |
| --- | --- |
| [GeometryViewport](frontend/src/components/GeometryViewport/GeometryViewport.svelte) | Geometry rendering, camera, picking, clipping, and visibility. |
| [ScalarControls](frontend/src/components/ScalarControls/ScalarControls.svelte) | Scalar field selection, palette, and display range. |
| [ScalarLegend](frontend/src/components/ScalarLegend/ScalarLegend.svelte) | Scalar field domain, scale, and units. |
| [MetricTable](frontend/src/components/MetricTable/MetricTable.svelte) | Computed metric rows and selection preview or pinning. |
| [EntityTable](frontend/src/components/EntityTable/EntityTable.svelte) | Entity filtering, visibility, and selection. |
| [PrimitiveTree](frontend/src/components/PrimitiveTree/PrimitiveTree.svelte) | Assembly or fitted-primitive hierarchy and membership selection. |
| [TraceTable](frontend/src/components/TraceTable/TraceTable.svelte) | Bounded canonical trace rows, termination states, paging, and overlay selection. |
| [UVViewport](frontend/src/components/UVViewport/UVViewport.svelte) | UV chart navigation and linked entity highlighting. |
| [OperationControls](frontend/src/components/OperationControls/OperationControls.svelte) | Operation parameters and explicit submission. |
