# Slice 7b: bounded Delaunay construction

Implemented from baseline `9ed3b2e` against
`docs/NATIVE_SLICE_7B_IMPLEMENTATION_PLAN.md`.

## Result and ownership

`cad::mat::build_delaunay` now accepts finite `Point3` samples plus explicit
policy and limits, then returns one value-owned `ConstructionResult`. Exact
coordinate triples are canonically ordered and deduplicated before insertion.
Constructed IDs therefore follow coordinate order rather than caller order; the
offset/value `ConstructedSampleMap` retains every original input ordinal.

The private implementation uses
`CGAL::Delaunay_triangulation_3` with
`Exact_predicates_exact_constructions_kernel`. Vertex and cell handles remain in
`delaunay.cpp`. Materialization preserves oriented local vertices and opposite
neighbours, represents the single infinite vertex with `no_sample`, and checks
exact circumcenter and squared-radius conversion before retaining doubles.
Finite and infinite cells are ordered by canonical support set before `CellId`
assignment, making snapshots stable under input permutation.

`cad_mat_voronoi` remains dependency-free. `CAD_MAT_ENABLE_DELAUNAY` defaults
off; when enabled it requires `find_package(CGAL 6.2 CONFIG REQUIRED)`, builds
`cad_mat_delaunay`, and registers `cad_mat_delaunay_tests`. No Python, OCP, or
Gradio caller was selected or changed.

## Admission, evidence, and budgets

Construction returns typed errors for nonfinite inputs, unsupported policy,
reserved or unrepresentable IDs, checked size overflow, insufficient affine
dimension, exact-to-double failure, dependency failure, allocation failure, and
the exact named limit. A failure carries no partial final snapshot.

Evidence records input, constructed, duplicate, finite-cell and infinite-cell
counts; affine dimension; exact cospherical disposition; logical usage; compiled
CGAL revision; and numeric conversion count. Exact cospherical adjacency is
tested with the kernel predicate and records CGAL symbolic perturbation rather
than implying a unique tetrahedralization.

Exact-to-double conversion rejects both overflow and underflow: a nonzero exact
quantity may not become infinity or zero in the retained snapshot.

Input and initial storage bounds are checked before adapter allocation.
Canonical-sample and minimum work/output bounds are checked before CGAL
insertion. Cell-dependent limits are checked before snapshot allocation. Logical
output bytes cover cells, correspondence arrays, and dependency text. Logical
owned bytes add explicit adapter staging and the cell-handle list. These figures
exclude allocator overhead, CGAL-private storage, process RSS, and caller input.
Construction work counts adapter visits, insertions, emitted cells, and explicit
cospherical predicates; it is not a wall-time or CGAL-internal operation bound.
The input-sample limit is the pre-construction control on CGAL-private work and
storage. Cell-dependent limits are necessarily checked from the completed private
triangulation, before any cell-handle or snapshot allocation by the adapter.

## Qualification

The public construction test exercises empty and one-to-three sample inputs,
nonfinite coordinates, collinear and coplanar sets, exact duplicates, one
tetrahedron, two adjacent tetrahedra, five cospherical samples, input
permutations, an unrepresentable extreme circumradius, sentinel use, original
correspondence, all six limit failures, and exact accepted boundaries. Constructed
snapshots pass the independently implemented finite-dual extractor. Existing
hand-authored malformed-snapshot tests remain exclusively in `voronoi_tests.cpp`.

Executed local gates:

- Standalone Debug CMake/CTest with Delaunay enabled: **2/2 passed**.
- Standalone Release CMake/CTest with Delaunay enabled: **2/2 passed**.
- Standalone AppleClang ASan/UBSan CMake/CTest: **2/2 passed**.
- Direct Apple Clang C++26 compile with `-Wall -Wextra -Werror -pedantic`: passed.
- Parent native Release suite with the option off: **10/10 passed**.
- Parent native Release suite with the option on: **11/11 passed**.
- Full root Python suite: **477 passed**, no skips, with 92% aggregate statement
  coverage.
- The option-off parent build also passed with scaffold checks enabled; no
  declaration-only Delaunay source remains.
- A configure check with CGAL discovery explicitly disabled failed at the
  required `find_package`, confirming that enablement cannot silently omit it.

The exact verification commands were:

