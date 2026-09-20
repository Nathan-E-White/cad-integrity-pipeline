# Polygonal inspection review

Baseline explicitly approved by the user: `e74437971300ea55a23ff613560d10654472820d`.
Initial reviewed commit: `07b3c77`. Comparison:
`git diff e74437971300ea55a23ff613560d10654472820d...HEAD`.
Standards and Spec were reviewed independently in parallel under the code-review
skill. The local implementation plan was the authoritative specification.

## Standards

No hard violations found in `CONTEXT.md`, `dependency-policy.toml`, or other
non-tooling standards reviewed. Source-face identity remains distinct from
rendered triangle identity.

One low-priority judgement call: possible Repeated Switches / Primitive Obsession
in the common Gradio route dispatcher. An unconstrained route string could take
inconsistent computation and projection branches.

Resolution: constrain the route to `Literal["example", "upload", "step"]`; all
callers supply those literals. Reviewer rechecked the change and confirmed the
concrete hazard is resolved. No further abstraction is needed for this bounded
set of routes.

**Standards: zero outstanding findings.**

## Spec

One P2 finding: a failed inspection projection appeared as an ordinary empty
workspace. The plan requires actual unavailable/error states to remain explicit.
The original diagnostic was appended after evidence publication and was not shown.

Resolution: project before publishing the evidence batch; include any inspection
diagnostic in the retained brief and JSON. Show an explicit Inspection unavailable
state while preserving computed checks and retained download paths. A new test
injects a projection limit failure through the public seam and checks retained
evidence and installed route delivery. Reviewer independently reran the regression
and confirmed it passed.

No unrequested scope expansion identified. The 141-case catalogue remains clearly
distinguished from executed coverage.

**Spec: zero outstanding findings.**

Summary: zero outstanding Standards findings and zero outstanding Spec findings.
The initial findings are retained above with their resolutions.
