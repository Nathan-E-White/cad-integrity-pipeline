# Native Voronoi foundation

This subtree owns a C++26 extraction step for the finite dual of a
bridge-supplied 3D Delaunay triangulation.  It is built as `cad_mat_voronoi` by the parent native build or standalone
subtree. It has no Python extension, CGAL bridge, OCP verifier, or accelerator
backend.

## Public seam

```cpp
cad::mat::extract_finite_voronoi_dual(const cad::mat::DelaunaySnapshot&)
```

The caller supplies finite and infinite Delaunay cells with oriented local
vertex IDs, neighbour IDs, exact-bridge circumcenters, and sampled radii. An
infinite cell has exactly one `no_sample` vertex. The function validates every
declared cell and reciprocal neighbour relation, then returns a value-owned
read-only view of canonical raw medial nodes and edges:

`no_sample` and `no_neighbor` are reserved sentinels; neither may be assigned
to an ordinary bridge sample or cell.

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

Standalone CMake/CTest (also registered by the parent native build):

```sh
cmake -S native/voronoi -B /private/tmp/cad-voronoi-build -DBUILD_TESTING=ON
cmake --build /private/tmp/cad-voronoi-build
ctest --test-dir /private/tmp/cad-voronoi-build --output-on-failure
```
