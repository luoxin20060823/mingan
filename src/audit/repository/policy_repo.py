from __future__ import annotations

import json
from datetime import datetime, timezone

from ..policy.settings import PolicySettings, RiskThresholds
from .db import Database


DEFAULT_POLICY_KEY = "moderation_policy"


class PolicySettingsRepository:
    def __init__(self, db: Database):
        self.db = db

    def get_policy(self) -> PolicySettings:
        with self.db.connect() as conn:
            row = conn.execute("SELECT value_json FROM policy_settings WHERE key = ?", (DEFAULT_POLICY_KEY,)).fetchone()
        if not row:
            return PolicySettings()
        return PolicySettings.model_validate(json.loads(row["value_json"]))

    def save_policy(self, policy: PolicySettings) -> PolicySettings:
        updated_at = datetime.now(timezone.utc).isoformat()
        payload = policy.model_dump_json()
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO policy_settings(key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at
                """,
                (DEFAULT_POLICY_KEY, payload, updated_at),
            )
            conn.commit()
        return policy

    def ensure_default_policy(self) -> PolicySettings:
        policy = self.get_policy()
        self.save_policy(policy)
        return policy
