# 真实样本评测报告

本文档记录当前内容安全审核系统在公开真实样本数据集上的测试结果。它的定位是可复现的工程评测报告，用于发现问题、跟踪优化效果，并不等同于生产级模型能力声明。

## 数据来源

本次评测使用了 3 个公开研究数据集：

- **COLDataset**：由 THU COAI 发布的中文攻击性语言数据集，用于测试攻击性评论与正常评论识别能力。仓库地址：<https://github.com/thu-coai/COLDataset>
- **ChineseHarm-Bench**：中文有害内容检测基准，覆盖不违规、低俗色情、博彩、欺诈、谩骂引战、黑产广告等类型。数据集地址：<https://huggingface.co/datasets/zjunlp/ChineseHarm-bench>
- **SWSR**：新浪微博性别歧视评论数据集，用于测试中文网络性别歧视识别能力。仓库地址：<https://github.com/aggiejiang/SWSR>

下载后的数据文件放在 `.tmp-real-datasets/` 目录下，该目录已被 Git 忽略。

## 标签映射规则

本系统是通用内容安全审核系统，而上述数据集的标签各有侧重。因此评测时做了如下映射：

- COLDataset 攻击性评论 -> 有害内容，可接受分类：`辱骂` 或 `其他`
- COLDataset 非攻击性评论 -> 安全内容，最高风险不应超过 `提示`
- ChineseHarm-Bench 不违规 -> 安全内容
- ChineseHarm-Bench 低俗色情 -> 有害内容，可接受分类：`低俗` 或 `色情`
- ChineseHarm-Bench 博彩、欺诈、黑产广告 -> 有害内容，可接受分类：`违法广告`、`诈骗` 或 `引流`
- ChineseHarm-Bench 谩骂引战 -> 有害内容，可接受分类：`辱骂` 或 `其他`
- SWSR 性别歧视 -> 有害内容，可接受分类：`辱骂`、`其他`、`低俗` 或 `色情`
- SWSR 非性别歧视 -> 安全内容

二分类指标中，`警告` 和 `违规` 计为有害预测；`合规` 和 `提示` 计为安全或低风险预测。

## 主要错误原因

本轮失败样本复核发现，错误主要来自以下几类：

- **上下文误判**：一些正常的社会、法律、性别、族群、营销讨论会包含敏感词，规则层或变体层容易将其过度判定。
- **L3 本地兜底优先级不足**：外部语义模型曾将部分短博彩、黑产广告判成较弱的 `提示/其他`，导致更明确的本地语义兜底没有机会覆盖。
- **短广告和黑话样本不足**：如 `金花牛牛玩吗`、`dy评论`、`小红书发文`、`抄小说吗` 等短句，需要组合意图信号判断，不能只依赖单个关键词。
- **隐晦辱骂和性别歧视识别弱**：谐音、暗讽、地域/性别刻板印象、SWSR 中的微歧视样本，需要更强的语义分类能力。
- **分类漂移**：一些混合了色情、辱骂、涉政或广告信号的样本虽然被识别为风险内容，但容易落到相邻分类，例如 `涉政`、`色情` 或 `违法广告`。
- **批量评测性能问题**：旧评测脚本逐条调用 `/audit/text`，每条样本都会重复创建审核器和变体引擎，导致大样本评测非常慢。

## 本轮优化内容

本轮做了 4 类针对性优化：

- **上下文告警降权**：当 L3 判定内容整体合规时，L1/L2 中非特异性的上下文类告警会被压低风险；但自定义词和明确高风险类别仍保留原有处置能力。
- **本地语义兜底优先级修正**：对于本地规则已明确识别的高置信风险，当 LLM 返回 `合规` 或较弱的 `提示/其他` 时，系统会采用本地结果。
- **短广告/黑话召回增强**：新增或扩展了博彩与黑产任务广告模式，包括 `金花/牛牛/棋牌/回血`、`dy/ks评论`、`小红书/小红薯发文`、`抄/炒/超小说` 等。
- **评测与运行性能优化**：L2 拼音变体在引擎初始化时预计算；真实样本评测脚本改用 `/audit/batch`，每批复用一个审核器。

