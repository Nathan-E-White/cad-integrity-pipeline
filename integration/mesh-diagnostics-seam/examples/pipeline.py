"""Auditing entry point. An existing integration/ audit should bypass this and
call assemble_payload directly with its already-computed results instead.
"""
from pathlib import Path
from mesh_diagnostics import AuditPolicy, audit_mesh, load_triangle_mesh, payload_from_audit


def process_and_audit_mesh(npz_file_path: str | Path) -> dict:
    mesh = load_triangle_mesh(npz_file_path, mesh_id=Path(npz_file_path).stem,
                              stage="original", units="unspecified")
    return payload_from_audit(audit_mesh(mesh, AuditPolicy(min_mean_ratio=0.15))).model_dump()
