# Native F2: slices 0 and 1

Implemented 2026-09-21 against baseline `cc6743827261c58b52c47725939fe7366b658db4`.
Scope: the handoff's next-session slices 0/1, not its eight-extension roadmap.
The CMake/scaffold preparation already present in the checkout is included as
prerequisite build material. Other extension declarations remain unimplemented.
The pre-existing include-order edit in `native/SimplicialComplex.hpp` is preserved
outside this commit.

## Design and reuse

The existing `F2ColumnReducer`, `ReductionBudget`, `F2ReductionEvidence`, `rank_f2`
and persistence engine remain the consuming interfaces. The set/XOR loop moves to
`cad::f2::reduce`; Python retains explicit integer-label packing, sparse coefficient
parity normalization and interval interpretation. There is one production reducer,
with no backend registry or fallback. Native code returns typed values/errors.

The signed CSR carrier describes signed incidence, whereas this calculation needs
ordered sparse F2 columns. Reusing it would conflate coefficient semantics and
transpose access. A small owned offset/value record is therefore justified. It
also packs every retained trace state without a separately allocated vector per
state. The current simplicial/mesh representations and geometry precision remain
unchanged. Existing native CMake policy is reused for `cad::f2`; setuptools compiles
the same source into the private extension. No polymorphic hierarchy is needed.

pybind11 provides NumPy dtype/layout inspection, owned output arrays and exception
translation without introducing a NumPy build-header ABI dependency. Input buffers
are copied under the GIL; numerical work releases it. Output mutation cannot alter
later reductions. Native C++ and Python boundaries are both exercised.

The host default retains full canonical evidence. Rank omits reduced columns and
traces; persistence omits traces. Trace-entry and packed-output-byte budgets are
separate from existing pivot/scratch storage limits. Budget failure has no final
rank. An 11-column fixture retains eight pivot entries and 44 trace entries.
Signed int64 normalization is explicit; Python integers outside that range are
rejected. Whole-input admission precedes numerical errors, as documented in the
[binding contract](../../../native/bindings/README.md).

## Validation

- Initial red: the new host evidence-mode test failed with unsupported keyword
  `evidence`; it passed after native integration. Existing host contract tests
  were retained rather than replaced by tests of helper implementation details.
- 29 native/host contract cases cover evidence modes, deterministic bitmask-reference
  parity across 12 seeds, int64 extremes, duplicate collapse, malformed offsets,
  dtype/stride/shape rejection, alias mutation, output lifetime/independence and
  exact evidence/output limits, including empty trace-state metadata.
- Full root suite: **338 passed**, no skips, 25.65 seconds; 91% Python statement
  coverage. This is local test evidence, not hosted CI or geometric qualification.
- Fresh isolated wheel build used CPython 3.13, setuptools 84.0.0, pybind11 3.1.0
  and AppleClang 21. Installed wheel imported from its own temporary environment,
  then passed **112 focused tests** (native binding, algebra and math sea trials).
  Source-distribution generation and a fresh wheel build from that extracted
  archive also passed, including the C++ header and both translation units.
- CMake Debug, Release and ASan+UBSan presets: **5/5 runtime tests each**. A direct
  strict C++26 ASan+UBSan compile/run also passed. Only unfinished declarations
  remain in the scaffold object target.
- Changed Python modules: Ruff and mypy pass. Repository-wide Ruff/mypy remain
  non-green because baseline `mesh_motorcycle.py` contains lint violations and an
  undefined `_gen_synthetic_mpaths` at line 23. Confirmed present in baseline;
  no unrelated tracer implementation was added to clear those gates.
- Two-axis review: Standards found no hard violation and one minor duplication
  of native target policy; replaced with `cad_native_library`. Spec found no
  implementation defect; requested this completion record, now supplied.

## Local measurements

Median milliseconds over nine warm repetitions, Apple Silicon/macOS, using the
baseline Python reducer as the reference. Inputs are preconstructed integer-label
tuples. Native host times include normalization, packing, copies, computation and
reconstruction of the immutable Python evidence. The packed boundary additionally
reported below includes binding input copies, native work and owned NumPy outputs;
it excludes host normalization and tuple reconstruction. These are elapsed times,
not isolated CPU or allocator measurements.

| Input | Baseline full evidence | Native full | Native reduced | Native rank |
|---|---:|---:|---:|---:|
| 200 disjoint columns, two entries each | 0.134 | 0.211 | 0.180 | 0.157 |
| 1,000 columns, eight sampled rows of 128, seed 901 | 112.772 | 48.171 | 23.079 | 22.156 |

For the second input, packed-boundary times were 24.627 / 21.145 / 21.222 ms for
full / reduced / rank. Small-input overhead is measurable: native full evidence
was slower on the first fixture. The XOR-heavy fixture improved, and evidence
selection removed substantial retention/conversion cost. No universal speedup is
claimed. A larger 3,000-column/256-row full-evidence probe hit the new default
trace cap; it was not reported as a successful timing or partial numerical result.

## Boundaries

Logical entry/packed-byte budgets do not cap process RSS, allocator capacity, map
node overhead or Python object overhead. No concurrent solver, persistent native
handle, zero-copy output view, database, GPU work, OCCT ABI bridge, native homology
of STEP shapes, or later geometry extension is introduced. Packaging/toolchain
qualification is local to CPython 3.13 on macOS arm64; other platforms require their
own compiler/build validation.

## Standards review

No hard documented-standard violations. One minor possible Duplicated Code smell
was reported in F2 target setup; it was resolved by using the existing native
library policy helper. The pre-existing header edit remains outside the commit.

## Spec review

No implementation findings within slices 0/1. The reviewer requested the missing
completion record containing measurements and reuse rationale; this document
supplies it. Later roadmap algorithms remain deferred.

Review summary: Standards 0 outstanding findings; Spec 0 outstanding findings.
