# B-rep and Mesh Refinement / Repair Methods

## Executive assessment

CAD Integrity Lab has a sound, deliberately narrow foundation: it separates polygonal combinatorial diagnosis from native CAD healing, preserves inputs, constrains tolerance-driven changes, verifies native STEP round trips, and declines to equate a passed check with recovered intent or physical certification. That is materially better than the usual “make it watertight” button, a device which has caused a fair amount of confident damage over the years.

The project does **not** yet cover several established method families needed for a broader repair or simulation-meshing claim: geometric self-intersection detection/resolution, topology-aware B-rep gap/overlap analysis, adaptive tolerance selection, trimmed-surface / periodic-seam meshing, constrained feature preservation, surface or volume Delaunay refinement, and error-estimator-driven adaptation. These are not omissions from the present stated scope; they are explicit capability gaps that should remain unadvertised until each has its own mathematical contract and verification plan.

The best next development is not a general “refine” command. It is a staged, evidence-producing workflow:

1. classify the representation and intended downstream use;
2. diagnose topology, geometry, tolerance, and intersection defects separately;
3. select an explicitly authorized repair family;
4. create a candidate without overwriting the source;
5. verify representation-specific invariants and preservation metrics; and
6. return an indeterminate / needs-review result where the evidence does not identify a unique legitimate repair.

That design preserves the project’s central intellectual advantage: a result can be useful without pretending to be an oracle.

## Existing mathematical coverage

| Area | Current coverage | Assessment |
|---|---|---|
| Polygonal topology | Exact F₂ and reference integer homology; Euler check; edge incidence; vertex links; orientability constraints | Strong for small, restricted cell complexes |
| Polygonal repair | Deterministic radius-to-representative welding; straight-edge deduplication; coherent loop reversal; nonmanifold / collapse rejection | Sound conservative repair for the declared model |
| Native B-rep | OCCT validity checks, ShapeFix / sewing, solid construction only under stated conditions, STEP round trip and preservation checks | Sensible kernel-mediated healing gate |
| Mesh refinement | Uniform conforming 1-to-4 triangle subdivision | Correct connectivity operation, not adaptive refinement |
| Mesh measures | Triangle quality, matching-connectivity area ratio, sampled point-set Hausdorff distance | Useful diagnostics; insufficient as geometric or PDE error guarantees |
| Local geometry | Bounded curve/surface least-squares root from a supplied guess | Correctly labelled local numerical demonstration |

The governing restrictions are correctly stated in the project mathematics: F₂ is not integer homology; b₁ is not a leak count; a combinatorial closed orientable 2-manifold is not an embedded CAD solid; a sampled Hausdorff distance is not a continuous surface bound; and a residual-checked root is not a global intersection solution. Those non-contracts should survive every extension.

## Method landscape

### 1. Native B-rep validity and healing

A production B-rep carries both topology (vertices, edges, wires, faces, shells, solids) and geometry (curves, p-curves, surfaces, parameter ranges, tolerances). Validity is therefore more than a graph condition. Representational-validity work gives sufficient conditions for ideal manifold B-reps, while CAD-kernel checks operationalize a subset of geometry/topology consistency checks.^1

The project’s native path already makes the right distinction. `BRepCheck_Analyzer`, interference checking, shell closure/orientation, solid ownership, positive volume, entity tolerances, and serialized STEP re-import test different propositions. No one of them implies the others. In particular, a valid B-rep does not establish preserved design intent, feature history, manufacturing suitability, or a bounded pointwise displacement.

Open CASCADE sewing illustrates why a single global tolerance should never be treated as an innocent knob. Its documented algorithm finds candidates, filters them, then merges; its working tolerance is merely a maximum distance considered, not a guarantee of merging. OCCT specifically warns that an over-large tolerance can sew an open shell incorrectly and cannot infer which small free boundary was intentional.^2 This supports the project’s current refusal to fill open holes silently.

### 2. B-rep defect classes and appropriate actions