```sh
cmake -S native/voronoi -B /private/tmp/cad-voronoi-7b-debug \
  -DBUILD_TESTING=ON -DCAD_MAT_ENABLE_DELAUNAY=ON -DCMAKE_BUILD_TYPE=Debug
cmake --build /private/tmp/cad-voronoi-7b-debug
ctest --test-dir /private/tmp/cad-voronoi-7b-debug --output-on-failure

cmake -S native/voronoi -B /private/tmp/cad-voronoi-7b-release \
  -DBUILD_TESTING=ON -DCAD_MAT_ENABLE_DELAUNAY=ON -DCMAKE_BUILD_TYPE=Release
cmake --build /private/tmp/cad-voronoi-7b-release
ctest --test-dir /private/tmp/cad-voronoi-7b-release --output-on-failure

cmake -S native/voronoi -B /private/tmp/cad-voronoi-7b-sanitizers \
  -DBUILD_TESTING=ON -DCAD_MAT_ENABLE_DELAUNAY=ON \
  -DCMAKE_BUILD_TYPE=Debug -DCAD_NATIVE_SANITIZERS=ON
cmake --build /private/tmp/cad-voronoi-7b-sanitizers
ctest --test-dir /private/tmp/cad-voronoi-7b-sanitizers --output-on-failure

xcrun clang++ -std=c++2c -Wall -Wextra -Werror -pedantic \
  -I native/voronoi/include -isystem /opt/homebrew/include \
  native/voronoi/src/voronoi.cpp native/voronoi/src/delaunay.cpp \
  native/voronoi/tests/delaunay_tests.cpp -L/opt/homebrew/lib -lgmp -lmpfr \
  -o /private/tmp/cad-mat-delaunay-direct
/private/tmp/cad-mat-delaunay-direct

cmake -S native -B /private/tmp/cad-native-7b-default \
  -DBUILD_TESTING=ON -DCMAKE_BUILD_TYPE=Release
cmake --build /private/tmp/cad-native-7b-default
ctest --test-dir /private/tmp/cad-native-7b-default --output-on-failure

cmake -S native -B /private/tmp/cad-native-7b-enabled \
  -DBUILD_TESTING=ON -DCAD_MAT_ENABLE_DELAUNAY=ON -DCMAKE_BUILD_TYPE=Release
cmake --build /private/tmp/cad-native-7b-enabled
ctest --test-dir /private/tmp/cad-native-7b-enabled --output-on-failure

cmake -S native -B /private/tmp/cad-native-7b-scaffold-default \
  -DBUILD_TESTING=ON -DCAD_NATIVE_CHECK_SCAFFOLDS=ON \
  -DCMAKE_BUILD_TYPE=Release
cmake --build /private/tmp/cad-native-7b-scaffold-default
ctest --test-dir /private/tmp/cad-native-7b-scaffold-default --output-on-failure

if cmake -S native/voronoi -B /private/tmp/cad-voronoi-7b-missing-cgal \
  -DCAD_MAT_ENABLE_DELAUNAY=ON -DCMAKE_DISABLE_FIND_PACKAGE_CGAL=TRUE; then
  exit 1
fi

pixi run test

git diff --check 9ed3b2e...HEAD -- docs/NATIVE_EXTENSION_FILE_PLAN.md \
  docs/NATIVE_SLICE_7B_IMPLEMENTATION_PLAN.md docs/reviews/native-delaunay \
  native/README.md native/cmake/ScaffoldChecks.cmake \
  native/tests/extension_contracts.md native/voronoi
```

The option-off run confirms that the base native build does not discover or link
CGAL. The option-on run used installed Homebrew CGAL **6.2**, found from
`/opt/homebrew/lib/cmake/CGAL`; its compiled revision is asserted through public
evidence. The local Homebrew formula metadata classifies the package as
GPL-3.0-or-later and lists Boost, Eigen, GMP, and MPFR dependencies. Distribution
and licensing decisions remain a product concern rather than something this
local build silently resolves.

## Non-guarantees

This slice establishes bounded construction of a Delaunay snapshot and its
finite Voronoi projection for the exercised native cases. It does not establish
an exact medial axis, shape-relative containment, closest-boundary verification,
significance pruning, fitted reconstruction, field generation, IGM, chart
tracing, remeshing quality, hosted CI, cross-platform qualification, simulation
readiness, or certification.
