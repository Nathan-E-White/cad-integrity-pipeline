# Ready-made pathological mesh fixtures

**The geometry files are already built. No modeling software, model weights, inference service, or GPU is needed to create them.** This is a separate fixture pack for CAD Integrity Lab; it does not replace the earlier project or its `01_integrity_lab.ipynb` notebook.

These are deliberately constructed **synthetic controls**, not GenCAD/SGS outputs and not faults observed in those models. The reference is a faceted round base with a cylindrical boss, constructed directly from indexed rings. No third-party model or image assets are included. There is no purported source photograph: the procedural reference is the ground truth.

## Start here

Extract this archive and open `pathological_cases.ipynb` in its extracted directory. The saved notebook includes executed results. NumPy and Plotly support the display cells; the live audit/repair cells use the `cad_integrity` package from the existing CAD Integrity Lab project. These are the same dependencies used by that project's notebook. No additional dependency installation is required when using that environment.

For a viewport, load a `.glb` from `meshes/`. For exact diagnostics in the existing package, use the `.npz` loader in `case_fixtures.py`. The notebook shows both. The geometry generator in `tools/` is only there for reproducibility: **you do not need to run it**.

## Files and observed results

| Mesh stem | Role | Triangles | Betti numbers over F2 | Free edges | Shared-edge winding conflicts | Nonmanifold vertices |
|---|---|---:|---|---:|---:|---:|
| `00_clean_boss` | Clean control | 508 | (1, 0, 1) | 0 | 0 | 0 |
| `01_detached_reversed_cap` | P1: detached and reversed cap | 508 | (2, 0, 0) | 128 | 0 | 0 |
| `01_welded_not_oriented` | P1 intermediate: joined but still reversed | 508 | (1, 0, 1) | 0 | 64 | 0 |
| `01_repaired_cap` | P1 result produced by the existing repair pipeline | 508 | (1, 0, 1) | 0 | 0 | 0 |
| `02_pinched_vertex` | P2: two closed surfaces sharing vertex 4 | 1,016 | (1, 0, 2) | 0 | 0 | 1 |

Each stem is supplied as **GLB, OBJ, and NPZ**. These are alternate representations of the same fixture/stage, not different cases.

The five GLBs together are 61,268 bytes (61.3 kB). Exact counts, hashes, and byte sizes are in `manifest.json`. GLB floating-point positions have normal float32 export rounding; exact float64 reference comparisons use NPZ/OBJ.

## P1: detached and reversed cap

The base diameter is 40 mm and its thickness is 5 mm. The boss is 18 mm in diameter and rises a further 12 mm. The mesh has 64 circumferential segments. Its top disk uses only boundary vertices; this avoids leaving an interior cap vertex behind after boundary welding.

The cap is detached by duplicating its 64 boundary vertices, translating it upward **0.05906775770248944 mm**, and reversing its 62 triangles. No triangles are missing. The displacement is 0.001 times the clean mesh's bounding-box diagonal. Coordinates and triangle indices are recorded in `provenance/construction.json`.

The demonstrated welding tolerance and movement budget are both **0.0738346971281118 mm**. With that explicit policy, the existing `RepairPipeline` merges 64 vertices/64 edges and corrects the cap's orientation. The repaired NPZ coordinates match the reference exactly, and every oriented triangle matches modulo cyclic vertex order. The input remains unchanged.

The detached disk is locally coherently oriented; no edge connects it to the body, so shared-edge diagnostics alone cannot call its orientation wrong before reattachment. Its reversal is known from the injection record. The separately saved **weld-only** stage makes the 64 orientation conflicts observable. This is why the intermediate is included.

A 0.001 mm welding budget is also tested: it does not close the gap and the pipeline returns `needs_review`, not a success claim.

## P2: pinched vertex

The second example uses two copies of the reference, reflected about a uniquely exposed vertex, with reflected winding corrected and only that vertex identified as shared. The supporting-plane condition puts the two copies on opposite sides of a plane; their only geometric contact is that point.

Every edge has two incident faces, and there are no shared-edge winding conflicts, but the shared vertex has a disconnected link. The native vertex ID in the canonical arrays is **4**. The existing welding policy refuses the input with decision **`rejected`** and produces no repair candidate.

There is intentionally no `02_repaired` file. Splitting the vertex, separating the bodies, or adding material would be different modeling decisions. This fixture tests detection and refusal, not an automatic physical interpretation.

## Load into CAD Integrity Lab

Run from this extracted folder, using the existing project's Python environment:

```python
from case_fixtures import load_brep, repair_policy
from cad_integrity import RepairPipeline

result = RepairPipeline(repair_policy()).run(load_brep("01_detached_reversed_cap"))
print(result.report.decision)  # topology_checks_passed

result = RepairPipeline(repair_policy()).run(load_brep("02_pinched_vertex"))
print(result.report.decision)  # rejected
```

For arrays only, without importing CAD Integrity Lab:

```python
from case_fixtures import load_arrays
vertices, triangles, unit = load_arrays("02_pinched_vertex")
```

The loader reads NPZ with `allow_pickle=False`, preserves indices and winding, and performs no automatic processing.

## Units and topology preservation

**NPZ and OBJ coordinates are millimetres. GLB positions are metres**, following glTF's unit convention. The GLB has one indexed triangle primitive with no per-face vertex splitting. Tests read it back through Trimesh with processing disabled, check every face index and vertex count, and verify the metre-to-millimetre conversion.

Use the canonical NPZ for pipeline tests. Do not enable automatic welding, manifold conversion, winding fixes, or vertex splitting while importing a deliberately defective fixture; doing so can change the test before the auditor sees it. STL is intentionally not supplied because it does not retain this indexed-topology contract.

The notebook shows actual coordinates, not an exaggerated exploded view. The gap is small, so the known detached cap and the detected seam are highlighted in crimson. Repaired/reference surfaces appear green only to indicate their recorded combinatorial checks passed. The pinched vertex has a crimson marker. The GLB files themselves use a neutral material; overlays belong to the diagnostics/display layer.

## Validation and limitations

On September 14, 2026 in the working Linux environment:

- **19 regression cases passed**, including fresh homology/diagnostics, actual GLB readback, exact OBJ readback, repair-to-reference equality, input preservation, pinched-junction refusal, too-small welding budget, and clean-reference no-op behavior.
- The included notebook was executed after generation. Its live cells use the unchanged `cad_integrity` source extracted from the earlier project archive. The environment and source hashes are recorded in `provenance/environment.json`.
- `reports/test-run.txt` and `reports/tests.xml` contain the recorded test run; the JSON reports contain the full observed diagnostics.

These are small polygonal controls, not a production benchmark or a test of arbitrary generated CAD. The library reports **combinatorial** validity; it does not execute a general geometric self-intersection test on these meshes. The constructed reference and repaired reference coincide exactly, while the pinched fixture's single-point contact follows from its construction. No native STEP solid or engineering certification is implied.

Plotly requires a WebGL-capable notebook frontend for the interactive figures. The geometry/data and recorded reports do not depend on the renderer.

For the distinction between combinatorial manifold requirements and geometric embedding defects, see CGAL's primary documentation: https://doc.cgal.org/latest/Polygon_mesh_processing/index.html

## Optional reproducibility

`tools/build_fixtures.py` regenerates the mesh/report subset into a **new** directory and refuses an existing destination. It is not required for normal use. The test suite additionally uses pytest and Trimesh. `manifest.json` lists SHA-256 hashes and sizes for every other delivered file.
