# Content Audit Platform 技术说明

## 1. 系统目标

这个系统面向中文内容审核场景，目标是把“规则命中、变体识别、语义判断、处置建议、历史留存”串成一条可执行链路。它的重点不是单纯给出一个分数，而是输出能直接用于运营或人工复核的结构化结果。

系统当前覆盖这些能力：

- 单条文本审核
- 批量文本审核
- 历史记录查询
- 敏感词增删查
- 正则规则增删查
- 风险阈值和高风险类别配置
- 静态 Web 控制台
- 公开真实中文敏感词库转换与 builtin 词库刷新

## 2. 总体架构

系统采用分层架构：

1. `src/audit/main.py` 负责应用装配、启动初始化和静态资源挂载
2. `src/audit/api/` 负责 HTTP 接口、参数校验和错误响应
3. `src/audit/pipeline/` 负责审核流水线
4. `src/audit/repository/` 负责 SQLite 持久化，包括审核记录、敏感词、正则规则和策略配置
5. `src/audit/domain/` 负责领域枚举和数据模型
6. `static/index.html` 负责前端控制台

应用启动时会把数据库、词库缓存、同音字映射、字形混淆表和正则规则加载进 `app.state`，路由处理阶段直接复用这些对象。启动阶段还会比较当前内置词库来源与数据库里的 builtin 词库；如果不一致，会替换 builtin 词库，并保留用户新增的 custom 词。正则规则会从 `seeds/regex_rules.yaml` 导入到 SQLite，后续自定义规则可通过 API 管理。策略配置会写入 SQLite，后续审核请求会读取最新策略。

服务提供 `GET /health` 用于部署和运维检查，返回数据库可用性、词库数量、启用规则数量以及当前语义审核模式。

## 3. 目录结构

- `src/audit/main.py`：FastAPI 入口
- `src/audit/settings.py`：环境变量和默认配置
- `src/audit/api/`：`/audit/text`、`/audit/batch`、`/history`、`/words`
- `src/audit/pipeline/`：L1-L4 审核引擎
- `src/audit/repository/`：SQLite 访问层
- `src/audit/cache/`：词库缓存
- `src/audit/domain/`：RiskLevel、ViolationCategory、HitDetail 等模型
- `seeds/`：内置种子数据
- `scripts/build_sensitive_seed.py`：公开真实词库到系统 CSV 的转换脚本
- `static/`：单页控制台
- `tests/`：单元、性质、集成和性能测试

## 4. 请求与数据流

### 4.1 单条审核

请求 `POST /audit/text` 后，处理流程是：

1. 校验文本长度和非空
2. 从 SQLite 读取当前词库
3. 执行 L1 规则扫描
4. 执行 L2 变体扫描
5. 调用 L3 语义引擎
6. 通过 L4 融合层合成最终结论
7. 构造处置建议
8. 写入 `audit_records`
9. 返回结构化结果

### 4.2 批量审核

`POST /audit/batch` 会复用同一个 orchestrator 对象，按文本逐条执行审核，再批量写入历史表。这样做能减少重复初始化开销，同时保持每条结果独立。

### 4.3 词库变更

`POST /words` 或 `DELETE /words/{id}` 之后会刷新 `app.state.word_cache`。这样下一次审核请求会读取最新词库，不需要重启服务。

### 4.4 规则变更

`POST /rules` 或 `DELETE /rules/{id}` 之后，后续审核请求会从 SQLite 读取最新启用规则。规则用于 L1 正则扫描，适合维护手机号、URL、联系方式、邀请码等模式型风险。

### 4.5 策略变更

`PUT /policy` 会更新风险阈值和高风险类别。后续审核请求会使用最新策略执行 L4 风险融合和处置建议生成。

### 4.6 builtin 词库刷新

系统启动时会读取当前内置词库来源，并与数据库中 `source=builtin` 的词条集合比较。词库来源优先级如下：

