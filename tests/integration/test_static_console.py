from pathlib import Path


def test_static_console_contains_management_tabs():
    html = Path("static/index.html").read_text(encoding="utf-8")
    for text in ("单条审核", "批量审核", "历史记录", "敏感词管理", "规则管理", "策略配置"):
        assert text in html


def test_static_console_contains_expected_workflow_controls():
    html = Path("static/index.html").read_text(encoding="utf-8")
    for text in (
        'type="file"',
        "historyFilters",
        "wordFilters",
        "ruleForm",
        "policyForm",
        "loadRules",
        "createRule",
        "deleteRule",
        "loadPolicy",
        "savePolicy",
        "/policy",
        "/rules",
        "selectedResult",
        "highlightText",
        "查看详情",
        "清除筛选",
        "setDefaultHistoryRange",
        "90 * 24 * 60 * 60 * 1000",
    ):
        assert text in html
