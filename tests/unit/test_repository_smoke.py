from audit.repository.db import Database
from audit.repository.word_repo import WordRepository


def test_word_repo_create_list_delete(tmp_path):
    db = Database(str(tmp_path / "audit.db"))
    repo = WordRepository(db)

    created = repo.create_word("测试词", "其他", "警告")
    assert created.word == "测试词"
    assert repo.count_words() == 1
    assert repo.delete_word(created.id) is True
    assert repo.count_words() == 0
