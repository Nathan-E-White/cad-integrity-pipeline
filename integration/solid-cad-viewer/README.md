# Solid CAD Viewer — mesh + B-Rep display base

A source-agnostic TypeScript/Solid viewer with a Three.js rendering core, optional TanStack Query loading, and a Nitro-compatible server boundary. It deliberately contains no engineering-domain rules.

**Implemented:** mesh rendering, topology-aware tessellation display and picking, assembly instances, camera controls, clipping, source adapters, numeric NPZ decoding, and a small demo.

**Not implemented:** a STEP/CAD kernel. `StepTessellator` is a real integration boundary, not a placeholder that returns imaginary triangles. Supply a kernel-backed worker/service, or request already tessellated documents through `HttpModelSource`. A B-Rep is displayed through its tessellation while retaining supplied face/edge IDs; the native exact model remains authoritative elsewhere.

## Run the demo

```sh
bun install
bun run dev
```

The project also supports npm. The package specifies Node 22.12+ for Vite and the Node-based tests. Bun is a package manager here; `bun run test` invokes Node intentionally.

The demo starts with a synthetic two-instance box assembly, including face/edge IDs and a large global translation. It is not an imported STEP model or a kernel-certified solid. Use the NPZ input to open `public/example.npz`. Choose units explicitly: the demo defaults to `unknown` rather than silently declaring millimeters.

```sh
bun run test       # strict compilation of dependency-free modules + Node tests
bun run typecheck # the full project, after dependencies are installed
bun run build     # full typecheck + Vite client build
bun run check     # Biome checks
bun run format    # Biome formatting, import organization and safe fixes
```

Dependencies could not be downloaded in the authoring environment. See `TESTING.md` for the precise validation boundary; this is not a claim of a completed browser acceptance test. Generate and commit your lockfile after installing the versions in your target application.

## Architecture

```text
STEP file ── injected StepTessellator ──┐
NPZ file  ── bounded numeric decoder ──┼── ModelDocument ── RenderModel ── ThreeCadViewer
API       ── normalized wire decoder ──┘                                     │
                                                                     CadViewer.tsx
                                                                           │
                                                                   ViewerPanel.tsx
                                                                           │
                                              ModelSource ── RemoteCadViewer.tsx
                                                                TanStack Query
```

| File | Responsibility |
| --- | --- |
| `src/model.ts` | Typed, validated display-document contract; identity, units, assembly and topology references. |
| `src/math.ts` | Double-precision transforms/bounds and camera-fit mathematics. |
| `src/selection.ts` | Triangle-to-face resolution, selection identity and stale-revision checks. |
| `src/viewer/ThreeCadViewer.ts` | Resource-owning imperative viewer class; cameras, controls, picking, layers and disposal. |
| `src/viewer/RenderModel.ts` | Transactional document-to-GPU construction, materials, visibility and highlights. |
| `src/viewer/CadViewer.tsx` | Thin Solid lifecycle/props wrapper. |
| `src/viewer/ViewerPanel.tsx` | Optional toolbar, status and selection controls. |
| `src/viewer/RemoteCadViewer.tsx` | Optional TanStack Query adapter around any `ModelSource`. |
| `src/data/*` | HTTP, worker-backed NPZ, numeric archive decoding and STEP injection. |
| `src/server/model-handler.ts` | Framework-independent authenticated, revision-addressed Web Request/Response endpoint factory. |
| `examples/nitro/*` | Nitro 3/H3 2 wrapper and explicitly public synthetic example service. |

Solid UI components are functions. Classes own imperative Three.js state; JSX belongs in `.tsx`, non-JSX classes in `.ts`.

## Direct component usage

Copy `src` into an existing app under your preferred module path, excluding `demo` and optionally `server`. This repository is a source starter, not a prebuilt published package.

