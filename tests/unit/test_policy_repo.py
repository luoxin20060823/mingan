from audit.domain.enums import ViolationCategory
from audit.policy.settings import PolicySettings, RiskThresholds
from audit.repository.db import Database
from audit.repository.policy_repo import PolicySettingsRepository


def test_policy_repo_ensures_default_policy(tmp_path):
    repo = PolicySettingsRepository(Database(str(tmp_path / "audit.db")))

    policy = repo.ensure_default_policy()

    assert policy.risk_thresholds.violation == 0.85
    assert ViolationCategory.MINOR_SAFETY in policy.high_risk_categories
    assert repo.get_policy() == policy


def test_policy_repo_saves_custom_policy(tmp_path):
    repo = PolicySettingsRepository(Database(str(tmp_path / "audit.db")))
    policy = PolicySettings(
        risk_thresholds=RiskThresholds(hint=0.1, warning=0.4, violation=0.7),
        high_risk_categories=[ViolationCategory.TERROR],
    )

    repo.save_policy(policy)

    loaded = repo.get_policy()
    assert loaded.risk_thresholds.violation == 0.7
    assert loaded.high_risk_categories == [ViolationCategory.TERROR]
