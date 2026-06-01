from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from ..domain.enums import RiskLevel, ViolationCategory
from .schemas import PageResponse

router = APIRouter()


def _parse_time(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid {field}") from exc


@router.get("/history", response_model=PageResponse)
def history(
    request: Request,
    risk_level: str | None = None,
    category: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    if page < 1 or page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="invalid pagination")
    if risk_level is not None:
        try:
            RiskLevel(risk_level)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid risk_level") from exc
    if category is not None:
        try:
            ViolationCategory(category)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid category") from exc

    parsed_start = _parse_time(start_time, "start_time")
    parsed_end = _parse_time(end_time, "end_time")
    if parsed_start and parsed_end and parsed_start > parsed_end:
        raise HTTPException(status_code=400, detail="invalid time range")

    where = []
    args = []
    if risk_level:
        where.append("risk_level = ?")
        args.append(risk_level)
    if category:
        where.append("violation_category = ?")
        args.append(category)
    if parsed_start:
        where.append("created_at >= ?")
        args.append(parsed_start)
    if parsed_end:
        where.append("created_at <= ?")
        args.append(parsed_end)
    sql_where = (" WHERE " + " AND ".join(where)) if where else ""
    with request.app.state.db.connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS c FROM audit_records{sql_where}", args).fetchone()["c"]
        rows = conn.execute(
            f"SELECT * FROM audit_records{sql_where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            [*args, page_size, (page - 1) * page_size],
        ).fetchall()
    return PageResponse(total=total, page=page, page_size=page_size, items=[dict(r) for r in rows])
