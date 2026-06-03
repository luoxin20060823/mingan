from pathlib import Path


def test_env_example_documents_all_runtime_settings():
    env_example = Path(".env.example").read_text(encoding="utf-8")

    for key in (
        "DEEPSEEK_API_KEY",
        "SQLITE_PATH",
        "SEED_PATH",
        "LEXICON_DIR",
        "HOMOPHONE_PATH",
        "GLYPH_PATH",
        "REGEX_RULES_PATH",
    ):
        assert f"{key}=" in env_example


def test_technical_overview_lists_all_console_tabs():
    overview = Path("docs/TECHNICAL_OVERVIEW.md").read_text(encoding="utf-8")

    for label in ("单条审核", "批量审核", "历史记录", "敏感词管理", "规则管理", "策略配置"):
        assert f"- {label}" in overview
