# Refactor review

## Review position

The prototype combines promising mathematical exploration with CAD integration, repair, and product claims. Making it reviewable for geometry specialists required correcting its contracts and claims, not merely moving functions into files. The resulting package is an independent work sample, not an implementation of Spectral's internal stack.

The uploaded `simplex.py` has 2,097 lines and fails to parse at line 1406. Other malformed arrays and concatenated statements would surface after that first error. Duplicate definitions overwrite earlier behavior, demonstrations run at module scope, and `from simplex import Simplex` introduces a self-import hazard. The archived original is not on the package import path.

## Defects and decisions

| Original issue | Why it matters | Replacement |
| --- | --- | --- |
| Duplicate classes, imports, inconsistent return schemas | Behavior depends on source ordering | One definition per responsibility; explicit dataclasses and imports |
| Signed edge IDs combine zero-based indices, signs, and padding | Edge zero has no negative sign; different methods disagree on indexing | Zero-based entity IDs; coedge token = sign × (edge ID + 1); no dummy row |
| Only an outer wire and endpoint arrays | Cannot represent arbitrary trimmed surfaces, inner loops, pcurves, or periodic seams | Name the array model `PolyhedralBRep`; keep general CAD authoritative in native OCP |
| b₁ described as “leaking holes”; low Betti counts gate export | An open disk has b₁=0; a closed torus has b₁=2 | Explicit boundary incidence, vertex links, orientation and native checks; homology is a descriptor |
| b₀ described as a number of solid bodies | Boundary components and material components differ for cavities | Describe b₀ of the particular analyzed complex, never infer material count from it |
| Numeric matrix rank presented as exact topological algebra | Rank depends on coefficients and numerical threshold | Exact F₂ sparse reduction; optional exact Z reference path; coefficient labels |
| Handwritten “Smith normal form” lacks a complete invariant-factor algorithm | A diagonal matrix is not necessarily Smith form | SymPy SNF with divisibility/torsion fixtures and bounded dense input |
| Filtration snapshots labeled persistence intervals | Betti curves do not give birth/death pairings | Actual boundary-column pairings over F₂, with [birth, death) conventions |
| Vertex welding allocates pairwise distance matrices | Quadratic memory before work begins | KD-tree queries with explicit neighborhood budgets |
| Overlapping neighborhoods can overwrite assignments or drift transitively | An endpoint can move much farther than the intended repair radius | Deterministic representative-radius clustering; no transitive radius assumption |
| Vertex remapping leaves duplicate edges | Coincident geometry is not shared topology | Edge deduplication and oriented-token remapping for straight polygonal edges |
| Flipping signs without reversing the ordered wire | The edge sequence no longer traverses a closed loop | Reverse order AND negate every token |
| BFS seeds only one component, or an override seeds no queue | Components remain unsynchronized; conflicting cycles are ignored | Visit every component and solve/check all orientation constraints |
| Endpoint-segment exporter replaces curves and constructs planar faces | Curved geometry and face trimming are lost | No array-to-general-CAD export; native shape → STEP → native readback |
| Locally bounded root solve described as exact intersection | Convergence neither proves global uniqueness nor finds every root | Bound parameter domains, check residual, label one local numerical intersection |
| Constant coordinates fail to broadcast | Flat surfaces and axis-aligned curves break | Broadcast each coordinate to the parameter shape before stacking |
| Triangle cosine formula subtracts the wrong squared side | Incorrect angles and skewness | Correct side/angle formula; analytic and scalene tests |
| Positive epsilon replaces degenerate area | An invalid element appears to have nonzero area | Report actual zero area and explicit degeneracy; never claim a healthy element |
| Adaptive splitting without conformity management | Hanging nodes/T-junctions corrupt topology | Shared-midpoint, conforming uniform subdivision; adaptive error control deferred |
| Area ratios called “high stress” or crack-tip detection | No constitutive model, loads, or solution was computed | Label area distortion as a geometric metric only |
| Open-boundary detection treated as physical fracture or damage intent | Geometry alone cannot identify design intent | Report boundaries, not diagnoses of damage |
| Reconstruction heuristics called guaranteed healing | Missing shape may be invented and a valid hole filled | No automatic hole filling or Poisson-solver claim |
| Sampled nearest-neighbor distance treated as exact Hausdorff fidelity | Finite samples do not bound continuous surfaces | Explicit sampled symmetric Hausdorff metric, cKDTree, no fidelity certificate |
| Viewer treats edge indices as vertex indices | Wrong defect locations are highlighted | Use endpoint lookup for polygonal edges and native curve sampling for CAD |
| A guessed SGS response and hardcoded endpoint | The client contract was never established; mock defects look like real model output | Explicit synthetic fixtures; no live inference adapter until a working contract exists |
| “Certified watertight” download | Geometric checks do not establish mechanical design safety or correctness | Explicit configured-policy result, provenance, limitations, and export gate |

