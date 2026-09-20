<script lang="ts">
  import MeshInspector from "./components/MeshInspector.svelte";
  import fixture from "../examples/torus-comparison.json";
  let value: unknown = fixture;
  let visible = true;
  let mounted = true;
</script>
<main>
  <p>Illustrative fixture · artificial defects and known reference geometry · not a repair-engine result</p>
  <nav aria-label="Fixture controls">
    <button onclick={() => value = fixture}>Load comparison</button>
    <button onclick={() => value = { ...fixture, linked_views: false }}>Independent views</button>
    <button onclick={() => value = { ...fixture, meshes: fixture.meshes.slice(0, 1) }}>Single mesh</button>
    <button onclick={() => value = null}>Clear document</button>
    <button onclick={() => value = { schema_version: 1, meshes: [{}] }}>Invalid document</button>
    <button onclick={() => visible = !visible}>{visible ? "Hide inspector" : "Show inspector"}</button>
    <button onclick={() => mounted = !mounted}>{mounted ? "Unmount inspector" : "Mount inspector"}</button>
  </nav>
  <div hidden={!visible}>{#if mounted}<MeshInspector {value} />{/if}</div>
</main>
<style>
  :global(body) { margin:0; background:#edf2f7; } main { max-width:1800px; padding:20px; margin:auto; }
  p, button { font:12px system-ui,sans-serif; color:#536a80; } nav { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; }
  button { padding:6px 10px; cursor:pointer; } [hidden] { display:none; }
</style>
