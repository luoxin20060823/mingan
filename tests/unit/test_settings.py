from audit.settings import Settings


def test_settings_load_defaults():
    settings = Settings()
    assert settings.sqlite_path.endswith(".db")
