from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, HTTPException, Request

from ..pipeline.orchestrator import AuditOrchestrator
from ..repository.audit_repo import AuditRepository
from ..repository.policy_repo import PolicySettingsRepository
from ..repository.rule_repo import RegexRuleRepository
from ..repository.word_repo import WordRepository
from .schemas import AuditBatchRequest, AuditBatchResponse, AuditTextRequest, AuditTextResponse

router = APIRouter()


def _response(result) -> AuditTextResponse:
    return AuditTextResponse(
        risk_level=result.risk_level,
        violation_category=result.violation_category,
        confidence_score=result.confidence_score,
        l1_score=result.l1_score,
        l2_score=result.l2_score,
        l3_score=result.l3_score,
        hit_details=result.hit_details,
        llm_explanation=result.llm_explanation,
        disposal_suggestion=result.disposal_suggestion,
        processing_time=result.processing_time,
    )


def _record_payload(text: str, response: AuditTextResponse) -> dict:
    return {
        "text": text,
        "risk_level": response.risk_level.value,
        "violation_category": response.violation_category,
        "confidence_score": response.confidence_score,
        "l1_score": response.l1_score,
        "l2_score": response.l2_score,
        "l3_score": response.l3_score,
        "hit_details_json": json.dumps([h.model_dump(mode="json") for h in response.hit_details], ensure_ascii=False),
        "llm_explanation": response.llm_explanation,
        "disposal_suggestion_json": response.disposal_suggestion.model_dump_json(),
        "processing_time_json": response.processing_time.model_dump_json(),
    }


async def _audit_and_store(request: Request, text: str) -> AuditTextResponse:
    words = WordRepository(request.app.state.db).list_words()
    regex_rules = [entry.__dict__ for entry in RegexRuleRepository(request.app.state.db).list_rules(enabled_only=True)]
    policy = PolicySettingsRepository(request.app.state.db).get_policy()
    result = await AuditOrchestrator(
        words=words,
        regex_rules=regex_rules,
        homophones=request.app.state.homophones,
        glyph_confusables=request.app.state.glyph_confusables,
        policy=policy,
    ).audit(text)
    response = _response(result)
    try:
        AuditRepository(request.app.state.db).insert_record(**_record_payload(text, response))
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail="persistence failed") from exc
    return response


@router.post("/audit/text", response_model=AuditTextResponse)
async def audit_text(payload: AuditTextRequest, request: Request):
    return await _audit_and_store(request, payload.text)


@router.post("/audit/batch", response_model=AuditBatchResponse)
async def audit_batch(payload: AuditBatchRequest, request: Request):
    words = WordRepository(request.app.state.db).list_words()
    regex_rules = [entry.__dict__ for entry in RegexRuleRepository(request.app.state.db).list_rules(enabled_only=True)]
    policy = PolicySettingsRepository(request.app.state.db).get_policy()
    orchestrator = AuditOrchestrator(
        words=words,
        regex_rules=regex_rules,
        homophones=request.app.state.homophones,
        glyph_confusables=request.app.state.glyph_confusables,
        policy=policy,
    )
    results: list[AuditTextResponse] = []
    records: list[dict] = []
    for text in payload.texts:
        response = _response(await orchestrator.audit(text))
        results.append(response)
        records.append(_record_payload(text, response))
    try:
        AuditRepository(request.app.state.db).insert_records(records)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail="persistence failed") from exc
    return AuditBatchResponse(results=results)
