"""Versioned JSON boundary, shared by Gradio and any other transport adapter."""
from __future__ import annotations
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, model_validator

Status = Literal["info", "pass", "warn", "fail", "not_checked"]
Identifier = Annotated[str, Field(min_length=1, max_length=256)]
Index = Annotated[StrictInt, Field(ge=0)]
Number = StrictInt | StrictFloat


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class FaceTarget(WireModel):
    id: Identifier
    geometry_revision: Identifier
    kind: Literal["faces"] = "faces"
    ids: list[Index] = Field(max_length=500_000)


class EdgeTarget(WireModel):
    id: Identifier
    geometry_revision: Identifier
    kind: Literal["edges"] = "edges"
    indices: list[Index] = Field(max_length=3_000_000)


class SegmentTarget(WireModel):
    """Unclassified WORLD-space segments, chiefly for legacy payload adaptation."""
    id: Identifier
    geometry_revision: Identifier
    kind: Literal["segments"] = "segments"
    positions: list[Number] = Field(max_length=3_000_000)


Target = Annotated[FaceTarget | EdgeTarget | SegmentTarget, Field(discriminator="kind")]


class Metric(WireModel):
    id: Identifier
    label: Annotated[str, Field(min_length=1, max_length=256)]
    value: Number | str | None
    status: Status
    description: str = Field(default="", max_length=4096)
    target_id: Identifier | None = None


class MeshPayload(WireModel):
    schema_version: Literal["mesh-diagnostics/1"] = "mesh-diagnostics/1"
    mesh_id: Identifier
    geometry_revision: Identifier
    diagnostic_revision: Identifier
    stage: Identifier = "unspecified"
    units: Identifier = "unspecified"
    positions: list[Number] = Field(max_length=750_000)
    triangles: list[Index] = Field(max_length=1_500_000)
    # Optional mapping to upstream polygon/native-face identity; local to this revision.
    triangle_parent_faces: list[Index] | None = Field(default=None, max_length=500_000)
    targets: list[Target] = Field(default_factory=list, max_length=128)
    metrics: list[Metric] = Field(default_factory=list, max_length=512)
    notes: list[str] = Field(default_factory=list, max_length=128)

    @model_validator(mode="after")
    def validate_relations(self) -> "MeshPayload":
        if len(self.positions) % 3 or len(self.triangles) % 3:
            raise ValueError("positions and triangles must be flat triples")
        nv, nf = len(self.positions)//3, len(self.triangles)//3
        if self.triangles and max(self.triangles) >= nv:
            raise ValueError("triangle index is outside the vertex array")
        if self.triangle_parent_faces is not None and len(self.triangle_parent_faces) != nf:
            raise ValueError("triangle_parent_faces must have one entry per triangle")
        target_ids = set()
        total_scalars = 0
        for target in self.targets:
            if target.id in target_ids:
                raise ValueError(f"duplicate target id: {target.id}")
            target_ids.add(target.id)
            if target.geometry_revision != self.geometry_revision:
                raise ValueError(f"target {target.id} belongs to a different geometry revision")
            if isinstance(target, FaceTarget):
                total_scalars += len(target.ids)
                if target.ids and max(target.ids) >= nf:
                    raise ValueError(f"target {target.id} contains an out-of-range triangle id")
            elif isinstance(target, EdgeTarget):
                total_scalars += len(target.indices)
                if len(target.indices) % 2 or (target.indices and max(target.indices) >= nv):
                    raise ValueError(f"target {target.id} must contain valid vertex-index pairs")
            else:
                total_scalars += len(target.positions)
                if len(target.positions) % 6:
                    raise ValueError(f"target {target.id} must contain coordinate sextuples")
        if total_scalars > 6_000_000:
            raise ValueError("combined targets exceed the inline diagnostic budget")
        metric_ids = set()
        for metric in self.metrics:
            if metric.id in metric_ids:
                raise ValueError(f"duplicate metric id: {metric.id}")
            metric_ids.add(metric.id)
            if metric.target_id is not None and metric.target_id not in target_ids:
                raise ValueError(f"metric {metric.id} references an unknown target")
        # JavaScript identity integers must be exactly representable.
        if self.triangle_parent_faces and max(self.triangle_parent_faces) > 2**53-1:
            raise ValueError("parent face IDs must be JavaScript-safe integers")
        return self
