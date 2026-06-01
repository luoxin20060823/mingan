from __future__ import annotations

import time

from pydantic import BaseModel

from ..domain.models import DisposalSuggestion, HitDetail, ProcessingTime
from .disposal import build_disposal
from .l1_rule import L1RuleEngine
from .l2_variant import L2VariantEngine
from .l3_semantic import L3SemanticEngine
from .l4_fusion import fuse


class AuditResult(BaseModel):
    risk_level: object
    violation_category: str
    confidence_score: float
    l1_score: float
    l2_score: float
    l3_score: float
    hit_details: list[HitDetail]
    llm_explanation: str
    disposal_suggestion: DisposalSuggestion
    processing_time: ProcessingTime


class AuditOrchestrator:
    def __init__(
        self,
        words,
        l3: L3SemanticEngine | None = None,
        regex_rules: list[dict] | None = None,
        homophones: dict[str, str] | None = None,
        glyph_confusables: dict[str, str] | None = None,
    ):
        self.words = list(words)
        self.l1 = L1RuleEngine(self.words, regex_rules=regex_rules)
        self.l2 = L2VariantEngine(self.words, homophones=homophones, glyph_confusables=glyph_confusables)
        self.l3 = l3 or L3SemanticEngine()

    async def audit(self, text: str) -> AuditResult:
        start = time.perf_counter()
        l1 = self.l1.scan(text)
        l2 = self.l2.scan(text)
        l3 = await self.l3.classify(text)
        decision = fuse(l1, l2, l3)
        hits = [*l1.hits, *l2.hits, *l3.hits]
        disposal = build_disposal(decision, hits)
        total_ms = max(0, int((time.perf_counter() - start) * 1000))
        processing = ProcessingTime(
            l1_ms=l1.elapsed_ms,
            l2_ms=l2.elapsed_ms,
            l3_ms=l3.elapsed_ms,
            total_ms=max(total_ms, l1.elapsed_ms, l2.elapsed_ms, l3.elapsed_ms),
        )
        return AuditResult(
            risk_level=decision.risk_level,
            violation_category=decision.category,
            confidence_score=decision.confidence_score,
            l1_score=decision.l1_score,
            l2_score=decision.l2_score,
            l3_score=decision.l3_score,
            hit_details=hits,
            llm_explanation=l3.explanation,
            disposal_suggestion=disposal,
            processing_time=processing,
        )
