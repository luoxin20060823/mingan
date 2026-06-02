from audit.domain.enums import ViolationCategory
from audit.policy.category_rules import normalize_category


def test_normalize_category_detects_fraud_from_word():
    assert normalize_category("刷单返利诈骗", "其他") == ViolationCategory.FRAUD.value


def test_normalize_category_detects_traffic_diversion_from_word():
    assert normalize_category("加微信私聊", "涉政") == ViolationCategory.TRAFFIC_DIVERSION.value


def test_normalize_category_detects_minor_safety_from_word():
    assert normalize_category("未成年裸聊", "色情") == ViolationCategory.MINOR_SAFETY.value


def test_normalize_category_keeps_existing_when_no_policy_keyword():
    assert normalize_category("普通辱骂", "辱骂") == ViolationCategory.ABUSE.value
