# Superseded native prototypes

These are byte-for-byte snapshots of the working files on 2026-09-20, before
consolidation. They include staged and unstaged user work. They are historical
source, excluded from the native build, not independent supported libraries.

The active implementation is `../../SimplicialComplex.cpp` and its public header.
It uses SimpComp3 as the base and retains arbitrary-facet closure from the original
SimplicialComplex implementation. SimpComp2's polygon, topology, box-query and BVH
behavior is already present in SimpComp3; its demo is the only different workflow.
The original's double arithmetic overloads were not a double-precision mesh path.

Snapshots retain their original issues, including unguarded subset shifts,
post-allocation budget checks, competing global definitions and embedded demos.
Do not compile them into the active library or interpret comments as benchmarks.
