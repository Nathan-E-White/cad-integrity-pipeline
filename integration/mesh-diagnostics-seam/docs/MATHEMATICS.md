# Mathematical definitions and limitations

## Triangle mean-ratio shape quality

For edge lengths a,b,c and unsigned area A:

    q = 4 sqrt(3) A / (a² + b² + c²)

For nondegenerate triangles, q lies in (0,1], with q=1 for an equilateral triangle. The implemented value is clipped to [0,1] for floating-point roundoff, and explicitly set to zero for triangles classified as degenerate by the selected tolerance.

The supplied code's `ideal_area` was

    sqrt(3)/4 * ((a²+b²+c²)/3).

Therefore its `area / ideal_area` simplifies to q above. This is a useful metric. It is **not signed**, and reversing the vertex ordering does not change it. It is not the same thing as a solver's signed scaled Jacobian. A surface triangle embedded in R³ has a 3×2 affine parameterization derivative; a signed scalar area measure additionally requires an oriented reference frame/normal.

## Radius aspect ratio

Let s=(a+b+c)/2, circumradius R=abc/(4A), and inradius r=A/s. Then

    radius_aspect = R/(2r) = abc*s/(8A²) = abc/(8*r*A).

Equilateral = 1; larger values indicate worse shape by this metric. The supplied executable aspect-ratio expression already implements this relationship for nondegenerate triangles. Its intermediate explanatory equality involving only `abc/(8*r)` was dimensionally inconsistent. The refactor keeps the useful metric, fixes the naming/comments, and replaces absolute epsilon substitutions with explicit degeneracy handling.

Degenerate triangles have infinite/undefined radius aspect internally. JSON never receives Infinity or NaN: the maximum over a set containing degenerate triangles is represented as null with a failing status and a description. The mean is explicitly labeled as the mean over finite triangles, rather than hiding excluded elements.

## Numerical scaling and degeneracy

Edge vectors are computed in float64. Each triangle's three edge vectors are divided by their common largest absolute component L∞ before cross products/norms are evaluated. Thus ordinary global unit scaling does not determine whether a triangle is labeled degenerate.

The test is

    |AB×AC| / L∞² <= relative_area_tolerance,

with zero-length elements separately caught. The default tolerance is 1e-12. It is a policy choice, not a CAD-modeling tolerance in millimeters. This reference implementation does not impose an absolute minimum physical element area. Coordinate differences that themselves overflow float64 raise an explicit error; rebase/rescale in the authoritative geometry layer.

## Topology

One lexicographically sorted undirected edge-incidence table provides unique edges, incident-face counts, CSR offsets and source face IDs. Direction signs are retained separately to identify a two-face edge whose faces traverse it in the same direction.

For a conforming triangle surface, count=1 identifies a boundary edge, count>2 identifies a non-manifold edge, and count=2 is only an edge-incidence condition. A manifold with boundary legitimately contains count=1 edges. The audit policy decides whether closure is required.

Two closed tetrahedral shells sharing one vertex demonstrate why count=2 everywhere is insufficient: every edge has two incident faces, but the shared vertex has a disconnected link. This case is included in the tests, and full manifold validation stays not_checked.

Repeated-index triangles are reported and excluded from the edge table, avoiding self-edge/incidence artifacts. Duplicate triangles are reported as ALL members of duplicate groups; they are not silently deleted. Geometrically collapsed triangles with three distinct indices remain part of the combinatorial table and are also flagged by quality diagnostics. This audit does not perform geometric welding.

Boundary **edges**, connected boundary components and closed boundary **loops** are distinct quantities. This implementation computes the first only. An arbitrary defective boundary graph may contain branches, so simply dividing edge count or counting connected components does not establish loop count.

## Orientation

A count-two shared edge with equal direction signs is a local winding conflict. It does not identify which of its two faces is globally wrong. Coherent local winding does not establish outwardness. Nonorientability/global propagation is not tested here.

With per-triangle reference normals, the implementation additionally computes the cosine between each triangle normal and its reference. A negative cosine means opposition to that reference, not necessarily a topological inversion. Degenerate or near-orthogonal comparisons are unresolved. Supply references in the same coordinates, triangle ordering and geometry revision. This comparison is not called a signed Jacobian.

## Not computed

Vertex-link manifoldness, self-intersections, global outwardness, boundary loop counts, connected-component/Betti analysis, solver-specific Jacobians, curved/high-order element validity, native B-Rep validity, or mesh suitability for a particular physical model. The UI must not synthesize passing values for these checks.

## Reference context

The Cubit triangular metrics documentation distinguishes area, shape, scaled Jacobian and relative-size measures. The definitions above are explicitly chosen and tested; they are not presented as exact reproductions of every CUBIT/Verdict solver metric. See `REFERENCES.md`.
