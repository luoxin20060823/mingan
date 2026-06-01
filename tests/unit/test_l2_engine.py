from dataclasses import dataclass

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


def test_l2_homophone_variant_scores_nine_tenths():
    result = L2VariantEngine([Word("坏词", "其他", "违规")], homophones={"壞": "坏"}).scan("这里有壞词")

    assert result.score == 0.9
    assert any(hit.engine == "homophone" and hit.matched_word == "坏词" for hit in result.hits)


def test_l2_glyph_variant_scores_nine_tenths():
    result = L2VariantEngine([Word("坏词", "其他", "违规")], glyph_confusables={"坯": "坏"}).scan("这里有坯词")

    assert result.score == 0.9
    assert any(hit.engine == "glyph" and hit.matched_word == "坏词" for hit in result.hits)
