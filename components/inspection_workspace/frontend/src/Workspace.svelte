<script lang="ts">
 import {parseInspection,type Target} from './core/inspection';
 import {initialState,transition,targetOutsideFilter,type Action,type Pane} from './core/state';
 import GeometryView from './components/GeometryViewport/GeometryViewport.svelte';
 import MetricTable from './components/MetricTable/MetricTable.svelte';
 import EntityTable from './components/EntityTable/EntityTable.svelte';
 import {GeometryViewport} from './render/GeometryViewport';
 import {linkCameras} from '../../../../integration/mesh-diagnostics-seam/src/render/CameraLink';
 import type {DisplayFrame} from '../../../../integration/mesh-diagnostics-seam/src/core/math';
 let {value}:{value:unknown}=$props();
 const parsed=$derived.by(()=>{try{const doc=parseInspection(value);performance.mark("inspection-parsed");return {doc,error:null};}catch(e){return {doc:{schema_version:2 as const,meshes:[]},error:String(e)};}});
 let ui=$state(initialState());let ports=$state<Partial<Record<Pane,GeometryViewport>>>({});
 const active=$derived(parsed.doc.meshes.find(m=>m.stage===ui.active));
 const frame=$derived.by(()=>{const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];for(const m of parsed.doc.meshes)for(let i=0;i<m.positions.length;i++){const k=i%3;min[k]=Math.min(min[k],m.positions[i]);max[k]=Math.max(max[k],m.positions[i]);}if(!Number.isFinite(min[0]))return {origin:[0,0,0],scale:1} as DisplayFrame;const origin=min.map((v,k)=>v/2+max[k]/2) as [number,number,number];return {origin,scale:Math.hypot(...max.map((v,k)=>v/2-min[k]/2))||1};});
 const act=(action:Action)=>ui=transition(ui,action);
 const select=(target:Target)=>act({type:'select',pane:ui.active,target});
 $effect(()=>{parsed.doc;ui=initialState();});
 $effect(()=>{const available=Object.values(ports).filter((v):v is GeometryViewport=>!!v);return linkCameras(available);});
 const muted=(pane:Pane)=>{const mesh=parsed.doc.meshes.find(m=>m.stage===pane);return !!mesh&&!ui.hover[pane]&&targetOutsideFilter(mesh,ui.selections[pane],ui.category,ui.defectsOnly);};
</script>
<section aria-label="Polygonal inspection">
{#if parsed.error}<p role="alert">{parsed.error}</p>{/if}
<div class="toolbar">
 <label>Picking <select aria-label="Picking" value={ui.mode} onchange={e=>act({type:'mode',mode:e.currentTarget.value as typeof ui.mode})}><option value="vertex">Vertex</option><option value="edge">Edge</option><option value="polygonal_face">Face</option></select></label>
 <label>Category <select aria-label="Category" value={ui.category??''} onchange={e=>act({type:'category',category:e.currentTarget.value||null})}><option value="">All categories</option>{#each parsed.doc.meshes[0]?.categories??[] as c}<option value={c.id}>{c.id.replaceAll('_',' ')}</option>{/each}</select></label>
 <label><input type="checkbox" checked={ui.defectsOnly} onchange={e=>act({type:'defects',value:e.currentTarget.checked})}/> Defects only</label>
 <label><input type="checkbox" checked={ui.xray} onchange={e=>act({type:'xray',value:e.currentTarget.checked})}/> X-ray</label>
 <button onclick={()=>ports[ui.active]?.focusSelection()}>Focus selection</button>
</div>
<div class="toolbar">
 <label><input type="checkbox" checked={ui.linkedClipping} onchange={e=>act({type:'link',value:e.currentTarget.checked})}/> Link clipping</label>
 <label><input type="checkbox" checked={ui.clips[ui.active].enabled} onchange={e=>act({type:'clip',pane:ui.active,clip:{...ui.clips[ui.active],enabled:e.currentTarget.checked}})}/> Clip {ui.active}</label>
 <label>Axis <select aria-label="Clipping axis" value={ui.clips[ui.active].axis} onchange={e=>act({type:'clip',pane:ui.active,clip:{...ui.clips[ui.active],axis:Number(e.currentTarget.value) as 0|1|2}})}><option value={0}>X</option><option value={1}>Y</option><option value={2}>Z</option></select></label>
 <label>Offset ({active?.length_unit??''}) <input type="number" value={ui.clips[ui.active].offset} onchange={e=>{const offset=Number(e.currentTarget.value);if(Number.isFinite(offset))act({type:'clip',pane:ui.active,clip:{...ui.clips[ui.active],offset}});}}/></label>
</div>
{#key parsed.doc}
<div class="panes" class:maximized={ui.maximized!==null}>
 {#each ['original','candidate'] as stage}{@const pane=stage as Pane}{@const mesh=parsed.doc.meshes.find(m=>m.stage===pane)}
 <section class="pane" class:active={ui.active===pane} class:concealed={ui.maximized!==null&&ui.maximized!==pane} aria-label={pane==='original'?'Original':'Candidate'}>
 <header><button onclick={()=>act({type:'active',pane})}>{pane==='original'?'Original':'Candidate'}</button><button disabled={!mesh} onclick={()=>act({type:'maximize',pane:ui.maximized===pane?null:pane})}>{ui.maximized===pane?'Restore':'Maximize'}</button></header>
 {#if mesh}<div role="group" onpointerdown={()=>act({type:'active',pane})}><GeometryView {mesh} {frame} {ui} muted={muted(pane)} onpick={target=>act({type:'select',pane,target})} onready={viewport=>{ports={...ports,[pane]:viewport??undefined};}}/></div>{:else}<div class="vacant"></div>{/if}
 </section>{/each}
</div>
{/key}
{#if active}<div class="tables"><MetricTable mesh={active} onselect={select} onhover={target=>act({type:'hover',pane:ui.active,target})} hidden={ui.hiddenCategories} onvisibility={category=>act({type:'visibility',category})}/><div><EntityTable mesh={active} category={ui.category} defectsOnly={ui.defectsOnly} selection={ui.selections[ui.active]} onselect={select} onhover={target=>act({type:'hover',pane:ui.active,target})} onclear={()=>act({type:'select',pane:ui.active,target:null})}/></div></div>{/if}
</section>
<style>input[type=checkbox]{appearance:auto;width:14px;height:14px;accent-color:#475569}.toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin:8px 0;font-size:13px}.toolbar label{display:flex;gap:5px;align-items:center}.toolbar input[type=number]{width:90px}.panes{display:grid;grid-template-columns:1fr 1fr;gap:8px}.panes.maximized{grid-template-columns:1fr}.pane{min-width:0;border:1px solid #94a3b866}.pane.active{border-color:#64748b}.concealed{display:none}.vacant{height:460px}header{display:flex;justify-content:space-between;padding:4px 8px}button{cursor:pointer}.tables{display:grid;align-items:start;grid-template-columns:minmax(200px,1fr) 2fr;gap:24px;margin-top:16px}</style>
