from dataclasses import dataclass

import pytest

from audit.pipeline.orchestrator import AuditOrchestrator


@dataclass
class Word:
    word: str
    category: str
    level: str


@pytest.mark.asyncio
async def test_orchestrator_returns_complete_audit_result_without_api_key():
    orchestrator = AuditOrchestrator(words=[Word("坏词", "其他", "违规")])
    result = await orchestrator.audit("这里有坏词")
    assert result.risk_level.value == "违规"
    assert result.violation_category == "其他"
    assert result.l1_score >= 0.85
    assert result.processing_time.total_ms >= result.processing_time.l1_ms
    assert result.disposal_suggestion.platform_action.value == "delete"
