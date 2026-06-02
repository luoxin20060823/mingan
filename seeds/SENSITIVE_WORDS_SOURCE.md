# 敏感词库来源说明

当前 `seeds/sensitive_words.csv` 来自公开项目：

- 项目：Sensitive-lexicon 中文敏感词库
- 地址：https://github.com/konsheng/Sensitive-lexicon
- 许可证：MIT License
- 来源目录：`Vocabulary/`

本项目将公开词库转换为统一 CSV 格式：

```csv
word,category,level
```

转换规则位于 `scripts/build_sensitive_seed.py`。分类和等级根据源文件名映射到本系统支持的枚举：

- `涉政`
- `暴恐`
- `色情`
- `辱骂`
- `违法广告`
- `其他`

说明：敏感词判断强依赖业务语境和适用地区。该词库是公开来源的基础拦截词库，不等同于最终审核政策，生产使用时仍应结合业务规则、人工复核和申诉机制。