这些优化刻意避免对所有隐晦词做粗暴关键词升级，因为那会明显增加正常讨论的误判风险。

## 基线评测：140 个样本

命令：

```powershell
python scripts/evaluate_real_world_samples.py --cold-per-label 20 --harm-per-category 10 --swsr-per-label 20 --output-dir .tmp-real-eval/baseline-140
```

指标：

| 指标 | 数值 |
| --- | ---: |
| 样本总数 | 140 |
| 通过样本 | 88 |
| 失败样本 | 52 |
| 准确率 Accuracy | 0.6643 |
| 精确率 Precision | 0.7416 |
| 召回率 Recall | 0.7333 |
| F1 | 0.7374 |
| 特异度 Specificity | 0.5400 |
| TP | 66 |
| TN | 27 |
| FP | 23 |
| FN | 24 |

分类映射准确率：`60 / 90 = 0.6667`。

## 最终本地修复前的线上可比评测：280 个样本

这次历史评测使用当时配置的语义层，保留为对照参考。

```powershell
python scripts/evaluate_real_world_samples.py --cold-per-label 40 --harm-per-category 20 --swsr-per-label 40 --output-dir .tmp-real-eval/expanded-280-final
```

| 指标 | 数值 |
| --- | ---: |
| 样本总数 | 280 |
| 通过样本 | 196 |
| 失败样本 | 84 |
| 准确率 Accuracy | 0.6714 |
| 精确率 Precision | 0.8729 |
| 召回率 Recall | 0.5722 |
| F1 | 0.6913 |
| 特异度 Specificity | 0.8500 |
| TP | 103 |
| TN | 85 |
| FP | 15 |
| FN | 77 |

分类映射准确率：`115 / 180 = 0.6389`。

## 最新本地可复现评测：280 个样本

本次评测显式关闭外部 LLM key，仅使用规则层、变体层、本地语义兜底、融合层和处置层，并通过 API 批量接口完成测试。

```powershell
$env:DEEPSEEK_API_KEY=''
python scripts/evaluate_real_world_samples.py --cold-per-label 40 --harm-per-category 20 --swsr-per-label 40 --output-dir .tmp-real-eval/expanded-280-local-after-fix
```

| 指标 | 数值 |
| --- | ---: |
| 样本总数 | 280 |
| 通过样本 | 174 |
| 失败样本 | 106 |
| 准确率 Accuracy | 0.5214 |
| 精确率 Precision | 0.8594 |
| 召回率 Recall | 0.3056 |
| F1 | 0.4508 |
| 特异度 Specificity | 0.9100 |
| TP | 55 |
| TN | 91 |
| FP | 9 |
| FN | 125 |

分类映射准确率：`86 / 180 = 0.4778`。

分数据源结果：

| 数据源 | 通过率 | 准确率 | 精确率 | 召回率 | F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| COLDataset | 58/80 | 0.5250 | 1.0000 | 0.0500 | 0.0952 |
| ChineseHarm-Bench / 不违规 | 19/20 | 0.9500 | 0.0000 | 0.0000 | 0.0000 |
| ChineseHarm-Bench / 低俗色情 | 7/20 | 0.5000 | 1.0000 | 0.5000 | 0.6667 |
| ChineseHarm-Bench / 博彩 | 12/20 | 0.6000 | 1.0000 | 0.6000 | 0.7500 |
| ChineseHarm-Bench / 欺诈 | 6/20 | 0.3500 | 1.0000 | 0.3500 | 0.5185 |
| ChineseHarm-Bench / 谩骂引战 | 5/20 | 0.0500 | 1.0000 | 0.0500 | 0.0952 |
| ChineseHarm-Bench / 黑产广告 | 18/20 | 0.9000 | 1.0000 | 0.9000 | 0.9474 |
| SWSR / SexComment | 49/80 | 0.4625 | 0.3846 | 0.1250 | 0.1887 |

