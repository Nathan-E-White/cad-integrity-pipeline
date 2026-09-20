# Diagnostics delivery status

September 20, 2026. Start with the repository's current
[integration plan](../../docs/INTEGRATION_PLAN.md) for adoption scope and ownership.
This directory is integration material, not an installed host component.

The original loose delivery placed files such as `contracts.py`, `payload.py`,
`gradio_component.py`, and `Index.svelte` directly in this directory (their current Python locations are listed below). Missing
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

## Runnable loose Python package

The formerly flat Python modules now live in `python/cad_mesh_inspector/`.
The distribution `cad-mesh-inspector` installs this package only; the restored
`python/mesh_diagnostics/` remains a separate reference implementation.
Use `from cad_mesh_inspector import inspect_triangles` or import submodules such
as `cad_mesh_inspector.adapters`. The optional Gradio backend is
`cad_mesh_inspector.gradio_component`; packaging it does not build a frontend.

From this directory, with the host and test/Gradio dependencies installed:

```sh
python -m pip install --no-deps -e .
python -m pytest tests_loose -q
python make_fixture.py
```

Pytest also supports a source checkout through the configured `python` path.
The default test target is `tests_loose`; restored archive tests remain in `tests`
and must be requested separately. Host adapter tests require the host package or
`CAD_INTEGRITY_SOURCE_DIR` pointing to its `src/cad_integrity` directory.

`test_io.py` remains an unfinished delivery specification outside that target:
its `cad_mesh_inspector.npz_io.load_numeric_npz` implementation was never supplied.
The package no longer advertises that missing function. Archive NPZ behavior is
not substituted for it. LE-4 through LE-6 are covered by the loose contract and payload tests.

## Source-face ID validation

`triangle_source_faces` contains source polygon row IDs, not native CAD face IDs.
Python and TypeScript require nonnegative safe integers, at most `2**53 - 1`,
and one mapping entry per display triangle. Both validators consume the shared
boundary cases in `tests_loose/source-face-id-cases.json`.
Run `bun run test:loose` here (after installing root workspace dependencies) for
the strict TypeScript compile and Node contract tests. This targets the loose
`contracts.ts`, independently of the archive frontend.

Standalone diagnostic cases are enumerated in
[LE5_LE6_CASES.md](tests_loose/LE5_LE6_CASES.md) and implemented in
`tests_loose/test_payload_coverage.py`. Empty or partially covered edge checks
cannot pass without complete coverage; detected failures remain failures. The
low-quality selection includes degenerate faces even at threshold zero.
