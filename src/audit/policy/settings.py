from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from ..domain.enums import ViolationCategory


class RiskThresholds(BaseModel):
    hint: float = Field(default=0.2, ge=0.0, le=1.0)
    warning: float = Field(default=0.5, ge=0.0, le=1.0)
    violation: float = Field(default=0.85, ge=0.0, le=1.0)

    @field_validator("warning")
    @classmethod
    def validate_warning(cls, value: float, info):
        hint = info.data.get("hint")
        if hint is not None and value <= hint:
            raise ValueError("warning threshold must be greater than hint threshold")
        return value

    @field_validator("violation")
    @classmethod
    def validate_violation(cls, value: float, info):
        warning = info.data.get("warning")
        if warning is not None and value <= warning:
            raise ValueError("violation threshold must be greater than warning threshold")
        return value


class PolicySettings(BaseModel):
    risk_thresholds: RiskThresholds = Field(default_factory=RiskThresholds)
    high_risk_categories: list[ViolationCategory] = Field(
        default_factory=lambda: [
            ViolationCategory.POLITICS,
            ViolationCategory.TERROR,
            ViolationCategory.PORN,
            ViolationCategory.MINOR_SAFETY,
        ]
    )

    def high_risk_category_values(self) -> set[str]:
        return {category.value for category in self.high_risk_categories}
