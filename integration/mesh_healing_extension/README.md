# Mesh-healing extension

This extends the Python supplied in the conversation. All original public classes
and function names are retained. Numerical/topology repair remains in
`mesh_healing_engine.py`; real CAD exchange and UV evaluation live in the small
companion `mesh_export.py`. The original nine-vertex fixture and IGM example are
retained in `example_pipeline.py` alongside a deliberately unstitched two-quad case.

**Delivered geometry standard: STEP.** No ONNX or ML runtime is needed. STEP is
written with CadQuery/OpenCascade, then reimported and checked before the final
file is committed. The optional JSON sidecar retains the original UV chart and
mesh indexing. The JSON schema is local to this package, not a claimed CAD standard.

## Run

From the extracted directory, with Python 3.10 or later:

```bash
python -m pip install -r requirements-dev.txt
python example_pipeline.py --output generated --step
python -m pytest -q
```

For just the numerical core and JSON/UV example, without the CAD dependencies:

```bash
python -m pip install -r requirements.txt
python example_pipeline.py --output generated
```

An editable installation is also supported:

```bash
python -m pip install -e '.[step,test]'
mesh-healing-demo --output generated --step
```

The declared dependency ranges are compatibility targets, not a tested version
matrix. The actual successful environment is recorded in
`generated/test_environment.json`: Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0,
pytest 9.0.2, CadQuery 2.8.0, and cadquery-ocp 7.9.3.1.1.

## Files and generated examples

| File | Purpose |
|---|---|
| `mesh_healing_engine.py` | Original APIs, cotangent FEM assembly, pre-pruner, reusable harmonic system, quad-strip tracer, IGM MILP, cross-field smoother |
| `mesh_export.py` | Actual STEP writer and reimport checks, JSON sidecar, piecewise-affine UV-to-XYZ evaluator |
| `example_pipeline.py` | Runnable original example, affine/soft updates, contamination repair, seam stitching, exports |
| `tests/test_mesh_healing.py` | 69 numerical, topology, compatibility, and export test cases |
| `generated/patch_uv.step` | Flattened UV chart as a real open CAD surface |
| `generated/patch_xyz.step` | Original piecewise-linear 3D patch as a real open CAD surface |
| `generated/patch.mesh.json` | Indexed polygons/triangles, original vertex IDs, XYZ, UV, units, and bounds |
| `generated/raw_mesh.npz` | The original nine-vertex geometry, saved before preprocessing |
| `generated/run_summary.json` | Numerical results and STEP reimport measurements |
| `generated/test_results.xml` | Machine-readable pytest results |
| `generated/test_output.txt` | Test execution summary |

The generated STEP examples contain eight triangular faces in an open shell, not
a manufactured solid. The actual example files use OpenCascade's AP214 schema.
Exporter configuration is delegated to the CAD kernel; no handwritten STEP
header or standalone Cartesian-point list is presented as a surface model.

## 1. Cotangent harmonic maps

For an edge `(i,j)` with opposite angles `alpha` and `beta`, the unweighted
assembly is

```text
W_ij = 1/2 * (cot(alpha) + cot(beta))
L    = diag(W * 1) - W
L_II X_I = -L_IB X_B,       X = [u v]
```

A boundary edge receives one triangle contribution. The scalar cotangent is
computed by `dot(a,b)/norm(cross(a,b))` on scale-normalized edge vectors. There is
no additive epsilon that silently changes the geometry of a degenerate triangle.
Degenerate input is instead pruned explicitly or rejected. `compute_cotangent_weights`
now returns a CSR **weight matrix W**. `compute_cotangent_laplacian` returns the
positive-semidefinite **stiffness matrix L**; they are not the same object.

