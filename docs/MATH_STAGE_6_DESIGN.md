# Stage 6 policy-consistent polygonal repair transition

`RepairPipeline` now lives in `pipeline.py`. Its interface is one
`RepairPolicy`, `run(raw, on_event=...)`, and the two approved direct operations
`weld(raw, policy)` and `synchronize_orientations(raw)`. The invariants are a
single coefficient/reduction-budget policy for every audit, source immutability,
ordered deterministic stage evidence, and no candidate on a controlled failure.
Audit exhaustion remains explicit unavailable evidence; it is never converted to
a passed repair.

`repair.py` contains the two transformation adapters. Its public convenience
functions require `repair_policy=` and return their policy-bound before/after
audits, so a direct operation cannot silently use the F2/default-budget detour
that Stage 5 characterized. The transition owns admission, audit, ordered
transforms, candidate verification, and the report; it does not claim CAD
embedding, outwardness, material validity, or certification.

The module is deep because one small policy and result interface hides the
before/transform/after accounting shared by the pipeline and the two direct
operation adapters. Deleting it would restore that complexity to all three
callers. There are exactly two transformation adapters today, welding and
orientation synchronization; no hypothetical third adapter is introduced.
