# NURBS Core Engine

A hardened revision of Nathan White's two-module geometry prototype. It retains
`NURBSCoreEngine.py` and `STLReader.py`, the original public class names, and the
STL → local features → RANSAC → geometry cards → STEP pipeline. `main.py` is now
both a command-line entry point and a callable orchestration layer.

**Scope:** analytic NURBS evaluation and approximate plane/cylinder surface
extraction. This is not a general STL-to-NURBS fitter, a topology reconstruction
system, or a watertight-solid generator. STEP output contains bounded surface
fragments constructed and checked by Open CASCADE.

## Install and run

Python 3.11 or newer is the declared target. The delivered revision was executed
on Python 3.13.5; see [VALIDATION.md](VALIDATION.md) for the exact tested environment.

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1

# Core numerics, STL ingestion, and JSON output:
python -m pip install -e .

# Add the optional Open CASCADE backend and test tooling:
python -m pip install -e '.[step,dev]'
```

The modules can also remain beside your application's `main.py`. Installing the
project is not necessary to import them, but NumPy and SciPy must be available.
OCP is imported only when STEP export is requested.

A deterministic, deliberately simple mesh fixture is included. Its coordinates
are to be interpreted as millimetres:

```bash
python main.py examples/plane.stl --units mm --cards plane.geometry.json

# Requires the [step] extra; use a different JSON filename to avoid overwriting:
python main.py examples/plane.stl --units mm \
  --cards plane.step.geometry.json --step plane.step --seed 42

# Installed command and inspection-only reader:
stl-to-cad --help
python STLReader.py examples/plane.stl
```

For your own scan:

```bash
python main.py noisy_scan_input.stl --units mm \
  --cards extracted.geometry.json --step extracted.step \
  --neighbors 24 --spatial-tol 0.01 --normal-tol-deg 3 \
  --curvature-threshold 0.05 --seed 42
```

These tolerances are starting examples, not calibrated defaults for every scan.
The application does not guess units. Distance tolerances, neighbor radii, and
fit RMSE thresholds use input length units; curvature thresholds use inverse
input length units. STEP geometry is explicitly converted to millimetres.

Existing outputs are refused unless `--overwrite` is supplied. The input and
output paths must be distinct. Output directories must already exist. CLI exit
codes are 0 for success, 2 for input/configuration/I/O errors, and 3 for STEP or
optional-backend failures. Native Open CASCADE transfer statistics may still
appear on the process console.

## Existing-style integration

The important calls in the supplied `main.py` remain available. The two changes
needed for STEP are installing the backend and declaring units:

```python
from NURBSCoreEngine import (
    CADGeometryCardEngine,
    RANSACPrimitiveClassifier,
    STEPGeometryExportEngine,
)
from STLReader import PointCloudGeometryEstimator, STLReader

points, face_normals, faces = STLReader.load_stl("noisy_scan_input.stl")

estimator = PointCloudGeometryEstimator(k_neighbors=15)
normals, curvatures = estimator.estimate_features(points)

segmenter = RANSACPrimitiveClassifier(
    spatial_tol=0.01, normal_tol_deg=3.0, random_state=42,
)
primitives = segmenter.segment_primitives(points, normals, curvatures)

card_engine = CADGeometryCardEngine(precision=4, length_unit="mm")
geometry_card = card_engine.compute_cards(primitives, points)
card_engine.write_json(geometry_card, "extracted.geometry.json")

step_engine = STEPGeometryExportEngine()
step_engine.write(geometry_card, "extracted.step")
# export(geometry_card) still returns the STEP string without writing a file.
```

For STL input, prefer the richer interface so winding-derived vertex normals
can guide orientation and diagnostics remain accessible:

```python
mesh = STLReader.read("noisy_scan_input.stl")
features = estimator.estimate(
    mesh.points, reference_normals=mesh.vertex_normals(),
)
segmentation = segmenter.segment(
    mesh.points, features.normals, features.curvatures,
)

print(mesh.report)
print(features.valid_mask.sum(), len(features.valid_mask))
print(segmentation.unassigned_indices)
```

A seeded classifier advances its local generator across calls. Construct a new
classifier with the same seed for an independent repeat. Do not share one
mutable generator between concurrent tasks expecting reproducibility.

The orchestration layer is reusable without running its CLI:

```python
from pathlib import Path
from main import PipelineConfig, run_pipeline

