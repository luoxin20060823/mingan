from audit.domain.enums import RiskLevel
from audit.domain.models import FinalDecision
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
