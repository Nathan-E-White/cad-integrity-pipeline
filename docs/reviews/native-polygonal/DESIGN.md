# Slice 2: owned polygonal assessment

Accepted design, 2026-09-21, originally inspected at e4dd9f1.
Implementation and qualification are recorded separately in IMPLEMENTATION.md.
The F2 implementation record closes slices 0/1. The design inspection preserved
then-dirty SHA256SUMS.json and native/SimplicialComplex.hpp. Additional motorcycle
work arrived concurrently during implementation and remains outside slice 2.

## Decision

Deepen polygonal facts and restricted cellular admission behind the existing host
interfaces. One native assessment owns edge uses, face-loop facts, vertex links,
orientation constraints, admission diagnostics and admitted signed incidence.
Python retains report construction, exception wording, repair decisions and homology
orchestration. Existing F2 reduction remains the downstream calculation.

The next executable vertical slice is raw polygonal input through
BRepHomologyStitchAnalyzer.evaluate_stitch_integrity to the existing TopologyReport.
Complete slice 2 by routing admission, orientation_solution and repair admission
through the same implementation. A port of admit_polygonal_cells alone leaves the
main duplication in place.

## Evidence for the seam

src/cad_integrity/polygonal_cells.py currently builds edge uses, validates cycles,
detects duplicate faces, builds vertex links and decides admission. Its admitted
view assembles signed SciPy incidence matrices.

src/cad_integrity/topology.py rebuilds edge uses before calling admission, and
orientation_solution builds them again to solve face-sign constraints. The analyzer
and repair.py are real consumers of admission. The deletion test is satisfied:
removing the proposed assessment would return incidence knowledge, diagnostic rules
and orientation traversal to multiple callers.

The native PolyhedralBRep already supplies signed one-based coedges and loop
operations, but uses float coordinates and int indices. The Python carrier uses
float64/int64. In particular, narrowing coordinates could turn a distinct pair of
endpoints into an exactly collapsed edge and change admission. Reuse must preserve
semantics, rather than merely share a type name.

## Proposed interface

Illustrative names, placed with the existing simplicial/polygonal module:

```cpp
std::expected<PolygonalAssessment, PolygonalError>
assess_polygonal(PolygonalInput input, const PolygonalLimits& limits);
```

PolygonalInput is an owned float64/int64 packed record using the existing coedge
encoding. It is a binding input value, not another mutable mesh framework.
PolygonalAssessment has read-only access to complete facts, a typed orientation
result, and optional admitted cells. Only assessment can construct admitted cells.
Admitted cells retain the assessment's immutable storage and expose signed incidence;
there is no caller-supplied boolean authorizing chain construction. Results must not
accept a second raw mesh with which their incidence could be accidentally combined.

Use one owner for copied input and retained computed data. Do not introduce a
persistent native-handle registry or cross-call cache. The host analyzer requests
one assessment and uses its facts and admitted incidence together. Independent
existing entry points may assess independently; a Python read-only array flag is
not sufficient justification for a global identity cache.

No AdmissionPolicy parameter initially: the existing restricted admission rule is
fixed. Add a policy only when there is an actual supported choice. No runtime
Strategy, backend selector or virtual hierarchy is justified.

## Complete interface contract

- Strict owned binding input: finite float64 XYZ, int64 endpoints/coedges/offsets,
  documented shapes/layout and supported unit metadata. Copy under the GIL before
  native work; range-check sizes and signed coedge magnitude before indexing.
- Preserve current host rejection of invalid layout, endpoint references, zero or
  out-of-range coedges, and faces with fewer than three coedges. These are input
  failures. Do not silently expand the host raw-carrier contract in this slice.
- Structurally decodable disconnected loops, repeated cycle vertices, duplicate
  faces, collapsed edges, nonmanifold edges/links and unused entities remain
  successful diagnostic assessments. Retain every currently reported defect and
  its deterministic ordering, with no admitted cells where current rules refuse.
- Open edges and inconsistent input face orientation do not themselves prevent
  cellular admission. Closedness, consistent orientation and admission remain
  separate facts. Orientation conflicts are distinct from current inconsistent-edge
  diagnostics. Preserve all-component sign solving, deterministic seed/traversal
  behavior and nonmanifold-edge failure in orientation_solution.
- Duplicate-face equivalence retains rotation and complete reversal semantics.
  Coordinate collapse remains exact endpoint equality; add no welding tolerance.
