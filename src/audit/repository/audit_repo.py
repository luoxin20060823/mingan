from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from .db import Database


class AuditRepository:
    def __init__(self, db: Database):
        self.db = db

    def insert_record(self, **record) -> int:
        return self.insert_records([record])[0]

    def insert_records(self, records: list[dict]) -> list[int]:
        if not records:
            return []
        ids: list[int] = []
        with self.db.connect() as conn:
            try:
                conn.execute("BEGIN")
                for record in records:
                    ids.append(self._insert_record(conn, record))
                conn.commit()
            except sqlite3.Error:
                conn.rollback()
                raise
        return ids

    @staticmethod
    def _insert_record(conn, record: dict) -> int:
        payload = dict(record)
        payload.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        cur = conn.execute(
            """
            INSERT INTO audit_records(
                text, risk_level, violation_category, confidence_score,
                l1_score, l2_score, l3_score, hit_details_json,
                llm_explanation, disposal_suggestion_json, processing_time_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["text"],
                payload["risk_level"],
                payload["violation_category"],
                payload["confidence_score"],
                payload["l1_score"],
                payload["l2_score"],
                payload["l3_score"],
                payload["hit_details_json"],
                payload["llm_explanation"],
                payload["disposal_suggestion_json"],
                payload["processing_time_json"],
                payload["created_at"],
            ),
        )
        return int(cur.lastrowid)
