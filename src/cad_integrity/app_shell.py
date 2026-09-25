"""Browser-local application chrome for the installed CAD Integrity lab."""
from __future__ import annotations

from typing import Any

_CHROME_HTML = """
<header class="cad-titlebar" aria-label="CAD Integrity application">
  <div class="cad-brand">CAD Integrity</div>
  <nav class="cad-menu" aria-label="Application menu">
    <button type="button" data-unavailable-action>File</button>
    <button type="button" data-unavailable-action>View</button>
    <button type="button" data-unavailable-action>Selection</button>
    <button type="button" data-unavailable-action>Fields</button>
    <button type="button" data-unavailable-action>Analysis</button>
  </nav>
  <div class="cad-title-context">LOCAL WORKBENCH</div>
  <div id="cad-unavailable-tooltip" class="cad-unavailable-tooltip"
       role="status" aria-label="Unavailable action" aria-live="polite"></div>
</header>
"""


_CHROME_SCRIPT = """
const tooltip = element.querySelector('.cad-unavailable-tooltip');
const actions = Array.from(element.querySelectorAll('[data-unavailable-action]'));
let active = null;
let dismissTimer = null;

const hide = () => {
  if (dismissTimer !== null) window.clearTimeout(dismissTimer);
  dismissTimer = null;
  tooltip.dataset.visible = 'false';
  if (active) active.removeAttribute('aria-describedby');
  active = null;
};

const show = (button) => {
  if (dismissTimer !== null) window.clearTimeout(dismissTimer);
  if (active && active !== button) active.removeAttribute('aria-describedby');
  active = button;
  button.setAttribute('aria-describedby', 'cad-unavailable-tooltip');
  tooltip.dataset.visible = 'false';
  tooltip.textContent = '';
  const bounds = button.getBoundingClientRect();
  window.requestAnimationFrame(() => {
    tooltip.textContent = 'Not ready yet.';
    const width = tooltip.getBoundingClientRect().width || 108;
    const left = Math.min(Math.max(8, bounds.left), window.innerWidth - width - 8);
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${bounds.bottom + 7}px`;
    tooltip.dataset.visible = 'true';
    dismissTimer = window.setTimeout(hide, 1250);
  });
};

for (const action of actions) action.addEventListener('click', () => show(action));
element.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    event.stopPropagation();
    hide();
  }
});
"""


