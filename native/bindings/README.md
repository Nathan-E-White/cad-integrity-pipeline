# Private NumPy binding: F2 and polygonal assessment

`cad_integrity._native` is a required private extension, built by setuptools with
pybind11 3.x and a C++26 compiler supporting `std::expected`. The qualified host is
CPython 3.13 / AppleClang 21 / macOS arm64. There is no Python fallback or backend
registry. A source checkout must be built before importing the host reducers:

```sh
python -m pip install -e .
# or build and install a wheel:
python -m build --wheel
python -m pip install dist/cad_integrity_lab-*.whl
```

Build isolation installs setuptools and pybind11; NumPy headers are not a build
dependency. NumPy remains a runtime dependency. The wheel contains the extension
and its type stub. The sdist inventory includes all three C++ sources and both headers.
CMake's `cad::f2` target compiles the same source for independent native consumers.

## Ownership and representation

`reduce_f2(offsets, values, evidence, limits...)` accepts only one-dimensional,
C-contiguous, native-endian int64 NumPy arrays. No implicit dtype or stride repair
occurs. Offsets start at zero, are monotone and end at the value count. Each column
is sorted and unique. Signed int64 row labels preserve negative host labels;
these are abstract algebra labels, not geometry array indices. Input counts are
checked before copying. Both arrays are copied before releasing the GIL, and no
borrowed Python buffer is used during reduction. Arrays in the returned dictionary
own their memory independently of the input and every later call.

`F2ColumnReducer.reduce` explicitly normalizes iterable integer-label sets into
this layout. Duplicate labels collapse, out-of-int64 labels raise `OverflowError`,
and noninteger labels raise `TypeError`. Matrix coefficient summation/modulo-two
normalization stays in `rank_f2`; filtration ordering stays in persistence.
All input is admitted before numerical reduction, so an invalid/over-budget later
column can be reported before an earlier column's numerical work failure.

## Evidence and budgets

The default `full_trace` reproduces every canonical host state, including initial
and empty final states. `rank_only` omits reduced columns and traces;
`reduced_columns` omits traces. All modes preserve ordered pivot values and usage.
The existing immutable host record uses empty tuples for omitted evidence.
Rank requests `rank_only`; persistence requests `reduced_columns`.

Existing input/pivot/scratch-entry and XOR-step limits retain their meanings.
`max_trace_entries` counts row labels in every retained state (not just pivots).
`max_output_bytes` counts all returned native int64 array payloads, their offset
sentinels, and four uint64 usage counters. It includes offsets for empty states.
Checks precede retention; budget failure returns no final rank or partial result.

These are logical payload limits, **not process RSS limits**: vector spare capacity,
map nodes, binding copies and Python tuple/int overhead are additional. Owned input
and scratch payloads are bounded by column/storage limits; retained packed output
is bounded separately. No allocator-wide cap or streaming claim is made.

Native domain errors become `ValueError`; typed budget failures become private
`BudgetExceeded`, translated by the host to `ResourceLimitExceeded`. `bad_alloc`
becomes `MemoryError`; vector `length_error` becomes `OverflowError`. The GIL is
reacquired during unwinding before Python exception translation.

The F2 binding activates no database, GPU, solver replacement or future extension. See `docs/reviews/native-f2/IMPLEMENTATION.md` for checks and measurements.

## Polygonal assessment: slice 2

`assess_polygonal(vertices, edges, offsets, coedges, unit, limits...)` accepts
C-contiguous native float64 `(V,3)` coordinates and native int64 `(E,2)` endpoints,
`(F+1,)` offsets and `(C,)` signed one-based coedges. There is no narrowing or
implicit normalization. Supported unit metadata is `mm`, `cm`, `m`, `in`; no
conversion occurs. Input byte admission precedes copies under the GIL. Numerical
work uses only owned copies with the GIL released. Independent simultaneous calls
share no mutable assessment state. Mutating a NumPy buffer from an external native
thread while it is being copied is unsupported.

Invalid shapes, layouts, finite-coordinate checks and references produce input
errors. Disconnected/repeated-vertex loops and other diagnosable defects produce
complete facts without admitted incidence. Open edges and inconsistent orientation
alone do not prevent cellular admission. Orientation multipliers preserve first-use
edge traversal and ascending face seeds; nonmanifold orientation identifies the
first offending edge in first-use order. Diagnosis lists retain host ordering.

Returned arrays own their storage. Admitted results include D1/D2 tuples of int64
`(row_offsets, column_indices, coefficients, shape)`. Unadmitted results omit them.
The native admitted value retains the copied input and incidence through a shared
immutable owner. Python retains independently owned incidence; its `raw` reference
identifies the source but is never used to rebuild admitted matrices. ChainComplex
still performs exact checked integer chain validation before homology conversion.

