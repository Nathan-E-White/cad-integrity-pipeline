# Motorcycle paths for mesh healing: feasibility and implementation boundary

## Decision brief

A Python motorcycle-path implementation is feasible **as a deterministic,
topological quad-layout partitioner**.  It should be introduced as a read-only
classifier and cut-plan producer for an already admitted, oriented 2-manifold
quadrilateral mesh.  It is not a general mesh-healing algorithm: it neither
welds gaps, resolves geometric self-intersections, converts triangles to quads,
nor reconstructs missing material or CAD intent.

That distinction is not pedantry.  The defining paper partitions *semi-regular
quadrilateral meshes* into structured submeshes; its stated applications are
canonical matching and compression, not repair of an arbitrary defective
surface. [1]  The inputs presently supplied by this repository's pathological
fixture pack are indexed triangles, so they are appropriate rejection and
pipeline-boundary controls, not positive fixtures for this capability.

The smallest defensible first delivery is therefore:

1. admit only an indexed, connected or component-separated, orientable
   quad 2-manifold with simple four-vertex faces;
2. calculate paths and a cut-edge set without changing coordinates or mesh
   connectivity;
3. return per-path termination evidence and the induced face components; and
4. label every failure of those preconditions `rejected` or `needs_review`.

If the product requirement is instead geometric mesh healing, use a separate
repair path backed by a geometry kernel.  CGAL, for example, deliberately
separates combinatorial polygon-mesh validity from geometric defects and has
specific facilities for self-intersection detection, degeneracy, boundary
stitching, and repair. [4]  A motorcycle graph is not a cheaper spelling of
those operations.

## What the construction is

Eppstein, Goodrich, Kim, and Tamstorf adapt the earlier geometric motorcycle
graph to a quad mesh.  Starting from extraordinary vertices, conceptual
motorcycles traverse the mesh through opposite edges of successive quads.  A
path stops at a boundary or a previously traced path; the resulting cut graph
partitions the mesh into structured pieces.  The authors define the input as
an orientable manifold quad mesh: every edge has one or two incident quads,
shared edges have opposite orientation, and each vertex star is connected.
An interior vertex is ordinary at degree four; a boundary vertex is ordinary
at degree at most three. [1][2]

The output is a **combinatorial decomposition**, not a new surface.  Its
pieces have no extraordinary vertices, and the paper characterizes structured
pieces as disks, annuli, or tori. [2]  The canonical construction is useful
because isomorphic copies obtain the same partition; minimizing the number of
pieces beyond that construction is NP-hard, so a first implementation should
not promise globally minimum cuts. [1]

The related 3D motorcycle *complex* is a different algorithm and a different
input class: it decomposes a hexahedral mesh or a volumetric seamless
parameterization into cuboid blocks. [3]  Do not route a surface-triangle or
B-rep request into it merely because all three words sound pleasantly
mechanical.

## Recommended Python algorithm

### Admission before path tracing

Build a pure-topological `QuadMesh` view from immutable arrays.  Reject before
tracing if any of these fail:

* a face is not a simple ordered 4-cycle, indices are out of range, or a
  duplicate/zero-length topological edge occurs;
* an undirected edge has other than one or two incident faces;
* two incident faces use their shared edge with the same direction;
* a vertex's incident-face fan is disconnected (a pinched/nonmanifold vertex);
* the requested component policy does not permit multiple components; or
* a caller asks the path layer to infer geometry-dependent adjacency.

Record the exact source face, vertex, and edge IDs in every diagnostic.  Do
not silently orient, weld, split, triangulate, or delete at this layer: those
are independent mutations with independent authorization and evidence needs.

### Trace state machine

Use directed halfedges/darts rather than geometric ray tests.  With a current
directed incoming edge in a quad, `next` twice selects its opposite edge; the
twin identifies the neighboring face.  A trace advances from one directed
edge to the opposite directed edge of its next face.  Its state is one of
`active`, `stopped_boundary`, `stopped_trace`, `stopped_singularity`, or
`rejected_limit`.

Launch a deterministic set of traces from the directed edges incident to each
extraordinary vertex.  Process one topological step per active trace in rounds
or through a priority queue ordered by `(step, source_vertex_id,
source_halfedge_id)`.  At each prospective step:

* stop at a boundary;
* stop when the target directed/undirected edge is already owned by a prior
  trace under the documented tie rule;
* resolve simultaneous arrivals as one explicit collision event, never by
  accidental Python list order;
