from audit.main import _bootstrap_builtin_words
from audit.repository.db import Database
from audit.repository.word_repo import WordRepository


def test_bootstrap_replaces_stale_builtin_words(tmp_path):
    seed = tmp_path / "seed.csv"
    seed.write_text(
        "word,category,level\n"
        + "\n".join(f"真实词{i},其他,提示" for i in range(1000)),
        encoding="utf-8",
    )

    repo = WordRepository(Database(str(tmp_path / "audit.db")))
    repo.create_word("演示词", "其他", "违规", source="builtin")
    repo.create_word("保留自定义词", "其他", "警告", source="custom")

    _bootstrap_builtin_words(repo, str(seed))

    words = repo.list_words()
    builtin_words = {entry.word for entry in words if entry.source == "builtin"}
    custom_words = {entry.word for entry in words if entry.source == "custom"}

    assert "演示词" not in builtin_words
    assert "真实词0" in builtin_words
    assert len(builtin_words) == 1000
    assert custom_words == {"保留自定义词"}
