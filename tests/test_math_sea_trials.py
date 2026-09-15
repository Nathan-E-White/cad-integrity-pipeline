"""Fixed-seed independent and metamorphic trials for public math seams."""

from collections.abc import Callable

import numpy as np
import pytest
from scipy.sparse import csr_matrix

from cad_integrity.algebra import (
    ChainComplex,
    ReductionBudget,
    compute_homology,
    rank_f2,
    smith_invariants,
)
from cad_integrity.errors import ResourceLimitExceeded
from cad_integrity.f2_reduction import F2ColumnReducer
from cad_integrity.simplicial import FilteredSimplicialComplex, PersistentHomologyEngine


def _dense_rank_f2(values: np.ndarray) -> int:
    """Independent row elimination oracle over F_2."""
    matrix = np.array(values, dtype=np.int64, copy=True) % 2
    pivot_row = 0
    for column in range(matrix.shape[1]):
        candidates = np.flatnonzero(matrix[pivot_row:, column])
        if not len(candidates):
            continue
        pivot = pivot_row + int(candidates[0])
        matrix[[pivot_row, pivot]] = matrix[[pivot, pivot_row]]
        for row in range(pivot_row + 1, matrix.shape[0]):
            if matrix[row, column]:
                matrix[row] ^= matrix[pivot_row]
        pivot_row += 1
        if pivot_row == matrix.shape[0]:
            break
    return pivot_row


def _chain_from_seed(seed: int) -> ChainComplex:
    """Build d1 and a nontrivial integer nullspace-derived d2 exactly."""
    generator = np.random.default_rng(seed)
    rows, free_columns, degree_two_columns = 3, 3, 2
    tail = generator.integers(-2, 3, size=(rows, free_columns), dtype=np.int64)
    d1 = np.hstack((np.eye(rows, dtype=np.int64), tail))
    kernel_basis = np.vstack((-tail, np.eye(free_columns, dtype=np.int64)))
    d2 = kernel_basis @ generator.integers(
        -2, 3, size=(free_columns, degree_two_columns), dtype=np.int64
    )
    assert not (d1 @ d2).any()
    return ChainComplex((
        csr_matrix((0, rows), dtype=np.int64),
        csr_matrix(d1),
        csr_matrix(d2),
    ))


def _live_interval_counts(
    intervals: tuple[object, ...], time: float, dimensions: int
) -> tuple[int, ...]:
    return tuple(
        sum(
            interval.dimension == dimension
            and interval.birth <= time
            and (interval.death is None or time < interval.death)
            for interval in intervals
        )
        for dimension in range(dimensions)
    )


def _sympy_snf_invariants(matrix: csr_matrix) -> tuple[int, ...]:
    pytest.importorskip("sympy", reason="the optional algebra extra is unavailable")
    from sympy import ZZ, Matrix
    from sympy.matrices.normalforms import smith_normal_form

    diagonal = smith_normal_form(Matrix(matrix.toarray().tolist()), domain=ZZ)
    return tuple(abs(int(diagonal[index, index]))
                 for index in range(min(matrix.shape)) if diagonal[index, index])


def test_rank_f2_detects_nontrivial_parity_relation() -> None:
    matrix = csr_matrix(np.array([[1, 1], [1, 1]], dtype=np.int64))
    assert rank_f2(matrix) == 1


@pytest.mark.parametrize("seed", range(12))
def test_rank_f2_matches_independent_dense_elimination_for_seeded_matrices(seed: int) -> None:
    generator = np.random.default_rng(seed)
    values = generator.integers(-5, 6, size=(3 + seed % 5, 2 + seed % 7), dtype=np.int64)
    assert rank_f2(csr_matrix(values)) == _dense_rank_f2(values)


@pytest.mark.parametrize(
    "values",
    [
        np.empty((0, 4), dtype=np.int64),
        np.empty((3, 0), dtype=np.int64),
        np.array([[2, -4, 6], [8, 10, -12]], dtype=np.int64),
    ],
)
def test_rank_f2_handles_empty_rectangular_and_all_even_inputs(values: np.ndarray) -> None:
    assert rank_f2(csr_matrix(values)) == _dense_rank_f2(values)


def test_rank_f2_normalizes_noncanonical_sparse_columns() -> None:
    matrix = csr_matrix(
        (
            np.array([1, 1, 3], dtype=np.int64),
            np.array([0, 0, 1], dtype=np.int32),
            np.array([0, 3], dtype=np.int32),
        ),
        shape=(1, 2),
    )
    assert not matrix.has_canonical_format
    assert rank_f2(matrix) == 1


