from __future__ import annotations

from fastapi import APIRouter, Request

from ..repository.rule_repo import RegexRuleRepository
from ..repository.word_repo import WordRepository

router = APIRouter()


@router.get("/health")
def health(request: Request):
    with request.app.state.db.connect() as conn:
        conn.execute("SELECT 1").fetchone()
    word_count = len(WordRepository(request.app.state.db).list_words())
    enabled_rule_count = len(RegexRuleRepository(request.app.state.db).list_rules(enabled_only=True))
    semantic_mode = "llm" if request.app.state.settings.deepseek_api_key else "local_fallback"
    return {
        "status": "ok",
        "database": "ok",
        "word_count": word_count,
        "enabled_rule_count": enabled_rule_count,
        "semantic_mode": semantic_mode,
    }
