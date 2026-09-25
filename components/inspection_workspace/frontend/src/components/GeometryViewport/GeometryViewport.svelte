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
<style>.viewport{height:100%;min-height:420px;min-width:0;width:100%}p{position:absolute;left:8px;bottom:8px;z-index:3;margin:0;color:#fb7185;background:#080e18ee;border:1px solid #7f1d36;padding:4px 6px}</style>
