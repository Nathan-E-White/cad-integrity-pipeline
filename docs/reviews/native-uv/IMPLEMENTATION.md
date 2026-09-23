# Slice 5: owned all-candidate UV location

Implemented from DESIGN.md on `38c3014`, following the owned surface slice.

## Implementation

`cad::uv::Locator::create` retains a native admitted chart and builds a private
binary64 2D index. Construction uses an explicitly budgeted pending-node stack
and private iterative heapsort, with no recursive sorting workspace. `locate` returns query-ordered records and complete candidate
groups sorted by discretization triangle ordinal, with original polygonal face
IDs, barycentric weights and XYZ. Unique and agreeing records resolve XYZ;
outside, conflicting overlap and incomplete searches do not. Agreeing candidates
are compared against the lowest triangle ordinal as in the retained reference.
No separate public evaluate operation bypasses overlap resolution.

The Python `cad_integrity.uv.prepare_locator` caller consumes the chart from
`cad_integrity.surface`. It never retriangulates or imports the integration bundle.
Only the native handle supplies geometry/provenance, including when a Python chart
wrapper's surface field is replaced. Index and result lifetimes retain the actual
chart; host projections use immutable bytes backing. Read-only concurrent queries
have independent workspace and counters. No solver concurrency is implied.

The median-split structure draws on Point3D v5/v6, with flat leaf ranges, deterministic
ordering and explicit accounting. Entire demonstration translation units remain
excluded. Motorcycle triangle interpolation was inspected; its small-denominator
vertex fallback was not adopted. No motorcycle tracing behavior is activated.

Index envelopes use the actual rounded inverse used by the query predicate.
Outward-rounded interval inversion maps an expanded barycentric acceptance
rectangle to UV. The expansion includes computed dot-product error and coordinate
normalization error. Ill-conditioned or unrepresentable envelopes become unbounded
boxes, ensuring their triangles are tested. Query arithmetic can still fail with a
typed numerical-range error. This refines the design's illustrative exact-coordinate
box expansion into a bound on the implemented predicate. It needs no public
numerical helper or selectable index adapter. See native/bindings/README.md for
floating-point assumptions, formulas, exclusions and exact work-counter definitions.

Resource exhaustion discards the current candidate group, retains complete earlier
queries and marks the current/suffix queries unfinished. Mandatory metadata is
admitted first so a resource stop can always be reported. Binding and Python copies
are documented separately from native logical reservations; no RSS bound is claimed.

## Red-green record

- Native interior/outside/vertex fixture failed against the declaration scaffold,
  then passed through the implemented interface.
- Stacked sheets with identical UV and different XYZ exposed first-hit acceptance;
  complete candidate resolution now returns ambiguous evidence and no resolved XYZ.
- Candidate-cap fixture exposed an incomplete group presented as success; resource
  stops now discard that group and explicitly mark the unattempted suffix.
- A distant query under a two-step search budget failed with the exhaustive loop;
  conservative box pruning now completes it as outside.
- The installed caller fixture failed on its missing module, then passed through
  the native binding and host location/sample interface.
- Exhaustive candidate/work fixtures found initial conservative boxes too broad;
  interval inversion tightened them while preserving all oracle candidate sets.

## Qualification

- Focused installed-host and reference suite: 17 tests passed. Covers shared edges,
  inserted diagonals, coincident sheets, conflicting overlap, reference-relative
  three-candidate agreement, source selection, concave/warped surfaces, both chart
  orientations, near-edge tolerances, extreme scales/translations, Decimal oracles,
  input layouts/alignment, non-forgeability, lifetime/aliasing, all budget classes,
  retained prefixes, empty batches and concurrent read-only use.
- Final CMake Release and ASan/UBSan workflows: 8/8 tests passed each, including
  expanded native budget, lifetime, scale and 31-sheet tree/ordering fixtures.
- Changed host module passes mypy; new host/tests pass Ruff.
- Isolated CPython 3.13 sdist and wheel build succeeded; wheel built from sdist.
- Final installed-wheel, full-suite, root checks and independent reviews are
  recorded below.

## Measurement

