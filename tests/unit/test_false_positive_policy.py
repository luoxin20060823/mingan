from audit.domain.enums import RiskLevel, ViolationCategory
from audit.policy.false_positive import adjust_hit_confidence


def test_generic_term_is_downgraded_without_risk_context():
    level, flags = adjust_hit_confidence("招聘", ViolationCategory.ILLEGAL_AD, RiskLevel.VIOLATION, "公司发布招聘信息")

    assert level == RiskLevel.HINT
    assert "low_confidence_generic" in flags


def test_generic_term_keeps_level_with_risk_context():
    level, flags = adjust_hit_confidence("兼职", ViolationCategory.ILLEGAL_AD, RiskLevel.VIOLATION, "兼职刷单返利稳赚")

    assert level == RiskLevel.VIOLATION
    assert "generic_with_risk_context" in flags
