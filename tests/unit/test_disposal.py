from audit.domain.enums import RiskLevel
from audit.domain.enums import ViolationCategory
from audit.domain.models import FinalDecision, HitDetail
from audit.pipeline.disposal import build_disposal


def test_violation_high_risk_category_blocks():
    decision = FinalDecision(risk_level=RiskLevel.VIOLATION, category="涉政", confidence_score=0.9)
    suggestion = build_disposal(decision, [])
    assert suggestion.platform_action.value == "block"
    assert "违规" in suggestion.operation_note


def test_warning_low_risk_category_folds():
    decision = FinalDecision(risk_level=RiskLevel.WARNING, category="辱骂", confidence_score=0.6)
    suggestion = build_disposal(decision, [])
    assert suggestion.platform_action.value == "fold"


def test_disposal_note_includes_explainable_hit_details():
    decision = FinalDecision(risk_level=RiskLevel.HINT, category="违法广告", confidence_score=0.2)
    hit = HitDetail(
        layer="L1",
        engine="ahocorasick",
        matched_word="招聘",
        original_fragment="招聘",
        start=0,
        end=2,
        category=ViolationCategory.ILLEGAL_AD,
        level=RiskLevel.HINT,
        flags=["low_confidence_generic"],
    )

    suggestion = build_disposal(decision, [hit])

    assert "L1/ahocorasick/违法广告/提示:招聘" in suggestion.operation_note
    assert "low_confidence_generic" in suggestion.operation_note