@pytest.mark.parametrize("seed", range(8))
def test_generated_chain_complexes_satisfy_euler_and_independent_f2_betti(seed: int) -> None:
    chain = _chain_from_seed(seed)
    report = compute_homology(chain)
    ranks = tuple(_dense_rank_f2(chain.boundary(degree).toarray())
                  for degree in range(len(chain.dimensions) + 1))
    expected = tuple(
        dimension - ranks[degree] - ranks[degree + 1]
        for degree, dimension in enumerate(chain.dimensions)
    )
    assert report.betti_numbers == expected
    assert all(betti >= 0 for betti in report.betti_numbers)
    assert sum((-1) ** degree * betti for degree, betti in enumerate(report.betti_numbers)) == (
        chain.euler_characteristic
    )


def test_rank_f2_respects_direct_sums() -> None:
    left = np.array([[1, 1], [1, 0]], dtype=np.int64)
    right = np.array([[2, 1, 0]], dtype=np.int64)
    direct_sum = np.zeros((3, 5), dtype=np.int64)
    direct_sum[:2, :2] = left
    direct_sum[2:, 2:] = right
    assert rank_f2(csr_matrix(direct_sum)) == (
        _dense_rank_f2(left) + _dense_rank_f2(right)
    )


def test_smith_invariants_preserve_torsion_and_direct_sums() -> None:
    left = csr_matrix(np.array([[2]], dtype=np.int64))
    right = csr_matrix(np.array([[3]], dtype=np.int64))
    direct_sum = csr_matrix(np.array([[2, 0], [0, 3]], dtype=np.int64))
    for matrix in (left, right, direct_sum):
        assert smith_invariants(matrix) == _sympy_snf_invariants(matrix)


def test_f2_and_integer_homology_diverge_on_a_torsion_fixture() -> None:
    pytest.importorskip("sympy", reason="the optional algebra extra is unavailable")
    projective_plane = ChainComplex((
        csr_matrix((0, 1), dtype=np.int64),
        csr_matrix([[0]], dtype=np.int64),
        csr_matrix([[2]], dtype=np.int64),
    ))
    integer_report = compute_homology(projective_plane, coefficients="Z")
    assert integer_report.betti_numbers == (1, 0, 0)
    assert integer_report.groups[1].torsion == (2,)
    assert compute_homology(projective_plane).betti_numbers == (1, 1, 1)


@pytest.mark.parametrize(
    ("operation", "axis", "message"),
    [
        (lambda: rank_f2(csr_matrix(np.eye(3, dtype=np.int64)), ReductionBudget(max_columns=2)),
         "input columns", "input"),
        (lambda: rank_f2(csr_matrix(np.eye(3, dtype=np.int64)),
                         ReductionBudget(max_stored_entries=2)), "input stored entries", "input"),
        (lambda: rank_f2(csr_matrix(np.ones((1, 3), dtype=np.int64)),
                         ReductionBudget(max_xor_steps=1)), "XOR steps", "work/storage"),
        (lambda: rank_f2(csr_matrix(np.array([[1, 0], [1, 0], [1, 0], [1, 1]], dtype=np.int64)),
                         ReductionBudget(max_stored_entries=6)), "sparse fill-in", "work/storage"),
        (lambda: smith_invariants(csr_matrix(np.eye(3, dtype=np.int64)),
                                  ReductionBudget(max_dense_entries=8)), "dense SNF entries", "dense"),
    ],
    ids=["columns", "input-storage", "xor-steps", "sparse-fill-in", "dense-snf"],
)
def test_reduction_budget_axes_fail_closed(
    operation: Callable[[], object], axis: str, message: str
) -> None:
    assert axis
    with pytest.raises(ResourceLimitExceeded, match=message):
        operation()


def test_rank_f2_accepts_exact_reduction_budget_boundaries() -> None:
    identity = csr_matrix(np.eye(3, dtype=np.int64))
    assert rank_f2(identity, ReductionBudget(max_columns=3)) == 3
    assert rank_f2(identity, ReductionBudget(max_stored_entries=3)) == 3
    repeated_column = csr_matrix(np.ones((1, 3), dtype=np.int64))
    assert rank_f2(repeated_column, ReductionBudget(max_xor_steps=2)) == 1
    late_fill_in = csr_matrix(np.array([[1, 0], [1, 0], [1, 0], [1, 1]], dtype=np.int64))
    assert rank_f2(late_fill_in, ReductionBudget(max_stored_entries=7)) == 2


