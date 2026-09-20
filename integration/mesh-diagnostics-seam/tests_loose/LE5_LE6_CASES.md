# LE-5 / LE-6 regression cases

Implemented in `test_payload_coverage.py`. These acceptance fixtures exercise the public
`cad_mesh_inspector.inspect_triangles` entry point and inspect metric statuses,
values, selection IDs, and labels in its validated payload. No NPZ or renderer is
needed. Keep original triangle-row IDs in all expectations.

## LE-5: coverage and status

| Fixture | Inputs / policy | Expected result |
|---|---|---|
| Empty mesh | Empty `(0, 3)` vertex and integer face arrays; test both `require_closed` values | `quality`, `degenerate`, `repeated`, `duplicate`, `nonmanifold`, and `winding` are `unknown`, with zero counts/empty selections. `minimum-quality` is `unknown`/null. Boundary is `unknown` when closedness is required, otherwise `info`. |
| Vertices without faces | Three valid vertices, empty `(0, 3)` faces | Same unchecked statuses as the empty mesh; vertex count remains informative. |
| Repeated-index face only | Vertices `(0,0,0)`, `(1,0,0)`; face `[0,0,1]` | `repeated` and `degenerate` fail. Zero nonmanifold/winding counts are `unknown`. Boundary is `unknown` if required, otherwise `info`. |
| Closed tetrahedron plus excluded face | Vertices origin and unit x/y/z; faces `[0,2,1]`, `[0,1,3]`, `[1,2,3]`, `[2,0,3]`, plus `[0,0,1]` | Zero boundary/nonmanifold/winding defects cannot pass because one face was excluded: applicable edge checks are `unknown`. Repeated-face failure remains visible. |
| Boundary found despite exclusion | A valid open triangle plus a repeated-index face | Boundary fails when closedness is required and remains `info` otherwise; incomplete incidence does not hide the observed defect. |
| Winding conflict despite exclusion | Valid faces `[0,1,2]`, `[0,1,3]` plus a repeated-index face; vertices chosen to make both valid faces nondegenerate | Shared edge `[0,1]` is selected; winding fails despite partial incidence. |
| Nonmanifold edge despite exclusion | Three nondegenerate faces sharing `[0,1]`, plus a repeated-index face | Shared edge has three uses; nonmanifold metric fails despite partial incidence. |
| Complete clean controls | Closed oriented tetrahedron; separately, one open nondegenerate triangle | Tetrahedron applicable edge checks pass. Open triangle boundary is fail/info according to policy; other checked defect-free metrics pass. |
| Known face defects | Duplicate valid triangles, and a distinct-index collinear triangle | Duplicate and degeneracy failures remain failures; distinct-index degeneracy alone must not be mistaken for excluded repeated-index incidence. |

Keep count-only metrics (`vertices`, `triangles`) informative and the explicitly
unperformed vertex-link/self-intersection/FEM check `unknown`. A repeated-index
face makes edge coverage partial, not every other check in the payload unknown.

## LE-6: low-quality selection

Use separate vertex blocks for independent triangles so fixture assembly does not
accidentally introduce shared edges or duplicate faces.

| Fixture | Parameters | Expected result |
|---|---|---|
| Exact degeneracy | Distinct collinear points `(0,0,0)`, `(1,0,0)`, `(2,0,0)`; threshold `0`, area tolerance `0` | Quality selection includes the face and fails; separate degeneracy metric also selects it. This catches the present strict-less-than-zero omission. |
| Repeated-index degeneracy | Face `[0,0,1]`; threshold `0` | Same quality/degeneracy inclusion, preserving the repeated-index diagnostic. |
| Tolerance-classified degeneracy | Right triangle with legs `1`, area `0.5`; area tolerance `0.5`; threshold `0` | Equality to the area tolerance is degenerate under the existing classifier and must enter the quality selection. A lower tolerance leaves it regular. |
| Positive-threshold union | Row 0 collinear; row 1 right triangle with legs `1` and `0.01`; row 2 right triangle with legs `1` and `1`; threshold `0.15` | Quality IDs exactly `[0,1]`, count `2`, failure. Degenerate IDs exactly `[0]`. Row 0 is not counted twice. |
| Regular zero-threshold control | Nondegenerate right triangle; threshold `0` | Empty quality/degenerate selections, counts `0`, both pass. |
| Empty selection | Empty mesh at thresholds `0` and `0.15` | Empty selection and count `0`; status follows LE-5 (`unknown`), not a pass. |

For all quality cases, assert the label says "below [threshold] or degenerate"
and the metric's selection reference resolves to the exact expected face rows.
Do not alter the mean-ratio formula, degeneracy classifier, or squared-coordinate
units of `area_tolerance` to obtain these results.
