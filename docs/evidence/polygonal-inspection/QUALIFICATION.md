# Polygonal inspection qualification protocol

Status: gates specified before capacity measurements; passed locally. See the
JSON measurements and implementation evidence in this directory.

Target: this local macOS ARM64 workstation, installed Gradio parent, local Chrome.
Record exact OS/browser/hardware versions with results. The installed inspection workspace is now the default; the old polygonal display
remains explicitly available through `inspection_enabled=False`.

## Resource and interaction gates

- Input: 250,000 vertices and 500,000 triangles within existing NPZ byte budgets;
  both original/candidate snapshots, plus dense diagnostic memberships.
- Encoded inspection JSON: at most 512 MB for both panes.
- Projection plus encoding: at most 30 seconds after numerical computation.
- Browser result load: at most 30 seconds after delivery starts.
- Entity selection/filter/clipping response: at most 500 ms on the target machine.
- Combined renderer resident memory: at most 4 GiB above idle; record browser and
  backend separately. Unavailable GPU-memory measurements remain unavailable.
- Ten replacements: no more than 256 MiB retained growth after comparable settling;
  no stale rows/targets, duplicate canvases, or residual contexts.
- Last entity of each kind remains selectable; no dropped entities, decimation or
  lower upload admission limits are acceptable substitutes for passing.

These are local implementation qualification gates, not hardware-independent
performance promises. Numerical time is recorded separately from projection and
browser time. Synthetic dense reports test display capacity, not analyzer validity.
An admitted parent-controller run is required separately.
