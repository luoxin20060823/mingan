# Requirements Document

## Introduction

本项目为"轻量级中文内容安全审核平台"，是网络空间安全治理课程的课程设计原型，模拟商业内容审核 SaaS（如阿里云内容安全、网易易盾）的核心能力。系统聚焦三大模块：

1. **多策略内容审核引擎**：通过 L1 规则匹配层、L2 变体识别层、L3 LLM 语义层、L4 综合决策层组成的流水线，对中文文本进行多维度违规检测；
2. **内容分级与处置建议**：输出 4 级违规等级、6 类违规标签，并给出结构化处置建议；
3. **REST API 与 Web 测试控制台**：提供单条/批量审核 API，并配套基于 HTML + Tailwind CSS + Alpine.js 的零构建前端控制台，支持单条审核、批量审核、历史记录、词库管理四个功能页。

后端使用 Python + FastAPI + SQLite，LLM 优先调用 DeepSeek API。系统仅处理中文文本，单条文本上限 2000 字。

## Glossary

- **Moderation_Platform**：整体内容审核平台，包含审核引擎、API 服务、Web 控制台、词库与历史记录存储。
- **Audit_Engine**：多策略审核引擎，由 L1、L2、L3、L4 四层组成的审核流水线。
- **L1_Rule_Layer**：规则层，对输入文本与敏感词库进行精确字符串匹配。
- **L2_Variant_Layer**：变体识别层，对拼音化、谐音字、形近字、emoji/特殊字符插入、空格/换行干扰共 5 种变体形式进行还原与匹配。
- **L3_Semantic_Layer**：语义层，调用国内 LLM API（DeepSeek 优先）对文本进行语义违规判定。
- **L4_Decision_Layer**：决策层，融合 L1/L2/L3 的独立分数与命中证据，输出最终违规等级、违规类别、置信度与处置建议。
- **Lexicon**：敏感词库，包括从公开 GitHub 词库（如 sensitive-stop-words）导入的基础词条与运营自定义词条。
- **Custom_Lexicon_Entry**：自定义敏感词条，每条包含词语、违规类别、违规等级、备注、创建时间字段。
- **API_Server**：基于 FastAPI 的后端服务，对外暴露审核与管理 REST 接口。
- **Web_Console**：基于静态 HTML + Tailwind CSS + Alpine.js 的前端测试控制台。
- **History_Service**：基于 SQLite 的审核历史记录服务，负责持久化每次审核请求与结果。
- **LLM_Client**：封装对 DeepSeek 等国内 LLM API 的调用与重试逻辑的客户端组件。
- **违规等级（Risk_Level）**：4 个枚举值——`compliant`（合规）、`notice`（提示）、`warning`（警告）、`violation`（违规）。
- **违规类别（Risk_Category）**：6 个枚举值——`politics`（涉政）、`violence`（暴恐）、`porn`（色情）、`abuse`（辱骂）、`illegal_ad`（违法广告）、`other`（其他）。
- **处置建议（Disposition）**：结构化字段，形如 `{platform_action, user_message, ops_note}`，其中 `platform_action` 取值为 `pass`（通过）、`fold`（折叠）、`delete`（删除）、`ban`（封禁）。
- **审核结果（Audit_Result）**：单条文本的完整审核响应，包含违规等级、违规类别列表、各层分数、命中详情、LLM 解释、处理耗时、总置信度、处置建议。
- **命中详情（Hit_Detail）**：一次命中的结构化记录，包含来源层（L1/L2/L3）、命中词或片段、起止字符位置、对应违规类别。

## Requirements

### Requirement 1：单条文本审核 API

**User Story:** 作为接入方开发者，我希望通过一个 REST 接口提交单条文本进行审核，以便在我的应用中实时拦截违规内容。

#### Acceptance Criteria

1. THE API_Server SHALL 暴露 `POST /audit/text` 接口，接收 JSON 请求体 `{ "text": string }`。
2. WHEN `POST /audit/text` 收到 `text` 长度在 1 到 2000 个 Unicode 字符之间的请求，THE API_Server SHALL 返回 HTTP 200 和符合 Audit_Result 结构的 JSON 响应。
3. IF `POST /audit/text` 收到 `text` 字段缺失或为空字符串的请求, THEN THE API_Server SHALL 返回 HTTP 400 和包含错误码 `EMPTY_TEXT` 的错误响应。
4. IF `POST /audit/text` 收到 `text` 长度超过 2000 个 Unicode 字符的请求, THEN THE API_Server SHALL 返回 HTTP 400 和包含错误码 `TEXT_TOO_LONG` 的错误响应。
5. THE Audit_Result SHALL 包含字段 `risk_level`、`risk_categories`、`scores`（含 `l1`、`l2`、`l3`）、`hits`、`llm_explanation`、`elapsed_ms`、`confidence`、`disposition`。
6. WHEN `POST /audit/text` 处理成功，THE History_Service SHALL 将本次请求文本与 Audit_Result 持久化为一条历史记录。