* otherwise mark the traversed edge as a cut candidate and advance through
  the opposite edge.

The resulting `cut_edge_ids` form the public result.  Face components of the
dual graph after removing those adjacencies are the induced patches.  Validate
each component again: its vertices must be ordinary under its local boundary
status, its incidence must remain a 2-manifold, and its Euler/boundary summary
must agree with its reported disk/annulus/torus classification.  The last
check is an invariant, not a claim that the embedded surface has become free
of intersections.

### Data structures and resource limits

Keep these compact, serializable records:

| Record | Essential fields | Purpose |
| --- | --- | --- |
| `QuadMesh` | `faces`, `halfedge_origin`, `twin`, `next`, `face`, stable IDs | topology and O(1) crossing |
| `VertexStar` | incident halfedges in cyclic order, boundary flag, degree | admission and extraordinary classification |
| `Trace` | source, current halfedge, traversed edge IDs, termination, blocker | reproducible path evidence |
| `CutPlan` | ordered traces, cut-edge bitset, collision log, patch face IDs | read-only proposed partition |
| `MotorcycleBudget` | max faces/halfedges/traces/steps/records | fail-closed resource control |

Use integer IDs and a Boolean/byte edge-owner array; do not scan all faces to
find a neighbor at every hop.  Put a strict upper bound on total successful
advances (no more than a documented multiple of directed halfedges) and on
stored trace records.  An unexpected revisit is a rejected invariant breach,
not an excuse to loop until the laptop develops a personality.

## Robustness and geometry boundary

For the stated first scope, the algorithm needs no floating-point predicate:
all decisions are incidences, cyclic orders, integer IDs, and deterministic
tie keys.  This is the principal attraction of a Python implementation.

Coordinates become relevant only if an upstream stage wants to establish
geometric validity, detect crossed faces, compare a displacement budget, or
derive a quad layout from a triangle mesh.  Do not use NumPy tolerances as a
substitute for that work.  CGAL explains why geometric control flow requires
reliable predicates: ordinary floating-point arithmetic can produce mutually
contradictory decisions; its kernels use exact predicates and, where needed,
filtered/exact constructions. [5]  Its mesh documentation also notes that a
combinatorial 2-manifold can still have self-intersections or degenerate
faces. [4]

The implementation boundary should therefore be explicit:

| Need | Suitable action | Not established by motorcycle paths |
| --- | --- | --- |
| Quad topology/layout | Pure Python halfedge tracer | geometric validity or physical healing |
| Triangle-soup orientation, stitching, hole filling | dedicated repair adapter | a valid quad manifold |
| Triangle self-intersection | robust geometry-kernel predicate | no intersections after a topological cut |
| Geometric intersection splitting/Boolean result | exact/adaptive predicate **and** controlled construction path | continuous displacement or CAD-intent recovery |

If a future geometric repair adapter is needed, call a pinned native process
or a reviewed binding, preserve the input and exact request, bound CPU/memory,
then re-import and revalidate its output.  CGAL's documented `does_self_intersect`
and `self_intersections` operate on triangle meshes; that is a useful
capability reference, but not a Python motorcycle-path dependency. [4]

## Dependency and licensing choices

| Option | Recommendation | License / caveat |
| --- | --- | --- |
| Small in-repo pure-Python tracer, standard library plus existing NumPy arrays | **Recommended** for the topology-only scope | Keep repository licensing and provenance; algorithmic ideas are not code reuse. |
| OpenMesh-backed halfedge adapter | Optional only if a maintained Python binding is already accepted | OpenMesh 4+ is BSD-3-Clause; validate binding availability/API separately. [6] |
| libigl Python bindings | Useful for array-oriented diagnostics or exact predicate access, not for the motorcycle algorithm itself | Bindings expose NumPy arrays and an `igl.predicates` module; copyleft modules are separately identified, so dependency selection must be reviewed. [7] |
| CGAL native adapter | Use only for the later geometric-repair boundary | Packages vary between LGPL/GPL; CGAL says higher-level algorithms are commonly GPL and offers commercial licensing. Confirm the exact package and distribution model before adoption. [8] |
| `Hassan-Bahrami/MotorCycleGraph` | Reference-only; do not vendor or depend on it | It advertises an MIT Python quad-partitioning prototype, but its exposed core performs face scans and visualization during construction, rather than providing an admitted, bounded, testable library seam. [9][10] |

