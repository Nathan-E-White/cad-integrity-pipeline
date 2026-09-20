# Unanswered design decisions

Planning register for design questions deferred during integration discussions.
Entries remain unresolved until an explicit decision is recorded. A recommendation
is not an accepted decision or authorization to implement it.

Existing capabilities awaiting integration are tracked separately in
[UNINTEGRATED_CAPABILITIES.md](UNINTEGRATED_CAPABILITIES.md).

## D-001 — Candidate inspection after candidate-file persistence failure

Status: deferred; unanswered.

Scope: polygonal result projection and inspector integration.

### Scenario

Computation produces an in-memory candidate, but writing `candidate.npz` fails.
The source remains retained. Should the inspector suppress the candidate view,
or allow inspection of the computed candidate without a downloadable artifact?

### Current behavior

[`_polygonal_analysis_outcome`](../src/cad_integrity/gradio_app.py) marks completion
incomplete, clears the candidate figure, and sets brief candidate availability
to false when candidate publication fails. The release contains no retained
candidate artifact.

This differs from a later evidence-file failure: a candidate already retained
before that failure remains available.

### Options

1. Preserve suppression: show the candidate only when its file was retained.
2. Permit in-memory inspection: represent inspection availability separately from
   download availability, including what happens after session loss or expiry.

### Recommendation considered

Preserve current behavior for the initial projection slice, avoiding an additional
behavior change during renderer integration. This recommendation has not been
accepted; the question was explicitly deferred.

### Revisit when

Defining candidate visibility and publication-failure behavior for the integrated
inspector. Resolve before finalizing that behavior and its acceptance tests.

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
