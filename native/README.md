# Native geometry and topology

`SimplicialComplex.cpp` is the consolidated polygonal/topology implementation.
`SimplicialComplex.hpp` exposes its value types and operations in `cad::simplicial`.
The historical prototypes are preserved under `archive/` and excluded from builds.

## Retained behavior

- Arbitrary-facet downward closure, canonical sorted simplex tiers and signed
  integer CSR incidence. Repeated facets are idempotent; duplicate vertices within
  a facet are rejected. Arbitrary integer labels are allowed in the facet path.
- Triangle-mesh closure preserves isolated vertices and rejects invalid indices,
  repeated triangle indices and duplicate triangles, regardless of winding.
  It computes incidence, not geometric quality or homology reduction.
- Signed coedge loops, optional shared edges, convex planar polygon admission
  and fan triangulation. Coordinates remain float, units are metadata, and no
  automatic conversion, concave triangulation, repair or OCCT operation occurs.
- Flat BVH primitive-box candidates, nearest two-sided ray hits and ordered batch
  ray results. Median partitioning bounds recursion depth. No speedup is claimed.

## Failure and numerical contracts

The simplex budget limits retained unique simplices and is checked before each
insertion; a facet whose closure cannot fit is rejected before expansion. Facet
sizes beyond the subset counter's representable range are rejected before shifting.
This is not a byte limit or a time budget; repeated input can still consume time,
and temporary input, indexing and output storage has additional cost.

Construction and triangulation return typed `TopologyStatus` errors. Allocation
failures propagate as exceptions. BVH admission and invalid ray construction throw
`std::invalid_argument`; async execution failures propagate rather than terminate.
Polygon methods validate public loop data before indexing it. Planarity tolerance
must be finite and nonnegative and uses the mesh's coordinate unit; convexity uses
the retained edge-scaled tolerance. Nonfinite arithmetic is rejected. Float
geometry is approximate. Polygon and ray arithmetic uses double intermediates;
ray parallelism uses 32 double epsilons scaled by edge and direction lengths.
Only strictly positive ray distances are hits; nearly parallel rays may be rejected.
Ray directions are normalized by `Ray::create`; zero/nonfinite directions fail.
BVH queries currently require the unchanged mesh used for construction.

The library does not print results or define `main`. Tests are separate consumers
of the public header, and their checks remain active under `NDEBUG`.

## Checks

```sh
cmake -S native -B /private/tmp/cad-native-build -DBUILD_TESTING=ON
cmake --build /private/tmp/cad-native-build
ctest --test-dir /private/tmp/cad-native-build --output-on-failure
```

A strict standalone topology check with sanitizers:

```sh
xcrun clang++ -std=c++2c -Wall -Wextra -Werror -pedantic \
  -fsanitize=address,undefined -I native native/SimplicialComplex.cpp \
  native/tests/simplicial_tests.cpp -o /private/tmp/cad-simplicial-tests
/private/tmp/cad-simplicial-tests
```