### Requirement 2：批量文本审核 API

**User Story:** 作为接入方开发者，我希望一次提交多条文本进行审核，以便在批处理场景下提高吞吐效率。

#### Acceptance Criteria

1. THE API_Server SHALL 暴露 `POST /audit/batch` 接口，接收 JSON 请求体 `{ "texts": string[] }`。
2. WHEN `POST /audit/batch` 收到 `texts` 数组长度在 1 到 50 之间且每条文本长度不超过 2000 个 Unicode 字符的请求，THE API_Server SHALL 返回 HTTP 200 和按输入顺序排列的 Audit_Result 数组。
3. IF `POST /audit/batch` 收到 `texts` 数组为空或长度超过 50 的请求, THEN THE API_Server SHALL 返回 HTTP 400 和包含错误码 `BATCH_SIZE_INVALID` 的错误响应。
4. IF `POST /audit/batch` 中某一条文本超出 2000 字上限, THEN THE API_Server SHALL 在该条对应的结果位置返回 `{ "error": "TEXT_TOO_LONG" }`，并继续处理其余文本。
5. WHEN `POST /audit/batch` 处理完成，THE History_Service SHALL 为每条非错误结果各持久化一条历史记录。

### Requirement 3：L1 规则匹配层

**User Story:** 作为安全策略运营，我希望平台对已知敏感词进行精确匹配，以便快速拦截已知违规内容。

#### Acceptance Criteria

1. WHEN Audit_Engine 收到一条文本，THE L1_Rule_Layer SHALL 在 Lexicon 中执行精确字符串匹配，输出每条命中词及其在原文中的起止字符位置。
2. THE L1_Rule_Layer SHALL 为每条命中词附加 Lexicon 中预先标注的违规类别。
3. THE L1_Rule_Layer SHALL 输出一个范围在 0.0 到 1.0 的 `l1` 分数，反映 L1 命中的严重程度。
4. WHEN 文本对所有 Lexicon 词条均无 L1 命中，THE L1_Rule_Layer SHALL 输出 `l1` 分数为 0.0 且 `hits` 中无 L1 来源的命中详情。
5. THE L1_Rule_Layer SHALL 对长度为 2000 个 Unicode 字符的输入文本在 50 毫秒内完成匹配。

### Requirement 4：L2 变体识别层

**User Story:** 作为安全策略运营，我希望平台能识别敏感词的常见变体写法，以便对抗用户绕过手段。

#### Acceptance Criteria

1. WHEN Audit_Engine 进入 L2 阶段，THE L2_Variant_Layer SHALL 对输入文本依次进行拼音化还原、谐音字归一化、形近字归一化、emoji 与特殊字符剥离、空格与换行剥离共 5 种变体处理。
2. WHEN 任一变体处理后的文本在 Lexicon 中匹配到敏感词，THE L2_Variant_Layer SHALL 输出一条 Hit_Detail，包含原文起止位置、变体类型、命中词、违规类别。
3. THE L2_Variant_Layer SHALL 输出一个范围在 0.0 到 1.0 的 `l2` 分数。
4. WHEN 文本经过全部 5 种变体处理后均无命中，THE L2_Variant_Layer SHALL 输出 `l2` 分数为 0.0。
5. WHERE 同一敏感词被 L1 与 L2 同时命中，THE L2_Variant_Layer SHALL 在 Hit_Detail 中标记 `duplicated_with_l1=true` 以避免决策层重复加权。

### Requirement 5：L3 语义识别层

**User Story:** 作为安全策略运营，我希望平台能通过 LLM 理解文本语义，以便发现规则与变体层都无法覆盖的隐性违规内容。

#### Acceptance Criteria

1. WHEN Audit_Engine 进入 L3 阶段，THE LLM_Client SHALL 向 DeepSeek API 发送包含输入文本与 6 类违规类别定义的提示词。
2. THE L3_Semantic_Layer SHALL 解析 LLM 响应并输出 `l3` 分数（0.0 到 1.0）、命中违规类别列表、自然语言解释 `llm_explanation`。
3. IF LLM_Client 调用 DeepSeek API 失败或超时（超过 10 秒）, THEN THE L3_Semantic_Layer SHALL 输出 `l3` 分数为 0.0、`llm_explanation` 为 `"LLM unavailable"`，并允许 Audit_Engine 继续返回基于 L1+L2 的结果。
4. THE L3_Semantic_Layer SHALL 在 `hits` 中为 LLM 判定的违规类别各添加一条来源为 `L3`、不含字符位置的 Hit_Detail。
5. WHERE 配置项 `l3_enabled` 为 false，THE Audit_Engine SHALL 跳过 L3_Semantic_Layer 并将 `l3` 分数置为 0.0。