1. 如果显式配置了 `LEXICON_DIR`，读取该真实词库目录
2. 否则读取 `SEED_PATH` 指向的 CSV，默认是 `seeds/sensitive_words.csv`

刷新规则：

1. 如果完全一致，不做写入
2. 如果不一致，删除旧 builtin 词条
3. 批量写入新的 builtin 词条
4. 保留 `source=custom` 的人工新增词条

这保证了从演示词库切换到真实词库后，旧数据库不会继续保留演示 builtin 词。

## 5. 领域模型

核心领域对象定义在 `src/audit/domain/`：

- `RiskLevel`：`合规 / 提示 / 警告 / 违规`
- `ViolationCategory`：`涉政 / 暴恐 / 色情 / 辱骂 / 违法广告 / 诈骗 / 引流 / 未成年人风险 / 低俗 / 其他`
- `PlatformAction`：平台动作枚举，包含 `pass / hint / fold / manual_review / block / delete`
- `HitDetail`：命中明细，记录层级、引擎、命中词、原文片段、位置、类别、等级和标记
- `LayerResult`：单层引擎输出，包含得分、命中和耗时
- `L3Result`：L3 额外包含风险等级、类别、解释和错误信息
- `FinalDecision`：融合后的最终判断
- `DisposalSuggestion`：处置建议
- `ProcessingTime`：各层和总耗时
- `AuditRecord`：历史表记录结构

这些模型统一用 Pydantic 表达，保证 API、内存对象和数据库序列化格式尽量一致。

## 6. L1-L4 审核流水线

### L1：规则命中

L1 主要做确定性识别：

- 敏感词精确匹配
- 正则规则匹配
- 命中结果直接生成 `HitDetail`

这层的特点是可解释性最强，适合低成本、高确定性的规则判断。

### L2：变体识别

L2 处理规避式写法，包括：

- 空白符拆分
- 符号插入
- 同音替换
- 拼音变体
- 字形相近替换

这层依赖 `homophones.json` 和 `glyph_confusables.json`，属于对抗型增强。

为降低误伤，L2 只在文本确实发生空白、符号、拼音、同音或字形变体时产生命中；普通原文精确命中由 L1 负责。拼音匹配会跳过单字和过短拼音词；混合拼音扫描还要求原文中确实出现英文字母，避免把正常中文短语全量转拼音后误判为规避文本，例如把“进群”误判为“禁区”的同音规避。

### L3：语义审核

L3 通过 DeepSeek 做语义级判断，返回：

- 风险等级
- 违规类别
- 解释文本
- 额外命中信息或错误信息

L3 请求会使用固定审核契约提示词，要求模型只输出 JSON，并限制字段为：

- `risk_level`：`合规 / 提示 / 警告 / 违规`
- `category`：系统支持的违规类别，合规时必须为空字符串
- `reason`：一句话依据
- `score`：`0.0` 到 `1.0`

响应进入融合层前会做本地校验：未知风险等级、未知类别、缺失字段、空原因、非法分数和非 JSON 内容都会转成 L3 降级错误，而不是把不可信模型输出直接传给 L4。合规响应会把类别归一为空，避免“合规 + 其他”影响最终类别。

如果 `DEEPSEEK_API_KEY` 没有配置，L3 会启用本地语义兜底规则。兜底规则只在多个上下文信号同时出现时触发，例如“保证金/刷单/返利/提现”组合归为诈骗，“未成年人/裸照/诱导”组合归为未成年人风险，“二维码/进群/领取”等组合归为引流。反诈提醒、科普和举报语境会被保护，避免把教育性内容误判为违规。

如果外部 LLM 请求失败、超时或返回非法 JSON，系统会返回 L3 错误降级结果，不阻断整体审核。

### L4：融合决策

L4 负责把三层结果综合起来，输出最终风险等级、类别和置信度。它的作用是避免某一层的单点判断直接决定全局结果。

