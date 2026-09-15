# Stage 5 repair-policy propagation characterization

This test-only slice fixes the public test surface for the next extraction.
The confirmed seams are `RepairPipeline.run`, `weld_vertices`, and
`synchronize_orientations`.

`RepairPipeline.run` currently acts as the deep module for a configured
before/transform/after run: its interface accepts one `RepairPolicy`, returns
the input fingerprint and evidence, and represents controlled failures with no
candidate.  Its invariants are source immutability, deterministic ordered
changes, and identical configured coefficients/reduction budget at both audit
points.  A reduction limit is evidence of an unavailable mathematical result,
not a proof that the candidate passed.  A six-vertex projective-plane fixture
demonstrates real coefficient propagation: it has F2 Betti numbers `(1, 1, 1)`
and integral H1 torsion `(2,)`, rather than merely carrying a label.

The two transformation adapters are welding and orientation synchronization.
They are deliberately characterized through their public convenience
interfaces now.  The direct weld test demonstrates that a helper currently has
no channel for a pipeline reduction budget; its hidden analyzer default is a
known default-policy detour, not a qualified direct proof.  That evidence is
the reason for the next stage: removing the eventual transition module would
spread admission, policy, transform, and non-regression checks across the
pipeline and both helpers.  The Stage 6 module should own that complexity
rather than create a third policy authority.

This does not broaden the polygonal contract: the evidence remains restricted
to combinatorial cells, F2/Z homology, and explicitly permitted coordinate or
loop changes.  It does not establish CAD embedding, outwardness, material
validity, or certification.