## 扩展本地评测：420 个样本

命令：

```powershell
$env:DEEPSEEK_API_KEY=''
python scripts/evaluate_real_world_samples.py --cold-per-label 60 --harm-per-category 30 --swsr-per-label 60 --output-dir .tmp-real-eval/expanded-420-local-after-fix
```

| 指标 | 数值 |
| --- | ---: |
| 样本总数 | 420 |
| 通过样本 | 246 |
| 失败样本 | 174 |
| 准确率 Accuracy | 0.4952 |
| 精确率 Precision | 0.8295 |
| 召回率 Recall | 0.2704 |
| F1 | 0.4078 |
| 特异度 Specificity | 0.9000 |
| TP | 73 |
| TN | 135 |
| FP | 15 |
| FN | 197 |

分类映射准确率：`115 / 270 = 0.4259`。

分数据源结果：

| 数据源 | 通过率 | 准确率 | 精确率 | 召回率 | F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| COLDataset | 85/120 | 0.5500 | 0.8750 | 0.1167 | 0.2059 |
| ChineseHarm-Bench / 不违规 | 28/30 | 0.9333 | 0.0000 | 0.0000 | 0.0000 |
| ChineseHarm-Bench / 低俗色情 | 8/30 | 0.3667 | 1.0000 | 0.3667 | 0.5366 |
| ChineseHarm-Bench / 博彩 | 17/30 | 0.5667 | 1.0000 | 0.5667 | 0.7234 |
| ChineseHarm-Bench / 欺诈 | 6/30 | 0.3000 | 1.0000 | 0.3000 | 0.4615 |
| ChineseHarm-Bench / 谩骂引战 | 5/30 | 0.0333 | 1.0000 | 0.0333 | 0.0645 |
| ChineseHarm-Bench / 黑产广告 | 19/30 | 0.6333 | 1.0000 | 0.6333 | 0.7755 |
| SWSR / SexComment | 78/120 | 0.4750 | 0.4286 | 0.1500 | 0.2222 |

## 结果解读

当前本地模式下的系统整体偏保守：

- 上下文告警保护降低了误判，420 样本本地评测中特异度达到 `0.9000`。
- 黑产广告在 280 个本地可比样本中表现较好，ChineseHarm-Bench 黑产广告通过率达到 `18/20`。
- 本地模式整体召回率仍偏低，尤其是隐晦辱骂、性别歧视、软诈骗、低俗色情黑话等内容。
- 在线语义层对泛化能力仍然重要。本地兜底更适合作为高精度安全网，而不是完整替代语义模型。

后续最需要补强的是专门的语义分类能力，尤其是辱骂、性别歧视和伪装诈骗。如果继续只靠规则和本地兜底，很难稳定理解编码表达、讽刺语境和复杂社会讨论。

## 复现方法

下载数据集：

```powershell
git clone --depth 1 https://github.com/thu-coai/COLDataset.git .tmp-real-datasets/COLDataset
git clone --depth 1 https://huggingface.co/datasets/zjunlp/ChineseHarm-bench .tmp-real-datasets/ChineseHarm-bench
git clone --depth 1 https://github.com/aggiejiang/SWSR.git .tmp-real-datasets/SWSR
```

运行最新扩展本地评测：

```powershell
$env:DEEPSEEK_API_KEY=''
python scripts/evaluate_real_world_samples.py --cold-per-label 60 --harm-per-category 30 --swsr-per-label 60 --output-dir .tmp-real-eval/expanded-420-local-after-fix
```

查看生成结果：

```text
.tmp-real-eval/expanded-420-local-after-fix/real_world_eval_report.md
.tmp-real-eval/expanded-420-local-after-fix/real_world_eval_results.json
```