### Requirement 6：L4 决策层与综合评分

**User Story:** 作为接入方，我希望平台输出统一的违规等级与置信度，而不是让我自己解读三层原始分数。

#### Acceptance Criteria

1. WHEN Audit_Engine 完成 L1、L2、L3 计算，THE L4_Decision_Layer SHALL 根据可配置权重将 `l1`、`l2`、`l3` 融合为总置信度 `confidence`，取值范围 0.0 到 1.0。
2. THE L4_Decision_Layer SHALL 根据 `confidence` 落入的可配置阈值区间，将 `risk_level` 映射为 `compliant`、`notice`、`warning`、`violation` 之一。
3. THE L4_Decision_Layer SHALL 汇总 L1、L2、L3 命中的违规类别，按命中权重排序后输出 `risk_categories` 数组。
4. WHEN `risk_categories` 为空且 `confidence` 低于 `compliant` 阈值，THE L4_Decision_Layer SHALL 将 `risk_level` 设为 `compliant` 且 `risk_categories` 设为 `["other"]` 之外的空数组。
5. THE L4_Decision_Layer SHALL 输出一个 `elapsed_ms` 字段，记录从 Audit_Engine 接收文本到产生最终结果的总耗时。

### Requirement 7：结构化处置建议

**User Story:** 作为内容运营，我希望审核结果直接告诉我应该对内容做什么动作，以便快速执行处置。

#### Acceptance Criteria

1. THE L4_Decision_Layer SHALL 为每个 Audit_Result 生成一个 Disposition 对象，包含 `platform_action`、`user_message`、`ops_note` 三个字段。
2. WHEN `risk_level` 为 `compliant`，THE L4_Decision_Layer SHALL 设置 `platform_action` 为 `pass`。
3. WHEN `risk_level` 为 `notice`，THE L4_Decision_Layer SHALL 设置 `platform_action` 为 `fold`。
4. WHEN `risk_level` 为 `warning`，THE L4_Decision_Layer SHALL 设置 `platform_action` 为 `delete`。
5. WHEN `risk_level` 为 `violation`，THE L4_Decision_Layer SHALL 设置 `platform_action` 为 `ban`。
6. THE L4_Decision_Layer SHALL 根据 `risk_categories` 与 `risk_level` 从可配置文案模板中渲染 `user_message` 与 `ops_note`，并保证两字段均为非空字符串。

### Requirement 8：敏感词库管理

**User Story:** 作为安全策略运营，我希望能维护自定义敏感词，以便快速响应新出现的违规内容。

#### Acceptance Criteria

1. THE API_Server SHALL 暴露 `GET /lexicon`，按分页返回所有 Custom_Lexicon_Entry，每条包含 `id`、`word`、`category`、`level`、`note`、`created_at`。
2. THE API_Server SHALL 暴露 `POST /lexicon`，接收 `{ "word", "category", "level", "note" }` 并新增一条 Custom_Lexicon_Entry。
3. WHEN `POST /lexicon` 收到的 `category` 不在 6 类违规类别中或 `level` 不在 4 级违规等级中，THE API_Server SHALL 返回 HTTP 400 和错误码 `INVALID_LEXICON_FIELD`。
4. THE API_Server SHALL 暴露 `PUT /lexicon/{id}` 与 `DELETE /lexicon/{id}` 用于更新与删除指定词条。
5. WHEN Custom_Lexicon_Entry 被新增、更新或删除，THE Audit_Engine SHALL 在下一次审核请求中使用最新的 Lexicon。
6. THE Lexicon SHALL 在系统首次启动时从打包的公开词库文件加载基础词条，且基础词条不可通过 `DELETE /lexicon/{id}` 删除。

### Requirement 9：历史记录持久化与查询

**User Story:** 作为运营人员，我希望查看历史审核记录并按条件筛选，以便复盘策略效果。

#### Acceptance Criteria

1. THE History_Service SHALL 使用 SQLite 持久化每条审核记录，字段包括 `id`、`text`、`risk_level`、`risk_categories`、`scores`、`disposition`、`elapsed_ms`、`created_at`。
2. THE API_Server SHALL 暴露 `GET /history`，按 `created_at` 倒序返回历史记录，支持查询参数 `risk_level`、`risk_category`、`start_time`、`end_time`、`page`、`page_size`。
3. WHEN `GET /history` 收到 `risk_level` 参数取值不在 4 级违规等级枚举内，THE API_Server SHALL 返回 HTTP 400 和错误码 `INVALID_FILTER`。
4. THE API_Server SHALL 在 `GET /history` 响应中包含 `total`、`page`、`page_size`、`items` 字段。
5. WHEN `start_time` 晚于 `end_time`，THE API_Server SHALL 返回 HTTP 400 和错误码 `INVALID_TIME_RANGE`。

