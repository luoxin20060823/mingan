# Real-World Evaluation Report

This report evaluates the current moderation system on sampled public benchmark data. It is a repeatable engineering evaluation, not a claim of production-grade model quality across all content domains.

## Data Sources

The evaluation uses three public, research-oriented datasets:

- **COLDataset**: Chinese offensive language dataset from THU COAI. Repository: <https://github.com/thu-coai/COLDataset>
- **ChineseHarm-Bench**: Chinese harmful content benchmark covering non-violation, vulgar/sexual content, gambling, fraud, flame/abuse, and black-market ads. Dataset page: <https://huggingface.co/datasets/zjunlp/ChineseHarm-bench>
- **SWSR**: Sina Weibo Sexism Review dataset for Chinese online sexism detection. Repository: <https://github.com/aggiejiang/SWSR>

Downloaded files are kept under `.tmp-real-datasets/`, which is ignored by Git.

## Label Mapping

The system is a general content safety auditor, while the datasets use specialized labels. The evaluation maps labels as follows:

- COLDataset offensive -> harmful; acceptable categories: `辱骂` or `其他`
- COLDataset non-offensive -> safe; expected max risk: `提示`
- ChineseHarm-Bench non-violation -> safe
- ChineseHarm-Bench low/vulgar/sexual -> harmful; acceptable categories: `低俗` or `色情`
- ChineseHarm-Bench gambling/fraud/black-market ads -> harmful; acceptable categories: `违法广告`, `诈骗`, or `引流`
- ChineseHarm-Bench flame/abuse -> harmful; acceptable categories: `辱骂` or `其他`
- SWSR sexist -> harmful; acceptable categories: `辱骂`, `其他`, `低俗`, or `色情`
- SWSR non-sexist -> safe

For binary harmful detection, `警告` and `违规` are counted as harmful predictions; `合规` and `提示` are counted as safe or low-risk predictions.

## Main Error Causes

The latest failure review found these dominant causes:

- **Contextual false positives**: safe social, legal, gender, race, or marketing discussion can contain sensitive tokens and be over-classified by keyword or variant layers.
- **L3/local fallback precedence bug**: when the external semantic model returned weak `提示/其他` results for short gambling or black-market ads, the stronger local semantic fallback was not allowed to override it.
- **Short-form ads and slang**: phrases such as `金花牛牛玩吗`, `dy评论`, `小红书发文`, and `抄小说吗` need grouped intent signals, not isolated keywords.
- **Implicit abuse and sexism**: coded insults, sarcasm, regional/gender stereotypes, and SWSR microaggressions require a dedicated semantic classifier or stronger LLM rubric.
- **Category drift**: mixed sexual/abusive/political samples are often detected but assigned to neighboring categories, such as `涉政`, `色情`, or `违法广告`.
- **Batch evaluation performance**: the old evaluator called `/audit/text` one case at a time, rebuilding the orchestrator and variant engine repeatedly. This made large benchmark runs impractically slow.

## Optimizations Performed

This round made four targeted changes:

- **Contextual warning reduction**: when L3 is compliant, non-specific L1/L2 warning hits in contextual categories are capped to low risk, while custom words and explicit high-risk categories remain enforceable.
- **Local semantic fallback precedence**: known local high-confidence warning/violation patterns now override LLM `合规` or weaker generic `提示/其他` responses.
- **Short ad/slang recall**: local semantic rules now cover additional gambling and black-market task-ad patterns, including `金花/牛牛/棋牌/回血`, `dy/ks评论`, `小红书/小红薯发文`, and `抄/炒/超小说`.
- **Evaluation/runtime performance**: L2 pinyin variants are precomputed at engine initialization, and the real-world evaluator now uses `/audit/batch` to reuse one orchestrator per batch.

The fixes intentionally avoid broad keyword-only escalation for ambiguous coded insults, because that would raise false positives on normal discussion.

## Baseline: 140-Case Evaluation

Command:

```powershell
python scripts/evaluate_real_world_samples.py --cold-per-label 20 --harm-per-category 10 --swsr-per-label 20 --output-dir .tmp-real-eval/baseline-140
```

Metrics:

| Metric | Value |
| --- | ---: |
| Total | 140 |
| Passed | 88 |
| Failed | 52 |
| Accuracy | 0.6643 |
| Precision | 0.7416 |
| Recall | 0.7333 |
| F1 | 0.7374 |
| Specificity | 0.5400 |
| TP | 66 |
| TN | 27 |
| FP | 23 |
| FN | 24 |

Category mapping accuracy: `60 / 90 = 0.6667`.

## Online Comparable Run Before Final Local Fix: 280 Cases

This earlier run used the configured semantic layer and is kept as historical context.

```powershell
python scripts/evaluate_real_world_samples.py --cold-per-label 40 --harm-per-category 20 --swsr-per-label 40 --output-dir .tmp-real-eval/expanded-280-final
```

| Metric | Value |
| --- | ---: |
| Total | 280 |
| Passed | 196 |
| Failed | 84 |
| Accuracy | 0.6714 |
| Precision | 0.8729 |
| Recall | 0.5722 |
| F1 | 0.6913 |
| Specificity | 0.8500 |
| TP | 103 |
| TN | 85 |
| FP | 15 |
| FN | 77 |

Category mapping accuracy: `115 / 180 = 0.6389`.

## Latest Comparable Local Run: 280 Cases

This run explicitly disables the external LLM key for reproducibility and exercises the rule, variant, local semantic, fusion, and disposal layers through the API batch endpoint.

