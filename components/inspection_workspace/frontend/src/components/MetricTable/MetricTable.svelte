<script lang="ts">
 import {entityCount,type Mesh,type Target} from '../../core/inspection';
 let {mesh,onselect,onhover,hidden,onvisibility}:{mesh:Mesh;onselect:(target:Target)=>void;onhover:(target:Target|null)=>void;hidden:string[];onvisibility:(id:string)=>void}=$props();
 const target=(id:string):Target=>({meshId:mesh.id,revision:mesh.revision,type:'category',categoryId:id});
 const unique=$derived.by(()=>{let count=0;for(const kind of ['vertex','edge','polygonal_face'] as const){const flags=new Uint8Array(entityCount(mesh,kind));for(const c of mesh.categories)if(c.kind===kind)for(const id of c.entity_ids)if(!flags[id]){flags[id]=1;count++;}}return count;});
</script>
<table aria-label={`${mesh.stage} metrics`}><caption>{mesh.stage==='original'?'Original':'Candidate'} · {mesh.length_unit} · {unique} affected entities</caption>
 <thead><tr><th>Category</th><th>Count</th><th>Overlay</th></tr></thead>
 <tbody>{#each mesh.categories as c}<tr><td><button onmouseenter={()=>onhover(target(c.id))} onmouseleave={()=>onhover(null)} onfocus={()=>onhover(target(c.id))} onblur={()=>onhover(null)} onclick={()=>onselect(target(c.id))}>{c.id.replaceAll('_',' ')}</button></td><td>{c.entity_ids.length}</td><td><input aria-label={`Show ${c.id}`} type="checkbox" checked={!hidden.includes(c.id)} onchange={()=>onvisibility(c.id)}/></td></tr>{/each}</tbody>
</table>
<style>input[type=checkbox]{appearance:auto;width:14px;height:14px;accent-color:#475569}table{border-collapse:collapse;width:100%;font-size:13px}caption{text-align:left;font-weight:600}td,th{text-align:left;padding:3px 6px;border-bottom:1px solid #94a3b833}button{background:none;border:0;color:inherit;cursor:pointer;text-align:left}</style>
