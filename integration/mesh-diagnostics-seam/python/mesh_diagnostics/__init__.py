"""Small reusable seams; Gradio is intentionally not imported here."""
from .model import MeshLimits, MeshValidationError, TriangleMesh
from .quality import TriangleQuality, triangle_quality
from .topology import EdgeTopology, edge_topology
from .audit import AuditPolicy, AuditResult, audit_mesh
from .contract import EdgeTarget, FaceTarget, SegmentTarget, Metric, MeshPayload
from .payload import assemble_payload, payload_from_audit
from .legacy import adapt_legacy_payload, mesh_from_mapping
from .io import ArchiveLimits, load_npz_arrays, load_triangle_mesh

__all__ = ["MeshLimits", "MeshValidationError", "TriangleMesh", "TriangleQuality", "triangle_quality",
    "EdgeTopology", "edge_topology", "AuditPolicy", "AuditResult", "audit_mesh", "EdgeTarget",
    "FaceTarget", "SegmentTarget", "Metric", "MeshPayload", "assemble_payload", "payload_from_audit",
    "adapt_legacy_payload", "mesh_from_mapping", "ArchiveLimits", "load_npz_arrays", "load_triangle_mesh"]
