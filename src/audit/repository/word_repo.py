from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .db import Database


@dataclass(frozen=True)
class WordEntry:
    id: int
    word: str
    category: str
    level: str
    source: str
    created_at: str


class WordRepository:
    def __init__(self, db: Database):
        self.db = db

    def list_words(self) -> list[WordEntry]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT id, word, category, level, source, created_at FROM sensitive_words ORDER BY id DESC"
            ).fetchall()
        return [WordEntry(**dict(row)) for row in rows]

    def get_word(self, word_id: int) -> WordEntry | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT id, word, category, level, source, created_at FROM sensitive_words WHERE id = ?",
                (word_id,),
            ).fetchone()
        return WordEntry(**dict(row)) if row else None

    def create_word(self, word: str, category: str, level: str, source: str = "custom") -> WordEntry:
        created_at = datetime.now(timezone.utc).isoformat()
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO sensitive_words(word, category, level, source, created_at) VALUES (?, ?, ?, ?, ?)",
                (word, category, level, source, created_at),
            )
            conn.commit()
            row = conn.execute(
                "SELECT id, word, category, level, source, created_at FROM sensitive_words WHERE id = ?",
                (cur.lastrowid,),
            ).fetchone()
        return WordEntry(**dict(row))

    def delete_word(self, word_id: int) -> bool:
        with self.db.connect() as conn:
            cur = conn.execute("DELETE FROM sensitive_words WHERE id = ?", (word_id,))
            conn.commit()
            return cur.rowcount > 0

    def count_words(self) -> int:
        with self.db.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM sensitive_words").fetchone()
        return int(row["c"])

    def count_words_by_source(self, source: str) -> int:
        with self.db.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM sensitive_words WHERE source = ?", (source,)).fetchone()
        return int(row["c"])
