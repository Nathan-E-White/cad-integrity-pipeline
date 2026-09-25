<script lang="ts">
 import {targetOutsideFilter} from '../../core/state';
 import {entityCount,entityTarget,entityKinds,type Mesh,type Kind,type Target} from '../../core/inspection';
 let {mesh,category,defectsOnly,selection,onselect,onhover,onclear}:{mesh:Mesh;category:string|null;defectsOnly:boolean;selection:Target|null;onselect:(target:Target)=>void;onhover:(target:Target|null)=>void;onclear:()=>void}=$props();
 let kind=$state<Kind>('polygonal_face');let page=$state(0);const pageSize=50;
 const selectedCategory=$derived(mesh.categories.find(c=>c.id===category));
 const effectiveKind=$derived(selectedCategory?.kind??(entityKinds(mesh).includes(kind)?kind:mesh.face_kind));
 const ids=$derived.by(()=>{
   if(selectedCategory)return selectedCategory.entity_ids;
   if(defectsOnly)return [...new Set(mesh.categories.filter(c=>c.kind===effectiveKind).flatMap(c=>c.entity_ids))].sort((a,b)=>a-b);
   return null;
 });
 const count=$derived(ids?.length??entityCount(mesh,effectiveKind));
 const pages=$derived(Math.max(1,Math.ceil(count/pageSize)));
 const current=$derived(Math.min(page,pages-1));
 const rows=$derived(Array.from({length:Math.min(pageSize,Math.max(0,count-current*pageSize))},(_,i)=>ids?.[current*pageSize+i]??current*pageSize+i));
 const label=(target:Target)=>target.type==='category'?target.categoryId.replaceAll('_',' '):`${target.kind==='native_face'?'Native face':target.kind==='polygonal_face'?'Face':target.kind==='edge'?'Edge':'Vertex'} ${target.entityId}`;
 const muted=$derived(targetOutsideFilter(mesh,selection,category,defectsOnly));
 const resetKey=$derived(JSON.stringify([mesh.id,mesh.revision,category,defectsOnly,kind]));
 $effect(()=>{resetKey;page=0;});
</script>
{#if selection}<div class:muted role="status" aria-label="Selection">{label(selection)} <button onclick={onclear}>Clear selection</button></div>{/if}
<label>Entity kind <select aria-label="Entity kind" value={effectiveKind} onchange={event=>kind=event.currentTarget.value as Kind} disabled={!!selectedCategory}>{#each entityKinds(mesh) as option}<option value={option}>{option==='native_face'?'Native face':option==='polygonal_face'?'Face':option==='edge'?'Edge':'Vertex'}</option>{/each}</select></label>
<table aria-label={`${mesh.stage==='original'?'Original':'Candidate'} entities`}><thead><tr><th>ID</th><th>{mesh.face_kind==='native_face'?'Display':'Categories / display'}</th></tr></thead><tbody>
{#each rows as id (id)}<tr><td><button onmouseenter={()=>onhover(entityTarget(mesh,effectiveKind,id))} onmouseleave={()=>onhover(null)} onfocus={()=>onhover(entityTarget(mesh,effectiveKind,id))} onblur={()=>onhover(null)} onclick={()=>onselect(entityTarget(mesh,effectiveKind,id))}>{label(entityTarget(mesh,effectiveKind,id))}</button></td><td>{mesh.categories.filter(c=>c.kind===effectiveKind&&c.entity_ids.includes(id)).map(c=>c.id.replaceAll('_',' ')).join(', ')}{#if effectiveKind===mesh.face_kind&&mesh.issues.some(i=>i.face_id===id)} · Interior unavailable{/if}</td></tr>{/each}
</tbody></table>
<nav aria-label="Entity pages"><button disabled={current===0} onclick={()=>page=0}>First</button><button disabled={current===0} onclick={()=>page=current-1}>Previous</button><span>{current+1} / {pages} · {count} entities</span><button disabled={current===pages-1} onclick={()=>page=current+1}>Next</button><button disabled={current===pages-1} onclick={()=>page=pages-1}>Last</button></nav>
<style>table{width:100%;border-collapse:collapse;font-size:11px;color:var(--text,#d9e2ea)}td,th{text-align:left;padding:4px 6px;border-bottom:1px solid var(--line-soft,#172337)}th{color:var(--muted,#7890a4);font-size:9px;text-transform:uppercase;letter-spacing:.06em}.muted{opacity:.5}button,select{color:var(--text,#d9e2ea);background:#0b1422;border:1px solid var(--line,#26354a);border-radius:0;min-height:23px;cursor:pointer;font-size:10px}td button{background:none;border:0;padding:0;color:#c9d7e2;text-transform:none}td button:hover,td button:focus-visible{color:var(--cyan,#7dd3fc)}nav{display:flex;gap:5px;align-items:center;margin:6px 0;color:var(--muted,#7890a4);font:10px "SFMono-Regular",Consolas,monospace}label{display:flex;gap:6px;align-items:center;margin:6px 0;color:var(--muted,#7890a4);font-size:10px}[role=status]{display:flex;justify-content:space-between;align-items:center;padding:5px 6px;border-left:2px solid var(--cyan,#38bdf8);background:#111b2a;color:var(--text,#d9e2ea);font:10px "SFMono-Regular",Consolas,monospace}</style>
