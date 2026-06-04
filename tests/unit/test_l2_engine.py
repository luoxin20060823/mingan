from dataclasses import dataclass
from time import perf_counter

from audit.pipeline.l2_variant import L2VariantEngine


@dataclass
class Word:
    word: str
    category: str
    level: str


def test_l2_empty_text_returns_zero_score():
    result = L2VariantEngine([Word("坏词", "其他", "违规")]).scan("   ")
    assert result.score == 0.0
    assert result.hits == []


def test_l2_whitespace_variant_scores_six_tenths():
    result = L2VariantEngine([Word("坏词", "其他", "违规")]).scan("坏 词")
    assert result.score == 0.6
    assert result.hits[0].engine == "whitespace"


def test_l2_stripper_reports_multiple_hits():
    result = L2VariantEngine([Word("坏词", "其他", "违规")]).scan("坏 词 和 坏 词")

    whitespace_hits = [hit for hit in result.hits if hit.engine == "whitespace"]
    assert len(whitespace_hits) == 2
    assert whitespace_hits[0].start == 0
    assert whitespace_hits[1].start > whitespace_hits[0].start


def test_l2_pinyin_variant_scores_nine_tenths():
    result = L2VariantEngine([Word("坏词", "其他", "违规")]).scan("huaici")
    assert result.score == 0.9
    assert result.hits[0].engine == "pinyin"


def test_l2_mixed_hanzi_and_pinyin_variant_scores_nine_tenths():
    result = L2VariantEngine([Word("坏词", "其他", "违规")]).scan("这里有坏ci")

    assert result.score == 0.9
    assert any(hit.engine == "pinyin" for hit in result.hits)


def test_l2_does_not_match_short_word_from_unrelated_hanzi_pinyin():
    result = L2VariantEngine([Word("禁区", "涉政", "警告")]).scan("扫描二维码进群领取福利")

    assert result.score == 0.0
    assert result.hits == []


def test_l2_does_not_match_short_word_inside_anti_fraud_education_context():
    result = L2VariantEngine([Word("哈克", "涉政", "警告")]).scan("反诈课堂提醒：不要相信刷单返利")

    assert result.score == 0.0
    assert result.hits == []


def test_l2_pinyin_hit_position_points_to_original_variant_fragment():
    result = L2VariantEngine([Word("坏词", "其他", "违规")]).scan("前缀 huaici 后缀")
    hit = next(hit for hit in result.hits if hit.engine == "pinyin")

    assert hit.original_fragment == "huaici"
    assert hit.start == 3
    assert hit.end == 9


def test_l2_homophone_variant_scores_nine_tenths():
    result = L2VariantEngine([Word("坏词", "其他", "违规")], homophones={"壞": "坏"}).scan("这里有壞词")

    assert result.score == 0.9
    assert any(hit.engine == "homophone" and hit.matched_word == "坏词" for hit in result.hits)


def test_l2_glyph_variant_scores_nine_tenths():
    result = L2VariantEngine([Word("坏词", "其他", "违规")], glyph_confusables={"坯": "坏"}).scan("这里有坯词")

    assert result.score == 0.9
    assert any(hit.engine == "glyph" and hit.matched_word == "坏词" for hit in result.hits)


def test_l2_does_not_treat_common_hanzi_as_political_pinyin_variants():
    words = [
        Word("主席", "涉政", "警告"),
        Word("傻习", "涉政", "警告"),
        Word("罢课", "涉政", "违规"),
        Word("核蛋", "涉政", "违规"),
    ]

    result = L2VariantEngine(words).scan("主线分支出现构建失败，沙箱进程启动失败，把可以复现的日志贴出来。")

    assert result.score == 0.0
    assert result.hits == []


def test_l2_still_detects_ascii_pinyin_evasion():
    result = L2VariantEngine([Word("坏词", "其他", "违规")]).scan("这里有 huai ci")

    assert result.score == 0.9
    assert any(hit.engine == "pinyin" for hit in result.hits)


def test_l2_does_not_match_pinyin_inside_technical_identifiers():
    result = L2VariantEngine([Word("女儿", "其他", "警告")]).scan("Invoke-RestMethod | ConvertTo-Json")

    assert result.score == 0.0
    assert result.hits == []


def test_l2_scales_reasonably_with_many_words():
    words = [Word(f"坏词{i}", "其他", "违规") for i in range(2000)] + [Word("坏词", "其他", "违规")]
    engine = L2VariantEngine(words)

    started = perf_counter()
    result = engine.scan(("正常内容" * 120) + "huai ci")
    elapsed_ms = (perf_counter() - started) * 1000

    assert result.score == 0.9
    assert elapsed_ms < 1200
