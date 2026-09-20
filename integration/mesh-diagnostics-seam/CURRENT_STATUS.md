# Diagnostics delivery status

The consolidation adopts `cad_mesh_inspector` and `gradio_meshdiagnostics` with
`InspectorDocument` v1, the shared Svelte inspector, and the numeric NPZ reader.
See [README.md](README.md) for current build/use instructions and
[VERIFICATION.md](VERIFICATION.md) for qualification evidence.

The root Bun workspace and catalog own JavaScript dependencies and `bun.lock`.
The Python distribution uses Hatchling and includes both the numeric package and
the Gradio backend; a normal wheel requires generated frontend assets.

The integration branch's conservative empty/partial diagnostic statuses and
degenerate-face selection are retained, with their regression fixtures in `tests/`.
Its restored reference implementation remains under `python/mesh_diagnostics/`,
`frontend/`, and `gradio_adapter/`; its Python tests are in `tests_reference/`.
These are separate reference contracts, not the installed component. The original
archive and its delivery documentation remain historical evidence.

Parent-app integration is still separate. Motorcycle capability will be developed
directly in the parent application, using the inspector as a display surface.