```tsx
import { ViewerPanel, type ModelDocument, type Selection } from "./cad-viewer";

export function EngineeringViewport(props: { document: ModelDocument | null }) {
  const select = (selection: Selection | null) => {
    if (selection?.kind === "face") {
      console.log(selection.documentId, selection.revision,
        selection.nodeId, selection.faceId, selection.faceKind);
    }
  };
  return (
    <ViewerPanel
      document={props.document}
      height="70vh"
      onSelectionChange={select}
      onReady={(viewer) => viewer.setPreset("isometric")}
      onError={(error) => console.error("Viewer", error)}
    />
  );
}
```

For a custom UI use `CadViewer` directly. Give it a definite height, or place it inside a parent with one. Its `projection`, `displayMode`, `selectionMode`, `document` and `clippingPlane` props are reactive. Theme/pixel-ratio options are construction-time; remount to change them. `onReady` exposes the imperative class, including `setSelection`, `fit`, `setVisible`, `isolate`, `showAll`, `setPreset` and `installLayer`.

The supplied panel owns its toolbar modes. Drive modes through `CadViewer` props in a controlled custom UI rather than changing the panel's class handle independently and expecting its dropdowns to synchronize.

## Loading through TanStack Query

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/solid-query";
import { createMemo } from "solid-js";
import { HttpModelSource, RemoteCadViewer } from "./cad-viewer";

export function ModelPage(props: { id: string; revision: string; authScope: string }) {
  const client = new QueryClient(); // scoped to this app root/request, not a global SSR singleton
  const source = createMemo(() => new HttpModelSource(
    `/api/models/${encodeURIComponent(props.id)}?revision=${encodeURIComponent(props.revision)}`,
    ["models-api", props.authScope, props.id, props.revision],
  ));
  return (
    <QueryClientProvider client={client}>
      <RemoteCadViewer source={source()} height="70vh" />
    </QueryClientProvider>
  );
}
```

Use the existing provider in an application that already has one. A request key must include authorization scope, source identity, revision and any tessellation settings that affect output. Never put credentials in keys. Clear model queries on logout/tenant change and dispose the visible document; keys are not access control.

`RemoteCadViewer` forwards the query's AbortSignal, starts after mount, disables structural sharing for typed-array snapshots, and retains inactive entries for 60 seconds. Revisions are treated as immutable and fresh indefinitely: publish a new revision/key for changed data. Clear queries for stricter memory/privacy requirements. Exclude keys beginning with `cad-model` from SSR dehydration/persistence; numeric typed arrays are not ordinary JSON application state. The actual renderer module is dynamically imported after mount and cleaned up when its Solid owner is disposed.

For an HTTP example without any server integration, `public/fixture.json` is the normalized synthetic fixture:

```ts
const source = new HttpModelSource("/fixture.json", ["public-fixture", "1"]);
```

## The display document and its invariants

`ModelDocument` separates reusable geometry assets from assembly occurrences. Nodes have unique IDs and optional `parentId`, `geometryId` and affine local transforms. A geometry asset can be referenced by many independently selectable nodes. Geometry buffers are shared on the GPU; this is not GPU instanced draw batching.

Positions are XYZ in document units. Transforms are **column-major, affine, relative to the parent**, in the same right-handed coordinate convention. `upAxis` chooses Y or Z camera conventions; it does not transform input geometry. The source adapter must normalize other handedness/coordinate conventions and apply units consistently. Reflections are permitted; projective/singular transforms are rejected.

Triangles use a zero-based `Uint32Array`, with three indices per triangle. Original order is retained. The viewer never welds, smooths, sorts, repairs or reindexes source geometry. Per-vertex UVs are carried unchanged, including values outside [0,1]; texture display is not part of this base. Optional vertex IDs carry original source identity.

Topology is represented by:

```ts
faces: [
  { id: "F:outer-wall", kind: "brep-face" },
  { id: "F:inlet", kind: "brep-face" },
],
triangleFaces: new Int32Array([0, 0, 0, 1, 1, -1]),
// -1 means this triangle has no supplied semantic face association.
edges: [
  { id: "E:rim", kind: "brep-edge", positions: new Float64Array(/* XYZ samples */) },
],
```

An edge is a polyline: consecutive positions define segments; repeat the initial point to close it. A triangle's mapping indexes the face table, not the face ID string. NPZ numeric labels become `mesh-region` references, never invented B-Rep topology. When semantic information is absent, selection returns a triangle or object explicitly. Automatically derived feature edges are visual decoration and are not topology-selectable.

A selection includes document ID, revision, assembly node ID and asset ID, then a face/edge ID or triangle index. Identity is valid within a document revision. Persistent CAD naming across edits/reimport is the upstream kernel's problem; this base does not claim to solve it. The optional `native` handle stores provider/key/revision references, not a serialized exact CAD model, credentials or native pointers.

Source documents are immutable snapshots **by contract**. TypeScript `readonly` does not freeze typed-array bytes. Never change borrowed arrays in place while cached/rendered; create a replacement snapshot and new revision. Upload buffers and display highlights are separately owned by the renderer.

Validation checks indexing, finite numbers, IDs, maps, hierarchy and budgets. It deliberately permits open surfaces and degenerate triangles for inspection. Validation does not establish watertightness, manifoldness, valid trimming, manufacturability or a valid solid.

## NPZ source

NPZ is a container, not a standardized CAD schema. This implementation documents one mesh schema and allows its array names to be remapped:

| Default key | Logical shape | Meaning |
| --- | --- | --- |
| `positions` | `(N,3)` | Required XYZ coordinates. |
| `triangles` | `(T,3)` | Required zero-based integer vertex indices. |
| `normals` | `(N,3)` | Optional per-vertex normals. |
| `uv` | `(N,2)` | Optional original, unnormalized UV coordinates. |
| `triangle_faces` | `(T,)` | Optional nonnegative integer region labels; -1 means unmapped. |

```ts
import { NpzWorkerSource } from "./cad-viewer";

