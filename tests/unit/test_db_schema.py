from audit.repository.db import Database


def test_audit_records_schema_has_history_filter_indexes(tmp_path):
    db = Database(str(tmp_path / "audit.db"))

    with db.connect() as conn:
        indexes = {row["name"] for row in conn.execute("PRAGMA index_list('audit_records')").fetchall()}

    assert "idx_audit_records_created_at" in indexes
    assert "idx_audit_records_risk_level" in indexes
    assert "idx_audit_records_category" in indexes
    assert "idx_audit_records_created_risk_category" in indexes


def test_sensitive_words_schema_has_unique_word_source_constraint(tmp_path):
    db = Database(str(tmp_path / "audit.db"))

    with db.connect() as conn:
        indexes = conn.execute("PRAGMA index_list('sensitive_words')").fetchall()
        unique_indexes = [row["name"] for row in indexes if row["unique"]]
        unique_columns = [
            [column["name"] for column in conn.execute(f"PRAGMA index_info('{index_name}')").fetchall()]
            for index_name in unique_indexes
        ]

    assert ["word", "source"] in unique_columns
