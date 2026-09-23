"""Owned UV location and complete candidate evidence on admitted polygonal charts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from . import _native
from .arrays import FloatArray, IntArray
from .errors import InvalidGeometry, ResourceLimitExceeded
from .surface import AdmittedChart, ParameterizationError


@dataclass(frozen=True, slots=True)
class LocationPolicy:
    barycentric_tolerance: float = 1e-9
    xyz_relative_tolerance: float = 1e-8

    def __post_init__(self) -> None:
        for value in (self.barycentric_tolerance, self.xyz_relative_tolerance):
            if not np.isfinite(value) or value < 0:
                raise ValueError("UV tolerances must be finite and nonnegative")


@dataclass(frozen=True, slots=True)
class LocationLimits:
    max_input_bytes: int = 256_000_000
    max_owned_bytes: int = 512_000_000
    max_work_steps: int = 50_000_000
    max_output_bytes: int = 256_000_000
    max_candidates_per_query: int = 1_000_000

    def __post_init__(self) -> None:
        for value in self._values():
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 1 << 64:
                raise ValueError("UV limits must be nonnegative uint64 integers")

    def _values(self) -> tuple[int, int, int, int, int]:
        return (
            self.max_input_bytes,
            self.max_owned_bytes,
            self.max_work_steps,
            self.max_output_bytes,
            self.max_candidates_per_query,
        )

    def _native_limits(self) -> _native.UVLimits:
        return _native.UVLimits(*self._values())


@dataclass(frozen=True, slots=True)
class LocationUsage:
    input_bytes: int
    owned_bytes: int
    work_steps: int
    output_bytes: int


class LocationStatus(IntEnum):
    OUTSIDE = 0
    UNIQUE = 1
    AGREEING = 2
    AMBIGUOUS = 3
    BUDGET_EXCEEDED = 4


class ExhaustedLimit(IntEnum):
    STORAGE = 3
    WORK = 4
    OUTPUT = 5
    CANDIDATES = 6


@dataclass(frozen=True, slots=True)
class Exhaustion:
    limit: ExhaustedLimit
    first_unfinished_query: int
    triangle: int | None


@dataclass(frozen=True, slots=True)
class Location:
    status: LocationStatus
    resolved: tuple[float, float, float] | None
    maximum_discrepancy: float


@dataclass(frozen=True, slots=True)
class Locations:
    records: tuple[Location, ...]
    offsets: NDArray[np.uint64]
    triangles: IntArray
    source_faces: IntArray
    barycentric: FloatArray
    xyz: FloatArray
    policy: LocationPolicy
    usage: LocationUsage
    exhaustion: Exhaustion | None
    _handle: _native.UVLocations = field(repr=False, compare=False)


def _immutable(value: Any) -> Any:
    return np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)


@dataclass(frozen=True, slots=True)
class Locator:
    _handle: _native.UVLocator = field(repr=False, compare=False)

    @property
    def usage(self) -> LocationUsage:
        return LocationUsage(**self._handle.usage())

    def locate(self, queries: ArrayLike, *, limits: LocationLimits = LocationLimits()) -> Locations:
        # Host normalization and immutable projections allocate outside native limits.
        values = np.ascontiguousarray(queries, dtype=np.float64)
        if values.ndim != 2 or values.shape[1] != 2:
            raise InvalidGeometry("UV queries require (Q,2) coordinates")
        try:
            handle = self._handle.locate(values, limits._native_limits())
        except _native.BudgetExceeded as exc:
            raise ResourceLimitExceeded(str(exc)) from exc
        except ValueError as exc:
            raise InvalidGeometry(str(exc)) from exc
        data = handle.arrays()
        records = tuple(
            Location(
                LocationStatus(int(status)),
                (
                    float(data["resolved"][i, 0]),
                    float(data["resolved"][i, 1]),
                    float(data["resolved"][i, 2]),
                )
                if data["valid"][i]
                else None,
                float(data["discrepancy"][i]),
            )
            for i, status in enumerate(data["status"])
        )
        exhausted = data["exhaustion"]
        return Locations(
            records,
            _immutable(data["offsets"]),
            _immutable(data["triangles"]),
            _immutable(data["source_faces"]),
            _immutable(data["barycentric"]),
            _immutable(data["xyz"]),
            LocationPolicy(*data["policy"]),
            LocationUsage(**data["usage"]),
            None
            if exhausted is None
            else Exhaustion(
                ExhaustedLimit(exhausted[0]),
                exhausted[1],
                None if exhausted[2] < 0 else exhausted[2],
            ),
            handle,
        )

    def sample(
        self, queries: ArrayLike, *, limits: LocationLimits = LocationLimits()
    ) -> FloatArray:
        result = self.locate(queries, limits=limits)
        if result.exhaustion is not None:
            e = result.exhaustion
            raise ResourceLimitExceeded(
                f"UV query {e.first_unfinished_query}: {e.limit.name} budget"
            )
        for i, record in enumerate(result.records):
            if record.status == LocationStatus.OUTSIDE:
                raise InvalidGeometry(f"UV query {i}: outside chart")
            if record.status == LocationStatus.AMBIGUOUS:
                raise ParameterizationError(f"UV query {i}: ambiguous overlapping triangles")
        return _immutable(
            np.asarray([r.resolved for r in result.records], dtype=np.float64).reshape(-1, 3)
        )


def prepare_locator(
    chart: AdmittedChart,
    *,
    policy: LocationPolicy = LocationPolicy(),
    limits: LocationLimits = LocationLimits(),
) -> Locator:
    if not isinstance(chart, AdmittedChart):
        raise TypeError("UV location requires an admitted chart")
    try:
        # Only the native chart is authoritative; never reconstruct from wrapper projections.
        handle = _native.prepare_uv_locator(
            chart._handle,
            policy.barycentric_tolerance,
            policy.xyz_relative_tolerance,
            limits._native_limits(),
        )
    except _native.BudgetExceeded as exc:
        raise ResourceLimitExceeded(str(exc)) from exc
    except ValueError as exc:
        raise InvalidGeometry(str(exc)) from exc
    return Locator(handle)
