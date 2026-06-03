from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from ..domain.enums import RiskLevel, ViolationCategory
from ..repository.rule_repo import RegexRuleRepository
from .schemas import PageResponse, RegexRuleCreateRequest, RegexRuleResponse

router = APIRouter()


@router.post("/rules", response_model=RegexRuleResponse, status_code=201)
def create_rule(payload: RegexRuleCreateRequest, request: Request):
    try:
        entry = RegexRuleRepository(request.app.state.db).create_rule(
            payload.name.strip(),
            payload.pattern,
            payload.category.value,
            payload.level.value,
            source="custom",
            enabled=payload.enabled,
        )
        return RegexRuleResponse(**entry.__dict__)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/rules", response_model=PageResponse)
def list_rules(
    request: Request,
    category: str | None = None,
    level: str | None = None,
    enabled: bool | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    if page < 1 or page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="invalid pagination")
    if category is not None:
        try:
            ViolationCategory(category)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid category") from exc
    if level is not None:
        try:
            RiskLevel(level)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid level") from exc

    rules = RegexRuleRepository(request.app.state.db).list_rules()
    if category:
        rules = [rule for rule in rules if rule.category == category]
    if level:
        rules = [rule for rule in rules if rule.level == level]
    if enabled is not None:
        rules = [rule for rule in rules if rule.enabled is enabled]
    if q and q.strip():
        keyword = q.strip().casefold()
        rules = [rule for rule in rules if keyword in rule.name.casefold() or keyword in rule.pattern.casefold()]
    start = (page - 1) * page_size
    items = [RegexRuleResponse(**rule.__dict__).model_dump() for rule in rules[start : start + page_size]]
    return PageResponse(total=len(rules), page=page, page_size=page_size, items=items)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, request: Request):
    repo = RegexRuleRepository(request.app.state.db)
    entry = repo.get_rule(rule_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="rule not found")
    if entry.source == "builtin":
        raise HTTPException(status_code=400, detail="builtin rules cannot be deleted")
    ok = repo.delete_rule(rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="rule not found")
    return Response(status_code=204)