The matrix is assembled over a common triangulation of the polygons. In
particular, a quad's triangulation diagonal contributes to the operator even
though it is not a polygon-boundary edge in `engine.adjacency`. The original 0--2
diagonal is retained when valid; a valid alternative is used for a concave quad.
Simple polygons also have a projected ear-clipping path. This is not a polygon
with holes triangulator, and strongly warped or self-intersecting polygons are
outside its contract. The selected triangulation defines the actual discrete
surface used for harmonic mapping, interpolation, and export.

The homogeneous Dirichlet problem does not need a mass matrix on the RHS. This
is the weak/FEM operator, not an API for a mass-normalized general Poisson solve.

### Geometry-aware is not a blanket shape or injectivity guarantee

Signed cotangents are retained. Cotangent weights may be negative on a
non-Delaunay triangulation. The assembled FEM energy remains positive
semidefinite, but the positive-weight convex-combination argument does not apply
in general. A fixed boundary can also impose substantial distortion.

The solver therefore checks each triangle's UV orientation and collapse, and
reports the largest singular-value ratio of its UV Jacobian. The default export
and solve convention is positive/CCW UV orientation. A deliberately mirrored
chart can be solved with `system.solve(..., orientation=-1)`, but the provided
JSON/STEP-with-UV exports require the positive convention.

Local positive triangle areas are **not** a global overlap certificate. There is
no boundary self-intersection test, global triangle-overlap audit, intrinsic
Delaunay remesher, ARAP optimization, or SLIM barrier in this extension. Invalid
local maps raise rather than silently switching back to Tutte weights.

### Compatibility

```python
# Preferred: existing helper, now with the geometry needed for cotangents.
uv = parameterize_macro_patch(
    internal_vertices, boundary_mapping, engine.adjacency,
    mesh_engine=engine,
)
```

The old graph-only three-argument call still works, but emits a `FutureWarning`
and retains uniform/Tutte weighting. Angles cannot be inferred from adjacency
alone. `weighting='cotangent'` without geometry is an error. Explicit
`weighting='uniform'` remains available. For a macro-patch within a larger engine,
pass `face_ids`; the internal/boundary union must exactly cover that selected
patch, not silently drop incident faces from an unspecified domain.

## 2. Real STEP and explicit UV-to-XYZ evaluation

```python
from mesh_export import export_step, export_frontend_json, UVSurfaceMap

# The parameter plane embedded in CAD coordinates.
export_step(engine, 'generated/flat.step', coords_2d=uv,
            space='uv', units='mm', uv_scale=1.0)

# The corresponding original piecewise-linear spatial surface.
export_step(engine, 'generated/surface.step', coords_2d=uv,
            space='xyz', units='mm')

# Preserve both coordinate sets, parent faces, indexing and parameter bounds.
export_frontend_json(engine, 'generated/patch.mesh.json', uv, units='mm')

surface_map = UVSurfaceMap(engine, uv)
xyz = surface_map.sample([[0.25, 0.25], [1.75, 1.75]])
```

`uv_scale` is an explicit physical-units-per-parameter-unit choice. UV is not
silently normalized to `[0,1]`, which would lose the meaning of integer-grid
coordinates. The `units` argument declares the XYZ coordinate unit and the physical
unit used for flattened UV geometry. Internal CAD construction uses millimeters,
with explicit conversion when a different output unit is requested.

The exporter builds planar CAD faces from the triangulation, sews shared edges
when requested, writes STEP, reimports it, and verifies B-rep validity, triangle
face count, total surface area, and bounding box. It rejects excessively small
triangles relative to the sewing/kernel tolerance. Writes use temporary files
and atomic replacement. Open surfaces stay open; no solid is falsely declared.

**A faceted STEP is not a fitted NURBS reconstruction, analytic feature recovery,
or a parametric CAD feature history.** The STEP face parameter frames are chosen
by the CAD kernel and do not preserve your original global UV chart. The sidecar
is the explicit correspondence source; reimported STEP face order is not promised
to match original triangle order.

