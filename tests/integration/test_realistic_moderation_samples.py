from fastapi.testclient import TestClient

from audit.main import create_app


TECHNICAL_LOG_SAMPLE = """刚才并行读取技能说明时沙箱启动有点抖，我换成单步检查。接下来我会先完成运行时接口验证；如果接口暴露出问题，就按失败点补测试和修复。

已运行 git status --short --branch
本地命令连续出现 spawn setup refresh，这更像是工具沙箱启动问题，不是项目代码问题。我会按规则对关键检查申请一次非沙箱执行；拿到状态后继续验证系统。

已拒绝 1 项请求已运行 1 条命令
审批服务本身拒绝了提权，原因是它的自动审核模型未配置价格；这和项目权限无关。我不会绕过这个审批去做同一件事，口但还可以先用普通沙箱命令继续尝试更低风险的运行时检查；如果工具恢复，就继续推进。

已运行 Invoke-RestMethod -Uri 'http://127.0.0.1:8010/health' -TimeoutSec 30 | ConvertTo-Json -Compress
健康检查也被同一个本地命令启动错误挡住了，说明当前不是某条命令写错，而是工具运行环境临时不可用。"""


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "audit.db"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    return TestClient(create_app())


def _audit(client: TestClient, text: str) -> dict:
    response = client.post("/audit/text", json={"text": text})
    assert response.status_code == 200
    return response.json()


def test_technical_operation_log_is_not_blocked_by_low_quality_lexicon_hits(tmp_path, monkeypatch):
    result = _audit(_client(tmp_path, monkeypatch), TECHNICAL_LOG_SAMPLE)

    assert result["risk_level"] in {"合规", "提示"}
    assert result["violation_category"] in {"", "其他"}
    assert result["disposal_suggestion"]["platform_action"] in {"pass", "hint"}
    assert result["l3_score"] == 0.0


def test_benign_engineering_notes_are_not_flagged_as_political_variants(tmp_path, monkeypatch):
    text = "主线分支出现构建失败，命令执行器日志显示沙箱进程启动失败，稍后继续跑接口验证。"

    result = _audit(_client(tmp_path, monkeypatch), text)

    assert result["risk_level"] in {"合规", "提示"}
    assert result["violation_category"] in {"", "其他"}
    assert result["disposal_suggestion"]["platform_action"] in {"pass", "hint"}


def test_realistic_fraud_sample_is_still_blocked(tmp_path, monkeypatch):
    text = "先交保证金，完成刷单任务后返利提现，客服会发银行卡收款信息。"

    result = _audit(_client(tmp_path, monkeypatch), text)

    assert result["risk_level"] == "违规"
    assert result["violation_category"] == "诈骗"
    assert result["disposal_suggestion"]["platform_action"] in {"block", "delete"}


def test_realistic_traffic_diversion_sample_is_still_reviewed_or_blocked(tmp_path, monkeypatch):
    text = "资料不方便在这里发，扫码进群后加我VX领取完整教程和交易链接。"

    result = _audit(_client(tmp_path, monkeypatch), text)

    assert result["risk_level"] in {"警告", "违规"}
    assert result["violation_category"] == "引流"
    assert result["disposal_suggestion"]["platform_action"] in {"fold", "manual_review", "block", "delete"}
