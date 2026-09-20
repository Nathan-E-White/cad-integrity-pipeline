<script lang="ts">
  import MeshDiagnosticsView from "../src/components/MeshDiagnosticsView.svelte";
  import fixture from "./fixture.json";
  let value: unknown = null;
  let mounted = true;
  let event = "No metric pinned.";
</script>
<main>
  <header><p>GEOMETRY / INSPECTION</p><h1>Mesh diagnostics workbench</h1>
    <div class="buttons">
      <button on:click={() => { value = fixture; }}>Load synthetic fixture</button>
      <button on:click={() => { value = null; }}>Clear data</button>
      <button on:click={() => { value = { ...fixture, triangles: [-1, 1, 2] }; }}>Invalid input</button>
      <button on:click={() => { mounted = !mounted; }}>{mounted ? "Unmount" : "Remount"} viewport</button>
    </div>
  </header>
  {#if mounted}<MeshDiagnosticsView {value} onSelection={(selection) => { event = JSON.stringify(selection); }} />{/if}
  <p class="event">{event}</p>
</main>
<style>
  :global(body) { margin: 0; background: #f1f5f9; color: #334155; font-family: system-ui, sans-serif; }
  main { max-width: 1380px; margin: 0 auto; padding: 30px 24px; }
  header p { font-size: 11px; letter-spacing: 2px; color: #64748b; } h1 { font-size: 27px; font-weight: 650; margin: 9px 0 20px; }
  .buttons { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 18px; }
  button { border: 1px solid #cbd5e1; border-radius: 5px; background: white; padding: 7px 10px; cursor: pointer; }
  .event { font: 11px ui-monospace, monospace; color: #64748b; overflow-wrap: anywhere; }
</style>
