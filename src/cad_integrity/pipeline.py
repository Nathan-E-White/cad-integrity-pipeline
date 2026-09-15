"""Compatibility imports for the policy-consistent polygonal repair transition."""
from .repair_transition import (
    RepairPipeline,
    RepairPolicy,
    RepairReport,
    RepairResult,
    StageEvent,
    fingerprint,
)

__all__ = [
    "RepairPipeline", "RepairPolicy", "RepairReport", "RepairResult", "StageEvent", "fingerprint",
]
