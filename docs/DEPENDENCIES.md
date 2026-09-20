# Dependency and artifact ownership

The root repository owns shared dependency policy. Children retain their own dependency
sets and package identities. Sharing a workspace does not integrate the Solid application
or qualify the incomplete diagnostics delivery for use in Gradio.

## Python

- `pyproject.toml` owns the application and the macOS ARM64 Pixi environment.
- `pixi.lock` is the exact environment lock. Use `pixi install --locked` and
  `pixi run --locked <task>` for reproduction.
- `dependency-policy.toml` declares shared Python compatibility ranges. All managed
  child `pyproject.toml` files use the same ranges for shared dependencies.
- `requirements/constraints.txt` records exact shared runtime/test versions from the
  validated Pixi environment for pip/CI. It is a portable baseline, not a complete
  hash-locked Linux dependency graph. Build backends keep their own requirements.
- `scripts/check_dependencies.py` checks shared declarations, duplicate ranges,
  requirements-file mirrors, component versions, local Pixi paths, JavaScript catalog
  use, and lockfile ownership. `--environment` also checks installed shared versions.
- The root `ui` extra declares both Gradio components at their local package versions.
  Pixi resolves those names from `components/`; pip callers must supply those local
  packages explicitly rather than look for these unpublished packages on PyPI.
- Component Python and frontend versions are `0.0.1`; this need not equal the app or
  unrelated prototype versions. Component demo requirements match those versions.
- Prototype minimum Python versions remain their own compatibility declarations.
  The repository's validated development runtime is Python 3.13. Conda numerical
  bounds are intentionally narrower than the reusable Python package ranges.

From the repository root, a pip-based development installation is:

```sh
python -m pip install -c requirements/constraints.txt \
  -e ./components/topological_delta_audit \
  -e ./components/verification_grid \
  -e '.[algebra,cad,notebook,ui,dev]'
```

The mesh-healing requirements files still support standalone installation with their
own dependency sets. Within this repository, apply the shared constraints file when
using pip. Installing every prototype into the root environment is unnecessary;
notably the flattened diagnostics package still has missing source/layout problems.

## CadQuery and native bindings

The root `cad` extra now includes CadQuery. The resolved baseline is CadQuery 2.8.0,
OCP 7.9.3.1.1, and PyPI VTK 9.6.2. `pythonocc-core` remains conda-only and explicitly
selects its `novtk` build. This keeps one owner for VTK: the wheel stack used by OCP
and CadQuery. PythonOCC's VTK bridge is intentionally unavailable; its CAD kernel
interfaces remain available. The Gradio viewer does not use that bridge.

This distinction is binary compatibility, not merely version alignment. A clean
install with conda VTK 9.6.2 satisfied the resolver but failed to load OCP because the
wheel expects PyPI VTK's library names/layout. The older mixed environment also had
missing and duplicate VTK files. The final environment is rebuilt from the corrected
lockfile. The previous environment is retained at
`.pixi/envs/default-before-cad-alignment` for recovery; it is not an active environment.

```sh
pixi run --locked check-cad
pixi run --locked test-mesh-healing
pixi run --locked test-nurbs
```

The CAD smoke check fails on import or native construction failure; a missing backend
cannot be reported as a passing skipped test. No changes to repair algorithms or
prototype application wiring are implied by these environment checks.

## JavaScript

One root `package.json` defines explicit Bun workspaces and a shared version catalog;
only root `bun.lock` owns resolution. The two previous child Bun locks are removed.
Children reference shared dependencies with `catalog:` while keeping unique dependencies
such as Solid Query out of the Gradio components.

Shared versions include Svelte 5.57.1, Vite 8.3.0, TypeScript 5.9.3, the Svelte Vite
plugin 7.3.0, and Three.js/types 0.186.0. The Gradio preview package already required
Vite 8. The Solid Vite plugin is updated to 2.11.14, whose peer range accepts Vite 8.
This replaces the incompatible original Vite 6/7 declarations. These are selected,
locked versions, not claims about the latest available releases.

Use Bun 1.4.0 and Node 22.12 or later:

```sh
bun install --frozen-lockfile --ignore-scripts
pixi run --locked build-components
```

The component build tasks use the Gradio CLI in the Pixi environment and disable
README/demo regeneration. The existing `pixi run gradio` task remains the app launcher.

Do not run independent npm installs or create child locks. Catalogs and workspaces are
[Bun's supported shared-version mechanism](https://bun.sh/docs/pm/catalogs). Reference
prototype build/test scripts remain their own checks; they are not implicitly run by
the app's build. Gradio component wheels must be built with frontend assets before
being treated as deployable UI distributions.

## Artifact manifests

`scripts/verify_artifacts.py` inventories tracked files plus untracked, unignored
source files using Git. It respects root and child ignore rules, so Finder metadata,
`node_modules`, build output, and local caches do not enter the manifest. Tracked files
remain covered even if an ignore rule later matches them. New untracked source still
causes verification to fail until recorded. A Git checkout is required.

`--write` updates the two live integration bundle checksum lists and then the root
`SHA256SUMS.json`. Original delivery archives remain unchanged and retain their original
manifests. The extracted live package manifests can therefore intentionally differ
from the archived snapshots. Example fixture provenance is verified, never regenerated
by this command.

```sh
pixi run --locked check-dependencies
pixi run --locked python scripts/verify_artifacts.py --write
pixi run --locked check-artifacts
```

Review the diff before committing. Dependency upgrades should update declarations,
root locks, portable shared constraints, and checksums together. CI installs the local
components and UI extra explicitly, verifies the Bun lock, checks dependency policy and
CAD availability, builds the two components, then runs the existing gates. Deferred
prototype lint/type errors are still reported; these changes do not suppress them.

## Verification for this alignment

Local checks on September 19–20, 2026, after a clean install of the final lock:

| Check | Result |
|---|---|
| Root Python suite | 260 passed; no skips |
| Mesh-healing suite, including STEP | 69 passed; no skips |
| NURBS suite, including STEP | 132 passed; no skips; earlier export crash did not recur |
| CadQuery/OCP/VTK smoke and combined PythonOCC import | Passed; no duplicate VTK library warnings |
| Dependency declarations and installed shared versions | Passed |
| Fresh Bun workspace frozen install | Passed in an empty temporary workspace; repeat frozen install unchanged |
| Two Gradio custom-component frontend/wheel builds | Passed |
| General viewer core tests and full production build | 47 passed; build passed with a bundle-size warning |
| Root Python wheel/sdist and compilation | Passed |
| New/changed validation scripts lint and manifest regression tests | Passed |
| Root and live bundle checksums | Passed; immutable example provenance checks retained |

The diagnostics prototype build still fails on its existing missing `/src/main.ts`
layout. Root lint still reports eight pre-existing errors and mypy reports the
undefined motorcycle helper. Those prototype/application issues remain deferred.
The updated hosted workflow has not been pushed or executed in GitHub Actions; these
are local results, not a hosted-CI claim. No browser/GPU acceptance was performed.
