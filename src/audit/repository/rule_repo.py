from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .db import Database


@dataclass(frozen=True)
class RegexRuleEntry:
    id: int
    name: str
    pattern: str
    category: str
    level: str
    source: str
    enabled: bool
    created_at: str


class RegexRuleRepository:
    def __init__(self, db: Database):
        self.db = db

    def list_rules(self, enabled_only: bool = False) -> list[RegexRuleEntry]:
        sql = "SELECT id, name, pattern, category, level, source, enabled, created_at FROM regex_rules"
        args: list[object] = []
        if enabled_only:
            sql += " WHERE enabled = ?"
            args.append(1)
        sql += " ORDER BY id DESC"
        with self.db.connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [self._entry(dict(row)) for row in rows]

    def get_rule(self, rule_id: int) -> RegexRuleEntry | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT id, name, pattern, category, level, source, enabled, created_at FROM regex_rules WHERE id = ?",
                (rule_id,),
            ).fetchone()
        return self._entry(dict(row)) if row else None

    def create_rule(
        self, name: str, pattern: str, category: str, level: str, source: str = "custom", enabled: bool = True
    ) -> RegexRuleEntry:
        created_at = datetime.now(timezone.utc).isoformat()
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO regex_rules(name, pattern, category, level, source, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (name, pattern, category, level, source, 1 if enabled else 0, created_at),
            )
            conn.commit()
            row = conn.execute(
                "SELECT id, name, pattern, category, level, source, enabled, created_at FROM regex_rules WHERE id = ?",
                (cur.lastrowid,),
            ).fetchone()
        return self._entry(dict(row))

    def delete_rule(self, rule_id: int) -> bool:
        with self.db.connect() as conn:
            cur = conn.execute("DELETE FROM regex_rules WHERE id = ?", (rule_id,))
            conn.commit()
            return cur.rowcount > 0

    def replace_rules_by_source(self, source: str, rows: list[dict]) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        with self.db.connect() as conn:
            conn.execute("BEGIN")
            conn.execute("DELETE FROM regex_rules WHERE source = ?", (source,))
            conn.executemany(
                """
                INSERT INTO regex_rules(name, pattern, category, level, source, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row["name"],
                        row["pattern"],
                        row["category"],
                        row["level"],
                        source,
                        1 if row.get("enabled", True) else 0,
                        created_at,
                    )
                    for row in rows
                ],
            )
            conn.commit()
        return len(rows)

    @staticmethod
    def _entry(row: dict) -> RegexRuleEntry:
        return RegexRuleEntry(
            id=row["id"],
            name=row["name"],
            pattern=row["pattern"],
            category=row["category"],
            level=row["level"],
            source=row["source"],
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
        )