```powershell
$env:DEEPSEEK_API_KEY=''
python scripts/evaluate_real_world_samples.py --cold-per-label 40 --harm-per-category 20 --swsr-per-label 40 --output-dir .tmp-real-eval/expanded-280-local-after-fix
```

| Metric | Value |
| --- | ---: |
| Total | 280 |
| Passed | 174 |
| Failed | 106 |
| Accuracy | 0.5214 |
| Precision | 0.8594 |
| Recall | 0.3056 |
| F1 | 0.4508 |
| Specificity | 0.9100 |
| TP | 55 |
| TN | 91 |
| FP | 9 |
| FN | 125 |

Category mapping accuracy: `86 / 180 = 0.4778`.

Notable by-source results:

| Source | Pass Rate | Accuracy | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| COLDataset | 58/80 | 0.5250 | 1.0000 | 0.0500 | 0.0952 |
| ChineseHarm-Bench / 不违规 | 19/20 | 0.9500 | 0.0000 | 0.0000 | 0.0000 |
| ChineseHarm-Bench / 低俗色情 | 7/20 | 0.5000 | 1.0000 | 0.5000 | 0.6667 |
| ChineseHarm-Bench / 博彩 | 12/20 | 0.6000 | 1.0000 | 0.6000 | 0.7500 |
| ChineseHarm-Bench / 欺诈 | 6/20 | 0.3500 | 1.0000 | 0.3500 | 0.5185 |
| ChineseHarm-Bench / 谩骂引战 | 5/20 | 0.0500 | 1.0000 | 0.0500 | 0.0952 |
| ChineseHarm-Bench / 黑产广告 | 18/20 | 0.9000 | 1.0000 | 0.9000 | 0.9474 |
| SWSR / SexComment | 49/80 | 0.4625 | 0.3846 | 0.1250 | 0.1887 |

## Expanded Local Run: 420 Cases

Command:

```powershell
$env:DEEPSEEK_API_KEY=''
python scripts/evaluate_real_world_samples.py --cold-per-label 60 --harm-per-category 30 --swsr-per-label 60 --output-dir .tmp-real-eval/expanded-420-local-after-fix
```

| Metric | Value |
| --- | ---: |
| Total | 420 |
| Passed | 246 |
| Failed | 174 |
| Accuracy | 0.4952 |
| Precision | 0.8295 |
| Recall | 0.2704 |
| F1 | 0.4078 |
| Specificity | 0.9000 |
| TP | 73 |
| TN | 135 |
| FP | 15 |
| FN | 197 |

Category mapping accuracy: `115 / 270 = 0.4259`.

Notable by-source results:

| Source | Pass Rate | Accuracy | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| COLDataset | 85/120 | 0.5500 | 0.8750 | 0.1167 | 0.2059 |
| ChineseHarm-Bench / 不违规 | 28/30 | 0.9333 | 0.0000 | 0.0000 | 0.0000 |
| ChineseHarm-Bench / 低俗色情 | 8/30 | 0.3667 | 1.0000 | 0.3667 | 0.5366 |
| ChineseHarm-Bench / 博彩 | 17/30 | 0.5667 | 1.0000 | 0.5667 | 0.7234 |
| ChineseHarm-Bench / 欺诈 | 6/30 | 0.3000 | 1.0000 | 0.3000 | 0.4615 |
| ChineseHarm-Bench / 谩骂引战 | 5/30 | 0.0333 | 1.0000 | 0.0333 | 0.0645 |
| ChineseHarm-Bench / 黑产广告 | 19/30 | 0.6333 | 1.0000 | 0.6333 | 0.7755 |
| SWSR / SexComment | 78/120 | 0.4750 | 0.4286 | 0.1500 | 0.2222 |

## Interpretation

The current local-mode system is conservative:

- False positives are lower after contextual warning protection. Local 420-case specificity is `0.9000`.
- Black-market ad recall improved on the 280-case comparable run, reaching `18/20` pass rate for ChineseHarm-Bench black-market ads.
- Overall recall remains weak in local-only mode, especially for implicit abuse, sexism, fraud soft ads, and vulgar/sexual slang.
- The online semantic layer remains important for generalization. The local fallback should be viewed as a high-precision safety net, not a complete classifier.

The most urgent remaining product gap is a dedicated semantic classifier or calibrated LLM rubric for abuse, sexism, and disguised fraud. The current rule/local-fallback approach is useful for high-confidence patterns but cannot reliably understand coded or context-heavy harms.

## Reproducibility

Download datasets:

```powershell
git clone --depth 1 https://github.com/thu-coai/COLDataset.git .tmp-real-datasets/COLDataset
git clone --depth 1 https://huggingface.co/datasets/zjunlp/ChineseHarm-bench .tmp-real-datasets/ChineseHarm-bench
git clone --depth 1 https://github.com/aggiejiang/SWSR.git .tmp-real-datasets/SWSR
```

Run the latest expanded local evaluation:

```powershell
$env:DEEPSEEK_API_KEY=''
python scripts/evaluate_real_world_samples.py --cold-per-label 60 --harm-per-category 30 --swsr-per-label 60 --output-dir .tmp-real-eval/expanded-420-local-after-fix
```

Read generated files:

```text
.tmp-real-eval/expanded-420-local-after-fix/real_world_eval_report.md
.tmp-real-eval/expanded-420-local-after-fix/real_world_eval_results.json
```
