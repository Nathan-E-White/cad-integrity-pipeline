import numpy as np
import pytest
from scipy.sparse import csr_matrix

from cad_integrity.algebra import (
    ChainComplex, ReductionBudget, compute_homology, rank_f2, smith_invariants,
)
from cad_integrity.errors import InvalidChainComplex, InvalidGeometry, ResourceLimitExceeded
from cad_integrity.simplicial import (
    FilteredSimplicialComplex, PersistentHomologyEngine, Simplex, SimplicialComplex,
)


def test_canonical_simplex():
    assert Simplex((3, 1, 2)).vertices == (1, 2, 3)
    assert Simplex((3, 1, 2)) == Simplex((2, 3, 1))
    assert Simplex((1,)).dim == 0


@pytest.mark.parametrize("vertices", [(), (1, 1), (1, "two"), (True, 2), (1.5, 2)])
def test_invalid_simplex(vertices):
    with pytest.raises(InvalidGeometry):
        Simplex(vertices)


@pytest.mark.parametrize("facets,expected", [
    ([], (0,)),
    ([(0,)], (1,)),
    ([(0,), (1,)], (2,)),
    ([(0, 1)], (1, 0)),
    ([(0, 1), (1, 2), (2, 0)], (1, 1)),
    ([(0, 1, 2)], (1, 0, 0)),
    ([(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)], (1, 0, 1)),
    ([(0, 1, 2, 3)], (1, 0, 0, 0)),
])
def test_standard_complexes(facets, expected):
    chain = SimplicialComplex(facets).to_chain_complex()
    assert compute_homology(chain).betti_numbers == expected
    pytest.importorskip("sympy")
    assert compute_homology(chain, coefficients="Z").betti_numbers == expected


def test_boundary_squared_zero():
    complex_ = SimplicialComplex([(0, 1, 2, 3, 4)])
    for degree in range(2, 5):
        product = complex_.boundary_operator(degree-1) @ complex_.boundary_operator(degree)
        product.eliminate_zeros()
        assert product.nnz == 0


def test_reject_non_chain():
    with pytest.raises(InvalidChainComplex, match="!= 0"):
        ChainComplex((csr_matrix((0, 1), dtype=np.int64),
                      csr_matrix([[1]], dtype=np.int64), csr_matrix([[1]], dtype=np.int64)))


def test_reject_dimension_mismatch():
    with pytest.raises(InvalidChainComplex, match="dimensions"):
        ChainComplex((csr_matrix((0, 2), dtype=np.int64), csr_matrix([[1]], dtype=np.int64)))


def test_reject_floating_boundaries():
    with pytest.raises(InvalidChainComplex):
        ChainComplex((csr_matrix(np.empty((0, 1))),))


def test_actual_smith_divisibility():
    pytest.importorskip("sympy")
    assert smith_invariants(csr_matrix([[2, 0], [0, 3]], dtype=np.int64)) == (1, 6)
    assert smith_invariants(csr_matrix([[2, 3]], dtype=np.int64)) == (1,)


def test_integer_torsion_and_field_dependence():
    pytest.importorskip("sympy")
    # Cellular RP^2: one cell in each dimension, d1=0 and d2=2.
    chain = ChainComplex((csr_matrix((0, 1), dtype=np.int64),
                          csr_matrix([[0]], dtype=np.int64), csr_matrix([[2]], dtype=np.int64)))
    integral = compute_homology(chain, coefficients="Z")
    assert integral.betti_numbers == (1, 0, 0)
    assert integral.groups[1].torsion == (2,)
    assert compute_homology(chain).betti_numbers == (1, 1, 1)


def test_snf_torsion_formula_with_nonzero_outgoing_boundary():
    pytest.importorskip("sympy")
    chain = ChainComplex((csr_matrix((0, 1), dtype=np.int64),
                          csr_matrix([[1, 0]], dtype=np.int64),
                          csr_matrix([[0], [6]], dtype=np.int64)))
    report = compute_homology(chain, coefficients="Z")
    assert report.groups[1].betti == 0
    assert report.groups[1].torsion == (6,)


def reference_rank_f2(a):
    a = np.array(a, dtype=np.int64) % 2
    row = 0
    for column in range(a.shape[1]):
        candidates = np.flatnonzero(a[row:, column])
        if not len(candidates):
            continue
        pivot = row + candidates[0]
        a[[row, pivot]] = a[[pivot, row]]
        for i in range(row+1, a.shape[0]):
            if a[i, column]:
                a[i] ^= a[row]
        row += 1
        if row == a.shape[0]:
            break
    return row


@pytest.mark.parametrize("seed", range(10))
def test_sparse_rank_against_independent_dense_elimination(seed):
    a = np.random.default_rng(seed).integers(-3, 4, size=(11, 17), dtype=np.int64)
    assert rank_f2(csr_matrix(a)) == reference_rank_f2(a)


def test_reduction_budgets():
    with pytest.raises(ResourceLimitExceeded):
        rank_f2(csr_matrix(np.eye(4, dtype=np.int64)), ReductionBudget(max_columns=2))
    with pytest.raises(ResourceLimitExceeded):
        smith_invariants(csr_matrix(np.eye(4, dtype=np.int64)), ReductionBudget(max_dense_entries=4))
    with pytest.raises(ResourceLimitExceeded):
        SimplicialComplex([range(20)], max_simplices=20)


def test_true_persistence_triangle_birth_and_fill():
    filtration = FilteredSimplicialComplex({(0,): 0, (1,): 0, (2,): 0,
                                           (0, 1): 1, (1, 2): 1, (0, 2): 2,
                                           (0, 1, 2): 3})
    bars = PersistentHomologyEngine(filtration).compute_persistence_intervals()
    assert [(bar.birth, bar.death) for bar in bars if bar.dimension == 1] == [(2, 3)]
    assert len([bar for bar in bars if bar.dimension == 0 and bar.death is None]) == 1
    for t in (0, 1, 2, 2.5, 3, 5):
        homology = compute_homology(filtration.get_subcomplex_at(t).to_chain_complex())
        for d, beta in enumerate(homology.betti_numbers):
            assert sum(b.dimension == d and b.birth <= t and (b.death is None or t < b.death)
                       for b in bars) == beta


def test_filtration_propagates_earlier_birth():
    filtration = FilteredSimplicialComplex({(0, 1): 5})
    filtration.add_filtered_simplex((0, 1, 2), 2)
    assert all(birth == 2 for _, birth in filtration.ordered())
    with pytest.raises(ValueError):
        filtration.add_filtered_simplex((3,), float("nan"))


def test_zero_length_intervals_explicit():
    filtration = FilteredSimplicialComplex({(0, 1, 2): 0})
    engine = PersistentHomologyEngine(filtration)
    assert len(engine.compute_persistence_intervals()) == 1
    assert len(engine.compute_persistence_intervals(include_zero_length=True)) == 4


def test_empty_persistence():
    assert PersistentHomologyEngine(FilteredSimplicialComplex()).compute_persistence_intervals() == ()
