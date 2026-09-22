# Slice 3: native face identity through display projection

Implementation scope authorized from the C++ handoff and seam design, following
polygonal slice 2 at 35f0096. Starting checkout: 29df902. Motorcycle sources and
build configuration are outside this slice.

## Decision and test seams

Carry native face identity through the existing OCCT display extraction, owned
WorkbenchOutcome inspection result, and installed inspection workspace. Test the
existing tessellate_for_display and run_step_workbench interfaces, encode_inspection,
and the browser parser/target resolver and installed workspace. These are the
handoff's projection/identity test seams; do not test private adjacency or callbacks.

OCCT copy history must associate each copied face with its source face ordinal.
Meshing happens on the copy. No coordinate matching or assumption that two shape
traversals enumerate faces identically is allowed. Missing triangulations retain
the source face and issue evidence. Resource refusal must not manufacture a partial
successful projection. This remains display geometry, not conforming realization.

Native inspection owns arrays without OCCT handles. Geometry scope is unique to the
retained shape snapshot; its revision records the corresponding STEP digest.
Original and candidate scopes are distinct even if their bytes happen to agree.
A fresh projection identity scopes display triangle ordinals. Native face targets
carry geometry scope, revision, native_face domain and a checked local ordinal.
No cross-revision or source-to-candidate face correspondence is inferred.

Keep polygonal v2 delivery unchanged. Introduce v3 for native-face display records,
with explicit native_face domain and projection identity. Display-only vertices and
segments do not become native vertices or native edges. Native picking/table rows
therefore expose faces only in this slice. Stale geometry/revision/domain targets
and stale projection triangle references fail resolution. Selection and hover reset
when the document changes. No compute submission or repair action is introduced.

Reuse the existing renderer, overlay and workspace; do not introduce a second viewer
or rewrite OCCT meshing in C++. Reuse the STEP controller's request guard, checks and
non-atomic artifact release. Preserve legacy Plotly delivery for existing callers;
the normal inspection-enabled app uses the owned workspace result. Inspection
failure must not change kernel acceptance or remove retained STEP evidence.

## Acceptance

- An asymmetric real OCCT shape maps display triangles to correct source faces,
  including transformed/reversed faces and unmeshed source ownership.
- Multiple triangles select one native face; absent face interiors remain listed.
- STEP original/candidate snapshots remain distinct, immutable and usable without
  source shape handles. Refusal retains original-only inspection.
- v2 polygonal behavior remains unchanged; v3 parsing rejects malformed ownership,
  foreign entity domains and missing projection identity.
- Stale revision, scope and projection references fail; remeshing cannot reinterpret
  an old display-triangle ordinal.
- Installed app displays native face rows, highlights/picks corresponding geometry,
  supports independent original/candidate selection, and clears on replacement.
- Focused Python/frontend tests, typechecks, component build, installed browser
  checks, full root Python suite once, artifact manifest and two-axis review.

No native tracing, geometric repair, conforming mesh claim, GPU compute, database,
or universal geometry carrier is included. Existing native C++ algorithms are not
changed; this slice closes the host-to-inspector identity seam.
