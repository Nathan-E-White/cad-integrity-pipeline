"""Bounded, deterministic sparse column reduction over F2."""

from collections.abc import Iterable
from dataclasses import dataclass
from operator import index as integer_index
from typing import Literal

import numpy as np

from . import _native
from .errors import ResourceLimitExceeded


@dataclass(frozen=True, slots=True)
class ReductionBudget:
    max_columns: int = 50_000
    max_stored_entries: int = 2_000_000
    max_xor_steps: int = 2_000_000
    max_dense_entries: int = 250_000
    max_trace_entries: int = 8_000_000
    max_output_bytes: int = 256_000_000

    def __post_init__(self) -> None:
        if min(self.max_columns, self.max_stored_entries, self.max_xor_steps,
               self.max_dense_entries, self.max_trace_entries, self.max_output_bytes) < 1:
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

    def reduce(
        self, columns: Iterable[Iterable[int]], *,
        evidence: Literal["rank_only", "reduced_columns", "full_trace"] = "full_trace",
    ) -> F2ReductionEvidence:
        """Reduce integer-label sets; omitted evidence is returned as empty tuples.

        Native input uses explicit int64 normalization. Matrix coefficient parity
        remains the matrix caller's responsibility. No Python fallback is used.
        """
        offsets = [0]
        values: list[int] = []
        for count, column in enumerate(columns, start=1):
            if count > self._budget.max_columns:
                raise ResourceLimitExceeded("F_2 input exceeds the configured reduction budget")
            canonical: set[int] = set()
            for value in column:
                label = integer_index(value)
                if not -(1 << 63) <= label < (1 << 63):
                    raise OverflowError("F_2 row labels must fit signed int64")
                canonical.add(label)
                if len(values) + len(canonical) > self._budget.max_stored_entries:
                    raise ResourceLimitExceeded("F_2 input exceeds the configured reduction budget")
            values.extend(sorted(canonical))
            offsets.append(len(values))
        try:
            result = _native.reduce_f2(
                np.asarray(offsets, dtype=np.int64), np.asarray(values, dtype=np.int64), evidence,
                self._budget.max_columns, self._budget.max_stored_entries,
                self._budget.max_xor_steps, self._budget.max_trace_entries,
                self._budget.max_output_bytes,
            )
        except _native.BudgetExceeded as error:
            raise ResourceLimitExceeded(str(error)) from error

        def unpack(offset_key: str, value_key: str) -> tuple[tuple[int, ...], ...]:
            packed = result[value_key].tolist()
            bounds = result[offset_key].tolist()
            return tuple(tuple(packed[start:end]) for start, end in zip(bounds[:-1], bounds[1:], strict=True))

        pivots = unpack("pivot_offsets", "pivot_values")
        states = unpack("state_offsets", "state_values")
        bounds = result["trace_offsets"].tolist()
        return F2ReductionEvidence(
            reduced_columns=unpack("reduced_offsets", "reduced_values"),
            reduction_traces=tuple(states[start:end] for start, end in zip(bounds[:-1], bounds[1:], strict=True)),
            pivot_columns=tuple((column[-1], column) for column in pivots),
            xor_steps=result["xor_steps"], stored_entries=result["stored_entries"],
        )
