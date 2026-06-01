import csv
import json
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .api.audit_routes import router as audit_router
from .api.errors import install_error_handlers
from .api.history_routes import router as history_router
from .api.word_routes import router as word_router
from .cache.word_cache import WordLibraryCache
from .domain.enums import RiskLevel, ViolationCategory
from .repository.db import Database
from .repository.word_repo import WordRepository
from .settings import Settings


def _bootstrap_builtin_words(repo: WordRepository, seed_path: str) -> None:
    builtin_count = repo.count_words_by_source("builtin")
    if builtin_count >= 1000:
        return

    rows = _load_seed_rows(Path(seed_path))
    for word, category, level in rows:
        try:
            repo.create_word(word, category, level, source="builtin")
        except sqlite3.IntegrityError:
            continue


def _load_seed_rows(seed_path: Path) -> list[tuple[str, str, str]]:
    if not seed_path.exists():
        raise RuntimeError(f"seed file not found: {seed_path}")

    with seed_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"word", "category", "level"}
        if reader.fieldnames:
            reader.fieldnames = [name.lstrip("\ufeff") for name in reader.fieldnames]
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise RuntimeError("seed file must contain word, category, level columns")
        rows = []
        for row in reader:
            word = row["word"].strip()
            category = row["category"].strip()
            level = row["level"].strip()
            if not word:
                continue
            try:
                ViolationCategory(category)
                RiskLevel(level)
            except ValueError as exc:
                raise RuntimeError(f"invalid seed row: {word}") from exc
            rows.append((word, category, level))

    if len(rows) < 1000:
        raise RuntimeError("seed file must contain at least 1000 rows")
    return rows


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


def create_app() -> FastAPI:
    app = FastAPI(title="Content Audit Platform")
    settings = Settings()
    app.state.settings = settings
    app.state.db = Database(settings.sqlite_path)
    _bootstrap_builtin_words(WordRepository(app.state.db), settings.seed_path)
    app.state.word_cache = WordLibraryCache(WordRepository(app.state.db))
    app.state.homophones = _load_character_mapping(settings.homophone_path)
    app.state.glyph_confusables = _load_character_mapping(settings.glyph_path)
    app.state.regex_rules = _load_regex_rules(settings.regex_rules_path)

    app.include_router(audit_router)
    app.include_router(word_router)
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