_SHELL_STYLE = """
:root {
  --cad-base: #070b12;
  --cad-surface: #0b111c;
  --cad-raised: #101827;
  --cad-line: #223047;
  --cad-line-soft: #172235;
  --cad-text: #dce6ee;
  --cad-muted: #71849a;
  --cad-cyan: #38bdf8;
}
html, body { background: var(--cad-base) !important; }
body { margin: 0; overflow-x: auto; }
.gradio-container {
  --body-background-fill: var(--cad-base);
  --background-fill-primary: var(--cad-surface);
  --background-fill-secondary: var(--cad-raised);
  --block-background-fill: var(--cad-surface);
  --block-border-color: var(--cad-line);
  --body-text-color: var(--cad-text);
  --body-text-color-subdued: var(--cad-muted);
  --border-color-primary: var(--cad-line);
  --input-background-fill: #0b1422;
  --input-background-fill-focus: #0d1928;
  --input-border-color: var(--cad-line);
  --input-border-color-focus: var(--cad-cyan);
  --input-placeholder-color: #5f7187;
  --button-secondary-background-fill: #0d1624;
  --button-secondary-background-fill-hover: #132033;
  --button-secondary-text-color: var(--cad-text);
  --color-accent-soft: #0c2231;
  --color-stop: #fb4165;
  --color-warning: #fbbf24;
  width: 100% !important;
  max-width: none !important;
  min-width: 760px;
  margin: 0 !important;
  padding: 0 !important;
  background: var(--cad-base) !important;
  color: var(--cad-text) !important;
}
.gradio-container > .main { gap: 0 !important; }
.gradio-container footer { display: none !important; }
#cad-app-shell { gap: 0 !important; background: var(--cad-base); }
.cad-application-chrome { margin: 0 !important; padding: 0 !important; }
.cad-titlebar {
  position: relative;
  display: flex;
  align-items: center;
  min-height: 34px;
  padding: 0 10px;
  border-bottom: 1px solid var(--cad-line);
  background: #060910;
  color: var(--cad-muted);
  font: 11px "SFMono-Regular", Consolas, monospace;
  letter-spacing: .02em;
}
.cad-brand { color: #eef6fa; font-weight: 700; letter-spacing: .045em; }
.cad-menu { display: flex; align-self: stretch; margin-left: 20px; }
.cad-menu button {
  min-width: 0;
  min-height: 0;
  padding: 0 10px;
  border: 0;
  border-bottom: 1px solid transparent;
  border-radius: 0;
  background: transparent;
  color: #8292a6;
  font: inherit;
  cursor: pointer;
}
.cad-menu button:hover { color: #d9e7ef; background: #0b111c; }
.cad-menu button:active { color: var(--cad-cyan); background: #0d1825; }
.cad-menu button:focus-visible {
  color: #e7f7ff;
  outline: 1px solid var(--cad-cyan);
  outline-offset: -3px;
}
.cad-title-context { margin-left: auto; color: #66778d; font-size: 9px; letter-spacing: .08em; }
.cad-unavailable-tooltip {
  position: fixed;
  z-index: 10000;
  width: max-content;
  padding: 4px 7px;
  border: 1px solid #33465f;
  background: rgba(8, 14, 24, .94);
  color: #afbdca;
  box-shadow: 0 8px 22px rgba(0, 0, 0, .35);
  font: 9px "SFMono-Regular", Consolas, monospace;
  letter-spacing: .045em;
  pointer-events: none;
  opacity: 0;
  transform: translateY(-3px);
  transition: opacity 250ms ease, transform 250ms ease;
}
.cad-unavailable-tooltip[data-visible="true"] { opacity: .88; transform: translateY(0); }
#cad-run-setup {
  margin: 0 !important;
  border: 0 !important;
  border-bottom: 1px solid var(--cad-line) !important;
  border-radius: 0 !important;
  background: var(--cad-surface) !important;
}
#cad-run-setup > button,
#cad-run-setup summary {
  min-height: 31px;
  color: #9fb1c2 !important;
  background: #0a101a !important;
  border-radius: 0 !important;
  font: 700 10px "SFMono-Regular", Consolas, monospace !important;
  letter-spacing: .09em;
  text-transform: uppercase;
}
#cad-run-setup .tabs { border-radius: 0 !important; }
#cad-run-setup .tab-nav,
#cad-evidence-dock .tab-nav { background: #0a101a !important; border-bottom: 1px solid var(--cad-line) !important; }
#cad-run-setup button[role="tab"],
#cad-evidence-dock button[role="tab"] {
  min-height: 29px;
  border-radius: 0 !important;
  color: var(--cad-muted) !important;
  font: 10px "SFMono-Regular", Consolas, monospace !important;
  text-transform: uppercase;
}
#cad-run-setup button[role="tab"][aria-selected="true"],
#cad-evidence-dock button[role="tab"][aria-selected="true"] {
  color: var(--cad-cyan) !important;
  border-color: var(--cad-cyan) !important;
}
.cad-setup-panel { padding: 8px 10px !important; background: var(--cad-surface) !important; }
.cad-setup-panel .prose { color: #8293a7 !important; font-size: 11px !important; }
.cad-setup-panel button.primary {
  border-radius: 0 !important;
  border-color: #1689b8 !important;
  background: #0b2a3c !important;
  color: #aee8ff !important;
}
#cad-main-workspace { margin: 0 !important; padding: 0 !important; }
#cad-main-workspace > .wrap { padding: 0 !important; }
#cad-evidence-dock {
  height: 216px;
  min-height: 216px;
  max-height: 216px;
  margin: 0 !important;
  border-top: 1px solid var(--cad-line) !important;
  border-radius: 0 !important;
  background: var(--cad-surface) !important;
  overflow: hidden !important;
}
#cad-evidence-dock .tabitem {
  height: 176px;
  max-height: 176px;
  padding: 8px !important;
  background: var(--cad-surface) !important;
  overflow: auto !important;
}
.cad-result-context, .cad-result-brief { color: #a9b8c5 !important; }
.cad-result-context .prose, .cad-result-brief .prose { font-size: 10px !important; }
.cad-artifact-row { gap: 1px !important; background: var(--cad-line-soft); }
.cad-artifact-row > * { border-radius: 0 !important; background: #0a101a !important; }
@media (max-width: 1050px) {
  .cad-title-context { display: none; }
  .cad-menu { margin-left: 10px; }
  .cad-menu button { padding-inline: 7px; }
}
@media (prefers-reduced-motion: reduce) {
  .cad-unavailable-tooltip { transition: none; }
}
"""


def application_chrome() -> Any:
    """Render semantic menu controls with browser-only unavailable feedback."""
    import gradio as gr

    return gr.HTML(
        value=_CHROME_HTML,
        apply_default_css=False,
        container=False,
        elem_classes=["cad-application-chrome"],
        js_on_load=_CHROME_SCRIPT,
        head=f"<style>{_SHELL_STYLE}</style>",
    )
