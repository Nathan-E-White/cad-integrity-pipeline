# Desired features

Planning register for capabilities we want to develop. Entries describe desired
behavior, not implementation commitments or completed integration.

Related registers:

- [Existing capabilities awaiting integration](UNINTEGRATED_CAPABILITIES.md)
- [Unanswered design decisions](OPEN_DESIGN_DECISIONS.md)
- [Active native Slice 7b completion plan](NATIVE_SLICE_7B_IMPLEMENTATION_PLAN.md)

## F-001 — Identity correspondence across mesh modifications

Status: desired; end-to-end correspondence is not implemented.

### Desired behavior

Retain explicit correspondence between entities in a mesh before and after
modification. Use this correspondence to connect inspection selections and
diagnostic targets across Original, Candidate, and intermediate mesh revisions.

Correspondence should describe vertices, edges, and faces, including entities
that are retained, merged, split, created, or removed. It must support relationships
other than one-to-one and identify the mesh revisions to which the entities belong.
Equal numeric indices alone do not establish correspondence.

For a sequence of modifications, retain enough operation-level correspondence to
relate the original mesh to the resulting candidate. Missing or ambiguous
correspondence must remain explicit rather than being inferred from proximity.

### Existing foundation

[`WeldResult`](../src/cad_integrity/repair.py) already exposes
`old_to_new_vertex` and `old_to_new_edge` maps. However,
[`RepairResult`](../src/cad_integrity/pipeline.py) does not retain a composed
correspondence for the complete repair workflow. This feature extends and carries
forward existing operation-level information rather than assuming no maps exist.

Display triangle-to-source-face mapping is a separate relationship: it identifies
the source face represented by a rendered triangle within a mesh revision. It does
not establish correspondence across modifications.

### Agreed behavior until available

Original and Candidate selections remain independent until explicit correspondence
maps are available. A selection in one mesh must not select an entity in the other
merely because their numeric IDs match.

Camera movement may remain linked for views sharing a coordinate frame; camera
linkage does not imply entity correspondence.

### Future design work

Define how correspondence is represented, composed across operations, and exposed
to inspection. Decide how a selection expands across merges or splits and how
removed or unmapped entities appear in linked views. These details remain open.

## F-002 — Retained inspection snapshots

Status: desired; deferred from the initial polygonal projection slice.

### Desired behavior

Retain a downloadable, versioned inspection snapshot for a run. The snapshot should
preserve geometry, diagnostic categories, entity identities, mesh revisions, units,
and display-to-source mappings so the inspection can be reconstructed without
rerunning analysis.

Treat the snapshot as a derived artifact alongside the existing evidence. It
records computed inspection data; it does not require saving camera position,
hover state, or temporary selections.

### Future design work

Define the snapshot format, compatibility rules, bounded loading, and reopening
workflow. Decide artifact retention and publication-failure behavior, and ensure
that incomplete snapshots cannot appear to contain a complete inspection result.

This entry records a desired capability, not a commitment to add snapshot
publication to the current integration slice.

## F-003 — Computation-to-result state management

Status: desired; deferred from the initial polygonal projection slice.

### Desired behavior

Manage computation lifecycle and displayed results explicitly, associating each
result with the computation that produced it. Coordinate inspection geometry,
diagnostics, reporting views, selections, and download references so results from
different runs cannot be presented as one result.

### Agreed behavior for the current cut

Starting a new computation immediately clears the previous displayed results:
inspection geometry and overlays, diagnostic rows, reporting views, selections,
and result download references. The previous result does not remain inspectable
while the new computation runs.

Clearing the displayed result does not mean deleting retained artifact files.
Existing artifact-retention behavior remains separate. A failed new computation
must not restore stale results from the previous run.

### Future design work

Define computation and result identities, lifecycle states, cancellation and
supersession, handling of late completions, and coordinated result replacement.
Decide whether previous results can remain inspectable during computation and,
if so, how their identity and relationship to the running computation are shown.
That richer behavior is deferred, not agreed for the current cut.