`UVSurfaceMap` uses triangle barycentric interpolation, exactly for this
piecewise-linear model up to numerical roundoff. For high-throughput front-end
queries, use a BVH/picking operation to obtain triangle IDs and call
`evaluate(queries, triangle_ids)`. The included `locate()` scans the triangles
and is intended for small examples. It rejects outside points and rejects a
query with overlapping candidate triangles that disagree on XYZ. Multiple
charts need an external chart ID/atlas; they must not be implicitly mixed.

`export_mock_step_structure(filename, uv)` is retained as a deprecated adapter
that now writes real planar STEP faces. Its original invalid/point-only text
output is not retained as a misleading file format.

## 3. Pre-pruner and conservative nonmanifold seam handling

```python
from mesh_healing_engine import MeshHealingEngine, prune_motorcycle_graph

engine = MeshHealingEngine(vertices, faces)
pruned = prune_motorcycle_graph(
    {}, 0.0, {}, mesh_engine=engine, stitch_tolerance=1e-5,
    return_report=True,
)
repair = pruned.preprocessing
boundary = repair.remap_constraints(original_boundary_constraints)
```

This path now performs actual geometry/topology preprocessing, not a print
statement suggesting that stitching could happen later. It removes explicitly
reported duplicate/degenerate faces, splits disconnected vertex fans, orients
faces consistently, stitches matching boundary edges, compacts unused vertices,
and rebuilds connectivity. The raw caller arrays were copied on construction;
the example also saves raw geometry separately before any repair.

The complete pre-pruner is transactional: unsupported topology or a later
trajectory-remapping failure leaves the caller's engine unchanged. Its provenance
is one-to-many because splitting a bowtie duplicates a vertex. Welded constraints
are remapped; contradictory UV assignments on vertices that become one vertex
raise an error instead of choosing a value silently.

Boundary stitching uses a KD-tree candidate search on boundary-edge midpoints,
then checks both endpoint distances in Euclidean space. It requires a unique
automatic partner, limits the diameter of every merged vertex cluster, and
validates each two-endpoint weld for face degeneracy, duplicate cells, edge
incidence, vertex links, and orientability. Coordinates and face IDs use the
same actual representatives. There is no `vertices[:number_of_unique_hashes]`
shortcut and no global merge of all nearby coordinates.

An inward-direction heuristic rejects likely coincident/overlapping sheets.
`non_manifold_stitching(..., seam_pairs=[((u,v),(a,b)), ...])` allows caller-selected
boundary pairs to bypass automatic partner search and that heuristic, but never
bypasses distance or topology checks. Coincidence alone cannot establish the
semantic ownership of a seam; the auto-repair is deliberately conservative.
Explicit pairs that become ambiguous after bowtie splitting are rejected.

**Unsupported cases are reported, not guessed:** three or more sheets on one
edge, missing seam subdivisions/T-junction edge insertion, geometric intersection
repair, arbitrary shell ownership, and filling true holes. Open boundaries are
not treated as inherently defective. Bowtie fan splitting separates sheets; it
is not equivalent to stitching unrelated sheets together.

When tracks already exist, pass their endpoint mapping:

```python
old_edge_vertices = tracer.edge_vertex_map()
result = prune_motorcycle_graph(
    trajectories, 0.05, initial_lengths,
    mesh_engine=engine,
    edge_vertices=old_edge_vertices,
    protected_tracks={critical_track_id},
    return_report=True,
)
trajectories = result.trajectories
```

The pruner remaps edge IDs and recomputes their Euclidean endpoint lengths.
An old half-edge integer by itself contains insufficient information for a safe
remap. A vertex split may require retracing, in which case the operation fails
before committing. Existing cached tracers are invalidated after preprocessing.
Remapping footprints does not extend old trajectories through a newly connected
seam; rebuild/retrace when the propagation domain changes.

