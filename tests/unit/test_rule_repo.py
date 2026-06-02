from audit.repository.db import Database
from audit.repository.rule_repo import RegexRuleRepository


def test_rule_repo_create_list_delete(tmp_path):
    repo = RegexRuleRepository(Database(str(tmp_path / "audit.db")))

    created = repo.create_rule("wechat", r"加微信\d+", "引流", "警告")

    assert created.id > 0
    assert created.enabled is True
    assert repo.list_rules(enabled_only=True)[0].name == "wechat"
    assert repo.delete_rule(created.id) is True
    assert repo.list_rules() == []


def test_rule_repo_replace_builtin_rules_preserves_custom(tmp_path):
    repo = RegexRuleRepository(Database(str(tmp_path / "audit.db")))
    repo.create_rule("custom", "x+", "其他", "提示", source="custom")

    count = repo.replace_rules_by_source(
        "builtin",
        [{"name": "phone", "pattern": r"1\d{10}", "category": "违法广告", "level": "警告", "enabled": True}],
    )

    rules = repo.list_rules()
    assert count == 1
    assert {rule.source for rule in rules} == {"builtin", "custom"}