const source = new NpzWorkerSource(file, {
  id: crypto.randomUUID(), // use a content-addressed ID for persistent caching
  revision: "1",
  name: file.name,
  units: "mm", // caller's knowledge, not guessed from coordinates
  upAxis: "Z",
  keys: { positions: "vertices", triangles: "faces" }, // optional mapping
});
```

Use `NpzModelSource` for a no-worker fallback or `decodeNpz` directly. Worker loading terminates the worker on cancellation, including synchronous CPU decode. The fallback only observes cancellation at checkpoints and asynchronous boundaries.

Supported: numeric NPY v1/v2/v3, little/big-endian values, signed/unsigned 1/2/4/8-byte integers, float32/64, C and Fortran layout, stored ZIP and deflate. Integer64 values outside JavaScript's exact integer range are rejected. Object/pickle, strings, structured dtypes, half floats and booleans are not accepted. Neither pickle nor header text is executed. Only selected array members are decoded. CRCs, lengths and input/expanded/decoded budgets are checked. There is no archive extraction to disk. Central-directory ZIP64, encrypted and multi-disk archives are rejected; NumPy's common local ZIP64 headers with 32-bit central sizes are supported.

Compressed input requires native `DecompressionStream("deflate-raw")` support in the browser/worker; incompatible browsers should use server decoding or a vetted decompressor adapter. Current budgets are guardrails, not a process-memory guarantee: transient arrays, wire decoding and GPU upload can coexist. For untrusted large uploads, isolate parsing in a quota-limited backend worker process.

`public/example.npz` was generated with real NumPy. Its generator is `scripts/make-example-npz.py`. More complex NPZ schemas—assemblies, per-corner attributes, NURBS coefficients, point clouds—need their own mapper to `ModelDocument`.

## STEP source

```ts
import { StepModelSource, type StepTessellator } from "./cad-viewer";

