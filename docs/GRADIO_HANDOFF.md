# Gradio handoff: local geometry first

## What is available now

The package provides local, synchronous functions and structured reports, not a hosted application. `RepairPipeline.run(..., on_event=...)` handles restricted polygonal experiments. `run_step_pipeline(..., on_event=...)` handles native STEP. Plotly helpers return figures without opening windows or starting a server.

The native adapter can tessellate a private copy for display, retain per-triangle native face IDs, and sample the native curves corresponding to free or problematic edges. These are the rendering inputs for a later left/right UI. Edge IDs are local to an audited shape, not persistent IDs across repairs; recompute an audit for each new candidate before drawing its overlays.

## Correct the external service assumption

On September 13, 2026, the official SGS-1 Space application states:

> The SGS-1 Research Demo has ended.

It announces SGS-2 for Q3 2026. That announcement is not a verified inference API, download contract, or statement that a private endpoint is available. The prototype's `Client(...).predict(...)` call and assumed result schema cannot be retained as functioning integration.

Source: https://huggingface.co/spaces/spectral-labs/SGS-1/raw/main/app.py

Start the UI with **local STEP upload**. When an authorized inference service becomes available, isolate it behind a client adapter, inspect its actual schema, test captured response fixtures, and implement timeouts, retry limits, cancellation and download-size checks. Never replace a service failure with synthetic geometry without explicitly switching to a labeled demonstration mode. Do not claim a downloaded STEP is “unhealed” unless the provider documents that contract.

## Proposed request lifecycle

```text
local STEP upload (or a future authorized inference adapter)
    → bounded per-request staging and content hash
    → kernel import, explicit mm normalization
    → original audit and original display data
    → private-copy healing under explicit policy
    → candidate audit and candidate display data
    → temporary native STEP export
    → readback, kernel checks, representation/metric comparisons
    → publish STEP plus separate evidence report
```

The failure branch is a first-class outcome: preserve the input, show the audit and refusal reason, and do not present a success/download action for a failed candidate. An existing valid input is a valid **no repair needed** outcome, not an excuse to invent a defect for the animation.

For polygonal demonstrations, show b₀, b₁ and b₂ with the coefficient field and analyzed-object label. For native input, show `homology not computed` until a proper decomposition adapter exists. Free-edge diagnostics still work. Never display fabricated Betti numbers to fill a dashboard slot.

## Deferred polygonal-upload formats

The first untrusted polygonal-upload slice is restricted to a documented NPZ
array contract. OBJ and GLB import are desired follow-on adapters, but are
deferred: their parser and unit/topology-preservation contracts must be
qualified before they can enter combinatorial diagnostics. Do not silently
convert, weld, deduplicate, reorient, or otherwise process an uploaded mesh at
import time.

## Product wording

Use separate labels for “boundary defects detected,” “candidate generated,” “kernel checks passed,” and “repair rejected.” Green indicates only the stated acceptance policy. It should not imply design intent or an engineering sign-off.

Suggested download text:

> Download STEP — passed configured kernel checks

Accompany it with units, policy tolerance, kernel version, input/output hashes, changes, and limitations. Do not use “certified watertight” as a blanket warranty. This prototype does not establish a continuous shape-deviation bound or compliance with a mechanical design specification.

## Boundaries to implement before public uploads

Use independent resource-limited **processes** for native parsing/healing/meshing. Python exception handling and triangle-count budgets cannot reliably interrupt all C++ work or contain native crashes. Give each request a wall-clock budget, CPU/memory limits, isolated temporary directory, upload/download limits, and explicit cleanup/cancellation. Never share mutable TopoDS handles between requests.

A local translator lock serializes this adapter's STEP operations; it does not govern other libraries calling the same kernel in the process. Worker isolation remains the appropriate deployment boundary. Do not reuse a global healing object as a Gradio session state.

Use opaque server-generated filenames; reject unexpected file types and do not interpret client-supplied paths. Hash and retain the exact input used for an audit. A STEP file and its JSON sidecar are currently separate artifacts; a production evidence store should publish a job manifest only once all required artifacts are durably present.

Before any future image is sent to a third-party service, make that transmission explicit. CAD and drawings may contain proprietary engineering information. Keep credentials out of notebooks, logs, archives, and client-visible errors. Adopt retention/deletion controls appropriate to the intended users.

## Technical work deliberately still outstanding

The highest-value next geometry task is a topology-preserving native decomposition with periodic seams, holes, and face/edge/vertex provenance. It would connect the exact algebra experiments to actual STEP topology without confusing rendering tessellation with a valid complex.

Other extensions require independent acceptance criteria: nested-shell reconstruction, topology-aware curved-edge correspondence, persistent native entity identities, continuous surface-distance bounds, a solver-scale homology backend, and a curated corpus of real generative outputs. None is silently simulated by the current package.
