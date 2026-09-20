# Validation record

Executed on 2026-09-17 in the working Linux environment. This is a record of
checks actually performed, not a certification of arbitrary input geometry.

## Environment

- Python 3.13.5
- NumPy 2.3.5
- SciPy 1.17.0
- pytest 9.0.2
- cadquery-ocp distribution 7.9.3.1.1 (OCP binding version 7.9.3.1)

The optional STEP backend was installed and exercised. Python 3.11 and 3.12 are
declared targets in the project and hosted CI matrix, but were not executed
locally. Mac/Windows behavior and external commercial CAD import were not tested.

## Automated suite

Command:

```bash
python -m pytest --cov=NURBSCoreEngine --cov=STLReader --cov=main --cov-report=term-missing -q
```

Result: **132 passed; none failed or skipped in this environment.**

| Module | Executable statements | Missed | Statement coverage |
| --- | ---: | ---: | ---: |
| NURBSCoreEngine.py | 701 | 64 | 91% |
| STLReader.py | 336 | 27 | 92% |
| main.py | 120 | 8 | 93% |
| Total | 1157 | 99 | 91% |

Coverage is statement coverage, not branch coverage and not a numerical accuracy
metric. Tests cover:

- ASCII/binary equivalence, byte order, binary attribute bytes, `solid`-prefixed
  binary files, empty inputs, malformed/truncated/extra data, nonfinite values,
  degenerate facets, and input/configuration limits.
- Basis derivatives against SciPy BSpline for degrees 0–5, repeated knots,
  endpoints, scaled/translated knot domains, and derivative orders above degree.
- Plane, exact rational cylinder, polynomial paraboloid, and saddle fixtures;
  curvature, orientation, scale, tile consistency, weight rescaling, large world
  translation, singularity behavior, and validation errors.
- Local plane/sphere features, normal reversal with signed-curvature ordering,
  scale behavior, sparse/collinear/duplicate neighborhoods, fit/radius gates,
  and the batch size of KD-tree queries.
- Plane/cylinder RANSAC, rotated axes, inward/outward and flipped normals,
  multiple planes and radii, seeded repeatability, untouched global RNG state,
  inlier-mask shapes, exclusive indices, and invalid-feature exclusion.
- Full-precision geometry cards, small dimensions, planar projection,
  seam-crossing cylinder bounds, malformed data, and strict finite JSON.
- STEP write/read round trips through Open CASCADE: face counts, surface areas,
  input-unit conversion for mm/cm/m/in, AP203/AP214IS/AP242DIS, rotated cylindrical
  bounds, settings restoration, and deliberate absence of solids.
- Atomic output publication, no-clobber behavior, cleanup, an eight-thread
  concurrent-creation test, CLI failures, optional backend errors, clean imports,
  and the complete STL-to-JSON/STEP pipeline.

## Additional checks

1. `compileall` completed successfully for all three delivered Python modules.
2. Source line wrapping was checked: each delivered module has a maximum line
   length of 100 characters. Formatting-only edits were compared using Python ASTs
   to confirm unchanged statement semantics before rerunning the suite.
3. Running `main.py` on `examples/plane.stl` produced JSON and STEP with 144 valid
   feature estimates, one plane, and zero unassigned vertices from 242 facets.
4. A wheel built successfully using the configured setuptools backend. Imports
   from the wheel in a separate working directory, with no source directory on
   `PYTHONPATH`, and a JSON pipeline run both passed. This was a build/import
   check, not an installation test across the full supported dependency range.

## Checks not performed / limitations

Ruff and mypy were unavailable and were not run. Their configurations are
included as development starting points, not as a claim of clean lint or strict
static typing. The hosted CI workflow has not been run in GitHub.

No representative real STL scan was supplied, so there is no measured real-part
reconstruction accuracy, calibrated uncertainty, maximum-file performance, or
peak-memory benchmark. The analytic fixtures test local numerical behavior,
not universal scan-to-CAD success. No commercial CAD application was used to
validate exchange; STEP validation here was kernel construction/checking and
round-trip read-back with Open CASCADE.

The generated faces are approximate bounded fragments, not recovered trim loops,
a sewn shell, or a watertight solid. See README.md for orientation, neighborhood,
parameter-domain, tolerance, resource-limit, and output-atomicity limitations.
