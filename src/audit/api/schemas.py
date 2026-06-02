from pydantic import BaseModel, Field, field_validator
import re

from ..domain.enums import RiskLevel, ViolationCategory
from ..domain.models import DisposalSuggestion, HitDetail, ProcessingTime


class AuditTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class AuditTextResponse(BaseModel):
    risk_level: RiskLevel
    violation_category: str
    confidence_score: float
    l1_score: float
    l2_score: float
    l3_score: float
    hit_details: list[HitDetail]
    llm_explanation: str
    disposal_suggestion: DisposalSuggestion
    processing_time: ProcessingTime


class AuditBatchRequest(BaseModel):
    texts: list[str]

    @field_validator("texts")
    @classmethod
    def validate_text_items(cls, value):
        if not 1 <= len(value) <= 50:
            raise ValueError("batch size out of range (1..50)")
        for index, item in enumerate(value):
            if not isinstance(item, str):
                raise ValueError(f"item index {index} must be a string")
            if not item.strip():
                raise ValueError(f"item index {index} must be non-empty")
            if len(item) > 2000:
                raise ValueError(f"item index {index} exceeds 2000 characters")
        return value


class AuditBatchResponse(BaseModel):
    results: list[AuditTextResponse]


class WordCreateRequest(BaseModel):
    word: str = Field(min_length=1, max_length=64)
    category: ViolationCategory
    level: RiskLevel

    @field_validator("word")
    @classmethod
    def validate_word(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("word must not be blank")
        return stripped


class WordResponse(BaseModel):
    id: int
    word: str
    category: str
    level: str
    source: str
    created_at: str


class RegexRuleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    pattern: str = Field(min_length=1, max_length=500)
    category: ViolationCategory
    level: RiskLevel
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, value: str) -> str:
        try:
            re.compile(value)
        except re.error as exc:
            raise ValueError(f"invalid regex pattern: {exc}") from exc
        return value


class RegexRuleResponse(BaseModel):
    id: int
    name: str
    pattern: str
    category: str
    level: str
    source: str
    enabled: bool
    created_at: str


class PageResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list
