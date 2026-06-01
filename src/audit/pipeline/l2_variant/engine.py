from __future__ import annotations

import re
import time

from pypinyin import lazy_pinyin

from ...domain.enums import RiskLevel, ViolationCategory
from ...domain.models import HitDetail, LayerResult


class L2VariantEngine:
    def __init__(self, words, homophones: dict[str, str] | None = None, glyph_confusables: dict[str, str] | None = None):
        self.words = list(words)
        self.homophones = homophones or {}
        self.glyph_confusables = glyph_confusables or {}

    def scan(self, text: str | None) -> LayerResult:
        start = time.perf_counter()
        if not text or not text.strip():
            return LayerResult(score=0.0, hits=[], elapsed_ms=self._elapsed(start))

        flags: list[str] = []
        working = text
        if len(working) > 2000:
            working = working[:2000]
            flags.append("truncated")

        hits: list[HitDetail] = []
        hits.extend(self._strip_and_scan(working, r"\s+", "whitespace", flags))
        hits.extend(self._strip_and_scan(working, r"[^\u4e00-\u9fffA-Za-z0-9_]", "symbol", flags))
        hits.extend(self._pinyin_scan(working, flags))
        hits.extend(self._mapped_scan(working, self.homophones, "homophone", flags))
        hits.extend(self._mapped_scan(working, self.glyph_confusables, "glyph", flags))
        return LayerResult(score=compute_l2_score(hits), hits=hits, elapsed_ms=self._elapsed(start))

    def _strip_and_scan(self, text: str, pattern: str, engine: str, flags: list[str]) -> list[HitDetail]:
        chars: list[str] = []
        index_map: list[int] = []
        for i, ch in enumerate(text):
            if re.match(pattern, ch):
                continue
            chars.append(ch)
            index_map.append(i)
        normalized = "".join(chars)
        hits: list[HitDetail] = []
        for entry in self.words:
            search_from = 0
            while entry.word:
                idx = normalized.find(entry.word, search_from)
                if idx < 0:
                    break
                if normalized != text:
                    hits.append(
                        self._hit(engine, entry, text, index_map[idx], index_map[idx + len(entry.word) - 1] + 1, flags)
                    )
                search_from = idx + len(entry.word)
        return hits

    def _pinyin_scan(self, text: str, flags: list[str]) -> list[HitDetail]:
        compact = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]", "", text).lower()
        mixed_compact = "".join(lazy_pinyin(compact)).lower()
        hits: list[HitDetail] = []
        for entry in self.words:
            full = "".join(lazy_pinyin(entry.word)).lower()
            initials = "".join(p[0] for p in lazy_pinyin(entry.word)).lower()
            has_plain_word = entry.word in compact
            if full and (full in compact or (not has_plain_word and full in mixed_compact) or initials in compact):
                hits.append(self._hit("pinyin", entry, text, 0, min(len(text), max(1, len(entry.word))), flags))
        return hits

    def _mapped_scan(self, text: str, mapping: dict[str, str], engine: str, flags: list[str]) -> list[HitDetail]:
        if not mapping:
            return []
        normalized = "".join(mapping.get(ch, ch) for ch in text)
        if normalized == text:
            return []

        hits: list[HitDetail] = []
        for entry in self.words:
            search_from = 0
            while entry.word:
                idx = normalized.find(entry.word, search_from)
                if idx < 0:
                    break
                hits.append(self._hit(engine, entry, text, idx, idx + len(entry.word), flags))
                search_from = idx + len(entry.word)
        return hits

    @staticmethod
    def _hit(engine: str, entry, text: str, start: int, end: int, flags: list[str]) -> HitDetail:
        return HitDetail(
            layer="L2",
            engine=engine,
            matched_word=entry.word,
            original_fragment=text[start:end],
            start=start,
            end=end,
            category=ViolationCategory(entry.category),
            level=RiskLevel(entry.level),
            flags=list(flags),
        )

    @staticmethod
    def _elapsed(start: float) -> int:
        return max(0, int((time.perf_counter() - start) * 1000))


def compute_l2_score(hits: list[HitDetail]) -> float:
    if not hits:
        return 0.0
    engines = {h.engine for h in hits}
    if engines & {"pinyin", "homophone", "glyph"}:
        return 0.9
    return 0.6
