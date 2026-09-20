# Package acceptance

Run in the canonical loose package layout, with the lockfile installed using
`npm ci`. Historical delivery reports in the archive are not current evidence.

| Boundary | Required behavior | Check |
|---|---|---|
| Python import | Numeric/document API imports outside source checkout | Install wheel in separate environment, inspect module paths |
| Numeric NPZ | Geometry aliases, no pickle, bounded headers/bytes, primitive arrays, preserved ordering, clear errors | `tests/test_io.py` |
| Prepared payload | Strict fields/indices/targets; existing report authority retained | Python contract/adapter tests; `tests/document.test.mjs` consumes Python fixture |
| Gradio backend | Null clears; output-only preprocessing; invalid payload fails; schema documentation is client-compatible | `tests/test_gradio.py` |
| Frontend compilation | Every adopted TS/Svelte/render source typechecks | `npm run check` |
| Standalone assets | Real production bundle resolves all imports | `npm run build`, browser suite also run against served production build |
| Inspector | Zero/one/two views; scalar/clip controls; local selection; invalid document clears stale geometry | `tests/browser/inspector.spec.ts` |
| Camera | Linked orbit changes both panes; independent orbit leaves other pane unchanged | Browser rendered-pixel comparison |
| Lifecycle | Clear/remount, hidden resize, actual context loss/restoration, failed initialization cleanup | Browser suite, browser error collection |
| Installed Gradio | Compiled assets serve; load/clear/reload; selection; visibility and resize | `tests/gradio-browser/component.spec.ts` using a wheel environment |

The backend owns prepared document validation, not file upload authorization or
engineering computation. Rendering normalization never changes source coordinates.
Selections belong to a mesh ID and geometry revision. Empty and unknown diagnostics
are not a pass. Synthetic paths and fixture geometry remain labeled.

Inspect captured standalone and Gradio screenshots for clipping, legibility and
usable controls. Typechecking is not a GPU test; browser success is not general
performance qualification. This acceptance suite does not qualify parent integration,
NURBS/STEP export, surface repair, or arbitrary large-model GPU memory envelopes.
