# Slice 8: owned canonical quad tracing

Implemented from baseline `a854ad1`. The user authorized the next native slice
and explicitly requested inspection/reuse of the existing native work.
See [DESIGN.md](DESIGN.md) for the frozen algorithm, admission and evidence contract.

## Delivered caller and reuse

```python
from cad_integrity.quad import prepare_quad_patch

patch = prepare_quad_patch(polygonal_brep)
result = patch.trace()
# result.complete, result.stop, result.events, result.segments, result.unfinished
# patch.boundary_edges are also part of the canonical graph.
xyz_segments = result.segment_coordinates()
```

`cad::quad` and the private NumPy binding activate the pre-existing scaffold.
The quad patch retains the existing polygonal assessment owner, with one new const
input accessor and quad-specific adjacency/admission. It preserves source edge,
vertex and face ordinals, float64 coordinates, signed coedges and units. Public
seed/event/segment IDs have distinct seed, edge and vertex types; error evidence
also names its entity domain. The native result retains its patch independently.

Both motorcycle prototypes were inspected. Their trail/event organization was a
useful starting point, but canonical edge/vertex stepping required different
admission, chronological collision and oriented tie logic. No prototype translation
unit was activated, and no float/int mesh migration or geometry duplication was
introduced. Point3D, chart tracing, raw fields, NURBS binding, Delaunay construction,
frontend protocol, database, GPU and repair/export remain outside this slice.

## Qualification and corrections

- First native fixture failed at link time on the unimplemented admission/tracing
  seams; the empty canonical grid then passed. The oriented pair fixture failed
  before scheduler implementation and passed after it. First host fixture failed
  on the missing caller. Host normalization tests then exposed the existing array
  helper's 1-D default and empty-list dtype rule; the adapter now requests (N,3)
  int64 seed layout explicitly.
- Cube: 24 canonical branches meet at 12 edge midpoints at time 1/2. Grid fixtures
  cover oriented perpendicular winners, opposing vertex arrivals, three/four-way
  simultaneous stops, shared launch exemptions, persisted deposited tracks,
  nonexistent future-track rejection, boundary termination and seed permutation.
- Torus: an explicitly seeded trace returns to its source and reports self-collision
  at five edge steps. An already structured torus has no canonical launches.
  This does not claim physical periodicity or graph-cycle certification.
- Distinct coincident components do not collide. Owner mutation/lifetime and
  immutable projection fixtures pass. Canonical cube output is invariant under
  orientation-preserving vertex/face relabelling and loop rotation. Reversing
  orientation reverses the declared perpendicular tie winner.
- Additional admission fixtures pass the broader polygonal cellular assessment
  but fail quad admission: parallel edge identities and two faces sharing a
  multi-edge path. Errors retain the offending edge/face domain and ordinal.
- An independent Python oracle advances heads on doubled Cartesian lattice
  coordinates at half steps, without native rotations, a priority queue or an
  edge index. All **3,160 unordered pairs of 80 directed launches** on a 5x5
  vertex grid agree on normalized segments, event times and reasons. Every
  possible event-count budget cutoff agrees on complete time-group event prefixes.
  This is bounded two-particle planar qualification. Blocker identities,
  deposition times, unfinished IDs, partial segment arrays, multiway events,
  extraordinary vertices and torus behavior have separate selected fixtures;
  the oracle does not independently cover every one of those contracts.

## Final verification

- Full root Python suite against the packaged native extension: **434 passed**,
  no skips, 25.31 seconds; 92% aggregate statement coverage.
- Focused quad host suite: **24 passed**, including the bounded exhaustive oracle.
- Native strict Release: **10/10 passed**. ASan/UBSan: **10/10 passed**.
- Isolated CPython 3.13 sdist and wheel built successfully, with the wheel built
  from the sdist. Quad header/source, binding, host caller and stub are included.
- Wheel installed and exercised outside the checkout: **63 passed**, no skips
  (24 quad, 15 surface, 15 UV, 9 BRep). Both module and extension paths resolve in
  `/private/tmp/cad-quad-verify/lib/python3.13/site-packages`. This environment
  shares installed Pixi dependencies; it is not independent platform qualification.
- Changed Python caller/tests/benchmark pass Ruff; the caller passes mypy.
  Root Ruff still has 7 pre-existing findings in `mesh_motorcycle.py`; root mypy
  still reports its pre-existing undefined `_gen_synthetic_mpaths`. That file is
  unchanged, so root lint/typechecking are not claimed green.
- Standards review found missing strong ID types and ambiguous error entity
  domains. Both were corrected and the reviewer confirmed resolution.
- Independent contract review found no runtime defect, requested a bounded oracle,
  and accepted the added oracle with the limits recorded above. Reviews were
  source reviews, not independent reruns of all validation.

## Measurements and limits

`benchmark.py` records seven-run medians after one warmup in `benchmark.json`.
For the 12,288-face L-shaped patch (12,545 vertices, 4 canonical launches,
130 committed segments), preparation plus host projection took 44.37 ms;
binding tracing 0.399 ms; native-result export 0.024 ms; full host trace call
0.865 ms. These are local phase measurements, not a reference speedup or RSS study.
Admission dominates this example because the existing assessed carrier retains
cellular evidence and the host also projects its owned topology.

`native/bindings/README.md` defines logical storage/work/output accounting and
exclusions. Supported trace stops preserve committed groups; validation/allocation
errors do not become partial success. Trace completion does not establish CAD
repair, a schematic partition, element quality, or simulation readiness.

## Continuation

Canonical quad tracing is complete for the admitted contract above. Chart-axis
tracing requires separate chart/transition admission and collision qualification;
raw-field tracing remains deferred. NURBS binding and Delaunay construction remain
independent branches requiring a concrete caller and their own qualification.
Do not enable the existing demonstration sources wholesale for any of those steps.