类别融合会优先保留更具体的业务类别，例如 `未成年人风险`、`诈骗`、`引流`。当泛类 `其他` 与更具体类别同时出现时，系统会尽量把最终类别归到更可运营的具体类别，而不是停留在 `其他`。

## 7. 处置建议

处置建议由最终决策和命中信息生成，输出三项内容：

- `platform_action`
- `user_message`
- `operation_note`

它的目标是把审核结果转换为可执行操作，而不是只给一个抽象分级。

`operation_note` 会包含前几条可解释命中，格式包括层级、引擎、类别、等级、命中词和 flags，例如 `L1/ahocorasick/违法广告/提示:招聘, flags=low_confidence_generic`。这让人工复核能快速判断风险来自规则命中、变体识别、LLM 降级还是低置信泛词。

动作映射规则：

- `合规`：`pass`
- `提示`：默认 `hint`
- 低置信泛词导致的 `提示`：`pass`，同时在命中 flags 中保留 `low_confidence_generic`
- `警告`：高风险类别进入 `manual_review`，其他类别 `fold`
- `违规`：高风险类别 `block`，其他类别 `delete`

## 8. SQLite 设计

### 8.1 表结构

#### `audit_records`

存储每次审核的最终结果和序列化后的附加信息：

- 原文
- 风险等级
- 违规类别
- 置信度
- L1/L2/L3 分数
- 命中详情 JSON
- LLM 解释
- 处置建议 JSON
- 耗时 JSON
- 创建时间

#### `sensitive_words`

存储敏感词词库：

- 词条
- 类别
- 等级
- 来源
- 创建时间

#### `regex_rules`

存储正则审核规则：

- 规则名
- 正则表达式
- 类别
- 等级
- 来源
- 启用状态
- 创建时间

规则有唯一约束 `UNIQUE(name, source)`。启动时会从 `seeds/regex_rules.yaml` 导入 builtin 规则，API 新增的是 custom 规则。

默认 builtin 正则覆盖：

- 手机号
- URL
- QQ
- 微信/VX/V 信联系方式
- 二维码进群/扫码领福利
- Telegram/TG/电报联系方式

联系方式和站外沟通类规则默认归为 `引流`，用于补足真实词库对模式型风险覆盖不足的问题。

#### `policy_settings`

存储审核策略配置：

- 配置键
- JSON 配置值
- 更新时间

当前默认键为 `moderation_policy`，配置内容包括风险阈值和高风险类别。

### 8.2 索引

当前建立了这些索引：

- `created_at`
- `risk_level`
- `violation_category`
- `(created_at, risk_level, violation_category)`

这些索引主要服务历史查询和筛选。

### 8.3 真实词库来源

`seeds/sensitive_words.csv` 可由 `scripts/build_sensitive_seed.py` 从公开词库转换生成：

- 项目：Sensitive-lexicon 中文敏感词库
- 地址：https://github.com/konsheng/Sensitive-lexicon
- 许可证：MIT License
- 来源目录：`Vocabulary/`

转换脚本会按源文件名映射到本系统支持的 `ViolationCategory` 和 `RiskLevel`。来源和许可说明保存在 `seeds/SENSITIVE_WORDS_SOURCE.md`。

如果不希望生成 CSV，可以配置 `LEXICON_DIR` 直接指向公开词库的 `Vocabulary/` 目录。

转换和运行时都会经过 `src/audit/policy/category_rules.py` 的类别归一化规则，用于把真实词库中的泛类词条细分到 `诈骗`、`引流`、`未成年人风险`、`低俗` 等更接近内容平台审核场景的类别。

`src/audit/policy/false_positive.py` 提供短泛词误伤控制。对“招聘”“兼职”“网络”等高频普通词，系统会在缺少风险上下文时降级为 `提示`，并在命中 flags 中标记 `low_confidence_generic`；当这些词与刷单、返利、私聊、加微信等风险上下文同现时，保留原风险等级并标记 `generic_with_risk_context`。

