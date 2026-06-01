# Requirements Document

## Introduction

轻量级内容安全审核 API 平台是一个面向社交舆情场景的敏感内容分级原型系统，目标是以"小而完整"的方式复现商业内容安全 SaaS（如阿里云内容安全、网易易盾）的核心能力。系统通过四层流水线（规则层 → 变体识别层 → 语义层 → 决策层）对文本进行综合研判，输出 0-5 级违规等级、命中类别与处置建议，并通过 REST API 与 Web 测试控制台对外提供能力。

本规格聚焦三个核心模块：

1. **多策略内容审核引擎**：L1 规则层（Aho-Corasick + 正则）、L2 变体识别层（拼音归一化 + 形近字还原 + emoji 解码）、L3 语义层（LLM API）、L4 决策层（综合研判）。
2. **内容分级与处置建议**：违规等级、多标签命中类别、处置建议映射。
3. **REST API + Web 测试控制台**：单条/批量审核接口与可视化试用页面。

明确排除：人工复核工作台、日志统计大屏、词库管理后台、变体攻防演示页、异步任务/限流/鉴权/计费、多模态审核、A/B 策略与合规报告。

## Glossary

- **Audit_Platform**：本系统整体，即"轻量级内容安全审核 API 平台"。
- **Pipeline**：四层流水线审核引擎，按 L1 → L2 → L3 → L4 顺序处理输入文本。
- **L1_Rule_Engine**：规则层，使用 Aho-Corasick 多模匹配进行敏感词库匹配，并执行正则规则。
- **L2_Variant_Normalizer**：变体识别层，对输入文本进行拼音归一化、形近字替换还原与 emoji 解码后再交由 L1 复检。
- **L3_Semantic_Classifier**：语义层，调用外部 LLM API（如 DeepSeek、通义千问）对文本进行语义级研判。
- **L4_Decision_Engine**：决策层，综合 L1、L2、L3 的结果输出最终等级、类别与处置建议。
- **Audit_API**：基于 FastAPI 暴露的 REST 接口，包含 `/audit/text` 与 `/audit/batch`。
- **Web_Console**：Web 测试控制台，供使用者在线输入文本并查看可视化审核结果。
- **Risk_Level**：违规等级，取值范围 0-5，分别对应：合规、提示、警告、折叠、删除、封禁。
- **Hit_Category**：命中类别，多标签，取值集合为 {涉政, 暴恐, 色情, 广告, 辱骂, 谣言, 隐私泄露, 其他}。
- **Disposal_Suggestion**：处置建议，与 Risk_Level 一一对应的运营动作（保留 / 加提示 / 折叠 / 删除 / 封禁账号 等）。
- **Audit_Result**：单条文本的审核结果，包含 Risk_Level、Hit_Category 列表、Disposal_Suggestion、各层判定明细与命中片段。
- **Hit_Span**：文本中被命中的片段，含起止偏移、原文片段、命中词与命中类别。
- **Sensitive_Lexicon**：敏感词库，每个词条包含词、所属类别与基础风险权重。

## Requirements

### Requirement 1: 多层流水线整体编排

**User Story:** 作为审核服务调用方，我希望系统按 L1 → L2 → L3 → L4 的顺序对文本进行综合研判，以便单层被绕过或误杀时仍能得到稳健结果。

#### Acceptance Criteria

1. WHEN 一段文本被提交至 Audit_API，THE Pipeline SHALL 依次执行 L1_Rule_Engine、L2_Variant_Normalizer、L3_Semantic_Classifier、L4_Decision_Engine 四个阶段。
2. THE Pipeline SHALL 在 Audit_Result 中分别记录 L1_Rule_Engine、L2_Variant_Normalizer、L3_Semantic_Classifier 各自的判定结果与命中证据。
3. WHEN L1_Rule_Engine 与 L2_Variant_Normalizer 均未命中任何敏感词且文本长度小于 4 个字符，THE Pipeline SHALL 跳过 L3_Semantic_Classifier 并由 L4_Decision_Engine 直接输出 Risk_Level 为 0 的 Audit_Result。
4. IF L3_Semantic_Classifier 调用失败或超时，THEN THE Pipeline SHALL 在 Audit_Result 中标记 L3 状态为 "unavailable" 并由 L4_Decision_Engine 仅基于 L1、L2 结果输出最终判定。
5. THE Pipeline SHALL 为每条审核请求生成一个全局唯一的审核标识，并记录在 Audit_Result 中。

