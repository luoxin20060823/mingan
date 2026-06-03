from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from ..domain.enums import RiskLevel, ViolationCategory
from ..repository.word_repo import WordRepository
from .schemas import PageResponse, WordCreateRequest, WordResponse

router = APIRouter()


@router.post("/words", response_model=WordResponse, status_code=201)
def create_word(payload: WordCreateRequest, request: Request):
    try:
        entry = WordRepository(request.app.state.db).create_word(
            payload.word.strip(), payload.category.value, payload.level.value
        )
        request.app.state.word_cache.invalidate()
        return WordResponse(**entry.__dict__)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/words", response_model=PageResponse)
def list_words(
    request: Request,
    category: str | None = None,
    level: str | None = None,
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
    words = WordRepository(request.app.state.db).list_words()
    if category:
        words = [w for w in words if w.category == category]
    if level:
        words = [w for w in words if w.level == level]
    if q and q.strip():
        keyword = q.strip().casefold()
        words = [w for w in words if keyword in w.word.casefold()]
    start = (page - 1) * page_size
    items = [WordResponse(**w.__dict__).model_dump() for w in words[start : start + page_size]]
    return PageResponse(total=len(words), page=page, page_size=page_size, items=items)


@router.delete("/words/{word_id}", status_code=204)
def delete_word(word_id: int, request: Request):
    repo = WordRepository(request.app.state.db)
    entry = repo.get_word(word_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="word not found")
    if entry.source == "builtin":
        raise HTTPException(status_code=400, detail="builtin words cannot be deleted")
    ok = repo.delete_word(word_id)
    if not ok:
        raise HTTPException(status_code=404, detail="word not found")
    request.app.state.word_cache.invalidate()
    return Response(status_code=204)