| Limit | Default | Accounted quantity |
|---|---:|---|
| `max_input_bytes` | 256,000,000 | `24V + 16E + 8(F+1) + 8C` array payload bytes |
| `max_owned_bytes` | 512,000,000 | Logical workspace reservation: input bytes + `256(V+E+C) + 128F + 64` |
| `max_work_steps` | 50,000,000 | Deterministic admission scan, face-token, cycle-entry, vertex-link and orientation visits; incidence scan allowances |
| `max_output_bytes` | 256,000,000 | All returned int64 array payloads, including matrix shape arrays |

The workspace reservation bounds input-proportional structures before allocating
them. It is not measured allocated memory, spare vector capacity, map-node overhead
or process RSS. Work steps do not count allocator work or comparisons internal to
standard containers and do not impose a wall-clock limit. Output bytes exclude
scalar status/usage metadata, Python objects and transient conversion copies.
Budget failure is all-or-nothing and follows the existing BudgetExceeded to
ResourceLimitExceeded translation; it never becomes invalid geometry or admission.
The four scalar usage counters expose these quantities. A disk uses 208 input
bytes, 3,472 workspace units, 84 work steps and 480 packed output bytes.

CMake `cad::simplicial` and setuptools compile the same SimplicialComplex.cpp.
No triangulation, geometric certification, OCCT, surface, UV or tracing behavior is
added by this binding. See `docs/reviews/native-polygonal/IMPLEMENTATION.md`.

## Surface preparation, operators and charts: slice 4

The private binding supplies opaque `Surface`, `SurfaceOperators` and
`AdmittedChart` values. Only the native preparation/qualification operations mint
these values. They retain immutable native owners; exported arrays are independent
copies. The host `cad_integrity.surface` exposes immutable bytes-backed projections
and makes mutable SciPy CSR copies on request. Copy/projection storage and SciPy
factorization allocations are additional to native logical budgets.

`prepare_surface` accepts the existing polygonal float64/int64 carrier, selected
source face IDs, units, tolerance and limits. `assemble_surface` accepts that owned
surface and source face confidence pairs. `qualify_surface_chart` accepts the same
surface, float64 `(active_vertices,2)` UV, orientation and tolerance. Array layout,
input byte totals and dimensions are checked before copies; computation uses only
owned data with the GIL released. External native mutation during a copy remains
unsupported. Allocation failure becomes MemoryError, length/range failure becomes
OverflowError, geometric/structural failure becomes ValueError and budget failure
becomes BudgetExceeded. Host adapters translate the latter two to InvalidGeometry
and ResourceLimitExceeded. Native errors include operation and source face when
available; `-1` means the failure cannot be assigned to one face.

The new host `prepare_surface(...).prepare_harmonic_system(...)` is an installed
programmatic caller. It imports no integration bundle. Its solver retains SciPy,
complete-current-set soft anchors, factorization counters, residual checks and
refactor fallback. Locally invalid UV can be returned only when orientation checks
are disabled; that never grants an admitted chart. A finite locally valid chart
can still overlap another part of itself.

### Logical accounting

Use the same four limits as polygonal admission. Budgets are operation-local;
retained input surface owners are not charged again to assembly/qualification.

- Preparation input: `24V + 16E + 8O + 8C + 8S` bytes (XYZ, edges, offsets,
  coedges, selection). Workspace reservation: `1024*(V+E+O+C+S+1)` bytes,
  conservatively including selected-patch assessment/incidence, maps, input and
  triangulation scratch. This can refuse inputs well below the input-byte limit.
- Preparation output: `32A + 8S + 8B + 56T + 48` bytes (active XYZ/source IDs,
  selected face IDs, source boundary vertex IDs, triangles/side edges/parent faces,
  metadata and usage). Allocation/accounting uses checked growth.
- Assembly input: `16K` confidence bytes. Workspace: `128K + 768T + 16(A+1)`.
  Output: `16K + 8(A+1) + 16N + 40`, where N is retained CSR nonzeros. The native
  operator retains normalized confidence even though Python only exports CSR.
- Chart input: `16A`. Workspace: `16A + 16T + 128`. Output: `56 + 8D`, plus
  `16A` only on admission; D counts reported flipped/collapsed triangles.

Work counts deterministic logical scans, selected coedge visits, inherited
polygonal assessment work, projected pair/ear predicates and ear membership scans,
assembly triangle/edge contributions, sorting comparisons, accumulation visits,
and chart input/triangle visits. It is not an instruction count: associative
container costs and allocation overhead are not measured CPU work. No wall-time,
allocator-wide, process RSS or SciPy-memory cap is promised. Any exhausted native
operation returns failure with no partially admitted surface, operator or chart.
