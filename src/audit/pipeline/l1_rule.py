from __future__ import annotations

import time
import re

import ahocorasick

from ..domain.enums import RiskLevel, ViolationCategory
from ..domain.models import HitDetail, LayerResult


LEVEL_ORDER = {
    RiskLevel.COMPLIANT: 0,
    RiskLevel.HINT: 1,
    RiskLevel.WARNING: 2,
    RiskLevel.VIOLATION: 3,
}
LEVEL_BASE = {RiskLevel.HINT: 0.20, RiskLevel.WARNING: 0.50, RiskLevel.VIOLATION: 0.85}
LEVEL_CAP = {RiskLevel.HINT: 0.50, RiskLevel.WARNING: 0.85, RiskLevel.VIOLATION: 1.00}


class L1RuleEngine:
    def __init__(self, words, regex_rules: list[dict] | None = None):
        self.words = list(words)
        self.automaton = self._build_automaton(self.words)
        self.regex_rules = [
            {
                "name": str(rule["name"]),
                "pattern": re.compile(str(rule["pattern"])),
                "category": ViolationCategory(rule["category"]),
                "level": RiskLevel(rule["level"]),
            }
            for rule in (regex_rules or [])
        ]

    def scan(self, text: str | None) -> LayerResult:
        start = time.perf_counter()
        if not text:
            return LayerResult(score=0.0, hits=[], elapsed_ms=self._elapsed(start))
        if len(text) > 10000:
            raise ValueError("text exceeds 10000 characters")

        hits: list[HitDetail] = []
        for end_idx, entry in self.automaton.iter(text):
            word = entry.word
            start_idx = end_idx - len(word) + 1
            hits.append(
                HitDetail(
                    layer="L1",
                    engine="ahocorasick",
                    matched_word=word,
                    original_fragment=text[start_idx : end_idx + 1],
                    start=start_idx,
                    end=end_idx + 1,
                    category=ViolationCategory(entry.category),
                    level=RiskLevel(entry.level),
                )
            )
        for rule in self.regex_rules:
            for match in rule["pattern"].finditer(text):
                hits.append(
                    HitDetail(
                        layer="L1",
                        engine=f"regex:{rule['name']}",
                        matched_word=rule["name"],
                        original_fragment=match.group(0),
                        start=match.start(),
                        end=match.end(),
                        category=rule["category"],
                        level=rule["level"],
                    )
                )
        return LayerResult(score=compute_layer_score(hits), hits=hits, elapsed_ms=self._elapsed(start))

    @staticmethod
    def _elapsed(start: float) -> int:
        return max(0, int((time.perf_counter() - start) * 1000))

    @staticmethod
    def _build_automaton(words):
        automaton = ahocorasick.Automaton()
        for entry in words:
            if entry.word:
                automaton.add_word(entry.word, entry)
        automaton.make_automaton()
        return automaton


def compute_layer_score(hits: list[HitDetail]) -> float:
    if not hits:
        return 0.0
    top_level = max((h.level for h in hits), key=lambda x: LEVEL_ORDER[x])
    if top_level == RiskLevel.COMPLIANT:
        return 0.0
    base = LEVEL_BASE[top_level]
    cap = LEVEL_CAP[top_level]
    count_bonus = min(0.05 * (len(hits) - 1), cap - base - 0.01)
    return round(base + max(0.0, count_bonus), 4)
