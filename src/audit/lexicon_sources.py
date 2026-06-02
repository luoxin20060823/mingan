from __future__ import annotations

import csv
from pathlib import Path

from .domain.enums import RiskLevel, ViolationCategory
from .policy.category_rules import normalize_category


VOCABULARY_FILE_MAP: dict[str, tuple[str, str]] = {
    "广告类型.txt": (ViolationCategory.ILLEGAL_AD.value, RiskLevel.VIOLATION.value),
    "非法网址.txt": (ViolationCategory.ILLEGAL_AD.value, RiskLevel.VIOLATION.value),
    "色情类型.txt": (ViolationCategory.PORN.value, RiskLevel.VIOLATION.value),
    "色情词库.txt": (ViolationCategory.PORN.value, RiskLevel.VIOLATION.value),
    "暴恐词库.txt": (ViolationCategory.TERROR.value, RiskLevel.VIOLATION.value),
    "涉枪涉爆.txt": (ViolationCategory.TERROR.value, RiskLevel.VIOLATION.value),
    "政治类型.txt": (ViolationCategory.POLITICS.value, RiskLevel.WARNING.value),
    "反动词库.txt": (ViolationCategory.POLITICS.value, RiskLevel.VIOLATION.value),
    "贪腐词库.txt": (ViolationCategory.POLITICS.value, RiskLevel.WARNING.value),
    "GFW补充词库.txt": (ViolationCategory.POLITICS.value, RiskLevel.WARNING.value),
    "COVID-19词库.txt": (ViolationCategory.OTHER.value, RiskLevel.HINT.value),
    "民生词库.txt": (ViolationCategory.OTHER.value, RiskLevel.HINT.value),
    "其他词库.txt": (ViolationCategory.OTHER.value, RiskLevel.WARNING.value),
    "补充词库.txt": (ViolationCategory.OTHER.value, RiskLevel.WARNING.value),
    "网易前端过滤敏感词库.txt": (ViolationCategory.OTHER.value, RiskLevel.WARNING.value),
}


def load_builtin_seed(seed_path: str, lexicon_dir: str = "") -> list[tuple[str, str, str]]:
    if lexicon_dir and Path(lexicon_dir).exists():
        return _load_public_vocabulary_dir(Path(lexicon_dir))
    return _load_seed_csv(Path(seed_path))


def _load_seed_csv(seed_path: Path) -> list[tuple[str, str, str]]:
    if not seed_path.exists():
        raise RuntimeError(f"seed file not found: {seed_path}")

    with seed_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"word", "category", "level"}
        if reader.fieldnames:
            reader.fieldnames = [name.lstrip("\ufeff") for name in reader.fieldnames]
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise RuntimeError("seed file must contain word, category, level columns")
        rows = [
            _validated_row(row["word"].strip(), row["category"].strip(), row["level"].strip())
            for row in reader
            if row["word"].strip()
        ]
    return _dedupe_and_validate(rows)


def _load_public_vocabulary_dir(source_dir: Path) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for filename, (category, level) in VOCABULARY_FILE_MAP.items():
        path = source_dir / filename
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
            word = raw.strip().strip("\ufeff")
            if not word or word.startswith("#"):
                continue
            rows.append(_validated_row(word, category, level))
    return _dedupe_and_validate(rows)


def _validated_row(word: str, category: str, level: str) -> tuple[str, str, str]:
    category = normalize_category(word, category)
    try:
        ViolationCategory(category)
        RiskLevel(level)
    except ValueError as exc:
        raise RuntimeError(f"invalid seed row: {word}") from exc
    return word, category, level


def _dedupe_and_validate(rows: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    seen: set[str] = set()
    deduped: list[tuple[str, str, str]] = []
    for word, category, level in rows:
        key = word.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append((word, category, level))
    if len(deduped) < 1000:
        raise RuntimeError("seed file must contain at least 1000 rows")
    return deduped