def test_static_rank_and_persistence_share_equivalent_xor_budget_boundary() -> None:
    """Both adapters reduce the complete ordered boundary stream of one filtration."""
    filtration_boundary = csr_matrix(np.array([
        [0, 0, 0, 1, 1, 0, 0],
        [0, 0, 0, 1, 0, 1, 0],
        [0, 0, 0, 0, 1, 1, 0],
        [0, 0, 0, 0, 0, 0, 1],
        [0, 0, 0, 0, 0, 0, 1],
        [0, 0, 0, 0, 0, 0, 1],
    ], dtype=np.int64))
    triangle_filtration = FilteredSimplicialComplex({(0, 1, 2): 0.0})

    assert rank_f2(filtration_boundary, ReductionBudget(max_columns=7)) == 3
    assert len(PersistentHomologyEngine(
        triangle_filtration, budget=ReductionBudget(max_columns=7)
    ).compute_persistence_intervals(include_zero_length=True)) == 4
    with pytest.raises(ResourceLimitExceeded):
        rank_f2(filtration_boundary, ReductionBudget(max_columns=6))
    with pytest.raises(ResourceLimitExceeded):
        PersistentHomologyEngine(
            triangle_filtration, budget=ReductionBudget(max_columns=6)
        ).compute_persistence_intervals(include_zero_length=True)

    with pytest.raises(ResourceLimitExceeded, match="work"):
        rank_f2(filtration_boundary, ReductionBudget(max_xor_steps=1))
    with pytest.raises(ResourceLimitExceeded, match="work"):
        PersistentHomologyEngine(
            triangle_filtration, budget=ReductionBudget(max_xor_steps=1)
        ).compute_persistence_intervals(include_zero_length=True)

    assert rank_f2(filtration_boundary, ReductionBudget(max_xor_steps=2)) == 3
    assert len(PersistentHomologyEngine(
        triangle_filtration, budget=ReductionBudget(max_xor_steps=2)
    ).compute_persistence_intervals(include_zero_length=True)) == 4

    assert rank_f2(filtration_boundary, ReductionBudget(max_stored_entries=9)) == 3
    assert len(PersistentHomologyEngine(
        triangle_filtration, budget=ReductionBudget(max_stored_entries=9)
    ).compute_persistence_intervals(include_zero_length=True)) == 4
    with pytest.raises(ResourceLimitExceeded, match="input"):
        rank_f2(filtration_boundary, ReductionBudget(max_stored_entries=8))
    with pytest.raises(ResourceLimitExceeded, match="input"):
        PersistentHomologyEngine(
            triangle_filtration, budget=ReductionBudget(max_stored_entries=8)
        ).compute_persistence_intervals(include_zero_length=True)


def test_f2_reduction_evidence_is_deterministic_immutable_and_matches_worked_table() -> None:
    columns = ((0, 1), (0, 2), (1, 2))
    first = F2ColumnReducer(ReductionBudget(max_xor_steps=2)).reduce(columns)
    second = F2ColumnReducer(ReductionBudget(max_xor_steps=2)).reduce(columns)

    assert first == second
    assert first.reduced_columns == ((0, 1), (0, 2), ())
    assert first.reduction_traces == (((0, 1),), ((0, 2),), ((1, 2), (0, 1), ()))
    assert first.pivot_columns == ((1, (0, 1)), (2, (0, 2)))
    assert (first.rank, first.xor_steps, first.stored_entries) == (2, 2, 4)
    with pytest.raises(AttributeError):
        first.pivot_columns[0][1].add(3)  # type: ignore[attr-defined]


def test_f2_reducer_accepts_exact_limits_and_labels_each_exhaustion() -> None:
    columns = ((0, 1), (0, 2), (1, 2))

    assert F2ColumnReducer(ReductionBudget(max_columns=3)).reduce(columns).rank == 2
    with pytest.raises(ResourceLimitExceeded) as exhausted_input:
        F2ColumnReducer(ReductionBudget(max_columns=2)).reduce(columns)
    assert str(exhausted_input.value) == "F_2 input exceeds the configured reduction budget"

    assert F2ColumnReducer(ReductionBudget(max_stored_entries=6)).reduce(columns).rank == 2
    with pytest.raises(ResourceLimitExceeded) as exhausted_input_storage:
        F2ColumnReducer(ReductionBudget(max_stored_entries=5)).reduce(columns)
    assert str(exhausted_input_storage.value) == "F_2 input exceeds the configured reduction budget"

    with pytest.raises(ResourceLimitExceeded) as exhausted_work:
        F2ColumnReducer(ReductionBudget(max_stored_entries=6)).reduce(((0, 1, 2, 3), (3,)))
    assert str(exhausted_work.value) == "F_2 reduction exceeded its work/storage budget"

    fill_in_columns = ((2, 3, 4, 5), (0, 1, 5), (6,))
    assert F2ColumnReducer(ReductionBudget(max_stored_entries=10)).reduce(
        fill_in_columns
    ).stored_entries == 10
    with pytest.raises(ResourceLimitExceeded) as exhausted_fill_in:
        F2ColumnReducer(ReductionBudget(max_stored_entries=9)).reduce(fill_in_columns)
    assert str(exhausted_fill_in.value) == "F_2 fill-in exceeds the storage budget"


