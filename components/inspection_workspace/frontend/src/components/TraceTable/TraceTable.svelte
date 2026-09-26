<script lang="ts">
    import {tracePage, type QuadTrace} from '../../core/inspection';
    let {trace, stage, selected, onselect, onhover}: {
        trace: QuadTrace; stage: 'original' | 'candidate'; selected: number | null;
        onselect: (traceId: number | null) => void; onhover: (traceId: number | null) => void;
    } = $props();
    let page = $state(0);
    const paging = $derived(tracePage(trace, page));
    const resetKey = $derived(`${trace.mesh_id}:${trace.revision}`);
    $effect(() => { resetKey; page = 0; });
</script>
<div class="trace-summary" role="status" aria-label="Trace completion">
    <span class:complete={trace.complete}></span>
    {trace.complete ? 'Complete' : `Incomplete · ${trace.stop.replaceAll('_', ' ')}`}
    · {trace.traces.length} traces · {trace.segments.length} segments · {trace.usage.work_steps} work steps
</div>
<table aria-label={`${stage === 'original' ? 'Original' : 'Candidate'} canonical traces`}>
    <thead><tr><th>Trace</th><th>Seed</th><th>Segments</th><th>Termination</th><th>Blocker</th></tr></thead>
    <tbody>{#each paging.rows as row (row.trace_id)}
        <tr class:selected={selected===row.trace_id}>
            <td><button aria-pressed={selected===row.trace_id} onmouseenter={()=>onhover(row.trace_id)} onmouseleave={()=>onhover(null)} onfocus={()=>onhover(row.trace_id)} onblur={()=>onhover(null)} onclick={()=>onselect(selected===row.trace_id?null:row.trace_id)}>T{row.trace_id}</button></td>
            <td>V{row.seed_vertex_id} / E{row.seed_edge_id}</td><td>{row.segment_ids.length}</td>
            <td>{row.termination.replaceAll('_', ' ')}</td><td>{row.blocker_trace_id===null?'—':`T${row.blocker_trace_id}`}</td>
        </tr>
    {/each}</tbody>
</table>
<nav aria-label="Trace pages"><button disabled={paging.current===0} onclick={()=>page=0}>First</button><button disabled={paging.current===0} onclick={()=>page=paging.current-1}>Previous</button><span>{paging.current+1} / {paging.pages} · {trace.traces.length} traces</span><button disabled={paging.current===paging.pages-1} onclick={()=>page=paging.current+1}>Next</button><button disabled={paging.current===paging.pages-1} onclick={()=>page=paging.pages-1}>Last</button></nav>
<style>
    .trace-summary{display:flex;align-items:center;gap:6px;padding:5px 2px;color:#8fa4b5;font:9px "SFMono-Regular",Consolas,monospace;text-transform:uppercase}.trace-summary span{width:7px;height:7px;border-radius:50%;background:#f59e0b}.trace-summary span.complete{background:#34d399}
    table{width:100%;border-collapse:collapse;font:10px "SFMono-Regular",Consolas,monospace}th,td{padding:3px 7px;text-align:left;border-bottom:1px solid #172337}th{color:#7890a4;text-transform:uppercase;letter-spacing:.05em}tr.selected{background:#10283a}
    button{min-height:20px;padding:1px 8px;color:#7dd3fc;background:#0b1422;border:1px solid #26354a;border-radius:0;cursor:pointer}button:hover,button:focus-visible,button[aria-pressed=true]{border-color:#38bdf8;color:#e9f8ff}
    nav{display:flex;gap:5px;align-items:center;margin:6px 0;color:#7890a4;font:10px "SFMono-Regular",Consolas,monospace}
</style>