## The integral-homology nuance worth preserving

The original idea of obtaining torsion from Smith invariants of the incoming boundary map is **not inherently wrong**. For a chain complex of free integer groups with d²=0,

```text
0 → H_k → coker(d_{k+1}) → im(d_k) → 0
```

splits as abelian groups because `im(d_k)` is free. Consequently the torsion of `H_k` is the torsion of `coker(d_{k+1})`, while its free rank is `n_k - rank(d_k) - rank(d_{k+1})`. The refactor preserves this valid reasoning, checks the chain condition, and replaces the untrusted reduction. A test with nonzero outgoing boundary and Z/6 torsion protects this point.

## Native CAD is an intentionally separate path

The adapter uses the installed, exercised `cadquery-ocp` bindings directly. This is an explicit dependency choice, not an assertion that the prototype's `pyoccad` package is fictional. Keeping the adapter isolated leaves room for a different kernel binding later without changing the algebra or UI.

Native import preserves the kernel's curved representation rather than rebuilding it from straight chords. STEP transfer itself can process/heal data; the initial report explicitly describes the imported shape. The adapter records units, input hash, kernel-binding version, acceptance policy, before/after state, and output hash.

Periodic seam edges can occur twice on one face. Sphere poles may use degenerate edges. Counting distinct neighboring faces would mislabel valid CAD in both cases. The native adapter counts occurrences and delegates geometric consistency to the kernel; a sphere and a torus are regression fixtures.

Existing solids are not globally disassembled and sewn. A hollow solid has two shells; constructing an independent filled solid for each would destroy its cavity. An existing cavity is tested and preserved. When unsewn faces require new solid construction, the prototype only accepts one unambiguous closed shell; multi-shell reconstruction needs a real nesting/containment analysis.

## Removed rather than cosmetically preserved

There is no fallback that fabricates SGS predictions, automatically fills a missing face, labels area distortion as stress, or silently turns a mesh into purported analytic STEP. There is no automatic native-face-to-simplicial conversion pretending to preserve topology. These are intentionally absent, not successful features omitted from documentation.

IGES export, adaptive curve-constrained refinement, native topology-preserving triangulation, generic shell nesting, and durable request orchestration are deferred. Adding thin wrappers with unverified semantics would make this work sample weaker.

## Audience-facing description

A defensible summary is:

> A tested geometry-integrity research prototype combining exact small-complex topology, conservative polygonal repair, and a native OCCT STEP verification path, with explicit provenance and acceptance policies.

Avoid claiming a general CAD certifier, production-scale homology solver, SGS integration, reconstruction of feature histories, or recovery of original design intent. The interesting engineering work is the careful separation of these concerns and the counterexamples used to test it.

## Upstream references

Accessed September 13, 2026. Online OCCT documentation can track a newer kernel than the installed binding; executable native tests target `cadquery-ocp 7.9.3.1.1`.

- SymPy Smith normal form: https://docs.sympy.org/latest/modules/matrices/normalforms.html
- OCCT Shape Healing (including seam handling, tolerances, and shape modification): https://occt3d.com/dev/doc/overview/html/occt_user_guides__shape_healing.html
- OCCT BRepCheck: https://occt3d.com/dev/doc/refman/html/class_b_rep_check___analyzer.html
- OCCT Sewing: https://occt3d.com/dev/doc/refman/html/class_b_rep_builder_a_p_i___sewing.html
- Official SGS-1 Space application: https://huggingface.co/spaces/spectral-labs/SGS-1/raw/main/app.py
