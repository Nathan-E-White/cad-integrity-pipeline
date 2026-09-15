# Stage 8 native classification fixtures

Stage 8 adds real-OCCT characterization fixtures only.  Its public seams are
`ocp.audit_shape` and `ocp.repair_shape`.  `audit_shape` identifies locally
indexed free native edges and `sample_edge_polylines` resolves those edge IDs
back to sampled native curves for diagnostic rendering; a selected ID is
checked against endpoints evaluated independently by OCCT's curve adaptor.
`repair_shape` is observed only to establish that an already valid two-solid
assembly, even with a gap smaller than its configured precision, is a no-op,
and that nearby open-boundary assemblies are refused without modifying their
source.

The existing native adapter remains the deep module: behind its compact
interface it counts face-edge occurrences (rather than distinct face
neighbours), recognizes degenerate edges, invokes kernel checks, and applies
the configured acceptance policy.  The fixtures exercise periodic cylinder,
sphere, and torus topology, free-edge identity/provenance, and the no-op
repair decision without adding another adapter or a generic repair seam.

Deleting these tests would leave the current native diagnostic contract
without real-kernel evidence for cylinder seams, a recoverable mapping from
reported free-edge IDs to native curve samples, and nearby-but-intended
separate solids.  They do not introduce a native defect classifier, infer an
intended mate from proximity, fill a boundary, establish self-intersection
when the kernel check is unavailable, or certify CAD validity beyond the
configured kernel policy.
