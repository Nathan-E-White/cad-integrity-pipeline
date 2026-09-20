# Motorcycle Paths and Native B-rep Healing

## Decision brief

**Do not implement “motorcycle-path B-rep healing” as an algorithmic repair
family.**  Motorcycle graphs are a combinatorial construction for partitioning
semi-regular *quadrilateral meshes* into structured submeshes; they are not a
repair method for a CAD boundary representation.  The original quad-mesh paper
is quite explicit about both the input and result: it adapts motorcycle graphs
to partition quadrilateral meshes, chiefly for canonicalization, isomorphism,
and compression.[^quad]

A defensible Python contribution is therefore a narrowly labelled **read-only
mesh-analysis sidecar**: tessellate a *validated* B-rep for display or a
separately governed quad-mesh workflow, retain the native entity provenance,
and (only when the resulting mesh satisfies the paper's preconditions) compute
a motorcycle-graph partition as diagnostic metadata.  It must not feed cut
paths back into B-rep topology automatically, nor call its output a healed
surface, a recovered feature layout, or evidence of simulation readiness.

The native healing path should instead remain kernel-mediated and evidence
producing: inspect a copied imported shape; classify its native defects; permit
only an explicitly selected repair; preserve exact input/output bytes and the
kernel/version/tolerance record; then validate and re-import the candidate.
Open CASCADE's own APIs make clear why: validity includes edge parameterization
and curve-on-surface consistency, not merely adjacency; its general fixer
iterates over subshapes; and sewing can modify or delete subshapes while using
tolerance-dependent decisions.[^check][^fix][^sew]

## Terminology correction

There are two related but distinct constructions that are easy to conflate.

1. In planar computational geometry, motorcycles start at positions with fixed
   velocities, leave tracks, and stop when they reach another track.  Their
   tracks form a planar motorcycle graph; the construction was introduced for
   the difficult part of straight-skeleton computation.[^straight]
2. Eppstein, Goodrich, Kim, and Tamstorf adapted that idea to an **abstract
   semi-regular quadrilateral mesh**.  Paths originate from extraordinary
   vertices and partition a clean quad mesh into structured regions.[^quad]

Neither definition supplies a representation of trimmed parametric surfaces,
coedges, p-curves, periodic seams, vertex/edge tolerances, shell orientation,
or solid containment.  Those are native B-rep obligations.  A triangle
tessellation of a CAD face is also not a quad mesh, and a quad layout generated
from a tessellation does not become authoritative B-rep topology merely because
its paths look tidy.

The later generalized-motorcycle-graph literature strengthens, rather than
weakens, this boundary: it says the original MCG targets pure-quad meshes and
does not handle T-junctions or non-two-manifold vertices; even a single
non-quad needs a conversion that adds irregularity.[^gmcg]  These are ordinary
conditions in damaged imports, precisely where a repair system needs the most
care.

## Feasibility assessment

| Proposed interpretation | Technically valid? | Appropriate result |
|---|---:|---|
| Run MCG on an abstract, admitted semi-regular quad mesh | Yes | Canonical partition / compressed layout metadata |
| Use MCG paths to diagnose an exported B-rep display mesh | Conditionally | Advisory, non-authoritative report with mesh and B-rep provenance |
| Use paths to choose native edges/faces to merge, split, sew, or fill | No | `needs_review`; there is no intent-preserving correspondence supplied by MCG |
| Claim MCG repaired a STEP B-rep, removed gaps, restored trims, or made a solid watertight | No | Unsupported claim |

The key mismatch is not Python performance.  It is semantic: MCG works over
mesh incidence and valence, while a B-rep's identity is the coordinated
topology-and-geometry relationship.  OCCT's validity check, for example,
requires closed and oriented wires/faces/shells and checks a face-context edge
against its 3-D curve and p-curve on the supporting surface within the edge
tolerance.[^check]  A motorcycle path has no information from which to repair
that relation.

## Conservative architecture

Keep the proposed capability as four one-way seams:

```text
immutable STEP bytes + import options
              |
              v
native B-rep inventory / validity / tolerance report ----> needs_review
              |
              | (only admitted, explicitly non-authoritative tessellation)
              v
quad-mesh admission + B-rep-face/edge/vertex provenance
              |
              v
motorcycle partition report (paths, stop reason, limits, mesh fingerprint)
```

### 1. Native inventory, before any candidate mutation

Record shape kind; solids/shells/faces/wires/edges/vertices; free boundaries;
edge uses; periodic or degenerate entities; local tolerances; import transfer
status; and stable references *within that one kernel session*.  Include a
cryptographic digest of the exact source bytes, units and import settings,
OCCT and Python binding versions, and a deterministic traversal/indexing
policy.  The index is evidence, not a durable CAD identifier: subsequent
topology-changing operations can replace or delete subshapes.

Run `BRepCheck_Analyzer` with geometric controls and retain its per-subshape
results.  OCCT documents that its default finite sampling can be faster but
possibly incorrect, whereas its exact curve-on-surface method is slower and
more correct; record which was selected.[^check]  Failure, ambiguity, or an
open/free boundary is a classified result, not authorization to infer a mate.

### 2. Mesh sidecar admission

Only construct the MCG sidecar after declaring the tessellation's purpose
(display, diagnostic, or downstream meshing input) and its chordal/angular
criteria.  Require a pure-quad, two-manifold connectivity model matching the
chosen MCG implementation; reject triangles, n-gons, T-junctions, disconnected
or non-manifold neighborhoods, inconsistent orientation, and provenance gaps.
No automatic triangle-to-quad conversion belongs in the healing path.

Every output path must retain: source mesh fingerprint; exact vertex/edge/face
indices; start singularity; ordering/tie-break rule; stop reason; and the
complete map to tessellated B-rep face/edge/vertex provenance.  Where a path
crosses an artificial tessellation edge, say so.  It cannot identify a native
coedge or a legal trim split without an additional, independently specified
surface-parameter and topology-reconstruction contract.

### 3. Native repair, independent of MCG

For a repair that the caller explicitly selects, copy the OCCT shape, bound
resources, configure a *named* operation and tolerances, and store the result
as a new artifact.  A suitable first scope is **selected local sewing of
identified free-boundary candidates**, not a global clean-up pass.  `BRepBuilderAPI_Sewing`
exposes set/min/max tolerance, optional local-tolerance accounting, and
per-input `IsModified`/`Modified` mappings; it also reports deleted faces.
That is useful provenance material, not proof that every edit was intended.[^sew]

`ShapeFix_Shape` is even broader: its `Perform()` iterates fixes over
subshapes, with independently configurable face, wire, shell, solid, vertex,
and same-parameter modes.[^fix]  Do not place it behind an unqualified “heal”
button.  If it is later exposed, default every mutation-capable mode off until
the exact operation has an approved policy, budget, fixtures, and report.

If a separately authorized product eventually needs a native split, use a
geometry-aware OCCT operation with its own contract.  For example,
`ShapeUpgrade_FaceDivide` documents splitting 3-D curves, p-curves, and the
supporting surface, and requires p-curves in the support surface's parameter
space.[^divide]  That prerequisite is exactly what an MCG trace does not
provide.  A projected path is therefore only a proposed input to a new,
review-gated native construction problem—not a repair instruction.

### 4. Candidate verification

Re-run native validity after repair; check shell closure/orientation, solid
construction and positive volume only when relevant, preservation of intended
component/cavity counts, tolerance growth against the declared budget, and
serialized STEP re-import.  Compare source and candidate with a semantic
provenance report, not only counts.  Preserve the candidate bytes separately;
never overwrite the source.

## Python / OCCT seam

Python is reasonable as orchestration, policy, serialization, deterministic
reporting, and fixture testing.  It is not a substitute for a robust native
kernel.  `pythonocc-core` declares itself a wrapper around the Open CASCADE
kernel and says it exposes almost all OCCT C++ classes with largely matching
names/signatures; pin the wrapper and OCCT binary pair rather than assuming
cross-version reproducibility.[^pythonocc]

A narrow interface should therefore look conceptually like this:

```python
report = inspect_brep(source_bytes, import_policy)
if not report.native_admission.ok:
    return NeedsReview(report)

sidecar = partition_admitted_quad_mesh(report.tessellation, mesh_policy)
# sidecar has no authority to alter report.shape or select a native repair.

candidate = sew_explicit_candidates(
    source_bytes, selected_boundary_pairs, repair_policy
)
return verify_and_package(candidate, source_bytes, repair_policy)
```

The public types should make it impossible to pass a motorcycle partition where
a native candidate-selection set is required.  Do not expose raw mutable
`TopoDS_Shape` as the primary public result; package an artifact path/digest,
read-only evidence, and explicit status (`accepted`, `rejected`,
`needs_review`, or `indeterminate`).

## Tolerance and provenance requirements

Tolerance is part of the model, not a cosmetic epsilon.  Record its length
unit, caller-supplied maximum, per-entity input values, all algorithm settings,
and before/after maximum and distribution.  OCCT's sewing documentation states
that, when local-tolerance mode is enabled, working tolerance includes both
edge tolerances in addition to the configured tolerance.[^sew]  Hence a report
that stores only a single UI value cannot reproduce or explain a merge.

Keep the original STEP bytes, import warnings, settings, source digest,
candidate digest, OCCT/pythonocc versions, selected entity references and their
pre-operation geometric evidence.  A STEP round trip is a useful compatibility
check, not a proof of preserved design history, manufacturing intent, feature
identity, or geometric equivalence.

## Hard non-claims

This work must not claim that it:

* reconstructs a designer's intended B-rep adjacency from nearby boundaries;
* repairs arbitrary gaps, overlaps, self-intersections, trims, periodic seams,
  or non-manifold STEP topology;
* transfers an MCG path to a native edge/face split or sewing decision;
* guarantees watertightness, geometric validity across other kernels, bounded
  Hausdorff displacement, feature preservation, or simulation readiness; or
* turns a successful `ShapeFix`/sewing operation or a successful re-import into
  certification of any of the above.

Those are deliberately severe restrictions.  They are the difference between
a traceable repair candidate and a device that confidently changes a part while
losing the argument for why it was allowed to do so.

## Licensing and dependencies

OCCT is LGPL-2.1 with its upstream OCCT exception; review the actual bundled
license and distribution obligations for the selected build.[^occtlicense]
`pythonocc-core` is LGPL-3.0 according to its upstream repository.[^pythonocc]
This research does not establish the licensing of a transitive conda package,
binary redistribution, or application distribution; capture those in the
release SBOM/notice review.  A pure-Python MCG sidecar can avoid additional
runtime geometry dependencies, but it does not remove the OCCT binding and
binary-provenance obligations of native healing.

## Staged validation plan

1. **Read-only fixtures:** valid box/cylinder/periodic face; open shell;
   intentional nearby but separate boundaries; mismatched p-curve/3-D curve;
   self-intersecting wire; multiple solids and a cavity.  Assert classification
   and byte immutability.
2. **Mesh-sidecar fixtures:** clean pure quad grids with known extraordinary
   vertices and path tie cases; then triangle, n-gon, T-junction, non-manifold,
   and missing-provenance cases that must decline admission.  Compare the
   partition combinatorially against fixed expected paths, never against a
   “healed B-rep” oracle.
3. **One native repair slice:** selected free-boundary pair sewing with a fixed
   scale-aware tolerance budget.  Include a near-feature counterexample that
   must not merge; assert original-byte retention, candidate provenance,
   `IsModified` capture, post-check, and STEP re-import.
4. **Qualification, not a unit-test shortcut:** deterministic fixed-seed
   perturbations around the declared tolerance; bounded malformed-input and
   resource tests in an isolated process; corpus growth from actual failures;
   and a separate review of versions/licenses.  Passing local fixtures remains
   evidence for that narrow slice only.

## Sources

[^straight]: H. Huber and M. Held, “[Motorcycle Graphs and Straight Skeletons](https://faculty.unist.ac.kr/algo/wp-content/uploads/sites/362/2016/09/motor.pdf),” *Computational Geometry* 47(2), 2014, pp. 115–127.  See its definition of positions, velocities, tracks, crashes, and planar graph.
[^quad]: D. Eppstein, M. T. Goodrich, E. Kim, and R. Tamstorf, “[Motorcycle Graphs: Canonical Quad Mesh Partitioning](https://diglib.eg.org/bitstreams/417e3d00-227c-432b-b84e-fa1638e84084/download),” *Computer Graphics Forum* 27(5), 2008, pp. 1477–1486, [doi:10.1111/j.1467-8659.2008.01288.x](https://doi.org/10.1111/j.1467-8659.2008.01288.x).
[^gmcg]: N. Schertler, D. Panozzo, S. Gumhold, and M. Tarini, “[Generalized Motorcycle Graphs for Imperfect Quad-Dominant Meshes](https://cims.nyu.edu/gcl/papers/2018-GMG.pdf),” *ACM Transactions on Graphics* 37(4), 2018.
[^check]: Open CASCADE, “[BRepCheck_Analyzer Class Reference](https://occt3d.com/dev/doc/refman/html/class_b_rep_check___analyzer.html),” OCCT 8.0.1 API reference, accessed 2026-09-15.
[^fix]: Open CASCADE, “[ShapeFix_Shape Class Reference](https://occt3d.com/dev/doc/refman/html/class_shape_fix___shape.html),” OCCT 8.0.1 API reference, accessed 2026-09-15.
[^sew]: Open CASCADE, “[BRepBuilderAPI_Sewing Class Reference](https://occt3d.com/dev/doc/refman/html/class_b_rep_builder_a_p_i___sewing.html),” OCCT 8.0.1 API reference, accessed 2026-09-15.
[^pythonocc]: tpaviot, “[pythonocc-core](https://github.com/tpaviot/pythonocc-core),” upstream repository and license, accessed 2026-09-15.
[^occtlicense]: Open Cascade SAS, “[OCCT upstream repository](https://github.com/Open-Cascade-SAS/OCCT),” license statement and `OCCT_LGPL_EXCEPTION.txt`, accessed 2026-09-15.
[^divide]: Open CASCADE, “[ShapeUpgrade_FaceDivide Class Reference](https://dev.opencascade.org/doc/refman/html/class_shape_upgrade___face_divide.html),” API reference, accessed 2026-09-15.
