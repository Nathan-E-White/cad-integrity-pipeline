# Slice 6: conforming BRep realization

Implemented from the handoff at 8f01063. The user confirmed the realization seam
and authorized native reuse. See DESIGN.md for the concrete scope.

## Result and ownership

`cad_integrity.brep.realize(shape, policy=..., limits=...)` copies and meshes a
millimetre native shape in the installed OCP runtime. It returns diagnostics and
an optional owned realized surface. Copy history associates native faces, edges
and vertices; copied occurrences retain their orientation and location. Edge
polygon parameters must agree exactly across occurrences before sharing samples.
Periodic branches are selected using the edge orientation within the forward face.

`cad::brep` receives copied numeric evidence through a private binding. It uses
native identity keys to consolidate nodes and checks coordinate agreement,
triangle nondegeneracy, complete native edge coverage, opposite paired orientation
and manifold vertex links. No coordinate welding, source mutation, repair or
foreign TopoDS pointer is involved. Dynamic linkage of the extension contains
libc++ and libSystem, with no OCCT libraries.

A private shared storage header permits both surface preparation and realization
to construct the same immutable Discretization owner. Operators and charts retain
that owner. Native face/edge IDs have an explicit domain; native vertex IDs are
separate from derived mesh vertex ordinals. The host result retains no OCCT handle.
This reuses the qualified storage/operators without treating native trimmed faces
as polygonal cells or adding a second mesh owner.

## Distinguishing qualification

- Box caller fixture failed on the missing module, then passed with 8 shared
  vertices, 12 triangles, 6 source faces, correct volume and existing operators.
- Cylinder admission passed; sphere admission exposed OCCT triangles whose pole
  edge has distinct UV nodes but one native vertex. Only declared degenerate
  native edge sides permit recorded removal (2 triangles in the sphere fixture).
  Ordinary degenerate triangles still prevent admission.
- Supporting-surface projection of triangle centroids replaces arbitrary averaging
  of UV coordinates at poles. Normal orientation and sampled surface/curve
  deviation checks remain explicit and may conservatively refuse geometry.
- An orphan native vertex initially escaped whole-shape admission. Complete native
  entity ownership now prevents admission. A repeated indexed native face
  occurrence similarly exposed silent deduplication and now fails closed.
- Host fixtures cover holed planar faces, disjoint coincident sheets, source cache
  isolation, copied translation/reversal, retained lifetime, immutable projections,
  cylinder/sphere/torus topology and analytic volume, all declared budget classes
  and sampled-deviation refusal.
- Native public-interface fixtures exercise retained surface lifetime/operators,
  disagreement, incomplete edge coverage, reversed incidence, orphan identity,
  nonfinite geometry, invalid indices and all four numerical budget classes.

## Verification

- Full root suite using the packaged extension: **410 passed**, no skips,
  24.36 seconds, 91% aggregate statement coverage.
- Native Release and ASan/UBSan workflows: **9/9 passed each** after final native
  edits. Source inventories continue to exclude Point3D and motorcycle prototypes.
- Isolated CPython 3.13 sdist and wheel build succeeded, with the wheel built from
  the sdist. Required native sources and the private shared storage header are in
  the source archive; the wheel contains the host module, stub and extension.
- Wheel installed outside the checkout: **39 passed**, no skips (9 BRep, 15
  surface, 15 UV). Module and extension paths resolve in the temporary environment.
  This shares qualified Pixi dependencies through system site packages; it is not
  an independent platform/dependency qualification.
- Changed Python modules and new tests/benchmark pass Ruff; changed host modules
  pass mypy. Root Ruff has 7 pre-existing findings in `mesh_motorcycle.py`; root
  mypy reports its pre-existing undefined `_gen_synthetic_mpaths`. That file is
  unchanged. Root lint/typechecking are therefore not claimed green.
- Independent standards review: **0 hard breaches, 0 actionable smells**.
- Independent spec review: **0 actionable findings**. The reviewer additionally
  smoke-tested cone apex, torus and sphere admission. Reviews were source reviews
  with those limited extra checks, not independent execution of the entire suite.

## Measurement and limits

`benchmark.py` records seven-run medians in benchmark.json. Local end-to-end times
were 2.25 ms for the box, 7.99 ms for the cylinder and 30.95 ms for the sphere.
Sphere extraction/geometry checking was 27.49 ms and binding qualification 1.08 ms.
Binding timing includes input copying and result export; total also includes numeric
conversion and immutable host projection. These are measured phase costs, not a
native-only benchmark, speedup claim or peak-memory measurement.

The binding README defines logical accounting and exclusions. Native triangle
nondegeneracy requires a cross-product norm above 1e-14 after normalizing edge
components by their largest magnitude. Extreme or skinny geometry may be refused.
Mesher/copy allocations and wall time are outside extraction and numerical budgets.

Deviation is sampled on supporting surfaces and curves. The result does not prove
continuous Hausdorff error, exact trim coverage, global injectivity, absence of
self-intersection, element quality or simulation readiness. OCCT supplies the face
meshing; the exercised fixtures qualify the recorded cases. No browser protocol,
viewer replacement, automatic repair, export, database or GPU work is included.

## Continuation

The main sequence now reaches canonical quad tracing, which requires its own
admitted mode and event/prefix contract. NURBS binding and Delaunay construction
remain independent branches when real callers are selected. Their declaration or
existing kernel status must not be confused with completed integration.