## F-004 — Concurrency management

Status: desired; follows F-003 (computation-to-result state management).

### Desired behavior

Manage concurrent computation requests with explicit admission, execution, and
result-delivery rules. Build on the computation identities and lifecycle defined
by F-003 so overlapping or late completions cannot replace the wrong result.

### Agreed behavior for the current cut

Only one computation may be active per browser session. While a computation is
active, both polygonal run actions are disabled until it finishes. Session-level
admission must also prevent overlapping execution; disabled controls alone are
not the enforcement mechanism.

This is a per-session rule, not a global single-computation limit. It does not
establish a policy for shared resources across sessions.

### Future design work

Define queueing versus rejection, cancellation and supersession, resource limits,
and coordination across sessions. Decide whether and how concurrent computations
may be exposed after F-003 establishes result ownership and lifecycle semantics.

## F-005 — Multiple-entity selection

Status: desired; deferred from the initial polygonal projection slice.

### Desired behavior

Allow an arbitrary set of mesh entities to be selected together for inspection,
with explicit ways to add, remove, and clear members. Keep entity identities
scoped to their mesh revision and avoid duplicate membership when entities belong
to multiple defect categories.

### Agreed behavior for the current cut

Each viewport supports one selected entity at a time or one whole defect category.
Selecting an entity or category replaces that viewport's previous selection.
Whole-category selection may highlight many entities but does not provide an
arbitrary editable selection set.

Original and Candidate retain independent selections, as recorded under F-001.

### Future design work

Define additive and range selection, keyboard modifiers, mixed vertex/edge/face
sets, and interaction between category selections and individual members. Decide
how combined selections are displayed and focused without changing the underlying
diagnostic category counts.

## F-006 — Keyboard shortcuts for viewport picking modes

Status: desired; deferred from the initial polygonal projection slice.

### Desired behavior

Provide keyboard shortcuts for switching viewport picking between Vertex, Edge,
and Face modes. Keep the active mode visible in the existing mode control.

### Agreed behavior for the current cut

Provide an explicit Vertex / Edge / Face picking-mode control. Table selection
can select any entity type independently of the viewport's current picking mode.
Keyboard shortcuts are deferred.

### Future design work

Choose key bindings and focus scope, including which viewport receives the mode
change. Avoid intercepting text entry or conflicting with browser and accessibility
commands. Define how users discover the shortcuts. No particular bindings have
been selected.

## Deferred computational capabilities from the maximal Slice 7 plan

The following capabilities preserve the useful ambitions of the maximal Slice 7
plan without placing them on the current native completion path. They are desired
computational capabilities, not commitments to one combined programme, one shared
dependency bundle, or simultaneous product integration. Each requires its own
caller, admission contract, evidence, resource limits, and qualification slice.

## F-007 — Shape-relative sampled medial evidence

Status: desired computational capability; deferred beyond Delaunay construction.

### Desired behavior

Accept either a provenance-carrying boundary sample set or samples produced from an
admitted closed OCP shape. Construct a finite sampled Voronoi graph, then retain
inside/on/outside classification, closest-boundary/contact evidence, sampled-radius
comparisons, source correspondence, units, policies, and resource use.

The evidence must distinguish the raw finite Voronoi graph from any subset admitted
by shape-relative verification. It must not describe the result as an exact medial
axis, a complete Voronoi complex, a maximal-ball certificate, or repair authority.

### Existing foundation and deferral

The existing native finite-dual extractor and the separately planned Delaunay
constructor supply the numerical foundation. Automatic OCP boundary sampling, a
goal-specific workbench controller, pruning/significance policy, retained artifacts,
and inspection projection remain deferred until a real shape-to-medial workflow is
selected.

## F-008 — Bounded STL feature and primitive reconstruction evidence

Status: desired computational capability; deferred from the current native slice.

### Desired behavior

