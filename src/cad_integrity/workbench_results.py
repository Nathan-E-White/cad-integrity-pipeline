"""Retained result contracts for local CAD workbench runs.

This module deliberately knows nothing about STEP, OCP, or polygonal topology.
Named controllers supply their geometry-specific evidence; this module gives every
completed, incomplete, or failed run the same honest release and presentation shape.
"""
from __future__ import annotations

import shutil
import tempfile
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class Completion(StrEnum):
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


class CheckState(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_RUN = "NOT RUN"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT APPLICABLE"


def verification_summary(checks: tuple[CheckResult, ...]) -> str:
    """Summarize the check ledger consistently across retained and live projections."""
    if any(check.status is CheckState.FAILED for check in checks):
        return "Needs review"
    if any(check.status is CheckState.UNAVAILABLE for check in checks):
        return "Unavailable"
    if any(check.status is CheckState.NOT_RUN for check in checks) or not any(
        check.status is CheckState.PASSED for check in checks
    ):
        return "Not verified"
    return "Passed"


def verification_markdown(checks: tuple[CheckResult, ...]) -> str:
    """Render the shared verification heading, summary, and check ledger."""
    lines = ["## Verification", f"Verification: {verification_summary(checks)}"]
    for check in checks:
        suffix = f" — {check.detail}" if check.detail else ""
        lines.append(f"- {check.name} [{check.status.value}]{suffix}")
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    status: CheckState
    detail: str = ""


@dataclass(frozen=True, slots=True)
class Diagnostic:
    stage: str
    message: str
    location: str | None = None


@dataclass(frozen=True, slots=True)
class DecisionBrief:
    """Human-readable projection of a workbench outcome."""

    outcome: str
    candidate_available: bool
    markdown: str
    dashboard_markdown: str | None = None
    dashboard_data: Any | None = None


@dataclass(frozen=True, slots=True)
class RetainedArtifact:
    role: str
    label: str
    path: Path


@dataclass(frozen=True, slots=True)
class ArtifactRelease:
    """The actual retained files from one run; it is intentionally non-atomic."""

    source: RetainedArtifact
    candidate: RetainedArtifact | None
    derived: tuple[RetainedArtifact, ...]
    expires_at: datetime

    def until_label(self) -> str:
        """Use local machine time; this is also the user's time in the local lab."""
        return f"Link active until {self.expires_at.astimezone().strftime('%H:%M')}"


@dataclass(slots=True)
class ReleaseDraft:
    """Mutable inventory for one deliberately non-atomic retained-artifact release."""

    source: RetainedArtifact
    expires_at: datetime
    candidate: RetainedArtifact | None = None
    derived: list[RetainedArtifact] = field(default_factory=list)

    def until_label(self) -> str:
        return f"Link active until {self.expires_at.astimezone().strftime('%H:%M')}"

    def record(self, artifact: RetainedArtifact, *, candidate: bool = False) -> None:
        """Add only an artifact that has already been written successfully."""
        if not artifact.path.is_file():
            raise ValueError(f"Cannot retain missing artifact: {artifact.role}")
        if candidate:
            if self.candidate is not None:
                raise ValueError("A release can retain only one candidate artifact")
            self.candidate = artifact
        else:
            self.derived.append(artifact)

    def preview(self, *pending_derived: RetainedArtifact) -> ArtifactRelease:
        """Describe the eventual inventory before its last artifact is written."""
        return ArtifactRelease(
            source=self.source,
            candidate=self.candidate,
            derived=(*self.derived, *pending_derived),
            expires_at=self.expires_at,
        )

    def finalize(self) -> ArtifactRelease:
        """Return the inventory of artifacts actually retained so far."""
        return self.preview()


@dataclass(frozen=True, slots=True)
class WorkbenchOutcome:
    """Small public controller result, independent of the geometry method used."""

    completion: Completion
    checks: tuple[CheckResult, ...]
    diagnostics: tuple[Diagnostic, ...]
    decision_brief: DecisionBrief
    release: ArtifactRelease | None
    original_figure: Any | None
    candidate_figure: Any | None


class ArtifactStore:
    """Bounded local request-artifact storage; not a production evidence store."""

    def __init__(self, root: Path | None = None, *, retention_seconds: int = 3_600) -> None:
        if retention_seconds < 1:
            raise ValueError("Artifact retention must be positive")
        self.root = root or Path(tempfile.gettempdir()) / "cad-integrity-gradio"
        self.retention_seconds = retention_seconds

    def create_request_directory(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        cutoff = time.time() - self.retention_seconds
        for candidate in self.root.iterdir():
            if candidate.is_dir() and candidate.stat().st_mtime < cutoff:
                shutil.rmtree(candidate)
        return Path(tempfile.mkdtemp(prefix="request-", dir=self.root))

    def release(
        self,
        *,
        source: RetainedArtifact,
        candidate: RetainedArtifact | None,
        derived: tuple[RetainedArtifact, ...],
    ) -> ArtifactRelease:
        draft = self.begin_release(source)
        if candidate is not None:
            draft.record(candidate, candidate=True)
        for artifact in derived:
            draft.record(artifact)
        return draft.finalize()

    def begin_release(self, source: RetainedArtifact) -> ReleaseDraft:
        """Start an expiry-bound release only after its retained source exists."""
        if not source.path.is_file():
            raise ValueError(f"Cannot release missing artifact: {source.role}")
        return ReleaseDraft(
            source=source,
            expires_at=datetime.fromtimestamp(time.time() + self.retention_seconds, UTC),
        )


def with_outcome_details(
    brief: DecisionBrief,
    *,
    completion: Completion,
    checks: tuple[CheckResult, ...],
    diagnostics: tuple[Diagnostic, ...] = (),
    release: ArtifactRelease | None = None,
) -> DecisionBrief:
    """Render the common completion/check ledger without a second source of truth."""
    lines = [
        brief.markdown,
        "",
        "## Completion",
        f"Completion: {completion.value.title()}",
        "",
        verification_markdown(checks),
    ]
    if diagnostics:
        lines.extend(("", "## Diagnostics"))
        for diagnostic in diagnostics:
            location = f" ({diagnostic.location})" if diagnostic.location else ""
            lines.append(f"- {diagnostic.stage}{location}: {diagnostic.message}")
    if release is not None:
        lines.extend(("", "## Availability", f"- {release.until_label()}"))
    return DecisionBrief(
        brief.outcome,
        brief.candidate_available,
        "\n".join(lines),
        brief.dashboard_markdown,
        brief.dashboard_data,
    )


def failed_outcome(stage: str, message: str) -> WorkbenchOutcome:
    """Return expected validation/admission failures as normal controller results."""
    brief = DecisionBrief("Request failed", False, "## Decision\nRequest could not be run.")
    checks = (CheckResult(stage, CheckState.FAILED, message),)
    diagnostics = (Diagnostic(stage, message),)
    return WorkbenchOutcome(
        Completion.FAILED,
        checks,
        diagnostics,
        with_outcome_details(brief, completion=Completion.FAILED, checks=checks, diagnostics=diagnostics),
        None,
        None,
        None,
    )