The last repository is evidence that a Python prototype exists, not evidence
of correctness, robustness, maintenance, or compatibility with this project.
Reimplement from the cited specification and test oracle; do not copy code.

## Validation plan and fixtures

Add generated, small indexed **quad** fixtures; retain the current triangle
fixtures unchanged as negative controls.  For every positive fixture, assert
the complete cut plan (stable IDs, trace order, termination reason, and patch
face memberships), then independently verify the induced components.

| Fixture family | Required assertion |
| --- | --- |
| Regular rectangular quad disk, annulus, and torus | no extraordinary launch where applicable; correct component type and deterministic no-op/cut plan |
| One interior valence-3 or valence-5 singularity | exact launched directions, expected paths, structured patches |
| Boundary extraordinary vertex | correct boundary termination and no path outside the mesh |
| Two simultaneous paths targeting one edge/vertex | explicit tie/collision record independent of insertion order |
| Long strip and repeated pattern | bounded step count, no duplicate cut edge, linear-ish storage accounting |
| Reindexed vertices/faces and cyclic rotations of every face | isomorphic result after inverse ID mapping |
| Global orientation reversal | same undirected cut graph after the documented normalization |
| Triangle, mixed polygon, repeated-index quad, nonmanifold edge, pinched star, inconsistent shared winding | admitted failure with no candidate and preserved input |
| Geometrically self-crossing but combinatorially valid quad mesh | either upstream geometric gate rejects it, or the trace report says geometry unchecked; never success as "healed" |

Use fixed-seed property tests to generate planar grid complexes with controlled
singularities.  Independently test the local patch condition rather than
having the tracer certify itself.  Apply mutation testing to collision,
opposite-edge, boundary, and budget branches; add a parser fuzz target only
for pure-Python import/admission code, not for in-process native geometry.

## Limits that must remain in the public contract

* It accepts quad 2-manifolds, not arbitrary polygon soups, triangles, STEP
  B-reps, or hexahedral volumes.
* It proposes a combinatorial cut layout; it does not mutate or heal geometry.
* A successful structured-patch report is not watertightness, lack of
  self-intersection, CAD validity, simulation readiness, or recovered design
  intent.
* Canonical does not mean minimum number of patches; the cited optimization
  problem is NP-hard. [1]
* The 3D motorcycle complex and a 2D surface motorcycle graph should stay
  separate capabilities with separate inputs, tests, and claims. [3]

## Sources

1. D. Eppstein, M. T. Goodrich, E. Kim, and R. Tamstorf, [*Motorcycle Graphs: Canonical Quad Mesh Partitioning*](https://disneyanimation.com/publications/motorcycle-graphs-canonical-quad-mesh-partitioning/), Symposium on Geometry Processing, 2008.  Publisher record: [DOI 10.1111/j.1467-8659.2008.01288.x](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-8659.2008.01288.x).
2. Eppstein et al., [author/publisher PDF](https://diglib.eg.org/bitstreams/417e3d00-227c-432b-b84e-fa1638e84084/download), especially the input mesh definition, structured-mesh classification, and cut construction.
3. H. Brückler, O. Gupta, M. Mandad, and M. Campen, [*The 3D Motorcycle Complex for Structured Volume Decomposition*](https://graphics.cs.uos.de/papers/3D_Motorcycle_Graph_EG2022.pdf), *Computer Graphics Forum* 41(2), 2022; [DOI record](https://onlinelibrary.wiley.com/doi/abs/10.1111/cgf.14470).
4. CGAL Project, [Polygon Mesh Processing User Manual](https://doc.cgal.org/latest/Polygon_mesh_processing/index.html), version 6.2.1, accessed 2026-09-15.
5. CGAL Project, [Robustness Issues](https://doc.cgal.org/latest/Manual/devman_robustness.html), version 6.2.1, accessed 2026-09-15.
6. RWTH Aachen, [OpenMesh license](https://www.openmesh.org/license/), accessed 2026-09-15.
7. libigl Project, [libigl Python bindings](https://libigl.github.io/libigl-python-bindings/), accessed 2026-09-15.
8. CGAL Project, [CGAL License](https://www.cgal.org/license.html), accessed 2026-09-15.
9. Hassan Bahrami, [MotorCycleGraph repository](https://github.com/Hassan-Bahrami/MotorCycleGraph), accessed 2026-09-15.
10. Hassan Bahrami, [prototype `Alg.py`](https://github.com/Hassan-Bahrami/MotorCycleGraph/blob/main/Alg.py), accessed 2026-09-15.
