<script lang="ts">
  import MeshInspector from "./components/MeshInspector.svelte";
  import fixture from "../../examples/torus-comparison.json";
</script>
<main><p>Illustrative fixture · artificial defects and known reference geometry · not a repair-engine result</p><MeshInspector value={fixture} /></main>
<style>:global(body) { margin:0; background:#edf2f7; } main { max-width:1600px; padding:20px; margin:auto; } p { font:12px system-ui,sans-serif; color:#536a80; }</style>