### Requirement 2: L1 规则层敏感词与正则匹配

**User Story:** 作为审核策略维护者，我希望规则层使用 Aho-Corasick 多模匹配命中已知敏感词，并通过正则规则覆盖固定模式，以便快速拦截显式违规内容。

#### Acceptance Criteria

1. THE L1_Rule_Engine SHALL 在系统启动时从 Sensitive_Lexicon 加载词条并构建 Aho-Corasick 自动机。
2. WHEN 一段文本进入 L1_Rule_Engine，THE L1_Rule_Engine SHALL 使用 Aho-Corasick 自动机一次扫描输出所有命中的 Hit_Span。
3. THE L1_Rule_Engine SHALL 支持配置一组正则规则，并在每次扫描时对输入文本执行全部正则规则，将匹配结果以 Hit_Span 形式合并输出。
4. THE L1_Rule_Engine SHALL 为每个 Hit_Span 标注命中词、起止字符偏移、所属 Hit_Category 与基础风险权重。
5. WHEN 同一片段被多条规则命中，THE L1_Rule_Engine SHALL 保留全部 Hit_Span 记录，不去重合并。
6. WHEN Sensitive_Lexicon 为空且未配置任何正则规则，THE L1_Rule_Engine SHALL 返回空的 Hit_Span 列表并标记自身状态为 "empty_ruleset"。

### Requirement 3: L2 变体识别层

**User Story:** 作为审核策略维护者，我希望系统能够识别拼音、形近字、emoji 等常见绕过手段，以便提升对变体文本的召回率。

#### Acceptance Criteria

1. THE L2_Variant_Normalizer SHALL 对输入文本依次执行 emoji 解码、形近字还原、拼音归一化三种归一化操作，并产出归一化后的文本。
2. WHEN 输入文本中包含 emoji 字符，THE L2_Variant_Normalizer SHALL 将 emoji 替换为其语义占位符或对应中文描述。
3. WHEN 输入文本中包含形近字字典中定义的字符，THE L2_Variant_Normalizer SHALL 将其替换为字典中对应的标准字符。
4. THE L2_Variant_Normalizer SHALL 使用 pypinyin 将归一化后的文本转换为不带声调的拼音串，并保留原文与拼音串的字符级偏移映射。
5. THE L2_Variant_Normalizer SHALL 将归一化后的文本与拼音串分别交由 L1_Rule_Engine 复检，并将命中结果的偏移通过映射关系还原回原始文本的偏移。
6. THE L2_Variant_Normalizer SHALL 在 Audit_Result 中输出归一化文本、拼音串以及由 L2 复检产生的 Hit_Span 列表，并对每个 Hit_Span 标记触发其命中的归一化通道（emoji / 形近字 / 拼音）。
7. IF 归一化后的文本与原文完全一致，THEN THE L2_Variant_Normalizer SHALL 跳过基于归一化文本的复检以避免重复。

### Requirement 4: L3 语义层 LLM 研判

**User Story:** 作为审核策略维护者，我希望调用外部 LLM API 对文本进行语义级研判，以便覆盖隐喻、反讽等规则难以处理的违规内容。

#### Acceptance Criteria

