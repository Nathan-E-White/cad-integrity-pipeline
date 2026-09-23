# Native extension file inventory

Created 2026-09-21 from the C++ handoff. **Slices 0–6 and 8 are implemented:**
F2 reduction, polygonal facts/admission and the owned private NumPy binding are active. Surface preparation/operators/chart qualification and native display identity are active. UV location and conforming BRep realization are active. Canonical quad tracing is active. Delaunay construction
remains a provisional declaration outside implemented targets; NURBS host binding
remains an independent unfinished branch.
`CAD_NATIVE_CHECK_SCAFFOLDS` compiles only those unfinished declarations.
See [the slice implementation record](reviews/native-f2/IMPLEMENTATION.md).

## Expected new files — created in this change

| Filename(s) | Purpose |
|---|---|
| `native/f2_reduction.hpp` / `native/f2_reduction.cpp` | Active bounded CPU reducer; `cad::f2` |
| `native/surface_preparation.hpp` / `native/surface_preparation.cpp` | Active owned polygonal surface computation; `cad::surface` |
| `native/uv_location.hpp` / `native/uv_location.cpp` | Active owned all-candidate chart location; `cad::uv` |
| `native/brep_realization.hpp` / `native/brep_realization.cpp` | Active owned correspondence/conformity qualification; `cad::brep`, OCP runtime extraction in `cad_integrity.brep` |
| `native/voronoi/include/cad_mat/delaunay.hpp` / `native/voronoi/src/delaunay.cpp` | Declaration scaffold and implementation notes |
| `native/quad_tracing.hpp` / `native/quad_tracing.cpp` | Active owned canonical quad admission and tracing; `cad::quad` |
| `native/bindings/module.cpp` | Active private owned NumPy binding |
| `native/bindings/README.md` | Binding contract and build instructions |
| `native/tests/extension_contracts.md` | Binding or qualification scaffold |
| `docs/NATIVE_EXTENSION_FILE_PLAN.md` | This inventory, scope and activation sequence |

## Existing files to refine, not duplicate

- `native/SimplicialComplex.hpp`, `.cpp`: polygonal facts/admission, shared mesh
  representation, precision/provenance, convex triangulation and BVH reuse.
  Preserve the user's pre-existing include-order edit.
- `native/nurbs/include/cad_mat/nurbs.hpp`, `native/nurbs/src/nurbs.cpp`: bind the
  retained evaluator; qualify rather than invent a second NURBS implementation.
- `native/voronoi/include/cad_mat/voronoi.hpp`, `native/voronoi/src/voronoi.cpp`:
  consume the existing snapshot/extractor; add construction in the listed files.
- `native/CMakeLists.txt`, `native/voronoi/CMakeLists.txt`, `pyproject.toml`:
  integrate only as implemented/tested slices become ready.
- `src/cad_integrity/f2_reduction.py`, `algebra.py`, `simplicial.py`: preserve host
  behavior while binding reduction; no replacement host module is required now.
- `src/cad_integrity/inspection.py`, `workbench_results.py`, `gradio_app.py` and
  `components/inspection_workspace/`: evolve existing identity/projection and
  explicit submission interfaces when corresponding computation is available.
- Existing native/Python/frontend test files: extend relevant contracts. New
  executable test filenames will be chosen with their implemented slices.

## Rules and sequence

1. Qualify the owned NumPy binding/toolchain, implement F2 and its rank/persistence
   callers, and only then link those files into implemented library/binding targets.
2. Refine polygonal admission and native display identity in existing modules.
3. Implement surface preparation with Python SciPy solve retained, then UV location.
4. Qualify conforming OCCT realization. NURBS binding and Delaunay construction
   can proceed as independent branches when their callers are ready.
5. Qualify canonical quad tracing before any separately admitted chart mode.

Prefer generalization, composition and appropriate polymorphic specialization of
existing implementations. New code is welcome when clearer or more correct.
Declarations are responsibility sketches, not a mandatory class hierarchy.
Do not duplicate identical mesh storage; preserve distinctions between polygonal
cells, simplicial incidence, display triangles and conforming realized geometry.
Runtime Strategy requires actual interchangeable implementations; static private
specialization can share real 2D/3D index mechanics without conflating queries.

Database persistence, CUDA/Metal compute, custom shaders and GPU abstractions
remain deferred. Existing frontend GPU rendering is allowed. Artifacts and owned
in-memory results remain the persistence model for now.

## Design references

The detailed handoff remains at
`/var/folders/96/1cqymb41491g06wgkv0bvkz00000gn/T/cpp-native-handoff-20260921.md`.
The seam rationale remains alongside it in
`native-seam-design-20260920-232459.md`.
Completed work and historical validation are in
`docs/reviews/native-consolidation/IMPLEMENTATION.md`.
