# Slice 5 design: owned UV location with complete candidate resolution

Proposal, 22 September 2026. Inspected clean checkout `38c3014`.
This is design work. Slice 4's implementation and measurements are recorded in
`../native-surface/IMPLEMENTATION.md`; they are not new validation of this slice.

## Decision

Implement the existing `cad::uv::Locator` scaffold as one deep, in-process module.
It retains a native `surface::AdmittedChart`, builds a private double-precision
2D index, and resolves every accepted triangle for each query. Return ordered
location evidence and an XYZ value only when the completed candidate search
supports one. The installed Python caller consumes the chart already produced by
`cad_integrity.surface`; it does not rebuild triangulation or qualify UV again.

The implementation record explicitly makes this the next primary slice. The older
roadmap's UV opportunity and the seam report agree. Conforming OCCT realization
remains slice 6; it is not a prerequisite for locating on admitted polygonal charts.

## Existing behavior and the depth being added

`native/uv_location.hpp` declares `Locator::create` and `locate`; its implementation
is pending. `surface_preparation.hpp` already supplies immutable double XYZ,
triangles, source maps and non-forgeable native chart ownership. Reuse these values.

The independently packaged `integration/mesh_healing_extension/mesh_export.py`
contains `UVSurfaceMap`. It computes barycentric coordinates for every triangle,
accepts candidates within tolerance, compares candidate XYZ against the first
candidate, then returns the first triangle only if they agree. `sample` subsequently
evaluates that triangle. Its mutable engine requires revision/fingerprint checks.
The root package does not contain this caller. Keep the bundle as a differential
reference; importing it at runtime would not constitute installed host adoption.

The existing `FlatBVH` owns a legacy float 3D triangle mesh. Its nearest-ray query
cannot establish complete UV candidates. Inspect its median partitioning mechanics
for private reuse, but do not convert chart data to float or introduce a public
dimension/backend hierarchy. Shared private machinery is justified only if both
implementations actually benefit without changing their numerical contracts.

The user expressly permits selecting useful code anywhere in `native/`, including
the Point3D family and motorcycle files. Their current exclusion from active builds
is a qualification state, not a prohibition on reuse. Targeted inspection found:

| Source | Useful material | Adaptation needed for this slice |
|---|---|---|
| `Point3D_v5.tcc` and `Point3D_v6.tcc` | Templated box accumulation and recursive median split by centroid | Use chart UV and tolerance envelopes; bounded flat storage, checked centroid arithmetic, deterministic ties and budget accounting. The prototype fully sorts each range and stores a vector in every leaf. Compare this with the active flat BVH before selecting mechanics. |
| `reference/developer-prototypes/motorcycle_graph_trig.cpp::map_2d_to_3d` | Explicit barycentric interpolation algebra | Consume the existing admitted chart rather than recomputing intrinsic face coordinates. Its small-denominator fallback returns vertex zero; replace this with checked numerical failure. |
| `reference/developer-prototypes/motorcycle_graph_quad.c++::map_2d_to_3d` | Local tangent-basis mapping | Not equivalent to the retained piecewise-linear triangulation on warped polygons; do not substitute it for chart interpolation. |
| Motorcycle `Vector2` and segment predicates | Small double arithmetic helpers | Reuse only where helpful internally. Fixed EPSILON, clamping and parallel/collinear handling do not establish the locator's conservative predicate contract. |

Extract and qualify useful routines under the locator's existing interface rather
than activating entire demonstration translation units. Broader Point3D algebra,
feature analysis and motorcycle event scheduling are not needed by this caller.
This is a reuse assessment, not a compile or correctness qualification of those files.

Deleting the proposed module would return ownership, conservative search,
barycentric admission, overlap resolution, provenance and budgets to every caller.
That is its depth. A public index plus caller-owned ambiguity handling would leave
the difficult part distributed across callers.

## Interface

Refine the existing scaffold around two operations. The following is illustrative
C++, not a declaration to compile before the contract fixtures exist:

```cpp
Locator::create(IndexRequest{chart, policy, index_limits})
    -> std::expected<Locator, LocationError>;
locator.locate(QueryRequest{query_span, query_limits})
    -> std::expected<Locations, LocationError>;
```

`IndexRequest` retains the existing `AdmittedChart` by value, sharing its immutable
native storage. `QueryRequest` borrows finite double UV pairs synchronously; the
binding owns a copied query buffer before releasing the GIL. Neither operation
accepts a second XYZ array, triangle array, or source-face mapping.

`LocationPolicy` fixes barycentric tolerance and relative XYZ agreement tolerance
when the locator is built. Initial defaults are `1e-9` and `1e-8`, matching the
reference. Both must be finite and nonnegative. Changing either creates a new
locator, keeping search envelopes and acceptance policy inseparable. No per-call
tolerance override or index tuning is exposed in the initial interface.

`Locations` retains the matching native chart owner and effective policy. It owns
one record per query and a packed candidate array with checked offsets of length
Q+1. Candidate groups are sorted by discretization triangle ordinal, independent
of tree traversal order. Each candidate includes triangle ordinal, source polygonal
face ID, three barycentric weights and interpolated double XYZ. Native storage is
private; Python exports independent copies or immutable bytes-backed projections.

| Query status | Meaning | Resolved XYZ |
|---|---|---|
| outside | Complete search, no accepted triangles | Absent |
| unique | Complete search, exactly one candidate | That candidate's XYZ |
| agreeing | Complete search, multiple candidates agree under policy | Lowest triangle ordinal's XYZ |
| ambiguous | Complete search, candidates disagree under policy | Absent |
| budget_exceeded | Search was not completed or not started due to exhaustion | Absent |

Use an optional resolved value rather than a fabricated zero or NaN point.
Ambiguous candidates retain their individual XYZ as evidence, not authorization to
choose one. Source IDs belong to the retained polygonal snapshot; triangle ordinals
are neither display IDs nor durable cross-revision identifiers. Resolve provenance
from the native chart, never from an independently replaceable Python wrapper field.

Do not add `evaluate(triangle_ids, barycentrics)` initially. `locate` already computes
the values needed by its caller; a second public evaluation operation permits
callers to sidestep ambiguity resolution without an established use case.

## Numerical contract

1. Validate the whole query batch and policy before traversal. Empty batches return
   empty records with offsets `[0]`. Nonfinite queries are input errors. Invalid
   local charts cannot enter through the native interface; both admitted chart
   orientations supported by slice 4 remain usable.
2. Compute barycentric coordinates on the retained triangulation, with no clamping
   or renormalization that changes the reference's tolerated extrapolation.
   Acceptance is `-epsilon <= b_i <= 1 + epsilon` for all three coordinates.
3. Index envelopes must contain every point that this predicate can accept. Exact
   triangle boxes are insufficient. For exact arithmetic, enlarging each axis by
   `2 * epsilon * triangle_axis_span` is a conservative bound: with three weights
   summing to one, at most two negative contributions expand an extremum. Production
   bounds also need outward rounding and a justified floating-point error margin.
   This algebraic observation alone is not a numerical qualification.
4. Normalize local calculations to avoid unsafe determinant/inverse arithmetic.
   Before enabling pruning, establish a conservative bound for numerical error in
   the implemented barycentric calculation. If a safe finite envelope cannot be
   established, keep that triangle in an always-tested list or return a typed
   numerical-range error. Never prune it using an optimistic box. Charge fallback
   triangle tests normally. Differential near-edge and scale tests gate activation.
5. Preserve the reference agreement rule: use the lowest accepted triangle ordinal
   as the reference point, and require the maximum Euclidean distance to it to be
   at most `xyz_relative_tolerance * chart_xyz_scale`. The scale is the maximum
   coordinate span of the selected surface, floored at the smallest positive normal
   double as in the reference. Use stable distance/range arithmetic; a nonfinite
   intermediate cannot count as agreement. This is reference-relative agreement,
   not an assertion that every pair is within that same distance.
