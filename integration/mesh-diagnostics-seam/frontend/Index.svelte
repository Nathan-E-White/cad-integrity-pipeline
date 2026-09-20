<script lang="ts">
  import MeshDiagnosticsView from "./src/components/MeshDiagnosticsView.svelte";
  import type { MetricSelection } from "./src/model/types.ts";

  // Minimal structural Gradio bridge. The generated host scaffold may wrap this
  // component with its own Block/StatusTracker and supply additional props.
  interface GradioBridge {
    dispatch(event: "select", data: { index: number; value: MetricSelection; selected: boolean }): void;
  }
  export let value: unknown = null;
  export let gradio: GradioBridge | undefined = undefined;
  export let elem_id = "";
  export let elem_classes: string[] = [];
  export let visible: boolean | "hidden" = true;
  export let label: string | null = "Mesh diagnostics";
  export let show_label = true;
  export let scale: number | null = null;
  export let min_width = 320;
  export let mode: "static" | "interactive" = "static";
  export let loading_status: { status?: string; progress?: number } | undefined = undefined;
  $: busy = loading_status?.status === "pending" || loading_status?.status === "generating";
  function selection(event: MetricSelection): void {
    // Never send hover traffic, mutate value, or dispatch change from a backend update.
    gradio?.dispatch("select", { index: event.metric_index, value: event, selected: event.selected });
  }
</script>

<div id={elem_id || undefined} class={elem_classes.join(" ")} hidden={visible !== true}
  style:flex-grow={scale ?? 1} style:min-width={`${min_width}px`} aria-busy={busy} data-mode={mode}>
  {#if label && show_label}<div class="label">{label}</div>{/if}
  {#if busy}<div role="status" class="loading">Updating diagnostics…</div>{/if}
  <MeshDiagnosticsView {value} onSelection={selection} />
</div>
<style>
  .label { font: 600 .9rem system-ui, sans-serif; margin-bottom: 8px; }
  .loading { font: .78rem system-ui, sans-serif; padding: 6px 0; }
</style>
