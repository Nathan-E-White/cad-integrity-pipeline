# Stage 9 native-classifier OCCT binding research

**Scope.** This note records the evidence available to a read-only classifier in
the installed `cadquery-ocp` 7.9.3.1.1 environment, inspected on 2026-09-15.
It does not establish a repair policy, design intent, or a general geometric
intersection guarantee.

## Supported evidence

| Need | Binding/API evidence | Classifier use and limit |
|---|---|---|
| Edge ownership and occurrence | `TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, map)` is exposed by the installed binding. OCCT specifies that it maps each edge to its face ancestors; `MapShapesAndUniqueAncestors` can instead suppress repeated ancestors. [1] | Use the non-unique map (or per-face edge exploration) for occurrence counts, plus a stable `TopTools_IndexedMapOfShape` index for report IDs. Do not use the unique map to decide whether a periodic seam is free: it removes precisely the repeated-face occurrence that matters. |
| Boundary wire provenance | `TopExp_Explorer(face, TopAbs_WIRE)` and `TopExp_Explorer(wire, TopAbs_EDGE)` are exposed; `TopExp.Vertices(wire, ...)` documents null endpoints for a non-manifold wire. `ShapeAnalysis_FreeBounds` is also exposed with open/closed-wire accessors. [1][7] | Keep direct edge/face indexes as the authoritative provenance, then use free-bound grouping only as a derived diagnostic. A wire report is topological provenance, not evidence that a missing face or a preferred mate exists. |
| Surface/edge parameter evidence | `BRep_Tool.CurveOnSurface_s(edge, face, ...)` and `BRep_Tool.IsClosed_s(edge, face)` are exposed. OCCT says the former returns the edge's p-curve for that face (or null); the latter identifies two p-curves on a closed surface. [2] | Preserve a `pcurve_available`/`edge_closed_on_face` status per edge-face use. Do not require every p-curve to be stored: OCCT says planar ones may be generated on demand. |
| Periodic faces and degenerate edges | `BRepAdaptor_Surface(face).IsUPeriodic/IsVPeriodic` and `UPeriod/VPeriod` are exposed. `BRep_Tool.Degenerated_s(edge)` is exposed and documented as the degeneracy predicate. [3][4] | Record periodic axes/periods by face and mark degenerate edges separately. An edge with one use is a free-boundary candidate only after excluding degenerates and accounting for seam use on its periodic owner. |
| Proximity candidate evidence | `BRepExtrema_DistShapeShape` is exposed with `Perform`, `IsDone`, `Value`, `NbSolution`, point/support, and edge/face parameter accessors. OCCT defines it as a minimum-distance computation and states that its deflection bounds deviation of extreme distances from the minimum. [5] | A supported candidate can retain the two IDs, completed-status, configured deflection, minimum distance, solution count, support types, witness points, and available parameters. This is geometry evidence only; it must be labelled `not_selected` unless a later authorized policy selects it. |
| Kernel validity and self-interference | `BRepCheck_Analyzer.IsValid`, `BRepAlgoAPI_Check(shape, bTestSE, bTestSI).IsValid`, and `BOPAlgo_CheckerSI` are exposed. OCCT documents `bTestSI` as the flag for self-interference checking; `BOPAlgo_CheckerSI` can be configured from V/V through all V/V...S/S interference classes, but its public report is errors/warnings rather than a simple stable pair-result API. [6][8] | Report BRepCheck validity separately from a named kernel Boolean/self-interference check. Until real fixtures establish an interpretable result mapping, report intersection pairs as `not_established`; a successful check is neither design-intent nor repair evidence. |

## Implementation consequences for Stage 9

The existing `audit_shape` already uses occurrence counting and
`BRep_Tool.Degenerated_s`; Stage 9 can deepen that adapter without a native
mutation by adding typed records for edge-to-face provenance, derived
free-bound groups, periodic-face metadata, and optional extrema witnesses.
The map and probe inputs should be enumerated deterministically from
`TopTools_IndexedMapOfShape`.  The report should distinguish `available`,
`not_run`, `failed`, and `not_established`; especially for intersection status
and intended mates.

The installed binding is a compiled extension
(`.pixi/envs/default/lib/python3.13/site-packages/OCP/OCP.cpython-313-darwin.so`),
so the callable names above were verified by importing the actual environment
and reading binding docstrings rather than inferred from a separate Python
stub.  The linked OCCT 8.0.1 reference is an API-semantic source; it is not a
claim that the packaged binary is OCCT 8.0.1.  Package metadata identifies the
Python distribution as `cadquery-ocp` 7.9.3.1.1.

## Sources

1. Open CASCADE, [TopExp](https://occt3d.com/dev/doc/refman/html/class_top_exp.html), OCCT 8.0.1 reference manual, accessed 2026-09-15.
2. Open CASCADE, [BRep_Tool](https://occt3d.com/dev/doc/refman/html/class_b_rep___tool.html), OCCT 8.0.1 reference manual, accessed 2026-09-15.
3. Open CASCADE, [BRepAdaptor_Surface](https://occt3d.com/dev/doc/refman/html/class_b_rep_adaptor___surface.html), OCCT 8.0.1 reference manual, accessed 2026-09-15.
4. Open CASCADE, [BRep_Tool::Degenerated](https://occt3d.com/dev/doc/refman/html/class_b_rep___tool.html#afe8f1ec8f0edc8f5c52f3c2d0b695eeb), OCCT 8.0.1 reference manual, accessed 2026-09-15.
5. Open CASCADE, [BRepExtrema_DistShapeShape](https://occt3d.com/dev/doc/refman/html/class_b_rep_extrema___dist_shape_shape.html), OCCT 8.0.1 reference manual, accessed 2026-09-15.
6. Open CASCADE, [BRepAlgoAPI_Check](https://occt3d.com/dev/doc/refman/html/class_b_rep_algo_a_p_i___check.html), OCCT 8.0.1 reference manual, accessed 2026-09-15.
7. Open CASCADE, [ShapeAnalysis_FreeBounds](https://occt3d.com/dev/doc/refman/html/class_shape_analysis___free_bounds.html), OCCT 8.0.1 reference manual, accessed 2026-09-15.
8. Open CASCADE, [BOPAlgo_CheckerSI](https://occt3d.com/dev/doc/refman/html/class_b_o_p_algo___checker_s_i.html), OCCT 8.0.1 reference manual, accessed 2026-09-15.