6. Preserve all candidates, including multiple triangles on an inserted diagonal,
   source edge or vertex. Agreement need not imply adjacency: separate coincident
   sheets can agree geometrically while retaining distinct provenance. A conflict
   found early is not permission to stop collecting complete candidate evidence.
7. Locally admitted charts can overlap globally. No query result certifies global
   injectivity. Near-threshold results remain tolerance-dependent measurements.

The stable reference candidate makes traversal changes invisible. Reordering source
triangles can change which agreeing point is selected within tolerance; do not
promise bitwise invariance under a different discretization. Record the policy and
maximum reference-relative discrepancy so the decision can be inspected.

## Ownership and reuse

The locator retains its chart, which retains its discretization. A result retains
its chart and owns its output, without keeping the index alive unnecessarily.
Deleting input arrays, the solver, chart wrapper or locator cannot invalidate a
retained result. Mutating exported arrays cannot change future native queries.

New UV, qualification policy, XYZ, topology, selection or triangulation requires
the appropriate new chart and locator. Repeated queries reuse the locator. A new
solver result does not update an old locator implicitly. No global cache, digest
registry, stale-engine fingerprint or runtime backend selector is needed.

All traversal stacks and counters are per call. Concurrent read-only queries are
an implementation goal requiring tests; immutable ownership alone is not evidence
of qualified concurrency. Solver sharing remains outside this slice.

## Budgets and failures

Use UV-specific index/query limit records and errors, following the existing
input/workspace/work/output vocabulary. Reuse arithmetic helpers only where their
semantics match. Do not extend the surface error enum to cover unrelated operations.

Index construction is all-or-nothing. Account for referenced chart payload as
logical input without copying it; account separately for new triangle records,
nodes, ordering storage, fallback lists and construction scratch. Count deterministic
build operations and check size arithmetic before allocation. Retaining an existing
chart does not mean the index owns another complete XYZ/UV allocation.

For queries, preflight input and mandatory Q-record/Q+1-offset output storage.
Failure to fit this minimum returns a typed batch error with no result. Then process
queries in input order using one batch-wide work/output/workspace budget and an
explicit per-query accepted-candidate cap. Stage one candidate group transactionally.
Only a complete, sorted, resolved group is committed to output.

On any query resource stop, discard that query's staged candidates, retain completed
earlier records, and mark the current and remaining records `budget_exceeded`.
Return `first_unfinished_query`, the exhausted limit and usage; later records are
explicitly not attempted. They are not geometric failures. This intentionally
chooses no partial candidate evidence for the stopped query, avoiding an additional
incomplete-candidate protocol. Sampling must reject the incomplete batch.

Count node visits, triangle tests, accepted-candidate insertions, candidate ordering
and XYZ comparisons. The implementation record must publish exact counters and
byte formulas, including staged output, before claiming bounded behavior. Check
candidate caps before insertion; never silently truncate a group. Mandatory status
storage is reserved before traversal so exhaustion can always be reported.

Malformed input and numerical-range failures return typed batch errors, not
`outside`. Include operation and query/triangle where available. Unexpected
allocation failures retain the existing exception translation; they are not a
computed budget result. Logical byte/work limits do not bound process RSS, binding
projection copies or wall-clock time. Document those exclusions explicitly.

## Installed Python caller

Add a focused `cad_integrity.uv` module rather than migrating the export engine:

```python
from cad_integrity.uv import prepare_locator

assessment = system.last_chart_assessment
assert assessment is not None and assessment.admitted is not None
locator = prepare_locator(assessment.admitted, policy=policy, limits=index_limits)
locations = locator.locate(queries, limits=query_limits)
xyz = locator.sample(queries, limits=query_limits)
```

`locate` returns typed evidence for the entire ordered batch. `sample` is a thin
convenience over the same operation: it returns a Q-by-3 immutable projection only
if every record is unique or agreeing. Otherwise it raises the existing appropriate
host geometry/resource exception with query index and reason. It neither retries
with larger limits nor selects an ambiguous candidate. No second numerical
implementation hides inside this convenience method.

