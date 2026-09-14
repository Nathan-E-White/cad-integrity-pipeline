# Validation record

Recorded September 13, 2026. These are observed results in the working Linux environment, not projected CI results.

## Executed checks

| Check | Observed result |
| --- | --- |
| Pytest, complete suite | **103 passed**, zero failures or skips in the recorded run |
| Real native-kernel tests | **24** of those cases exercise OCP; geometry is not mocked |
| Statement coverage | **91.19%** overall: 1,356 of 1,487 executable statements |
| Native adapter statement coverage | **91%** |
| `compileall` on source, tests, examples | Passed |
| Editable installation with local dependencies | Passed |
| Build a non-editable wheel | Passed |
| Wheel installed into a separate target; imports from that target | Passed |
| Wheel-based polygonal repair and native cylinder audit | Passed |
| Jupyter notebook execution | All **9 code cells** executed successfully, including native sewing and STEP readback |
| CLI synthetic demo and JSON report | Passed |

See `evidence/test-run.txt`, `evidence/pytest.xml`, `evidence/coverage.json`, `evidence/environment.json`, and `evidence/synthetic-repair.json` for the recorded outputs. Coverage is statement coverage, **not branch coverage**. It does not prove correctness or constitute a performance benchmark.

## Exercised environment

Python 3.13.5; NumPy 2.3.5; SciPy 1.17.0; SymPy 1.14.0; cadquery-ocp 7.9.3.1.1; pytest 9.0.2; Plotly 6.5.2. The JSON manifest records the remaining exact package versions.

The Python compatibility range and dependency ranges in `pyproject.toml` are not a claim that every combination has been executed. The supplied GitHub Actions workflow targets Python 3.11 and 3.13 on Linux; it has **not** been run remotely. No macOS, Windows, or user's PyCharm interpreter was available for validation.

## What the regression suite checks

Exact algebra is checked on empty complexes, points, intervals, loops, disks, sphere boundaries, a filled tetrahedron, a torsion-bearing cellular chain complex, and randomly generated integer matrices compared with an independent dense F₂ elimination. The chain identity and Smith divisibility conditions are explicit tests. Persistence intervals are compared against sublevel homology at selected times.

Topology/repair tests include a disk, an open cube, a closed cube, a torus, pinched vertices, inconsistent orientations, multiple components, a Möbius strip, degenerate/duplicate faces, unused topology, immutable inputs, welding idempotence, edge remapping, movement limits, and resource failures. The acceptance property is explicitly combinatorial, not a geometric embedding theorem.

Numerical checks cover constant-coordinate broadcasting, bounded local intersections, no-intersection rejection, triangle quality including scalene and degenerate cases, matching-connectivity area ratios, sampled nearest-neighbor distances, and shared-midpoint refinement. Package import is tested for absence of runtime output, GUI, native-kernel or network-client initialization.

Real OCP cases include box, cylinder, sphere and torus STEP round trips; native sewing of independently copied box/cylinder faces; preserved analytic surface types; periodic seam and degenerate-pole handling; a preserved internal cavity; multiple solids and ambiguous shell grouping; missing-face refusal; unowned-vertex refusal; tolerance enforcement; disabled-check rejection; source/output protection; deliberately failed serialization/readback; geometric drift at readback; display triangle provenance/orientation; actual curve sampling; metre-to-millimetre conversion; and overlapping-solid rejection.

## Not executed or not established

Ruff and mypy configuration is supplied but neither tool was installed in the validation environment. Installation attempts were blocked by unavailable network/package access, so **no lint or static-type-check pass is claimed**. The source was parsed/compiled and dynamically exercised, which is not a substitute for either tool.

The interactive Plotly data structures are tested and were emitted by the executed notebook. The self-contained HTML was loaded in a headless Chromium document with two Plotly containers and no JavaScript exceptions, but this browser environment has WebGL disabled. The 3D scenes therefore could not be visually verified there. Open the HTML in a WebGL-capable browser, or use a notebook frontend that supports Plotly's 3D renderer. The browser preview is optional and has no role in geometry acceptance.

There is no live SGS-1/SGS-2 test, no real SGS-output evaluation corpus, no Gradio deployment, no load/stress benchmark, no native fuzz-testing campaign, no process sandbox, and no continuous geometry-distance guarantee. Native repairs were exercised on controlled unsewn-face fixtures; this is not a claim of robust healing for arbitrary generative defects or gap sizes.

Integer SNF size limits do not bound wall-clock duration in every case. Native C++ operations may allocate memory or run for a long time before Python-level size checks return. A hosted deployment must implement independent process-level limits and cancellation.
