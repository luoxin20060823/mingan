"""Evaluate the moderation API on downloaded public real-world datasets.

Expected local inputs:
- .tmp-real-datasets/COLDataset/COLDataset/test.csv
- .tmp-real-datasets/ChineseHarm-bench/*.json
- .tmp-real-datasets/SWSR/SWSR/SexComment.csv

The script writes reports under .tmp-real-eval/ and does not require network
access once datasets are downloaded.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from audit.main import create_app


RISK_ORDER = {"合规": 0, "提示": 1, "警告": 2, "违规": 3}


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    source: str
    text: str
    expected_min_risk: str | None = None
    expected_max_risk: str | None = None
    expected_category: str | None = None
    acceptable_categories: tuple[str, ...] = ()
    expected_harmful: bool = False


def load_coldataset(path: Path, per_label: int) -> list[EvalCase]:
    cases: list[EvalCase] = []
    counts: Counter[str] = Counter()
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            label = str(row.get("label", "")).strip()
            text = str(row.get("TEXT", "")).strip()
            if not text or label not in {"0", "1"}:
                continue
            if counts[label] >= per_label:
                continue
            counts[label] += 1
            if label == "1":
                cases.append(
                    EvalCase(
                        case_id=f"cold_offensive_{counts[label]}",
                        source="COLDataset",
                        text=text,
                        expected_min_risk="提示",
                        acceptable_categories=("辱骂", "其他"),
                        expected_harmful=True,
                    )
                )
            else:
                cases.append(
                    EvalCase(
                        case_id=f"cold_normal_{counts[label]}",
                        source="COLDataset",
                        text=text,
                        expected_max_risk="提示",
                        expected_harmful=False,
                    )
                )
            if counts["0"] >= per_label and counts["1"] >= per_label:
                break
    return cases


def load_chineseharm(root: Path, per_category: int) -> list[EvalCase]:
    mapping = {
        "不违规.json": {"expected_max_risk": "提示", "expected_harmful": False},
        "低俗色情.json": {"expected_min_risk": "提示", "expected_category": "低俗", "expected_harmful": True},
        "博彩.json": {
            "expected_min_risk": "警告",
            "acceptable_categories": ("违法广告", "诈骗", "引流"),
            "expected_harmful": True,
        },
        "欺诈.json": {
            "expected_min_risk": "警告",
            "acceptable_categories": ("诈骗", "引流", "违法广告"),
            "expected_harmful": True,
        },
        "谩骂引战.json": {
            "expected_min_risk": "提示",
            "acceptable_categories": ("辱骂", "其他"),
            "expected_harmful": True,
        },
        "黑产广告.json": {
            "expected_min_risk": "警告",
            "acceptable_categories": ("违法广告", "诈骗", "引流"),
            "expected_harmful": True,
        },
    }
    cases: list[EvalCase] = []
    for filename, expectation in mapping.items():
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
                    case_id=f"chineseharm_{path.stem}_{count}",
                    source=f"ChineseHarm-bench/{path.stem}",
                    text=text,
                    expected_min_risk=expectation.get("expected_min_risk"),
                    expected_max_risk=expectation.get("expected_max_risk"),
                    expected_category=expectation.get("expected_category"),
                    acceptable_categories=tuple(expectation.get("acceptable_categories", ())),
                    expected_harmful=bool(expectation.get("expected_harmful", True)),
                )
            )
            if count >= per_category:
                break
    return cases


def load_swsr(path: Path, per_label: int) -> list[EvalCase]:
    cases: list[EvalCase] = []
    counts: Counter[str] = Counter()
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            label = str(row.get("label", "")).strip()
            text = str(row.get("comment_text", "")).strip()
            if not text or label not in {"0", "1"}:
                continue
            if counts[label] >= per_label:
                continue
            counts[label] += 1
            if label == "1":
                cases.append(
                    EvalCase(
                        case_id=f"swsr_sexist_{counts[label]}",
                        source="SWSR/SexComment",
                        text=text,
                        expected_min_risk="提示",
                        acceptable_categories=("辱骂", "其他", "低俗", "色情"),
                        expected_harmful=True,
                    )
                )
            else:
                cases.append(
                    EvalCase(
                        case_id=f"swsr_nonsexist_{counts[label]}",
                        source="SWSR/SexComment",
                        text=text,
                        expected_max_risk="提示",
                        expected_harmful=False,
                    )
                )
            if counts["0"] >= per_label and counts["1"] >= per_label:
                break
    return cases


def evaluate_case(client: TestClient, case: EvalCase) -> dict[str, Any]:
    response = client.post("/audit/text", json={"text": case.text})
    response.raise_for_status()
    body = response.json()
    errors: list[str] = []

    risk = body["risk_level"]
    category = body["violation_category"]
    predicted_harmful = RISK_ORDER[risk] >= RISK_ORDER["警告"]
    if case.expected_min_risk and RISK_ORDER[risk] < RISK_ORDER[case.expected_min_risk]:
        errors.append(f"risk below {case.expected_min_risk}")
    if case.expected_max_risk and RISK_ORDER[risk] > RISK_ORDER[case.expected_max_risk]:
        errors.append(f"risk above {case.expected_max_risk}")
    acceptable_categories = set(case.acceptable_categories)
    if case.expected_category:
        acceptable_categories.add(case.expected_category)
    if case.expected_category == "低俗":
        acceptable_categories.add("色情")
    if acceptable_categories and category not in acceptable_categories:
        expected = "/".join(sorted(acceptable_categories))
        errors.append(f"category expected {expected}, got {category or 'empty'}")

    return {
        "id": case.case_id,
        "source": case.source,
        "text": case.text,
        "expected_min_risk": case.expected_min_risk,
        "expected_max_risk": case.expected_max_risk,
        "expected_category": case.expected_category,
        "acceptable_categories": list(case.acceptable_categories),
        "expected_harmful": case.expected_harmful,
        "predicted_harmful": predicted_harmful,
        "risk_level": risk,
        "violation_category": category,
        "action": body["disposal_suggestion"]["platform_action"],
        "l1_score": body["l1_score"],
        "l2_score": body["l2_score"],
        "l3_score": body["l3_score"],
        "hit_count": len(body["hit_details"]),
        "errors": errors,
    }


def _binary_metrics(results: list[dict[str, Any]]) -> dict[str, float | int]:
    tp = sum(1 for item in results if item["expected_harmful"] and item["predicted_harmful"])
    tn = sum(1 for item in results if not item["expected_harmful"] and not item["predicted_harmful"])
    fp = sum(1 for item in results if not item["expected_harmful"] and item["predicted_harmful"])
    fn = sum(1 for item in results if item["expected_harmful"] and not item["predicted_harmful"])
    total = len(results)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    return {
        "total": total,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy": (tp + tn) / total if total else 0.0,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "specificity": specificity,
    }


def _category_accuracy(results: list[dict[str, Any]]) -> dict[str, float | int]:
    category_cases = [
        item
        for item in results
        if item["expected_harmful"] and (item["expected_category"] or item["acceptable_categories"])
    ]
    correct = 0
    for item in category_cases:
        acceptable = set(item["acceptable_categories"])
        if item["expected_category"]:
            acceptable.add(item["expected_category"])
        if item["expected_category"] == "低俗":
            acceptable.add("色情")
        if item["violation_category"] in acceptable:
            correct += 1
    return {
        "total": len(category_cases),
        "correct": correct,
        "accuracy": correct / len(category_cases) if category_cases else 0.0,
    }


def _fmt(value: float | int) -> str:
    return f"{value:.4f}" if isinstance(value, float) else str(value)


def write_report(results: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "real_world_eval_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    total = len(results)
    failed = [item for item in results if item["errors"]]
    overall_metrics = _binary_metrics(results)
    category_metrics = _category_accuracy(results)
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in results:
        by_source[item["source"]].append(item)

    lines = [
        "# Real-World Moderation Evaluation",
        "",
        f"- Total cases: {total}",
        f"- Passed: {total - len(failed)}",
        f"- Failed: {len(failed)}",
        "",
        "## Binary Harmful Detection Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Accuracy | {_fmt(overall_metrics['accuracy'])} |",
        f"| Precision | {_fmt(overall_metrics['precision'])} |",
        f"| Recall | {_fmt(overall_metrics['recall'])} |",
        f"| F1 | {_fmt(overall_metrics['f1'])} |",
        f"| Specificity | {_fmt(overall_metrics['specificity'])} |",
        f"| TP | {overall_metrics['tp']} |",
        f"| TN | {overall_metrics['tn']} |",
        f"| FP | {overall_metrics['fp']} |",
        f"| FN | {overall_metrics['fn']} |",
        "",
        "## Category Mapping Accuracy",
        "",
        f"- Category accuracy: {_fmt(category_metrics['accuracy'])} "
        f"({category_metrics['correct']}/{category_metrics['total']})",
        "",
        "## By Source",
    ]
    for source, items in sorted(by_source.items()):
        source_failed = sum(1 for item in items if item["errors"])
        metrics = _binary_metrics(items)
        lines.append(
            f"- {source}: {len(items) - source_failed}/{len(items)} passed; "
            f"accuracy={_fmt(metrics['accuracy'])}, precision={_fmt(metrics['precision'])}, "
            f"recall={_fmt(metrics['recall'])}, f1={_fmt(metrics['f1'])}"
        )
    lines.extend(["", "## Failures"])
    if not failed:
        lines.append("- None")
    for item in failed[:80]:
        text = item["text"].replace("\n", " ")[:160]
        lines.append(
            f"- `{item['id']}` [{item['source']}]: {', '.join(item['errors'])}; "
            f"got {item['risk_level']}/{item['violation_category'] or 'empty'}/{item['action']}; text={text}"
        )
    (output_dir / "real_world_eval_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--datasets-dir", default=".tmp-real-datasets")
    parser.add_argument("--output-dir", default=".tmp-real-eval")
    parser.add_argument("--cold-per-label", type=int, default=20)
    parser.add_argument("--harm-per-category", type=int, default=10)
    parser.add_argument("--swsr-per-label", type=int, default=20)
    parser.add_argument("--fail-on-errors", action="store_true", help="return a non-zero exit code when cases fail")
    args = parser.parse_args()

    datasets_dir = Path(args.datasets_dir)
    cases = []
    cold_path = datasets_dir / "COLDataset" / "COLDataset" / "test.csv"
    harm_root = datasets_dir / "ChineseHarm-bench"
    swsr_path = datasets_dir / "SWSR" / "SWSR" / "SexComment.csv"
    if cold_path.exists():
        cases.extend(load_coldataset(cold_path, args.cold_per_label))
    if harm_root.exists():
        cases.extend(load_chineseharm(harm_root, args.harm_per_category))
    if swsr_path.exists():
        cases.extend(load_swsr(swsr_path, args.swsr_per_label))
    if not cases:
        raise SystemExit("no dataset cases found")

    client = TestClient(create_app())
    results = [evaluate_case(client, case) for case in cases]
    write_report(results, Path(args.output_dir))

    failed = sum(1 for item in results if item["errors"])
    print(f"evaluated {len(results)} cases; passed {len(results) - failed}; failed {failed}")
    print(f"report: {Path(args.output_dir) / 'real_world_eval_report.md'}")
    return 1 if args.fail_on_errors and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
