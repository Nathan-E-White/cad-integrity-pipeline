# MAT Voronoi data-structures research

**Scope.** This note selects the transient and persisted representations for a
read-only, boundary-sampled approximate medial-axis transform (MAT). It is
evidence for a CGAL-backed Delaunay/Voronoi bridge, not an assertion that a
sampled Voronoi diagram is an exact medial axis of a trimmed B-rep.

## Recommended representation

Use `CGAL::Delaunay_triangulation_3` as the bridge's *transient* data
structure. CGAL separates geometric triangulation behavior from a
`Triangulation_data_structure_3` (TDS) holding the combinatorics. The TDS
stores vertices and 3-cells only: a finite cell has four vertex handles and
four neighbour-cell handles, with neighbour `i` opposite vertex `i`; facets
and edges are implicit descriptors. This gives direct local traversal without
materialising a general-purpose Voronoi mesh. [1][2]

The bridge should emit a flat, immutable snapshot rather than expose CGAL
handles:

| Record | Canonical identity | Required contents |
| --- | --- | --- |
| Boundary sample | `sample_id` fixed before bridge entry | normalized coordinates; original CAD coordinates; face/edge/trim provenance; sampling rule and source fingerprint |
| Finite Delaunay cell | sorted four `sample_id`s | ordered vertices as emitted, finite-neighbour cell keys, degeneracy/cospherical disposition |
| Raw medial node | supporting finite-cell key | CGAL circumcenter, sampled Delaunay radius, four supporting sample IDs |
| Raw medial edge | sorted pair of retained node IDs | shared-facet's sorted three sample IDs; sampled in-solid checks |
| Verified node/edge | raw identity plus verification revision | OCP clearance/membership/contact evidence and an accepted, rejected, or indeterminate disposition |

The first two records are enough to reproduce the computational input. The
latter records are a sparse derived medial complex, not a serialization of the
entire Voronoi tessellation. Store them in the existing NPZ/JSON evidence
artifact shape; do not persist a CGAL object or its handles.

## Delaunay-to-Voronoi extraction

For each finite Delaunay cell, `dual(cell)` is the circumcenter of its four
vertices. For a Delaunay facet, the dual is a segment when both incident cells
are finite and a ray when either incident cell is infinite. Accordingly, an
initial MAT graph has a raw node per finite Delaunay cell and a raw edge only
for a shared finite facet whose two node candidates survive OCP validation.
The three vertices of that facet are the support provenance for the edge. [3]

This is intentionally a graph projection of the Voronoi complex. It is useful
for a first visual/evidence artifact, but it does not retain Voronoi faces or
volumes and cannot represent the full two-dimensional medial sheets. If a
later feature requires sheet topology, add a separately-versioned complex
record whose cells are derived from the same canonical Delaunay incidence;
do not overload the graph edge schema.

CGAL represents the outside using an auxiliary infinite vertex, making every
facet incident to two cells. Infinite cells must not create MAT nodes, rays
must not be serialized as finite MAT edges, and no geometric predicate should
be evaluated on the infinite vertex. [1][2]

## Robustness, provenance, and identity

Use `Exact_predicates_exact_constructions_kernel` (EPECK) in the bridge: it
provides exact predicates *and* exact constructions from `double` Cartesian
inputs. Exact constructions matter here because MAT candidates consume
circumcenters, not merely Delaunay combinatorics. CGAL recommends EPECK when
the dual must be exact, but documents a cost of at least 4--5 times EPICK in
some settings. Make kernel selection and bridge resource usage recorded
specification/evidence, rather than assuming exact construction is free. [1][4]

Attach the preassigned `sample_id` to CGAL vertices through
`Triangulation_vertex_base_with_info_3`; an analogous cell-info base is
available if bridge-local flags are useful. These `info()` fields and cached
circumcenters are not durable evidence: CGAL documents that stream I/O drops
additional info, and its circumcenter-cache class also drops its cache. [5][6]
Therefore serialize the application records above explicitly.

Do not make a handle, iteration position, or insertion order a product ID.
Range insertion may spatially sort input, and equal input points produce one
vertex with one of the supplied info values. Before bridge entry, canonically
sort samples and deduplicate exact normalized coordinate triples while
retaining a list of all collapsed source-provenance IDs. A duplicated sample
without this reduction makes ownership arbitrary. [3]

