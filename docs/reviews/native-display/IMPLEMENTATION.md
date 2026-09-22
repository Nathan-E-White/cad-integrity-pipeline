# Native face inspection: slice 3

Implemented from the C++ handoff and seam design after polygonal slice 2 at
35f0096. Starting checkout: 29df902. No motorcycle or native C++ algorithm changes.
The accepted scope and public test seams are recorded in DESIGN.md.

## Implementation and reuse

OCCT display extraction now resolves copied faces through BRepBuilderAPI_Copy
history and checks a complete one-to-one association with the copied face map.
The history identifies the face; the copied occurrence supplies its orientation
and location. Tests caught that distinction: using the history result directly
lost reversed orientation. Meshing remains on a private copy, and the source
shape's triangulation cache remains untouched.

Source face count and missing-triangulation IDs survive extraction. Face and
vertex output limits join the existing triangle limit. These bound retained
extraction/projection counts, not OCCT mesher memory, elapsed time or process RSS.
Missing interiors remain native face rows with explicit issue evidence; no interior
or conforming connectivity is invented.

NativeMeshInspection owns immutable array storage without OCCT handles. Each
retained shape snapshot receives a distinct opaque mesh ID and its STEP digest as
revision; each display receives a fresh projection ID. Original and candidate IDs
are independent, including when geometry or bytes agree. This slice does not infer
cross-revision or original-to-candidate face correspondence. Native face ordinals
belong only to the retained shape snapshot that supplied them.

The existing STEP controller returns native inspection on WorkbenchOutcome, including
original-only results after refusal. Display failure retains native checks and STEP
artifacts with explicit warning evidence. Legacy figures remain available to existing
controller callers and build_app(inspection_enabled=False). The normal STEP tab uses
the existing inspection workspace and avoids a second Plotly tessellation.

V2 polygonal delivery keeps its existing fields and meanings. Native V3 records
carry native_face and projection_id; browser triangle picks require the matching
projection. Entity resolution checks mesh ID, revision, domain and ordinal. No
native vertex/edge identity is fabricated from display vertices/segments. Native
controls expose faces only, including while the candidate pane is vacant. Native
kernel checks remain in the existing decision brief; polygonal category controls
and counts are not presented as native diagnostic coverage.

The existing renderer, face overlay, tables, transport and session admission are
reused. No new viewer, runtime dispatch framework, OCCT binding, workflow release
policy, compute submission, or native numerical implementation was introduced.

## Red-green and qualification evidence

- Source correspondence fixture initially failed because FaceTessellation lacked
  source_face_count. Real disjoint asymmetric faces, a translated occurrence and a
  reversed face now have the expected source IDs, positions and orientation.
- The STEP controller fixture initially failed because inspection was None. It
  now returns two owned snapshots with separate scope and projection identities.
- V3 parser fixture initially failed with Unsupported inspection version. Native
  picks now select all triangles of the native face and refuse stale revision,
  scope, projection and foreign polygonal/vertex targets.
- Output face/vertex budget fixtures initially failed for unsupported parameters;
  they now refuse extraction at the declared limits.
- A real unbounded OCCT face remains listed while a bounded neighbor renders.
  A kernel mesher failure leaves retained STEP evidence and explicit display
  diagnostics. Array writeability cannot be reopened on retained inspection data.
- Spec review found a vacant-pane toolbar fallback to polygonal picking. A real
  open-face STEP refusal reproduced Face instead of Native face in the installed
  viewer. The corrected toolbar derives its native domain from the document.
- Standards review identified a weak canvas-pick assertion. The browser test now
  clears selection and verifies absence before clicking, so a no-op pick fails.

## Verification

- Full root Python suite: **354 passed**, no skips, 25.15 seconds; 90% aggregate
  statement coverage. No production Python code changed after this run.
- Changed Python modules: Ruff and mypy pass; compileall passes.
- Root Ruff and mypy remain non-green exclusively in pre-existing
  src/cad_integrity/mesh_motorcycle.py (including undefined _gen_synthetic_mpaths).
  This slice does not change that deferred work.
- Frontend contract/state/transport suite: **16 passed**. Svelte check reports
  zero errors and zero warnings.
- Component frontend build, sdist and wheel succeeded with the Pixi Python 3.13
  toolchain. Parent isolated wheel build succeeded with setuptools 84.0.0 and
  pybind11 3.1.0. No C++ changes require rerunning native algorithm qualification;
  the earlier unfiltered motorcycle CMake failure remains outside this slice.

- Installed parent browser suite: **7 passed**, including both native STEP tests
  and all five retained polygonal tests. Actual canvas picks, independent pane
  selection, replacement clearing and the refused-candidate vacant pane passed.
  The native screenshot was visually inspected.
- Parent and component wheels installed into a temporary Python 3.13 environment
  outside the source tree, sharing the qualified Pixi dependency environment.
  Package, native extension and component imports all resolved inside the temporary
  environment. **42 focused tests passed**, no skips; the copied test file emitted
  one unregistered `cad` marker warning because repository pytest settings were not
  copied. This was not a fully independent dependency-environment qualification.
- Artifact manifests and scoped diff whitespace checks pass. Manifest regeneration
  also reconciles the already committed motorcycle rename/addition at 29df902;
  motorcycle source and target definitions are unchanged by this slice.

## Standards review

Independent read-only standards review: 0 documented-standard violations and 0
remaining actionable smells. The browser verification concern above was corrected
and the reviewer confirmed the source change.

## Spec review

Independent read-only spec review found the vacant-pane picking issue above. It was
corrected; the reviewer confirmed 0 remaining spec findings. This establishes local
implementation and review evidence, not hosted CI, cross-platform qualification,
native repair authority or a conforming surface realization.

## Next primary slice

Slice 4: owned surface triangulation and operator assembly, retaining the Python
solve and qualifying chart results. Preserve the handoff's concave/warped cases,
correspondence, precision and cache-invalidating inputs. Motorcycle work remains
an independent deferred branch.
