"""Deterministic simplicial complexes and actual F_2 persistence intervals."""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import combinations
from numbers import Integral

import numpy as np
from scipy.sparse import csr_matrix

from .algebra import ChainComplex, ReductionBudget
from .errors import InvalidGeometry, ResourceLimitExceeded
from .f2_reduction import F2ColumnReducer


@dataclass(frozen=True, slots=True, order=True)
class Simplex:
    """Canonical vertex ordering. Input labels must be integer IDs."""
    vertices: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.vertices or any(isinstance(v, bool) or not isinstance(v, Integral)
                                    for v in self.vertices):
            raise InvalidGeometry("A simplex needs one or more integer vertex IDs")
        vertices = tuple(sorted(int(v) for v in self.vertices))
        if len(set(vertices)) != len(vertices):
            raise InvalidGeometry("Repeated vertices in a simplex")
        object.__setattr__(self, "vertices", vertices)

    @property
    def dim(self) -> int:
        return len(self.vertices) - 1

    def codimension_one_faces(self) -> tuple[Simplex, ...]:
        if self.dim == 0:
            return ()
        return tuple(Simplex(self.vertices[:i] + self.vertices[i+1:])
                     for i in range(len(self.vertices)))


def _closure(simplex: Simplex, limit: int) -> Iterable[Simplex]:
    if (1 << len(simplex.vertices)) - 1 > limit:
        raise ResourceLimitExceeded("Simplex closure exceeds the simplex budget")
    return (Simplex(face) for size in range(1, len(simplex.vertices)+1)
            for face in combinations(simplex.vertices, size))


class SimplicialComplex:
    """Immutable downward closure; geometry and input facet orientation are not stored."""

    def __init__(self, facets: Iterable[Iterable[int]] = (), *, max_simplices: int = 50_000) -> None:
        if max_simplices < 1:
            raise ValueError("max_simplices must be positive")
        simplices: set[Simplex] = set()
        for vertices in facets:
            for simplex in _closure(Simplex(tuple(vertices)), max_simplices):
                simplices.add(simplex)
                if len(simplices) > max_simplices:
                    raise ResourceLimitExceeded("Complex exceeds the simplex budget")
        self.simplices = tuple(sorted(simplices, key=lambda s: (s.dim, s.vertices)))
        self.max_dim = max((s.dim for s in self.simplices), default=0)
        self._by_dim = tuple(tuple(s for s in self.simplices if s.dim == d)
                             for d in range(self.max_dim+1))

    def get_simplices_of_dim(self, d: int) -> tuple[Simplex, ...]:
        return self._by_dim[d] if 0 <= d < len(self._by_dim) else ()

    def boundary_operator(self, d: int) -> csr_matrix:
        if d < 0:
            raise ValueError("Boundary degree must be nonnegative")
        current = self.get_simplices_of_dim(d)
        lower = self.get_simplices_of_dim(d-1)
        lookup = {s: i for i, s in enumerate(lower)}
        rows, cols, values = [], [], []
        for j, simplex in enumerate(current):
            for k, face in enumerate(simplex.codimension_one_faces()):
                rows.append(lookup[face])
                cols.append(j)
                values.append((-1)**k)
        return csr_matrix((np.asarray(values, dtype=np.int64), (rows, cols)),
                          shape=(len(lower), len(current)), dtype=np.int64)

    def to_chain_complex(self) -> ChainComplex:
        return ChainComplex(tuple(self.boundary_operator(d) for d in range(self.max_dim+1)))


class FilteredSimplicialComplex:
    """Insertions propagate minimum birth time to every face, enforcing a filtration."""

    def __init__(self, facet_filtrations: Mapping[tuple[int, ...], float] | None = None,
                 *, max_simplices: int = 50_000) -> None:
        if max_simplices < 1:
            raise ValueError("max_simplices must be positive")
        self._births: dict[Simplex, float] = {}
        self.max_simplices = max_simplices
        for vertices, birth in (facet_filtrations or {}).items():
            self.add_filtered_simplex(vertices, birth)

    def add_filtered_simplex(self, vertices: Iterable[int], birth_time: float) -> None:
        if not math.isfinite(birth_time):
            raise ValueError("Filtration birth times must be finite")
        faces = tuple(_closure(Simplex(tuple(vertices)), self.max_simplices))
        if len(self._births.keys() | set(faces)) > self.max_simplices:
            raise ResourceLimitExceeded("Filtration exceeds the simplex budget")
        for face in faces:
            self._births[face] = min(self._births.get(face, math.inf), float(birth_time))

    def ordered(self) -> tuple[tuple[Simplex, float], ...]:
        return tuple(sorted(self._births.items(), key=lambda item:
                            (item[1], item[0].dim, item[0].vertices)))

    def get_subcomplex_at(self, t: float) -> SimplicialComplex:
        if math.isnan(t):
            raise ValueError("Filtration query cannot be NaN")
        return SimplicialComplex((s.vertices for s, birth in self._births.items() if birth <= t),
                                 max_simplices=self.max_simplices)


@dataclass(frozen=True, slots=True)
class PersistenceInterval:
    dimension: int
    birth: float
    death: float | None  # None means infinity; intervals are [birth, death).
    birth_simplex: tuple[int, ...]
    death_simplex: tuple[int, ...] | None
    coefficients: str = "F2"


class PersistentHomologyEngine:
    """Standard boundary-column pairing over F_2, not repeated Betti snapshots."""

    def __init__(self, complex_: FilteredSimplicialComplex,
                 budget: ReductionBudget = ReductionBudget()) -> None:
        self.complex, self.budget = complex_, budget

    def compute_persistence_intervals(self, *, include_zero_length: bool = False
                                     ) -> tuple[PersistenceInterval, ...]:
        ordered = self.complex.ordered()
        if len(ordered) > self.budget.max_columns:
            raise ResourceLimitExceeded("Filtration exceeds the reduction budget")
        index = {simplex: i for i, (simplex, _) in enumerate(ordered)}
        births: set[int] = set()
        paired_births: set[int] = set()
        result = []
        evidence = F2ColumnReducer(self.budget).reduce(
            (tuple(index[face] for face in simplex.codimension_one_faces())
             for simplex, _ in ordered), evidence="reduced_columns",
        )
        for j, ((simplex, death), reduced_column) in enumerate(
                zip(ordered, evidence.reduced_columns, strict=True)):
            if reduced_column:
                i = reduced_column[-1]
                paired_births.add(i)
                born_simplex, birth = ordered[i]
                if include_zero_length or birth != death:
                    result.append(PersistenceInterval(born_simplex.dim, birth, death,
                                                       born_simplex.vertices, simplex.vertices))
            else:
                births.add(j)
        for i in sorted(births - paired_births):
            simplex, birth = ordered[i]
            result.append(PersistenceInterval(simplex.dim, birth, None, simplex.vertices, None))
        return tuple(sorted(result, key=lambda bar: (bar.dimension, bar.birth,
                                                     math.inf if bar.death is None else bar.death,
                                                     bar.birth_simplex)))
