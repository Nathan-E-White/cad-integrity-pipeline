# Stage 10 selected-local-sewing OCCT research

**Scope.** This note constrains the Stage 10 native operation: an application
selects the already-classified candidate shapes deterministically, passes only
that selection to OCCT sewing, and independently evaluates the resulting
shape.  It is not evidence for automatic mate selection, hole filling, or
design-intent recovery.  OCCT 8.0.1 references describe the kernel API;
binding names must be checked against the pinned `cadquery-ocp` environment.

## Kernel operation and selection boundary

`BRepBuilderAPI_Sewing` has the direct workflow required here: construct with
a working tolerance, `Add()` every shape to sew, `Perform()`, then obtain
`SewedShape()`.  The API also permits a local mode (`Load(context)`, then
`Add()` selected local shapes); use that mode only when the policy explicitly
names and preserves a context shape.  `SewedShape()` can be null and otherwise
can be a face, shell, solid, or compound, so neither completion nor output
type may be inferred from a successful call alone. [1][2]

This means that the project owns candidate selection, ambiguity refusal, input
order/evidence, and the named tolerance policy.  It must not give OCCT all
nearby free edges and describe the kernel's candidate search as an approved
selection.  The user guide says a working tolerance is the *maximum distance*
for eligibility, not a guarantee of sewing: other criteria still apply. [2]

## Tolerance policy

Use one explicit, policy-bounded working tolerance for each operation.  OCCT
supports large working tolerances but advises the smallest practical value:
larger values cost more and can incorrectly join edges on shells with free
boundaries.  It specifically warns about open-shell boundaries when the
tolerance exceeds the size of their faces.  Do not implement tolerance
escalation as a retry strategy. [2]

The optional local-tolerances mode changes the working tolerance to the
configured tolerance plus the two edge tolerances.  Leave it off unless the
policy deliberately authorizes that expansion and records it.  Separately,
`BRep_Tool::Tolerance` exposes per-vertex, -edge, and -face tolerances and
`MaxTolerance` exposes a shape-subshape maximum; these support an independent
postcondition cap rather than treating the configured sewing tolerance as an
output guarantee. [1][3]

## Required output evidence and refusal checks

Record the selected input identifiers, tolerance/options, output type/null
status, and OCCT's sewing diagnostics.  In particular, `NbFreeEdges()` counts
edges shared by one face, `NbContigousEdges()` those shared by two, and
`NbMultipleEdges()` those shared by more than two.  The sewing API states that
it finds manifold shapes and does not sew with multiple edges; a manifold
policy should reject or report any nonzero multiple-edge result.  Whether free
edges are acceptable must remain explicit: an open-shell workflow can allow
them, while a closed-solid workflow cannot. [1]

Check the returned shape with `BRepCheck_Analyzer(...).IsValid()` and retain
the exact-mode choice in evidence.  The analyzer's contract includes
topological and edge-parameterization checks, including closed shells for
solids; its default non-exact geometric method samples finitely and can be
incorrect, while exact mode is slower and applies only to SameParameter edges.
Thus validity is a kernel check, not CAD-design or continuous-geometry
certification. [4]

For policy-specific regression checks, count topological entities with
`TopExp` maps/exploration, compare surface area with `BRepGProp`, and compute
volume only after the closed-solid admission check.  OCCT warns that volume
properties require an object without free boundaries and coherent orientation;
the algorithm does not enforce those preconditions and can return false
results otherwise. [5][6]

## Binding check made for this repository

The pinned environment exposes `Add`, `Load`, `Perform`, `SewedShape`, the
free/contiguous/multiple-edge accessors, `Modified`, tolerance accessors, and
`SetLocalTolerancesMode` on `OCP.BRepBuilderAPI.BRepBuilderAPI_Sewing`
(inspected 2026-09-15).  That is a compatibility observation, not a substitute
for the OCCT sources above.  OCP describes itself as thin OCCT bindings, so
the C++ documentation remains the semantic authority. [7]

## Sources

1. Open CASCADE, [BRepBuilderAPI_Sewing](https://occt3d.com/dev/doc/refman/html/class_b_rep_builder_a_p_i___sewing.html), OCCT 8.0.1 reference manual, accessed 2026-09-15.
2. Open CASCADE, [Modeling Algorithms: Sewing Algorithm](https://occt3d.com/dev/doc/overview/html/occt_user_guides__modeling_algos.html), OCCT 8.0.1 user guide, accessed 2026-09-15.
3. Open CASCADE, [BRep_Tool](https://occt3d.com/dev/doc/refman/html/class_b_rep___tool.html), OCCT 8.0.1 reference manual, accessed 2026-09-15.
4. Open CASCADE, [BRepCheck_Analyzer](https://occt3d.com/dev/doc/refman/html/class_b_rep_check___analyzer.html), OCCT 8.0.1 reference manual, accessed 2026-09-15.
5. Open CASCADE, [TopExp](https://occt3d.com/dev/doc/refman/html/class_top_exp.html), OCCT 8.0.1 reference manual, accessed 2026-09-15.
6. Open CASCADE, [BRepGProp](https://occt3d.com/dev/doc/refman/html/class_b_rep_g_prop.html), OCCT 8.0.1 reference manual, accessed 2026-09-15.
7. CadQuery, [OCP](https://github.com/CadQuery/OCP), project repository README, accessed 2026-09-15.
