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

## UV location: slice 5

`cad::uv::Locator` and `cad_integrity.uv.prepare_locator` retain an admitted chart.
Only its native handle is authoritative. Index construction fixes barycentric and
XYZ agreement tolerances. Queries return complete, triangle-ordered candidate
sets; unique/agreeing queries also have an optional resolved XYZ. Agreement compares
all candidates against the lowest triangle ordinal, matching the retained reference.
A local chart or successful query does not establish global injectivity.

The private binding accepts only native-endian C-contiguous float64 `(Q,2)` input.
It checks input bytes before copying with `memcpy` into aligned vectors, then releases
the GIL. Native code borrows those vectors only for that call. Independent calls
share an immutable index; stacks, candidates and counters are local. Returned
`UVLocations` retain their native chart, while array exports own independent copies.
Host records use `None` for unresolved points; packed binding arrays use an explicit
validity mask. Values in invalid packed slots have no geometric meaning.

The host accepts array-like queries and normalizes them explicitly. Its conversion,
result export and immutable projection copies are outside native logical limits.
`sample` raises on any incomplete batch, outside point or ambiguous query and never
silently chooses a triangle. The legacy integration package is unchanged.

### Accounting

Default index/query limits are 256,000,000 input bytes, 512,000,000 owned bytes,
50,000,000 work steps and 256,000,000 output bytes. The query candidate cap is
1,000,000 accepted triangles per query. The common limit carrier is operation-local;
index construction does not use the candidate cap. Counts and products are checked
before allocations. These are logical payload/reservation counters, not process
RSS, vector spare capacities, allocator overhead or wall-clock bounds.

Let V/T/F/B denote selected vertices/triangles/faces/boundary vertices, Q queries,
C committed candidates, G the current staged group, and N actual index nodes.
All `sizeof` terms refer to the qualified C++ build, not serialized wire layouts.

- Index input: `48V + 56T + 8(F+B)` referenced chart payload, without another copy.
- Index output reservation: `sizeof(Storage) + T * (sizeof(TriangleData)
  + sizeof(size_t) + 2*sizeof(Node))`. The 2T node reservation includes unused leaf
  capacity. Index owned reservation adds `T*sizeof(size_t)` for an explicit pending-node
  construction stack, admitted before allocation. Tree construction and private
  heapsort are iterative; sorting uses constant local scratch. Constant scalar/local
  state is excluded. No recursive or third-party sorting workspace is hidden.
- Query input: `16Q`; native input is borrowed synchronously. Binding input copying
  checks the same input cap separately. Finiteness admission visits every query even
  when its work budget is zero; admission, output initialization and final status
  filling are bounded by admitted Q and excluded from the work counter.
- Mandatory output: `M = Q*sizeof(Record) + 8*(Q+1)`. Failure to fit M in output or
  owned limits returns a batch error before traversal and result allocation.
- Query output reservation during staging: `M + (C+G)*sizeof(Candidate)`. Reported
  output after completion/exhaustion is `M + C*sizeof(Candidate)`.
- Query owned high-water reservation: mandatory/output reservation plus
  `N*sizeof(size_t)` traversal stack and `G*sizeof(Candidate)` extra staged payload.
  Thus the staged group is charged twice while it is copied into committed output.
  Sorting is in place. Export arrays and Python records are outside this counter.
- Index work: one per triangle preparation, source-vertex extent visit, created node,
  node primitive-box accumulation and ordering comparison.
- Query work: one per started query, popped node, leaf primitive-box test, barycentric
  triangle test, accepted insertion, candidate ordering comparison and XYZ comparison.
  Counter exhaustion precedes the counted operation. Private iterative heapsort fixes
  ordering comparison counts; repeatability is scoped to the same numerical build.

A resource stop discards the current group, retains completed earlier records and
marks the current query and suffix budget-exceeded. `exhaustion` identifies the
first unfinished query and resource; the suffix is not attempted. No partial
candidate group or false outside result is returned. Invalid input/numerical range
returns a typed batch error. Allocation failures retain existing exception
translation rather than masquerading as a measured resource stop.

### Conservative index arithmetic

The predicate evaluates normalized edge inverse M in double precision. Index boxes
are built from that actual rounded M, not from ideal exact edges. Outward-rounded
interval arithmetic bounds its determinant and inverse. For K >= ||M^-1||_inf and
L >= ||M||_inf, finite `16*epsilon*K*L <= 1/2` bounds the query-vector magnitude from
accepted computed b1/b2. A rounded-dot-product error allowance expands their
acceptance rectangle; interval M^-1 maps that rectangle back to UV, with subtraction,
division, rescaling and subnormal absolute allowances. Ignoring b0's constraint
only enlarges the box. Overflow, uncertified determinant or excessive condition
produces an unbounded always-tested box. Such a triangle is never optimistically
pruned. Arithmetic failure during its actual query produces a numerical-range error.

This uses IEEE binary64, round-to-nearest, gradual underflow and no fast-math.
Alternative floating-point modes are not qualified. The retained test evidence
includes exhaustive candidate comparisons and Decimal oracles; it does not imply
exact predicates for arbitrary real-number inputs. Extreme inputs may fail closed.

## Conforming BRep realization (slice 6)

The host entry point is `cad_integrity.brep.realize(shape, policy=..., limits=...)`.
The input shape is interpreted in millimetres, as in the STEP adapter. OCP performs
copying, meshing, copy-history mapping and geometry queries in its own runtime.
The private `_native.realize_brep` binding accepts only copied contiguous native
float64/int64 evidence. No TopoDS pointer, ABI cast, serialization dependency or
additional OCCT linkage is introduced. Standalone `cad::brep` tests the same
numerical qualification source. Direct native admission is relative to the supplied
correspondence; only the OCP host operation establishes its source-kernel origin.

