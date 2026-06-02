import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .api.audit_routes import router as audit_router
from .api.errors import install_error_handlers
from .api.history_routes import router as history_router
from .api.rule_routes import router as rule_router
from .api.word_routes import router as word_router
from .cache.word_cache import WordLibraryCache
from .lexicon_sources import load_builtin_seed
from .repository.db import Database
from .repository.rule_repo import RegexRuleRepository
from .repository.word_repo import WordRepository
from .settings import Settings


def _bootstrap_builtin_words(repo: WordRepository, seed_path: str, lexicon_dir: str = "") -> None:
    rows = load_builtin_seed(seed_path, lexicon_dir)
    current = [(entry.word, entry.category, entry.level) for entry in repo.list_words() if entry.source == "builtin"]
    if set(current) == set(rows) and len(current) == len(rows):
        return
    repo.replace_words_by_source("builtin", rows)


def _load_character_mapping(path: str) -> dict[str, str]:
    mapping_path = Path(path)
    if not mapping_path.exists():
        return {}
    data = json.loads(mapping_path.read_text(encoding="utf-8-sig"))
    normalized: dict[str, str] = {}
    for canonical, variants in data.items():
        if isinstance(variants, str):
            normalized[canonical] = variants
            continue
        for variant in variants:
            normalized[str(variant)] = str(canonical)
    return normalized


def _load_regex_rules(path: str) -> list[dict]:
    rules_path = Path(path)
    if not rules_path.exists():
        return []
    rules: list[dict] = []
    current: dict[str, str] = {}
    for raw_line in rules_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("- "):
            if current:
                rules.append(current)
            current = {}
            line = line[2:].strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key == "pattern":
            value = value.replace("\\\\", "\\")
        current[key] = value
    if current:
        rules.append(current)
    return rules


def _bootstrap_builtin_regex_rules(repo: RegexRuleRepository, rules_path: str) -> None:
    rows = _load_regex_rules(rules_path)
    current = [
        {
            "name": entry.name,
            "pattern": entry.pattern,
            "category": entry.category,
            "level": entry.level,
            "enabled": entry.enabled,
        }
        for entry in repo.list_rules()
        if entry.source == "builtin"
    ]
    normalized_rows = [
        {
            "name": row["name"],
            "pattern": row["pattern"],
            "category": row["category"],
            "level": row["level"],
            "enabled": row.get("enabled", True),
        }
        for row in rows
    ]
    if current == normalized_rows:
        return
    repo.replace_rules_by_source("builtin", normalized_rows)


def create_app() -> FastAPI:
    app = FastAPI(title="Content Audit Platform")
    settings = Settings()
    app.state.settings = settings
    app.state.db = Database(settings.sqlite_path)
    _bootstrap_builtin_words(WordRepository(app.state.db), settings.seed_path, settings.lexicon_dir)
    _bootstrap_builtin_regex_rules(RegexRuleRepository(app.state.db), settings.regex_rules_path)
    app.state.word_cache = WordLibraryCache(WordRepository(app.state.db))
    app.state.homophones = _load_character_mapping(settings.homophone_path)
    app.state.glyph_confusables = _load_character_mapping(settings.glyph_path)

    app.include_router(audit_router)
    app.include_router(word_router)
    app.include_router(rule_router)
    app.include_router(history_router)
    install_error_handlers(app)

    static_dir = Path("static")
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    def index():
        return RedirectResponse("/static/index.html")

    return app


app = create_app()
