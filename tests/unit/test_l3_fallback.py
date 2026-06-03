import pytest

from audit.domain.enums import RiskLevel, ViolationCategory
from audit.pipeline.l3_semantic import L3SemanticEngine
from audit.settings import Settings


@pytest.mark.asyncio
async def test_l3_missing_api_key_returns_error_payload():
    result = await L3SemanticEngine(Settings(deepseek_api_key="")).classify("普通文本")
    assert result.score == 0.0
    assert result.error == "missing_api_key"
    assert result.explanation.startswith("L3 错误")
    assert "l3_error" in result.hits[0].flags


class DummyResponse:
    def __init__(self, content: str):
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self.content}}]}


class DummyClient:
    def __init__(self, content: str):
        self.content = content
        self.payload = None

    async def post(self, url, headers=None, json=None):
        self.payload = json
        return DummyResponse(self.content)


@pytest.mark.asyncio
async def test_l3_prompt_constrains_schema_categories_and_false_positive_contexts():
    client = DummyClient('{"risk_level":"合规","category":"","reason":"正常表达","score":0.01}')

    await L3SemanticEngine(Settings(deepseek_api_key="key"), client=client).classify("招聘客服，月薪面议")

    messages = client.payload["messages"]
    combined_prompt = "\n".join(message["content"] for message in messages)
    assert "risk_level" in combined_prompt
    assert "score" in combined_prompt
    assert "诈骗" in combined_prompt
    assert "引流" in combined_prompt
    assert "未成年人风险" in combined_prompt
    assert "正常招聘" in combined_prompt
    assert "只输出 JSON" in combined_prompt


@pytest.mark.asyncio
async def test_l3_valid_semantic_violation_response_creates_specific_hit():
    client = DummyClient('{"risk_level":"违规","category":"诈骗","reason":"诱导私下转账","score":0.91}')

    result = await L3SemanticEngine(Settings(deepseek_api_key="key"), client=client).classify(
        "平台外联系，先交保证金再返利"
    )

    assert result.error is None
    assert result.risk_level == RiskLevel.VIOLATION
    assert result.category == ViolationCategory.FRAUD
    assert result.score == 0.91
    assert result.hits[0].category == ViolationCategory.FRAUD
    assert result.hits[0].level == RiskLevel.VIOLATION


@pytest.mark.asyncio
async def test_l3_compliant_response_has_no_hits_and_empty_category():
    client = DummyClient('{"risk_level":"合规","category":"其他","reason":"新闻背景介绍","score":0.02}')

    result = await L3SemanticEngine(Settings(deepseek_api_key="key"), client=client).classify(
        "本文介绍某地公开新闻事件的背景"
    )

    assert result.error is None
    assert result.risk_level == RiskLevel.COMPLIANT
    assert result.category is None
    assert result.score == 0.02
    assert result.hits == []


@pytest.mark.asyncio
async def test_l3_invalid_category_is_rejected_as_error_result():
    client = DummyClient('{"risk_level":"违规","category":"未知类别","reason":"不可识别","score":0.8}')

    result = await L3SemanticEngine(Settings(deepseek_api_key="key"), client=client).classify("风险文本")

    assert result.error
    assert "invalid category" in result.error
    assert "l3_error" in result.hits[0].flags


@pytest.mark.asyncio
async def test_l3_malformed_json_is_rejected_as_error_result():
    client = DummyClient("不是 JSON")

    result = await L3SemanticEngine(Settings(deepseek_api_key="key"), client=client).classify("风险文本")

    assert result.error
    assert "JSON" in result.error or "Expecting value" in result.error
    assert "l3_error" in result.hits[0].flags
