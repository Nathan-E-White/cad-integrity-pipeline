# Slice 6: conforming BRep realization

Starting point: 8f01063. The user confirmed the realization test seam and authorized
reuse of native code. The public host operation is `cad_integrity.brep.realize`:
a native shape, explicit millimetre policy and limits produce diagnostic assessment
and an optional admitted realized surface. The native numerical boundary consumes
owned extracted evidence; it accepts no OCCT pointers.

## Runtime and reuse

Use BRepBuilderAPI_Copy in the installed OCP runtime, with geometry copied and mesh
caches excluded. Resolve face/edge/vertex correspondence by copy history, retaining
occurrence orientation and location. Mesh the whole copy with OCCT. Extract each
oriented edge occurrence's PolygonOnTriangulation, including both seam branches.
Native edge identity and matching curve-parameter sequences establish shared node
identity. Native vertex identity establishes endpoints and degenerate poles.
Coincident coordinates never establish topology. The source must remain unmodified
by the caller during the synchronous operation; returned results own no OCP handles.

The existing surface storage, operators and chart qualification are reused. A
realized surface retains that single owner plus native correspondence. Derived
vertex ordinals remain distinct from native vertex ordinals. Source domain is
explicit; native faces are not admitted polygonal cells. No foreign OCCT ABI,
additional mesher, serialization format or second triangle-storage owner is needed.

## Admission and evidence

OCP extraction checks source/copy identity, BRep validity, complete face meshing,
finite XYZ and projection parameters, edge sample parameter agreement, and sampled surface/curve deviation.
C++ consolidates only declared identities, checks coordinate agreement, triangle
nondegeneracy, complete edge-use correspondence, opposite paired orientation and
manifold vertex links. Every unmatched triangle side must be a native boundary.
Every native edge segment must have its declared incidence. A failed check returns
diagnostics without an admitted surface; budgets fail explicitly.

Native face normals and sampled supporting-surface deviations are checked by
projecting triangle centroids. Declared degenerate native edge sides permit only
recorded pole-triangle removal. These are sampled evidence, not a continuous Hausdorff bound, global
intersection test, engineering element-quality certificate or simulation readiness.
The scope includes open surfaces, holes, disconnected sheets, periodic seams and
poles when all checks pass. Unsupported topology or numerical ranges fail closed.

## Limits and qualification

Limits cover extracted faces/edges/vertices/nodes/triangles/edge samples, native
logical input/workspace/work/output and host numeric projections. OCP copy and
mesher internal allocations and elapsed time are not bounded by these counters.
Read-only numerical use is independent; source mutation during copying is excluded.

Test through host `realize` and native `realize`/returned surface interfaces: box
shared edges, cylinders and spheres, translated/reversed occurrences, holed faces,
coincident independent sheets, copy/lifetime ownership, failed admission, budget
refusal and existing surface operators. Keep independent analytic/topology oracles.
Measure copy/mesh/extraction/native qualification separately where practical.
No display substitution, repair, browser changes, export, database or GPU work.
