# Slice 4 design: owned polygonal surfaces and qualified charts

Proposal, 22 September 2026. Inspected clean checkout `6ef60c0`.
This is design work; no numerical implementation or new qualification is claimed.

## Recommendation

Implement an owned surface module behind a focused Python harmonic caller. Native
code owns selected-patch admission, deterministic triangulation, correspondence,
cotangent assembly and local chart qualification. Python retains constraints,
SciPy factorization, update reuse, residual acceptance and fallback.

One immutable surface owner is the central decision. Operators and admitted charts
retain it; solving and chart qualification never retriangulate the source. This
provides depth by concentrating ownership, precision, provenance and geometric
checks behind three native operations.

The latest implementation record explicitly names this as the next primary slice.
The important addition to the earlier sketches is a concrete installed caller:
HarmonicSystem currently exists in the standalone integration bundle, while root
packaging includes only src/cad_integrity. A native library plus bundle tests would
not establish host adoption.

## Existing evidence and reuse

- `native/surface_preparation.hpp` and `.cpp` are declaration-only scaffolds.
- `native/SimplicialComplex.hpp::PolygonalInput` already owns double coordinates,
  int64 coedges and unit metadata. Reuse this conversion vocabulary and polygonal
  assessment machinery. Legacy Point3 uses float and is unsuitable here.
- `AdmittedPolygonalCells` exposes signed incidence, not surface geometry. Cellular
  admission allows inconsistent orientation. Do not use this carrier as proof of
  an oriented geometric patch or expand it into a universal valid-mesh object.
- `SparseCSR` has int8 incidence coefficients. Cotangent stiffness requires double
  coefficients. A small concrete floating CSR value is warranted; a generic sparse
  hierarchy is not required to preserve integer incidence.
- `integration/mesh_healing_extension/mesh_healing_engine.py` contains projected
  ear clipping, cotangent assembly, HarmonicSystem, UVQuality and their test cases.
  It is the migration reference, not a package the installed host can import.
- Host TriangleMesh is a useful projection shape, but lacks source-face and
  inserted-diagonal correspondence. It need not become the computational owner.
- Slice 3 NativeMeshInspection represents display geometry. Its native face
  provenance does not establish shared-edge conformity or numerical admission.

## Interface and ownership

Illustrative native operations, refining the existing scaffold names:

```cpp
prepare(PreparationRequest) -> expected<Discretization, SurfaceError>
assemble(Discretization, ConfidencePolicy, SurfaceLimits)
    -> expected<Operators, SurfaceError>
qualify_chart(Discretization, OwnedUV, ChartPolicy, SurfaceLimits)
    -> expected<ChartAssessment, SurfaceError>
```

PreparationRequest contains the existing PolygonalInput, explicit selected source
face IDs, triangulation policy and limits. Slice 4 has one actual input form. Do
not introduce a variant for future OCCT realization or borrow display geometry.

Discretization is non-forgeable and retains immutable double XYZ, triangle indices,
source vertex/face maps, original-edge versus inserted-diagonal correspondence,
unit metadata, patch boundary facts and preparation evidence. Source face order is
the requested order; active source vertices are compacted in ascending source-ID
order. Every compact index has a reverse source map. Triangle ordinals belong to
this discretization and its preparation policy, never to a display projection.

Operators retains the discretization and owns finite double stiffness CSR plus
normalized confidence and assembly evidence. CSR has sorted columns, summed
duplicates and checked dimensions/indices. No signed cotangent clamping.

ChartAssessment contains local quality evidence and an optional AdmittedChart.
AdmittedChart owns UV values and retains precisely the qualifying discretization.
Invalid local geometry returns evidence without admission. Malformed input,
unrepresentable arithmetic and budget exhaustion are typed failures. Global UV
overlap is not established by this admission; slice 5 must still resolve ambiguity.

Binding admission checks dtype, native endianness, layout, dimensions and integer
ranges before copying and before releasing the GIL. Reuse existing exception
translation. Python receives private owned handles and immutable views whose base
retains the owner, or independent copies. No writable aliases into native storage.
Mutable SciPy matrices are copies; they cannot mutate retained operators.

