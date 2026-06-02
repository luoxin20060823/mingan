from __future__ import annotations

import csv
from pathlib import Path

from audit.lexicon_sources import load_builtin_seed


SOURCE_DIR = Path(".tmp-sensitive-lexicon/Vocabulary")
OUTPUT_PATH = Path("seeds/sensitive_words.csv")


def main() -> None:
    rows = load_builtin_seed(str(OUTPUT_PATH), str(SOURCE_DIR))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["word", "category", "level"])
        writer.writerows(rows)
    print(f"wrote {len(rows)} words to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