Admit bounded STL input with explicit units while retaining original bytes, facet and
corner identities, dropped-facet disposition, and source-corner-to-deduplicated-point
correspondence. Produce inspectable local-feature validity, deterministic primitive
membership, fit residuals, source support, complete unassigned selections, and
full-precision plane/cylinder geometry cards.

The result is approximate reconstruction evidence. Planar hulls and cylindrical
envelopes do not recover trim topology, prove a repaired shell, or turn unassigned
regions into inferred NURBS surfaces.

### Future design work

Freeze total memory/work limits, dimension-aware tolerances, reproducible fitting
policy, point/primitive inspection identity, and the host-owned result interface.
Keep supplied-surface NURBS evaluation independent of this workflow.

## F-009 — Qualified fitted-fragment STEP publication

Status: desired computational capability; deferred until F-008 and shared translator
coordination are qualified.

### Desired behavior

Construct bounded plane and cylinder fragments from qualified geometry cards and
publish them as explicitly named derived STEP artifacts. Coordinate all OCCT
translator settings through one process-wide owner, restore settings on failure,
reimport each output, and record only successfully retained files.

Fitted fragments remain approximations and never become an audited repair candidate
or repaired solid. Publication is an explicitly requested operation until evidence
supports a different product policy.

### Future design work

Define mixed-workflow concurrency, kernel round-trip acceptance, partial publication,
unit conversion, and the relationship between card support, unassigned regions, and
export eligibility.

## F-010 — Qualified directional-field generation and audit

Status: desired computational capability; deferred pending a field domain contract.

### Desired behavior

Admit an immutable oriented surface and either preserve an imported directional field
or generate a new field from explicit constraints. Retain representation and basis,
matching, transported effort, singularity indices, boundary and generator-loop
coverage, feature-alignment residuals, undefined regions, provenance, and backend-
specific admission decisions.

Imported values must not be silently normalized, smoothed, or regenerated. A field
may be displayable while remaining inadmissible for tracing or seamless integration.

### Future design work

Choose and pin a field backend only after its ownership, licensing, packaging, index
conventions, global consistency checks, and actual caller are qualified. The earlier
Directional investigation is evidence for this decision, not a dependency commitment.

## F-011 — Fully integral seamless parameterization and IGM

Status: desired computational capability; deferred as a separate research and
implementation programme.

### Desired behavior

From an admitted surface and qualified field, build a deterministic cut, comb the
field, integrate a sign-symmetric four-function, solve integer seam translations,
and retain seam, singularity, residual, Jacobian, distortion, conditioning, solver,
budget, and original-to-cut correspondence evidence.

Infeasible, uncertain, or budget-exhausted runs must retain useful partial evidence
without publishing a qualified parameterization. A relaxed smooth field or standalone
integer length vector does not establish a seamless global parameterization.

### Future design work

Freeze topology and boundary admission, singularity policy, scale selection, integer
solver behavior, interruption, dependency/license choices, and independent analytic
fixtures before implementation begins.

## F-012 — Chart-axis tracing and derived quad remeshing

Status: desired computational capability; deferred until F-010 and F-011 are
qualified.

### Desired behavior

Trace parameterized triangle-axis paths over an admitted chart with explicit seam
transitions, collision participants, recurrence witnesses, uncertain ordering, and
committed prefixes on exhaustion. Extract and stitch integer-isoline arrangements
into a value-owned derived mesh with source-triangle/barycentric correspondence.

Qualify finite coordinates, orientation, incidence, noncollapsed faces, surface
deviation, self-intersection, and the declared pure-quad or quad-dominant mode before
publication. Any quad result should be independently admitted by the existing
polygonal and canonical-quad modules.

### Future design work

Define the chart event scheduler, exact-versus-filtered arithmetic, seam and periodic
state identity, mesher acceptance, source selection behavior, and inspection payload.
Raw cross-field streamlines remain a separately named capability and cannot substitute
for chart-axis or IGM evidence.
