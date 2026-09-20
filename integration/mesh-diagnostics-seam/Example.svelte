<script lang="ts">
  import MeshInspector from "./src/components/MeshInspector.svelte";
  export let value: unknown = null;
</script>
<MeshInspector {value} />