## Concrete Python caller

Recommended installed location: `src/cad_integrity/surface.py`, with the existing
HarmonicSystem algorithm migrated in focused form rather than importing the bundle
or copying MeshHealingEngine and its repair/tracing/export behavior wholesale.

```python
surface = prepare_surface(raw_brep, face_ids=selected, policy=policy, limits=limits)
system = surface.prepare_harmonic_system(
    internal_nodes, boundary_nodes, face_confidence=confidence,
    require_full_boundary=True, max_update_rank=32,
)
uv = system.solve(boundary_values, soft_constraints=anchors)
assessment = system.last_chart_assessment
```

Host vertex/face arguments use source IDs; the module owns compact-index translation.
Keep the familiar solve mapping and factorization counters. Expose chart evidence
as a typed result and allow direct qualification of caller-supplied UV through the
surface. With orientation checks disabled, a solve may return locally invalid UV,
but it must not mint an admitted chart. Boundary-only solves remain supported.

Move only the solver, constraint values and residual/update logic needed by this
caller. Keep the integration implementation as an explicit reference during parity
qualification; do not add runtime backend selection or silent Python fallback.
Package tests must run without the integration directory on sys.path. Later
retirement of the independently packaged bundle is a separate compatibility task.

The new caller is snapshot-based. Mutating the original raw arrays after preparation
cannot change a surface or invalidate a completed result. An explicit new preparation
creates new ownership. The existing mutable bundle keeps its stale-system refusal;
if a compatibility adapter is later added there, it must retain that refusal.

## Numerical and admission contract

1. Validate structural decoding before indexing. Assess the selected patch rather
   than requiring the entire source to be an oriented manifold. Reject duplicate
   selected IDs, an empty patch, broken loops, duplicate faces, nonmanifold edges or
   vertex fans, and inconsistent winding. Reuse slice 2 facts internally, retaining
   maps back to source IDs; do not automatically apply orientation multipliers.
2. Preserve the reference projected triangulation: normalized coordinates, simple
   projection checks, original 0–2 quad diagonal where valid, alternate diagonal
   otherwise, and geometric ear ordering for larger polygons. Reversal and vertex
   renumbering preserve the same piecewise-linear facets where the reference does.
   There is no new arbitrary warp cutoff hidden behind “mildly nonplanar”.
3. Preserve concave and warped cases. A convex fast path is optional and only valid
   if it gives the same required triangulation/correspondence. In particular, a
   different diagonal on a warped quad changes the actual surface.
4. Assemble L = diag(W 1) - W, with half-cotangent edge contributions and confidence
   in [0,1] applied to every triangle belonging to its source face. Missing confidence
   defaults to one. Source IDs are validated before indexing; inactive source-face
   confidence may be validated and ignored, matching the reference behavior.
5. Retain normalization and explicit numerical-range failure. No silent float32 or
   index narrowing. Units remain metadata without automatic rescaling.
6. Python validates disjoint internal/boundary sets covering all active vertices,
   required patch boundary constraints and anchoring on assembled nonzero support.
   Zero confidence can disconnect a patch and must not silently pin vertices.
7. Retain SuperLU, complete-current-set soft anchors, bounded Woodbury updates,
   refactor fallback and the reference 1e-10 relative backward-error acceptance.
   Each concurrent worker owns its own HarmonicSystem.
8. Local chart qualification preserves orientation +/-1, flipped/collapsed triangle
   evidence, signed double-area and conformal distortion semantics. Retain explicit
   nonfinite/range failures. Distortion is evidence unless policy expressly adds a
   threshold; local validity says nothing about global injectivity.

## Reuse and invalidation

| Change | Surface | Operators | Solver state | Chart |
|---|---|---|---|---|
| XYZ, connectivity, units, face selection or triangulation policy | New | New | New | New |
| Face confidence | Reuse | New | New | Requalify new UV |
| Internal/boundary membership or ordering | Reuse | Reuse | New | Requalify new UV |
| Dirichlet values only | Reuse | Reuse | Reuse factorization | New |
| Soft target only, same IDs and weights | Reuse | Reuse | Reuse update | New |
| Soft membership or weights | Reuse | Reuse | Replace update; retain base when valid | New |
| Qualification policy/orientation only | Reuse | Reuse | Reuse numerical solve | Requalify |

