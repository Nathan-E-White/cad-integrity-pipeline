<script lang="ts">
  import { untrack } from "svelte";
  import { Block } from "@gradio/atoms";
  import { StatusTracker } from "@gradio/statustracker";
  import { Gradio } from "@gradio/utils";
  import type { InspectorEvents, InspectorProps } from "./types";
  import MeshInspector from "./src/components/MeshInspector.svelte";
  const props = $props();
  const gradio = untrack(() => new Gradio<InspectorEvents, InspectorProps>(props));
  gradio.watch_for_change();
</script>
<Block visible={gradio.shared.visible} elem_id={gradio.shared.elem_id} elem_classes={gradio.shared.elem_classes}
  container={false} scale={gradio.shared.scale} min_width={gradio.shared.min_width}>
  {#if gradio.shared.loading_status}<StatusTracker autoscroll={gradio.shared.autoscroll} i18n={gradio.i18n}
    {...gradio.shared.loading_status} on_clear_status={() => gradio.dispatch("clear_status", gradio.shared.loading_status)} />{/if}
  <MeshInspector value={gradio.props.value} />
</Block>
