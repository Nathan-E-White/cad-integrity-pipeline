import { QueryClient, QueryClientProvider } from "@tanstack/solid-query";
import { createSignal, Show } from "solid-js";
import { NpzWorkerSource } from "../data/NpzWorkerSource";
import type { ModelSource } from "../data/sources";
import type { LengthUnit } from "../model";
import { RemoteCadViewer } from "../viewer/RemoteCadViewer";
import { ViewerPanel } from "../viewer/ViewerPanel";
import { makeDemoDocument } from "./fixture";

export default function App() {
  const client = new QueryClient();
  const fixture = makeDemoDocument();
  const [source, setSource] = createSignal<ModelSource>();
  const [units, setUnits] = createSignal<LengthUnit>("unknown");
  return (
    <QueryClientProvider client={client}>
      <main style={{ "max-width": "1440px", margin: "24px auto", padding: "0 20px", "font-family": "system-ui, sans-serif" }}>
        <h1>Geometry viewer</h1>
        <p>Source-agnostic mesh and B-Rep presentation. The built-in fixture has two instances, semantic faces, and explicit edges.</p>
        <div style={{ display: "flex", gap: "16px", "flex-wrap": "wrap", "align-items": "center", "margin-bottom": "16px" }}>
          <label>NPZ units <select value={units()} onChange={(e) => setUnits(e.currentTarget.value as LengthUnit)}>
            <option value="unknown">Unknown (do not assume)</option><option value="mm">Millimetres</option><option value="m">Metres</option><option value="in">Inches</option>
          </select></label>
          <label>Open local NPZ <input type="file" accept=".npz" onChange={(e) => {
            const file = e.currentTarget.files?.[0];
            if (file) setSource(new NpzWorkerSource(file, { id: crypto.randomUUID(), revision: "1", name: file.name, units: units(), upAxis: "Z" }));
            e.currentTarget.value = "";
          }} /></label>
          <button type="button" onClick={() => setSource(undefined)}>Reset demo</button>
        </div>
        <Show when={source()} fallback={<ViewerPanel document={fixture} height="70vh" />}>
          {(modelSource) => <RemoteCadViewer source={modelSource()} height="70vh" />}
        </Show>
        <p>Drag: orbit. Right-drag: pan. Wheel: zoom. F: fit. Escape: clear. Edge picking requires “Shaded + edges”.</p>
        <p>NPZ keys: positions (N×3), triangles (T×3), optional normals, uv, triangle_faces. STEP import requires an injected tessellator or a normalized server response.</p>
      </main>
    </QueryClientProvider>
  );
}
