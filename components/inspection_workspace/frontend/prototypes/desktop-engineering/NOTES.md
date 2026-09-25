# Verdict

Question: how do the five structural layouts change when the proposed visual
language is applied without adopting the supplied example code as architecture?

Applied across every variant:

- Obsidian depth hierarchy with restrained cyan, amber, and rose laser accents.
- Geometric sans-serif labels with tabular monospace values and identifiers.
- View-local FIT, EDGES, CLIP Z, and XRAY HUD controls plus render telemetry.
- Dense validation rows with status rings and failure/review edge markers.
- Discrete solver iteration steps, explicit sample anchors, and crisp grid ticks.

These remain visual suggestions over live Three.js canvases. They do not define
the production Svelte component boundaries, inspection-document schema, or
Python-to-Gradio delivery contract.

## Checkpoint 01 — obsidian / laser pass

Accepted direction as of 2026-09-24: keep the five structural layouts and their
dense desktop proportions. Keep the obsidian depth hierarchy, restrained status
accents, hybrid typography, viewport-local controls, tabular diagnostics, and
discrete solver chart treatment.

Frozen comparison image:
`renders/checkpoint-01-obsidian-laser.png`

SHA-256:
`45c8d5b5c2d160757b3ba72682f1e515623d96d0d04e2cfacd6f22fb08fa0096`

Active exploration: conventional scene lights have been replaced by procedural
camera-relative matte shading. Element borders use barycentric screen-space
coverage inside the same front-face-culled mesh shader, so ghost mode does not
reintroduce rear-surface wire clutter. A separate CPU pass compares adjacent
face normals and emits restrained ridge/cavity segments. Variant E uses an
alpha-0.18 ghost shell around unobscured trace paths; Variant D applies the
existing synthetic scalar field over the matte response and exposes a compact
tolerance legend. This remains a visual experiment, not a production shader
contract or a claim of physically based ambient occlusion.

## Checkpoint 02 — matte surface / crease / ghost pass

Accepted progress as of 2026-09-24: retain the procedural matte surface
response, front-face-integrated element grid, adjacent-normal crease pass,
compact scalar legend, and ghost-shell trace composition.

Frozen comparison image:
`renders/checkpoint-02-matcap-crease-ghost.png`

SHA-256:
`1f3533d072e897f15613d1e2f0a3429ec5c53ff07bb3a4feb0c9b6f7c674b28d`

Next exploration: lift the viewport center away from black with a restrained
radial field, attenuate distant faces and grid coverage toward that field,
adapt grid contrast in low-luminance scalar zones, and promote genuinely failed
tolerance readings without enlarging ordinary HUD copy.

## Current candidate — depth field / adaptive grid pass

- The WebGL canvas is transparent over a slate-centered radial viewport field.
- Camera-space distance fades surfaces, integrated grid coverage, crease lines,
  traces, and the ground grid toward the viewport field.
- A real `metric` buffer attribute is normalized in the shader against the
  displayed `[0.15, 1.10]` bounds.
- Heatmap edges remain dark over warm/high-luminance regions and transition to
  muted ice blue below normalized `0.38`.
- The mean-ratio readout uses its actual minimum-bound semantics:
  `0.318 < 0.750` is `OUT OF TOL` and receives the larger alert treatment.
- The mesh grid remains inside the front-face shader. It was not split into an
  independent `WireframeGeometry`, which would undermine ghost-mode culling.

## Checkpoint 03 — depth cue / adaptive grid pass

Accepted progress as of 2026-09-24: retain the slate radial viewport field,
camera-distance cueing, shader-normalized metric attribute, adaptive low-band
grid contrast, and failure-only typography escalation.

Frozen comparison image:
`renders/checkpoint-03-depth-cue-adaptive-grid.png`

SHA-256:
`28ba3f2e4910838c8d57b40c266933ad5d6b761f7437edf332e717ec596c30dd`

Next exploration: compact both side docks automatically in split comparison,
neutralize reference geometry, instrument histogram axes, enlarge step anchors,
raise isoline visibility, and increase HUD backing opacity without changing the
accepted workspace framing.

## Current candidate — compact comparison / instrument pass

- Variant B automatically replaces the 20% side panels with 48 px icon docks,
  expanding the synchronized comparison canvases without removing access cues.
- Variant C uses titanium/slate reference geometry and cyan selection emphasis;
  red remains reserved for actual failed conditions and defect targets.
- Histogram views now expose face-count ticks, metric-bin values, and a visible
  minimum-bound line. Solver points use larger explicit iteration anchors.