Five co-spherical points make a mathematical Delaunay triangulation
non-unique. CGAL selects a unique triangulation using symbolic perturbation;
record this as a deterministic implementation choice, not as proof that the
resulting medial complex is uniquely determined by the samples. Lower affine
dimension (`dimension() < 3`) must be a typed refusal for this 3D MAT bridge.
[1][7]

## Resource and lifecycle policy

Build once, call `is_valid()` for bridge diagnostics, extract the immutable
snapshot, then destroy the triangulation. `is_valid()` checks combinatorial
and geometric embedding validity plus empty circumspheres; it is not a proof
of B-rep membership, maximality, or MAT correctness. OCP remains authoritative
for each candidate's inside/outside state and closest-boundary evidence. [3]

Budget by both samples and finite cells. CGAL documents a quadratic worst case
for 3D Delaunay triangulations, while typical surface distributions can be
near-linear. For volumetric distributions it reports about 6.7 cells per
vertex, and a 64-bit Delaunay benchmark of roughly 519 bytes per input point;
these are planning observations, not guarantees for CAD boundary samples.
The MAT specification should therefore declare `max_samples`, `max_cells`,
`max_bridge_bytes`, and `max_nodes/edges`, with an exhausted budget returning
`needs_review`/incomplete evidence rather than a partial result labelled
complete. [1]

The optional cached-circumcenter cell base can avoid recomputation during one
extraction pass, but it increases transient memory and its cache is not
serializable. Use it only after profiling shows dual construction dominates;
it changes no durable interface. [6]

## Conclusions

The deep module should expose one evidence-producing MAT operation. Its CGAL
adapter owns exact Delaunay predicates, TDS traversal, finite dual extraction,
and bridge-local provenance attachment. Callers receive stable sample/cell/node
records and never learn CGAL handles, infinite-cell rules, or facet index
conventions. This concentrates numerical and ABI risk in one place while
keeping the persisted MAT artifact reproducible and independently verifiable
against the source B-rep.

Qhull was not selected: its own documentation maps Delaunay facets to Voronoi
vertices and provides diagram traversal, but CGAL provides the exact-predicate,
custom-info, finite/infinite-cell, and kernel choices needed by this qualified
MAT bridge. [8]

## Sources

1. CGAL, [3D Triangulations manual](https://doc.cgal.org/latest/Triangulation_3/index.html), CGAL 6.2, accessed 2026-09-18.
2. CGAL, [TriangulationDataStructure_3::Cell](https://doc.cgal.org/Manual/latest/doc_html/cgal_manual/TriangulationDS_3_ref/Concept_TriangulationDataStructure_3--Cell.html), accessed 2026-09-18.
3. CGAL, [Delaunay_triangulation_3 reference](https://doc.cgal.org/latest/Triangulation_3/classCGAL_1_1Delaunay__triangulation__3.html), CGAL 6.2, accessed 2026-09-18.
4. CGAL, [Exact_predicates_exact_constructions_kernel](https://doc.cgal.org/Manual/3.1/doc_html/cgal_manual/Kernel_23_ref/Class_Exact_predicates_exact_constructions_kernel.html), accessed 2026-09-18.
5. CGAL, [Triangulation_vertex_base_with_info_3 reference](https://doc.cgal.org/latest/Triangulation_3/classCGAL_1_1Triangulation__vertex__base__with__info__3.html), CGAL 6.2, accessed 2026-09-18.
6. CGAL, [Delaunay_triangulation_cell_base_with_circumcenter_3 reference](https://doc.cgal.org/latest/Triangulation_3/classCGAL_1_1Delaunay__triangulation__cell__base__with__circumcenter__3.html), CGAL 6.2, accessed 2026-09-18.
7. CGAL, [3D Triangulations manual, degeneracy discussion](https://doc.cgal.org/5.2.1/Triangulation_3/index.html), accessed 2026-09-18.
8. Qhull, [qvoronoi data and conventions](https://qhull.org/html/qvoronoi.htm), accessed 2026-09-18.