- Admitted incidence keeps source vertex/edge/face order. D1 is V by E with -1/+1
  endpoint coefficients; D2 is E by F with signed coedge coefficients. No display
  triangulation or simplicial expansion is involved. Preserve the existing exact
  integer chain validation before F2 conversion; export coefficients as int64.
- Local IDs refer to the copied input's ordinals. No compaction, renumbering or
  durable revision identity is needed for this slice. Owner association is enforced
  by construction; typed IDs alone do not establish it.
- Checked logical limits cover input bytes, work, retained storage and output bytes.
  Specify counters/defaults with fixtures before implementation. Exhaustion returns
  a typed resource failure, not a complete assessment or admissibility verdict.
  Do not translate resource exhaustion into invalid geometry. Allocation failures
  remain exceptions. Logical budgets do not bound process RSS.
- No planarity, nonintersection, outwardness or physical-solid claim follows from
  cellular admission. Geometric triangulation keeps its separately restricted rules.

The broader handoff asks for unresolved-reference diagnosis. The current host
constructor forbids those references. Preserve its contract now; a future wider
raw-document carrier requires its own explicit interface and qualification.

## Reuse and file placement

Refine native/SimplicialComplex.hpp and .cpp as directed by the file inventory.
Extract private loop/index helpers only where the existing polygonal operations and
new assessment actually share semantics. Keep float/int legacy operations unchanged;
a narrow owned double/int64 input is justified by the host's precision contract.
Avoid templating the entire geometry hierarchy to support this one addition.

Reuse SparseCSR's signed incidence layout where it fits. Its int8 coefficients can
represent these admitted incidence entries; binding export widens exactly to int64.
Check index representability and keep chain-product arithmetic wide and checked.
Do not make F2 columns a subclass or reinterpretation of signed CSR.

Extend native/bindings/module.cpp and its README using the existing pybind11 copy,
GIL, error and independently owned output conventions. Keep CMake and setuptools
building the same implemented source. Adapt polygonal_cells.py and topology.py;
repair behavior remains exercised through its existing interface. Do not activate
surface, UV, OCCT or tracing scaffolds.

## Acceptance sequence

1. Characterize existing host interfaces: disk, cube, torus, disconnected shells,
   flipped faces, orientation conflicts, broken loops, repeated vertices, rotated
   and reversed duplicates, pinched links, unused entities, exact collapsed edges,
   and empty input. Retain diagnostic ordering and exception contracts.
2. Implement the native assessment and admitted incidence through native interface
   tests. Compare exact D1/D2 against the existing independent matrix fixtures;
   exercise entity renumbering and exact chain identity.
3. Bind and route the analyzer first, then admission/orientation/repair consumers.
   Preserve the current public host entry points and result behavior. Keep reference
   calculations in tests, with one production implementation and no fallback switch.
4. Qualify alias mutation, owner lifetime, independent outputs, invalid shape/dtype,
   int64 extremes, float64 distinctions lost by float32, checked sizes and exact
   budget limits. Failure must not mint an admitted result.
5. Run focused native/host contracts, relevant root tests, installed-wheel tests,
   CMake Debug/Release/sanitizers and changed-surface lint/type checks. Record any
   baseline failures separately. Refresh the manifest only for deliberate changes,
   preserving unrelated dirty work.
6. Measure small and representative large inputs through host analysis and the
   binding, separating conversion/retention costs where measurable. Report actual
   costs rather than assuming the language change is a speedup.

Completion means shared native facts, preserved host diagnosis/admission/orientation,
exact admitted incidence, owned binding evidence and a reviewed implementation
record. Surface preparation and native display identity remain later slices.

## Source anchors

- docs/reviews/native-f2/IMPLEMENTATION.md
- docs/NATIVE_EXTENSION_FILE_PLAN.md
- native/README.md and native/SimplicialComplex.hpp
- src/cad_integrity/models.py:51 (raw input contract)
- src/cad_integrity/polygonal_cells.py:109 (admission)
- src/cad_integrity/topology.py:64 (orientation), :111 (analyzer)
- tests/test_polygonal_cell_admission.py (independent signed matrices and invariants)
- cpp-native-handoff-20260921.md, Finding 2 and slice table
- native-seam-design-20260920-232459.md and HTML companion
- architecture-review-20260920-120945-native-extension-roadmap.html