1. THE L3_Semantic_Classifier SHALL 通过 HTTPS 调用配置的 LLM API（如 DeepSeek 或通义千问）对输入文本进行分类。
2. THE L3_Semantic_Classifier SHALL 向 LLM 提交一个固定的系统提示词，要求模型输出包含 Risk_Level（0-5）与 Hit_Category 列表的 JSON。
3. WHEN LLM 返回的内容不是合法 JSON 或缺少 Risk_Level 字段，THE L3_Semantic_Classifier SHALL 标记自身状态为 "parse_error" 并返回 Risk_Level 为 0、Hit_Category 为空的兜底结果。
4. THE L3_Semantic_Classifier SHALL 为单次 LLM 调用设置不超过 10 秒的超时时间。
5. IF LLM 调用超时或返回非 2xx HTTP 状态码，THEN THE L3_Semantic_Classifier SHALL 标记自身状态为 "unavailable" 并返回兜底结果。
6. THE L3_Semantic_Classifier SHALL 从环境变量或配置文件读取 LLM API 的密钥与端点，且不得将密钥写入 Audit_Result。

### Requirement 5: L4 决策层综合研判

**User Story:** 作为审核服务调用方，我希望系统综合三层判定结果输出统一的违规等级、命中类别与处置建议，以便直接驱动业务侧动作。

#### Acceptance Criteria

1. THE L4_Decision_Engine SHALL 接收 L1_Rule_Engine、L2_Variant_Normalizer、L3_Semantic_Classifier 三层的判定结果作为输入。
2. THE L4_Decision_Engine SHALL 取 L1、L2、L3 三层各自映射出的 Risk_Level 的最大值作为最终 Risk_Level。
3. THE L4_Decision_Engine SHALL 将 L1、L2、L3 三层产生的 Hit_Category 取并集作为最终 Hit_Category 列表。
4. WHEN L3 状态为 "unavailable" 或 "parse_error"，THE L4_Decision_Engine SHALL 仅基于 L1 与 L2 的结果计算最终 Risk_Level 与 Hit_Category，并在 Audit_Result 中标记 "degraded" 为 true。
5. THE L4_Decision_Engine SHALL 根据最终 Risk_Level 输出对应的 Disposal_Suggestion，映射关系遵循 Requirement 6 中定义的等级表。
6. THE L4_Decision_Engine SHALL 在 Audit_Result 中输出整合后的 Hit_Span 列表，且每个 Hit_Span 必须保留其来源层标识（L1 或 L2）。

### Requirement 6: 违规等级与处置建议映射

**User Story:** 作为审核服务调用方，我希望每个违规等级都有清晰的语义与对应的运营动作，以便在业务侧无需额外判断即可执行处置。

#### Acceptance Criteria

1. THE Audit_Platform SHALL 定义 Risk_Level 取值集合为 {0, 1, 2, 3, 4, 5}，分别对应语义 {合规, 提示, 警告, 折叠, 删除, 封禁}。
2. THE Audit_Platform SHALL 为每个 Risk_Level 定义唯一的 Disposal_Suggestion，对应关系为：0→保留，1→加提示，2→警告用户，3→折叠内容，4→删除内容，5→封禁账号。
3. THE Audit_Platform SHALL 定义 Hit_Category 取值集合为 {涉政, 暴恐, 色情, 广告, 辱骂, 谣言, 隐私泄露, 其他}，并允许一条 Audit_Result 同时命中多个类别。
4. THE Audit_Platform SHALL 在 Sensitive_Lexicon 中为每个词条配置一个 Hit_Category 与一个基础 Risk_Level。
5. WHEN L1_Rule_Engine 命中多个词条，THE L4_Decision_Engine SHALL 取这些词条基础 Risk_Level 的最大值作为 L1 层贡献的 Risk_Level。

### Requirement 7: REST API 单条文本审核接口

**User Story:** 作为系统集成方，我希望通过 HTTP 调用 `/audit/text` 提交一段文本，以便同步获得审核结果。

#### Acceptance Criteria

