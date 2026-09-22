# Slice 4: owned polygonal surface computation

Implemented from DESIGN.md on `dd1fd2b`, following native display slice 3 at
`6ef60c0`. The intervening commit added Point3D dump files to multiple CMake
source lists. Those files remain untouched; their target entries and the
unqualified motorcycle target were removed. No scratch or motorcycle source is
compiled by active libraries, tests, scaffold checks or Python packaging.

## Implementation

The existing surface scaffold now implements `prepare`, `assemble` and
`qualify_chart` in `cad::surface`. Preparation reuses native polygonal assessment
on the selected compact patch, requires consistent winding and owns float64
geometry, deterministic projected triangulation, source vertex/face IDs, source
edge versus inserted-diagonal correspondence and boundary facts. Cell admission
alone does not authorize a surface. The legacy float polygon/BVH contracts are
unchanged.

Operators and admitted charts retain the same immutable native surface owner.
Native values have no public minting constructors. Binding exports are independent
copies; retained host projections use immutable bytes backing. Native typed errors
carry operation and source face where available. Limits account for logical input,
workspace, work and output separately; binding copies, host projections and SciPy
allocations do not constitute an RSS guarantee. Exact accounting is documented in
native/bindings/README.md.

The installed `cad_integrity.surface` caller prepares selected polygonal geometry,
assembles signed cotangent stiffness, runs the migrated focused HarmonicSystem in
Python/SciPy and qualifies the resulting chart. It imports no integration bundle.
The retained standalone bundle is the differential reference and remains unchanged.
Source mutation cannot affect an owned snapshot. Confidence changes reuse geometry
and rebuild operators/factorization; RHS-only and compatible soft-target changes
reuse the appropriate factorization/update.

Chart evidence reports local flips, collapse, signed area and conformal distortion.
No chart is admitted on local failure or resource exhaustion. Orientation-disabled
solves can return invalid coordinates with explicit unadmitted chart evidence.
Local admission deliberately does not establish global injectivity.

The Python migration also closes a discovered Woodbury fallback gap: finite large
weights can overflow an intermediate before residual evaluation. Such intermediates
now trigger refactor fallback, and nonfinite residuals cannot pass acceptance.
No change was made to the retained integration reference.

## Red-green and qualification

- Native owned preparation fixture failed against the declaration scaffold; it now
  preserves concave source-face/diagonal correspondence and independent lifetime.
- Known right-triangle stiffness failed before assembly existed; exact reference
  coefficients now pass. Flipped-chart fixtures failed before qualification existed.
- Host import/caller fixtures failed before the installed surface module and
  harmonic interface existed; affine solves and reusable factorization now pass.
- Large-weight Woodbury fixture reproduced an unhandled nonfinite intermediate;
  the bounded update now falls back to a checked refactor.
- Focused host/binding and differential reference suite: 30 passed. Coverage includes
  concave alternate diagonals, warped polygons, winding/renumbering, scale extremes,
  negative cotangents, confidence cuts, constraints, ownership, byte/work limits,
  invalid input layouts, source selection and local versus global validity.
- Retained integration suite: 83 passed. Root pytest does not collect it implicitly.
- Native Release and ASan/UBSan workflows: 7/7 tests passed in each. Compile command
  inventories contain no Point3D or motorcycle source entries.
- Changed host module passes mypy; changed Python files pass Ruff.
- Isolated CPython 3.13 sdist and wheel build succeeded. Installed package tests,
  final root suite and independent review are recorded below.

## Measurement

`benchmark.py` is a reproducible sequential local comparison against the retained
integration reference. `benchmark.json` records seven-run medians for a 25x25 grid
(625 vertices, 576 quads, 1,152 triangles), with conversion/projection, assembly,
solver preparation, repeated solves and chart qualification distinguished.
Binding preparation includes native computation and input copying. A standalone
native benchmark separately measures owned input copying, preparation, assembly,
UV copying and chart qualification. Python profiling measures initial and repeated
solve time excluding chart qualification; those measurements include profiler
overhead. Array export and immutable projection copying have separate timings.
Costs overlap where labels explicitly say so. Build the native benchmark with:

```sh
xcrun clang++ -std=c++2c -O2 -Wall -Wextra -Werror -pedantic -I native \
  docs/reviews/native-surface/benchmark.cpp native/surface_preparation.cpp \
  native/SimplicialComplex.cpp -o /private/tmp/cad-surface-benchmark
/private/tmp/cad-surface-benchmark
```

On this workload, host end-to-end median was 6.88 ms and the reference was 179.78 ms.
Pure native preparation was 1.71 ms, assembly 0.69 ms and qualification 0.031 ms;
owned polygonal input copying was 0.0052 ms. These separate runs are not additive.
This is one planar workload on the local machine, not a general performance claim,
peak-memory measurement or qualification of parallel solver use.

## Scope

No browser protocol, display substitution, repair action, export/publication change,
OCCT conforming realization, UV locator, GPU compute or motorcycle implementation.
The next primary slice is the owned all-candidate UV locator consuming AdmittedChart.


## Independent review

Standards review found unaligned contiguous NumPy confidence buffers could reach
misaligned typed loads. The binding now uses memcpy into aligned owned vectors.
The reviewer confirmed the correction and zero outstanding standards findings.
The regression also passed in a separately UBSan-instrumented shared binding with
halt-on-error enabled.

Spec review identified the same alignment issue and incomplete timing attribution.
Separate native-stage, copy/export and profiled initial/repeated-solve measurements
were added. The reviewer confirmed both corrections and zero outstanding spec
findings. A subsequent residual-denominator overflow regression prevents false
acceptance of a nonfinite normalization.


## Final verification

- Full root suite on final numerical sources: **384 passed**, no skips, 30.07 s,
  91% aggregate statement coverage. The final focused surface/parity suite has
  **30 passed**. Full checks were repeated after the reviewed binding and residual
  corrections so this count covers the completed source.
- Final sdist and wheel built in isolated CPython 3.13 environments. The wheel was
  built from the generated sdist. Required native headers were present; no Point3D
  or motorcycle C++ source was packaged.
- Final wheel installed outside the checkout: **15 tests passed**, no skips.
  Both surface.py and the compiled extension resolved within the temporary venv.
  This environment reused the qualified Pixi dependency environment via system
  site packages; it is not an independent dependency/platform qualification.
- Native Release and ASan/UBSan: **7/7 passed** each. Separate UBSan shared-binding
  check passed for intentionally unaligned contiguous confidence arrays.
- Changed host files pass Ruff and mypy; compileall passes. Required root lint and
  mypy remain non-green in pre-existing mesh_motorcycle.py, including undefined
  _gen_synthetic_mpaths. A broader optional test-file lint also found pre-existing
  test issues. None are changed or hidden by this slice.
- Both independent reviewers confirmed zero remaining findings; the spec reviewer
  also confirmed the residual-normalization fix. Artifact manifests and diff
  whitespace checks pass. Scratch/dump contents match the starting commit.

This is local implementation, numerical parity, packaging and review evidence.
It does not establish hosted CI, cross-platform qualification, conforming native
BRep realization, globally injective charts or simulation readiness.
