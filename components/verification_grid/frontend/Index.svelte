<script lang="ts">
	import { Block } from "@gradio/atoms";
	import { StatusTracker } from "@gradio/statustracker";
	import { Gradio } from "@gradio/utils";
	import type { VerificationEvents, VerificationProps } from "./types";

	const props = $props();
	const gradio = new Gradio<VerificationEvents, VerificationProps>(props);
	gradio.watch_for_change();
	const container = false;
</script>

<Block visible={gradio.shared.visible} elem_id={gradio.shared.elem_id} elem_classes={gradio.shared.elem_classes} {container} scale={gradio.shared.scale} min_width={gradio.shared.min_width}>
	{#if gradio.shared.loading_status}<StatusTracker autoscroll={gradio.shared.autoscroll} i18n={gradio.i18n} {...gradio.shared.loading_status} on_clear_status={() => gradio.dispatch("clear_status", gradio.shared.loading_status)} />{/if}
	<section class="verification" aria-label={gradio.props.value?.title ?? "Verification"}>
		<header><strong>{gradio.props.value?.title ?? "Verification"}</strong><span>{gradio.props.value?.summary ?? "0 / 0"}</span></header>
		<div class="groups">{#each gradio.props.value?.groups ?? [] as group}<section><h3>{group.name}</h3>{#each group.checks as check}<div class="check"><i class={check.state}></i><div><code>{check.name}</code>{#if check.detail}<small>{check.detail}</small>{/if}</div></div>{/each}</section>{/each}</div>
	</section>
</Block>

<style>
	.verification {
		--status-pass: #16803a;
		color: var(--body-text-color);
		font-size: var(--text-sm);
	}
	header { align-items: baseline; display: flex; gap: var(--spacing-md); margin-bottom: var(--spacing-lg); }
	header strong { font-weight: var(--font-weight-bold); }
	header span { color: var(--body-text-color-subdued); font-size: var(--text-xs); }
	.groups { display: grid; gap: var(--spacing-xl); grid-template-columns: repeat(3, minmax(0, 1fr)); }
	h3 { border-bottom: 1px solid var(--border-color-primary); color: var(--body-text-color-subdued); font-size: var(--text-xs); letter-spacing: .06em; margin: 0 0 var(--spacing-sm); padding-bottom: var(--spacing-sm); text-transform: uppercase; }
	.check { align-items: baseline; display: grid; gap: var(--spacing-sm); grid-template-columns: 8px 1fr; padding: 3px 0; }
	i { border-radius: 50%; height: 7px; width: 7px; }
	i.passed { background: var(--status-pass); }
	i.failed { background: var(--color-stop); }
	i.inconclusive { background: var(--color-warning); }
	code { font-size: var(--text-sm); }
	small { color: var(--body-text-color-subdued); display: block; font-size: var(--text-xs); }
	@media (max-width: 720px) { .groups { grid-template-columns: 1fr; } }
</style>
