"""Native reduction contracts through the existing host and packed binding seams."""
import numpy as np
import pytest

from cad_integrity.errors import ResourceLimitExceeded
from cad_integrity.f2_reduction import F2ColumnReducer, ReductionBudget


def test_evidence_modes_preserve_rank_and_requested_evidence():
    columns = ((0, 1), (0, 2), (1, 2))
    full = F2ColumnReducer().reduce(columns)
    rank = F2ColumnReducer().reduce(columns, evidence="rank_only")
    reduced = F2ColumnReducer().reduce(columns, evidence="reduced_columns")
    assert rank.rank == reduced.rank == full.rank == 2
    assert rank.reduced_columns == rank.reduction_traces == ()
    assert reduced.reduced_columns == ((0, 1), (0, 2), ())
    assert reduced.reduction_traces == ()
    assert full.reduction_traces == (((0, 1),), ((0, 2),), ((1, 2), (0, 1), ()))


def packed(offsets=(0, 2, 4, 6), values=(0, 1, 0, 2, 1, 2), **limits):
    from cad_integrity import _native
    options = dict(max_columns=50_000, max_stored_entries=2_000_000,
                   max_xor_steps=2_000_000, max_trace_entries=8_000_000,
                   max_output_bytes=256_000_000)
    options.update(limits)
    return _native.reduce_f2(np.asarray(offsets, dtype=np.int64),
                             np.asarray(values, dtype=np.int64), "full_trace", **options)


def test_trace_budget_is_separate_from_pivot_storage_and_consumers_omit_traces():
    # Eleven independent/repeated columns: eight pivot entries, 44 trace entries.
    columns = ((0, 1, 2, 3), (4, 5, 6, 7)) * 5 + ((0, 1, 2, 3),)
    result = F2ColumnReducer(ReductionBudget(max_trace_entries=44)).reduce(columns)
    assert result.stored_entries == 8
    assert sum(len(state) for trace in result.reduction_traces for state in trace) == 44
    with pytest.raises(ResourceLimitExceeded, match="trace exceeds"):
        F2ColumnReducer(ReductionBudget(max_trace_entries=43)).reduce(columns)
    assert F2ColumnReducer(ReductionBudget(max_trace_entries=1)).reduce(
        columns, evidence="rank_only").rank == 2
    from scipy.sparse import csr_matrix
    from cad_integrity.algebra import rank_f2
    assert rank_f2(csr_matrix(np.eye(8, dtype=np.int64)),
                   ReductionBudget(max_trace_entries=1)) == 8


def test_owned_outputs_survive_input_alias_mutation_and_later_calls():
    source = np.array([0, 1, 0, 2, 1, 2], dtype=np.int64)
    alias = source.view()
    source.flags.writeable = False
    result = packed(values=source)
    alias[:] = 99
    for value in result.values():
        if isinstance(value, np.ndarray):
            assert value.flags.owndata
            assert not np.shares_memory(value, source)
    assert result["reduced_values"].tolist() == [0, 1, 0, 2]
    result["pivot_values"][:] = -1
    assert packed()["pivot_values"].tolist() == [0, 1, 0, 2]
    del source, alias
    assert result["state_values"].tolist() == [0, 1, 0, 2, 1, 2, 0, 1]


@pytest.mark.parametrize("values", [np.array([0.0]), np.array([0], dtype=np.int32),
    np.array([0], dtype=">i8"), np.zeros((1, 1), dtype=np.int64),
    np.arange(4, dtype=np.int64)[::2]])
def test_packed_binding_rejects_implicit_dtype_shape_or_layout_conversion(values):
    from cad_integrity import _native
    with pytest.raises(ValueError, match="native int64"):
        _native.reduce_f2(np.array([0, len(values)], dtype=np.int64), values,
                          "full_trace", 10, 10, 10, 10, 1000)


@pytest.mark.parametrize("offsets,values", [([], []), ([1], []), ([0, -1, 1], [0]),
    ([0, 2], [0]), ([0, 2, 1], [0]), ([0, 2], [1, 0]), ([0, 2], [1, 1])])
def test_packed_binding_rejects_malformed_offsets_and_noncanonical_columns(offsets, values):
    with pytest.raises(ValueError):
        packed(offsets, values)


def test_output_budget_counts_empty_state_offsets_as_well_as_entries():
    result = packed()
    expected_bytes = sum(value.nbytes for value in result.values() if isinstance(value, np.ndarray)) + 32
    assert result["output_bytes"] == expected_bytes
    assert packed(max_output_bytes=expected_bytes)["stored_entries"] == 4
    from cad_integrity import _native
    with pytest.raises(_native.BudgetExceeded, match="output exceeds"):
        packed(max_output_bytes=expected_bytes - 1)
    with pytest.raises(_native.BudgetExceeded, match="output exceeds"):
        packed((0, 0, 0, 0), (), max_output_bytes=64)


def test_direct_columns_collapse_duplicates_and_preserve_signed_int64_labels():
    result = F2ColumnReducer().reduce(((-2, -2, 7), (7, -2)))
    assert result.reduced_columns == ((-2, 7), ())
    assert result.reduction_traces == (((-2, 7),), ((-2, 7), ()))
    assert F2ColumnReducer().reduce(((-(1 << 63), (1 << 63) - 1),)).rank == 1
    with pytest.raises(OverflowError):
        F2ColumnReducer().reduce(((1 << 63,),))
    with pytest.raises(TypeError):
        F2ColumnReducer().reduce(((1.5,),))


@pytest.mark.parametrize("seed", range(12))
def test_full_evidence_matches_independent_integer_bitmask_elimination(seed):
    rng = np.random.default_rng(seed)
    masks = [int(value) for value in rng.integers(0, 1 << 18, size=80)]
    def labels(mask):
        return tuple(row for row in range(18) if mask & (1 << row))
    pivots = {}
    traces, reduced = [], []
    for mask in masks:
        states = [labels(mask)]
        while mask and mask.bit_length() in pivots:
            mask ^= pivots[mask.bit_length()]
            states.append(labels(mask))
        if mask:
            pivots[mask.bit_length()] = mask
        traces.append(tuple(states))
        reduced.append(labels(mask))
    result = F2ColumnReducer().reduce(labels(mask) for mask in masks)
    assert result.reduced_columns == tuple(reduced)
    assert result.reduction_traces == tuple(traces)
    assert result.pivot_columns == tuple((row - 1, labels(mask)) for row, mask in sorted(pivots.items()))
