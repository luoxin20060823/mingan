from dataclasses import dataclass

from audit.pipeline.l1_rule import L1RuleEngine, compute_layer_score
from audit.domain.enums import RiskLevel, ViolationCategory
from audit.domain.models import HitDetail


@dataclass
class Word:
    word: str
    category: str
    level: str


def test_l1_empty_text_returns_zero_score():
    result = L1RuleEngine([Word("坏词", "其他", "违规")]).scan("")
    assert result.score == 0.0
    assert result.hits == []


def test_l1_hit_uses_word_metadata_and_positions():
    result = L1RuleEngine([Word("坏词", "其他", "违规")]).scan("这是坏词")
    assert result.score >= 0.85
    assert result.hits[0].matched_word == "坏词"
    assert result.hits[0].start == 2
    assert result.hits[0].end == 4
    assert result.hits[0].category == ViolationCategory.OTHER


def test_compute_layer_score_respects_warning_band():
    hit = HitDetail(
        layer="L1",
        engine="ahocorasick",
        matched_word="词",
        original_fragment="词",
        start=0,
        end=1,
        category=ViolationCategory.OTHER,
        level=RiskLevel.WARNING,
    )
    assert compute_layer_score([hit]) == 0.5


def test_l1_regex_rule_detects_phone_number():
    engine = L1RuleEngine(
        [Word("坏词", "其他", "违规")],
        regex_rules=[{"name": "phone", "pattern": r"1[3-9]\d{9}", "category": "违法广告", "level": "警告"}],
    )

    result = engine.scan("联系我 13800138000")

    assert result.score >= 0.5
    assert any(hit.engine == "regex:phone" and hit.matched_word == "phone" for hit in result.hits)


def test_l1_normalizes_traffic_diversion_category():
    result = L1RuleEngine([Word("加微信私聊", "其他", "警告")]).scan("想了解更多请加微信私聊")

    assert any(hit.category.value == "引流" for hit in result.hits)


def test_l1_downgrades_generic_term_without_risk_context():
    result = L1RuleEngine([Word("招聘", "违法广告", "违规")]).scan("我们正在招聘后端工程师")

    assert result.score == 0.2
    assert result.hits[0].level == RiskLevel.HINT
    assert "low_confidence_generic" in result.hits[0].flags


def test_l1_keeps_generic_term_high_risk_with_context():
    result = L1RuleEngine([Word("兼职", "违法广告", "违规")]).scan("兼职刷单返利稳赚")

    assert result.score >= 0.85
    assert result.hits[0].level == RiskLevel.VIOLATION
    assert "generic_with_risk_context" in result.hits[0].flags


def test_l1_builds_ahocorasick_automaton():
    engine = L1RuleEngine([Word("坏词", "其他", "违规")])

    assert engine.automaton is not None


def test_l1_ignores_low_quality_single_character_seed_terms():
    result = L1RuleEngine([Word("令", "其他", "警告"), Word("p", "其他", "警告")]).scan("命令执行器输出 p 参数")

    assert result.score == 0.0
    assert result.hits == []


def test_l1_ignores_common_benign_seed_terms_without_risk_context():
    result = L1RuleEngine([Word("价格", "涉政", "警告"), Word("完成", "其他", "警告")]).scan(
        "审批模型未配置价格，接口验证已经完成。"
    )

    assert result.score == 0.0
    assert result.hits == []
