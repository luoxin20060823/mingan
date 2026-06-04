"""Evaluate an intentionally easy, demo-friendly subset of public datasets.

This benchmark is meant for product demos and smoke checks. It uses clear,
high-signal categories from ChineseHarm-Bench and should not be presented as a
full real-world moderation benchmark.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit.main import create_app
from scripts.evaluate_real_world_samples import EvalCase, evaluate_cases, write_report


EASY_CHINESEHARM_CATEGORIES = {
    "不违规.json": {
        "expected_max_risk": "提示",
        "expected_harmful": False,
    },
    "黑产广告.json": {
        "expected_min_risk": "警告",
        "acceptable_categories": ("违法广告", "诈骗", "引流"),
        "expected_harmful": True,
    },
}


def load_easy_chineseharm(root: Path, per_category: int) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for filename, expectation in EASY_CHINESEHARM_CATEGORIES.items():
        path = root / filename
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        count = 0
        for item in data:
            text = str(item.get("文本", "")).strip()
            if not text:
                continue
            count += 1
            cases.append(
                EvalCase(
                    case_id=f"easy_chineseharm_{path.stem}_{count}",
                    source=f"EasyDemo/ChineseHarm-Bench/{path.stem}",
                    text=text,
                    expected_min_risk=expectation.get("expected_min_risk"),
                    expected_max_risk=expectation.get("expected_max_risk"),
                    acceptable_categories=tuple(expectation.get("acceptable_categories", ())),
                    expected_harmful=bool(expectation.get("expected_harmful", True)),
                )
            )
            if count >= per_category:
                break
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--datasets-dir", default=".tmp-real-datasets")
    parser.add_argument("--output-dir", default=".tmp-real-eval/easy-demo")
    parser.add_argument("--per-category", type=int, default=20)
    parser.add_argument("--fail-on-errors", action="store_true")
    args = parser.parse_args()

    harm_root = Path(args.datasets_dir) / "ChineseHarm-bench"
    cases = load_easy_chineseharm(harm_root, args.per_category)
    if not cases:
        raise SystemExit("no easy demo cases found")

    client = TestClient(create_app())
    results = evaluate_cases(client, cases)
    write_report(results, Path(args.output_dir))

    failed = sum(1 for item in results if item["errors"])
    print(f"evaluated {len(results)} easy demo cases; passed {len(results) - failed}; failed {failed}")
    print(f"report: {Path(args.output_dir) / 'real_world_eval_report.md'}")
    return 1 if args.fail_on_errors and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