## 9. API 设计

### 9.1 审核接口

- `POST /audit/text`
- `POST /audit/batch`
- `GET /health`

请求模型限制：

- 单条文本最大 2000 字符
- 批量最多 50 条

`GET /health` 返回运行状态，不写入历史记录。主要字段包括：

- `status`
- `database`
- `word_count`
- `enabled_rule_count`
- `semantic_mode`

### 9.2 历史接口

- `GET /history`

支持参数：

- `risk_level`
- `category`
- `start_time`
- `end_time`
- `page`
- `page_size`

### 9.3 词库接口

- `POST /words`
- `GET /words`
- `DELETE /words/{word_id}`

删除时会拒绝内置词条 `source=builtin`。

`GET /words` 支持 `q`、`category`、`level`、`page`、`page_size` 参数。`q` 对词条文本做大小写不敏感的包含匹配。

### 9.4 规则接口

- `POST /rules`
- `GET /rules`
- `DELETE /rules/{rule_id}`

创建规则时会验证正则表达式能正常编译。删除时会拒绝内置规则 `source=builtin`。

`GET /rules` 支持 `q`、`category`、`level`、`enabled`、`page`、`page_size` 参数。`q` 会匹配规则名和正则表达式。

### 9.5 策略接口

- `GET /policy`
- `PUT /policy`

策略接口支持调整风险阈值和高风险类别。阈值必须满足 `hint < warning < violation`。

## 10. 错误处理

系统统一使用 JSON 错误封装：

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "请求参数非法",
    "details": []
  }
}
```

两类主要错误处理：

- `RequestValidationError` 统一映射为 400
- `HTTPException` 统一映射为带 `error` 外壳的响应

这样前端只需要处理一种错误格式。

## 11. 前端实现

`static/index.html` 是一个单页静态控制台，使用 CDN 加载：

- Tailwind CSS
- Alpine.js
- ECharts

页面包含：

- 单条审核
- 批量审核
- 历史记录
- 敏感词管理

前端直接调用后端 API，没有单独的前端构建步骤。

## 12. 配置项

配置定义在 `src/audit/settings.py`：

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_MODEL`
- `DEEPSEEK_TIMEOUT_SECONDS`
- `SQLITE_PATH`
- `SEED_PATH`
- `HOMOPHONE_PATH`
- `GLYPH_PATH`
- `REGEX_RULES_PATH`
- `LOG_LEVEL`

默认值适合本地演示。

## 13. 测试策略

测试分为四层：

- `tests/unit`：算法和领域逻辑
- `tests/property`：性质测试，验证不变量
- `tests/integration`：接口、启动和静态页面
- `tests/perf`：性能基线
- `tests/fixtures/moderation_cases.jsonl`：典型审核样例集，覆盖正常、违规、变体、边界、联系方式引流和误伤场景

案例集测试会显式清空 `DEEPSEEK_API_KEY`，避免本机 `.env` 或网络状态影响本地规则、词库和融合逻辑的回归结果。L3 自身的提示词、响应校验和异常降级由单元测试使用 mock client 覆盖。

推荐的完整验证命令：

```bash
python -m pytest tests/unit tests/property tests/integration tests/perf -q
python -m compileall -q src/audit
```

## 14. 已知限制

- L3 外部模型不可用时只提供保守本地语义兜底，不能替代完整语义模型
- 公开词库仍需要按具体业务场景校准，不能替代平台政策和人工复核
- 当前没有认证、权限、限流和多租户能力
- 静态控制台适合内部演示，不是生产级后台

## 15. 后续优化方向

- 扩充词库和规则库
- 为 L3 增加更强的本地语义模型或可插拔多模型 fallback
- 给历史查询增加分页总页数和导出能力
- 增加认证、审计日志和限流
- 把静态控制台拆成可维护的前端工程
