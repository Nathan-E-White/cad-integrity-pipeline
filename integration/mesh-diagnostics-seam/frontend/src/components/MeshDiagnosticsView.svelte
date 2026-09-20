<script lang="ts">
  import { onMount } from "svelte";
  import { decodePayload } from "../model/parse.ts";
  import type { MeshDocument, Metric, MetricSelection } from "../model/types.ts";
  import { ThreeMeshViewport, DEFAULT_OPTIONS, MAX_WIREFRAME_TRIANGLES } from "../render/ThreeMeshViewport.ts";
  import MetricsPanel from "./MetricsPanel.svelte";

  export let value: unknown = null;
  export let onSelection: (selection: MetricSelection) => void = () => {};
  let host: HTMLDivElement;
  let viewport: ThreeMeshViewport | null = null;
  let selectedTarget: string | null = null;
  let previewTarget: string | null = null;
  let selectedMetric: { id: string; index: number } | null = null;
  let currentIdentity: string | null = null;
  let runtimeError: string | null = null;
  let options = { ...DEFAULT_OPTIONS };

  $: decoded = decodePayload(value);
  $: document = decoded.document;
  $: reconcile(document);
  $: activeTarget = previewTarget ?? selectedTarget;
  $: if (viewport) applyDocument(viewport, document);
  $: if (viewport) applySelection(viewport, activeTarget);
  $: if (viewport) viewport.setOptions(options);
  $: error = decoded.error ?? runtimeError;
  $: faceCount = document ? document.triangles.length / 3 : 0;

  function reconcile(doc: MeshDocument | null): void {
    const identity = doc ? JSON.stringify([doc.payload.mesh_id, doc.payload.geometry_revision]) : null;
    if (identity !== currentIdentity) { selectedTarget = null; previewTarget = null; selectedMetric = null; }
    else {
      if (selectedTarget && !doc?.targets.has(selectedTarget)) { selectedTarget = null; selectedMetric = null; }
      if (selectedMetric && doc) {
        const index = doc.payload.metrics.findIndex((metric) => metric.id === selectedMetric?.id && metric.target_id === selectedTarget);
        if (index < 0) { selectedTarget = null; selectedMetric = null; }
        else selectedMetric = { id: selectedMetric.id, index };
      }
      if (previewTarget && !doc?.targets.has(previewTarget)) previewTarget = null;
    }
    currentIdentity = identity;
  }
  function applyDocument(engine: ThreeMeshViewport, doc: MeshDocument | null): void {
    try { engine.setDocument(doc); runtimeError = null; }
    catch (error) {
      engine.setDocument(null);
      runtimeError = error instanceof Error ? error.message : "Failed to build the mesh view.";
    }
  }
  function applySelection(engine: ThreeMeshViewport, id: string | null): void {
    try { engine.setSelection(id); }
    catch (error) { runtimeError = error instanceof Error ? error.message : "Failed to highlight selection."; }
  }
  function selectMetric(metric: Metric, index: number): void {
    if (!document || !metric.target_id) return;
    selectedTarget = selectedTarget === metric.target_id ? null : metric.target_id;
    selectedMetric = selectedTarget ? { id: metric.id, index } : null;
    previewTarget = null;
    onSelection({ mesh_id: document.payload.mesh_id, geometry_revision: document.payload.geometry_revision,
      diagnostic_revision: document.payload.diagnostic_revision, metric_id: metric.id,
      target_id: metric.target_id, metric_index: index, selected: selectedTarget !== null });
  }
  function clearSelection(): void {
    const id = selectedTarget;
    const pinned = selectedMetric;
    selectedTarget = null; previewTarget = null; selectedMetric = null;
    if (!document || !id) return;
    const index = pinned?.index ?? document.payload.metrics.findIndex((m) => m.target_id === id);
    if (index < 0) return;
    onSelection({ mesh_id: document.payload.mesh_id, geometry_revision: document.payload.geometry_revision,
      diagnostic_revision: document.payload.diagnostic_revision, metric_id: document.payload.metrics[index].id,
      target_id: id, metric_index: index, selected: false });
  }
  onMount(() => {
    try {
      const engine = new ThreeMeshViewport(host, (status) => {
        runtimeError = status.state === "ready" ? null : status.message;
      });
      viewport = engine;
      return () => { viewport = null; engine.dispose(); };
    } catch (error) {
      runtimeError = error instanceof Error ? error.message : "WebGL is unavailable in this browser.";
    }
  });
</script>

