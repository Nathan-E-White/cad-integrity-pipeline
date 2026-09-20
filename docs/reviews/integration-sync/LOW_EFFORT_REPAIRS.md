# Low-effort repair shortlist

September 20, 2026. Derived from `REVIEW.md` and `GEOMETRY_REVIEW.md` in
`integration/sync`. This is a work list, not an implementation record.

“Low effort” here means a localized change, a reasonably clear expected behavior,
and focused verification. It does not mean low importance. Effort includes proving
the fix, so an easy edit in an unbuildable package is marked as conditional.

## Ready to scope now

| ID | Repair | Concrete scope and acceptance | Why small |
|---|---|---|---|
| LE-1 | Stop the host reporting empty/unchecked verification as Passed | Change `src/cad_integrity/workbench_results.py:33–39`. Preserve FAILED/UNAVAILABLE precedence; use an explicit nonpassing summary when no applicable check passed or any applicable check is NOT_RUN. Cover empty, all-NOT_RUN, all-NOT_APPLICABLE, mixed passed/unrun, failures and a fully passed ledger. Settle the summary wording in this patch. | One aggregation function and its projection tests; no geometry behavior changes. |
| LE-2 | Correct the broken handoff reference and label historical documentation | Replace the nonexistent `CODEX_HANDOFF.md` reference in loose `gradio_component.py` with an accurate current guide. Add a short live-directory note identifying the original flat delivery versus restored archive layout and their historical verification claims. Preserve archive members and avoid rewriting the historical reports. | Documentation-only; prevents following instructions for the wrong implementation. |
| LE-3 | Check resolved VTK ownership as well as direct declarations | Extend dependency validation to inspect the active resolved Pixi environment for conda VTK providers, while retaining the current novtk/PyPI choice. Add a fixture where a transitive conda VTK entry is present despite clean direct declarations, and a fixture for the current allowed lock. Use structured lock parsing and explicit environment selection. | Small checker enhancement with existing manifest regression infrastructure. Slightly larger than the other two; parser availability must be checked before choosing an implementation. |

LE-3 is preventive coverage, not a current dependency defect. Current lock inspection
found only the intended VTK provider. It can follow the functional repairs.

## Small code repairs once the diagnostics test target is coherent

| ID | Repair | Concrete scope and acceptance | Dependency |
|---|---|---|---|
| LE-4 | Match Python parent-ID limits to TypeScript | In loose `contracts.py:97–99`, reject `triangle_source_faces` above `2**53-1`. Test the accepted maximum and rejected next integer against both validators. Do not change source-ID meaning. | The chosen loose Python/TS contract tests must run; the flat package currently does not collect normally. |
| LE-5 | Avoid passing empty or partial standalone diagnostic checks | In loose `payload.py`, emit `unknown` for unchecked empty results and zero-defect edge checks whose incidence excluded repeated-index faces. Preserve detected failures and policy-neutral `info` boundaries. Port the archive's empty/partial fixtures with deliberate status-vocabulary adaptation. | Same package/test-target issue. This is distinct from LE-1: one produces individual diagnostics; the other summarizes the host ledger. |
| LE-6 | Include degeneracy in the standalone low-quality selection | Union degenerate face IDs with threshold failures in loose `payload.py:45`, and update the metric label to say “below threshold or degenerate.” Preserve the separate degeneracy metric. Test threshold zero and ordinary positive thresholds. | Same package/test-target issue. This aligns with the archive's conservative quality definition; do not quietly change the formula or tolerance units. |

Do not claim these are complete merely because the corresponding archive behavior
already exists. The loose and archive contracts differ. Conversely, if the standalone
loose audit is not adopted, do not spend time repairing it solely to retain dead code;
carry the regression behavior into the adopted module instead.

## Likely small, but one decision comes first

**LE-7 — Restore native NURBS interface/build consistency.** The header now templates
`SurfaceGeometry<Fp>` and returns `SurfaceGeometry<float>`, while the implementation
uses the old unparameterized type and accessors still expose double curvature spans.
Agree whether to restore the previously documented double-precision interface or
complete the precision change. Then make declaration/definition/storage/accessors
consistent and run the standalone native suite under strict compilation. This is
probably localized, but “add template arguments until it compiles” is not a sufficient
acceptance criterion. Full Python/native numerical parity remains a separate task.

## Cheap edits that should not take priority

The simple loose `Index.svelte` could be repaired to dispose replaced geometry and
materials and initialize correctly when its first value arrives after mount. Those
are bounded lifecycle fixes, but that component consumes the wrong payload and is
not the proposed advanced viewer. Prefer repairing the selected renderer/composition
owner rather than polishing an implementation we may not use.

Moving files or changing imports can look similarly cheap. The missing NPZ API,
paired-view composition, three payload formats and duplicate frontend package
declarations require a coherent package/contract decision first. They are not a
collection of independent path substitutions.

## Excluded from this shortlist

- Read-only seam extraction and source-revision-bound selected operation plans.
- Reconciliation of complete diagnostic payloads, package layout and renderer ownership.
- Global UV overlap evidence or general motorcycle/IGM algorithms.
- Original STL facet/corner mappings and a retained reconstruction evidence carrier.
- Cross-workflow translator coordination or process isolation.
- End-to-end resource budgets/cancellation and partial-release integration.
- NURBS native/Python parity qualification beyond repairing native compilation.

These require broader contracts or cross-module failure tests. No broad internal
cleanup of mesh healing or the Python NURBS bundle is justified by the review.

Suggested order: LE-1 and LE-2 first; decide LE-7's precision intent; take LE-4–6
with the diagnostics package slice; add LE-3 as dependency-check hardening.
