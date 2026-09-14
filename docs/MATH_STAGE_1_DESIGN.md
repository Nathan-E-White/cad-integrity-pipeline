# Stage 1 mathematical test design

## Module and interface

Stage 1 adds a deterministic test module, `tests/test_math_sea_trials.py`.
Its interface is the established public mathematical seams:
`rank_f2`, `compute_homology`, `smith_invariants`, and
`PersistentHomologyEngine.compute_persistence_intervals`.  The tests treat
their declared coefficient choice, validated `ChainComplex` input, finite
filtration births, and positive `ReductionBudget` limits as invariants.  The
expected error modes are the existing `InvalidChainComplex`,
`ResourceLimitExceeded`, and optional-dependency skip at the SymPy seam.
Generated cases use fixed seeds and small bounded dimensions, so their work is
both reproducible and within the default reduction budgets.

## Seam, adapters, and depth

This is a test-only slice: it introduces no new production seam or adapter.
The four public functions are the test seams.  `rank_f2` and persistence have
two real reduction consumers, but their shared-reducer extraction is expressly
deferred to Commit 2.  Consequently Stage 1 records behavior before changing
that design.

The test module is deep rather than a collection of implementation probes: a
small set of independent dense elimination, exact constructed chain complexes,
and sublevel-homology checks exercises parity, chain identity, budget limits,
and interval semantics.  Deleting it would restore duplicated oracle and
metamorphic reasoning to each affected test file; that is the relevant
deletion-test result.  No hypothetical production adapter is added.
