<script lang="ts">
	import { Block } from "@gradio/atoms";
	import { StatusTracker } from "@gradio/statustracker";
	import { Gradio } from "@gradio/utils";
	import type { DeltaAuditEvents, DeltaAuditProps, AuditCategory } from "./types";

	const props = $props();
	const gradio = new Gradio<DeltaAuditEvents, DeltaAuditProps>(props);
	gradio.watch_for_change();
	const container = false;
	const labels: Record<AuditCategory, string> = {
		geometry: "Geometry",
		topology: "Topology",
		execution: "Execution"
	};

	function rows(category: AuditCategory) {
		return (gradio.props.value?.rows ?? []).filter((row) => row.category === category);
	}
</script>

<Block
	visible={gradio.shared.visible}
	elem_id={gradio.shared.elem_id}
	elem_classes={gradio.shared.elem_classes}
	{container}
	scale={gradio.shared.scale}
	min_width={gradio.shared.min_width}
>
	{#if gradio.shared.loading_status}
		<StatusTracker
			autoscroll={gradio.shared.autoscroll}
			i18n={gradio.i18n}
			{...gradio.shared.loading_status}
			on_clear_status={() => gradio.dispatch("clear_status", gradio.shared.loading_status)}
		/>
	{/if}
	<section class="audit" aria-label={gradio.props.value?.title ?? "Topological delta audit"}>
		<header>{gradio.props.value?.title ?? "Topological & Geometric Delta Audit"}</header>
		<div class="scroll"><table>
			<thead><tr><th>Category</th><th>Entity / invariant</th><th>Before</th><th>After</th><th>Δ</th></tr></thead>
			<tbody>{#each (["geometry", "topology", "execution"] as AuditCategory[]) as category}
				{#each rows(category) as row, index}
					<tr class:group-start={index === 0} class:execution={category === "execution"}>
						{#if index === 0}<td class="category" rowspan={rows(category).length}>{labels[category]}</td>{/if}
						<td class="entity">{row.entity}</td><td>{row.before}</td><td>{row.after}</td><td class="delta">{row.delta}</td>
					</tr>
				{/each}
			{/each}</tbody>
		</table></div>
	</section>
</Block>

<style>
	.audit { color: var(--body-text-color); font-size: var(--text-sm); }
	header { border-bottom: 2px solid var(--body-text-color); font-weight: var(--font-weight-bold); padding: 0 0 var(--spacing-lg); }
	.scroll { overflow-x: auto; } table { border-collapse: collapse; min-width: 690px; width: 100%; } th { border-bottom: 1px solid var(--body-text-color); color: var(--body-text-color-subdued); font-size: var(--text-xs); letter-spacing: .05em; padding: var(--spacing-md); text-align: left; text-transform: uppercase; } td { border-bottom: 1px solid var(--border-color-primary); font-variant-numeric: tabular-nums; padding: var(--spacing-md); } td:not(.category):not(.entity) { text-align: right; white-space: nowrap; } .category { color: var(--body-text-color-subdued); font-size: var(--text-xs); font-weight: var(--font-weight-bold); letter-spacing: .05em; text-transform: uppercase; vertical-align: top; } .entity { font-weight: var(--font-weight-semibold); } .delta { font-weight: var(--font-weight-bold); } .group-start td { border-top: 1px solid var(--body-text-color); } .execution td { background: var(--background-fill-secondary); }
</style>
