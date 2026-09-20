<script lang="ts">
  import { parseDocument } from "../core/contracts.js";
  import { frameFor } from "../core/math.js";
  import { linkCameras } from "../render/CameraLink.js";
  import type { Viewport } from "../render/Viewport.js";
  import MeshPane from "./MeshPane.svelte";
  export let value: unknown = null;

  function prepare(input: unknown) {
    try {
      const document = parseDocument(input);
      const shared = document.linked_views ? frameFor(document.meshes) : null;
      return { document, frames: document.meshes.map(mesh => shared ?? frameFor([mesh])), error: null };
    } catch (cause) {
      return { document: parseDocument(null), frames: [], error: cause instanceof Error ? cause.message : String(cause) };
    }
  }
  $: prepared = prepare(value);
  // Each input document gets an isolated camera registry. Pane teardown unlinks
  // before releasing GPU resources, including when invalid input clears the view.
  function registry(linked: boolean) {
    const ports = new Set<Viewport>();
    let unlink = () => {};
    return (port: Viewport) => {
      unlink(); ports.add(port);
      unlink = linked && ports.size === 2 ? linkCameras([...ports]) : () => {};
      return () => { unlink(); unlink = () => {}; ports.delete(port); };
    };
  }
  $: ready = registry(prepared.document.linked_views);
</script>
<div class="inspector">
  {#if prepared.error}<p role="alert">Invalid mesh document: {prepared.error}</p>
  {:else if prepared.document.meshes.length === 0}<p>No mesh to inspect.</p>
  {:else}
    {#key prepared}
      <div class="panes">
        {#each prepared.document.meshes as mesh, i (mesh.id)}
          <MeshPane {mesh} frame={prepared.frames[i]} onReady={ready} />
        {/each}
      </div>
    {/key}
  {/if}
</div>
<style>
  .inspector { color:var(--body-text-color,#26364a); width:100%; }
  .panes { display:grid; gap:12px; grid-template-columns:repeat(auto-fit,minmax(min(100%,650px),1fr)); }
  p { padding:16px; font:13px system-ui,sans-serif; } [role=alert] { color:#b42318; }
</style>