| Defect / condition | Diagnostic evidence | Legitimate method family | What must remain unclaimed |
|---|---|---|---|
| Inconsistent orientation | coedge/wire direction, shell orientation, containment | orientation propagation; kernel solid-orientation logic | outwardness for abstract polygonal complexes |
| Small gap between intended mates | 3D curve/surface proximity plus p-curve / parameter evidence and feature context | local sewing or topology reconstruction under a budget | that proximity alone identifies intended adjacency |
| Overlap / duplicate face / T-junction | intersection and adjacency classification | local topology reconstruction; split / retrim / reparameterize | that vertex welding fixes curved topology |
| Missing face / hole | free-boundary loop, surrounding surface continuity, design intent | explicit surface reconstruction / patch fill, usually review-gated | recovered original geometry or intent |
| Sliver face / short edge | scale-aware thresholds, neighboring geometry, downstream meshing needs | defeaturing or local merge / retrim | tolerance change as a universal remedy |
| Self-intersection | robust surface/curve intersection and region classification | arrangement / Boolean / local reconstruction | that edge incidence or volume alone detects it |
| Periodic seam / degenerate pole | underlying surface and p-curve semantics | kernel-aware surface meshing and validation | treating it as a polygonal gap |

Published B-rep repair work uses iterative stitching and filling, often with adaptive rather than constant tolerances, precisely because gaps, overlaps, T-connections, and invalid topology are not equivalent failures.^3 Extended B-rep approaches retain both continuous and discrete representations to repair small gaps/overlaps while keeping the continuous input geometry untouched for meshing; that is a serious architecture, not merely a post-processing filter.^4

**Implication for this project.** Add geometric-topology repair only as a separately named native capability. It needs an evidence record of candidate pairs, their geometric discrepancy, tolerance justification, entities modified, and post-repair topology/geometry checks. A global “heal more aggressively” option is unsuitable: it removes the only honest part of the evidence trail.

### 3. Polygonal-mesh repair

Polygonal repair should be classified before it is attempted:

* **Connectivity repair:** merge duplicate vertices, orient faces, rebuild halfedge incidence, split or duplicate nonmanifold configurations when the target representation permits it.
* **Geometric repair:** detect intersections, split triangles along intersection curves, resolve the resulting arrangement, and handle numerical rounding.
* **Surface completion / reconstruction:** close holes, remove noise, or reconstruct missing regions. This is intrinsically assumption-laden; it changes the object rather than merely restoring a known representation invariant.
* **Quality repair:** remove or transform degenerate elements, edge-flip, smooth, relocate, or remesh while protecting features and preserving constraints.

CGAL’s current polygon-mesh material is a useful operational benchmark. It treats soup orientation and recovery of connectivity as separate steps; it identifies nonmanifoldness through local topology, including points whose infinitesimal neighborhood is not a disk. It distinguishes orientation, duplicated nonmanifold edges, self-intersection autorefinement, and removal of almost-degenerate faces.^5 This is broadly aligned with the project’s vertex-link check and conservative welding policy.

For self-intersections, the distinction between exact predicates and constructions matters. CGAL notes that autorefinement with exact predicates but inexact constructions can introduce new intersections through coordinate rounding; its iterative snap-rounding option may add subdivisions to prevent this.^6 A project that uses floating-point local intersections should therefore not advertise robust intersection repair. The required work is a different numerical regime, with exact/adaptive predicates, controlled constructions, and a post-rounding verification loop.

### 4. Mesh refinement versus mesh repair

Uniform 1-to-4 triangle subdivision preserves conformity across shared edges if the input connectivity is conforming. It does **not** improve a poor feature approximation, cure self-intersections, protect sharp features, adapt to curvature, establish a discretization error bound, or make a nonmanifold surface suitable for volume meshing. It multiplies the bookkeeping faithfully, which is useful but not miraculous.

Established refinement families include:

| Family | Primary objective | Main prerequisites / limits |
|---|---|---|
| Uniform subdivision | globally reduce edge length | needs conforming input; no quality or error objective by itself |
| Isotropic remeshing | target edge length and better element distribution | must protect curves / features; target may conflict with immutable long constraints |
| Constrained Delaunay refinement | size / shape / grading subject to input constraints | proof conditions matter; small angles and 3D slivers remain hard |
| Restricted Delaunay surface meshing | approximate a surface while controlling topology / facet quality | needs a suitable surface representation and sampling assumptions |
| Metric / anisotropic adaptation | align elements to solution or geometry metric | needs a well-defined metric or estimator; anisotropy is intentional, not bad quality |
| Optimization-based smoothing / flips / relocations | improve quality without changing intended constraints | must project to geometry and avoid inverted elements |
| Error-estimator adaptation | reduce a specified PDE discretization error | requires a solved PDE, estimator, marking policy, and convergence study |

