"""UI-independent orchestration for the polygonal research path."""
from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass

from .algebra import ReductionBudget
from .errors import IntegrityError, RepairRejected
from .models import PolyhedralBRep
from .repair import WeldPolicy, synchronize_orientations, weld_vertices
from .topology import BRepHomologyStitchAnalyzer, TopologyReport

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StageEvent:
    stage: str
    message: str


@dataclass(frozen=True, slots=True)
class RepairPolicy:
    weld: WeldPolicy | None = None  # No coordinate changes unless the caller opts in.
    synchronize_orientation: bool = True
    coefficients: str = "F2"
    reduction_budget: ReductionBudget = ReductionBudget()


@dataclass(frozen=True, slots=True)
class RepairReport:
    schema_version: str
    input_sha256: str
    before: TopologyReport
    after: TopologyReport | None
    decision: str
    changes: tuple[str, ...]
    maximum_vertex_displacement: float
    length_unit: str
    errors: tuple[str, ...]
    scope: str = "polygonal_combinatorial_diagnostics_not_CAD_certification"


@dataclass(frozen=True, slots=True)
class RepairResult:
    original: PolyhedralBRep
    candidate: PolyhedralBRep | None
    report: RepairReport


def fingerprint(brep: PolyhedralBRep) -> str:
    digest = hashlib.sha256()
    digest.update(brep.length_unit.encode("ascii"))
    for array in (brep.vertices, brep.edges, brep.face_offsets, brep.face_coedges):
        digest.update(str(array.shape).encode("ascii"))
        digest.update(array.astype(array.dtype.newbyteorder("<")).tobytes(order="C"))
    return digest.hexdigest()


class RepairPipeline:
    """The later Gradio callback can consume these events and returned reports.

    Unexpected programming errors propagate. Controlled analysis/repair failures
    become rejected reports, and never overwrite the input or fabricate an output.
    """

    def __init__(self, policy: RepairPolicy = RepairPolicy()) -> None:
        self.policy = policy

    def run(self, brep: PolyhedralBRep, *, on_event: Callable[[StageEvent], None] | None = None
            ) -> RepairResult:
        def event(stage: str, message: str) -> None:
            logger.info("%s: %s", stage, message)
            if on_event is not None:
                on_event(StageEvent(stage, message))

        def analyze(candidate: PolyhedralBRep) -> TopologyReport:
            return BRepHomologyStitchAnalyzer(candidate, coefficients=self.policy.coefficients,
                budget=self.policy.reduction_budget).evaluate_stitch_integrity()

        event("analyze", "Analyzing the input polygonal boundary")
        before = analyze(brep)
        changes = []
        maximum_move = 0.0
        try:
            if before.homology is None:
                raise RepairRejected(before.homology_unavailable_reason or
                                     "Input is not an admissible polygonal cell complex")
            candidate = brep
            if self.policy.weld is not None:
                event("weld", "Attempting explicitly authorized boundary-vertex welding")
                welded = weld_vertices(candidate, self.policy.weld)
                candidate = welded.candidate
                maximum_move = welded.maximum_displacement
                changes.append(f"Merged {welded.removed_vertex_count} vertices and {welded.removed_edge_count} straight edges")
            if self.policy.synchronize_orientation:
                event("orient", "Solving orientation constraints across every component")
                oriented = synchronize_orientations(candidate)
                candidate = oriented.candidate
                changes.append(f"Reversed complete loops on {len(oriented.flipped_face_ids)} faces")
            event("verify", "Re-running diagnostics on the candidate")
            after = analyze(candidate)
            decision = "topology_checks_passed" if after.is_closed_oriented_2manifold else "needs_review"
            report = RepairReport("1.0", fingerprint(brep), before, after, decision,
                                   tuple(changes), maximum_move, brep.length_unit, ())
            event("complete", decision)
            return RepairResult(brep, candidate, report)
        except IntegrityError as exc:
            event("rejected", str(exc))
            report = RepairReport("1.0", fingerprint(brep), before, None, "rejected",
                                   tuple(changes), maximum_move, brep.length_unit, (str(exc),))
            return RepairResult(brep, None, report)
