from audit.domain.enums import PlatformAction, RiskLevel, ViolationCategory


def test_risk_level_values():
    assert [x.value for x in RiskLevel] == ["合规", "提示", "警告", "违规"]


def test_violation_category_values():
    assert [x.value for x in ViolationCategory] == [
        "涉政",
        "暴恐",
        "色情",
        "辱骂",
        "违法广告",
        "诈骗",
        "引流",
        "未成年人风险",
        "低俗",
        "其他",
    ]


def test_platform_action_values():
    assert [x.value for x in PlatformAction] == ["pass", "hint", "fold", "delete", "block", "manual_review"]