@pytest.mark.parametrize("seed", range(6))
def test_persistence_intervals_equal_independent_sublevel_betti_numbers(seed: int) -> None:
    generator = np.random.default_rng(seed)
    filtration = FilteredSimplicialComplex({
        (0, 1, 2): float(generator.integers(0, 4)),
        (0, 2, 3): float(generator.integers(0, 4)),
        (0, 1, 3): float(generator.integers(0, 4)),
        (1, 2, 3): float(generator.integers(0, 4)),
    })
    intervals = PersistentHomologyEngine(filtration).compute_persistence_intervals()
    for time in sorted({birth for _, birth in filtration.ordered()}):
        betti = compute_homology(filtration.get_subcomplex_at(time).to_chain_complex()).betti_numbers
        assert _live_interval_counts(intervals, time, len(betti)) == betti


def test_equal_time_filtration_orders_faces_before_cofaces_and_labels_zero_length_policy() -> None:
    filtration = FilteredSimplicialComplex({(0, 1, 2): 0.0})
    ordered = filtration.ordered()
    assert [simplex.dim for simplex, _ in ordered] == [0, 0, 0, 1, 1, 1, 2]
    engine = PersistentHomologyEngine(filtration)
    omitted = engine.compute_persistence_intervals()
    included = engine.compute_persistence_intervals(include_zero_length=True)
    assert len(omitted) == 1
    assert len(included) == 4
    assert all(interval.birth == interval.death for interval in included if interval.death is not None)


def test_persistence_default_excludes_zero_length_intervals() -> None:
    filtration = FilteredSimplicialComplex({(0, 1, 2): 0.0})
    intervals = PersistentHomologyEngine(filtration).compute_persistence_intervals()
    assert all(interval.death is None or interval.birth != interval.death for interval in intervals)


def test_persistence_pairs_deterministically_under_filtration_ties() -> None:
    filtration = FilteredSimplicialComplex({
        (0,): 0.0,
        (1,): 0.0,
        (2,): 0.0,
        (0, 1): 1.0,
        (0, 2): 1.0,
        (1, 2): 2.0,
        (0, 1, 2): 3.0,
    })
    intervals = PersistentHomologyEngine(filtration).compute_persistence_intervals(
        include_zero_length=True
    )
    assert [
        (interval.dimension, interval.birth, interval.death,
         interval.birth_simplex, interval.death_simplex)
        for interval in intervals
    ] == [
        (0, 0.0, 1.0, (1,), (0, 1)),
        (0, 0.0, 1.0, (2,), (0, 2)),
        (0, 0.0, None, (0,), None),
        (1, 2.0, 3.0, (1, 2), (0, 1, 2)),
    ]


def test_persistence_reduction_honors_work_and_storage_budgets() -> None:
    tetrahedron = FilteredSimplicialComplex({(0, 1, 2, 3): 0.0})
    with pytest.raises(ResourceLimitExceeded, match="work"):
        PersistentHomologyEngine(
            tetrahedron, budget=ReductionBudget(max_xor_steps=1)
        ).compute_persistence_intervals(include_zero_length=True)
    with pytest.raises(ResourceLimitExceeded, match="input"):
        PersistentHomologyEngine(
            tetrahedron, budget=ReductionBudget(max_stored_entries=1)
        ).compute_persistence_intervals(include_zero_length=True)
    with pytest.raises(ResourceLimitExceeded, match="input"):
        PersistentHomologyEngine(
            tetrahedron, budget=ReductionBudget(max_stored_entries=18)
        ).compute_persistence_intervals(include_zero_length=True)
    assert len(PersistentHomologyEngine(
        tetrahedron, budget=ReductionBudget(max_stored_entries=28)
    ).compute_persistence_intervals(include_zero_length=True)) == 8