result = run_pipeline(PipelineConfig(
    input_path=Path("noisy_scan_input.stl"),
    cards_path=Path("extracted.geometry.json"),
    step_path=Path("extracted.step"),
    units="mm",
    seed=42,
))
print(result.primitive_count, result.unassigned_count)
```

## Numerical and data contracts

### STLReader

`load_stl` returns three arrays: vertices `(V, 3)`, face normals `(F, 3)`, and
integer faces `(F, 3)`. `read` returns the same arrays in `MeshData`, together
with an `STLReadReport`. Face normals are recomputed from triangle winding for
both encodings. Stored normals and vendor color/attribute bytes are discarded.

Binary ingestion uses 50-byte little-endian records. Auto-detection checks the
file-size/facet-count relationship before looking for `solid`, which may also
occur in binary headers. ASCII ingestion checks the facet grammar, accepts
multiple complete solid blocks, and rejects malformed/truncated data. Explicit
`format="ascii"` or `format="binary"` is available for ambiguous files.

Default guards are 2,000,000 facets and 256 MiB input size. These bound input,
**not peak process memory**: triangle arrays, deduplication, and indexing create
additional allocations. Exact duplicate vertices are merged; near duplicates
are not welded. Degenerate facets are dropped and counted by default, or can
be rejected with `degenerate_policy="error"`. An empty valid STL returns empty
arrays with consistent shapes; the full feature pipeline needs more samples.

### Point-cloud features

Feature estimation uses batched `scipy.spatial.cKDTree` queries rather than an
all-pairs distance matrix. Each local fit is centered at the actual query,
scaled by neighborhood size, and solved with weighted quadratic least squares.
Rank and condition checks prevent failed fits from silently becoming planes.
`k_neighbors` includes the query point and must be at least six. Query workers
parallelize the tree queries, not the entire per-point fitting loop.

`FeatureEstimationResult` exposes normals, principal curvatures, validity, fit
RMSE, condition number, and neighbor count. A failed fit may retain a PCA normal,
but its curvatures are NaN and `Valid` is false. `max_radius`, `max_fit_rmse`, and
`max_condition` provide explicit rejection controls. RMSE is a local graph-fit
residual, not a certified point-to-surface error or curvature uncertainty.

Principal curvatures are ordered **algebraically**, not by absolute value.
Reversing a normal reverses both curvatures and swaps their order. The default
centroid orientation is only a heuristic; it is not reliable global orientation
for concave/open surfaces. Supply reference normals or a known scanner viewpoint
when available. Winding-derived normals are orientation hints and can average
across sharp edges; this module does not repair inconsistent mesh winding.

### NURBS evaluation

`find_span_vectorized`, `basis_derivatives_vectorized`, and
`evaluate_surface_geometry` are retained. `evaluate_surface` returns a richer
`SurfaceGeometry` with mean/Gaussian curvature and validity.

A four-component control point means **`(x*w, y*w, z*w, w)`**, not `(x,y,z,w)`.
Use `NURBSCoreEngine.to_homogeneous(cartesian_control_points, weights)` to convert.
Three-component nets use unit weights. Weights must be positive. Knot vectors,
control-net dimensions, multiplicities, and parameter domains are validated.

Parameter vectors describe a tensor-product grid, not paired samples. The
upper endpoint is evaluated exactly. At interior repeated knots the selected
span gives a right-hand value/derivative; at the upper endpoint it is left-hand.
Derivatives above the polynomial degree are zero. A valid parameterization at
one side of a repeated knot does not imply smoothness across that knot.

The evaluator retains local-support tensor contractions, tiled to reduce the
large control-point gather. The returned grids still occupy memory proportional
to the number of output samples. Normals follow `S_u × S_v`; singular samples
have zero normals, NaN curvatures, and a false validity flag. Set
`singular_policy="raise"` to reject any singular sample. Geometry with extreme
coordinate or weight ranges may still require rescaling; no arbitrary-precision
or condition-independent guarantee is made.

### Segmentation and geometry cards

Plane and cylinder hypotheses are constrained by distance and normal agreement.
Plane fits use an SVD consensus refit; cylinders can use a bounded nonlinear
refit. Both normal signs are supported. The cylinder radius is estimated from
samples; `target_curvature` in the direct fitting API is an optional prior.

Segmentation repeatedly extracts supported planes/cylinders up to configured
budgets. It retains original flattened sample indices and reports unassigned
samples. It does not guarantee a global optimum or estimate model uncertainty.
Topology labels use curvature magnitudes, so a cylinder does not disappear just
because the nonzero curvature changes algebraic position after a normal flip.
The historical `cylinder_fillet` dictionary tag is retained for compatibility;
its presence does **not** establish fillet adjacency or tangency.

Cards include schema version, units, full-precision machine parameters,
source indices, fit diagnostics, and explicit bounding methods. `precision=4`
now affects only `display_parameters`. JSON serialization rejects NaN/infinity.
Unassigned sample counts and run settings appear in the CLI's provenance block.
The rich segmentation result, rather than that summary block, retains the
actual unassigned indices.

### STEP export and its limits

The old handwritten STEP emitter was replaced with an optional OCP adapter.
It constructs bounded planar and cylindrical faces, checks them with
`BRepCheck_Analyzer`, checks STEP writer statuses, and returns the exchange text.
AP203, AP214IS (default), and AP242DIS are supported. Source units must be
`mm`, `cm`, `m`, or `in`; conflicting exporter/card declarations are errors.
The construction tolerance defaults to `1e-7` millimetres.

Plane boundaries are projected convex hulls. They can fill holes and concavities
or bridge disconnected coplanar support. Cylinder bounds are a minimal sampled
angular envelope and an axial range; finite samples do not prove full 360-degree
coverage. These choices make the approximation explicit rather than inventing
recovered trim topology.

Output is a **compound of bounded surface fragments**. Faces are not sewn into
a shell; cylinders are not capped; there is no solid, manifoldness, Boolean
reconstruction, or fabrication-ready claim. The STL feature pipeline also does
not create freeform NURBS patches for unassigned regions. Existing NURBS
control-net evaluation remains a separate capability.

`start_id` is accepted but deprecated and no longer controls entity IDs. Open
CASCADE owns IDs and metadata; byte-identical headers/timestamps are not
promised. This adapter serializes and restores the process-global exchange
settings it changes, but unrelated Open CASCADE code must coordinate its own
access. Native OCP dependencies have their own upstream licenses.

## Failure handling and output safety

Library functions raise descriptive exceptions and use module loggers without
configuring application logging. Result dataclasses prevent rebinding fields,
but contained NumPy arrays remain writable; they are not deeply immutable.
Inputs are not deliberately modified by the numerical routines.

JSON and STEP writes use same-directory temporary files with atomic publication.
No-clobber mode uses a hard link, and therefore requires filesystem support for
hard links; an unsupported filesystem reports an I/O failure instead of falling
back to an unsafe write. Explicit overwrite uses `os.replace`. These are
per-file guarantees, not a two-file transaction or power-loss guarantee. A later
publication failure can leave one complete output. The CLI propagates the error.

## Tests and project layout

```bash
python -m pytest -q
python -m pytest --cov=NURBSCoreEngine --cov=STLReader --cov=main --cov-report=term-missing
python -m compileall -q NURBSCoreEngine.py STLReader.py main.py
```

STEP tests skip when OCP is absent. The delivered validation run included it.
Ruff and mypy configurations are provided for continued development, but those
tools were unavailable in the execution environment and were not run. The CI
workflow runs compilation and pytest on declared Python versions, plus a
separate optional-STEP job; that hosted matrix has not been executed here.

- `NURBSCoreEngine.py`: NURBS geometry, RANSAC, cards, optional STEP adapter.
- `STLReader.py`: STL ingestion, mesh reports, and local feature estimation.
- `main.py`: CLI and callable pipeline.
- `tests/`: analytic, ingestion, failure-path, concurrency, and STEP round-trip tests.
- `examples/plane.stl`: 144-vertex planar smoke-test mesh; interpret units as mm.
- `originals/`: unchanged supplied files for comparison and rollback.
- `professionalization.patch`: diff of the three supplied modules.

See [MIGRATION.md](MIGRATION.md) for behavior changes and
[VALIDATION.md](VALIDATION.md) for what was actually tested.

## Primary implementation references

- SciPy B-spline interface and domain conventions:
  <https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.BSpline.html>
- SciPy KD-tree query interface:
  <https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.cKDTree.query.html>
- Open CASCADE face construction:
  <https://dev.opencascade.org/doc/refman/html/class_b_rep_builder_a_p_i___make_face.html>
- Open CASCADE STEP writer:
  <https://dev.opencascade.org/doc/refman/html/class_s_t_e_p_control___writer.html>
- OCP bindings:
  <https://github.com/CadQuery/OCP>
- Library of Congress binary STL description:
  <https://www.loc.gov/preservation/digital/formats/fdd/fdd000505.shtml>
