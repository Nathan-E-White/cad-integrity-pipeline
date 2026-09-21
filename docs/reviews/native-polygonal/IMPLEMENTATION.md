# Native polygonal assessment: slice 2

Implemented against the e4dd9f1 host/native baseline, 2026-09-21. Concurrent
motorcycle work (including commit 5027a1b and subsequent edits) is outside this
slice. The earlier header include-order change was committed by that concurrent
work and is preserved. Review scope is the polygonal paths, not the whole moving
branch. The accepted design is in DESIGN.md; final verification follows below.

## Implementation and reuse

One `assess_polygonal` computation in SimplicialComplex.cpp owns signed edge uses,
face cycles, duplicate detection, vertex links, deterministic orientation and
restricted admission. Admitted values retain a shared immutable owner of input and
signed incidence. SparseCSR is reused with exact int8 incidence coefficients,
widened to int64 on export. Float/int geometry and its triangulation stay unchanged.
A small owned double/int64 input is necessary to preserve the host's exact collapse
predicate and ranges. No polymorphic interface or alternative production backend
was introduced. Existing CMake policy and pybind11 packaging are reused.

The host admission interface projects one assessment; the analyzer consumes those
facts without rebuilding edge uses. Orientation and repair admission use the same
implementation. Native matrices are retained independently of source aliases.
`to_chain_complex` copies and checks exact integer incidence before F2 conversion.
The accepted native seam, binding seam, existing host interfaces and installed-wheel
path remain the test surfaces. No private adjacency or traversal state is tested.

Open edges and inconsistent orientation remain distinct from admission. Invalid
references/layouts are input failures; decodable invalid cycles produce complete
facts. No geometry, outwardness or nonintersection claim follows from admission.
Logical byte/work policies and deterministic failure semantics are documented in
native/bindings/README.md. The workspace figure is a reservation formula, not a
measurement or guarantee of allocator usage/RSS. No partial assessment is returned
on a budget failure. Python source references are retained for compatibility but
are not authority for already admitted matrices.

## Red-green evidence

- Native disk contract initially failed compilation because the seam did not exist.
- Broken-wire admission, reversed duplicate detection, orientation multipliers and
  input-budget refusal each failed assertions before their corresponding behavior.
- Binding disk test failed with missing `_native.assess_polygonal` before binding.
- Host alias-mutation test failed with InvalidChainComplex when the old admitted
  view rebuilt matrices from modified source arrays. It passes using retained
  incidence from the assessment.
- Existing host matrix, renumbering, diagnostic and repair tests were retained.

## Local measurements

Nine warm repetitions, medians in milliseconds, CPython 3.13 / AppleClang / macOS
arm64. Baseline admission/topology code was loaded from e4dd9f1 solely for this
measurement. Inputs were preconstructed. Both admission columns include exact
ChainComplex validation; native admission additionally returns orientation facts.
Binding timings include input copies, native computation and owned NumPy output.
Analyzer timings include actual F2 homology and host report construction.

| Fixture | Baseline admission + chain | Native admission + chain | Binding | Baseline analyzer | Native analyzer |
|---|---:|---:|---:|---:|---:|
| Disk, 1 face | 0.253 | 0.181 | 0.013 | 0.411 | 0.336 |
| Torus, 1,024 triangles | 21.859 | 3.531 | 1.471 | 35.180 | 14.542 |
| Torus, 4,096 triangles | 152.044 | 14.477 | 6.014 | not measured | not measured |

These are local fixture results, not a universal speedup claim. Intermediate timing
script/output are `/private/tmp/measure-polygonal.py` and
`/private/tmp/polygonal-measurements.json`.

## Verification status

- Full root Python suite: **346 passed**, no skips, 30.56 seconds, 91% Python
  statement coverage. A later explicit nonmanifold-orientation exception test was
  added during final inspection; the focused admission/binding set then passed
  **30 tests**. No production code changed after the full-suite run.
- Native qualified targets: **6/6** CTest cases passed in each of Debug, Release
  and ASan+UBSan. After review added native renumbering qualification, polygonal
  tests passed again in all three configurations. A direct strict C++26
  ASan+UBSan compile/run also passed during implementation.
- Fresh isolated CPython 3.13 wheel build: setuptools 84.0.0 and pybind11 3.1.0.
  Installed package and extension imports were confirmed to resolve inside their
  temporary virtual environment, outside the source tree; **106 focused tests**
  passed. A fresh sdist and wheel built from that sdist also succeeded; the final
  installed-sdist-wheel run passed **107 focused tests**, including the added
  exception case.
- Changed Python modules pass Ruff and mypy; compileall and scoped diff checks
  pass. Root Ruff/mypy remain non-green in pre-existing mesh_motorcycle.py,
  including undefined `_gen_synthetic_mpaths` at line 23. No tracer patch was
  introduced to clear unrelated gates.
- Commit manifest is generated from committed-tree contents plus this slice's
  selected paths, preserving unrelated staged motorcycle renames and source edits.
  Working-tree artifact consistency is not claimed for those concurrent edits.
- These checks establish local implementation/packaging behavior, not hosted CI,
  cross-platform qualification or geometric validity.

The unfiltered native Debug workflow currently fails in the concurrent motorcycle
sources: `std::clamp` is unavailable under that target's language configuration.
This slice does not edit those files or their CMake target. Qualified native targets
are built explicitly before CTest, and that narrower evidence is reported separately.


## Standards review

Independent read-only review found no documented-standard breaches or actionable
baseline smells. The implementation preserves the existing native module, typed
results, ownership and host projection responsibilities. Standards: 0 findings.

## Spec review

The first review found one partial acceptance requirement: native renumbering was
missing despite host coverage. Added native cube tests that permute vertices,
reverse/reorder edges, reorder faces and rotate loops; D1/D2 are checked against
expected permutations and signs. The reviewer confirmed resolution, and the test
passed in all three native configurations. Spec: 0 remaining findings.