Reuse initially means retaining the same owned objects, not a global cache keyed by
hashes. Python owns durable source/result identity when a workflow needs it. No
registry or browser command protocol is needed for this programmatic caller.

## Budgets and failure

Use separate input, owned-workspace, deterministic work and output limits following
the existing binding convention. Specify accounting before implementation: selected
loops/maps, triangulation predicates and emitted triangles, assembly contributions,
CSR sorting/accumulation and chart diagnostics must all be charged. Ear clipping
can be expensive; a triangle-count limit alone does not bound its work.

Check multiplication, offset growth and representability before allocation. Errors
carry operation and source entity when available. Preparation and assembly return
no partial successful carrier. Chart budget failure cannot mint admission. Python
and SciPy factorization allocations are outside native logical limits; document
this explicitly rather than promising a process-memory or wall-clock cap.

## Implementation order and acceptance

1. Prepare one owned polygonal patch through the native interface and private binding.
   Exercise a concave polygon, warped quad, orientation reversal, renumbering,
   source correspondence, malformed input, ownership lifetime and budget refusal.
2. Assemble through that owner and wire the installed Python HarmonicSystem caller.
   Compare right-triangle weights, negative cotangents, symmetry, constant nullspace,
   PSD within tolerance, affine reference cases, extreme scales and confidence cuts.
3. Qualify each solve against the same surface. Cover flips, collapse, range errors,
   explicit orientation, boundary-only cases, missing constraints, unanchored
   components, RHS reuse, soft target reuse/removal, refactor and residual fallback.
4. Run installed-wheel tests outside the checkout without integration imports. Check
   binding lifetime/alias behavior, scoped native Release and ASan/UBSan tests, root
   Python checks and applicable manifests. Include the integration reference cases
   explicitly: root pytest testpaths does not collect that suite.
5. Measure preparation, conversion/copy cost, assembly, initial solve, repeated solve,
   qualification and end-to-end cost independently. Report workload and retained
   payload; do not infer speedup from native code or reuse alone.

Tests use prepare/assemble/qualify and the installed harmonic caller, not private
ear-clipping or cache internals. Preserve existing public bundle tests while it
remains independently packaged. Replace redundant internal tests only after the
new interface exercises the corresponding behavior.

Expected edits: existing surface scaffold pair, focused native test, private binding
and stub, setuptools/sdist inventory, native CMake target/test registration, new
focused host surface module/tests, and slice evidence. Shared storage helpers are
extracted only where both consumers actually benefit. No legacy float BVH rewrite.
The unrelated motorcycle target must not be repaired as a side effect; record any
unfiltered build limitation and qualify the selected surface target explicitly.

## Scope and decision

Finish slice 4 with one installed polygonal preparation → harmonic solve → chart
qualification path. STEP conformity belongs to slice 6; UV location belongs to
slice 5. Browser submissions, export/publication policy, NURBS, Delaunay and motorcycle
tracing remain independent work. No existing display or repair workflow is changed.

Deleting this proposed module would restore triangulation, ownership, face mapping,
precision checks and admission obligations to assembly, solve and chart callers.
That is the depth being purchased. A bag of native helper functions would merely
move those obligations across the language seam.

Sources inspected: the two seam reports, native extension roadmap, C++ handoff,
native/README.md, docs/reviews/native-display/{DESIGN,IMPLEMENTATION}.md,
docs/NATIVE_EXTENSION_FILE_PLAN.md, native/SimplicialComplex.hpp,
native/bindings/README.md, src/cad_integrity/{models,polygonal_cells}.py,
integration/mesh_healing_extension/{mesh_healing_engine.py,pyproject.toml,
tests/test_mesh_healing.py}, root setup.py, pyproject.toml and native/CMakeLists.txt.
