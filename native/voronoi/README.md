# Native Delaunay/Voronoi foundation

This subtree owns two C++26 modules. `cad_mat_voronoi` is the dependency-free
finite-dual extractor. Optional `cad_mat_delaunay` constructs the extractor's
value-owned snapshot with CGAL 6.2. Neither module is a Python extension, OCP
verifier, medial-axis certificate, repair operation, or accelerator backend.

## Public seams

```cpp
cad::mat::build_delaunay(samples, policy, limits)
cad::mat::extract_finite_voronoi_dual(snapshot)
```

Construction rejects nonfinite coordinates, unsupported policy values,
unrepresentable reserved IDs, affine dimension below three, checked numerical
conversion failures, and each named limit. It lexicographically canonicalizes
finite coordinate triples, merges exact duplicates, assigns stable constructed
sample IDs, and retains every original input ordinal in an owning offset/value
map. CGAL handles and triangulation storage do not cross the seam.

The snapshot includes finite and infinite cells in canonical support-set order.
Local vertex orientation and opposite-neighbour incidence remain CGAL's; an
infinite cell has exactly one `no_sample` vertex. `no_sample` and `no_neighbor`
are reserved and never assigned to ordinary samples or cells. Exact-kernel
circumcenters and squared radii are checked when converted to the snapshot's
double representation. A failure returns no partial `ConstructionResult`.

CGAL resolves valid cospherical ambiguity through its deterministic symbolic
perturbation. Construction detects an exact cospherical finite-cell adjacency
and records that disposition; it does not pretend the simplicial choice is unique.
Evidence also records counts, affine dimension, numeric conversions, logical
usage, and the compiled CGAL revision.

The extractor independently validates supplied incidence, canonicalizes durable
cell identities, and returns a value-owned read-only finite dual:

- one node per finite cell;
- one edge per reciprocal finite-cell facet;
- no node for an infinite cell and no representation of a Voronoi ray;
- no opaque triangulation handle or insertion order in returned evidence.

## Limits and accounting

`ConstructionLimits` independently bounds input samples, canonical constructed
samples, all cells, logical adapter-owned bytes, construction work, and retained
output bytes. Sums and products are checked before their corresponding allocation.
Known admission and canonicalization lower bounds are checked before CGAL
insertion; cell-dependent bounds are checked before snapshot materialization.

Logical output bytes cover cell payload, correspondence offsets and values, and
the dependency tag. Logical owned bytes add the adapter's indexed/canonical
staging and cell-handle list. They exclude allocator overhead, CGAL's private
allocation, caller input, process RSS, and Python objects. Work charges one unit
per admission visit, correspondence visit, insertion, emitted cell, and
finite-finite cospherical predicate. It is a deterministic adapter budget, not a
count or time bound for CGAL's internal exact-arithmetic operations.
The input-sample limit is therefore the pre-construction control on CGAL's private
work and storage; the cell and adapter-work limits do not retrospectively measure
that dependency implementation.

## Build and focused checks

The extractor remains on by default. Construction is explicit and fails
configuration when CGAL 6.2 cannot be found:

```sh
cmake -S native/voronoi -B /private/tmp/cad-voronoi-build \
  -DBUILD_TESTING=ON -DCAD_MAT_ENABLE_DELAUNAY=ON
cmake --build /private/tmp/cad-voronoi-build
ctest --test-dir /private/tmp/cad-voronoi-build --output-on-failure
```

A direct Apple Clang check uses the same public seams:

```sh
xcrun clang++ -std=c++2c -Wall -Wextra -Werror -pedantic \
  -I native/voronoi/include -isystem /opt/homebrew/include \
  native/voronoi/src/voronoi.cpp native/voronoi/src/delaunay.cpp \
  native/voronoi/tests/delaunay_tests.cpp \
  -L/opt/homebrew/lib -lgmp -lmpfr \
  -o /private/tmp/cad-mat-delaunay-tests
/private/tmp/cad-mat-delaunay-tests
```

Independently authored snapshot fixtures remain in `voronoi_tests.cpp` so
extractor validation is not made circular by the CGAL constructor.

## Non-guarantees

The output is a bounded Delaunay snapshot plus finite Voronoi projection. It does
not establish an exact medial axis, shape containment, closest-boundary distance,
sample significance, reconstruction quality, field validity, IGM, chart traces,
remeshing quality, simulation readiness, or certification. Those need separately
selected callers and qualification.
