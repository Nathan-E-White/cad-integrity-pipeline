# Motorcycle kernel: evidence, admission, and qualification

Research date: 2026-09-20. Status: design research; no native tracing backend is implemented or qualified by this report.

## Implementation placement decision

Following this research, the project decision is to develop motorcycle capability
directly in the parent application, rather than introduce another intermediate
component. The existing inspector remains the display surface. The evidence
contracts and qualification slices below still apply; the native boundary is an
internal parent-app module, not a new separately integrated package.

## Recommendation

Build a small, value-owned native C++ kernel around **field assessment and trace evidence**. Keep the existing inspector as a presentation adapter. Qualify one precisely named tracing mode before adding another. A plausible library combination is Directional for field operations and CGAL for chart-local intersections; Geometry Central is an alternative geometry/field foundation. The reviewed material establishes useful components, not a verified end-to-end library for this package's collision scheduler and recurrence contract.

The immediate decision is the admitted input. An existing pure-quad mesh permits a discrete, topology-driven backend. A triangle mesh with a qualified seamless parameterization permits a different chart-axis backend. A triangle mesh with only sampled cross directions requires a separately qualified integral-line method. Calling all three “motorcycle tracing” would hide most of the engineering cost.

## What the sources establish

| Source | Verified contribution and limit |
|---|---|
| [Eppstein's author explanation](https://11011110.github.io/blog/2008/07/13/quadrilateral-meshes-motorcycle.html) and [2008 paper](https://diglib.eg.org/bitstreams/417e3d00-227c-432b-b84e-fa1638e84084/download) | Canonical partitioning of quad connectivity. Particles leave extraordinary vertices along incident edges and continue through opposite edges at ordinary interior vertices. This is not opposite-side traversal through quad faces. The construction has an orientation-dependent simultaneous-arrival rule. |
| [Directional](https://avaxman.github.io/Directional/) | C++ field representation, matching, processing, streamlines, and integration facilities. Its page advertises version 3.0 while retaining older 2.0 wording; pin a source revision and selected headers before qualification. It states primarily MPL-2 licensing with file-specific exceptions. No selected dependency version or build has been qualified here. |
| [Geometry Central direction fields](https://geometry-central.net/surface/algorithms/direction_fields/) | Supports power-represented symmetric fields, field generation with boundary/curvature alignment, and index computation. Vertex-sampled fields place computed singularities on faces, and face-sampled fields on vertices. A fourth power represents a cross, not a single chosen branch. |
| [Geometry Central geodesic tracing](https://geometry-central.net/surface/algorithms/geodesic_paths/) | `traceGeodesic` follows intrinsic straightest paths on a manifold mesh. It supports boundaries, barriers, iteration limits, and returned surface points. Its result includes endpoint direction and length. This does not by itself implement following a varying cross-field or deciding collisions with newly deposited tracks. |
| [CGAL intersection API](https://doc.cgal.org/latest/Kernel_23/group__intersection__linear__grp.html) | Segment intersections can be empty, a point, or an overlapping segment. Preserve that distinction. [EPECK](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__exact__constructions__kernel.html) supplies exact predicates and constructions, including points constructed from doubles. Exact arithmetic on admitted coordinates does not establish accuracy of the field or its numerical integration. |
| [Myles, Pietroni, Zorin, 2014](https://ashishmyles.com/projects/files/14fieldtrace.pdf) | Their method combines robust cross-field integral-line tracing, layout changes, and global parameterization. It may add cones to resolve obstructions. The paper explains why piecewise-constant tracing can merge or split integral lines and instead uses angular interpolation for its purpose. A field need not admit a global parameterization with its original topology. These are paper-reported results, not capabilities reproduced in this repository. |
| [Yu, Li, Gong, 2025 DOI](https://doi.org/10.1016/j.cag.2025.104173) | The publisher search-indexed summary verifies the title, authors, and reported piecewise tracing and feature-preserving simplification contributions. Direct publisher full-text retrieval returned HTTP 403. The attachment describes parameterized triangles, but detailed input assumptions, numerical rules, guarantees, code availability, and performance remain unverified here. Treat the parameterized backend below as our proposed input contract, not a reproduced implementation of this paper. |

The supplied [NYU 2014 PDF](https://cims.nyu.edu/gcl/papers/myles2014rfa.pdf) failed browser retrieval; the author's alternative PDF was downloaded and its 14 pages extracted. The original publisher copy of the 2008 paper was likewise downloaded and its 10 pages extracted, including the construction on printed page 1481. The 2025 publisher access limitation is a research gap, not evidence that the method is unsuitable.

## Correction to the existing project description

The canonical construction is **vertex-to-vertex along mesh edges**. The existing helper is explicitly a **quad-strip diagnostic**, choosing opposite sides of successive faces. The older [mesh-healing research note](/Users/nathanwhite/Software-Development/cad-integrity-pipeline/docs/MOTORCYCLE_PATH_MESH_HEALING_RESEARCH.md) describes the latter while attributing it to the canonical construction; this report supersedes that description.

The current [`MotorcycleGraphTracer`](/Users/nathanwhite/Software-Development/cad-integrity-pipeline/integration/mesh_healing_extension/mesh_healing_engine.py:957) uses occupied edges/faces and sequential seed execution. It does not return chronological collision records. Replacing its internal stepping rule is insufficient: its scheduler, state, and evidence contract are also different.

## 1. What constitutes a collision?

### Surface and time must both agree

The deposited-track definition comes from the original construction: particles stop on tracks that earlier motion actually produced. A geometric intersection of unlimited candidate trajectories is only an event candidate. [Author explanation](https://11011110.github.io/blog/2008/07/13/quadrilateral-meshes-motorcycle.html)

**Proposed operational definition.** At a common surface location `x`, let trace A arrive at `tA`, and let B's first actual deposition there occur at `tB`. A track collision requires `tB < tA`, with B having reached `x` before its terminal time. Equality goes through the declared simultaneous policy. The stored arrival of B is its arrival at `x`, not B's launch time or eventual stopping time. Retain both times even after B has stopped elsewhere: deposited tracks persist.

Use carrier identities, not 3D proximity, to decide whether locations coincide. A triangle interior location is `(mesh identity, triangle ID, barycentric coordinates)`. Edge and vertex hits require canonical shared-element ownership. A seam must have an admitted transition identifying the two local representations. Two overlapping UV charts, coincident display positions, or folded sheets are not sufficient identification. Conversely, two incident faces can share a real edge event even though their face IDs differ.

### Proposed scheduler invariants

1. Separate **candidate continuation** from the committed deposited prefix. Only the latter blocks motion.
2. Order prospective advances, intersections, boundary hits, and launches by their declared time model. Batch genuinely simultaneous events; never let priority-queue insertion order decide their meaning.
3. Attach trace revision and segment identity to every candidate. When a trace terminates, invalidate candidates requiring its unrealized continuation. Retain events involving its already deposited prefix.
4. Revalidate candidate carrier, participant reachability, and arrival times before committing an event. A's invalid future segment must never stop C after B has already stopped A.
5. Commit the entire simultaneous group according to one policy, then update terminal states and create subsequent candidates. Multi-party encounters require a group record, not arbitrary pairwise processing.
6. Bound events, stored segments, candidate intersections, traversal steps, and arithmetic work. Exhaustion returns committed evidence and an explicit incomplete result.

A naïve epsilon equality test can be non-transitive: A is near B and B near C while A is not near C. Choose exact comparable times when possible. Otherwise retain certified time intervals, refine ambiguous comparisons, and return `unresolved_event_order` if the budget runs out. Do not resolve numerical ambiguity by silently changing the simultaneous policy.

### Policy fields that must be frozen

| Policy | Proposed contract requirement |
|---|---|
| Speed metric | Name topological edge steps, chart distance, or intrinsic physical arclength. Include launch times, speed units, and how seam transitions affect elapsed time. A unit edge step is not physical constant speed on unequal edges. |
| Simultaneous arrivals | Name the exact backend-specific rule. `stop_all` is suitable for an experiment but must not carry a canonical-2008 label. Preserve orientation and participant incidence for reproducibility. |
| Source exemptions | Shared launch points should not immediately kill all emitted branches. Exempt only the declared launch incidence/time; a later return to that source is a separate encounter. |
| Boundaries and features | Declare stop, barrier, or explicitly qualified transition. A boundary is not a reason to extrapolate into a missing face. Include boundary edges in a canonical partition output when that is the chosen algorithm. |
| Overlap | Return overlap endpoints and parameter/time intervals. Compute the earliest contact with a deposited subset, including opposing travel. Do not pick an arbitrary point from an overlap. |
| Self-contact | Exempt the immediately contiguous path endpoint; distinguish returning to older deposited geometry from ordinary segment adjacency. |
| Determinism | Reordering a seed array must not alter geometry, terminal reasons, or normalized events. Stable semantic IDs may control presentation order, not silently determine collisions. |

For an initial triangle backend, rejecting unsupported overlap configurations with retained evidence is preferable to claiming a qualified overlap rule. For pure quads, shared-edge and head-on cases are part of the backend's required qualification.

### Canonical tie rule

The 2008 construction advances particles in equal edge steps. Opposing encounters stop both particles; reaching an already traversed vertex or the boundary stops the arriving particle. At a vertex, three or four simultaneous arrivals all stop. With exactly two perpendicular arrivals, the particle on the clockwise side of the right-angle sector between their incoming tracks stops; the other continues. This is defined by the oriented surface's cyclic order, not a camera view. The motorcycle graph also includes boundary edges. [Original paper, construction section](https://diglib.eg.org/bitstreams/417e3d00-227c-432b-b84e-fa1638e84084/download)

An opposing meeting can occur inside an edge between vertex ticks, for example at a half-step. The implementation must schedule that contact; a vertex-arrival-only collision loop misses it.

Changing start times or speeds produces an experimental scheduling policy. Reproducing one appealing picture does not establish canonical partitioning under mesh isomorphism.

## 2. What constitutes a cycle?

The following are proposed evidence categories, not interchangeable labels:

| Concept | Required evidence | What is insufficient |
|---|---|---|
| Periodic trajectory | A repeated complete deterministic traversal state, with the intervening trajectory and the equality model | Visiting a face twice or merely approaching an old point |
| Self-collision | Contact with the trace's own previously deposited track, with both visit times and surface location | A nearby sample or adjacent polyline endpoint |
| Graph cycle | A closed sequence of graph edges/vertices after splitting at qualified events; declare directed or undirected interpretation | One trace's loop label |

For pure-quad continuation, a candidate complete state includes mesh revision, directed incoming halfedge, branch/continuation mode, and orientation. Record the first and repeated offsets and the intervening halfedges. A finite state repeated under a fixed deterministic transition map proves recurrence of that **transition map**. If collision rules stop the trace on its own earlier track, the terminal outcome is self-collision; a continuation witness can accompany it. If future behavior depends on changing deposited tracks or time-dependent input, geometric state alone does not prove repetition of the full scheduler state.

For triangle tracing, include carrier position, directed tangent/branch, chart transition state, and relevant integrator state. A periodic surface identifies points through its quotient/seams; retain the transition word or winding information rather than confusing equal chart coordinates with equal surface states. An exact repeat in a floating-point discretization establishes only recurrence of that discretization, unless additional mathematical certification is supplied.

Use `cycle_witnessed`, `possible_recurrence`, `self_collision`, and `budget_exhausted` distinctly. A near-return finding should carry position/direction residuals, tolerances, and the compared path range. It can coexist with a later boundary termination. A budget limit is a stopping fact, not evidence of periodicity. Graph-cycle assessment should be a separate postprocessing result and remain incomplete if tracing or event splitting is incomplete.

## 3. What constitutes an acceptable cross-field?

An imported field must remain inspectable without being silently regenerated, smoothed, normalized, or optimized. Generation and modification are separate requested operations with new input identities.

Directional distinguishes branch matching from angular effort. Matching identifies branch correspondence modulo the field degree; it cannot retain all complete turns. Its tutorial warns that principal reconstruction can alias undersampled fields and that `principal_matching()` does not populate boundary/generator-loop singularities. Those are explicit missing measurements, not zeros. [Directional tutorial, principal matching and sampling](https://avaxman.github.io/Directional/tutorial/)

The inspected [`principal_matching.h`](https://raw.githubusercontent.com/avaxman/Directional/master/include/directional/principal_matching.h) expects counterclockwise raw vectors and divides complex field values. Validate ordering and definedness before calling it. [`effort_to_indices.h`](https://raw.githubusercontent.com/avaxman/Directional/master/include/directional/effort_to_indices.h) uses cycle effort plus degree-scaled curvature, divided by `2π`; its integer is **degree times the conventional index**. Its field overload retains local-cycle singularities. Do not omit the geometric transport correction or confuse a stored `+1` with conventional cross-field index `+1` rather than `+1/4`.

**Proposed audit evidence:**

| Audit | Records and checks | Admission consequence |
|---|---|---|
| Definedness | Per-sample finite checks; magnitude before normalization; representation, basis, degree, units; zero/near-zero thresholds | Undefined directions block tracing where used; preserve original values |
| Local consistency | Signed transported angular residual modulo `π/2`; raw matching; lifted effort when supplied; edge ID and ambiguity flag | A small residual is evidence about samples only |
| Feature alignment | Residual to declared boundary/feature tangent; corner policy; feature identity and provenance | Report unassessed features separately from aligned ones |
| Singularities | Carrier, oriented cycle, signed conventional index and scaled integer, pre-rounding residual, unresolved cases | Never silently round an inconsistent cycle into a confirmed singularity |
| Global consistency | Oriented boundary and noncontractible-loop basis; transport/holonomy and effort; index convention; coverage | Missing loops are `not_assessed`; no blanket Poincaré–Hopf claim without correct boundary terms |
| Parameterization readiness | Backend-specific integrability/curl residuals, Jacobian orientation/conditioning, seam transition and period residuals | Smoothness does not imply an admitted seamless parameterization |

Store statuses such as `assessed`, `unresolved`, `not_assessed`, and `not_applicable` separately from severity. A field may be adequate for display and inadmissible for a selected tracing backend. Return that distinction as an admission decision based on individual findings, not a universal quality score.

Sampling needs an explicit model. A discrete field can be fully inspected relative to its finite representation. It cannot certify an unspecified smooth field between its samples. If the source provides a continuous evaluator or regularity bound, adaptive sampling may qualify stronger statements. Otherwise retain `sampling_adequacy_unknown`, including on a visually smooth field. Repeated measurements at greater density are useful experiments, not an automatic proof of the absence of hidden singularities.

## 4. What leaves the kernel?

The proposed public C++ boundary returns ordinary owning values. Third-party mesh handles, Eigen expression references, borrowed pointers, and CGAL internal types stay behind it. The application derives prose from stable codes and records.

```text
KernelResult
  schema_version
  field_audit: FieldAudit
  trace_run: optional TraceRun
  provenance: RunProvenance

FieldAudit
  findings[]: code, assessment_status, severity, carrier_refs, measured_values
  singularities[]: carrier, cycle, signed_index, scaled_index, residual
  transport_residuals[]: cycle_or_edge, orientation, effort, holonomy, coverage
  unresolved_regions[]: carrier_refs, reason
  backend_admission[]: backend_id, decision, finding_refs

TraceRun
  completion: complete | incomplete | rejected
  paths[]: stable_trace_id, source, surface_segments, display_samples
  terminals[]: trace_id, reason, location, time, evidence_refs
  collision_events[]: event_id, kind, participant_arrivals[], carrier, policy
  recurrence_witnesses[]: trace_id, state_pair, intervening_path, equality_model
  graph_audit: optional graph cycles and coverage

RunProvenance
  mesh/field/parameterization/seed identities and revisions
  kernel revision, backend revision, dependency revisions
  representations, units, orientation, policies
  numerical model, tolerances, budgets, measured consumption
```

Every collision participant includes its trace ID, segment reference, and arrival time. For multi-party events retain all participants. An overlap record includes its surface interval and time functions or endpoint times. A recurrence witness includes the repeated state and the path between occurrences, not just a boolean. Stable references bind to immutable mesh identity and explicit source maps; coordinates alone are inadequate. Large native IDs need a lossless serialized encoding or checked mapping into the inspector's JavaScript-safe integer range.

Retain partial audits and deposited prefixes on ordinary failure. Use structured failure values for invalid admission, unresolved arithmetic, and exhausted budgets. Exceptional process failures still require the host to record that no complete result was produced; they must not be rewritten as an empty successful trace run.

### Compatibility with the existing package

The current [`Trace` contract](/Users/nathanwhite/Software-Development/cad-integrity-pipeline/integration/mesh-diagnostics-seam/python/cad_mesh_inspector/contracts.py:35) has a small display-status vocabulary and forbids unexpected fields. Add evidence in a separate versioned envelope/sidecar, not by inserting unrecognized properties into v1 payloads. An adapter can project qualified recurrence to `cycle_detected`, budget termination to `iteration_limit`, and other terminals to `terminated`, while preserving the precise meaning in sidecar records. Display status never substitutes for that evidence. The existing line contract requires at least two XYZ samples. For rejected or launch-only paths, retain terminal evidence in the sidecar and omit the unsupported line; do not invent a duplicate endpoint merely to satisfy the renderer.

[`payload.py`](/Users/nathanwhite/Software-Development/cad-integrity-pipeline/integration/mesh-diagnostics-seam/python/cad_mesh_inspector/payload.py) and its trace import seam do not infer collisions or cycles. Imported legacy statuses should remain labelled imported assertions. The current NPZ geometry loader is not a field or trace schema; supporting those arrays requires a separately versioned transport contract with shape, dtype, reference, and aggregate-budget validation. NPZ remains transport, not a place for native scheduling decisions.

The standalone owning-value patterns in [`native/nurbs`](/Users/nathanwhite/Software-Development/cad-integrity-pipeline/native/nurbs) and [`native/voronoi`](/Users/nathanwhite/Software-Development/cad-integrity-pipeline/native/voronoi) are useful precedents. No native motorcycle module is claimed here.

## Four implementation slices

| Slice | Deliverable | Exit gate |
|---|---|---|
| 1. Freeze evidence contract | Native owning types, serialized sidecar, stable IDs, display adapter, explicit capability/policy identifiers | Round-trip and compatibility fixtures; precise status mapping; partial failure retained; no UI dependency on a geometry library |
| 2. Qualify field assessment | Read-only imported-field audit with explicit coverage and representation conversion | Known indices and transport cases; zero/nonfinite rejection; boundary/global-loop omissions visible; aliasing fixtures; imported data identity unchanged |
| 3. Implement one backend | Prefer `quad_vertex_canonical_2008` when qualified quads exist; otherwise `parameterized_triangle_axis` with admitted charts | Chronological event suite, complete tie/overlap/source policy, recurrence witnesses, deterministic seed permutation, resource bounds, independent oracle |
| 4. Integrate the parent | Optional native adapter, evidence download/view, versioned transport, failure projection | Parent behavior preserved; unavailable backend and partial runs useful; package/install checks; no automatic repaired-mesh candidate |

Slice 3 is a branch in the plan, not permission to implement all modes. Canonical quads do not require a cross-field generator. Parameterized triangles require chart orientation, nondegeneracy, seam compatibility, singularity locations, and time consistency before tracing. `raw_cross_field_integral_lines` remains separately named and deferred until its interpolation, edge continuation, singularity handling, and numerical error contract are qualified. The 2014 paper is relevant to that work; reproducing its complete layout/parameterization pipeline is substantially beyond wiring a streamline call.

Do not add both Directional and Geometry Central merely for symmetry. Prototype the selected headers behind the owning adapter, measure dependency/build cost, and choose one mesh/field authority. Add CGAL only where construction/predicate robustness is required; the discrete quad backend need not pay for a triangle-intersection stack.

## Acceptance fixtures and independent evidence

These are proposed qualification fixtures; they have not been run against a native kernel.

| Fixture | Required assertion |
|---|---|
| Two perpendicular simultaneous quad arrivals | Correct oriented canonical winner; distinct result under explicitly selected `stop_all` |
| Three/four arrivals; head-on shared edge | Group event and all required terminal records, including correct event times |
| Older deposited track | Later trace stops even after depositing trace has terminated elsewhere |
| Invalidated future track | B stops A before A reaches C's crossing; C ignores A's unrealized continuation |
| Collinear overlaps | Earliest deposited contact and overlap interval; opposing and same-direction cases |
| Shared launch point | Only declared initial exemptions apply; returning later can self-collide |
| Folded/coincident sheets | No collision without surface identification, despite equal display projection or coordinates |
| Adjacent faces and seams | One event at a shared edge; no duplicate events or missed cross-chart identification |
| Periodic quad/parameterized surface | Repeated full state with path and transition witness; clarify continuation versus self-contact terminal |
| Near-return with changed direction or chart state | `possible_recurrence`, never a proved cycle |
| Graph cycle assembled from several traces | Graph witness distinct from every trace's recurrence status |
| Boundary singularity and genus-bearing surface | Correct signed conventions and explicit measured/missing boundary and generator quantities |
| Undersampled field with known hidden winding | Sparse residuals cannot produce a continuous-field certificate |
| Zero/near-zero and nonfinite power samples | Findings before unsafe normalization or matching |
| Smooth but incompatible seam/integrability data | Field display succeeds; parameterized backend admission fails with specific residuals |
| Permuted seeds and relabelled mesh | Identical normalized evidence under fixed policy; orientation-preserving relabelling test for canonical mode |
| Budget exhaustion and uncertain event ordering | Retained committed prefix, honest incomplete status, measured budget use |

Use a small independent exhaustive/reference scheduler for bounded cases and exact combinatorial or rational fixtures where possible. Compare event participants, times, carrier references, termination, and witness paths, not screenshots alone. Test orientation reversal separately: a chirality-dependent right-hand rule must be interpreted with its stated orientation convention. Track build/ABI, numerical parity, resource limits, and browser presentation as different evidence categories.

## Attached demonstrator

The [motorcycle kernel lab](/Users/nathanwhite/Software-Development/cad-integrity-pipeline/docs/research-assets/motorcycle-kernel-lab.html) is a supplied educational prototype covering synthetic planar scheduling, finite periodic-state traversal, and sampled winding. Its `stop_all` tie policy is experimental. Current local Chrome verification passed nine embedded numerical assertions and three additional control checks (48-step recurrence, 16-sample field winding, simultaneous collision), with zero page errors; desktop and mobile screenshots were visually inspected. These replace, rather than inherit, the attached narrative's earlier control-check claim.

The example uses three fixed planar unit-speed rays. It skips parallel/collinear pairs, so it does not exercise overlaps; its `1e-9` time grouping is not a qualified general ordering method. Recurrence uses a finite lattice torus, and the field alias warning knows the analytic example's true index. That warning cannot be applied to an unknown imported field. One seed-array reversal check is not broad invariance evidence.

The demonstrator is useful for inspecting proposed semantics; it does not qualify the canonical quad construction, field tracing on a mesh, intrinsic collision geometry, native arithmetic, or parent integration. The supplied HTML/CSS/JavaScript fragment was preserved unchanged (original fragment SHA-256 `3014c0c99a9ce75212533694dcb540d393885a79a934652523791105b94c7054`); the standalone wrapper supplies presentation styling.

## Remaining decisions and research gaps

1. Choose the first admitted carrier: existing pure quads or an already qualified triangle parameterization. Do not infer a seamless parameterization from a cross-field.
2. Acquire and inspect the 2025 paper's full methods before relying on its particular event structures, robustness guarantees, simplification rules, or performance. No implementation availability claim is made.
3. Pin library revisions and qualify selected APIs, arithmetic, dependency footprint, and boundary conventions. Documentation on moving branches is research evidence, not a dependency lock.
4. Freeze timing, overlap, source, simultaneous-event, and uncertain-comparison policies before implementation. Some choices alter results, not merely tolerances.
5. Decide which periodicity claims are required: exact discrete recurrence, periodicity of an admitted continuous model, or observational near-return diagnostics. Their proof obligations differ.

A successful trace is derived diagnostic evidence. It does not become a repaired mesh, establish design intent, or authorize a topology edit. Keep any future partition extraction, layout simplification, parameterization, and repair operations separately selected and separately qualified.
