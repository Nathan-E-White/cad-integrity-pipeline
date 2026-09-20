# Native NURBS foundation

This subtree owns a portable C++26 reference evaluator for rational
tensor-product NURBS surfaces. It evaluates a Cartesian product of independent
u and v parameter vectors and returns value-owned positions, oriented normals,
principal curvatures, mean/Gaussian curvature, and regularity flags.

## Public seam

```cpp
cad::nurbs::evaluate_surface(const cad::nurbs::SurfaceSpec&,
                             const cad::nurbs::EvaluationRequest&)
```

`SurfaceSpec` stores homogeneous control points in u-major
`(x*w, y*w, z*w, w)` order. The module requires positive finite weights and a
nondecreasing knot vector with a positive active domain. `EvaluationRequest`
supplies independent u/v vectors, a dimensionless regularity tolerance, and a
singular policy. Traversal is internal to the evaluator. Full result arrays and
u/v basis tables are allocated; no tile-based working-memory bound is promised.
The prototype `tile_side` request field was removed; callers should omit it.

Results are flattened in u-major order: `u_index * v_count + v_index`. Normal
orientation is `S_u cross S_v`; principal curvatures are algebraically ordered.
Masked singular samples have a zero normal, NaN curvature fields, and a zero
validity byte. Rejecting singular samples returns `SurfaceErrorCode::singular_surface`.

`basis_derivatives` is deliberately available as a smaller native numerical
interface. It returns only the local nonzero B-spline terms for each parameter;
orders above the degree are zero. Interior knots choose the right-hand piece,
while the exact upper endpoint belongs to the final active span.

The module returns typed `SurfaceError` values. It has no string formatting,
Python dependency, file I/O, geometry-kernel linkage, or accelerator backend.
Those responsibilities remain with future adapters after their contracts are
qualified.

## Focused local checks

The same module target is used by the parent native build and standalone subtree:

```sh
cmake -S native/nurbs -B /private/tmp/cad-nurbs-build -DBUILD_TESTING=ON
cmake --build /private/tmp/cad-nurbs-build
ctest --test-dir /private/tmp/cad-nurbs-build --output-on-failure
```

The equivalent direct compile is useful as a strict, dependency-free check:

```sh
xcrun clang++ -std=c++2c -Wall -Wextra -Werror -pedantic \
  -I native/nurbs/include \
  native/nurbs/src/nurbs.cpp native/nurbs/tests/nurbs_tests.cpp \
  -o /private/tmp/cad-nurbs-tests && /private/tmp/cad-nurbs-tests
```
