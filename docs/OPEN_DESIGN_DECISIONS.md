# Unanswered design decisions

Planning register for design questions deferred during integration discussions.
Entries remain unresolved until an explicit decision is recorded. A recommendation
is not an accepted decision or authorization to implement it.

Existing capabilities awaiting integration are tracked separately in
[UNINTEGRATED_CAPABILITIES.md](UNINTEGRATED_CAPABILITIES.md).

## D-001 — Candidate inspection after candidate-file persistence failure

Status: resolved on 2026-09-20: permit in-memory inspection without a download.

Scope: polygonal result projection and inspector integration.

### Scenario

Computation produces an in-memory candidate, but writing `candidate.npz` fails.
The source remains retained. Should the inspector suppress the candidate view,
or allow inspection of the computed candidate without a downloadable artifact?

### Accepted behavior

The user selected in-memory inspection. When `candidate.npz` writing fails,
completion is incomplete and the retained release has no candidate artifact.
The immutable computed candidate remains available in the inspection snapshot.
Download availability and inspection availability are separate facts.

The snapshot lasts as the current displayed result: a newly admitted computation
clears it, and page reload does not reopen it. It is not a retained snapshot export.
An already loaded view does not require its candidate download link to remain valid.
A later evidence-write failure likewise preserves already retained files.

The legacy Plotly path keeps its existing file-publication display behavior until
replacement is qualified. This does not restrict the new runtime snapshot.

## D-002 — Comparison layout when no candidate is available

Status: deferred; unanswered. Interim behavior agreed below.

Scope: side-by-side Original and Candidate inspection with optional maximization.

### Question

When no candidate is available, should Original expand into the candidate pane's
space, or should the comparison layout retain both pane areas?

### Agreed behavior for the current cut

Leave the candidate pane vacant. Preserve the side-by-side layout and Original's
width; do not dynamically resize the panels because a candidate is absent.

The separately agreed explicit maximization control remains available. Candidate
absence must not automatically invoke it.

### Options for later consideration

1. Retain the vacant candidate pane and stable comparison layout.
2. Automatically expand Original while no candidate is available, restoring the
   comparison layout when a candidate becomes available.

### Revisit when

Reviewing comparison-layout behavior after the initial inspector integration.
Automatic expansion is not authorized for the current cut.