<div class="mesh-diagnostics">
  <div class="toolbar" aria-label="Visualization controls">
    <label><input type="checkbox" bind:checked={options.ghost} />Ghost shell</label>
    <label title={faceCount > MAX_WIREFRAME_TRIANGLES ? "Wireframe omitted above the configured triangle budget." : "Show triangle tessellation, not CAD edges"}>
      <input type="checkbox" bind:checked={options.wireframe} disabled={faceCount > MAX_WIREFRAME_TRIANGLES} />Wireframe
    </label>
    <label><input type="checkbox" bind:checked={options.xray} />X-ray annotations</label>
    <label title="Optional 1 Hz pulse. Disabled when your system requests reduced motion."><input type="checkbox" bind:checked={options.pulse} />Gentle pulse</label>
    <span class="spacer"></span>
    <button type="button" on:click={() => viewport?.fit()} disabled={!document}>Fit model</button>
    <button type="button" on:click={clearSelection} disabled={!activeTarget}>Clear selection</button>
  </div>
  <div class="split">
    <div class="viewer-column">
      <div class="viewport" bind:this={host}></div>
      <div class="caption">
        {#if document}
          <strong>{document.payload.mesh_id}</strong>
          <span>{document.payload.stage} · {faceCount.toLocaleString()} triangles · units: {document.payload.units}</span>
        {:else}
          <strong>No mesh loaded</strong><span>Run an audit or select an example.</span>
        {/if}
      </div>
      <div class="legend" aria-live="polite">
        {#if activeTarget}<span class="selected">Inspecting: {activeTarget}</span>{/if}
        <span>{options.xray ? "X-ray: annotations may be behind the surface" : "Depth-tested annotations"}</span>
        {#if faceCount > MAX_WIREFRAME_TRIANGLES}<span>Wireframe omitted for this mesh size.</span>{/if}
      </div>
      {#if error}<div class="error" role="alert">{error}</div>{/if}
    </div>
    <MetricsPanel metrics={document?.payload.metrics ?? []} {selectedTarget} {previewTarget}
      onPreview={(target) => { previewTarget = target; }} onSelect={selectMetric} />
  </div>
  {#if document?.payload.notes.length}
    <details class="notes"><summary>Scope and provenance</summary>
      {#each document.payload.notes as note}<p>{note}</p>{/each}
      <p class="revision">Geometry revision: {document.payload.geometry_revision}</p>
    </details>
  {/if}
</div>

<style>
  .mesh-diagnostics { width: 100%; min-width: 0; border: 1px solid #dbe3ec; border-radius: 10px; overflow: hidden;
    background: white; color: #334155; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
  .toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding: 11px 13px; border-bottom: 1px solid #e2e8f0; background: #fff; }
  label { display: inline-flex; gap: 5px; align-items: center; font-size: .72rem; cursor: pointer; }
  input { accent-color: #0e7490; }
  .spacer { flex: 1; }
  button { font: inherit; font-size: .72rem; color: #334155; padding: 5px 9px; border: 1px solid #cbd5e1; border-radius: 5px; background: #fff; cursor: pointer; }
  button:hover { background: #f1f5f9; } button:disabled { opacity: .45; cursor: default; }
  button:focus-visible { outline: 2px solid #0e7490; outline-offset: 2px; }
  .split { display: grid; grid-template-columns: minmax(0, 3fr) minmax(320px, 2fr); height: 520px; }
  .viewer-column { position: relative; min-width: 0; min-height: 0; border-right: 1px solid #e2e8f0; background: #f8fafc; }
  .viewport { position: absolute; inset: 0; }
  .caption { position: absolute; left: 15px; top: 15px; max-width: calc(100% - 30px); pointer-events: none; }
  .caption strong { display: block; font-size: .83rem; }
  .caption span { display: block; margin-top: 4px; font-size: .68rem; color: #64748b; }
  .legend { position: absolute; bottom: 13px; left: 14px; right: 14px; pointer-events: none; display: flex; flex-direction: column; gap: 4px; }
  .legend span { align-self: flex-start; font-size: .66rem; background: #ffffffeb; padding: 4px 7px; border-radius: 4px; }
  .legend .selected { background: #fff7ed; color: #9a3412; }
  .error { position: absolute; inset: auto 14px 70px; padding: 10px; border: 1px solid #fda4af; background: #fff1f2; color: #9f1239; border-radius: 6px; font-size: .8rem; overflow-wrap: anywhere; }
  .notes { border-top: 1px solid #e2e8f0; padding: 10px 14px; font-size: .72rem; color: #64748b; }
  summary { cursor: pointer; } .notes p { margin: 9px 0 0; line-height: 1.5; }
  .revision { overflow-wrap: anywhere; font-family: ui-monospace, monospace; font-size: .66rem; }
  @media (max-width: 850px) {
    .split { grid-template-columns: minmax(0, 1fr); grid-template-rows: 420px 380px; height: auto; }
    .viewer-column { border-right: 0; border-bottom: 1px solid #e2e8f0; }
  }
</style>
