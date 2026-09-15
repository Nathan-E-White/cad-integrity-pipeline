# Stage 10 selected native sewing

`sew_selected_native_boundaries(shape, evidence, selected_wire_pairs, policy)` is
the sole Stage 10 mutation seam.  It accepts only `FreeBoundaryWire` IDs issued
by `classify_native_defects` for the exact source fingerprint and policy audit;
the caller groups the IDs into explicit pairs.  The IDs are local evidence
references, not durable CAD names or inferred mates.

The module rejects stale evidence, duplicate/unknown/empty selection, unowned
topology, partial wire selection, uncovered unowned faces, an ambiguous shell,
an open shell, detached faces, failed orientation, count/area policy violations,
a result that retains the exact selected pairs, and an output that fails the
existing kernel gate.  It copies selected faces into
a private compound, runs `BRepBuilderAPI_Sewing` with the named precision and
maximum tolerance, then constructs one oriented solid.  It returns immutable
selection, source-fingerprint, and pre/post audit evidence; it does not publish
a STEP file or certify geometry fidelity.

The operation sews only the selected free-face set and preserves any unselected
faces already owned by input solids.  It refuses arbitrary unselected *open*
faces because returning a whole-shape candidate for those would require a
further topology-reconstruction contract.  The generic `repair_shape` route
also refuses to auto-sew, so proximity is never silently converted into an
inferred repair selection.

This is a deep module: callers learn one selection-and-policy interface while it
localizes source identity, evidence admission, private copying, OCCT sewing,
shell/solid construction, and postcondition checks.  There is one native OCCT
adapter, not a speculative abstraction.  Removing the module would reintroduce
all of that proof and policy logic to each caller, which satisfies the deletion
test.

The scope remains a controlled local operation on selected free boundary wires.
It does not establish design intent, feature history, continuous displacement,
CAD certification, general hole filling, boolean/arrangement repair, general
self-intersection repair, or native fuzz isolation.
