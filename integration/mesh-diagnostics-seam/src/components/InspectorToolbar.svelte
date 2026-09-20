<script lang="ts">
  import type { ScalarField } from "../core/contracts.js";
  import type { Bounds } from "../core/math.js";
  import type { InspectionState } from "../core/state.js";
  export let state: InspectionState;
  export let fields: ScalarField[] = [];
  export let bounds: Bounds;
  export let hasSelection = false;
  export let onFit: () => void = () => {};
  export let onFocus: () => void = () => {};
  export let onClear: () => void = () => {};
  let oldAxis = state.clipAxis;
  $: low = bounds.min[state.clipAxis];
  $: high = bounds.max[state.clipAxis];
  $: if (oldAxis !== state.clipAxis) {
    oldAxis = state.clipAxis;
    state = { ...state, clipOffset: bounds.min[oldAxis] / 2 + bounds.max[oldAxis] / 2 };
  }
</script>
<div class="toolbar" aria-label="Mesh display controls">
  <label>Surface
    <select bind:value={state.mode}><option value="solid">Shaded</option><option value="ghost">Ghost shell</option><option value="wireframe">Wireframe</option></select>
  </label>
  <label>Face scalar
    <select aria-label="Face scalar" bind:value={state.fieldId}><option value={null}>No heatmap</option>{#each fields as field (field.id)}<option value={field.id}>{field.label}</option>{/each}</select>
  </label>
  <label class="range">Element size: {Math.round(state.shrink * 100)}%
    <input type="range" min="0.1" max="1" step="0.01" bind:value={state.shrink} />
  </label>
  <label class="check"><input type="checkbox" bind:checked={state.wire} /> Facet edges</label>
  <label class="check"><input type="checkbox" bind:checked={state.clipEnabled} /> Plane clip</label>
  <label class="check"><input type="checkbox" bind:checked={state.peelEnabled} /> Radial face filter</label>
  <label class="check"><input type="checkbox" bind:checked={state.isolate} /> Isolate selection</label>
  <label class="check"><input type="checkbox" bind:checked={state.xray} /> X-ray diagnostics</label>
  <label class="check"><input type="checkbox" bind:checked={state.pulse} /> Gentle selection pulse</label>
  <div class="actions"><button type="button" on:click={onFit}>Fit view</button><button type="button" disabled={!hasSelection} on:click={onFocus}>Focus selection</button><button type="button" disabled={!hasSelection} on:click={onClear}>Clear selection</button></div>
  {#if state.clipEnabled}
    <label>Clip axis <select aria-label="Clip axis" bind:value={state.clipAxis}><option value={0}>X</option><option value={1}>Y</option><option value={2}>Z</option></select></label>
    <label class="range wide">Keep coordinate ≤ {state.clipOffset.toPrecision(5)} (source units)
      <input type="range" min={low} max={high > low ? high : low + 1} step={high > low ? (high - low) / 500 : 1} disabled={high === low} bind:value={state.clipOffset} />
    </label>
  {/if}
  {#if state.peelEnabled}
    <label class="range wide">Face-centroid radius cutoff: {Math.round(state.radialFraction * 100)}% of mesh radius
      <input type="range" min="0" max="1" step="0.01" bind:value={state.radialFraction} />
    </label>
  {/if}
</div>
<style>
  .toolbar { display:flex; flex-wrap:wrap; gap:12px; align-items:end; padding:14px; background:#f7f9fc; border-bottom:1px solid #d7e0e9; }
  label { display:grid; gap:5px; font-size:11px; color:#405268; min-width:0; }
  select,button { font:inherit; color:#20334a; background:#fff; border:1px solid #b7c5d5; border-radius:3px; padding:7px; min-height:32px; }
  select { max-width:260px; } .range { width:180px; } .wide { flex:1 1 280px; } .check { display:flex; align-items:center; padding-bottom:7px; }
  input[type="range"] { width:100%; accent-color:#305982; } input[type="checkbox"] { appearance:auto; accent-color:#305982; }
  .actions { display:flex; flex-wrap:wrap; gap:6px; } button { cursor:pointer; } button:disabled { opacity:.5; cursor:default; }
  button:focus-visible,select:focus-visible,input:focus-visible { outline:2px solid #2166ac; outline-offset:3px; }
</style>
