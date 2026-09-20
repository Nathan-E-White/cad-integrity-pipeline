# Medial-axis discussion handoff

## Purpose

Continue the design discussion only if the user wants to turn the exploratory
medial-axis material into a qualified CAD Integrity capability. No production
implementation has been authorized or made.

## Current conclusion

`developer/MedialAxisTransform.py` is not suitable for import or integration.
It combines three distinct ambitions:

1. approximate an interior medial axis;
2. classify small-clearance regions as CAD slivers; and
3. prune a skeletal graph.

The file currently computes distances from user-supplied interior candidates to
user-supplied boundary samples. That is a sampled-clearance heuristic, not a
medial-axis-transform algorithm. It has no B-rep/domain adapter, inside/outside
test, source provenance, scale-aware tie rule, feature distinction, resource
budget, or mutation policy. It allocates a dense M-by-N distance matrix and
contains module-scope mock execution; its supplied empty adjacency mapping makes
the skeletal demonstration fail when imported.

Do not represent a small sampled clearance as authorization to delete geometry.
It does not establish a CAD sliver, intended feature ownership, or a safe repair.
Mesh slivers, thin material regions, and small B-rep features are separate
phenomena with different diagnostics and remedies.

## Recommended scope if resumed

Start with a read-only `sampled clearance probe`, not a medial-axis module:

```python
report = probe_sampled_clearance(
    validated_shape,
    probe_specification,
    clearance_policy,
)
```

Its evidence should retain probe locations, inside-domain status, nearest
boundary witnesses and native ownership, distances in declared units, sampling
and tolerance policy, source fingerprint, resource use, and explicit
`not_established` states. It may flag results for review; it must not create a
repair/deletion candidate.

An approximate medial complex is a later, separately qualified research slice:

```text
validated closed solid
  -> inside/outside and closest-point domain adapter
  -> bounded candidate generator
  -> maximal-ball/contact-set verifier
  -> connected medial complex with radius/contact provenance
  -> optional simplification plan
```

Choose and document one algorithm family before coding:

- adaptive boundary sampling plus Voronoi/Delaunay approximation with explicit
  coverage/error assumptions; or
- B-rep-aware continuous tracing using surface/curve distance and curvature.

The latter is a specialist computational-geometry project. Python may
orchestrate a native implementation but should not substitute for robust
predicates/constructions.

## Product architecture constraints

- Do not import or execute `developer/MedialAxisTransform.py`; retain it as
  inspected research material.
- Keep native OCP shapes separate from polygonal topology and numerical
  sidecars. Existing `BRepExtrema` distance/proximity evidence is not proof of
  an interior MAT.
- Do not attach this work to motorcycle paths, harmonic UV charts, or seam
  repair unless a concrete workflow requires the shared evidence.
- Gradio should remain a thin controller. A future local-lab action would return
  a typed report, Decision Brief, Plotly evidence, and JSON artifacts through
  the existing artifact flow; it would not mutate geometry.

## Verification required before any implementation claim

- Analytic fixtures: sphere, cylinder, box, annulus/cavity, and narrow channel.
- Fixed-seed sampling-density, rigid-transform, and unit-scaling tests.
- Adversarial near features, periodic/seamed faces, multiple solids, open shells,
  and ambiguous/intersection cases that return refusal or `not_established`.
- Explicit CPU, memory, probe-count, candidate-count, and output-record budgets.
- Independent oracle or documented bound for the selected approximation family.
- Separate evidence for any later skeletal simplification: contact/radius error,
  topology claim, threshold rationale, and reconstruction-error scope.

## Primary sources already consulted

- Ramanathan and Gurumoorthy, *Interior Medial Axis Transform computation of 3D
  objects bound by free-form surfaces*:
  https://ed.iitm.ac.in/~raman/agcl/3DMAT_CorrectedProof.pdf
- CGAL Mesh_3 User Manual, including feature protection and the distinction
  between tetrahedral slivers and other geometric defects:
  https://doc.cgal.org/latest/Mesh_3/index.html
- Open CASCADE BRepExtrema package reference:
  https://occt3d.com/dev/doc/refman/html/package_brepextrema.html

## Relevant repository references

- Prototype: `developer/MedialAxisTransform.py`
- Native classifier research: `docs/evidence/stage-9-occt-native-classifier-research.md`
- Native repair research: `docs/evidence/stage-10-occt-selected-local-sewing-research.md`
- Broader repair-method survey: `docs/BREP_MESH_REFINEMENT_REPAIR_RESEARCH.md`
- Local app/controller seam: `src/cad_integrity/gradio_app.py`
- Native OCP adapter: `src/cad_integrity/adapters/ocp.py`

## Working-tree cautions

The repository already contains user changes and untracked developer materials.
Preserve them. This discussion created no repository changes.

## Suggested skills

- `research` before selecting a medial-axis approximation or B-rep tracing
  algorithm; use primary sources and save findings only if requested.
- `codebase-design` when defining the evidence/report module and its seam with
  native OCP adapters and Gradio controllers.
- `tdd` if implementation is authorized; establish analytic fixtures and
  refusal/budget tests before production code.
- `code-review` after a bounded implementation slice, with separate standards
  and specification review.
