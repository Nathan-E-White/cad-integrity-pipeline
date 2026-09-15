# Stage 7 numerical geometry sea trials

This is a test-only slice.  Its confirmed public seams are
`ParametricCurve.evaluate`, `ParametricSurface.evaluate`,
`intersect_curve_surface`, `mesh_parametric_patch`, `uniform_refine`,
`mesh_quality`, `sampled_hausdorff`, and `area_distortion`.

The existing `numerics` and `metrics` modules remain the deep modules.  Their
interfaces carry the relevant contracts: finite, broadcastable coordinates;
bounded local root finding with a checked residual; an untrimmed rectangular
patch; conforming global one-to-four refinement; and measurements over finite
samples or matching-connectivity meshes.  Failures are explicit
`InvalidGeometry`, `ValueError`, or `ResourceLimitExceeded` outcomes.  No
adapter is added: there is one NumPy/SciPy implementation per operation, and
inventing a hypothetical second one would merely add ceremony.

The sea-trial seam is deep enough to exercise analytic, brute-force, and
metamorphic evidence without observing private helpers.  Deleting it would
restore duplicated, weaker examples in caller-focused tests and leave the
central invariants without an independent oracle.  It does not turn sampled
distances into continuous bounds, local roots into global intersection proofs,
or planar subdivision into CAD surface healing.

Mutation evidence was run with `pixi run mutmut run --max-children 4` after
scoping the project configuration to these two modules.  The final run
generated 576 mutants: 448 killed, 128 survived, and zero timeouts,
suspicious, or unviable mutants.  The survivors include equivalent vector
identities, diagnostic-message changes, and solver-tuning alternatives.
The public-seam trials kill the behavior-bearing mutations exercised for
finite/bounded admission, area and quality calculations, directed
nearest-neighbor comparison, connectivity and degenerate-baseline rejection,
mesh indexing/refinement budgets, length-unit propagation, and the default
local-root residual tolerance.  The two-root fixture also establishes that the
result depends on the supplied initial guess; it does not claim global root
enumeration.
