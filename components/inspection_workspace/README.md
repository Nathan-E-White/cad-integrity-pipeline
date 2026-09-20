# Inspection workspace placeholders

Directory placeholders for the orthogonal Svelte components proposed in the
integrated architecture review. Each component has a comment-only Svelte file.
Interfaces, rendering, backend integration, packaging, and application wiring
are not implemented.

These components are intended for composition within an inspection workspace.
The existing Topological Delta Audit and Verification Grid remain separate.

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
