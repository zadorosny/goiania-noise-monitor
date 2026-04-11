from __future__ import annotations

from pydantic import BaseModel, Field


class Detection(BaseModel):
    """A single detection from one source."""

    source: str
    score: int = Field(ge=0, le=100)
    confidence: str  # "alta", "média", "baixa", "nenhuma"
    sold_out: bool = False
    evidence: list[str] = Field(default_factory=list)
    ticket_links: list[str] = Field(default_factory=list)


class CheckResult(BaseModel):
    """Aggregated result of a full check cycle."""

    detections: list[Detection] = Field(default_factory=list)
    fingerprint: str | None = None
    errors: list[str] = Field(default_factory=list)

    @property
    def has_findings(self) -> bool:
        return any(d.score > 0 for d in self.detections)

    @property
    def max_score(self) -> int:
        if not self.detections:
            return 0
        return max(d.score for d in self.detections)

    @property
    def best_confidence(self) -> str:
        order = {"alta": 3, "média": 2, "baixa": 1, "nenhuma": 0}
        if not self.detections:
            return "nenhuma"
        return max(self.detections, key=lambda d: order.get(d.confidence, 0)).confidence
