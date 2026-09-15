# Stage 9 native defect classifier

Stage 9 extends the existing `ocp` module with one read-only seam:
`classify_native_defects(shape, policy, max_candidate_pair_comparisons=...)`.  It returns
a frozen `NativeDefectReport`, serializable by the project's strict report
serializer, while leaving the supplied `TopoDS_Shape` untouched.

The interface records locally indexed edge ownership with face-local occurrence
counts and closed-on-face seam evidence, derived free-boundary wire groups,
periodic face and degenerate-edge evidence, shell-to-face connectivity,
per-entity tolerance distributions, and a bounded list of OCCT minimum-distance
observations between free edges.  A candidate pair is deliberately not a repair
selection: its scope says that distance within `policy.precision_mm` is not
design intent.  `max_candidate_pair_comparisons` is a nonnegative comparison budget; the
report records both comparisons performed and whether the limit truncated work.
This prevents a large free-boundary set from becoming an unbounded all-pairs
native diagnostic.

The report labels its confidence as `kernel_evidence_only`.  Its
`FreeBoundaryWire` entries are derived connected free-edge groups, not a claim
that OCCT supplied reconstructed boundary wires across faces.

Self-intersection and design intent are typed `not_established` facts.  The
existing Boolean-suitability check remains part of the audit, but it is not
mislabelled as a dedicated intersection classifier.  No generic repair button,
mate inference, hole filling, CAD-validity certification, or polygonal homology
path is added.

The module remains deep because callers learn one report interface while the
adapter contains native indexing, face/wire traversal, periodicity inspection,
tolerance aggregation, and bounded curve-distance evaluation.  There is one
native adapter rather than a speculative second abstraction.  Deleting this
interface would return those details to every diagnostic caller; it would not
remove any of the kernel complexity.
