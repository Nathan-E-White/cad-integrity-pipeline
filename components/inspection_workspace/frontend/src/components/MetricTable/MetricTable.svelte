<script lang="ts">
 import {entityCount,entityKinds,type Mesh,type Target} from '../../core/inspection';
 let {mesh,onselect,onhover,hidden,onvisibility}:{mesh:Mesh;onselect:(target:Target)=>void;onhover:(target:Target|null)=>void;hidden:string[];onvisibility:(id:string)=>void}=$props();
 const target=(id:string):Target=>({meshId:mesh.id,revision:mesh.revision,type:'category',categoryId:id});
 const unique=$derived.by(()=>{let count=0;for(const kind of entityKinds(mesh)){const flags=new Uint8Array(entityCount(mesh,kind));for(const c of mesh.categories)if(c.kind===kind)for(const id of c.entity_ids)if(!flags[id]){flags[id]=1;count++;}}return count;});
</script>
<table aria-label={`${mesh.stage} metrics`}><caption>{mesh.stage==='original'?'Original':'Candidate'} · {mesh.length_unit} · {unique} affected entities</caption>
 <thead><tr><th>Category</th><th>Count</th><th>Overlay</th></tr></thead>
 <tbody>{#each mesh.categories as c}<tr><td><button onmouseenter={()=>onhover(target(c.id))} onmouseleave={()=>onhover(null)} onfocus={()=>onhover(target(c.id))} onblur={()=>onhover(null)} onclick={()=>onselect(target(c.id))}>{c.id.replaceAll('_',' ')}</button></td><td>{c.entity_ids.length}</td><td><input aria-label={`Show ${c.id}`} type="checkbox" checked={!hidden.includes(c.id)} onchange={()=>onvisibility(c.id)}/></td></tr>{/each}</tbody>
</table>
<style>input[type=checkbox]{appearance:auto;width:13px;height:13px;accent-color:var(--cyan,#38bdf8)}table{border-collapse:collapse;width:100%;font-size:11px;color:var(--text,#d9e2ea)}caption{text-align:left;color:var(--muted,#8ca1b4);font:9px "SFMono-Regular",Consolas,monospace;text-transform:uppercase;padding:7px 0;border-bottom:1px solid var(--line,#26354a)}td,th{text-align:left;padding:5px 3px;border-bottom:1px solid var(--line-soft,#172337)}th{color:var(--muted,#7890a4);font-size:9px;text-transform:uppercase;letter-spacing:.06em}td:nth-child(2){font-family:"SFMono-Regular",Consolas,monospace;font-variant-numeric:tabular-nums;text-align:right}button{background:none;border:0;color:inherit;cursor:pointer;text-align:left;padding:0}button:hover,button:focus-visible{color:var(--cyan,#7dd3fc)}</style>