**Deleting a track is not a macro-patch cell merge.** The supplied code had no
patch-to-track incidence or global T-mesh update model, so this extension does
not invent one. The fine mesh remains intact when a graph feature is pruned.
Protect structural tracks explicitly and rebuild any application-specific
macro-patch/IGM constraints after changing the feature graph. The original
edge-length-sum pruning metric is retained; it is not a geodesic flight-time
measure for the opposite-edge strip tracer.

## 4. Contamination via linear/affine system updates

Here, contamination means caller-identified unreliable UV observations or
unreliable face contributions. This is an explicit interpretation of the request,
not an automatic detector, ownership-type system, or geometric outlier classifier.

### Reuse a Dirichlet factorization

```python
system = engine.prepare_harmonic_system(internal, list(boundary))
uv = system.solve(boundary)
uv_moved = system.solve(changed_boundary_values)  # same boundary IDs
```

For fixed geometry, topology, coefficients and constrained IDs, only
`-L_IB @ boundary_values` changes. `u` and `v` are solved as two RHS columns using
one cached SuperLU factorization. The map is affine-equivariant under a common
affine transformation of the boundary values, provided the requested orientation
remains valid.

### Soft observations and bounded-rank updates

```python
from mesh_healing_engine import SoftConstraint

uv = system.solve(boundary, soft_constraints={
    interior_vertex_id: SoftConstraint(target=(1.12, 0.94), weight=0.1),
})

# This is the whole current set, not a delta: dropping it removes the observation.
uv_without_observation = system.solve(boundary, soft_constraints={})
```

For selector matrix `S`, nonnegative diagonal `C`, and target rows `Y`:

```text
(A + S C S^T) X = -L_IB B + S C Y
U = S sqrt(C)
Z = A^-1 U
X = A^-1 rhs - Z (I + U^T Z)^-1 U^T A^-1 rhs
```

Small anchor sets use this Woodbury expression without forming `A^-1`. The
small dense system uses a Cholesky factorization; changed targets with unchanged
IDs/weights reuse the same update. Larger updates, ill-conditioned small systems,
or a failed backward-error check fall back to a separate sparse factorization.
There is no claim that SciPy incrementally updates its existing SuperLU factors.

The default maximum low-rank anchor count is 32; its dense workspace is roughly
`N_internal * rank`, not `N_internal^2`. Counters expose full factorizations,
low-rank preparations, the most recent method, and residuals.

### Freeze trusted UV data, reconstruct only flagged values

```python
repaired = engine.repair_contaminated_coordinates(uv_with_bad_values, bad_vertex_ids)
```

Every unflagged coordinate is a hard constraint in this localized reconstruction.
This avoids moving trusted regions in response to the contaminated observations.
It cannot compensate for incorrect trusted boundary data or repair the 3D shape.

### Confidence-weighted element contributions

```python
weighted_system = system.with_face_confidence({face_id: 0.25})
weighted_uv = weighted_system.solve(boundary)
```

A nonnegative confidence multiplies the **whole triangle FEM energy**, not a
hand-selected set of possibly negative cotangent edges. Confidence zero removes
that face's stiffness contribution; positive values scale it. This preserves
positive semidefiniteness, but can disconnect/unanchor a domain at zero confidence.
Every component containing an unknown must have a Dirichlet anchor; failures are
reported rather than patched with arbitrary diagonal entries.

Face-confidence changes explicitly rebuild/refactor the stiffness system. They
are not incorrectly labeled RHS-only updates, nor silently treated as low-rank
anchor changes. Treat confidence as a modeling decision: downweighting geometric
stiffness does not automatically recover the geometry that should have been there.

Geometry/topology edits invalidate harmonic systems, tracers, and UV evaluators.
Version checks plus geometry/connectivity fingerprints also catch in-place edits
to the legacy public arrays. They require new systems, and usually constraint
remapping, rather than reuse of stale matrix entries.

## Other preserved components