### Requirement 10：Web 控制台 - 单条审核

**User Story:** 作为评审与演示用户，我希望在网页上输入一段文本就能看到完整的多层审核结果，以便直观理解平台能力。

#### Acceptance Criteria

1. THE Web_Console SHALL 提供"单条审核"标签页，包含一个最多 2000 字的文本输入区与"提交审核"按钮。
2. WHEN 用户点击"提交审核"按钮，THE Web_Console SHALL 调用 `POST /audit/text` 并在响应到达后展示 Audit_Result。
3. THE Web_Console SHALL 在原文展示区高亮所有 Hit_Detail 对应的字符片段，并区分 L1 与 L2 的命中颜色。
4. THE Web_Console SHALL 使用雷达图展示 `l1`、`l2`、`l3` 三个独立分数。
5. THE Web_Console SHALL 展示 `risk_level`、`risk_categories`、`confidence`、`elapsed_ms`、`llm_explanation` 与 Disposition 的全部字段。
6. IF `POST /audit/text` 返回非 200 响应, THEN THE Web_Console SHALL 显示后端返回的错误码与错误信息。

### Requirement 11：Web 控制台 - 批量审核

**User Story:** 作为评审用户，我希望一次批量审核多条文本，以便观察平台在批量场景下的表现。

#### Acceptance Criteria

1. THE Web_Console SHALL 提供"批量审核"标签页，支持两种输入方式：在多行文本框中按行粘贴文本，或上传 CSV 文件。
2. WHEN 用户上传 CSV 文件，THE Web_Console SHALL 解析首列为待审核文本，并在表格中预览前 50 条。
3. WHEN 用户点击"开始批量审核"，THE Web_Console SHALL 调用 `POST /audit/batch` 并以表格形式展示每条文本的 `risk_level`、`risk_categories`、`confidence`、`platform_action`。
4. IF 批量结果中某一条返回错误对象, THEN THE Web_Console SHALL 在该行的状态列显示对应错误码。
5. THE Web_Console SHALL 提供"导出 CSV"按钮，将批量审核结果导出为 UTF-8 编码的 CSV 文件。

### Requirement 12：Web 控制台 - 历史记录

**User Story:** 作为评审用户，我希望查看历史审核记录并按条件筛选，以便回看演示数据。

#### Acceptance Criteria

1. THE Web_Console SHALL 提供"历史记录"标签页，展示来自 `GET /history` 的分页结果。
2. THE Web_Console SHALL 提供按 `risk_level`、`risk_category`、时间范围的筛选控件，并在筛选条件变化时重新调用 `GET /history`。
3. THE Web_Console SHALL 在每行末尾提供"查看详情"按钮，点击后展示该条记录的完整 Audit_Result。
4. WHEN `GET /history` 返回空结果集，THE Web_Console SHALL 显示"暂无符合条件的历史记录"提示文案。

### Requirement 13：Web 控制台 - 词库管理

**User Story:** 作为安全策略运营，我希望在 Web 上管理自定义敏感词，以便无需直接操作数据库。

#### Acceptance Criteria

1. THE Web_Console SHALL 提供"词库管理"标签页，展示来自 `GET /lexicon` 的分页结果。
2. THE Web_Console SHALL 提供新增词条的表单，包含 `word`、`category`、`level`、`note` 输入控件，其中 `category` 与 `level` 为下拉选择。
3. WHEN 用户提交新增表单，THE Web_Console SHALL 调用 `POST /lexicon` 并在成功后刷新词条列表。
4. THE Web_Console SHALL 在每条词条所在行提供"编辑"与"删除"按钮，分别调用 `PUT /lexicon/{id}` 与 `DELETE /lexicon/{id}`。
5. WHERE 词条来源为基础词库，THE Web_Console SHALL 禁用该行的"删除"按钮并显示"基础词库"标记。

### Requirement 14：性能与可观测性

**User Story:** 作为答辩演示者，我希望平台在课程设计典型负载下保持稳定的响应耗时，以便演示效果可控。

#### Acceptance Criteria

1. WHEN `POST /audit/text` 处理一条 500 字以内的文本且 `l3_enabled` 为 false，THE Audit_Engine SHALL 在 200 毫秒内返回响应。
2. WHEN `POST /audit/text` 处理一条 500 字以内的文本且 `l3_enabled` 为 true 且 LLM 调用成功，THE Audit_Engine SHALL 在 5 秒内返回响应。
3. THE API_Server SHALL 为每个审核请求记录一条结构化日志，包含请求 ID、`risk_level`、`elapsed_ms`、`l3_enabled`。
4. IF API_Server 在处理审核请求时发生未预期异常, THEN THE API_Server SHALL 返回 HTTP 500 和错误码 `INTERNAL_ERROR`，并将异常堆栈写入服务端日志。