The private binding admits native-endian contiguous float64 Q-by-2 arrays with
checked counts and unaligned-buffer-safe copies. The host can normalize array-like
input explicitly, documenting its additional allocations. Apply existing exception,
ownership and GIL conventions. The retained bundle keeps its existing stale-engine
behavior and exception contract; it is not silently replaced in this slice.

## Acceptance and implementation sequence

1. Freeze public-contract fixtures through `create` and `locate`: analytic triangle
   interior, outside, vertices, shared edges and inserted diagonals; stacked sheets
   with equal UV and different XYZ; coincident XYZ with distinct source provenance.
   Cover both admitted orientations, concave/warped triangulation and source subsets.
2. Implement complete resolution and private conservative indexing together. Compare
   against exhaustive reference results for ordinary inputs; add independent
   analytic/high-precision fixtures at tolerance thresholds, large translations,
   extreme scales and ill-conditioned admitted triangles. Match full candidate
   sets using a test-owned exhaustive oracle: the legacy `locate` returns only IDs.
   Test candidate ordering and reference-relative agreement with three candidates.
3. Exercise every budget separately, including a stop after an apparently unique
   early hit, a later conflicting triangle, an output cap midway through a group,
   minimum metadata refusal and an untouched suffix. Verify no incomplete query
   becomes a sample. Test numerical errors separately from budgets.
4. Bind the same kernel and complete the installed chart-to-location-to-sample path.
   Test native non-forgeability, mismatched host wrapper rejection or authoritative
   handle use, owner lifetime, alias mutation, empty batches, layout/range refusal
   and unaligned contiguous arrays. Test repeated and simultaneous read-only calls
   before making concurrency claims.
5. Activate `cad::uv` and its contract executable in CMake and include the same source
   in setuptools/sdist packaging. Run native Release and ASan/UBSan, focused host
   and explicit reference tests, required root checks and installed-wheel tests
   outside the checkout without integration imports. Record pre-existing failures
   separately. Refresh artifact manifests for intentional changes.
6. Measure index creation, binding copies, query computation, output projection and
   end-to-end sampling separately. Include one-shot and repeated batches on growing
   grids, near-edge queries, many coincident candidates and conflicting overlaps.
   Record work counters and retained payload. Compare equivalent candidate/evidence
   work as well as the legacy first-ID caller. Worst-case overlap still visits every
   triangle and output can grow as Q times T; no universal speedup is promised.

Tests cross the same interface as callers. No mock index adapter or public triangle
predicate is required for pure in-process computation. Keep the reference unchanged
through qualification; retiring its independently packaged exports is separate work.

Expected edits: the existing UV scaffold pair, native tests and CMake registration,
private binding/stub and accounting guide, source packaging inventories, focused
host module/tests, slice measurements and implementation record. Surface ownership
should need no numerical redesign. Browser commands, display substitutions, STEP
export, repair actions, OCCT conformity, NURBS, Delaunay and motorcycle tracing remain
outside this slice.

Useful routines extracted from Point3D or motorcycle sources are expressly within
scope; implementing motorcycle tracing itself remains separate.

## Source record

Inspected the linked seam HTML and Markdown, native extension roadmap HTML and
`cpp-native-handoff-20260921.md`; those describe the earlier sequence. Current
decisions were checked against `native/README.md`, `docs/NATIVE_EXTENSION_FILE_PLAN.md`,
`docs/reviews/native-surface/{DESIGN,IMPLEMENTATION}.md`,
`native/{surface_preparation,uv_location,SimplicialComplex}.hpp`,
`native/uv_location.cpp`, `native/bindings/README.md`,
the BVH sections of `native/Point3D_v{5,6}.tcc`, the mapping/vector sections of both
motorcycle files and `native/Point3D.c++`,
`src/cad_integrity/surface.py`, and the retained bundle's `mesh_export.py` and
`tests/test_mesh_healing.py`. No implementation test was run for this design-only
change. Historical slice 4 test counts and timings remain historical evidence.
