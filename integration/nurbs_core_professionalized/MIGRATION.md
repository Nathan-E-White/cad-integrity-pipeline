# Migration from the supplied prototype

## Preserved entry points

The original module and class names remain available. `STLReader.load_stl`
returns the actual three-array tuple used by the supplied `main.py`. The old
annotation incorrectly described only two arrays. `estimate_features`,
`evaluate_surface_geometry`, the basis/span methods, both direct RANSAC fitting
methods, `segment_primitives`, `compute_cards`, and `export` remain available.

New rich-result methods are additive: `STLReader.read`, estimator `estimate`,
NURBS `evaluate_surface`, and classifier `segment`. Existing principal curvature
keys remain, with extra validity/diagnostic fields.

## Deliberate changes

| Area | Change and action |
| --- | --- |
| Dependencies | NumPy and SciPy are core requirements. STEP additionally needs `cadquery-ocp`; install the `[step]` extra. |
| STEP units | Declare `CADGeometryCardEngine(length_unit="mm")`, another supported source unit, or an explicit exporter unit. Unspecified units are allowed for JSON only. |
| STEP contents | Real bounded faces replace the handwritten empty-bound records. Missing bounds, empty operations, or invalid faces are rejected. Output is not a solid. |
| STEP IDs | `start_id` is accepted for call compatibility but deprecated; the kernel assigns IDs. Private `curr_id`, `lines`, and `_emit` state are no longer exposed. |
| Card precision | `parameters` retain numerical precision; rounding moves to `display_parameters`. Compare numeric values with appropriate tolerances, not four-decimal snapshots. |
| Curvature failure | Singular or failed estimates return NaN and `Valid=False`, not zero curvature. Do not turn invalid features into plane candidates. The revised segmenter already handles this. |
| Curvature ordering | Max/min mean algebraically largest/smallest. Normal reversal also reverses and reorders curvatures. For cylindrical magnitude use `max(abs(k1), abs(k2))`, not just `abs(k1)`. |
| NURBS domains | Out-of-domain parameters now raise instead of being silently clipped. Endpoints are treated explicitly. |
| Homogeneous control points | The original weighted convention is documented and enforced with positive weights. Use `to_homogeneous` rather than passing unweighted coordinates with a weight appended. |
| STL strictness | Truncated input, extra binary bytes, malformed facets, and resource-limit breaches raise. Near-duplicate vertices are not automatically welded. |
| Degenerate triangles | Dropped and reported by default; use `degenerate_policy="error"` to fail instead. |
| Empty direct RANSAC fits | Masks always match the input length, including insufficient-support cases. A failed plane retains the legacy zero-equation sentinel; a failed cylinder returns `None`. Check the mask before using a model. |
| RANSAC randomness | Use `random_state=42` on the classifier instead of relying on `np.random.seed`. A reused instance advances its private generator. |
| Segmentation | Repeated extraction may return more than one plane or cylinder, with exclusive original sample indices and remaining-point diagnostics. |
| Neighbors | Quadratic fitting requires at least six configured neighbors; sparse/rank-deficient actual neighborhoods remain invalid rather than being padded into a valid result. |
| Writes | Existing outputs are refused by default. Use `overwrite=True` or CLI `--overwrite` deliberately. Writes are per-file atomic, not jointly transactional. |
| Main program | Importing `main` no longer starts a hard-coded scan. Use its CLI or `run_pipeline(PipelineConfig(...))`. |

The original synthetic demos were removed from the library execution paths or
replaced with small deterministic inspection/demo entry points. More substantial
verification now lives in automated tests rather than print-only harnesses.

## Before applying to a real part

Choose input units and scale tolerances accordingly. Inspect valid-feature and
unassigned counts. Inspect fitted bounds rather than treating convex hulls as
recovered trim loops. Preserve the original mesh and JSON diagnostics. Confirm
STEP import and scale in the actual consuming CAD application before relying on
that exchange path. No representative real scan was supplied with this task, so
scan-specific accuracy, noise tolerance, and large-file performance remain to
be measured on your data.
