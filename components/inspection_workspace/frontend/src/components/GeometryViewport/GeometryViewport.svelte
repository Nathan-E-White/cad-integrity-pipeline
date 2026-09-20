<script lang="ts">
 import {onMount} from 'svelte';
 import {GeometryViewport} from '../../render/GeometryViewport';
 import type {Mesh,Target} from '../../core/inspection';
 import type {WorkspaceState} from '../../core/state';
 import type {DisplayFrame} from '../../../../../../integration/mesh-diagnostics-seam/src/core/math';
 let {mesh,frame,ui,muted,onpick,onready}:{mesh:Mesh;frame:DisplayFrame;ui:WorkspaceState;muted:boolean;onpick:(target:Target|null)=>void;onready:(viewport:GeometryViewport|null)=>void}=$props();
 let host:HTMLDivElement;let viewport:GeometryViewport|undefined;let error=$state<string|null>(null);
 onMount(()=>{try{viewport=new GeometryViewport(host,mesh,frame,onpick,message=>error=message);viewport.update(ui,muted);onready(viewport);}catch(e){error=String(e);viewport?.dispose();}return()=>{onready(null);viewport?.dispose();};});
 $effect(()=>{viewport?.update(ui,muted);});
</script>
<div class="viewport" bind:this={host}></div>
{#if error}<p role="alert">{error}</p>{/if}
<style>.viewport{height:460px;min-width:0;width:100%}p{color:#b42318}</style>
