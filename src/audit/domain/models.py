from typing import Literal

from pydantic import BaseModel, Field

from .enums import PlatformAction, RiskLevel, ViolationCategory


class HitDetail(BaseModel):
    layer: Literal["L1", "L2", "L3"]
    engine: str
    matched_word: str = ""
    original_fragment: str = ""
    start: int
    end: int
    category: ViolationCategory
    level: RiskLevel
    flags: list[str] = Field(default_factory=list)


class LayerResult(BaseModel):
    score: float
    hits: list[HitDetail] = Field(default_factory=list)
    elapsed_ms: int


class L3Result(LayerResult):
    risk_level: RiskLevel | None = None
    category: ViolationCategory | None = None
    explanation: str = ""
    error: str | None = None


class FinalDecision(BaseModel):
    risk_level: RiskLevel
    category: str = ""
    confidence_score: float
    l1_score: float = 0.0
    l2_score: float = 0.0
    l3_score: float = 0.0
    l1_hits: list[HitDetail] = Field(default_factory=list)
    l2_hits: list[HitDetail] = Field(default_factory=list)
    l3_hits: list[HitDetail] = Field(default_factory=list)
    l1_available: bool = True
    l2_available: bool = True
    l3_available: bool = True


class DisposalSuggestion(BaseModel):
    platform_action: PlatformAction
    user_message: str
    operation_note: str


class ProcessingTime(BaseModel):
    l1_ms: int
    l2_ms: int
    l3_ms: int
    total_ms: int


class AuditRecord(BaseModel):
    id: int
    text: str
    risk_level: RiskLevel
    violation_category: str
    confidence_score: float
    l1_score: float
    l2_score: float
    l3_score: float
    hit_details_json: str
    llm_explanation: str
    disposal_suggestion_json: str
    processing_time_json: str
    created_at: str
