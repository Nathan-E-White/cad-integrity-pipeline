<script lang="ts">
  import type { Metric } from "../model/types.ts";
  export let metrics: Metric[] = [];
  export let selectedTarget: string | null = null;
  export let previewTarget: string | null = null;
  export let onPreview: (target: string | null) => void = () => {};
  export let onSelect: (metric: Metric, index: number) => void = () => {};
  const statuses = { info: "Info", pass: "Pass", warn: "Warning", fail: "Fail", not_checked: "Not checked" };
  const numberFormat = new Intl.NumberFormat(undefined, { maximumSignificantDigits: 6 });
  function display(value: Metric["value"]): string {
    return value === null ? "—" : typeof value === "number" ? numberFormat.format(value) : value;
  }
</script>

<section class="audit" aria-label="Mesh diagnostic metrics">
  <header><h3>Diagnostic audit</h3><p>Hover or focus to preview. Click to pin.</p></header>
  <div class="scroll">
    <table>
      <thead><tr><th>Metric</th><th>Value</th><th>Status</th></tr></thead>
      <tbody>
        {#each metrics as metric, index (metric.id)}
          <tr class:active={metric.target_id !== null && (metric.target_id === selectedTarget || metric.target_id === previewTarget)}>
            <td colspan="3">
              {#if metric.target_id}
                <button
                  type="button" class="metric-row" title={metric.description}
                  aria-pressed={metric.target_id === selectedTarget}
                  on:mouseenter={() => onPreview(metric.target_id)}
                  on:mouseleave={() => onPreview(null)}
                  on:focus={() => onPreview(metric.target_id)}
                  on:blur={() => onPreview(null)}
                  on:click={() => onSelect(metric, index)}
                >
                  <span class="label">{metric.label}<span class="hint">Inspect geometry</span></span>
                  <span class="number">{display(metric.value)}</span>
                  <span class="status" data-status={metric.status}>{statuses[metric.status]}</span>
                </button>
              {:else}
                <div class="metric-row" title={metric.description}>
                  <span class="label">{metric.label}</span>
                  <span class="number">{display(metric.value)}</span>
                  <span class="status" data-status={metric.status}>{statuses[metric.status]}</span>
                </div>
              {/if}
              {#if metric.description}<p class="description">{metric.description}</p>{/if}
            </td>
          </tr>
        {:else}
          <tr><td colspan="3" class="empty">No diagnostic telemetry attached.</td></tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>

<style>
  .audit { display: flex; flex-direction: column; min-height: 0; height: 100%; background: #fff; }
  header { padding: 15px 16px 12px; border-bottom: 1px solid #e2e8f0; }
  h3 { margin: 0; font-size: .9rem; font-weight: 650; }
  header p { margin: 5px 0 0; color: #64748b; font-size: .74rem; }
  .scroll { overflow: auto; flex: 1; min-height: 0; }
  table { width: 100%; border-collapse: collapse; table-layout: fixed; }
  thead { font-size: .7rem; color: #64748b; text-transform: uppercase; text-align: left; }
  th { padding: 9px 14px; }
  th:first-child { width: 53%; } th:nth-child(2) { width: 20%; }
  td { padding: 0; border-top: 1px solid #edf0f4; }
  .metric-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 10px; align-items: center;
    width: 100%; box-sizing: border-box; padding: 11px 14px 5px; color: #334155; text-align: left;
    font: inherit; font-size: .79rem; border: 0; background: transparent; }
  button { cursor: pointer; } button:focus-visible { outline: 2px solid #0e7490; outline-offset: -2px; }
  .active { background: #fff7ed; } button:hover { background: #f8fafc; }
  .label { overflow-wrap: anywhere; font-weight: 550; }
  .hint { display: block; font-size: .65rem; color: #0e7490; margin-top: 3px; }
  .number { font: .77rem ui-monospace, SFMono-Regular, monospace; max-width: 110px; overflow-wrap: anywhere; }
  .status { font-size: .65rem; border-radius: 4px; padding: 3px 5px; white-space: nowrap; background: #e2e8f0; color: #334155; }
  .status[data-status="pass"] { background: #d1fae5; color: #065f46; }
  .status[data-status="warn"] { background: #ffedd5; color: #9a3412; }
  .status[data-status="fail"] { background: #ffe4e6; color: #9f1239; }
  .description { padding: 0 14px 10px; margin: 0; font-size: .66rem; line-height: 1.45; color: #64748b; overflow-wrap: anywhere; }
  .empty { padding: 24px 16px; color: #64748b; font-size: .8rem; }
</style>