`Vertex`, `HalfEdge`, `Face`, and `MotorcycleGraphTracer` remain. `from_mesh()` now
builds a consistent half-edge structure for an oriented all-quad mesh. Boundary
exit edges and face-interior crossings are tracked. `compute_graph()` resets
state by default so repeated calls are repeatable. **The algorithm remains a
deterministic sequential quad-strip approximation**: not simultaneous geodesic
event scheduling, not a full continuous cross-field motorcycle graph, and not a
proof of valid T-junction macro-patches. The cross field and tracer are not
presented as a fully coupled remesher.

`solve_igm_quantization()` retains the original L1 mixed-integer objective,
positive integer lengths, and opposite-side sum constraints. Its implementation
uses sparse matrices, accumulates repeated segment coefficients, validates IDs
and bounds, checks solver status, rounds instead of truncating, and rechecks
integrality and patch equalities. A valid integer length vector does not prove
that an independently supplied T-mesh is watertight or geometrically injective.

`CrossFieldOptimizer` normalizes input normals, estimates sharp-edge tangents from
intersecting face planes, includes normal-aligning frame transport, and adds a
gauge anchor per effective connected component. It now returns the complex
4-representation, with optional magnitude normalization. Zero-magnitude directions
are reported instead of divided by zero. Antiparallel adjacent normals have
ambiguous minimal-rotation transport and require an orientation repair. This is
still a relaxed linear field smoother, not a prescribed-singularity optimizer.

## Verification and remaining engineering boundaries

The included run passed **69 tests**, including actual STEP reimport checks in
millimeters, meters, and inches. Test coverage includes cotangent signs/symmetry/
PSD, quad diagonals, scale invariance, planar affine precision, boundary-only
patches, unanchored components, Woodbury-vs-direct agreement, removal of soft
anchors, invalidation, seam remapping, bowtie fans, failed-repair rollback,
legacy calls, IGM integrality, cross-field transport, UV interpolation, and STEP
geometry/units.

On the supplied noisy grid, the center is approximately
`(0.9999563025210634, 1.0000686696947936)`. It need not be exactly `(1,1)` because
cotangents incorporate the displaced 3D geometry. The sample affine-boundary
update error was about `1.11e-16`. The separate seam fixture welded two duplicated
vertices, reducing eight vertices to six without closing its genuine perimeter.

These tests are fixtures and numerical consistency checks, not formal proofs or
qualification for arbitrary CAD data. There is no global self-intersection audit,
CAD semantic feature reconstruction, global atlas/seam consistency engine, or
certification against multiple commercial CAD importers. OpenCascade reimport
validity is a useful check but is not an independent standards-conformance suite.

For large meshes, conservative stitching currently rebuilds/checks candidate
meshes globally for each proposed seam. Its worst-case validation work scales
with the number of candidate welds times mesh size. It prioritizes auditability
and safe rejection over production-scale local topology editing. Fingerprints
also cost a mesh scan per cached-object use. Harmonic systems and CAD exchange
are not generally thread-safe; use independent systems per worker. The STEP
exporter serializes its own exchange calls because OCCT has global settings, but
cannot coordinate unrelated CAD code outside this module.

## Primary references

Implementation choices and API contracts were checked against:

- Geometry Central, cotangent weights and weak Laplacian:
  https://geometry-central.net/surface/geometry/quantities/
- libigl tutorial, harmonic parameterization and FEM operators:
  https://libigl.github.io/tutorial/
- SciPy `splu`, reusable sparse LU solves:
  https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.splu.html
- SciPy `milp`, domain constraints and solver status:
  https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html
- OpenCascade `STEPControl_Writer`:
  https://occt3d.com/dev/doc/refman/html/class_s_t_e_p_control___writer.html
- CadQuery import/export, STEP and physical units:
  https://cadquery.readthedocs.io/en/latest/importexport.html
- ONNX concepts, explaining the separate computational-graph role of ONNX:
  https://onnx.ai/onnx/intro/concepts.html
