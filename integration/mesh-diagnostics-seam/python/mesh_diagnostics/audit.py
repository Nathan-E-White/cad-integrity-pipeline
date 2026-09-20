"""Application policy over independent numeric results. No Gradio dependency."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import numpy as np
from .model import TriangleMesh
from .quality import TriangleQuality, triangle_quality
from .topology import EdgeTopology, edge_topology


@dataclass(frozen=True, slots=True)
class AuditPolicy:
    require_closed_surface: bool = True
    min_mean_ratio: float = 0.15
    max_radius_aspect: float = 3.0
    relative_area_tolerance: float = 1e-12

    def __post_init__(self) -> None:
        if not isinstance(self.require_closed_surface, bool):
            raise ValueError("require_closed_surface must be boolean")
        if not np.isfinite(self.min_mean_ratio) or not 0 <= self.min_mean_ratio <= 1:
            raise ValueError("min_mean_ratio must be in [0,1]")
        if not np.isfinite(self.max_radius_aspect) or self.max_radius_aspect < 1:
            raise ValueError("max_radius_aspect must be finite and >= 1")
        if not np.isfinite(self.relative_area_tolerance) or not 0 <= self.relative_area_tolerance < 1:
            raise ValueError("relative_area_tolerance must be in [0,1)")


@dataclass(frozen=True, slots=True)
class AuditResult:
    mesh: TriangleMesh
    topology: EdgeTopology
    quality: TriangleQuality
    policy: AuditPolicy


def audit_mesh(mesh: TriangleMesh, policy: AuditPolicy = AuditPolicy(), *,
               reference_normals: np.ndarray | None = None) -> AuditResult:
    return AuditResult(mesh, edge_topology(mesh), triangle_quality(
        mesh, relative_area_tolerance=policy.relative_area_tolerance,
        reference_normals=reference_normals), policy)
