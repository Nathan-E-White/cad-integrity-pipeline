"""Admission of raw polygonal carriers to the restricted cellular topology path.

This module establishes combinatorial cell facts only.  It neither validates an
embedded CAD model nor establishes geometry, outwardness, or material volume.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix

from . import _native
from .algebra import ChainComplex
from .errors import InvalidGeometry, ResourceLimitExceeded
from .models import PolyhedralBRep

INADMISSIBLE_REASON = "Inadmissible polygonal cells: refusing a misleading homology result"
_ADMISSION_TOKEN = object()


@dataclass(frozen=True, slots=True)
class PolygonalLimits:
    """Logical native limits; separate from homology reduction budgets and RSS."""

    max_input_bytes: int = 256_000_000
    max_owned_bytes: int = 512_000_000
    max_work_steps: int = 50_000_000
    max_output_bytes: int = 256_000_000

    def __post_init__(self) -> None:
        for value in (self.max_input_bytes, self.max_owned_bytes,
                      self.max_work_steps, self.max_output_bytes):
            if not isinstance(value, int) or not 0 <= value < 1 << 64:
                raise ValueError("Polygonal limits must be nonnegative uint64 integers")


@dataclass(frozen=True, slots=True, init=False)
class ValidatedPolygonalCells:
    """Chain-authorized snapshot; raw is the source reference, not matrix storage."""

    raw: PolyhedralBRep
    _boundaries: tuple[csr_matrix, ...]

    def __init__(self, raw: PolyhedralBRep, *, _admission_token: object,
                 _boundaries: tuple[csr_matrix, ...]) -> None:
        if _admission_token is not _ADMISSION_TOKEN:
            raise InvalidGeometry("Polygonal cells require successful admission")
        object.__setattr__(self, "raw", raw)
        object.__setattr__(self, "_boundaries", _boundaries)

    def to_chain_complex(self) -> ChainComplex:
        """Copy and exactly validate the signed incidence from the assessed snapshot."""
        return ChainComplex(self._boundaries)


@dataclass(frozen=True, slots=True)
class PolygonalCellAdmission:
    """Complete admission evidence; invalid raw carriers intentionally have no view."""

    cells: ValidatedPolygonalCells | None
    nonmanifold_edge_ids: tuple[int, ...]
    nonmanifold_vertex_ids: tuple[int, ...]
    unused_vertex_ids: tuple[int, ...]
    unused_edge_ids: tuple[int, ...]
    invalid_face_ids: tuple[int, ...]
    duplicate_face_ids: tuple[int, ...]
    collapsed_edge_ids: tuple[int, ...]
    boundary_edge_ids: tuple[int, ...] = ()
    inconsistent_orientation_edge_ids: tuple[int, ...] = ()
    orientation_multipliers: tuple[int, ...] = ()
    orientation_conflicts: tuple[int, ...] = ()
    orientation_nonmanifold_edge: int | None = None
    signed_edge_uses: tuple[tuple[int, tuple[tuple[int, int], ...]], ...] = ()

    @property
    def reason(self) -> str | None:
        return None if self.cells is not None else INADMISSIBLE_REASON

    def require_cells(self) -> ValidatedPolygonalCells:
        if self.cells is None:
            raise InvalidGeometry(self.reason)
        return self.cells


def edge_uses(brep: PolyhedralBRep) -> dict[int, list[tuple[int, int]]]:
    """Project signed uses from the same native assessment used by admission."""
    return {edge: list(uses) for edge, uses in admit_polygonal_cells(brep).signed_edge_uses}


def admit_polygonal_cells(
    raw: PolyhedralBRep, *, limits: PolygonalLimits = PolygonalLimits(),
) -> PolygonalCellAdmission:
    """Assess once; retain complete diagnostics and optional owned signed incidence."""
    try:
        result = _native.assess_polygonal(
            raw.vertices, raw.edges, raw.face_offsets, raw.face_coedges, raw.length_unit,
            limits.max_input_bytes, limits.max_owned_bytes,
            limits.max_work_steps, limits.max_output_bytes,
        )
    except _native.BudgetExceeded as error:
        raise ResourceLimitExceeded(str(error)) from error
    except ValueError as error:
        raise InvalidGeometry(str(error)) from error

    def ids(name: str) -> tuple[int, ...]:
        return tuple(int(value) for value in result[name])

    cells = None
    if result["admitted"]:
        matrices = []
        for key in ("d1", "d2"):
            offsets, columns, values, shape = result[key]
            matrices.append(csr_matrix((values, columns, offsets), shape=tuple(shape), copy=True))
        cells = ValidatedPolygonalCells(
            raw, _admission_token=_ADMISSION_TOKEN,
            _boundaries=(csr_matrix((0, matrices[0].shape[0]), dtype=np.int64), *matrices),
        )
    bounds = result["edge_offsets"].tolist()
    faces, signs = result["edge_faces"].tolist(), result["edge_signs"].tolist()
    uses = tuple(
        (int(edge), tuple(zip(faces[bounds[edge]:bounds[edge+1]],
                             signs[bounds[edge]:bounds[edge+1]], strict=True)))
        for edge in result["edge_order"].tolist()
    )
    return PolygonalCellAdmission(
        cells=cells,
        nonmanifold_edge_ids=ids("nonmanifold_edge_ids"),
        nonmanifold_vertex_ids=ids("nonmanifold_vertex_ids"),
        unused_vertex_ids=ids("unused_vertex_ids"), unused_edge_ids=ids("unused_edge_ids"),
        invalid_face_ids=ids("invalid_face_ids"), duplicate_face_ids=ids("duplicate_face_ids"),
        collapsed_edge_ids=ids("collapsed_edge_ids"), boundary_edge_ids=ids("boundary_edge_ids"),
        inconsistent_orientation_edge_ids=ids("inconsistent_orientation_edge_ids"),
        orientation_multipliers=ids("multipliers"), orientation_conflicts=ids("conflicting_edge_ids"),
        orientation_nonmanifold_edge=result["orientation_nonmanifold_edge"], signed_edge_uses=uses,
    )
