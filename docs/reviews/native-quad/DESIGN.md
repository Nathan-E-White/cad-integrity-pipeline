# Slice 8: owned quad motorcycle tracing

Baseline: `a854ad1`. This activates `quad_tracing.hpp/.cpp` and an installed
`cad_integrity.quad.prepare_quad_patch(mesh).trace()` caller. Independent NURBS
binding and Delaunay construction branches remain unfinished.

## Reuse decision

The existing `PolygonalInput`, `PolygonalAssessment`, signed coedge loops and
manifold/link qualification are reused. A const `PolygonalAssessment::input()`
accessor exposes the retained snapshot. `AdmittedQuadPatch` retains that same
assessment owner, adding incident edges, an oriented edge rotation, boundary
flags and canonical launches. It neither creates a second geometry owner nor
promotes a triangulation to a quad mesh. The existing cellular incidence matrices
remain retained as part of the assessment; their cost is included.

The two `motorcycle_graph_*` prototypes were inspected. Their trail/event/queue
organization informs the implementation, but their face-interior tangent-angle
stepping, epsilon intersection test, speculative segments and demonstration I/O
are not qualified canonical quad operations. Their translation units remain
excluded. No BVH is needed: exact vertex/edge identities resolve this discrete
collision domain. No runtime strategy has two qualified implementations here.

## Source and admission

The original [2008 paper, sections 2 and 5](https://media.disneyanimation.com/uploads/production/publication_asset/36/asset/motorcycle_sgp_2008.pdf)
is the algorithm source. Oriented pure quads must satisfy the existing cellular
admission, consistent supplied winding, a simple edge graph, and face intersection
conditions: two quads share at most one edge or one vertex. Disconnected components
are handled independently, an explicit extension of the paper's connected input.

Coordinates must be finite and edges noncollapsed under existing admission.
This is a combinatorial surface contract: no planarity, embedding, self-intersection,
physical speed, feature field, global parameterization, or simulation-quality claim.
No winding correction, coordinate welding or automatic mesh repair occurs.

## Public seams and rules

- `AdmittedQuadPatch::create(PolygonalAssessment, Limits)` adds the quad guarantee
  and retains its owner. Python `prepare_quad_patch(PolyhedralBRep, limits=...)`
  owns numeric copies before releasing the GIL for assessment/admission.
- `trace_quads(patch, seeds, limits)` returns owning evidence. Python `patch.trace()`
  uses all canonical launches: one directed branch along every incident edge of
  an extraordinary vertex. Interior degree unequal to four is extraordinary;
  boundary degree greater than three is extraordinary. Boundary corners do not launch.
- Supplied seeds have unique nonnegative IDs and unique directed launch incidences.
  All launch simultaneously at zero and traverse one edge per unit time.
  Public C++ seed/edge/vertex identities use distinct domain types; failures
  retain an entity domain and ordinal. The mode is explicitly noncanonical unless the normalized full records equal the
  canonical launch set. A supplied trace reaching an unlaunched extraordinary
  vertex stops with `extraordinary`; it does not invent an opposite edge.
- Interior continuation takes the opposite edge in the supplied oriented cyclic
  order. A clockwise branch of a perpendicular pair stops; the other continues.
  Opposing pairs stop, as do three/four-way simultaneous arrivals. Boundaries and
  previously deposited vertices stop arrivals. Source exemption applies only at
  launch; returning to one's own source or deposited prefix is self-collision.
- Opposite traversal of an edge meets at its midpoint after half a time unit.
  Exact uint64 half-step times avoid epsilon equality. A priority queue schedules
  only the next committed continuation, never an unlimited predicted path.
- Every simultaneous time group is decided against the same prior deposition
  state and committed atomically. Events are ordered by time then semantic seed
  ID for presentation. ID order does not decide geometric collision outcomes.
  Multiple blockers have a deterministic representative; group participants are
  all retained as event records with equal time and carrier. Earlier depositor
  identity and time remain available after that particle terminates.
- Segment evidence retains source edge and vertex identities. `to_vertex == -1`
  means a midpoint on that segment's edge, not a new vertex ID. Boundary edges are
  retained separately on the patch and are part of the graph even with no launches.
- A supported trace budget stop returns the previously committed evidence, unfinished
  seeds, stop code and optional last committed time. In-flight uncommitted segments
  are not fabricated. An allocation failure or invalid request is an error.

A finite mesh cannot produce endless admitted unit-step motion: a surviving
particle must reach an unvisited regular vertex each step, or stop at a boundary,
source, previous track, or collision. A torus return is reported as self-collision,
not physical periodicity, graph-cycle certification, or budget exhaustion.

## Scope

The caller supplies an authoritative owned polygonal model. The output is reusable
numerical evidence and line coordinates, not a new viewer protocol, a repair
candidate, an exported CAD object, or a constructed schematic partition. Chart
tracing, raw fields, path simplification, database persistence and GPU computation
remain deferred. Existing prototype UI helpers remain separate and unchanged.
