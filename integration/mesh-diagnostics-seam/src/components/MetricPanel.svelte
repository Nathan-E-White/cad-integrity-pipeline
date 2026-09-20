<script lang="ts">
  import { onDestroy } from "svelte";
  import type { MeshPayload, Metric, Selection } from "../core/contracts.js";
  import { type Target, sameTarget, selectionHasGeometry } from "../core/selection.js";
  export let mesh: MeshPayload;
  export let target: Target | null = null;
  export let onPreview: (target: Target | null) => void = () => {};
  export let onSelect: (target: Target | null) => void = () => {};
  let hovered: Target | null = null;
  let focused: Target | null = null;
  let category: Selection | undefined;
  let faceLimit = 50;
  let pathLimit = 50;
  let previousMesh = mesh;
  $: if (mesh !== previousMesh) { previousMesh = mesh; hovered = null; focused = null; category = undefined; faceLimit = 50; pathLimit = 50; }
  $: onPreview(hovered ?? focused);
  $: shownFaces = category?.face_ids.slice(0, faceLimit) ?? [];
  function metricTarget(metric: Metric): Target | null {
    return metric.selection_id ? { meshId: mesh.id, revision: mesh.revision, kind: "selection", id: metric.selection_id } : null;
  }
  function faceTarget(faceId: number): Target { return { meshId: mesh.id, revision: mesh.revision, kind: "face", faceId }; }
  function pathTarget(pathId: string): Target { return { meshId: mesh.id, revision: mesh.revision, kind: "path", pathId }; }
  function chooseMetric(metric: Metric): void {
    category = mesh.selections.find(s => s.id === metric.selection_id); faceLimit = 50; onSelect(metricTarget(metric));
  }
  onDestroy(() => onPreview(null));
</script>
<aside class="audit" aria-label="Diagnostic audit and selection controls">
  <h3>Diagnostic audit</h3>
  <p class="scope">{mesh.provenance}</p>
  <div class="metric-list">
    {#each mesh.metrics as metric (metric.id)}
      {@const selection = mesh.selections.find(s => s.id === metric.selection_id)}
      {#if selectionHasGeometry(selection)}
        <button type="button" class="metric" class:selected={sameTarget(target, metricTarget(metric))}
          aria-pressed={sameTarget(target, metricTarget(metric))} title={metric.scope}
          on:mouseenter={() => hovered = metricTarget(metric)} on:mouseleave={() => hovered = null}
          on:focus={() => focused = metricTarget(metric)} on:blur={() => focused = null}
          on:click={() => chooseMetric(metric)}>
          <span>{metric.label}</span><b>{metric.value ?? "Unknown"}</b><small class={metric.status}>{metric.status}</small>
        </button>
      {:else}
        <div class="metric" title={metric.scope}><span>{metric.label}</span><b>{metric.value ?? "Unknown"}</b><small class={metric.status}>{metric.status}</small></div>
      {/if}
    {:else}<p class="scope">No diagnostics supplied. Absence is not a passing result.</p>{/each}
  </div>
  {#if category && category.face_ids.length}
    <h3>{category.label}</h3><p class="scope">{category.face_ids.length} affected triangles. IDs belong to revision {mesh.revision}.</p>
    <div class="faces">
      {#each shownFaces as id (id)}
        <button type="button" class:selected={sameTarget(target, faceTarget(id))} aria-pressed={sameTarget(target, faceTarget(id))}
          on:mouseenter={() => hovered = faceTarget(id)} on:mouseleave={() => hovered = null}
          on:focus={() => focused = faceTarget(id)} on:blur={() => focused = null} on:click={() => onSelect(faceTarget(id))}>
          Triangle {id}{#if mesh.triangle_source_faces}<small>Source polygon {mesh.triangle_source_faces[id]}</small>{/if}
        </button>
      {/each}
    </div>
    {#if category.face_ids.length > faceLimit && faceLimit < 500}<button class="more" type="button" on:click={() => faceLimit += 50}>Show 50 more</button>{/if}
    {#if category.face_ids.length > 500 && faceLimit >= 500}<p class="scope">Row display capped at 500; the complete selection remains highlighted.</p>{/if}
  {/if}
  {#if mesh.paths.length}
    <h3>Motorcycle / trajectory traces</h3>
    <p class="scope">Imported path state is shown as supplied. Active does not imply cyclic; termination is not automatically a failure.</p>
    {#each mesh.paths.slice(0, pathLimit) as path (path.id)}
      <button type="button" class="path" class:selected={sameTarget(target, pathTarget(path.id))} aria-pressed={sameTarget(target, pathTarget(path.id))}
        on:mouseenter={() => hovered = pathTarget(path.id)} on:mouseleave={() => hovered = null}
        on:focus={() => focused = pathTarget(path.id)} on:blur={() => focused = null} on:click={() => onSelect(pathTarget(path.id))}>
        <strong>{path.label}</strong><span>{path.status} · {path.points.length / 3} points</span>
        <small>{path.provenance}{path.termination_reason ? ` · ${path.termination_reason}` : ""}</small>
      </button>
    {/each}
    {#if mesh.paths.length > pathLimit && pathLimit < 500}<button type="button" class="more" on:click={() => pathLimit += 50}>Show 50 more paths</button>{/if}
  {/if}
</aside>
<style>
  .audit { min-width:0; background:#fff; border:1px solid #d7e0e9; max-height:560px; overflow:auto; }
  h3 { margin:0; padding:13px; font-size:12px; letter-spacing:.04em; color:#334b64; background:#f7f9fc; border-bottom:1px solid #d7e0e9; }
  .scope { padding:0 13px; font-size:11px; line-height:1.5; color:#63748a; }
  .metric { display:grid; grid-template-columns:minmax(0,1fr) auto; align-items:center; gap:4px 10px; width:100%; text-align:left; border:0; border-bottom:1px solid #e4eaf0; padding:11px 13px; background:#fff; color:#34475e; font:inherit; font-size:12px; box-sizing:border-box; }
  b { font-variant-numeric:tabular-nums; overflow-wrap:anywhere; } small { font-size:10px; color:#63748a; } .metric small { grid-column:1 / -1; }
  button { cursor:pointer; } button:hover { background:#f1f6fa; } button:focus-visible { outline:2px solid #2166ac; outline-offset:-3px; }
  .selected { background:#fff2e5 !important; box-shadow:inset 3px 0 #e18020; } .pass { color:#087147; } .fail { color:#ad3345; } .warn { color:#8b591b; }
  .faces { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); padding:8px; gap:5px; }
  .faces button,.more { color:#34506d; padding:8px; background:#fff; border:1px solid #c8d6e4; font:inherit; font-size:11px; text-align:left; }
  .faces small { display:block; } .more { margin:10px; }
  .path { display:grid; gap:5px; width:100%; text-align:left; padding:12px; border:0; border-bottom:1px solid #e4eaf0; background:#fff; color:#34506d; font-size:11px; }
</style>
