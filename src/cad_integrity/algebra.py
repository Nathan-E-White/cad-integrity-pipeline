"""Small-complex homology with declared coefficients and bounded exact arithmetic.

The default field is F_2, NOT R or Z. The optional integer reference path uses
SymPy's Smith normal form, not an ad hoc elimination labeled as SNF.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.sparse import csr_matrix

from .errors import InvalidChainComplex, MissingOptionalDependency, ResourceLimitExceeded
from .f2_reduction import F2ColumnReducer, ReductionBudget


@dataclass(frozen=True, slots=True)
class HomologyGroup:
    dimension: int
    betti: int
    torsion: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class HomologyReport:
    coefficients: str
    groups: tuple[HomologyGroup, ...]
    euler_characteristic: int

    @property
    def betti_numbers(self) -> tuple[int, ...]:
        return tuple(group.betti for group in self.groups)


class ChainComplex:
    """Finite chain complex of free integer groups; matrices map columns to rows.

    boundaries[d] has shape (n[d-1], n[d]); boundaries[0] is (0, n[0]).
    The data is copied. Every adjacent product is checked exactly in int64 after
    bounding coefficients to avoid overflow in that validation multiplication.
    """

    def __init__(self, boundaries: tuple[csr_matrix, ...]) -> None:
        if not boundaries:
            boundaries = (csr_matrix((0, 0), dtype=np.int64),)
        converted = []
        for boundary in boundaries:
            if boundary.dtype.kind not in "iu":
                raise InvalidChainComplex("Boundary coefficients must be integers")
            if boundary.nnz and max(abs(int(x)) for x in boundary.data) > 1_000_000:
                raise InvalidChainComplex("Reference backend limits coefficients to 10^6")
            matrix = boundary.astype(np.int64).tocsr(copy=True)
            matrix.sum_duplicates()
            matrix.eliminate_zeros()
            converted.append(matrix)
        self._boundaries = tuple(converted)
        if self._boundaries[0].shape[0] != 0:
            raise InvalidChainComplex("Use unreduced homology: boundary[0] must have zero rows")
        for d in range(1, len(self._boundaries)):
            left, right = self._boundaries[d-1:d+1]
            if left.shape[1] != right.shape[0]:
                raise InvalidChainComplex(f"Boundary dimensions disagree at d={d}")
            a = max((abs(int(x)) for x in left.data), default=0)
            b = max((abs(int(x)) for x in right.data), default=0)
            if a * b * left.shape[1] > np.iinfo(np.int64).max:
                raise InvalidChainComplex("Boundary product could overflow int64")
            product = left @ right
            product.eliminate_zeros()
            if product.nnz:
                raise InvalidChainComplex(f"boundary[{d-1}] @ boundary[{d}] != 0")

    @property
    def dimensions(self) -> tuple[int, ...]:
        return tuple(int(matrix.shape[1]) for matrix in self._boundaries)

    def boundary(self, d: int) -> csr_matrix:
        if d < 0:
            raise ValueError("Boundary degree must be nonnegative")
        if d >= len(self._boundaries):
            rows = self.dimensions[-1] if d == len(self._boundaries) else 0
            return csr_matrix((rows, 0), dtype=np.int64)
        return self._boundaries[d].copy()

    @property
    def euler_characteristic(self) -> int:
        return sum((-1)**d * n for d, n in enumerate(self.dimensions))


def rank_f2(matrix: csr_matrix, budget: ReductionBudget = ReductionBudget()) -> int:
    """Exact sparse column reduction over F_2; bounded, not a large-scale solver."""
    if matrix.dtype.kind not in "iu":
        raise InvalidChainComplex("F_2 reduction requires integer coefficients")
    csc = matrix.tocsc(copy=True)
    csc.sum_duplicates()
    columns = []
    for j in range(csc.shape[1]):
        lo, hi = csc.indptr[j:j+2]
        columns.append(
            tuple(int(i) for i, value in zip(csc.indices[lo:hi], csc.data[lo:hi], strict=True)
                  if int(value) % 2)
        )
    return F2ColumnReducer(budget).reduce(columns).rank


def smith_invariants(matrix: csr_matrix, budget: ReductionBudget = ReductionBudget()) -> tuple[int, ...]:
    """Positive, nonzero integer SNF invariant factors (divisibility order)."""
    if matrix.dtype.kind not in "iu":
        raise InvalidChainComplex("SNF requires integer coefficients")
    if matrix.shape[0] * matrix.shape[1] > budget.max_dense_entries:
        raise ResourceLimitExceeded("Integer reference computation exceeds the dense-entry budget")
    if 0 in matrix.shape or matrix.nnz == 0:
        return ()
    try:
        from sympy import ZZ, Matrix
        from sympy.matrices.normalforms import smith_normal_form
    except ImportError as exc:
        raise MissingOptionalDependency("Install cad-integrity-lab[algebra]") from exc
    diagonal = smith_normal_form(Matrix(matrix.toarray().tolist()), domain=ZZ)
    return tuple(abs(int(diagonal[i, i])) for i in range(min(matrix.shape)) if diagonal[i, i])


def compute_homology(chain: ChainComplex, *, coefficients: str = "F2",
                     budget: ReductionBudget = ReductionBudget()) -> HomologyReport:
    """Compute free ranks and, for Z, torsion of a validated integer chain complex."""
    if coefficients not in {"F2", "Z"}:
        raise ValueError("Supported coefficients are 'F2' and 'Z'")
    if coefficients == "F2":
        ranks = [rank_f2(chain.boundary(d), budget) for d in range(len(chain.dimensions)+1)]
        invariants: list[tuple[int, ...]] = [()] * len(ranks)
    else:
        invariants = [smith_invariants(chain.boundary(d), budget)
                      for d in range(len(chain.dimensions)+1)]
        ranks = [len(values) for values in invariants]
    groups = tuple(HomologyGroup(d, n-ranks[d]-ranks[d+1],
                                 tuple(v for v in invariants[d+1] if v > 1))
                   for d, n in enumerate(chain.dimensions))
    if any(group.betti < 0 for group in groups):
        raise InvalidChainComplex("Negative Betti number: inconsistent boundary data")
    # For Z, torsion(coker d_{k+1}) = torsion(H_k), because im d_k is free.
    # Thus the original adjacent-SNF formula is valid IF d^2=0 and the SNFs are correct.
    report = HomologyReport(coefficients, groups, chain.euler_characteristic)
    if sum((-1)**g.dimension * g.betti for g in groups) != chain.euler_characteristic:
        raise InvalidChainComplex("Euler-Poincare check failed")
    return report


class HomologyEngine:
    """Small convenience interface for objects exposing to_chain_complex()."""

    def __init__(self, complex_: Any, *, coefficients: str = "F2",
                 budget: ReductionBudget = ReductionBudget()) -> None:
        self.chain = complex_ if isinstance(complex_, ChainComplex) else complex_.to_chain_complex()
        self.coefficients, self.budget = coefficients, budget

    def report(self) -> HomologyReport:
        return compute_homology(self.chain, coefficients=self.coefficients, budget=self.budget)

    def compute_all_betti_numbers(self) -> dict[int, int]:
        return {g.dimension: g.betti for g in self.report().groups}


class IntegralHomologyEngine(HomologyEngine):
    def __init__(self, complex_: Any, *, budget: ReductionBudget = ReductionBudget()) -> None:
        super().__init__(complex_, coefficients="Z", budget=budget)

    def compute_all_groups(self) -> dict[int, HomologyGroup]:
        return {g.dimension: g for g in self.report().groups}
