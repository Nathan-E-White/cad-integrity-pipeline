# Integration consolidation

September 20, 2026. Normal merge on `integration/consolidate`.
First parent: `af04563` (`integration/sync`). Second parent: `c3dad06`
(`integration/dedup`). Both histories are retained; no rebase or blanket side selection.

## Resolution decisions

- Adopt the newer working diagnostics layout, shared inspector, Gradio backend,
  optional numeric NPZ loader, admission limits, area representability checks,
  build guard, and browser coverage from `integration/dedup`.
- Retain `integration/sync`'s empty/partial diagnostic status rules and inclusion
  of degenerate faces in low-quality selections, with the added regression cases.
- Keep one adopted test directory. Move restored `mesh_diagnostics` reference
  tests to `tests_reference` to avoid confusing them with `cad_mesh_inspector`.
  Preserve the reference source and original archive.
- Retain the root Bun catalog and lockfile. Remove the competing child npm lock;
  adopt the package build scripts and exports. Resolve the Gradio preview executable
  through Node so workspace hoisting does not break component builds. Python build
  and optional requirements follow the existing shared declaration policy.
- Add root TypeScript import-preservation settings for hoisted Svelte dependencies.
  Gradio's preprocessor otherwise removes a module-script import used by an
  instance script in `@gradio/statustracker`. This reproduces on the dependency
  source alone; it is a build-configuration defect exposed by local validation,
  not an established inspector merge regression.
- Restore the public `load_numeric_npz` export removed by an automatic merge;
  NPZ regression tests now import the public API.
- Explicitly retain the Gradio props proxy with `untrack` during one-time wrapper
  construction, avoiding the newer Svelte compiler's initial-reference warning.
- Retain dependency checks, parent ledger fixes, geometry fixes, and NURBS fixes
  from `integration/sync`. Update current package guidance; historical verification
  records remain labelled as prior evidence.
- Motorcycle development remains a future internal parent-app capability, not
  another intermediate package. This merge does not integrate the inspector into
  parent controllers or implement motorcycle tracing.

## Local validation

The build environment uses the existing Python 3.13 runtime with an isolated
editable diagnostics installation. Parent tests explicitly use `PYTHONPATH=src`
so they exercise this worktree rather than another checkout's editable install.
JavaScript dependencies use the root frozen Bun lockfile (Bun 1.4.0).

| Check | Result |
|---|---|
| Parent Python suite | 278 passed |
| Adopted and reference diagnostics Python suites | 183 passed |
| Public NPZ API regression after reconciliation | 13 passed |
| Mesh-healing suite | 83 passed |
| Python NURBS suite | 143 passed |
| Diagnostics TypeScript tests | 28 passed |
| Svelte check | Zero errors and warnings |
| Standalone production build | Passed; bundle-size advisory remains |
| Gradio assets and wheel build | Passed |
| Production standalone Chrome tests | 4 passed |
| Installed-wheel Gradio Chrome tests | 2 passed |
| Dependency declarations and resolved VTK ownership | Passed |
| Frozen root Bun install | Passed |

These installed-wheel browser checks were performed during consolidation; they
are not evidence supplied by the feeder process that generated the components.
No hosted CI or new native C++ qualification is claimed. In particular, the
native NURBS interface/build issue recorded as LE-7 in the integration review is
outside this merge's repairs; passing Python NURBS tests does not resolve it.
