from pathlib import Path

import pytest

from audit.main import create_app
from audit.repository.word_repo import WordRepository


def _write_seed(path: Path, rows: list[tuple[str, str, str]]) -> None:
    path.write_text(
        "word,category,level\n"
        + "\n".join(f"{word},{category},{level}" for word, category, level in rows)
        + "\n",
        encoding="utf-8",
    )


def test_startup_imports_builtin_words_from_seed_csv(tmp_path, monkeypatch):
    seed_path = tmp_path / "sensitive_words.csv"
    rows = [("测试词A", "其他", "违规"), ("测试词B", "辱骂", "警告")]
    rows.extend((f"测试词{i}", "其他", "提示") for i in range(998))
    _write_seed(seed_path, rows)
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "audit.db"))
    monkeypatch.setenv("SEED_PATH", str(seed_path))

    app = create_app()

    repo = WordRepository(app.state.db)
    words = repo.list_words()
    assert repo.count_words() == 1000
    assert {"测试词A", "测试词B"}.issubset({w.word for w in words})
    assert {w.source for w in words} == {"builtin"}


def test_startup_fails_when_seed_missing_for_empty_database(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "audit.db"))
    monkeypatch.setenv("SEED_PATH", str(tmp_path / "missing.csv"))

    with pytest.raises(RuntimeError, match="seed file not found"):
        create_app()


def test_startup_enriches_partial_builtin_seed_without_removing_custom_words(tmp_path, monkeypatch):
    db_path = tmp_path / "audit.db"
    seed_path = tmp_path / "sensitive_words.csv"
    rows = [("坏词", "其他", "违规")]
    rows.extend((f"补齐词{i}", "其他", "提示") for i in range(999))
    _write_seed(seed_path, rows)
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    monkeypatch.setenv("SEED_PATH", str(seed_path))

    from audit.repository.db import Database

    repo = WordRepository(Database(str(db_path)))
    repo.create_word("坏词", "其他", "违规", source="builtin")
    repo.create_word("自定义保留词", "其他", "违规", source="custom")

    app = create_app()

    words = WordRepository(app.state.db).list_words()
    builtin_count = sum(1 for word in words if word.source == "builtin")
    assert builtin_count == 1000
    assert any(word.word == "自定义保留词" and word.source == "custom" for word in words)


def test_default_seed_file_has_at_least_1000_builtin_rows():
    seed_path = Path("seeds/sensitive_words.csv")
    assert seed_path.exists()
    row_count = len(seed_path.read_text(encoding="utf-8").splitlines()) - 1
    assert row_count >= 1000
