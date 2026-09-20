from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

@dataclass(frozen=True, slots=True)
class DeltaAuditRow:
    category: Literal["geometry", "topology", "execution"]
    entity: str
    before: str
    after: str
    delta: str

@dataclass(frozen=True, slots=True)
class TopologicalDeltaAuditData:
    title: str
    rows: tuple[DeltaAuditRow, ...]
    def to_json(self) -> dict[str, Any]:
        return {"title": self.title, "rows": [asdict(row) for row in self.rows]}
