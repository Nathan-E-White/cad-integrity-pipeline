# Native Slice 7b — Delaunay construction implementation plan

Status: implemented. Executed gates and remaining non-guarantees are recorded in
`docs/reviews/native-delaunay/IMPLEMENTATION.md`.

## Objective

Complete the construction side of `native/voronoi` without activating the deferred
product-level medial, reconstruction, field, IGM, remeshing, or inspection features
recorded in `DESIRED_FEATURES.md`.

The slice accepts finite 3D samples, constructs one bounded value-owned
`DelaunaySnapshot`, preserves original-sample correspondence and construction
evidence, and feeds the existing independently tested
`extract_finite_voronoi_dual` operation. It does not certify an exact medial axis.

## Native interface and ownership

Replace the declaration-only scaffold with a small `cad::mat` interface:

```cpp
struct ConstructionPolicy;
struct ConstructionLimits;
struct ConstructionEvidence;
struct ConstructedSampleMap;
struct ConstructionResult {
    DelaunaySnapshot snapshot;
    ConstructedSampleMap original_samples_by_constructed_sample;
    ConstructionEvidence evidence;
};

std::expected<ConstructionResult, ConstructionError>
build_delaunay(std::span<const Point3> samples,
               const ConstructionPolicy& policy,
               const ConstructionLimits& limits);
```

- `ConstructedSampleMap` is an owning offset/value representation: one offset range
  per constructed sample containing every corresponding original `SampleId`.
- `ConstructionPolicy` freezes exact duplicate handling and the recorded disposition
  of valid cospherical inputs. It does not contain OCP verification or pruning policy.
- `ConstructionLimits` separately bounds input samples, constructed samples,
  emitted cells, adapter-owned logical bytes, deterministic adapter work, and
  output bytes. These counters do not claim to measure CGAL-private allocation or
  exact-arithmetic operations; the input-sample limit is the pre-construction
  control on that dependency work.
- `ConstructionEvidence` records input/constructed counts, duplicates, affine
  dimension, finite/infinite cell counts, degeneracy disposition, measured usage,
  dependency revision, and numeric conversions.
- Errors identify invalid input, reserved/unrepresentable IDs, insufficient affine
  dimension, numerical conversion failure, dependency failure, and the exact limit
  exceeded. Validation/allocation errors do not return a partial final snapshot.

The CGAL triangulation and all handles remain private to `delaunay.cpp`. Pin CGAL
6.2 and use `Exact_predicates_exact_constructions_kernel` for construction and
circumcenters, then perform checked conversion into the existing double-valued
snapshot. CGAL is a dependency of this module, not an umbrella advanced-geometry
abstraction.

## Implementation sequence

1. **Freeze admission and accounting.** Reject nonfinite coordinates, reserved or
   unrepresentable sample counts, size-arithmetic overflow, and every input-derived
   limit before CGAL insertion. Canonically sort exact coordinate triples,
   deduplicate them, and build the original-sample correspondence. Check
   cell-dependent adapter limits after triangulation but before cell-handle or
   snapshot allocation; do not present CGAL-private work or storage as measured
   adapter usage.
2. **Construct the triangulation.** Insert canonical samples with stable constructed
   IDs. Reject affine dimension below three. Record, rather than conceal, CGAL's
   deterministic triangulation of cospherical inputs.
3. **Materialize the snapshot.** Assign checked `CellId` values to finite and infinite
   cells; preserve oriented local vertices and opposite neighbours; use `no_sample`
   and `no_neighbor` only for their reserved meanings. Compute finite-cell
   circumcenters and sampled radii through the exact construction kernel, then reject
   nonfinite or unrepresentable double output.
4. **Reuse extraction.** Pass successful snapshots to the existing extractor in tests
   and in any future caller. Do not merge construction and extraction, expose CGAL
   state, or change the finite-only node/edge contract.
5. **Integrate narrowly.** Keep `cad_mat_voronoi` dependency-free. Add a separate
   `cad_mat_delaunay` target that links it and pinned CGAL 6.2, guarded by the explicit
   `CAD_MAT_ENABLE_DELAUNAY` CMake option, defaulting off. Enabling the option requires
   `find_package(CGAL 6.2 CONFIG REQUIRED)` and builds the construction tests; a
   missing or mismatched dependency fails configuration rather than silently omitting
   the capability. Preserve the current Python extension unless a concrete installed
   caller is separately selected.
6. **Record completion.** Update the Voronoi README, native inventory, contract matrix,
   and a Slice 7b implementation record with exact commands, results, dependency
   provenance, and remaining non-guarantees.

## Test and acceptance plan

- Direct native cases: empty and fewer-than-four inputs, nonfinite coordinates,
  duplicates, collinear/coplanar samples, a tetrahedron, adjacent tetrahedra,
  five-cospherical samples, insertion permutations, and extreme finite coordinates.
- Identity cases: stable constructed IDs, complete many-to-one original mapping,
  reserved sentinels, cell-count narrowing, reciprocal finite/infinite incidence, and
  snapshot equivalence under input permutation after canonical normalization.
- Limit cases: every input, constructed-sample, cell, owned-byte, work, and output
  boundary; overflow rejected before allocation; no partial snapshot presented as
  complete.
- Composition cases: independently authored snapshot fixtures continue to test the
  extractor; constructed snapshots pass extraction; malformed snapshot rejection
  remains owned by the extractor rather than duplicated in construction.
- Verification: strict Release and Debug CMake/CTest, direct Apple Clang C++26 warning
  build, ASan/UBSan, path-scoped `git diff --check`, and the existing parent native
  suite. Add Python/OCP tests only if the separately selected caller is activated.

Slice 7b is complete when those gates pass and the construction result is documented
as a bounded Delaunay snapshot plus finite Voronoi projection. Shape sampling,
inside/closest-boundary verification, significance pruning, Gradio integration,
fitted reconstruction, field generation, IGM, and chart tracing remain deferred
capabilities rather than implied follow-on work.

## Worktree constraint

The existing modification to `native/Point3D_v6.tcc` is unrelated user work. Exclude
it from edits, formatting, staging, verification fixes, and any Slice 7b commit.
