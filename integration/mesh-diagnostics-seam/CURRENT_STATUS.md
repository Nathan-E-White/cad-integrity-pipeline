# Diagnostics delivery status

September 20, 2026. Start with the repository's current
[integration plan](../../docs/INTEGRATION_PLAN.md) for adoption scope and ownership.
This directory is integration material, not an installed host component.

The original loose delivery places files such as `contracts.py`, `payload.py`,
`gradio_component.py`, and `Index.svelte` directly in this directory. Missing
archive-relative files were subsequently restored under `python/`, `frontend/`,
`gradio_adapter/`, `tests/`, `examples/`, `docs/`, and `tools/`, without overwriting
the loose files. The two layouts have different contracts; restoring files does
not reconcile their packaging, payloads, or renderer ownership.

The supplied `README.md` and `CODEX_INTEGRATION.md` describe the archive-style
package. Their paths and commands must be checked against the selected layout.
The supplied `VERIFICATION.md`, `docs/VERIFICATION.md`, acceptance documents,
and test transcripts record historical delivery evidence, not qualification of
this combined directory or the host application. They remain unchanged, as does
`mesh-diagnostics-seams.tar.gz`.

Agree the adopted package and wire contract before following either delivery's
installation instructions. Host integration and a built Gradio frontend remain
separate work.
