# Slice 7a: retained NURBS evaluation through an owned NumPy seam

Baseline: `a28d451`. The next slice is NURBS binding, independently of the
unfinished Delaunay constructor and separately admitted chart tracing.

## Reuse and callers

Compile `native/nurbs/src/nurbs.cpp` into the existing private extension. Keep
`SurfaceSpec`, `EvaluationRequest`, `SurfaceGeometry` and the public C++ signatures.
No second numerical kernel, prepared surface owner, backend registry, or mesh
representation is needed. One synchronous function hides native validation,
differentiation, rational evaluation and allocation admission.

The installed caller is `cad_integrity.nurbs.evaluate_surface`. The standalone
bundle adds `NURBSCoreEngine.evaluate_surface_native`, preserving its existing
result/exception classes. Its existing Python evaluator remains the differential
reference and the default for standalone Python 3.11 consumers. Native evaluation
requires the parent package and Python 3.13. This explicit compatibility reason
justifies retaining the two paths; there is no automatic fallback or runtime
backend selector. Segmentation, feature policy and STEP export remain Python.

## Contract

- Real arrays normalize explicitly to native-endian float64, C layout. Three-value
  control nets gain unit weights; four-value nets already contain homogeneous
  `(x*w,y*w,z*w,w)` coordinates. Degrees reject booleans and nonintegral values.
- The private binding refuses incorrect dtype, rank and layout; copies all input
  buffers while holding the GIL; releases it only for the numerical call. It
  retains no borrowed Python buffer. Foreign threads must synchronize their own
  writes during the snapshot, as with other NumPy operations.
- Outputs are independent, writable NumPy owners. XYZ and normal arrays are
  `(len(u),len(v),3)`; curvature and bool mask arrays are `(len(u),len(v))`.
  Cartesian-product order, exact endpoints, right-hand interior knot pieces,
  oriented `S_u cross S_v` normals and algebraic curvature ordering are retained.
- Repeated upper endpoints select the last nonempty left-hand span. Shared
  qualification exposed this existing C++ discrepancy and corrects it in the
  retained basis implementation. Derivatives at repeated knots are one-sided;
  the validity mask does not certify smoothness there.
- Singular `mask` returns zero normals and NaN curvatures. `raise` fails without
  partial output. Invalid inputs raise ValueError, numerical evaluation failures
  ArithmeticError, range failures OverflowError, admission refusal BudgetExceeded,
  and allocation failure MemoryError. Bundle conversion preserves its public
  geometry and evaluation exceptions. BudgetExceeded remains distinct.
- The bundle accepts and validates `batch_size` for compatibility; it does not
  control native traversal or promise streaming.

## Admission accounting

For sample counts U,V, local basis sizes L=p+1,M=q+1 and homogeneous control
storage C bytes:

- I: sum of all five normalized float64 input buffers (knots, net, parameters).
- O: `81*U*V` logical output bytes (10 doubles plus one validity byte).
- B: `U*(4+24*L) + V*(4+24*M)` basis spans and three derivative orders.
- S: `8*(L*L+4*L+M*M+4*M)` conservative simultaneous basis scratch.
- Owned bound: `I+C+B+S+2*O`, including the normalized native control copy and
  both native and exported output payloads. Some terms are not live together;
  summing them deliberately overestimates live payload.
- Work admission score: `6*U*V*L*M + 6*U*L*L + 6*V*M*M`. This bounds the selected
  contraction/recurrence dimensions; it is not an instruction or wall-clock cap.

Every sum/product is overflow-checked before allocation/copy. Shape dimensions
must fit uint32 and degrees the kernel's signed recurrence range. Limits apply
only through this binding; standalone C++ keeps its existing signature and
allocation behavior. Limits exclude Python normalization, caller storage,
allocator overhead/capacity, Python objects and process RSS. They are not a total
memory guarantee. Full outputs and basis tables are retained.

## Qualification

Use analytic planes/cylinders/polynomial patches, retained Python differential
fixtures, repeated endpoint regression, small/translated geometry, rational
weight scaling, malformed data, singular/empty grids, private layout rejection,
independent output ownership, simultaneous calls and each budget refusal.
Exercise the installed wheel built from the sdist outside source import paths.
Measure end-to-end native and Python callers and private binding with already
normalized data; do not call their difference pure conversion time.
