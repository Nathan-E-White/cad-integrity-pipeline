"""Versioned JSON display DTOs. IDs are revision-local, never native CAD identity."""
from __future__ import annotations

import math
from typing import Annotated, Any, Literal, Self
from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_VERTICES = 500_000
MAX_TRIANGLES = 250_000
MAX_PATH_POINTS = 500_000
MAX_SAFE_INTEGER = 2**53 - 1
WireText = Annotated[str, Field(max_length=1024)]
SourceFaceId = Annotated[int, Field(ge=0, le=MAX_SAFE_INTEGER)]
Status = Literal["info", "pass", "warn", "fail", "unknown"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class ScalarField(Contract):
    id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=256)
    association: Literal["face"] = "face"
    values: list[float | None] = Field(max_length=MAX_TRIANGLES)
    domain: list[float] = Field(default_factory=lambda: [0.0, 1.0], min_length=2, max_length=2)
    better: Literal["higher", "lower", "neither"] = "neither"
    unit: WireText | None = None

    @model_validator(mode="after")
    def ordered_domain(self) -> Self:
        if self.domain[1] <= self.domain[0] or not math.isfinite(self.domain[1] - self.domain[0]):
            raise ValueError("Scalar domain must be strictly increasing")
        return self


class Trace(Contract):
    id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=256)
    points: list[float] = Field(min_length=6, max_length=3 * MAX_PATH_POINTS)
    status: Literal["active", "terminated", "cycle_detected", "iteration_limit", "unknown"] = "unknown"
    termination_reason: str | None = Field(default=None, max_length=512)
    provenance: Literal["computed", "imported", "synthetic_fixture"] = "imported"

    @model_validator(mode="after")
    def triples(self) -> Self:
        if len(self.points) % 3:
            raise ValueError("Path points must be xyz triples")
        return self


class Selection(Contract):
    id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=256)
    face_ids: list[int] = Field(default_factory=list, max_length=MAX_TRIANGLES)
    edge_pairs: list[int] = Field(default_factory=list, max_length=6 * MAX_TRIANGLES)
    # For diagnostics defined on another carrier, e.g. polygonal B-Rep edges.
    segments: list[float] = Field(default_factory=list, max_length=18 * MAX_TRIANGLES)
    path_ids: list[Annotated[str, Field(min_length=1, max_length=128)]] = Field(default_factory=list, max_length=10_000)


class Metric(Contract):
    id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=256)
    value: float | int | WireText | None
    status: Status = "info"
    selection_id: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    scope: str = Field(default="Display diagnostic; not solver/CAD certification", max_length=1024)


class MeshPayload(Contract):
    id: str = Field(min_length=1, max_length=128)
    revision: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=256)
    frame_id: str = Field(min_length=1, max_length=128)
    length_unit: str | None = Field(default=None, max_length=32)
    positions: list[float] = Field(max_length=3 * MAX_VERTICES)
    triangles: list[int] = Field(max_length=3 * MAX_TRIANGLES)
    # Optional display triangle -> source polygon row. NOT a native CAD face ID.
    triangle_source_faces: list[SourceFaceId] | None = Field(default=None, max_length=MAX_TRIANGLES)
    fields: list[ScalarField] = Field(default_factory=list, max_length=32)
    selections: list[Selection] = Field(default_factory=list, max_length=256)
    metrics: list[Metric] = Field(default_factory=list, max_length=256)
    paths: list[Trace] = Field(default_factory=list, max_length=10_000)
    provenance: str = Field(default="Imported triangle display mesh", max_length=1024)

    @model_validator(mode="before")
    @classmethod
    def aggregate_budgets(cls, value: Any) -> Any:
        """Check raw collection lengths before Pydantic copies nested numeric lists."""
        if not isinstance(value, dict):
            return value
        for collection, columns, item_limit, total_limit, message in (
            ("paths", ("points",), 10_000, 3 * MAX_PATH_POINTS, "Total path point budget exceeded"),
            ("selections", ("face_ids", "edge_pairs", "segments"), 256, 8_000_000, "Selection data budget exceeded"),
        ):
            items = value.get(collection, [])
            if not isinstance(items, list):
                continue  # Strict field validation rejects non-list values.
            if len(items) > item_limit:
                raise ValueError(message)
            total = 0
            for item in items:
                for column in columns:
                    if isinstance(item, dict):
                        values = item.get(column, [])
                    elif isinstance(item, Contract):
                        values = getattr(item, column, [])
                    else:
                        continue
                    if isinstance(values, list):
                        total += len(values)
                        if total > total_limit:
                            raise ValueError(message)
        return value

    @model_validator(mode="after")
    def valid_references(self) -> Self:
        # Nested, already-created model instances may bypass before validation.
        self.aggregate_budgets({"paths": self.paths, "selections": self.selections})
        if len(self.positions) % 3 or len(self.triangles) % 3:
            raise ValueError("positions and triangles must contain complete xyz/triangle triples")
        nv, nf = len(self.positions) // 3, len(self.triangles) // 3
        if any(i < 0 or i >= nv for i in self.triangles):
            raise ValueError("Triangle vertex index out of range")
        for name in ("fields", "selections", "metrics", "paths"):
            items = getattr(self, name)
            if len({item.id for item in items}) != len(items):
                raise ValueError(f"Duplicate {name} IDs")
        if any(len(f.values) != nf for f in self.fields):
            raise ValueError("Each face scalar must have exactly one value per triangle")
        if self.triangle_source_faces is not None:
            if len(self.triangle_source_faces) != nf or any(i < 0 or i > MAX_SAFE_INTEGER for i in self.triangle_source_faces):
                raise ValueError("Source face mapping must be nonnegative and triangle-sized")
        selections = {s.id for s in self.selections}
        paths = {p.id for p in self.paths}
        for selection in self.selections:
            if any(i < 0 or i >= nf for i in selection.face_ids):
                raise ValueError(f"Selection {selection.id}: face ID out of range")
            if len(set(selection.face_ids)) != len(selection.face_ids):
                raise ValueError(f"Selection {selection.id}: duplicate face IDs")
            if len(selection.edge_pairs) % 2 or any(i < 0 or i >= nv for i in selection.edge_pairs):
                raise ValueError(f"Selection {selection.id}: invalid edge vertex pair")
            if len(selection.segments) % 6:
                raise ValueError(f"Selection {selection.id}: segments require six coordinates")
            if not set(selection.path_ids) <= paths:
                raise ValueError(f"Selection {selection.id}: unknown path reference")
        if any(m.selection_id is not None and m.selection_id not in selections for m in self.metrics):
            raise ValueError("Metric references an unknown selection")
        return self


class InspectorDocument(Contract):
    schema_version: Literal[1] = 1
    meshes: list[MeshPayload] = Field(default_factory=list, max_length=2)
    linked_views: bool = True

    @model_validator(mode="after")
    def coherent_views(self) -> Self:
        if len({m.id for m in self.meshes}) != len(self.meshes):
            raise ValueError("Duplicate mesh IDs")
        if self.linked_views and len(self.meshes) == 2:
            a, b = self.meshes
            if a.frame_id != b.frame_id or a.length_unit != b.length_unit:
                raise ValueError("Linked views require identical explicit frames and units")
            right_fields = {f.id: f for f in b.fields}
            for field in a.fields:
                other = right_fields.get(field.id)
                if other is not None and (field.domain != other.domain or field.unit != other.unit):
                    raise ValueError("Compared fields with the same ID require a shared domain and unit")
        return self