`benchmark.py` records seven-run medians for growing grids, a one-query workload,
near-edge queries and 32 overlapping sheets with agreement/conflict. Timings
separate index creation, binding query with input copy, array export, immutable
projection copying and full host work. `benchmark.cpp` independently measures pure
native index construction, query copying and query computation. Build/run with:

```sh
xcrun clang++ -std=c++2c -O2 -Wall -Wextra -Werror -pedantic -I native \
  docs/reviews/native-uv/benchmark.cpp native/uv_location.cpp \
  native/surface_preparation.cpp native/SimplicialComplex.cpp -o /private/tmp/cad-uv-benchmark
/private/tmp/cad-uv-benchmark
.pixi/envs/default/bin/python docs/reviews/native-uv/benchmark.py
```

On the local 25x25 grid (1,152 triangles), repeated host sampling of 400 queries
had a 0.66 ms median versus 27.74 ms for the legacy reference. Index creation was
0.52 ms. Host locate including all candidate projections was 0.46 ms versus
27.42 ms for a NumPy exhaustive all-candidate reference. These are different
interfaces and their timings are identified separately in `benchmark.json`.

The one-query index-plus-locate cost was 0.55 ms versus 0.077 ms for the exhaustive
all-candidate reference: constructing an index is not automatically worthwhile.
The pure native run used 576 queries; index construction was 0.486 ms, query copy
0.0002 ms and query computation 0.146 ms. Separate runs/workloads are not additive.
Worst-case overlaps still visit and retain every accepted triangle. Final measurements
were run sequentially after build/test workloads completed. They do not establish
platform-wide speedups, memory peaks or hosted CI.

## Scope

No browser protocol, display substitution, repair, publication/export, OCCT
conforming realization, NURBS, Delaunay or motorcycle tracing changes. The next
primary roadmap slice remains conforming OCCT realization through a qualified
runtime/copy seam. Successful UV location does not establish global injectivity,
conforming CAD realization or simulation readiness.

## Independent review corrections

The Standards reviewer found no actionable findings. The Spec reviewer identified
unaccounted construction scratch and a missing mid-group output-exhaustion fixture.
Construction is now iterative with a checked T-entry pending-node reservation;
ordering uses private iterative heapsort. A red fixture proved retained output alone
could previously satisfy the owned budget; it now refuses that undersized workspace.
The added overlap fixture exhausts output after one candidate of a two-candidate
group, preserving an earlier completed query, discarding the incomplete group and
marking the suffix unfinished. Both reviewers rechecked the corrected implementation and confirmed zero remaining
actionable findings. Reviews were source inspections, not independent test runs.

## Final verification

- Full root suite after the reviewed numerical corrections: **401 passed**, no
  skips, 26.66 s, 91% aggregate statement coverage. Focused UV host/parity: **17 passed**.
- Retained integration suite: **83 passed**, no skips. No integration source changed.
- Final native Release and ASan/UBSan: **8/8 passed** each. Explicit source inventories
  contain no Point3D or motorcycle translation units; their contents remain unchanged.
- Separate UBSan-instrumented shared binding with halt-on-error: **15 UV host tests
  passed**, including an intentionally unaligned contiguous query buffer.
- Isolated CPython 3.13 sdist and wheel build succeeded after correction, with the
  wheel built from that sdist. Archive inventories contain the required UV sources
  and headers, host module and stub, and exclude prototype translation units.
- Final wheel installed outside the checkout: **30 tests passed**, no skips (15 UV,
  15 surface). Both host module and compiled extension resolve inside the temporary
  venv. This reused qualified Pixi dependencies via system site packages; it is not
  an independent dependency/platform qualification.
- Changed host module passes mypy; new host/test/benchmark files pass Ruff;
  compileall passes. Required root lint/mypy remain non-green only in the unchanged
  `mesh_motorcycle.py`: seven Ruff findings and undefined `_gen_synthetic_mpaths`
  under mypy. Those pre-existing failures are not hidden or repaired by this slice.
- Standards review: zero remaining findings. Spec review: two findings corrected,
  zero remaining. Artifact manifest and whitespace checks pass before commit.

This is local implementation, numerical, packaging, measurement and review evidence.
It does not establish hosted CI, other floating-point environments or CAD conformity.
