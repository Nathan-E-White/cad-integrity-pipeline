# Native Voronoi foundation

This subtree owns a C++26 extraction step for the finite dual of a
bridge-supplied 3D Delaunay triangulation.  It is intentionally not yet a
build target, Python extension, CGAL bridge, OCP verifier, or accelerator
backend.

## Public seam

```cpp
cad::mat::extract_finite_voronoi_dual(const cad::mat::DelaunaySnapshot&)
```

The caller supplies finite and infinite Delaunay cells with oriented local
vertex IDs, neighbour IDs, exact-bridge circumcenters, and sampled radii. The
function returns canonical, immutable raw medial nodes and edges:

- one node per finite cell;
- one edge per reciprocal finite-cell facet;
- no node for an infinite cell and no representation of a Voronoi ray;
- no opaque triangulation handle, insertion order, or cached construction in
  the returned evidence.

The future CGAL bridge owns robust predicates and circumcenter construction.
The future OCP adapter owns point-in-solid and closest-boundary verification.
This module rejects malformed bridge snapshots rather than inferring either
fact from array geometry.

## Focused local check

```sh
xcrun clang++ -std=c++2c -Wall -Wextra -Werror -pedantic \
  -I native/voronoi/include \
  native/voronoi/src/voronoi.cpp native/voronoi/tests/voronoi_tests.cpp \
  -o /private/tmp/cad-mat-voronoi-tests && /private/tmp/cad-mat-voronoi-tests
```