Delaunay refinement has unusually strong theory for appropriate piecewise-linear inputs: it inserts points until size and quality constraints are met, with established bounds on element quality, edge length, and grading. But those guarantees are conditional; small input angles and 3D slivers are real limitations, not a missing command-line switch.^7 Shewchuk’s overview is refreshingly clear that good tetrahedral dihedral-angle guarantees remain difficult, and that algorithms can have geometric limits at sharp creases.^8

Gmsh provides a useful engineering model for the separate decisions involved: it starts bottom-up (curves, then surfaces, then volumes) to enforce conformity; supports point-, curvature-, distance-, and background-field sizing; and treats CAD and discrete models differently.^9 That bottom-up flow is relevant if this project ever meshes native B-reps: surface/curve provenance and periodic/seam constraints must survive into the generated mesh. A display tessellation is not enough.

### 5. Repair for simulation requires an additional contract

“Simulation-ready” combines at least four claims:

1. a valid geometric / topological representation;
2. a conforming discretization of the intended domain;
3. element quality appropriate to a named formulation and solver; and
4. accuracy evidence for that formulation, usually through convergence or an estimator.

The current package only establishes pieces of (1) for its two restricted paths and small diagnostic pieces of (2)/(3) for triangles. Its own documentation correctly says triangle area distortion is not stress, strain, or fracture mechanics. Extending the package should preserve that separation. A successful native repair plus a quality mesh report does not establish finite-element convergence; it establishes a candidate worth handing to a mesher or solver workflow.

## Gap analysis and recommended scope

### Keep as-is

* Keep native and polygonal paths separate. Arbitrary trimmed CAD faces must not be made into disk cells to manufacture Betti numbers.
* Keep the polygonal repair policy opt-in, deterministic, bounded, and immutable-input.
* Keep native repair copy-on-write, source/output protection, and serialized recheck.
* Keep `needs_review` as a first-class outcome; it is the proper result for ambiguous geometric intent.

### Add next: native repair evidence, not broader automatic healing

Add a read-only **native defect classifier** before adding a new mutation. It should report: free-boundary wires, face/edge/vertex ownership, shell connectivity, candidate proximity pairs, periodic / degenerate entities, intersections if the kernel can establish them, tolerances, and classification confidence. It should never infer an intended mate from Euclidean proximity alone.

Then add only one narrowly-scoped repair operation at a time, for example **local sewing of explicitly selected free-boundary candidates**. Its acceptance tests should include intentional nearby features that must not merge, periodic surfaces, cavity preservation, multiple solids, unit conversion, tolerance monotonicity, and STEP re-import. Store the selected entities and the full tolerance rationale in the report.

### Add later: topology-preserving surface meshing

If the goal is a mesh suitable for downstream numerical work, the next mathematical capability is a **native B-rep surface-meshing adapter**, not more display triangulation. It should:

* mesh curves first and share their discretization with adjacent faces;
* retain native face / edge / vertex provenance and parameter coordinates;
* explicitly represent periodic seams and degenerate poles;
* preserve declared sharp features and user constraints;
* report chordal deviation, angular deviation, edge length / sizing-field statistics, degeneracy, intersection status, and topology correspondence; and
* decline to report homology unless the construction actually preserves the relevant topology.

The interface should return a labelled mesh-evidence report, not a naked triangle array. That permits a caller to distinguish display output from a meshing result with stated geometric criteria.

### Add only with a downstream PDE use case: adaptive refinement

Adaptive refinement needs a stated objective. For geometry-only adaptation, use curvature / chordal / normal-deviation criteria with feature constraints. For PDE adaptation, require an elementwise error indicator or estimator, a marking rule (for example, bulk marking), a refinement / coarsening rule, solution transfer, and a convergence record. Without those, calling it “adaptive” means that the mesh got smaller somewhere, which is not the same thing.

### Do not add without exactness investment

