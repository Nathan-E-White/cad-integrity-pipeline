# Stage 2 bounded F2 reduction design

## Module and interface

Stage 2 introduces the internal `f2_reduction` module. Its single interface
accepts an ordered stream of normalized F2 boundary columns with a
`ReductionBudget`, returning immutable evidence: canonical reduced columns,
the ordered XOR trace for each input, pivot ownership, XOR steps, and stored
pivot entries. Columns retain their
supplied order and use their greatest row index as pivot. The module owns the
positive-budget invariant and column, XOR-step, and sparse fill-in limits.
It raises `ResourceLimitExceeded` without returning partial evidence.

Static rank retains sparse-input size checks and integer-to-parity
normalization. Persistence retains filtration order, face indexing,
birth/death identities, and its zero-length policy. Those are adapter
concerns. Integer Smith normal form is excluded: its arithmetic, storage
model, and evidence differ.

## Seam, adapters, and depth

The reducer interface is the seam, not a new public mathematical entry point.
The two real adapters are `rank_f2` sparse boundary columns and
`PersistentHomologyEngine.compute_persistence_intervals` filtration boundary
columns. Both require identical pivot ownership, XOR, and fill-in accounting;
they differ only in how a reduced column is interpreted.

The module is deep: callers supply ordered columns and receive bounded,
deterministic immutable evidence without learning the pivot map or accounting
algorithm. Deleting it would restore that logic to both adapters, satisfying
the deletion test. The existing pair of adapters makes the seam real rather
than speculative.
