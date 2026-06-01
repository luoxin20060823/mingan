from dataclasses import dataclass
from time import perf_counter

from audit.pipeline.l1_rule import L1RuleEngine
from audit.pipeline.l2_variant import L2VariantEngine


@dataclass
class Word:
    word: str
    category: str
    level: str


def test_l1_scans_demo_sized_input_under_budget():
    words = [Word(f"演示敏感词{i}", "其他", "提示") for i in range(1000)]
    engine = L1RuleEngine(words)
    text = "正常内容" * 250 + "演示敏感词999"

    started = perf_counter()
    result = engine.scan(text)
    elapsed_ms = (perf_counter() - started) * 1000

    assert result.score >= 0.2
    assert elapsed_ms < 200


def test_l2_scans_demo_sized_input_under_budget():
    words = [Word("坏词", "其他", "违规")]
    engine = L2VariantEngine(words)
    text = ("正常内容" * 250) + "huai ci"

    started = perf_counter()
    result = engine.scan(text)
    elapsed_ms = (perf_counter() - started) * 1000

    assert result.elapsed_ms >= 0
    assert elapsed_ms < 1000
