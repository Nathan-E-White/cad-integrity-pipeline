# Mesh diagnostics: functional seams

A source integration bundle for triangle-mesh diagnostics and an interactive Svelte/Three.js view. It replaces the duplicated snippets with numerical, contract, transport, rendering, and UI boundaries. **It is not a prebuilt Gradio custom-component wheel, a replacement CAD kernel, or a full FEM validator.**

Start with `CODEX_INTEGRATION.md` before merging into the mother project. The standalone renderer is an exercise harness; reuse the mother's existing framework-independent viewer instead of introducing a competing renderer when one is already available.

## What is implemented

The viewport includes a ghost shell, subdued tessellation wireframe, batched diagnostic edges, compact failed-triangle overlays, vertex markers for collapsed triangles, hover/focus preview, click-to-pin selection, separate fit and clear controls, and an explicit X-ray toggle. A depth-only pass makes occlusion meaningful when the visible shell is transparent and X-ray is off. The default highlight is steady; an optional smooth 1 Hz pulse and orbit damping respect reduced-motion preferences.

The viewport mounts even when the initial value is null, waits for nonzero container dimensions, fits on geometry replacement rather than metric clicks, renders on demand except during interaction/pulse, and pauses offscreen/when the document is hidden. Controls, observers, DOM listeners, materials, geometries, and the renderer have explicit ownership and cleanup. Context-loss/restoration handlers are present; real-browser behavior still needs the acceptance tests below.

Python computes unsigned triangle mean-ratio quality, radius aspect ratio, degeneracy, unique edge incidence, boundary edges, >2-incidence edges, two-face winding conflicts, repeated-index triangles, and duplicate-face groups. Optional per-triangle reference normals supply an independent orientation comparison.

## Layout and ownership

| Location | Responsibility |
|---|---|
| `python/mesh_diagnostics/model.py` | Validated, owned, read-only triangle-array snapshots and geometry revisions |
| `quality.py` | Vectorized, unit-invariant triangle quality and optional reference-normal alignment |
| `topology.py` | A single reusable edge-incidence/CSR table and combinatorial defect sets |
| `audit.py` | Configurable audit policy; no UI, serialization, or repair |
| `contract.py` | Pydantic schema and cross-reference validation |
| `payload.py` | Numerical results to metrics + revision-scoped targets |
| `legacy.py` | One explicit compatibility adapter for old aliases and unclassified segments |
| `io.py` | Bounded, pickle-free, header-validated NPZ loading |
| `frontend/src/model/` | TypeScript contract, unknown-JSON validation, coordinate frame, compact buffers |
| `frontend/src/render/DiagnosticsLayer.ts` | Framework-independent diagnostic overlays |
| `frontend/src/render/ThreeMeshViewport.ts` | Standalone Three.js lifecycle/camera/render host |
| `frontend/src/render/resources.ts` | Idempotent explicit resource ownership |
| `frontend/src/components/` | Svelte view and accessible metric panel |
| `frontend/Index.svelte` / `Example.svelte` | Thin Gradio-facing presentation and lightweight example view |
| `gradio_adapter/meshdiagnostics.py` | Gradio data model, serialization, example values and select event |
| `examples/` | Synthetic fixture generator and explicit pipeline integration examples |
| `tests/`, `frontend/test/` | Numerical, safety, contract, buffer and ownership regressions |

## Python usage

```bash
python -m pip install -e '.[test]'
python -m pytest -q
PYTHONPATH=python python examples/make_fixtures.py
```

```python
from mesh_diagnostics import (
    TriangleMesh, AuditPolicy, audit_mesh, payload_from_audit,
)

mesh = TriangleMesh(
    vertices, faces,
    mesh_id="bracket-17",
    geometry_revision="authoritative-revision-42",  # omit to compute a geometry digest
    stage="original", units="mm",
)
result = audit_mesh(mesh, AuditPolicy(
    require_closed_surface=True,
    min_mean_ratio=0.15,
    max_radius_aspect=3.0,
))
viewer_value = payload_from_audit(result).model_dump()
```

The policy defaults are illustrative inspection thresholds, not industry acceptance standards. Results are for **linear surface triangles**, not tetrahedra, hexahedra, high-order elements, or native B-Rep validity.

When the existing pipeline has already computed the diagnostics, **do not rerun `audit_mesh` in the component**. Use the assembly seam:

```python
from mesh_diagnostics import FaceTarget, Metric, assemble_payload

bad_faces = FaceTarget(
    id="analysis:low-shape-quality",
    geometry_revision=mesh.geometry_revision,
    ids=failed_triangle_ids,
)
metric = Metric(
    id="analysis:low-shape-quality-count",
    label="Low shape-quality triangles",
    value=len(failed_triangle_ids),
    status="fail" if failed_triangle_ids else "pass",
    target_id=bad_faces.id,
    description="Computed by the authoritative existing pipeline.",
)
viewer_value = assemble_payload(mesh, metrics=[metric], targets=[bad_faces]).model_dump()
```

`mesh_from_mapping` accepts exactly one position alias (`vertices`, `positions`) and one connectivity alias (`faces`, `indices`, `triangles`). It accepts flat triples or N×3 arrays, rejects quads/ragged arrays, and never silently casts fractional or negative indices into unsigned integers.