1. THE Audit_API SHALL 暴露 HTTP POST 端点 `/audit/text`，接收 JSON 请求体，字段为 `text` (string)。
2. WHEN `/audit/text` 收到合法请求，THE Audit_API SHALL 调用 Pipeline 处理文本并以 JSON 形式返回 Audit_Result。
3. THE Audit_API SHALL 在响应中包含字段：`request_id`、`risk_level`、`hit_categories`、`disposal_suggestion`、`hit_spans`、`layer_details`、`degraded`。
4. IF 请求体缺少 `text` 字段或 `text` 不是字符串，THEN THE Audit_API SHALL 返回 HTTP 422 状态码与描述性错误消息。
5. IF `text` 字段长度超过 10000 个字符，THEN THE Audit_API SHALL 返回 HTTP 413 状态码与描述性错误消息。
6. WHEN `text` 为空字符串，THE Audit_API SHALL 返回 Risk_Level 为 0、Hit_Category 为空的合规结果。

### Requirement 8: REST API 批量文本审核接口

**User Story:** 作为系统集成方，我希望通过 `/audit/batch` 一次提交多条文本，以便减少网络往返开销。

#### Acceptance Criteria

1. THE Audit_API SHALL 暴露 HTTP POST 端点 `/audit/batch`，接收 JSON 请求体，字段为 `texts` (string 数组)。
2. WHEN `/audit/batch` 收到合法请求，THE Audit_API SHALL 对数组中的每个元素调用 Pipeline，并按输入顺序返回 Audit_Result 数组。
3. THE Audit_API SHALL 在响应顶层返回 `request_id` 与 `results`，其中 `results` 是与输入顺序一致的 Audit_Result 数组。
4. IF `texts` 数组长度超过 50，THEN THE Audit_API SHALL 返回 HTTP 413 状态码与描述性错误消息。
5. IF 数组中某条文本长度超过 10000 个字符，THEN THE Audit_API SHALL 在对应位置返回带有 `error` 字段的占位结果，而不中断其余条目处理。
6. WHEN `texts` 数组为空，THE Audit_API SHALL 返回 HTTP 200 与空的 `results` 数组。

### Requirement 9: Web 测试控制台

**User Story:** 作为课程演示者，我希望有一个简单的网页可以输入文本并直观看到分级结果，以便在答辩时演示系统能力。

#### Acceptance Criteria

1. THE Web_Console SHALL 提供一个单页页面，包含文本输入框、提交按钮与结果展示区。
2. WHEN 使用者点击提交按钮，THE Web_Console SHALL 调用 `/audit/text` 接口并将返回结果渲染到结果展示区。
3. THE Web_Console SHALL 在结果展示区显示最终 Risk_Level、Disposal_Suggestion 与 Hit_Category 列表。
4. THE Web_Console SHALL 在原文中以高亮样式标记每个 Hit_Span 的位置，并在悬浮或就近位置展示其命中词与所属层。
5. THE Web_Console SHALL 分块展示 L1_Rule_Engine、L2_Variant_Normalizer、L3_Semantic_Classifier 三层的判定明细，包括各层 Risk_Level、命中证据与状态。
6. IF Audit_Result 中 `degraded` 为 true，THEN THE Web_Console SHALL 在结果区显示降级提示，说明 L3 不可用。
7. IF Audit_API 返回非 2xx 状态码，THEN THE Web_Console SHALL 在结果区显示错误消息并保留输入文本。

### Requirement 10: 配置与本地部署

**User Story:** 作为课程演示者，我希望系统可以在本地一键启动，以便答辩环境无需复杂依赖。

#### Acceptance Criteria

1. THE Audit_Platform SHALL 支持通过单条命令启动 Audit_API 服务，并默认监听本地端口。
2. THE Audit_Platform SHALL 从配置文件或环境变量加载 Sensitive_Lexicon 路径、形近字字典路径、LLM API 端点与密钥。
3. THE Audit_Platform SHALL 使用 SQLite 作为本地存储后端，存储 Sensitive_Lexicon 词条与可选的审核记录。
4. WHEN 启动时配置文件缺失或必填字段未提供，THE Audit_Platform SHALL 输出描述性错误日志并以非零退出码终止。
5. THE Web_Console SHALL 由 Audit_API 同进程提供静态资源服务，无需额外启动前端服务即可访问。
