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
must be finite and nonnegative and uses the mesh's coordinate unit. Convexity
and projected segment intersection are checked independently using scale-aware
double roundoff bounds; self-intersecting loops and collapsed fan triangles are
rejected. Near-degenerate geometry may be rejected conservatively. Nonfinite arithmetic is rejected. Float
geometry is approximate. Polygon and ray arithmetic uses double intermediates;
ray parallelism uses 32 double epsilons scaled by edge and direction lengths.
Only strictly positive ray distances are hits; nearly parallel rays may be rejected.
Ray directions are normalized by `Ray::create`; zero/nonfinite directions fail.
The BVH owns an admitted mesh snapshot, including optional polygonal face IDs.
Later changes to caller-owned geometry cannot affect it. Both scalar and batch
queries validate and normalize rays before traversal. Invalid batches fail before
launching workers.

Convex triangulation emits one polygonal face ID per display triangle. IDs are
face indices local to the original polygon model snapshot and are retained in ray
hits; they do not assert cross-revision identity. Direct triangle input may omit
provenance, represented by an empty ID vector and an empty optional in hit results.
Malformed nonempty mappings are rejected at BVH construction.

The library does not print results or define `main`. Tests are separate consumers
of the public header, and their checks remain active under `NDEBUG`.

## CMake build and test interface

Requires CMake 4.3+ and a compiler/standard library supporting the C++26 mode and
`std::expected`. Presets use Ninja. No external C++ test framework is downloaded.
The maintained native root is this directory; Python packaging remains separate.

From `native/`, configure, build, and run CTest in one command:

```sh
cmake --workflow --preset release
cmake --workflow --preset debug
cmake --workflow --preset sanitizers
```

Presets write to `build/native/<preset>` in the repository and export
`compile_commands.json`. Individual steps and label filtering are also available:

```sh
cmake --preset release
cmake --build --preset release
ctest --preset release
ctest --preset release -L integration
```

The six qualified CTest executables cover polygonal assessment, F2 reduction, simplicial behavior, NURBS, finite Voronoi, and a
consumer linking all three libraries. Labels are `native` and the module name (or
`integration`); each test has a 120-second timeout. Assertions remain enabled in
Release test executables. Sanitizer tests halt on ASan/UBSan errors.

### Targets and options

Link build-tree consumers against `cad::simplicial`, `cad::nurbs`, and
`cad::voronoi`, plus `cad::f2` for bounded sparse reduction. Existing `simplicial`, `cad_mat_nurbs`, `cad_mat_voronoi`, and parent
aliases `nurbs`/`voronoi` remain available. Public header file sets supply include
paths; C++26 requirements propagate to consumers. Libraries use position-independent
code for future binding linkage. Warning flags remain private to project targets.
There is no installed package/export contract yet.

| Option | Default | Meaning |
|---|---|---|
| `BUILD_TESTING` | ON for a standalone root | Build and register numerical/consumer tests; when embedded, the parent controls testing |
| `CAD_NATIVE_WARNINGS_AS_ERRORS` | ON | Treat project warnings as errors; consumers can disable this without editing flags |
| `CAD_NATIVE_SANITIZERS` | OFF | ASan + UBSan with frame pointers for GNU-style Clang/GCC; runtime link requirements propagate |
| `CAD_NATIVE_CHECK_SCAFFOLDS` | OFF; ON in presets | Compile unfinished source declarations into an unlinked object target; this is not algorithm validation |

Scaffolds never enter the implemented libraries or a Python extension. Their
compile-only check catches declaration/include errors without advertising working
algorithms. Archived prototypes are excluded. Sources are enumerated explicitly.

Standalone NURBS and Voronoi builds remain supported through their existing
CMakeLists. Both reuse the same target policy and CTest registration helper.
Use `add_subdirectory(native)` for embedding; the parent must enable testing if it
wants native tests. No global compiler flags or parent build type are overwritten.
In-source builds are rejected. Keep local preset overrides in the ignored
`CMakeUserPresets.json`.

A generator-independent build without tests:

```sh
cmake -S native -B build/native/library-only -DBUILD_TESTING=OFF
cmake --build build/native/library-only
```

The sanitizer preset is qualified locally on AppleClang. Other compiler/platform
combinations require their own validation; unsupported sanitizer drivers fail
configuration explicitly. Leak-sanitizer support is platform-dependent and is not
promised by this preset.

Preset structure follows the [CMake presets reference](https://cmake.org/cmake/help/latest/manual/cmake-presets.7.html).

## Private Python binding

Slices 0–2 activate F2 and polygonal facts/admission. See [bindings/README.md](bindings/README.md) for
owned arrays, evidence budgets, packaging requirements and measured costs. The
Python extension and `cad::f2` compile the same numerical source; the extension
is built by setuptools, while CMake validates the dependency-free CPU kernel.

## Native face inspection

Host integration slice 3 carries OCCT source face identity through private-copy
meshing into the existing inspection workspace. It adds no C++ algorithm or new
OCCT binding. See [the implementation record](../docs/reviews/native-display/IMPLEMENTATION.md)
for copy correspondence, V3 native-face delivery, scope/projection identity and
qualification; polygonal V2 delivery remains unchanged.