* General self-intersection repair of arbitrary triangle soups.
* General Boolean/arrangement-based mesh repair.
* Automatic hole filling advertised as design recovery.
* General B-rep topology reconstruction from arbitrary malformed STEP.
* Guarantees of Hausdorff displacement, watertightness, CAD validity, or simulation readiness inferred from vertex welding or sampled distances.

These are feasible research and product areas, but each requires robust predicates/constructions, a carefully selected representation, hostile fixtures, and substantially stronger resource isolation than the present in-process numerical budgets.

## Verification matrix for future work

| Capability | Required mathematical tests | Evidence that is insufficient |
|---|---|---|
| Native local sewing | intentional and accidental near pairs; shell closure; periodic seams; cavity and multiple-solid preservation; round trip | entity count or a successful sew alone |
| Native surface mesh | exact shared edge nodes; face/edge provenance; seam / pole behavior; deviation criteria; no inverted or degenerate faces | display triangulation and visual inspection |
| Triangle-soup repair | exact / robust intersection fixtures; duplicate and nonmanifold cases; post-rounding recheck; selection semantics | no free edges or consistent normals alone |
| Isotropic remesh | target-size distribution; protected-feature preservation; manifoldness; geometric deviation | mean triangle quality alone |
| Delaunay / volume meshing | constraint recovery; domain conformity; sliver metrics; volume orientation; sizing and quality criteria | surface manifoldness alone |
| PDE adaptation | estimator identity, marking, refinement history, solution transfer, convergence in named norm | more elements or lower sampled geometric distance |

## Conclusion

The project has covered the conservative diagnostic-and-repair core well. It has **not** covered the full B-rep or mesh-repair landscape, and it should not imply otherwise. The most defensible expansion is a native defect-classification and local-sewing evidence path, followed by a topology-provenance-aware surface-meshing adapter. General mesh repair, geometric intersection resolution, and adaptive numerical refinement belong in later, separately qualified capabilities.

## Sources

1. T. Sakkalis, G. Shen, and N. M. Patrikalakis, “[Representational validity of boundary representation models](https://www.sciencedirect.com/science/article/abs/pii/S0010448500000476),” *Computer-Aided Design* 32(12), 2000.
2. Open CASCADE, “[Technical Overview: Sewing Algorithm and Tolerance Management](https://sso.opencascade.com/doc/occt-6.8.0/overview/html/technical_overview.html),” accessed September 2026.
3. P. S. Patel, “[Robust and efficient CAD topology generation using adaptive tolerances](https://onlinelibrary.wiley.com/doi/abs/10.1002/nme.2263),” *International Journal for Numerical Methods in Engineering*, 2008.
4. J. Chen et al., “[Automatic surface repairing, defeaturing and meshing algorithms based on an extended B-rep](https://engweb.swan.ac.uk/~cfli/papers_pdf_files/2015_AES_Automatic_surface_repairing_defeaturing_and_meshing.pdf),” *Advances in Engineering Software* 86, 2015.
5. CGAL Project, “[Polygon Mesh Processing: User Manual](https://doc.cgal.org/6.1/Polygon_mesh_processing/index.html),” version 6.1, accessed September 2026.
6. CGAL Project, “[Polygon Mesh Repair: User Manual](https://doc.cgal.org/latest/PMP_Mesh_repair/index.html),” version 6.2.1, accessed September 2026.
7. J. R. Shewchuk, “[Delaunay Refinement Algorithms for Triangular Mesh Generation](https://www.cs.cmu.edu/~jrs/jrspapers.html),” *Computational Geometry* 22(1–3), 2002; publication page and author-hosted materials.
8. J. R. Shewchuk, “[Delaunay Refinement Mesh Generation](https://www.cs.cmu.edu/~jrs/jrspapers.html),” PhD thesis, Carnegie Mellon University, 1997; author’s overview of 2D/3D limits and slivers.
9. C. Geuzaine and J.-F. Remacle, “[Gmsh reference manual](https://gmsh.info/dev/doc/texinfo/gmsh.html),” development documentation accessed September 2026.
10. Open CASCADE, “[BRepAlgoAPI_Check](https://dev.opencascade.org/doc/occt-7.7.0/refman/html/class_b_rep_algo_a_p_i___check.html),” reference manual, accessed September 2026.
