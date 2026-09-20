from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

VerificationState = Literal["passed", "failed", "inconclusive"]

@dataclass(frozen=True, slots=True)
class VerificationCheck:
    name: str
    detail: str
    state: VerificationState

@dataclass(frozen=True, slots=True)
class VerificationGroup:
    name: str
    checks: tuple[VerificationCheck, ...]

@dataclass(frozen=True, slots=True)
class VerificationGridData:
    title: str
    summary: str
    groups: tuple[VerificationGroup, ...]
    def to_json(self) -> dict[str, Any]:
        return {"title": self.title, "summary": self.summary, "groups": [asdict(group) for group in self.groups]}
