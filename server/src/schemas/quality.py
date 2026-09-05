"""Quality check Pydantic schemas (Phase 5)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DimensionIssueRead(BaseModel):
    type: str = ""
    character: str = ""
    quote: str = ""
    problem: str = ""
    suggestion: str = ""


class DimensionResultRead(BaseModel):
    dimension: str
    score: float
    issues: list[DimensionIssueRead] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    error: str | None = None


class QualityReportRead(BaseModel):
    chapter_id: int
    novel_id: int
    chapter_title: str
    genre: str
    total_score: float
    dimension_scores: dict[str, float]
    dimension_results: list[DimensionResultRead] = Field(default_factory=list)
    issues: list[DimensionIssueRead] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    provider: str = "unknown"
    model: str = ""
