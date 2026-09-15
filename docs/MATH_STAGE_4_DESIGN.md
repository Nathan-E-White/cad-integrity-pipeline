# Stage 4 validated polygonal-cell view

`PolyhedralBRep` remains the immutable raw carrier. It is intentionally
constructible when its cells are malformed, duplicated, collapsed, pinched, or
unused, because those facts are diagnostic evidence. It no longer constructs a
chain complex itself.

`admit_polygonal_cells(raw)` is the Stage 4 seam. It returns complete,
deterministic combinatorial admission evidence. An admissible result exposes a
`ValidatedPolygonalCells` view and only that view can construct the restricted
cellular chain complex. An inadmissible result has no view and retains labeled
face, incidence/link, duplicate, collapsed, and unused-entity diagnostics.

`BRepHomologyStitchAnalyzer` consumes this admission result before homology;
`RepairPipeline` consumes the analyzer's resulting admission facts before a
transition. The two adapters therefore cannot silently disagree about whether
a raw carrier authorizes cellular topology work.

The view represents simple polygonal disk faces and straight-edge incidence. It
does not establish a CAD embedding, planarity, self-intersection freedom,
outwardness, nesting, material volume, or physical certification. Boundary and
orientation remain reportable/repairable combinatorial conditions, rather than
cell-admission failures.
