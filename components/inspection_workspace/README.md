# Geometry inspection workspace

Installed Gradio component for parent-owned V2 polygonal and V3 native-face
inspection snapshots. V2 field meanings remain unchanged. V3 requires
`face_kind: native_face` and a `projection_id` in each mesh record; native face
rows retain original/candidate geometry scopes, revisions and local face IDs.
Display triangle picks require the matching projection identity. Native display
vertices and segments are not native vertices or edges, so V3 offers face-only
picking. Faces without triangulation remain listed with an explicit issue.
GeometryViewport, MetricTable and EntityTable implement the current topology-only
workspace. Camera, clipping, selection, hover, filters and picking stay local.
Original and Candidate keep independent revision-scoped identities.

The installed layer-2 shell uses a dense model / viewport / validation / instrument
layout. Camera coupling is explicit and browser-local; view HUD controls, matte
depth treatment and a camera-following XYZ gnomon do not change the V2/V3 wire
document. Diagnostic membership and display-issue summaries use only fields already
present in that document. Scalar gauges, histogram envelopes and solver histories
remain unimplemented until an authoritative versioned projection supplies them.

The existing report components remain separate. The installed workspace is the default polygonal and STEP display after local qualification.
`build_app(inspection_enabled=False)` retains the legacy display path. Run the installed-parent
preview with `.pixi/envs/default/bin/python scripts/run_inspection_preview.py`
from the repository root; it binds only to `127.0.0.1:7863`.

Build with `pixi run build-inspection-component`. From the frontend directory,
`bun run check`, `bun run test`, and `bun run test:browser` perform type, public
contract/state, and installed-parent browser checks. Browser tests start and stop
their own parent server on port 7863.

Geometry travels as a bounded gzip document through Gradio-managed file delivery;
interaction stays local after the initial fetch. This cache is distinct from
retained release artifacts and does not add snapshot export/reopen functionality.

The remaining component files are reserved placeholders, outside this cut.

| Component | Intended responsibility |
| --- | --- |
| [GeometryViewport](frontend/src/components/GeometryViewport/GeometryViewport.svelte) | Geometry rendering, camera, picking, clipping, and visibility. |
| [ScalarControls](frontend/src/components/ScalarControls/ScalarControls.svelte) | Scalar field selection, palette, and display range. |
| [ScalarLegend](frontend/src/components/ScalarLegend/ScalarLegend.svelte) | Scalar field domain, scale, and units. |
| [MetricTable](frontend/src/components/MetricTable/MetricTable.svelte) | Computed metric rows and selection preview or pinning. |
| [EntityTable](frontend/src/components/EntityTable/EntityTable.svelte) | Entity filtering, visibility, and selection. |
| [PrimitiveTree](frontend/src/components/PrimitiveTree/PrimitiveTree.svelte) | Assembly or fitted-primitive hierarchy and membership selection. |
| [TraceTable](frontend/src/components/TraceTable/TraceTable.svelte) | Computed trajectory rows, termination states, and selection. |
| [UVViewport](frontend/src/components/UVViewport/UVViewport.svelte) | UV chart navigation and linked entity highlighting. |
| [OperationControls](frontend/src/components/OperationControls/OperationControls.svelte) | Operation parameters and explicit submission. |
