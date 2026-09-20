<script lang="ts">
  import { onMount } from "svelte";
  import type { MeshPayload } from "../core/contracts.js";
  import { boundsFor, type DisplayFrame } from "../core/math.js";
  import { defaultState } from "../core/state.js";
  import { resolveTarget, type Target } from "../core/selection.js";
  import { Viewport } from "../render/Viewport.js";
  import InspectorToolbar from "./InspectorToolbar.svelte";
  import MetricPanel from "./MetricPanel.svelte";
  import ScalarLegend from "./ScalarLegend.svelte";

  export let mesh: MeshPayload;
  export let frame: DisplayFrame;
  export let onReady: (viewport: Viewport) => () => void;
  let host: HTMLDivElement;
  let viewport: Viewport | undefined;
  let error: string | null = null;
  let state = defaultState();
  let pinned: Target | null = null;
  let preview: Target | null = null;
  $: bounds = boundsFor([mesh]) ?? { min: [0, 0, 0] as [number, number, number], max: [0, 0, 0] as [number, number, number] };
  $: target = preview ?? pinned;
  $: field = mesh.fields.find(f => f.id === state.fieldId);
  $: viewport?.applyState(state);
  $: viewport?.select(target);
  onMount(() => {
    let disconnect = () => {};
    try {
      viewport = new Viewport(host, { onError: message => error = message, onPick: picked => pinned = picked });
      viewport.setMesh(mesh, frame);
      state = { ...state, clipOffset: bounds.min[0] / 2 + bounds.max[0] / 2 };
      disconnect = onReady(viewport);
    } catch (cause) {
      viewport?.dispose(); viewport = undefined;
      error = cause instanceof Error ? cause.message : String(cause);
    }
    return () => { disconnect(); viewport?.dispose(); viewport = undefined; };
  });
</script>
<section class="pane" aria-label={mesh.label}>
  <h3>{mesh.label}</h3>
  <InspectorToolbar bind:state fields={mesh.fields} {bounds} hasSelection={resolveTarget(mesh, target) !== null}
    onFit={() => viewport?.fit()} onFocus={() => viewport?.focusSelection()} onClear={() => { pinned = null; preview = null; }} />
  <div class="content">
    <div class="display">
      <div class="viewport" bind:this={host}></div>
      {#if error}<p role="alert">{error}</p>{/if}
      {#if field}<div class="legend"><ScalarLegend {field} /></div>{/if}
    </div>
    <MetricPanel {mesh} target={pinned} onPreview={value => preview = value} onSelect={value => pinned = value} />
  </div>
</section>
<style>
  .pane { min-width:0; border:1px solid var(--border-color-primary,#ccd5df); font:12px system-ui,sans-serif; }
  h3 { margin:0; padding:10px; font-size:13px; }
  .content { display:grid; grid-template-columns:minmax(0,3fr) minmax(220px,2fr); }
  .display { position:relative; min-width:0; } .viewport { height:450px; }
  .legend { position:absolute; bottom:10px; left:10px; pointer-events:none; }
  p { padding:10px; color:#b42318; } :global(.content .audit) { max-height:530px; overflow:auto; }
  @media(max-width:700px) { .content { grid-template-columns:1fr; } }
</style>
