# Native consolidation and architecture findings

Implemented on 2026-09-20 from the native C++ architecture review. Baseline was
`400eb7a` plus the user's staged/unstaged native prototypes. Those working files
were captured byte-for-byte under `native/archive/simplicial-prototypes-2026-09-20`
before editing. Finding 1 is commit `68384c0`; subsequent work implements the
remaining four findings and resolves a final polygon admission defect.

## Scope and disposition

1. One active `native/SimplicialComplex.cpp` and public header in
   `cad::simplicial`. SimpComp3 supplies the base; the original contributes general
   facet closure. SimpComp2 contains no materially distinct retained algorithm.
   Archives are excluded from compilation. Native code returns values, has no
   demonstration `main`, and does not print output.
2. BVH owns an admitted geometry/provenance snapshot. Public query methods no
   longer accept an unrelated mesh. Internal arrays are private. Ray admission
   precedes worker launch; scalar and batch queries share traversal.
3. Polygon triangulation retains one local polygonal face ID per display triangle.
   BVH hits return the optional face ID; direct meshes can omit provenance.
   The IDs belong to the source model snapshot, not a cross-revision registry.
4. Parent CMake composes authoritative NURBS/Voronoi targets. Both subtrees remain
   buildable independently. All three test executables are registered at the
   parent. Numerical assertion tests run in Release and fail compilation if
   independently built with assertions disabled.
5. NURBS traversal policy is internal. Removed `EvaluationRequest::tile_side` and
   the inaccurate memory-bound promise. Full results and basis tables are retained;
   numerical output ordering and singular policies remain unchanged.

## Professionalization and review repairs

- Guard subset representability before shifting. Check the unique-simplex budget
  before insertion. General-facet duplicates remain idempotent; mesh duplicate
  triangles are errors, and isolated vertices survive closure.
- Typed polygon errors cover malformed offsets/coedges, invalid indices, unsupported
  units, nonfinite coordinates and invalid tolerances. Allocation-heavy methods
  no longer promise `noexcept`; allocation/executor failures propagate.
- Shared private per-face helpers avoid repeated whole-model validation.
- Median BVH partitioning bounds recursion depth. Ray arithmetic uses double
  intermediates and scale-aware parallelism checks. Slab-plane origins avoid
  zero-times-infinity arithmetic. Async failures are collected with `get()`.
- Polygon admission separates plane-distance tolerance from convexity, rejects
  projected self-intersections, and refuses collapsed fan triangles.

The budget bounds retained unique simplex count, not bytes or execution time.
Incremental ordered sets replace unbounded staging of repeated simplex entries;
this pays for early budget admission with per-insertion tree allocation/comparison.
No performance improvement is claimed. Geometry remains approximate float input
with double intermediate arithmetic; near-degenerate cases may reject conservatively.
No host bindings, exact predicates, CAD healing, or NURBS accelerator were added.

## Validation

Observed red cases before repairs:

- The prototype headers did not expose a consumable facet builder.
- A 64-vertex facet caused UBSan's shift-exponent error and incorrect acceptance.
- NaN planarity tolerance was accepted.
- Finite ray geometry at scale 1e20 missed; independent review also reproduced
  misses at scale 1e-4.
- Ownership/provenance tests failed compilation against the prior interface.
- A scale-1e-4 bow-tie polygon triangulated instead of rejecting.

Final checks:

- Strict C++26 compilation (`-Wall -Wextra -Werror -pedantic`).
- Parent Release CMake/CTest: 3/3 native executables pass, assertions enabled.
- Standalone Release NURBS and Voronoi CMake/CTest: 1/1 each passes.
- AddressSanitizer + UndefinedBehaviorSanitizer, fail-fast: all three native
  executables pass; simplicial checks rerun after the final polygon fix.
- Repository Python suite: 309 passed, no skips.
- Artifact manifests and `git diff --check` pass.
- Independent Standards and Spec review findings resolved and rechecked.

Native checks cover arbitrary-dimensional closure, signed incidence composition
(∂² = 0), exact budget limits, malformed input, polygon fan output, scaled invalid
polygons, box candidates, nearest rays, slab-edge origins, scalar/batch parity,
owned geometry after caller mutation, and optional face identity. NURBS retains
analytic curvature/endpoint/singularity cases and uses a 67×3 rectangular planar grid.

Reproduce using `native/README.md`. Detailed local standalone/sanitizer logs were
retained in `/private/tmp/cad-native-final-checks-20260920`; local logs are not
hosted CI evidence. The first attempted Python command referenced the obsolete
`tests_loose` directory and ran zero tests; the successful result above is from
current configured `tests/`, not that failed invocation.
