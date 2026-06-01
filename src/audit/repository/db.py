from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA temp_store = MEMORY;

CREATE TABLE IF NOT EXISTS audit_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    violation_category TEXT NOT NULL DEFAULT '',
    confidence_score REAL NOT NULL,
    l1_score REAL NOT NULL,
    l2_score REAL NOT NULL,
    l3_score REAL NOT NULL,
    hit_details_json TEXT NOT NULL,
    llm_explanation TEXT NOT NULL DEFAULT '',
    disposal_suggestion_json TEXT NOT NULL,
    processing_time_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sensitive_words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL,
    category TEXT NOT NULL,
    level TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(word, source)
);

CREATE INDEX IF NOT EXISTS idx_audit_records_created_at
    ON audit_records(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_records_risk_level
    ON audit_records(risk_level);
CREATE INDEX IF NOT EXISTS idx_audit_records_category
    ON audit_records(violation_category);
CREATE INDEX IF NOT EXISTS idx_audit_records_created_risk_category
    ON audit_records(created_at, risk_level, violation_category);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        return conn
