<script lang="ts">
    import {parseInspection, entityKinds, type Target} from './core/inspection';
    import {initialState, transition, targetOutsideFilter, type Action, type Pane} from './core/state';
    import GeometryView from './components/GeometryViewport/GeometryViewport.svelte';
    import MetricTable from './components/MetricTable/MetricTable.svelte';
    import EntityTable from './components/EntityTable/EntityTable.svelte';
    import {GeometryViewport} from './render/GeometryViewport';
    import {linkCameras} from '../../../../integration/mesh-diagnostics-seam/src/render/CameraLink';
    import type {DisplayFrame} from '../../../../integration/mesh-diagnostics-seam/src/core/math';

    let {value}: { value: unknown } = $props();
    const parsed = $derived.by(() => {
        try {
            const doc = parseInspection(value);
            performance.mark('inspection-parsed');
            return {doc, error: null};
        } catch (error) {
            return {doc: {schema_version: 2 as const, meshes: []}, error: String(error)};
        }
    });
    let ui = $state(initialState());
    let ports = $state<Partial<Record<Pane, GeometryViewport>>>({});
    const active = $derived(parsed.doc.meshes.find(mesh => mesh.stage === ui.active));
    const controlMesh = $derived(active ?? parsed.doc.meshes[0]);
    const diagnosticSummary = $derived.by(() => active ? {
        groups: active.categories.filter(category => category.entity_ids.length > 0).length,
        memberships: active.categories.reduce((count, category) => count + category.entity_ids.length, 0),
        displayIssues: active.issues.length
    } : null);
    const frame = $derived.by(() => {
        const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
        for (const mesh of parsed.doc.meshes) for (let i = 0; i < mesh.positions.length; i++) {
            const axis = i % 3;
            min[axis] = Math.min(min[axis], mesh.positions[i]);
            max[axis] = Math.max(max[axis], mesh.positions[i]);
        }
        if (!Number.isFinite(min[0])) return {origin: [0, 0, 0], scale: 1} as DisplayFrame;
        const origin = min.map((item, axis) => item / 2 + max[axis] / 2) as [number, number, number];
        return {origin, scale: Math.hypot(...max.map((item, axis) => item / 2 - min[axis] / 2)) || 1};
    });
    const act = (action: Action) => ui = transition(ui, action);
    const select = (target: Target) => act({type: 'select', pane: ui.active, target});
    const geometryLabel = (pane: Pane) => pane === 'original' ? 'Original geometry' : 'Candidate geometry';
    $effect(() => {
        const first = parsed.doc.meshes[0];
        ui = {...initialState(first?.face_kind, parsed.doc.meshes.length === 2), active: first?.stage ?? 'original'};
    });
    $effect(() => {
        const available = Object.values(ports).filter((viewport): viewport is GeometryViewport => !!viewport);
        if (!ui.linkedCameras) {
            for (const viewport of available) viewport.onPose = null;
            return;
        }
        return linkCameras(available);
    });
    const muted = (pane: Pane) => {
        const mesh = parsed.doc.meshes.find(candidate => candidate.stage === pane);
        return !!mesh && !ui.hover[pane] && targetOutsideFilter(mesh, ui.selections[pane], ui.category, ui.defectsOnly);
    };
</script>

