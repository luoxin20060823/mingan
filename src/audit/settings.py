from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    deepseek_timeout_seconds: int = 5
    sqlite_path: str = "./data/audit.db"
    seed_path: str = "./seeds/sensitive_words.csv"
    lexicon_dir: str = ""
    homophone_path: str = "./seeds/homophones.json"
    glyph_path: str = "./seeds/glyph_confusables.json"
    regex_rules_path: str = "./seeds/regex_rules.yaml"
    log_level: str = "INFO"
