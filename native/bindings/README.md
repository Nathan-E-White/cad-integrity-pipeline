# Private NumPy binding: F2 slices 0 and 1

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
and its type stub. The sdist inventory includes both C++ sources and the header.
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

No database, GPU, geometry binding, solver replacement or future extension is
activated. See `docs/reviews/native-f2/IMPLEMENTATION.md` for checks and measurements.