Shared identity comes from native vertices or edge/sample ordinals after exact
agreement of the OCCT curve-parameter sequences. Unequal sampling fails admission;
there is no tolerance-based coordinate welding or automatic resampling. Periodic
edge orientation selects the corresponding polygon branch. Only triangle sides
explicitly supplied by degenerate native edges permit pole-triangle removal,
reported as `collapsed_pole_triangles`. Ordinary collapsed triangles are refused.

C++ checks shared-coordinate agreement, finite/nondegenerate triangles, native
edge-use coverage, orientation and manifold vertex links. The resulting surface
shares the existing immutable Discretization storage with operators/charts. Its
`source_domain` is `native_face`; triangle face/edge IDs refer to native entities.
`surface.source_vertices` and boundary IDs are derived mesh vertex ordinals;
`RealizedSurface.native_vertex_ids` separately identifies native vertices (-1 for
edge/interior samples). A fresh `source_snapshot_id` scopes that realization's
correspondence; it is not cross-revision matching or the viewer's mesh identity.

The caller must not mutate a shape while realization reads/copies it. The source's
meshing cache is untouched and no kernel handles survive in the output. Array
projections are copied onto immutable bytes. Numerical native work releases the GIL.
OCP copy/mesher concurrency and cancellation guarantees are not added by this seam.

Count limits bound retained extraction, not OCP maps/copy/mesher allocations or
wall time. Native input bytes sum the six numeric arrays. Native logical workspace
reserves input bytes plus 512 bytes per input node, 2048 per triangle, 256 per edge
segment and 64 per source edge. These conservative per-item reservations cover
algorithmic payloads; allocator overhead, container capacity growth and external
kernel allocations are excluded. Output reservation is 48 bytes per input node
plus 64 per input triangle, bounding numeric result arrays including native vertex
IDs, boundary IDs and selected faces. Reservations may exceed actual retained data.

Work counts each input node, triangle, segment and source edge, each consolidated
triangle side, each vertex-link edge and each pending traversal pop. Ordered-map
comparisons, allocation and binding conversion are outside this logical counter;
it is not a CPU instruction or deadline bound. Mandatory checks reject budgets
before corresponding bulk native work/output. Python extraction independently
checks counts and numeric input reservation. Binding inputs are one additional
copy; export arrays and immutable host projections each add an output-sized copy.
Those copies and Python object overhead are not described as native workspace.

Sampled deviation measures triangle-centroid distance to the supporting surface
and edge node/midpoint distance to its curve. The supporting-surface projection
avoids arbitrary UV averaging at poles. This is neither a continuous error bound
nor proof of global injectivity, absence of self-intersection, element quality,
exact trim coverage, CAD repair or simulation readiness. Face meshing comes from
OCCT; holed, periodic, pole, translated and reversed fixtures qualify the exercised
cases. Unowned native entities and repeated indexed face occurrences fail closed.

## Canonical quad tracing (slice 8)

`cad_integrity.quad.prepare_quad_patch(mesh)` copies float64 XYZ and int64 signed
coedges/offsets/edges into the existing polygonal assessment owner, then adds
quad admission. `patch.trace()` uses the canonical launch set; explicit `Seed`
records select a labelled seeded experiment under the same timing/tie rules.
The module retains source ordinals, units and an immutable owned patch.

Private arrays require native-endian float64/int64 C-contiguous declared layouts;
no implicit casts occur there. Host seed normalization and immutable projection
allocate outside native limits. Inputs are copied before GIL release; callers
must not concurrently mutate inputs while that copy is in progress. Separate
trace calls on one admitted patch use independent state. Native handles cannot
be directly constructed by Python. Returned projections are backed by immutable
bytes; no array borrows a C++ buffer.

Admission uses `PolygonalLimits`. Input/output/assessment accounting is inherited;
quad topology reserves an additional 128 bytes per vertex, 256 per edge and 256
per coedge, including temporary ordered indexes, above assessment owned bytes.
Its work allowance is the remainder after assessment. The displayed patch usage
currently reports quad admission work/output and combined logical owned storage;
assessment output remains part of the retained owner. Limits describe phases,
not allocator capacity or process RSS. See the implementation record for measurements.

Tracing has independent `TraceLimits`: workspace reserves 128 bytes per vertex
and 1024 per seed; input seed copying is included in that logical reservation.
The retained input patch is excluded because it is shared. Output reserves
`sizeof(Seed)+sizeof(Id)` per seed (including unfinished IDs), and
`sizeof(Segment)+sizeof(Event)` per committed participant. Output allocations
are separate from workspace. Vector capacity, allocator overhead, Python objects
and export copies are outside these logical counts. Initialization charges two
work units per vertex and 128 per seed; each committed event participant charges
256 units for scheduler/index work. These are deterministic accounting units,
not CPU instructions or a wall-time guarantee. Admission charges its loop visits;
ordered-container comparisons are not individually counted.

Seed validation/initial reservation failures raise errors. Event, segment, work
or output exhaustion during execution preserves only complete simultaneous groups,
with `stop`, `unfinished`, and `last_committed_time2`. Terminal reasons differ from
incompleteness. `segment_coordinates()` is a derived XYZ projection; edge/vertex
identities and exact half-step times are authoritative.
