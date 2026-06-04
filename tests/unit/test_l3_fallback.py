import pytest

from audit.domain.enums import RiskLevel, ViolationCategory
from audit.pipeline.l3_semantic import L3SemanticEngine
from audit.settings import Settings


@pytest.mark.asyncio
async def test_l3_missing_api_key_uses_local_semantic_fallback_for_plain_text():
    result = await L3SemanticEngine(Settings(deepseek_api_key="")).classify("普通文本")
    assert result.score == 0.0
    assert result.error is None
    assert result.risk_level == RiskLevel.COMPLIANT
    assert result.category is None
    assert result.hits == []
    assert "本地语义" in result.explanation


@pytest.mark.asyncio
async def test_l3_local_semantic_fallback_detects_fraud_context_without_api_key():
    result = await L3SemanticEngine(Settings(deepseek_api_key="")).classify("先交保证金，完成刷单后返利提现")

    assert result.error is None
    assert result.risk_level == RiskLevel.VIOLATION
    assert result.category == ViolationCategory.FRAUD
    assert result.score >= 0.85
    assert result.hits[0].engine == "local_semantic"
    assert "local_fallback" in result.hits[0].flags


@pytest.mark.asyncio
async def test_l3_local_semantic_fallback_detects_minor_safety_context_without_api_key():
    result = await L3SemanticEngine(Settings(deepseek_api_key="")).classify("诱导未成年人发送裸照")

    assert result.error is None
    assert result.risk_level == RiskLevel.VIOLATION
    assert result.category == ViolationCategory.MINOR_SAFETY
    assert result.hits[0].engine == "local_semantic"


@pytest.mark.asyncio
async def test_l3_local_semantic_fallback_detects_gambling_ad_context_without_api_key():
    result = await L3SemanticEngine(Settings(deepseek_api_key="")).classify(
        "累积500返388，每天包赢几百，100送100，新人有扶持，私信。"
    )

    assert result.error is None
    assert result.risk_level == RiskLevel.WARNING
    assert result.category == ViolationCategory.ILLEGAL_AD
    assert result.hits[0].engine == "local_semantic"


@pytest.mark.asyncio
async def test_l3_local_semantic_fallback_detects_black_market_task_ad_without_api_key():
    result = await L3SemanticEngine(Settings(deepseek_api_key="")).classify("宝宝，要了解一下抄小说赚r吗？")

    assert result.error is None
    assert result.risk_level == RiskLevel.WARNING
    assert result.category == ViolationCategory.ILLEGAL_AD
    assert result.hits[0].engine == "local_semantic"


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["小红书发图文感兴趣吗？", "抄小说要了解一下吗？"])
async def test_l3_local_semantic_fallback_detects_short_black_market_task_ads(text):
    result = await L3SemanticEngine(Settings(deepseek_api_key="")).classify(text)

    assert result.error is None
    assert result.risk_level == RiskLevel.WARNING
    assert result.category == ViolationCategory.ILLEGAL_AD
    assert result.hits[0].engine == "local_semantic"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "金花牛牛玩吗",
        "手机金花牛牛小游戏玩的来",
        "接dy发评论吗？",
        "ks评论长期稳定要做吗",
        "炒小说做吗？一周一结。",
        "抄小说有兴趣吗",
        "抄小说吗？",
        "宝子，小红书发文，内容我们提供。考虑一下呢？",
    ],
)
async def test_l3_local_semantic_fallback_detects_more_short_ads(text):
    result = await L3SemanticEngine(Settings(deepseek_api_key="")).classify(text)

    assert result.error is None
    assert result.risk_level == RiskLevel.WARNING
    assert result.category in {ViolationCategory.ILLEGAL_AD, ViolationCategory.TRAFFIC_DIVERSION}
    assert result.hits[0].engine == "local_semantic"


@pytest.mark.asyncio
async def test_l3_local_semantic_fallback_keeps_anti_fraud_education_compliant():
    result = await L3SemanticEngine(Settings(deepseek_api_key="")).classify(
        "反诈课堂提醒：不要相信刷单返利，也不要向陌生人提供验证码。"
    )

    assert result.error is None
    assert result.risk_level == RiskLevel.COMPLIANT
    assert result.category is None
    assert result.hits == []


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
async def test_l3_local_fallback_overrides_llm_compliant_for_known_black_market_ad():
    client = DummyClient('{"risk_level":"合规","category":"","reason":"正常交流","score":0.01}')

    result = await L3SemanticEngine(Settings(deepseek_api_key="key"), client=client).classify("小红书发图文感兴趣吗？")

    assert result.error is None
    assert result.risk_level == RiskLevel.WARNING
    assert result.category == ViolationCategory.ILLEGAL_AD
    assert result.hits[0].engine == "local_semantic"


@pytest.mark.asyncio
async def test_l3_local_fallback_overrides_llm_hint_for_known_black_market_ad():
    client = DummyClient('{"risk_level":"提示","category":"其他","reason":"轻微关注","score":0.25}')

    result = await L3SemanticEngine(Settings(deepseek_api_key="key"), client=client).classify("金花牛牛玩吗")

    assert result.error is None
    assert result.risk_level == RiskLevel.WARNING
    assert result.category == ViolationCategory.ILLEGAL_AD
    assert result.hits[0].engine == "local_semantic"


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