- Variant E raises isoline opacity and uses desaturated ice-blue lines with cyan
  active emphasis. The ghost shell and depth cue remain unchanged.
- View labels, telemetry, legends, and ghost readouts use 0.92–0.96 backing
  opacity and brighter technical copy for office and field-monitor readability.
- Variant A receives a lighter titanium base and reduced depth-fade strength to
  recover convex/concave recognition without losing its low-clutter character.

## Checkpoint 04 — compact docks / instrumented analytics

Accepted progress as of 2026-09-24: retain automatic compact docks in split
comparison, neutral reference geometry, instrumented histogram axes, larger
solver anchors, brighter trace isolines, more opaque HUD plates, and the lighter
topology surface response.

Frozen comparison image:
`renders/checkpoint-04-compact-docks-instrumented-analytics.png`

SHA-256:
`9624e4f8ec0e3b4c94de8ad9f77b4c2985d71accc15571903e757aef6c3832da`

Next exploration: add camera-tracking coordinate gnomons, make comparison-camera
coupling explicit, distinguish clipped scalar values from in-range maxima, bind
histogram bins to geometry emphasis, and ground the contour-only view.

## Current candidate — spatial tracking / cross-probe pass

- Every WebGL viewport now renders a fixed-corner secondary coordinate scene.
  Its muted XYZ triad follows the active orbit camera while the `GLOBAL XYZ`
  frame remains screen-fixed.
- Variant B exposes `CAMERAS LINKED` on the split divider. The control switches
  to `INDEPENDENT ORBIT`, and linked mode copies camera pose and orbit target
  between the two real `OrbitControls` instances.
- The scalar field contains values above the displayed upper bound. Those faces
  render with an explicit white/dark hatch and a matching `CLIPPED > 1.100`
  legend key instead of silently saturating at the end of the color ramp.
- Histogram bars are real cross-probe targets. The selected metric interval is
  shown in the legend and passed to the mesh shader as a cyan face-emphasis
  range; bin 07 is active in the comparison image.
- Variant E strengthens its desaturated ground grid, adds a horizon reference,
  and reports the ground elevation while retaining front-face ghosting and
  distance cueing.

Prototype boundaries: the gnomon, camera coupling, clipping, and cross-probe
are working browser behaviors over synthetic geometry. They do not establish
the eventual production Svelte component API, GPU data contract, or Gradio
payload schema.

## Checkpoint 05 — spatial tracking / cross-probe

Accepted progress as of 2026-09-24: retain the camera-following coordinate
gnomons, explicit comparison-camera coupling, clipped-value hatch, histogram
cross-probe interaction, and grounded trace viewport.

Frozen comparison image:
`renders/checkpoint-05-spatial-tracking-cross-probe.png`

SHA-256:
`9151d1832c4b7d715aa4e87ee3fd94bc1de7f2988714e3992042ab5a50200e3d`

Next exploration: remove the default histogram selection, turn an explicit
cross-probe into selected-envelope isolation with a white perimeter fence, add
an asymmetric deviation gauge, and expand solver evidence into a logarithmic
dual-axis monitor with a scientific iteration table.

## Current candidate — contextual isolation / scientific monitor

- Histogram cross-probing now starts clear. Clicking a bin retains the selected
  metric envelope, desaturates and attenuates the remaining chassis, suppresses
  unrelated element lines, and marks both scalar boundaries with white fences.
  Clicking the active bin again restores the complete field.
- Variant D adds a compact asymmetric deviation gauge with distinct nominal,
  permitted, limit, and over-ceiling regions. The demonstrated `1.200 mm`
  observation is `+26.3%` above its independent `0.950 mm` ceiling.
- Variant E replaces the small decorative convergence chart with a dual-axis
  instrument: base-10 L2 residuals use the left logarithmic axis; relaxation
  omega uses a separate right linear axis. The adjacent table reports exact
  iteration IDs, exponential residual notation, omega, and solver state.
- The current contact sheet shows Variant D after an explicit bin-07 click so
  the isolation behavior is visible. Opening the live prototype still begins
  with `PROBE OFF` and no unexplained cyan selection band.

Prototype boundaries: the gauge and convergence values remain illustrative
payloads. The interface establishes display hierarchy and interaction behavior,
not a solver-data schema or production shader contract.

| Variant | Keep | Reject |
| --- | --- | --- |
| A — Topology workbench |  |  |
| B — Revision compare |  |  |
| C — Surface and UV |  |  |
| D — Quality field |  |  |
| E — Trace solver |  |  |