`adapt_legacy_payload` preserves old metric values as producer-supplied assertions. It does not claim that a legacy “Jacobian” is a signed Jacobian. Old `error_edges` become unclassified world-coordinate segments; missing metric IDs get explicit, inspectable legacy rows. It never guesses semantic links from display labels.

## Standalone frontend development

```bash
cd frontend
bun install
bun run test
bun run check
bun run dev
```

`npm install` / `npm run ...` are also usable. The test script requires Node 22.6+ because it uses native TypeScript stripping. The demo uses Svelte 5's `mount`; the reusable component sources use legacy `export let` / reactive syntax to avoid forcing a compiler migration in the Gradio host. They were compiled here with Svelte 5.48.0. Svelte 4 host compatibility has not been exercised.

The Three.js reference dependency is explicitly `0.180.0`, not a claim about the newest release. Keep the mother project's vetted dependency versions and corresponding addons/types together. Resolve and commit a lockfile in that project. A full npm/Bun install/build could not be performed in the delivery environment; see `docs/VERIFICATION.md` for the exact checks that did run.

## Contract

The JSON schema is `docs/mesh-diagnostics.schema.json`, generated from `MeshPayload` by `examples/make_fixtures.py`.

Each payload identifies `mesh_id`, `geometry_revision`, `diagnostic_revision`, `stage`, and `units`. Geometry is flat `positions` + `triangles`. Source triangle IDs refer to the triple ordering in **this payload**, not a previous mesh, a native CAD face, or a post-decimation mesh.

Metrics contain an independent `target_id`. Targets are discriminated unions:

```typescript
type Target =
  | { id: string; geometry_revision: string; kind: "faces"; ids: number[] }
  | { id: string; geometry_revision: string; kind: "edges"; indices: number[] }
  | { id: string; geometry_revision: string; kind: "segments"; positions: number[] };
```

An edge target contains vertex-index pairs, not coordinates. A segment target contains flat world-coordinate sextuples. Optional `triangle_parent_faces` is an explicit upstream identity map; it does not itself establish a relationship to a native B-Rep. All target revisions must match the payload geometry revision. Metric IDs and target IDs must be unique within their respective collections.

A changed geometry/topology/order requires a changed geometry revision. Changed diagnostics/policy require a changed diagnostic revision. These identifiers are cache/provenance keys, not cryptographic authorization. Caller-provided revisions are trusted immutable identities. The orchestrator, not the viewer, must reject stale job responses; hashes are not timestamps.

## Precision and scaling

Python keeps coordinates in float64. JSON carries finite numeric values. The frontend computes a local origin and uniform rendering scale **before** converting positions to Float32Array. Indexed overlays use the same local vertex table; legacy coordinate segments use the same transformation. This avoids unnecessary float32 precision loss from a large global offset. It does not make a float32 viewport exact metrology, preserve sub-float64 input detail, or solve huge local dynamic-range problems.

The inline contract has conservative resource ceilings: 250,000 vertices, 500,000 triangles, 128 targets, 512 metrics, and a combined diagnostic scalar budget. Wireframe construction is omitted above 150,000 triangles. These are guardrails, not benchmark-certified capacity guarantees. Large payloads must move to authorized binary artifacts, workers and explicit display-to-analysis mappings rather than casually raising every ceiling.

NPZ compression does not survive conversion into ordinary JSON lists. This implementation is not a compressed stream, a zero-copy GPU path, or an out-of-core mesh analyzer. NumPy's edge sort is O(F log F) with O(F) storage. No face decimation or vertex welding occurs silently.

## Gradio integration

Generate/build the custom component using the mother's pinned Gradio toolchain. Copy the adapter's class into that generated backend package, and use `frontend/Index.svelte` and `Example.svelte` with the generated frontend configuration. Preserve the scaffold's `Block`, `StatusTracker`, styles, packaging/build hooks and compiler dependencies as appropriate. The minimal wrapper here forwards the select event without importing Gradio's private UI internals.

`postprocess` only validates and serializes prepared values. It does not open a user-supplied path or run the audit. `None` clears the view. Invalid payloads raise explicit errors. File upload stays in a standard `gr.File(type="filepath")`; application/session authorization precedes the local NPZ loader.

Hover/focus is entirely local. Pin/unpin emits `select` with an integer metric index and a value carrying mesh/revision/metric/target identifiers. It does not resend the entire geometry or emit `change` on every backend update. Selection event data and client-returned metrics remain untrusted input.

See `examples/gradio_app.py` after the custom-component package is built; its `gradio_meshdiagnostics` import is intentionally a scaffold-dependent integration point.

## Scientific scope

See `docs/MATHEMATICS.md`. The audit deliberately does not compute vertex-link manifoldness, self-intersection, boundary loop counts, homology/Betti numbers, global outwardness, or signed FEM Jacobians. The UI marks these as not checked. “No edge-incidence defects” is not “valid solid.” An open surface can be correct under an open-surface policy.

The ghost shell is an inspection material, not physically accurate optical glass or order-independent transparency. X-ray mode prioritizes finding defects and explicitly sacrifices occlusion cues. Wireframe shows tessellation, not recovered CAD topology.
