# Mathematical contracts and non-contracts

## The boundary of a boundary

For each modeled complex the integer matrices use the convention

```text
d_k : C_k → C_(k-1),     matrix shape = (n_(k-1), n_k)
d_(k-1) d_k = 0.
```

`C_0` uses unreduced homology: `d_0` has shape `(0, n_0)`. Construction checks integer coefficients, compatible dimensions, and the chain identity. Simplicial boundary signs follow canonical increasing vertex order. Geometry and the original orientation of a triangle are not part of that canonical simplex identity.

For a coefficient field K:

```text
b_k(K) = dim(C_k) - rank_K(d_k) - rank_K(d_(k+1)).
```

The default is **F₂**. It is exact, not floating-point rank. It is also not interchangeable with rational or integer homology in spaces with torsion. The real projective plane fixture has `(1,1,1)` over F₂, but integral free ranks `(1,0,0)` and H₁ torsion Z/2. Over Z the reference backend uses exact Smith invariants. Euler–Poincaré equality is checked for each homology report.

The sparse set-XOR reducer and dense SymPy SNF are reference algorithms with explicit resource limits, not a high-throughput algebra backend. Matrix sparsity is not a guarantee against fill-in or coefficient growth. A process deadline is still appropriate for hostile or difficult workloads.

## Homology is not a watertightness predicate

These are computed regression cases, with the surface/boundary complex as the object of study:

| Complex | (b₀,b₁,b₂), F₂ | Closed 2-manifold? |
| --- | --- | --- |
| Filled planar disk | (1,0,0) | No; has a boundary |
| Cube boundary with one face missing | (1,0,0) | No; has a boundary |
| Complete cube boundary | (1,0,1) | Yes |
| Triangulated torus surface | (1,2,1) | Yes |
| Two tetrahedron boundaries sharing one vertex | (1,0,2) | No; nonmanifold at the shared vertex |

The last example has no free edges. Merely counting two incident faces per edge is insufficient; the link of the shared vertex is disconnected. The analyzer checks vertex links as paths or cycles and rejects pinches.

A surface's b₀ counts surface components. A connected material body with an enclosed cavity can have two boundary components. Native solid count and surface component count are not synonyms.

The polygonal acceptance property checks a **combinatorial, closed, coherently oriented 2-manifold**. It does not check geometric self-intersections, guarantee planarity of every abstract polygon, resolve nesting, establish positive material volume, or certify a CAD embedding. Its name and report explicitly preserve that distinction.

## Orientation is not outwardness

For an edge shared by faces f and g with existing coedge signs s and t, coherent orientations require

```text
x_g = -s t x_f,     x_f ∈ {−1,+1}.
```

The algorithm propagates these constraints across every component and checks already visited neighbors for contradictions. Nonorientable fixtures produce conflicts rather than an arbitrary answer. Reversing a face changes an ordered wire `[e₁,…,eₙ]` to `[−eₙ,…,−e₁]`; negating without reversing is not a valid traversal.

A connected orientable component admits two global orientations. Choosing outward material normals requires embedding, containment, and solid semantics, which the polygonal propagation does not claim. Existing CAD solids and newly constructed single-shell native solids use the kernel's solid-orientation machinery.

## Why arbitrary CAD faces do not go straight into d₂

`PolyhedralBRep` represents each face as one abstract polygonal disk with an ordered, simple outer loop and straight edges. Its cellular boundary operator follows that contract.

A native face can instead be trimmed by outer and inner wires, span a periodic parametric surface, or use seam identifications and degenerate edges. Counting every such face as one disk cell changes the topology being modeled. Likewise, independently tessellated CAD faces duplicate shared vertices; their triangle union is not automatically a conforming surface complex.

For this reason native reports return `homology = null` with a stated reason. `tessellate_for_display` keeps per-triangle face provenance but labels its mesh display-only. Computing meaningful native Betti numbers requires a topology-preserving cell decomposition or conforming tessellation with native edge/vertex provenance. Euclidean welding alone is not a proof: nearby but distinct material boundaries can be merged accidentally.

## Repair and geometry budgets

The polygonal zipper uses deterministic representative-radius clustering, not the transitive closure of distance ≤ tolerance. Every moved vertex must lie within the displacement budget of the chosen representative. It then merges duplicate **straight** edges, remaps oriented coedges, and rechecks topology. This endpoint-based edge identity must not be generalized to curved CAD: two different curves may have the same endpoints.

A native entity tolerance is an allowance for geometric/topological consistency, not a measured displacement field or a Hausdorff-distance certificate. ShapeFix can alter geometry and topology; the adapter checks the result again and caps actual resulting entity tolerances. Count, area, and volume preservation checks are useful guards but do not prove pointwise equivalence. There is no claim that the configured tolerance proves a bound on all surface motion.

## Persistence and numerical geometry

Persistence uses filtration order `(birth time, dimension, vertex tuple)` so faces precede cofaces at ties. Reduction pairs births with deaths; intervals are half-open `[birth, death)`. `None` denotes an essential class. Zero-length intervals are omitted unless requested. The triangle-loop regression creates H₁ at time 2 and kills it with a filled face at time 3.

The local curve/surface solver is bounded least squares with a checked residual. It finds, at most, one local intersection from a supplied initial guess. The parametric mesher handles an untrimmed rectangular domain. Conforming uniform subdivision preserves shared edges but does not implement a posteriori error control. Sampled nearest-neighbor Hausdorff distance is a distance between point sets, not a guaranteed surface bound. Triangle area distortion is not stress, strain, or fracture mechanics.
