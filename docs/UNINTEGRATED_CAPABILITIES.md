# Existing capabilities awaiting integration

This register records capabilities already present in the repository that have
not yet been integrated into the parent application's intended workflows. An entry
acknowledges existing implementation; it does not authorize integration or imply
that the parent workflow has been validated.

Add capabilities here as they are identified. Keep links to their implementations
and distinguish existing behavior from the work needed to integrate it.

## Triangle-quality computation

Status: implemented; awaiting integration into the polygonal inspection workflow.

- Existing implementation: [`mesh_quality` and `MeshQualityReport`](../src/cad_integrity/metrics.py).
- Available results: triangle areas, aspect ratios, mean ratios, skewness, and
  degenerate-triangle IDs.
- Existing projection: [`from_triangle_reports`](../integration/mesh-diagnostics-seam/python/cad_mesh_inspector/adapters.py)
  consumes the host quality report and supplies mean-ratio and aspect-ratio fields
  plus a degenerate-triangle selection.
- Integration work: compute and retain quality results for the intended geometry
  snapshots, preserve triangle/source-polygon mapping, and project those results
  into the inspector. Choose explicit area tolerances and comparison domains.
- Preserve the host aspect-ratio definition, longest edge / (2√3 × inradius),
  rather than substituting another metric with the same general name.

## Scalar fields

Status: implemented in the supplied inspector; awaiting parent-app integration.

- Existing contract: [`ScalarField`](../integration/mesh-diagnostics-seam/python/cad_mesh_inspector/contracts.py)
  carries face-associated values, a display domain, units, and whether higher or
  lower values are preferable. Values may be null.
- Existing presentation: [`InspectorToolbar`](../integration/mesh-diagnostics-seam/src/components/InspectorToolbar.svelte),
  [`ScalarLegend`](../integration/mesh-diagnostics-seam/src/components/ScalarLegend.svelte),
  and [`SurfaceLayer`](../integration/mesh-diagnostics-seam/src/render/SurfaceLayer.ts).
- Integration work: supply backend-computed fields through the parent projection,
  keep values aligned with displayed triangles, handle unavailable values, and
  use shared domains and units for matching fields in linked comparisons.
- Current coverage is face-associated scalar data. Vertex fields, vector fields,
  and tensor fields are separate future extensions, not existing capabilities
  acknowledged by this entry.

Both entries are tracked separately from the initial projection of existing
polygonal topology results.
