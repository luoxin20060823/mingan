from __future__ import annotations

from fastapi import APIRouter, Request

from ..policy.settings import PolicySettings
from ..repository.policy_repo import PolicySettingsRepository
from .schemas import PolicySettingsRequest, PolicySettingsResponse

router = APIRouter()


@router.get("/policy", response_model=PolicySettingsResponse)
def get_policy(request: Request):
    policy = PolicySettingsRepository(request.app.state.db).get_policy()
    return PolicySettingsResponse.model_validate(policy.model_dump())


@router.put("/policy", response_model=PolicySettingsResponse)
def update_policy(payload: PolicySettingsRequest, request: Request):
    policy = PolicySettings(
        risk_thresholds=payload.risk_thresholds,
        high_risk_categories=payload.high_risk_categories,
    )
    saved = PolicySettingsRepository(request.app.state.db).save_policy(policy)
    return PolicySettingsResponse.model_validate(saved.model_dump())