export function sourceForStep(file: Blob, kernel: StepTessellator) {
  return new StepModelSource(
    ["my-kernel", "asset-42", "revision-7", "mm", 0.05, 0.15],
    file,
    kernel,
    { outputUnits: "mm", linearDeflection: 0.05, angularDeflectionRadians: 0.15 },
  );
}
```

The numerical tolerances above illustrate the interface, not recommended engineering acceptance criteria. The adapter owns STEP parsing, document/assembly locations, unit conversion, face-oriented triangulation, trimmed surfaces, normals, CAD edge sampling and ID assignment. It should retain the exact model outside the rendering document. Its cancellation implementation must stop or detach expensive work safely; the interface alone cannot preempt a native kernel.

For server-side kernels, an import/tessellation job can publish a revision-addressed normalized model and then use `HttpModelSource`. JSON is an inspectable reference transport; very large models should use a binary/chunked transport under another `ModelSource`, preserving the same document contract. Do not put CPU-heavy CAD translation synchronously on Nitro's request event loop.

## Nitro integration

`src/server/model-handler.ts` requires an injected `ModelService` with both authorization and repository loading. It only resolves opaque, bounded model IDs and revisions; it is not an arbitrary file reader or URL proxy. It verifies returned identity/revision, validates the document, uses private/no-store HTTP headers, and avoids returning raw server diagnostics.

`examples/nitro` shows current Nitro 3/H3 2 `defineHandler` wiring and explicit `serverDir` configuration. It intentionally is not installed into the standalone Vite demo and is excluded from that demo's typecheck. Reuse your existing Nitro installation/configuration; a Nitro 2 application needs its existing H3 event-to-Web-Request wrapper instead. The framework-independent service contract remains unchanged.

The only publicly authorized example is `/api/models/synthetic-box-assembly?revision=1`. Replace the synthetic service with your application's authentication, ACL checks and repository. Never retain its demonstration authorization policy for private uploaded models. Authentication and backend isolation are not supplied by a browser viewer.

## Rendering behavior and extension points

The core supplies perspective/orthographic cameras; orbit/pan/zoom; fit; principal views; shaded, shaded-with-edges and wireframe modes; face, edge, triangle and object picking; selection overlays; hide/isolate/show-all; visual clipping; resizing; on-demand rendering; and explicit GPU cleanup. Clicks are distinguished from orbit drags. F fits, Escape clears, and double-click fits.

Source float64 coordinates are recentered per geometry and again in assembly/world space before float32 GPU use. This improves display precision for large offsets without modifying the source data. It does not make all render calculations exact, fix pathological scale ranges or recover precision already lost upstream. Returned picked points are approximate intersections in the original document's world coordinate frame.

Clipping keeps `normal · point + constant >= 0` in document-world coordinates and is honored by picking. It is visual material clipping: no section caps, exact section curves or altered source geometry are produced. Custom layers must implement their own clipping behavior when needed.

`ViewerLayer.mount(context)` gets an overlay group, document snapshot, origin conversion, camera accessor and invalidation function. Return a cleanup function for every layer-owned resource/listener. Layers remount on document changes. They are excluded from base picking/bounds. Use composition for coordinate axes, analysis fields, region labels, measurements and domain overlays rather than subclassing file readers or mixing physics into the renderer. A mount function that throws must clean up any resources it allocated before throwing.

Deliberate omissions: exact B-Rep editing/evaluation/booleans, analytic measurement, model healing, STEP export, scalar legends/field solvers, part-tree UI, BVH acceleration, GPU pick buffers, LOD, out-of-core meshes, textures and hidden-line rendering. Baseline picking and face highlighting scan triangles; the provided maximum-size validation limits are not an interactive performance promise. A future BVH/optimizer must preserve or explicitly remap source triangle identity.

## Upstream references

- Solid lifecycle: https://docs.solidjs.com/reference/lifecycle/on-mount and https://docs.solidjs.com/reference/lifecycle/on-cleanup
- TanStack Solid Query: https://tanstack.com/query/latest/docs/framework/solid/overview
- Query cancellation: https://tanstack.com/query/latest/docs/framework/solid/guides/query-cancellation
- Three.js picking: https://threejs.org/docs/pages/Raycaster.html
- Three.js controls: https://threejs.org/docs/pages/OrbitControls.html
- OpenCascade tessellation: https://occt3d.com/dev/doc/overview/html/occt_user_guides__mesh.html
- NumPy format: https://numpy.org/doc/stable/reference/generated/numpy.lib.format.html
- Nitro routing: https://nitro.build/docs/routing
- Biome configuration: https://biomejs.dev/reference/configuration/
