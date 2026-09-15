"""Bounded, deterministic sparse column reduction over F2."""

from collections.abc import Iterable
from dataclasses import dataclass

from .errors import ResourceLimitExceeded


@dataclass(frozen=True, slots=True)
class ReductionBudget:
    max_columns: int = 50_000
    max_stored_entries: int = 2_000_000
    max_xor_steps: int = 2_000_000
    max_dense_entries: int = 250_000

    def __post_init__(self) -> None:
        if min(self.max_columns, self.max_stored_entries, self.max_xor_steps,
               self.max_dense_entries) < 1:
            raise ValueError("All reduction budgets must be positive")


@dataclass(frozen=True, slots=True)
class F2ReductionEvidence:
    """Immutable canonical evidence for one ordered F2 column reduction."""

    reduced_columns: tuple[tuple[int, ...], ...]
    reduction_traces: tuple[tuple[tuple[int, ...], ...], ...]
    pivot_columns: tuple[tuple[int, tuple[int, ...]], ...]
    xor_steps: int
    stored_entries: int

    @property
    def rank(self) -> int:
        return len(self.pivot_columns)


class F2ColumnReducer:
    """Own pivot ownership and bounded XOR/fill-in accounting for F2 columns."""

    def __init__(self, budget: ReductionBudget = ReductionBudget()) -> None:
        self._budget = budget

    def reduce(self, columns: Iterable[Iterable[int]]) -> F2ReductionEvidence:
        pivots: dict[int, set[int]] = {}
        reduced_columns: list[tuple[int, ...]] = []
        reduction_traces: list[tuple[tuple[int, ...], ...]] = []
        input_entries = stored = steps = 0
        for index, values in enumerate(columns, start=1):
            if index > self._budget.max_columns:
                raise ResourceLimitExceeded("F_2 input exceeds the configured reduction budget")
            column = set(values)
            input_entries += len(column)
            if input_entries > self._budget.max_stored_entries:
                raise ResourceLimitExceeded("F_2 input exceeds the configured reduction budget")
            trace = [tuple(sorted(column))]
            while column:
                pivot = max(column)
                previous = pivots.get(pivot)
                if previous is None:
                    stored += len(column)
                    if stored > self._budget.max_stored_entries:
                        raise ResourceLimitExceeded("F_2 fill-in exceeds the storage budget")
                    pivots[pivot] = column
                    break
                column ^= previous
                trace.append(tuple(sorted(column)))
                steps += 1
                if (steps > self._budget.max_xor_steps
                        or stored + len(column) > self._budget.max_stored_entries):
                    raise ResourceLimitExceeded("F_2 reduction exceeded its work/storage budget")
            reduced_columns.append(tuple(sorted(column)))
            reduction_traces.append(tuple(trace))
        return F2ReductionEvidence(
            reduced_columns=tuple(reduced_columns),
            reduction_traces=tuple(reduction_traces),
            pivot_columns=tuple(
                (pivot, tuple(sorted(column))) for pivot, column in sorted(pivots.items())
            ),
            xor_steps=steps,
            stored_entries=stored,
        )
