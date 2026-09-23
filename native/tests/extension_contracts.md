# Contract gates for native extensions

F2 and its binding are now exercised by `f2_tests.cpp`,
`tests/test_native_f2.py` and the existing algebra/math sea trials. Their executed
results are recorded in `docs/reviews/native-f2/IMPLEMENTATION.md`. Quad tracing is exercised by `quad_tests.cpp` and `tests/test_native_quad.py`,
including the bounded independent lattice oracle; see
`docs/reviews/native-quad/IMPLEMENTATION.md`. Delaunay construction and finite-dual
composition are exercised by `delaunay_tests.cpp`; see
`docs/reviews/native-delaunay/IMPLEMENTATION.md`. Other rows are qualification
requirements; consult each implemented slice record for executed coverage. Extend tests as implementations
land; no empty passing test executables are created.

| Slice | Required distinguishing cases |
|---|---|
| F2 | Set duplicates vs coefficient parity; ordered pivots; full canonical traces; rank/persistence parity; input/pivot/scratch/trace budgets; no partial final answer |
| Polygonal refinements | Diagnosable unresolved references; oriented links; exact signed chains; admission and owner identity |
| Surface | Concave/warped faces; provenance; confidence/constraint invalidation; RHS-only reuse; residual/fallback behavior |
| UV | Outside, agreeing edge hits, conflicting overlaps, tolerance envelopes, ordered queries, incomplete candidate budget |
| BRep | Shared-edge conformity, periodic/seam orientation, source correspondence, failed admission |
| NURBS | Endpoint, rational weight, derivative, singularity and layout parity using existing kernel |
| Delaunay | Duplicate/degenerate samples, sentinels, ID range checks, original correspondence, independent finite extractor fixtures |
| Quad tracing | Chronological deposited prefix, qualified simultaneous ties, deterministic termination, explicit partial results |
| Binding | dtype/layout/overflow, alias mutation, owner lifetime, exceptions, concurrent-use rules |
| Host/frontend | Stale geometry/category/projection, late completion, delivery errors, incomplete retention |

Run native strict compilation, focused public-contract tests and relevant host
checks when activating a module. Historical validation in the handoff is not
validation of these future algorithms.
