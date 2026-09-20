# Stabilization verification — September 20, 2026

The four stabilization deliverables are implemented. The canonical source is the
reorganized loose delivery, with its archive preserved unchanged. Parent-app
integration has not been performed.

| Check | Result |
|---|---|
| Locked dependency reproduction | `npm ci --ignore-scripts --no-audit --no-fund` passed |
| Package Python suite | 64 passed, no skips, 2.89s |
| Parent app regression suite | 253 passed, no skips, 10.17s |
| Full Svelte/Three.js typechecking | 0 errors, 0 warnings |
| Pure TypeScript public-boundary tests | 3 passed; Python fixture, revision-scoped selection, null/invalid input |
| Standalone production build | Passed; Vite reports the expected large Three.js bundle warning |
| Production-build Chrome suite | 4 passed, 10.7s |
| Installed-wheel Gradio Chrome suite | 2 passed, 16.1s |
| Wheel packaging | Gradio component/example JS, CSS and runtime assets emitted; both Python packages included |
| Installed imports | Verified in a separate environment's site-packages, outside the source checkout |
| Visual inspection | Standalone and Gradio screenshots inspected for geometry, layout, controls and metrics |

Commands are in README.md. For the served production suite, set
`INSPECTOR_PRODUCTION=1` when running `npx playwright test`. For the Gradio suite,
set `INSPECTOR_PYTHON` to the Python executable of the wheel environment.
Timing values are observations, not performance guarantees.

The browser suite covers zero/one/two meshes, local selection/clear, scalar and clip
controls, invalid-document clearing, hidden resize, repeated mounts, real WebGL
context loss/restoration, and failed initialization cleanup. Rendered-pixel checks
verify linked orbit changes the other pane while independent orbit does not.
The installed Gradio tests additionally observe loading status, dynamic removal and
recreation through `gr.render`, and context recovery under the actual host.

Browser checks exposed unbound animation callbacks and partial-constructor canvas
leaks; both were fixed. Installed-host testing exposed a Gradio client schema
converter that rejects boolean additionalProperties. API metadata now omits that
unsupported documentation keyword; runtime InspectorDocument validation stays strict,
including rejection of unexpected keys.

Builds use a temporary editable build environment; runtime tests use a separate
wheel environment. `scripts/build_component.py` verifies the editable source location
and removes only its generated component/example asset directories before building,
so a no-op discovery cannot qualify stale assets.

## Standards

No actionable Standards findings. The reviewed boundaries separate document
validation/camera registration, per-pane viewport lifetime/local interaction, Gradio
presentation, and numeric archive admission. The registration subclass serves actual
Gradio asset ownership rather than introducing another renderer.

## Spec

Zero remaining findings. Review initially identified missing installed-host loading,
mount/unmount and context-recovery coverage. The added installed-host test closes that
gap. No parent-app integration or unrelated geometry/export work was introduced.

## Environment and limits

Python 3.13.15, NumPy 2.5.3, Pydantic 2.13.5, Gradio 6.27.0,
gradio_client 2.7.0; Node 26.7.0; Svelte 5.48.0; Three.js/types 0.180.0;
TypeScript 5.9.2; Playwright 1.63.0; installed Google Chrome on macOS ARM64.
The lockfile records the standalone and Gradio build toolchains.

No hosted CI, arbitrary-model performance envelope, exhaustive GPU memory budget,
STEP/NURBS export, surface repair, or parent-controller integration is established.
Incoming document replacement resets panes and local view state; interactions within
a document reuse its geometry. Separate diagnostic revision remains future schema
work. Original delivery reports are retained in the unchanged archive and must not
be confused with these local results.
