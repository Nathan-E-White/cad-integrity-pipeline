# Stage 3 raw polygonal-cell admission characterisation

## Module and interface

Stage 3 adds no production module. Its test interface is the established raw
`PolyhedralBRep` carrier, `to_chain_complex`,
`BRepHomologyStitchAnalyzer.evaluate_stitch_integrity`, and `RepairPipeline.run`.
Raw carriers remain constructible for diagnosis. Their report distinguishes
structural cell admission from an unavailable homology computation caused by an
explicit reduction budget.

## Seam, adapters, and depth

This is a test-only slice. The raw B-rep and topology analyzer are the existing
adapters; no hypothetical production seam is added. The tests use valid disks,
spheres, and tori; malformed/duplicate/collapsed/pinched/unused raw inputs;
loop equivalence; and renumbering invariance. Deleting this module would remove
the independent admission and identity evidence scattered across these public
seams.

The validated polygonal-cell view and universal authorization of chain
construction remain Step 4 work. Stage 3 does not broaden CAD validity,
embeddedness, outwardness, or physical-certification claims.
