# Real-World Evaluation Report

This report evaluates the current moderation system on sampled public benchmark data. It is intended as a repeatable engineering evaluation, not a claim of production-grade model quality across all content domains.

## Data Sources

The evaluation uses three public, research-oriented datasets:

- **COLDataset**: Chinese offensive language dataset from THU COAI, used for offensive vs. non-offensive comment detection. Repository: <https://github.com/thu-coai/COLDataset>
- **ChineseHarm-Bench**: Chinese harmful content detection benchmark covering non-violation, vulgar/sexual content, gambling, fraud, flame/abuse, and black-market ads. Dataset page: <https://huggingface.co/datasets/zjunlp/ChineseHarm-bench>
- **SWSR**: Sina Weibo Sexism Review dataset for Chinese online sexism detection. Repository: <https://github.com/aggiejiang/SWSR>

Downloaded dataset files are kept under `.tmp-real-datasets/`, which is ignored by Git.

## Sampling

Command used:

```powershell
python scripts/evaluate_real_world_samples.py --cold-per-label 20 --harm-per-category 10 --swsr-per-label 20
```

Sample sizes:

- COLDataset: 40 cases, 20 offensive and 20 non-offensive
- ChineseHarm-Bench: 60 cases, 10 from each selected category
- SWSR SexComment: 40 cases, 20 sexist and 20 non-sexist
- Total: 140 cases

## Label Mapping

The system is a general content safety auditor, while the datasets use specialized labels. The evaluation maps labels as follows:

- COLDataset offensive -> harmful, acceptable categories: `辱骂` or `其他`
- COLDataset non-offensive -> safe, expected max risk: `提示`
- ChineseHarm-Bench non-violation -> safe
- ChineseHarm-Bench low/vulgar/sexual -> harmful, acceptable categories: `低俗` or `色情`
- ChineseHarm-Bench gambling/fraud/black-market ads -> harmful, acceptable categories: `违法广告`, `诈骗`, or `引流`
- ChineseHarm-Bench flame/abuse -> harmful, acceptable categories: `辱骂` or `其他`
- SWSR sexist -> harmful, acceptable categories: `辱骂`, `其他`, `低俗`, or `色情`
- SWSR non-sexist -> safe

For binary harmful detection, `警告` and `违规` are counted as harmful predictions; `合规` and `提示` are counted as safe or low-risk predictions.

## Overall Metrics

| Metric | Value |
| --- | ---: |
| Accuracy | 0.6643 |
| Precision | 0.7416 |
| Recall | 0.7333 |
| F1 | 0.7374 |
| Specificity | 0.5400 |
| TP | 66 |
| TN | 27 |
| FP | 23 |
| FN | 24 |

Category mapping accuracy on harmful samples with expected categories:

```text
60 / 90 = 0.6667
```

## By Dataset

| Source | Case Pass Rate | Accuracy | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| COLDataset | 26/40 | 0.6750 | 0.7059 | 0.6000 | 0.6486 |
| ChineseHarm-Bench / 不违规 | 9/10 | 0.9000 | 0.0000 | 0.0000 | 0.0000 |
| ChineseHarm-Bench / 低俗色情 | 6/10 | 0.9000 | 1.0000 | 0.9000 | 0.9474 |
| ChineseHarm-Bench / 博彩 | 9/10 | 0.9000 | 1.0000 | 0.9000 | 0.9474 |
| ChineseHarm-Bench / 欺诈 | 9/10 | 0.9000 | 1.0000 | 0.9000 | 0.9474 |
| ChineseHarm-Bench / 谩骂引战 | 5/10 | 0.5000 | 1.0000 | 0.5000 | 0.6667 |
| ChineseHarm-Bench / 黑产广告 | 6/10 | 0.9000 | 1.0000 | 0.9000 | 0.9474 |
| SWSR / SexComment | 16/40 | 0.4000 | 0.4333 | 0.6500 | 0.5200 |

Notes:

- Precision/recall are meaningful when a source contains both harmful and safe labels. For single-class subsets, some values are structurally zero because there are no positive or negative examples for that subset.
- SWSR is a specialized sexism benchmark. Many non-sexist examples discuss sexual assault, gender politics, or social conflict, so a general safety auditor may intentionally mark them for review even when the SWSR label is non-sexist.

## Error Analysis

Main false-positive patterns:

- **Sensitive social/legal discussion**: SWSR non-sexist examples discussing sexual assault, gender rights, or protests are often flagged because the content is sensitive even if not sexist.
- **Historical/legal/political context**: COLDataset comments about legal cases, race, or national identity can be mapped to `涉政` or `其他` warning.
- **Benign but high-risk keywords**: examples containing sexual assault terms, violence, or discrimination terms are sometimes elevated even when the context is discussion or criticism.

Main false-negative patterns:

- **Implicit flame/abuse**: poetic, coded, or context-dependent insults are difficult to detect without conversation context.
- **Subtle sexism**: SWSR includes microaggressions and stereotype-based sexism that require domain-specific understanding.
- **Very short black-market slang**: some short task-ad phrases remain ambiguous without surrounding recruitment/payment context.

## Interpretation

The system performs reasonably on explicit harmful advertising, fraud, gambling, vulgar/sexual, and black-market samples from ChineseHarm-Bench, where most subset accuracies are around `0.90`.

The weaker areas are:

- generalized offensive-language understanding,
- implicit/indirect abuse,
- sexism-specific nuance,
- false-positive reduction for discussion of sensitive topics.

These results are consistent with a hybrid rules plus lightweight semantic fallback system. Stronger performance on SWSR and implicit abuse would likely require a dedicated abuse/sexism classifier or more robust LLM semantic scoring with calibrated thresholds.

## Reproducibility

To reproduce:

1. Download datasets:

```powershell
git clone --depth 1 https://github.com/thu-coai/COLDataset.git .tmp-real-datasets/COLDataset
git clone --depth 1 https://huggingface.co/datasets/zjunlp/ChineseHarm-bench .tmp-real-datasets/ChineseHarm-bench
git clone --depth 1 https://github.com/aggiejiang/SWSR.git .tmp-real-datasets/SWSR
```

2. Run evaluation:

```powershell
python scripts/evaluate_real_world_samples.py --cold-per-label 20 --harm-per-category 10 --swsr-per-label 20
```

3. Read generated files:

```text
.tmp-real-eval/real_world_eval_report.md
.tmp-real-eval/real_world_eval_results.json
```

