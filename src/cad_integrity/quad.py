"""Owned, topology-driven quad motorcycle traces with exact half-step evidence.

Canonical launches come from extraordinary vertices. Explicit seeds use the same
collision policy but are labelled noncanonical unless they equal that full set.
Coordinates are projections; geometric intersections do not identify mesh carriers.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import numpy as np

from . import _native
from .arrays import FloatArray, IntArray, integers
from .errors import InvalidGeometry, ResourceLimitExceeded
from .models import PolyhedralBRep
from .polygonal_cells import PolygonalLimits


@dataclass(frozen=True, slots=True)
class TraceLimits:
    max_owned_bytes: int = 512_000_000
    max_work_steps: int = 50_000_000
    max_output_bytes: int = 256_000_000
    max_events: int = 1_000_000
    max_segments: int = 1_000_000

    def _values(self) -> tuple[int, int, int, int, int]:
        return (self.max_owned_bytes, self.max_work_steps, self.max_output_bytes,
                self.max_events, self.max_segments)

    def __post_init__(self) -> None:
        for value in self._values():
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 1 << 64:
                raise ValueError("Trace limits must be nonnegative uint64 integers")


@dataclass(frozen=True, slots=True)
class Usage:
    owned_bytes: int
    work_steps: int
    output_bytes: int


@dataclass(frozen=True, slots=True)
class Seed:
    id: int
    vertex: int
    edge: int


class Reason(IntEnum):
    ADVANCE = 0
    BOUNDARY = 1
    DEPOSITED_TRACK = 2
    SELF_COLLISION = 3
    OPPOSING = 4
    SIMULTANEOUS = 5
    RIGHT_HAND = 6
    EXTRAORDINARY = 7


class Stop(IntEnum):
    NONE = 0
    WORK_BUDGET = 1
    EVENT_BUDGET = 2
    SEGMENT_BUDGET = 3
    OUTPUT_BUDGET = 4


@dataclass(frozen=True, slots=True)
class Segment:
    seed: int
    edge: int
    from_vertex: int
    to_vertex: int  # -1 denotes this edge's midpoint, not an invented mesh vertex.
    start2: int
    end2: int


@dataclass(frozen=True, slots=True)
class Event:
    time2: int
    seed: int
    edge: int
    vertex: int
    reason: Reason
    blocker: int
    deposited_time2: int


@dataclass(frozen=True, slots=True)
class TraceResult:
    patch: QuadPatch
    canonical: bool
    stop: Stop
    last_committed_time2: int | None
    seeds: tuple[Seed, ...]
    segments: tuple[Segment, ...]
    events: tuple[Event, ...]
    unfinished: tuple[int, ...]
    usage: Usage

    @property
    def complete(self) -> bool:
        return self.stop == Stop.NONE

    def segment_coordinates(self) -> FloatArray:
        points = []
        for segment in self.segments:
            a = self.patch.vertices[segment.from_vertex]
            if segment.to_vertex < 0:
                # Halve before adding to avoid overflow for extreme finite coordinates.
                ends = self.patch.vertices[self.patch.edges[segment.edge]]
                b = ends[0] * 0.5 + ends[1] * 0.5
            else:
                b = self.patch.vertices[segment.to_vertex]
            points.append((a, b))
        return _immutable(np.asarray(points, dtype=np.float64).reshape(-1, 2, 3))


def _immutable(value: Any) -> Any:
    return np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)


@dataclass(frozen=True, slots=True)
class QuadPatch:
    vertices: FloatArray
    edges: IntArray
    face_offsets: IntArray
    face_coedges: IntArray
    boundary_edges: tuple[int, ...]
    canonical_seeds: tuple[Seed, ...]
    length_unit: str
    usage: Usage
    _handle: _native.QuadPatch = field(repr=False, compare=False)

    def trace(
        self, seeds: Sequence[Seed] | None = None, *, limits: TraceLimits = TraceLimits()
    ) -> TraceResult:
        chosen = self.canonical_seeds if seeds is None else seeds
        values = (integers([(s.id, s.vertex, s.edge) for s in chosen], name="quad seeds", width=3)
                  if len(chosen) else np.empty((0, 3), dtype=np.int64))
        values = np.ascontiguousarray(values.reshape(-1, 3))
        try:
            data = self._handle.trace(values, _native.QuadLimits(*limits._values())).arrays()
        except _native.BudgetExceeded as exc:
            raise ResourceLimitExceeded(str(exc)) from exc
        except ValueError as exc:
            raise InvalidGeometry(str(exc)) from exc
        return TraceResult(
            self, data["canonical"], Stop(data["stop"]), data["last_committed_time2"],
            tuple(Seed(*s) for s in data["seeds"]),
            tuple(Segment(*s) for s in data["segments"]),
            tuple(Event(e[0], e[1], e[2], e[3], Reason(e[4]), e[5], e[6])
                  for e in data["events"]),
            tuple(data["unfinished"]), Usage(**data["usage"]),
        )


def prepare_quad_patch(
    mesh: PolyhedralBRep, *, limits: PolygonalLimits = PolygonalLimits()
) -> QuadPatch:
    """Admit oriented pure quads; retain source ordinals and an immutable native owner."""
    try:
        handle = _native.prepare_quad_patch(
            mesh.vertices, mesh.edges, mesh.face_offsets, mesh.face_coedges, mesh.length_unit,
            limits.max_input_bytes, limits.max_owned_bytes,
            limits.max_work_steps, limits.max_output_bytes,
        )
    except _native.BudgetExceeded as exc:
        raise ResourceLimitExceeded(str(exc)) from exc
    except ValueError as exc:
        raise InvalidGeometry(str(exc)) from exc
    data = handle.arrays()
    return QuadPatch(
        _immutable(np.asarray(data["vertices"], dtype=np.float64)),
        _immutable(np.asarray(data["edges"], dtype=np.int64)),
        _immutable(np.asarray(data["face_offsets"], dtype=np.int64)),
        _immutable(np.asarray(data["face_coedges"], dtype=np.int64)),
        tuple(data["boundary_edges"]), tuple(Seed(*s) for s in data["seeds"]),
        mesh.length_unit, Usage(**data["usage"]), handle,
    )