<section class="workspace" aria-label={parsed.doc.schema_version===3?'Native inspection':'Polygonal inspection'}>
    {#if parsed.error}<p role="alert">{parsed.error}</p>{/if}
    <header class="command-bar">
        <div class="identity">
            <strong>Topology workbench</strong>
            <span>{parsed.doc.schema_version === 3 ? 'Native inspection' : 'Polygonal inspection'}</span>
            <span class="geometry-identity">{geometryLabel(ui.active)}</span>
        </div>
        <div class="command-group">
            <label>Pick <select aria-label="Picking" value={ui.mode}
                               onchange={event=>act({type:'mode',mode:event.currentTarget.value as typeof ui.mode})}>
                {#each controlMesh ? entityKinds(controlMesh) : parsed.doc.schema_version === 3 ? ['native_face'] : ['polygonal_face'] as kind}
                    <option value={kind}>{kind === 'native_face' ? 'Native face' : kind === 'polygonal_face' ? 'Face' : kind === 'edge' ? 'Edge' : 'Vertex'}</option>
                {/each}
            </select></label>
            <button class:engaged={ui.linkedCameras} aria-pressed={ui.linkedCameras}
                    onclick={()=>act({type:'cameraLink',value:!ui.linkedCameras})}>
                {ui.linkedCameras ? 'Cameras linked' : 'Independent cameras'}
            </button>
            <button aria-pressed={ui.compactDocks} onclick={()=>act({type:'docks',compact:!ui.compactDocks})}>
                {ui.compactDocks ? 'Expand docks' : 'Compact docks'}
            </button>
            <label><input type="checkbox" checked={ui.linkedClipping}
                          onchange={event=>act({type:'link',value:event.currentTarget.checked})}/> Linked clip</label>
            {#if diagnosticSummary}
                <span class="command-status">{diagnosticSummary.memberships} memberships · {diagnosticSummary.displayIssues} display issues</span>
            {/if}
        </div>
    </header>

    <div class="workspace-grid" class:compact={ui.compactDocks}>
        <section class="model-dock" aria-label="Model and entities">
            <h2>Model / entities</h2>
            <div class="dock-badge">M</div>
            <div class="model-name" role="status" aria-label="Active geometry identity">{geometryLabel(ui.active)}{active ? '' : ' unavailable'}</div>
            {#each ['original', 'candidate'] as stage}
                {@const pane = stage as Pane}
                {@const mesh = parsed.doc.meshes.find(candidate => candidate.stage === pane)}
                <div class="tree-row" class:unavailable={!mesh}>
                    <span class="status-dot" class:ready={!!mesh}></span>
                    <span>{geometryLabel(pane)}</span>
                    <span>{mesh ? 'available' : 'unavailable'}</span>
                </div>
            {/each}
            {#if active}
                <dl>
                    {#if active.face_kind === 'native_face'}
                        <dt>Display vertices</dt><dd>{active.positions.length / 3}</dd>
                        <dt>Native faces</dt><dd>{active.face_count}</dd>
                    {:else}
                        <dt>Vertices</dt><dd>{active.positions.length / 3}</dd>
                        <dt>Edges</dt><dd>{active.edges.length / 2}</dd>
                        <dt>Faces</dt><dd>{active.face_count}</dd>
                    {/if}
                    <dt>Frame</dt><dd>{active.frame_id}</dd>
                    <dt>Units</dt><dd>{active.length_unit}</dd>
                </dl>
            {/if}
            <div class="selection-readout">
                <span>Active stage</span><strong>{ui.active}</strong>
                <span>Selection</span><strong>{ui.selections[ui.active] ? 'pinned' : 'clear'}</strong>
            </div>
        </section>

        <section class="viewport-deck" aria-label="Inspection viewport">
            {#key parsed.doc}
                <div class="panes" class:maximized={ui.maximized!==null}>
                    {#each ['original', 'candidate'] as stage}
                        {@const pane = stage as Pane}
                        {@const mesh = parsed.doc.meshes.find(candidate => candidate.stage === pane)}
                        <section class="pane" class:active={ui.active===pane}
                                 class:concealed={ui.maximized!==null&&ui.maximized!==pane}
                                 aria-label={pane==='original'?'Original':'Candidate'}>
                            <header class="pane-header">
                                <button class="stage-button" onclick={()=>act({type:'active',pane})}>{pane === 'original' ? 'Original' : 'Candidate'}</button>
                                <span>{mesh ? `${mesh.face_count} faces` : `${geometryLabel(pane)} unavailable`}</span>
                                <button disabled={!mesh}
                                        onclick={()=>act({type:'maximize',pane:ui.maximized===pane?null:pane})}>{ui.maximized === pane ? 'Restore' : 'Maximize'}</button>
                            </header>
                            {#if mesh}
                                <div class="viewport-shell" role="group" onpointerdown={()=>act({type:'active',pane})}>
                                    <GeometryView {mesh} {frame} {ui} muted={muted(pane)}
                                                  onpick={target=>act({type:'select',pane,target})}
                                                  onready={viewport=>{ports={...ports,[pane]:viewport??undefined};}}/>
                                    {#if ui.active===pane}
                                        <div class="view-hud">
                                            <button onclick={()=>ports[pane]?.focusSelection()}>Focus selection</button>
                                            <label><input type="checkbox" checked={ui.xray}
                                                          onchange={event=>act({type:'xray',value:event.currentTarget.checked})}/> X-ray</label>
                                            <label><input type="checkbox" checked={ui.clips[pane].enabled}
                                                          onchange={event=>act({type:'clip',pane,clip:{...ui.clips[pane],enabled:event.currentTarget.checked}})}/> Clip {pane}</label>
                                            <label>Axis <select aria-label="Clipping axis" value={ui.clips[pane].axis}
                                                                onchange={event=>act({type:'clip',pane,clip:{...ui.clips[pane],axis:Number(event.currentTarget.value) as 0|1|2}})}>
                                                <option value={0}>X</option><option value={1}>Y</option><option value={2}>Z</option>
                                            </select></label>
                                            <label>Offset <input aria-label={`Clipping offset ${pane}`} type="number" value={ui.clips[pane].offset}
                                                                 onchange={event=>{const offset=Number(event.currentTarget.value);if(Number.isFinite(offset))act({type:'clip',pane,clip:{...ui.clips[pane],offset}});}}/></label>
                                        </div>
                                    {/if}
                                    <div class="gnomon-label">Global XYZ</div>
                                    <div class="view-telemetry">{mesh.length_unit} · {ui.linkedCameras ? 'linked camera' : 'independent orbit'}</div>
                                </div>
                            {:else}
                                <div class="vacant"><span>{geometryLabel(pane)} unavailable</span></div>
                            {/if}
                        </section>
                    {/each}
                </div>
            {/key}
        </section>

        <section class="validation-dock" aria-label="Validation and diagnostics">
            <h2>Validation / diagnostics</h2>
            <div class="dock-badge">V</div>
            {#if diagnosticSummary}
                <div class="validation-summary">
                    <span><strong>{diagnosticSummary.groups}</strong> defect groups</span>
                    <span><strong>{diagnosticSummary.memberships}</strong> memberships</span>
                    <span class:attention={diagnosticSummary.displayIssues>0}><strong>{diagnosticSummary.displayIssues}</strong> display issues</span>
                </div>
            {/if}
            {#if parsed.doc.schema_version !== 3}
                <label>Category <select aria-label="Category" value={ui.category??''}
                                        onchange={event=>act({type:'category',category:event.currentTarget.value||null})}>
                    <option value="">All categories</option>
                    {#each parsed.doc.meshes[0]?.categories ?? [] as category}
                        <option value={category.id}>{category.id.replaceAll('_',' ')}</option>
                    {/each}
                </select></label>
                <label><input type="checkbox" checked={ui.defectsOnly}
                              onchange={event=>act({type:'defects',value:event.currentTarget.checked})}/> Defects only</label>
            {/if}
            {#if active?.face_kind !== 'native_face' && active}
                <MetricTable mesh={active} onselect={select} onhover={target=>act({type:'hover',pane:ui.active,target})}
                             hidden={ui.hiddenCategories} onvisibility={category=>act({type:'visibility',category})}/>
            {:else if active}
                <div class="native-summary"><span class="status-dot ready"></span>{active.face_count} native faces available</div>
            {/if}
        </section>

        <section class="instrument-dock" aria-label="Analytical instruments">
            <header><h2>Entity register</h2><span>{active ? `${active.stage} · ${active.length_unit}` : 'No active result'}</span></header>
            {#if active}
                <EntityTable mesh={active} category={ui.category} defectsOnly={ui.defectsOnly}
                             selection={ui.selections[ui.active]} onselect={select}
                             onhover={target=>act({type:'hover',pane:ui.active,target})}
                             onclear={()=>act({type:'select',pane:ui.active,target:null})}/>
            {/if}
        </section>
    </div>
</section>

<style>
    :global(.workspace *) { box-sizing: border-box; }
    .workspace {
        --base: #080d15; --surface: #0c1320; --line: #26354a; --line-soft: #172337;
        --text: #d9e2ea; --muted: #7890a4; --cyan: #38bdf8; --green: #34d399;
        color: var(--text); background: var(--base); border: 1px solid var(--line); min-width: 760px;
        font: 12px Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    input[type=checkbox] { appearance: auto; width: 14px; height: 14px; accent-color: var(--cyan); }
    .command-bar { display: flex; justify-content: space-between; align-items: center; gap: 16px; min-height: 38px; padding: 5px 8px; border-bottom: 1px solid var(--line); background: #0a101b; }
    .identity, .command-group, .view-hud, .pane-header, .instrument-dock > header { display: flex; align-items: center; gap: 8px; }
    .identity strong { letter-spacing: .08em; text-transform: uppercase; }
    .identity span { color: var(--muted); }
    .geometry-identity, .command-status, .view-telemetry, .tree-row span:last-child, dl, .selection-readout, .instrument-dock > header span { font-family: "SFMono-Regular", Consolas, monospace; font-variant-numeric: tabular-nums; }
    .command-status { color: var(--muted); font-size: 9px; text-transform: uppercase; }
    button, select, input[type=number] { color: var(--text); background: #0b1422; border: 1px solid var(--line); border-radius: 0; min-height: 24px; }
    button { cursor: pointer; text-transform: uppercase; font-size: 10px; letter-spacing: .04em; }
    button:hover, button:focus-visible, button.engaged { border-color: var(--cyan); color: #e9f8ff; }
    button:disabled { cursor: default; opacity: .35; }
    label { display: flex; align-items: center; gap: 5px; color: var(--muted); }
    .workspace-grid { display: grid; grid-template-columns: 210px minmax(420px, 1fr) 270px; grid-template-rows: minmax(430px, calc(100vh - 565px)) 160px; grid-template-areas: "model viewport validation" "model instruments instruments"; min-height: 590px; }
    .workspace-grid.compact { grid-template-columns: 48px minmax(420px, 1fr) 48px; }
    .model-dock, .validation-dock, .instrument-dock { background: var(--surface); }
    .model-dock { grid-area: model; border-right: 1px solid var(--line); }
    .viewport-deck { grid-area: viewport; min-width: 0; }
    .validation-dock { grid-area: validation; border-left: 1px solid var(--line); overflow: auto; }
    .instrument-dock { grid-area: instruments; border-top: 1px solid var(--line); overflow: auto; }
    .model-dock, .validation-dock { padding: 8px; }
    .instrument-dock { padding: 6px 8px; }
    h2 { margin: 0 0 8px; color: #9eb1c2; font-size: 10px; letter-spacing: .12em; text-transform: uppercase; }
    .dock-badge { display: none; place-items: center; width: 28px; height: 28px; margin: 8px auto; color: var(--cyan); border: 1px solid var(--line); font: 11px "SFMono-Regular", Consolas, monospace; }
    .compact .model-dock, .compact .validation-dock { padding-inline: 5px; overflow: hidden; }
    .compact .model-dock > :not(h2):not(.dock-badge), .compact .validation-dock > :not(h2):not(.dock-badge) { display: none; }
    .compact .model-dock h2, .compact .validation-dock h2 { writing-mode: vertical-rl; margin: 0 auto; padding-top: 4px; white-space: nowrap; }
    .compact .dock-badge { display: grid; }
    .model-name { padding: 7px 5px; border-block: 1px solid var(--line-soft); font-weight: 600; }
    .tree-row { display: grid; grid-template-columns: 10px 1fr auto; gap: 5px; padding: 6px 4px; border-bottom: 1px solid var(--line-soft); text-transform: capitalize; }
    .tree-row.unavailable { opacity: .45; }
    .status-dot { width: 7px; height: 7px; margin-top: 4px; border: 1px solid var(--muted); border-radius: 50%; }
    .status-dot.ready { border-color: var(--green); box-shadow: inset 0 0 0 2px var(--surface); background: var(--green); }
    dl { display: grid; grid-template-columns: 1fr auto; gap: 6px; margin: 14px 4px; }
    dt { color: var(--muted); } dd { margin: 0; text-align: right; }
    .selection-readout { display: grid; grid-template-columns: 1fr auto; gap: 6px; padding: 8px 4px; border-top: 1px solid var(--line); }
    .selection-readout span { color: var(--muted); }
    .selection-readout strong { text-transform: uppercase; font-size: 10px; }
    .panes { height: 100%; display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: var(--line); }
    .panes.maximized { grid-template-columns: 1fr; }
    .pane { min-width: 0; background: var(--base); border-top: 2px solid transparent; overflow: hidden; }
    .pane.active { border-top-color: var(--cyan); }
    .pane-header { height: 30px; padding: 3px 6px; border-bottom: 1px solid var(--line); background: #0b111d; }
    .pane-header span { flex: 1; color: var(--muted); font: 10px "SFMono-Regular", Consolas, monospace; text-transform: uppercase; }
    .stage-button { border: 0; padding-inline: 2px; color: #dce8f1; }
    .viewport-shell { position: relative; height: calc(100% - 30px); min-height: 390px; background: radial-gradient(circle at 52% 45%, #182638 0, #0e1826 43%, #070c14 100%); }
    .view-hud { position: absolute; z-index: 2; top: 7px; right: 7px; padding: 4px; background: #080e18f2; border: 1px solid var(--line); flex-wrap: wrap; justify-content: flex-end; max-width: calc(100% - 14px); }
    .view-hud input[type=number] { width: 62px; }
    .gnomon-label { position: absolute; z-index: 2; right: 10px; bottom: 73px; color: #7890a4; font: 8px "SFMono-Regular", Consolas, monospace; text-transform: uppercase; }
    .view-telemetry { position: absolute; z-index: 2; right: 8px; bottom: 6px; padding: 3px 5px; color: #8fa4b5; background: #080e18eb; text-transform: uppercase; font-size: 9px; }
    .concealed { display: none; }
    .vacant { height: calc(100% - 30px); min-height: 390px; display: grid; place-items: center; color: var(--muted); background: radial-gradient(circle at center, #101a28, #080d15 70%); text-transform: uppercase; letter-spacing: .08em; }
    .validation-dock > label { margin: 6px 0; }
    .validation-summary { display: grid; grid-template-columns: 1fr; gap: 4px; padding: 5px 0 8px; border-bottom: 1px solid var(--line); color: var(--muted); font: 9px "SFMono-Regular", Consolas, monospace; text-transform: uppercase; }
    .validation-summary span { display: flex; justify-content: space-between; }
    .validation-summary strong { color: var(--text); }
    .validation-summary .attention, .validation-summary .attention strong { color: #fb7185; }
    .native-summary { display: flex; gap: 6px; padding: 8px 3px; border-block: 1px solid var(--line-soft); }
    .instrument-dock > header { justify-content: space-between; border-bottom: 1px solid var(--line-soft); }
    .instrument-dock > header h2 { margin: 0; }
    @media (max-width: 1050px) {
        .workspace { min-width: 680px; }
        .workspace-grid { grid-template-columns: 150px minmax(360px, 1fr) 210px; }
        .identity span:not(.geometry-identity) { display: none; }
    }
</style>
