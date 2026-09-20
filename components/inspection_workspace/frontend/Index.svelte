<script lang="ts">
 import {untrack} from 'svelte';
 import {Block} from '@gradio/atoms';
 import {Gradio} from '@gradio/utils';
 import type {Props,Events} from './types';
 import Workspace from './src/Workspace.svelte';
 import {decodeInspectionWire} from './src/core/wire';
 let decoded=$state<unknown>(null);let decodeError=$state<string|null>(null);
 const props=$props();const gradio=untrack(()=>new Gradio<Events,Props>(props));gradio.watch_for_change();
 const wire=$derived(JSON.stringify(gradio.props.value??null));
 $effect(()=>{
   const value=JSON.parse(wire);let current=true;const controller=new AbortController();performance.mark("inspection-delivery");
   decoded=null;decodeError=null;
   decodeInspectionWire(value,undefined,controller.signal).then(result=>{if(current){performance.mark("inspection-decoded");decoded=result;}},error=>{if(current)decodeError=String(error);});
   return ()=>{current=false;controller.abort();};
 });
</script>
<Block visible={gradio.shared.visible} elem_id={gradio.shared.elem_id} elem_classes={gradio.shared.elem_classes} container={false} scale={gradio.shared.scale} min_width={gradio.shared.min_width}>{#if decodeError}<p role="alert">{decodeError}</p>{/if}<Workspace value={decoded}/></Block>
