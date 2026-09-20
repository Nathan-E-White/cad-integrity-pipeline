# Browser and integration acceptance

These are required before treating the source bundle as deployed. They were not run in the delivery environment.

| Case | Acceptance criterion |
|---|---|
| Initial null → populated | Load the demo without data, then the fixture; exactly one usable canvas appears without remounting the component. |
| Invalid input | Negative/fractional/out-of-range indices produce visible errors; no silent empty-success fallback and no unsigned wrapping. |
| Hover / keyboard | Hover and Tab-focus on a metric preview the corresponding target; Enter/Space pins it; blur/mouseleave restores the pinned selection. |
| Shared target | Minimum mean-ratio and failed-quality count may reference one target. Pin/clear events retain correct metric and revision identity. |
| Geometry reuse | Compare `getResourceStats().surfaceBuilds` before/after repeated selection. It must not increase on selection. |
| Clear versus fit | Clear selection must not recenter the camera. Fit model explicitly reframes the geometry. |
| Original versus repaired | Change geometry revision and triangle ordering; stale targets are rejected. Never display original indices against repaired geometry without a mapping. |
| Report-only update | Same geometry revision, new diagnostic revision: overlay/metric updates without surface regeneration. |
| Hidden tab | Hide the Gradio tab/container, update data, then reveal. No aspect division by zero; deferred fit runs when dimensions become nonzero. |
| Responsive layout | Exercise narrow and wide containers, DPR 1 and 2, zoom and resize. Lines remain readable and the audit remains scrollable. |
| Occlusion | With ghost shell and X-ray off, the depth prepass occludes rear annotations. X-ray on exposes them and the label explains the tradeoff. |
| Degenerate face | Select the collapsed triangle in the fixture; point/edge markers make it discoverable even when it has no filled area. |
| Reduced motion | With OS reduced motion on, no pulse or inertial orbit damping, even with the pulse checkbox enabled. |
| Idle / visibility | No continuing RAF sequence when idle without pulse; pause when offscreen/document hidden and resume correctly. |
| Lifetime | Repeatedly load/clear data, switch target types and unmount/remount. GPU geometries/material allocations must not grow without bound. Account for renderer-internal caches when measuring. |
| Context loss | Use a browser test or WEBGL_lose_context extension to lose/restore the context. Status appears; restoration re-renders; unmount while lost remains safe. |
| Real Gradio package | Build/install the scaffolded component, exercise upload → callback → value updates, loading state, examples and select callback. |
| Multiple instances | Separate viewports, cameras, selection state, event handlers and cleanup. No global scene/controller state. |
| Heavy fixture | Measure JSON size, parse/normalization time, renderer time and GPU allocations on target hardware; do not infer capacity from unit tests. |

## Suggested performance assertions

The current standalone host exposes `getResourceStats()` for integration instrumentation. Record surfaceBuilds, renderer memory, frame rate under interaction, idle RAF activity and allocation plateaus after repeated data replacement. Baseline edge draws scale with diagnostic target/category count, not edge count. Selected faces use a compact, bounded active overlay; they do not clone the full original vertex table.

The wireframe threshold is a deliberate budget and must be visible to users. The package does not silently decimate geometry to make an oversized payload appear successful.
