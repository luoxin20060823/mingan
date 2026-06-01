import pytest

from audit.pipeline.l3_semantic import L3SemanticEngine
from audit.settings import Settings


@pytest.mark.asyncio
async def test_l3_missing_api_key_returns_error_payload():
    result = await L3SemanticEngine(Settings(deepseek_api_key="")).classify("普通文本")
    assert result.score == 0.0
    assert result.error == "missing_api_key"
    assert result.explanation.startswith("L3 错误")
    assert "l3_error" in result.hits[0].flags
