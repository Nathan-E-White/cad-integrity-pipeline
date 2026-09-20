# Mesh diagnostics inspector

A standalone Svelte/Three.js inspector and an output-only Gradio component, sharing
one `InspectorDocument` v1 contract and renderer. This package displays prepared
engineering reports. It does not repair meshes or replace the parent application's
audit, upload policy, or result ledger.

## Layout and public interfaces

| Path | Responsibility |
|---|---|
| `python/cad_mesh_inspector/` | Validated documents, host-report adapters, numeric NPZ reader, standalone reference diagnostics |
| `backend/gradio_meshdiagnostics/` | Installed `MeshDiagnostics` component and generated assets |
| `src/core/` | Browser validation, revision-scoped targets, display coordinates and state |
| `src/render/` | One viewport lifecycle, surface/diagnostic layers, picking, linked cameras |
| `src/components/MeshInspector.svelte` | Reusable inspector accepting `value: unknown`; validates incoming documents |
| `Index.svelte` | Gradio shared props, loading status and visibility; delegates to the inspector |
| `src/main.ts`, `src/Demo.svelte` | Standalone fixture harness |
| `examples/` | Python-generated torus fixture and installed-component demo |

```python
from cad_mesh_inspector import document, mesh_payload, load_numeric_npz
from gradio_meshdiagnostics import MeshDiagnostics

arrays = load_numeric_npz("authorized-local-mesh.npz")
mesh = mesh_payload(arrays["positions"], arrays["triangles"],
                    mesh_id="source", revision="source-hash", frame_id="world",
                    length_unit="mm")
value = document(mesh).model_dump(mode="json")
```

`adapters.from_triangle_reports` and `adapters.from_polygonal_report` project
existing host reports. Use those adapters or `mesh_payload` when audit results
already exist; `inspect_triangles` is a standalone reference path.

`None` clears the inspector. Invalid input produces a visible error and clears stale
geometry. Metrics remain readable when WebGL is unavailable. Controls and hover do
not rebuild base geometry. Replacing an incoming document remounts its panes and
resets local selections/controls; camera poses and display controls are not persisted
between documents. Within a document, hover temporarily overrides a pinned target.
Linked cameras share a display frame only when units and frame IDs agree. Face IDs
are never copied between source and candidate panes.

## Standalone development

From this directory, with Node available:

```sh
npm ci
npm run check
npm test
npm run build
npm run dev
```

The development server binds loopback. `npm run build` emits the standalone harness
under `dist/`; it is not the Gradio wheel. Svelte 5 is the supported framework target.
The lockfile includes the standalone Vite toolchain and Gradio preview's own toolchain.
No sibling package dependency graph is changed.

## Build and install the Gradio wheel

Use a separate Python environment with Python 3.11 or later. Install the project's
Gradio extra, build tools, and editable source before building the frontend:

```sh
python -m pip install hatchling build editables
python -m pip install -e '.[gradio,test]'
npm ci
python scripts/build_component.py
```

The builder uses the installed Gradio preview tooling and checks that actual component
assets were emitted before creating `dist/gradio_meshdiagnostics-0.1.0-py3-none-any.whl`.
The wheel contains both Python import packages. The numeric/document API can be
imported without Gradio; importing `gradio_meshdiagnostics` requires the Gradio extra.

Install that wheel in a separate runtime environment and run:

```sh
python -m pip install 'dist/gradio_meshdiagnostics-0.1.0-py3-none-any.whl[gradio]'
python examples/gradio_demo.py
```

The demo defaults to `127.0.0.1:7878`; set `GRADIO_SERVER_PORT` to change its port.
It does not modify or launch the parent app. The generated component class owns its
packaged frontend; `cad_mesh_inspector.gradio_component` provides backend behavior
for that class and is not the component users should instantiate in an app.

## Numeric NPZ contract

`load_numeric_npz(path, limits=ArchiveLimits())` accepts an authorized local file with
exactly one `positions`/`vertices` array and one `triangles`/`faces` array. It returns
read-only canonical arrays, preserving vertex and triangle order. Structured/object,
boolean, complex and string arrays are rejected, as are fractional connectivity,
nonfinite coordinates, bad indices, unexpected members and ambiguous aliases.

The reader checks ZIP and NPY headers before materializing arrays. Defaults are
64 MiB compressed, 128 MiB expanded, at most four members and 10,000 header bytes;
geometry additionally uses the contract's 500,000-vertex and 250,000-triangle bounds.
Duplicate/encrypted members, inconsistent body sizes, oversized shapes and pickle
payloads fail. Malformed ZIP containers retain `zipfile.BadZipFile`; invalid content
raises `ValueError`. No archive member is extracted to disk.

IDs, revisions, frame, units and provenance are explicit caller metadata. This
optional helper does not replace the parent application's restricted
`vertices/triangles/length_unit` upload format. It introduces no browser filesystem
endpoint, browser NPZ worker, or inferred repair.

## Verification

```sh
python -m pytest tests
npm run check
npm test
npm run build
npx playwright test
INSPECTOR_PYTHON=/absolute/path/to/wheel-environment/bin/python \
  npx playwright test --config playwright.gradio.config.ts
```

Browser tests use installed Google Chrome and loopback ports 5178 and 7878. The
Gradio test must use a wheel installation, not the editable source. See
`ACCEPTANCE.md` and `VERIFICATION.md` for current evidence and limits.

## Provenance and integration boundary

The loose delivery is the canonical working base. `PROVENANCE.json` records each
original-to-current path, original SHA-256 and byte matches in the preserved archive.
The archive is a distinct delivery with different Python names and payload contracts;
it must not be extracted over this source. Its header-first numeric reader informed
`npz_io.py`; its broader accepted aliases and error types were not adopted.

The original delivery did not supply a standalone license grant. Preserve its source
attribution and archive; do not infer a new redistribution license from third-party
dependency licenses. Those dependencies retain their own package notices.

`docs/MESH_DIAGNOSTICS_STABILIZATION_PLAN.md` in the parent repository defines this
work. Parent integration still requires authoritative report projection, explicit
stage/revision/units/source-face mapping, and preservation of candidate visibility.
This v1 contract has one mesh revision; separate diagnostic revision is future,
explicit schema work. Mesh healing and NURBS export remain separate qualification tasks.
