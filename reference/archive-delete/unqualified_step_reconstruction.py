"""Record why a generic STEP sew-and-solidify operation is not available.

The archived script indiscriminately submitted an entire imported shape to
OCCT sewing and attempted to turn resulting shells into solids.  That loses
the provenance needed to distinguish intended joins from nearby, unrelated
geometry.  The product has a selected-wire, evidence-backed native path instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReconstructionRequest:
    source: Path
    tolerance_mm: float
    status: str
    reason: str


def inspect_reconstruction_request(step_path: str | Path, *, tolerance_mm: float = 1e-3) -> ReconstructionRequest:
    """Validate a request and return an explicit refusal of global sewing.

    A genuine implementation requires source-fingerprinted classifier evidence,
    explicit complete wire selection, ownership checks, and checked candidate
    export.  A tolerance alone is not design intent.
    """
    source = Path(step_path)
    if not source.is_file() or source.suffix.lower() not in {".step", ".stp"}:
        raise ValueError("step_path must name an existing .step or .stp file")
    if tolerance_mm <= 0:
        raise ValueError("tolerance_mm must be positive")
    return ReconstructionRequest(
        source.resolve(), tolerance_mm, "not_established",
        "Refusing generic whole-shape sewing and solidification without selected-boundary evidence.",
    )
