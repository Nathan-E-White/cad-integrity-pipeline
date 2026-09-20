<script lang="ts">
  import type { ScalarField } from "../core/contracts.js";
  import { legendGradient, MISSING_COLOR } from "../core/colors.js";
  export let field: ScalarField;
  $: missing = field.values.filter(value => value === null).length;
  $: outside = field.values.filter(value => value !== null && (value < field.domain[0] || value > field.domain[1])).length;
</script>
<div class="scalar-legend" aria-label={`${field.label} color legend`}>
  <strong>{field.label}</strong>
  <div class="gradient" style:background={legendGradient}></div>
  <div class="ends"><span>{field.domain[0].toPrecision(3)}</span><span>{field.domain[1].toPrecision(3)}</span></div>
  <span>{field.better === "neither" ? "Scalar magnitude" : `${field.better} is better`} · {field.unit ?? "dimensionless / unit not supplied"}</span>
  {#if missing}<span><i style:background={MISSING_COLOR}></i> {missing} missing values</span>{/if}
  {#if outside}<span>{outside} values outside display range are color-clamped.</span>{/if}
</div>
<style>
  .scalar-legend { width:210px; padding:10px; background:rgba(255,255,255,.95); border:1px solid #ccd5df; color:#344458; font-size:10px; display:grid; gap:6px; }
  strong { font-size:11px; } .gradient { height:10px; } .ends { display:flex; justify-content:space-between; font-variant-numeric:tabular-nums; }
  i { display:inline-block; width:9px; height:9px; }
</style>
