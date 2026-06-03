# Content Audit Platform

中文内容审核平台，基于 FastAPI + SQLite，提供单条审核、批量审核、历史查询、敏感词管理、规则管理和策略配置的静态控制台。内置词库可由公开真实中文敏感词库转换生成，不依赖手写演示词。

## 如何运行

### 1. 环境要求

- Python 3.12 或更高
- Windows / macOS / Linux 均可
- 可选：DeepSeek API Key，用于 L3 语义审核

### 2. 安装依赖

```bash
python -m pip install -e .[dev]
```

### 3. 启动服务

```bash
python -m uvicorn audit.main:app --reload --reload-dir src --reload-dir static --reload-dir seeds --host 127.0.0.1 --port 8000
```

启动后浏览器打开：

```text
http://127.0.0.1:8000/
```

首页会自动跳转到静态控制台。

### 4. 首次启动会做什么

- 自动创建 SQLite 数据库：`./data/audit.db`
- 自动创建 `audit_records` 和 `sensitive_words` 两张表
- 自动导入内置敏感词种子：`./seeds/sensitive_words.csv`
- 如果 CSV 中的 builtin 词库和数据库已有 builtin 词库不一致，会自动替换数据库中的 builtin 词；自定义词 `source=custom` 会保留
- 自动加载：
  - `./seeds/homophones.json`
  - `./seeds/glyph_confusables.json`
  - `./seeds/regex_rules.yaml`

### 5. 可选配置

复制 `.env.example` 为 `.env` 后按需修改：

```env
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_TIMEOUT_SECONDS=5
SQLITE_PATH=./data/audit.db
```

说明：

- `DEEPSEEK_API_KEY` 为空时，L3 会降级为错误结果，但 L1/L2/L4 仍可正常工作
- `SQLITE_PATH` 可改成其他数据库文件路径

## 使用说明

### 静态控制台

控制台包含六个入口：

- 单条审核
- 批量审核
- 历史记录
- 敏感词管理
- 规则管理
- 策略配置

当前风险类别包括：涉政、暴恐、色情、辱骂、违法广告、诈骗、引流、未成年人风险、低俗、其他。

为降低真实大词库带来的误伤，系统会对部分短泛词做低置信处理。例如“招聘”“兼职”“网络”等词，如果没有刷单、返利、私聊、加微信等风险上下文，会降级为提示并继续保留命中解释；如果和风险上下文同现，则保持高风险。

### 单条审核

1. 切换到“单条审核”
2. 输入不超过 2000 字的文本
3. 点击“提交审核”
4. 查看：
   - 风险等级
   - 违规类别
   - 置信度
   - 命中片段
   - 处置建议
   - 各层耗时

### 批量审核

1. 切换到“批量审核”
2. 每行输入一条文本，最多 50 条
3. 点击“批量审核”
4. 逐条查看结果

### 历史记录

支持按以下条件筛选：

- 风险等级
- 违规类别
- 时间范围

### 敏感词管理

支持：

- 新增自定义敏感词
- 查看敏感词列表
- 按类别和等级筛选
- 删除自定义词条

内置词库 `source=builtin` 不能删除。

### 规则管理

控制台和后端 API 都支持正则规则管理：

- `GET /rules`
- `POST /rules`
- `DELETE /rules/{rule_id}`

启动时会把 `seeds/regex_rules.yaml` 导入为 `source=builtin` 规则；内置规则不能删除。通过控制台或 API 新增的 `source=custom` 规则会立即参与后续审核。

默认内置规则覆盖手机号、URL、QQ、微信/VX、二维码进群和 Telegram/TG 等模式型风险。其中微信、二维码进群和 Telegram/TG 默认归为 `引流`。

### 策略配置

控制台和后端 API 都支持策略配置：

- `GET /policy`
- `PUT /policy`

当前可配置项包括：

- 风险阈值：`hint`、`warning`、`violation`
- 高风险类别：影响警告时是否进入人工复核，以及违规时是拦截还是删除

更新策略后会立即影响后续审核。

## 真实词库

本项目提供真实词库转换脚本：

```bash
python scripts/build_sensitive_seed.py
```

脚本会读取公开项目 `konsheng/Sensitive-lexicon` 的 `Vocabulary/` 目录，并生成：

```text
seeds/sensitive_words.csv
```

词库来源和许可说明见：

```text
seeds/SENSITIVE_WORDS_SOURCE.md
```

如果你已经启动过旧版本系统，重新启动服务后，系统会自动用新的 CSV 替换数据库里的 builtin 词库，并保留手工新增的 custom 词。

转换和运行时会做类别归一化，把部分泛类词条细分到诈骗、引流、未成年人风险、低俗等更实用的审核类别。

也可以不生成 CSV，直接通过环境变量指定真实词库目录：

```env
LEXICON_DIR=./.tmp-sensitive-lexicon/Vocabulary
```

配置后，系统启动时会优先从该目录读取词库。

## API 快速示例

### 单条审核

```bash
curl -X POST "http://127.0.0.1:8000/audit/text" ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"示例文本\"}"
```

### 批量审核

```bash
curl -X POST "http://127.0.0.1:8000/audit/batch" ^
  -H "Content-Type: application/json" ^
  -d "{\"texts\":[\"文本1\",\"文本2\"]}"
```

### 查询历史

```bash
curl "http://127.0.0.1:8000/history?page=1&page_size=20"
```

### 新增敏感词

```bash
curl -X POST "http://127.0.0.1:8000/words" ^
  -H "Content-Type: application/json" ^
  -d "{\"word\":\"测试词\",\"category\":\"其他\",\"level\":\"违规\"}"
```

### 删除敏感词

```bash
curl -X DELETE "http://127.0.0.1:8000/words/123"
```

### 新增正则规则

```bash
curl -X POST "http://127.0.0.1:8000/rules" ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"invite_code\",\"pattern\":\"邀请码[:：]?[A-Z0-9]{6}\",\"category\":\"引流\",\"level\":\"警告\"}"
```

### 更新策略配置

```bash
curl -X PUT "http://127.0.0.1:8000/policy" ^
  -H "Content-Type: application/json" ^
  -d "{\"risk_thresholds\":{\"hint\":0.1,\"warning\":0.4,\"violation\":0.8},\"high_risk_categories\":[\"涉政\",\"暴恐\",\"色情\",\"未成年人风险\"]}"
```

## 测试与验证

```bash
python -m pytest tests/unit tests/property tests/integration tests/perf -q
python -m compileall -q src/audit
```

典型审核样例集位于：

```text
tests/fixtures/moderation_cases.jsonl
```

样例覆盖正常文本、误伤文本、诈骗、引流、未成年人风险、符号变体、同音变体、默认联系方式规则和反诈教育文本。每次策略调整后都应运行完整测试，避免审核能力退化。

## 常见问题

### 端口被占用

改成其他端口启动即可：

```bash
uvicorn audit.main:app --host 127.0.0.1 --port 8001
```

### 没有 DeepSeek Key 能不能跑

可以。系统会自动降级，L1/L2/L4 继续可用。

### 想重置数据库

停止服务后删除 `./data/audit.db` 及相关 `-wal`、`-shm` 文件，再重新启动。

### PowerShell 里中文显示异常

这是终端编码显示问题，不影响服务本身。接口返回和文件内容都按 UTF-8 处理。
