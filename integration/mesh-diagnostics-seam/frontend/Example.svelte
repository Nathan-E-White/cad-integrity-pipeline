<script lang="ts">
  import type { MeshPayload } from "./src/model/types.ts";
  export let value: MeshPayload | null = null;
  export let type: "gallery" | "table" = "table";
  export let selected = false;
  export let index = 0;
</script>
<div class:selected class:gallery={type === "gallery"} aria-label={`Mesh example ${index + 1}`}>
  <strong>{value?.mesh_id ?? "Empty mesh"}</strong>
  <span>{((value?.triangles.length ?? 0) / 3).toLocaleString()} triangles</span>
</div>
<style>
  div { padding: 8px 12px; font: .8rem system-ui, sans-serif; }
  span { display: block; font-size: .72rem; margin-top: 4px; }
  .selected { outline: 2px solid #0e7490; }.gallery { min-width: 160px; }
</style>
