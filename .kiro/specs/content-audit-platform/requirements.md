# Requirements Document

## Introduction

内容安全审核平台（Content Audit Platform）是一个面向中文文本的轻量级内容审核原型，模拟阿里云内容安全 / 网易易盾等商业审核服务的核心能力。平台由三个核心模块构成：

1. **多策略审核流水线**：L1 规则层（敏感词 + 正则）、L2 变体识别层（拼音 / 谐音 / 形近 / 干扰符 / 空白干扰）、L3 LLM 语义层（DeepSeek）、L4 决策融合层。
2. **内容分级与处置建议**：4 级风险（合规 / 提示 / 警告 / 违规）+ 6 类违规标签 + 结构化处置建议。
3. **REST API + Web 测试控制台**：单条 / 批量审核接口 + 可交互前端控制台 + 敏感词库管理 + 历史记录。

技术栈：Python + FastAPI + SQLite（后端），纯静态 HTML + Tailwind CSS + Alpine.js（前端），DeepSeek API（L3 语义层）。仅审核中文内容。

本文档面向三类用户：
- **API 接入开发者（API_Consumer）**：通过 REST API 集成审核能力。
- **平台运营人员（Platform_Operator）**：管理敏感词库、查看历史。
- **演示查看者（Demo_Viewer）**：通过 Web 控制台体验审核效果。

## Glossary

- **Audit_Platform**：本平台整体系统，提供中文内容审核能力的服务集合。
- **Audit_Pipeline**：四层审核流水线（L1 → L2 → L3 → L4）的统称。
- **L1_Rule_Engine**：第一层审核引擎，基于 Aho-Corasick 多模式匹配的敏感词扫描和正则规则匹配。
- **L2_Variant_Engine**：第二层变体识别引擎，识别拼音化、谐音字、形近字、表情/特殊符号插入、空白/换行干扰等 5 种规避手段。
- **L3_Semantic_Engine**：第三层语义审核引擎，调用 DeepSeek LLM API 进行语义级判别。
- **L4_Decision_Fusion**：第四层决策融合层，综合 L1/L2/L3 三层结果输出最终分级与类别。
- **Risk_Level**：风险等级，取值为 `合规`、`提示`、`警告`、`违规` 四档。
- **Violation_Category**：违规类别，取值为 `涉政`、`暴恐`、`色情`、`辱骂`、`违法广告`、`其他` 六类。
- **Disposal_Suggestion**：处置建议，包含 `平台动作`、`用户提示文案`、`运营备注` 三个结构化字段。
- **Platform_Action**：平台动作，取值为 `pass`、`fold`、`delete`、`block`、`manual_review` 等枚举。
- **Sensitive_Word_Library**：敏感词库，包含开源初始词库和用户自定义词条，每条记录附带类别与等级元数据。
- **Custom_Word_Entry**：用户在管理界面添加的自定义敏感词记录，必须包含 `词条文本`、`违规类别`、`违规等级` 三个字段。
- **Audit_Record**：一次审核请求的完整持久化记录，包含输入文本、各层结果、最终结论、时间戳等。
- **REST_API**：基于 HTTP 的对外审核接口集合，包括单条审核、批量审核、词库管理、历史查询。
- **Web_Console**：纯静态前端测试控制台，包含单条审核、批量审核、历史记录、敏感词管理四个 Tab。
- **Confidence_Score**：审核结论的置信度分数，取值范围 [0.0, 1.0]。
- **Layer_Score**：单层（L1/L2/L3）独立给出的风险分数，取值范围 [0.0, 1.0]。
- **Hit_Detail**：命中详情，记录命中所在层、命中词或片段、原文位置、命中类别。
- **Pinyin_Matcher**：L2 中的拼音匹配子组件，将文本转拼音后匹配敏感词拼音序列。
- **Homophone_Matcher**：L2 中的谐音字匹配子组件，基于谐音字典将变体还原后匹配。
- **Glyph_Matcher**：L2 中的形近字匹配子组件，基于形近字典还原后匹配。
- **Symbol_Stripper**：L2 中的表情/特殊符号剔除子组件。
- **Whitespace_Stripper**：L2 中的空白与换行剔除子组件。

## Requirements

### Requirement 1: L1 规则审核层

**User Story:** 作为 API 接入开发者，我希望平台对输入文本进行高速敏感词与正则匹配，以便在毫秒级内识别明文违规内容。

#### Acceptance Criteria

1. WHEN 长度在 1 至 10000 个中文字符之间的文本被提交至 L1_Rule_Engine，THE L1_Rule_Engine SHALL 使用 Aho-Corasick 多模式匹配算法对当前配置的敏感词库进行一次完整扫描。
2. WHEN L1_Rule_Engine 完成扫描，THE L1_Rule_Engine SHALL 返回所有命中词条的列表，每条记录包含命中词、起始位置（从 0 起的整数偏移）、结束位置（整数偏移，区间右开）、违规类别（涉政、暴恐、色情、辱骂、违法广告、其他六个枚举值之一）、违规等级（合规、提示、警告、违规四个枚举值之一）。
3. THE L1_Rule_Engine SHALL 支持配置正则表达式规则集，对手机号、URL、QQ 号、微信号等结构化模式进行匹配，单次扫描所加载的正则规则总数不超过 500 条。
4. WHEN 输入文本长度不超过 2000 个中文字符且当前敏感词库规模不超过 100000 条，THE L1_Rule_Engine SHALL 在 100 毫秒内完成扫描并返回结果。
5. THE L1_Rule_Engine SHALL 输出 0.0 到 1.0 之间的 L1_Layer_Score，其值随命中条目数量增加单调非递减，且在存在至少一个等级为 `违规` 的命中时不低于 0.85，在最高命中等级为 `警告` 时不低于 0.50 且不高于 0.85，在最高命中等级为 `提示` 时不低于 0.20 且不高于 0.50。
6. IF 输入文本为空字符串或为 null，THEN THE L1_Rule_Engine SHALL 返回空命中列表且 L1_Layer_Score 为 0.0。
7. IF 输入文本长度超过 10000 个中文字符，THEN THE L1_Rule_Engine SHALL 拒绝执行扫描并返回输入超长的错误指示，且不输出命中列表与 L1_Layer_Score。

### Requirement 2: L2 变体识别层

**User Story:** 作为 API 接入开发者，我希望平台能够识别经过常见变形手段规避的敏感内容，以便提升对抗对抗性输入的能力。

#### Acceptance Criteria

1. THE L2_Variant_Engine SHALL 实现以下 5 种变体识别技术：拼音化匹配、谐音字替换、形近字替换、表情/特殊符号插入、空白与换行干扰。
2. WHEN 输入文本在敏感词字符位置上将至少 50% 的字符替换为对应汉字的拼音（含全拼或首字母缩写），THE Pinyin_Matcher SHALL 通过将文本转换为拼音序列后与敏感词拼音序列比对的方式识别该变体；多音字按敏感词的官方读音匹配。
3. WHEN 输入文本将敏感词字符替换为同音或近音的汉字，THE Homophone_Matcher SHALL 基于内置谐音字典将谐音字还原后再与敏感词库匹配。
4. WHEN 输入文本将敏感词字符替换为字形相近的汉字（如 `日` ↔ `曰`），THE Glyph_Matcher SHALL 基于内置形近字字典将形近字还原后再与敏感词库匹配。
5. WHEN 输入文本在敏感词字符之间插入表情符号、`*`、`#` 等非汉字非字母数字字符，THE Symbol_Stripper SHALL 在匹配前剔除这些非汉字非字母数字字符（保留中文与字母数字）再进行敏感词比对。
6. WHEN 输入文本在敏感词字符之间插入空格、全角空格、制表符或换行符等空白字符，THE Whitespace_Stripper SHALL 在匹配前剔除全部 Unicode 空白字符再进行敏感词比对。
7. WHEN L2_Variant_Engine 命中变体内容，THE L2_Variant_Engine SHALL 在 Hit_Detail 中记录命中所用的变体识别技术名称（pinyin / homophone / glyph / symbol / whitespace 之一）、还原后的命中词以及在原文中的起止位置（0 起整数偏移、区间右开）。
8. THE L2_Variant_Engine SHALL 输出 0.0 到 1.0 之间的 L2_Layer_Score；当未命中任何变体时输出 0.00；当仅由空白或符号干扰命中时输出 0.60；当由拼音、谐音或形近字命中时输出 0.90。多种技术同时命中取最大值。
9. WHEN 输入文本长度不超过 2000 个中文字符，THE L2_Variant_Engine SHALL 在 500 毫秒内完成全部 5 种变体识别。
10. IF 输入文本长度超过 2000 个中文字符，THEN THE L2_Variant_Engine SHALL 仅对前 2000 个字符执行变体识别，并在 Hit_Detail 中标注 `truncated` 状态。
11. IF 输入文本为空字符串或仅由空白字符组成，THEN THE L2_Variant_Engine SHALL 跳过 5 种变体识别，返回空命中列表且 L2_Layer_Score 为 0.0。

### Requirement 3: L3 LLM 语义审核层

**User Story:** 作为 API 接入开发者，我希望平台具备语义级理解能力，以便识别没有显性敏感词但存在隐性违规倾向的内容。

#### Acceptance Criteria

1. WHEN 文本进入 L3_Semantic_Engine，THE L3_Semantic_Engine SHALL 调用 DeepSeek API 以预设的审核 Prompt 模板进行推理，且单次单条审核请求最多调用一次 DeepSeek API。
2. THE L3_Semantic_Engine SHALL 要求 DeepSeek 返回结构化 JSON，包含 `risk_level`（取值必须为 `合规`/`提示`/`警告`/`违规` 之一）、`category`（取值必须为 `涉政`/`暴恐`/`色情`/`辱骂`/`违法广告`/`其他`/`合规` 之一）、`reason`（中文推理说明）、`score`（0.0–1.0 风险分）四个字段。
3. WHEN DeepSeek 返回符合 schema 的结果，THE L3_Semantic_Engine SHALL 将 `score` 作为 L3_Layer_Score、`reason` 作为 LLM_Explanation 输出，并将 `reason` 在超过 1000 字符时截断至前 1000 字符并附 `...` 截断标记。
4. WHEN L3_Semantic_Engine 调用 DeepSeek API，THE L3_Semantic_Engine SHALL 在 10 秒内返回结果或判定为超时。
5. IF DeepSeek API 返回 HTTP 错误、连接超时、读取超时、非合法 JSON 或缺失任一必需字段，THEN THE L3_Semantic_Engine SHALL 将 L3_Layer_Score 设为 0.0、LLM_Explanation 设为对应错误描述（错误类型 + 简要原因），并在 Hit_Detail 中标注 `l3_error` 状态。
6. IF DeepSeek 返回的 `risk_level` 或 `category` 字段值不在 Requirement 3.2 列出的合法枚举内，THEN THE L3_Semantic_Engine SHALL 视为格式错误并按 Requirement 3.5 处理。

### Requirement 4: L4 决策融合层

**User Story:** 作为 API 接入开发者，我希望平台对三层结果进行融合输出统一结论，以便我无需自行处理多层冲突。

#### Acceptance Criteria

1. WHEN L1、L2、L3 三层均在 5 秒内完成审核并返回结果，THE L4_Decision_Fusion SHALL 在收到最后一层结果后 200 毫秒内综合三层 Layer_Score 与命中类别，输出最终的 Risk_Level 和 Violation_Category。
2. THE L4_Decision_Fusion SHALL 使用以下分数阈值规则将三层 Layer_Score 的最大值（max_score）映射为 Risk_Level：max_score ≥ 0.85 输出 `违规`；0.5 ≤ max_score < 0.85 输出 `警告`；0.2 ≤ max_score < 0.5 输出 `提示`；max_score < 0.2 输出 `合规`。
3. THE L4_Decision_Fusion SHALL 对最终 Risk_Level 进行单调性约束：在其他两层 Layer_Score 与命中类别不变时，任一层 Layer_Score 严格增大（`>`）SHALL NOT 导致最终 Risk_Level 降低。
4. WHEN 多个层级命中不同 Violation_Category，THE L4_Decision_Fusion SHALL 选择 Layer_Score 最高的层级所对应的类别作为最终 Violation_Category；若多个层级 Layer_Score 相等，THE L4_Decision_Fusion SHALL 按 L3 > L2 > L1 的固定优先级选择对应类别。
5. THE L4_Decision_Fusion SHALL 输出 0.0 到 1.0 之间（含端点）的最终 Confidence_Score，且 Confidence_Score 不小于三层 Layer_Score 的最大值。
6. IF 三层全部判为合规（即三层 Layer_Score 均 < 0.2），THEN THE L4_Decision_Fusion SHALL 输出 Risk_Level 为 `合规`，Violation_Category 为空字符串，Confidence_Score 不低于 0.8 且不大于 1.0。
7. WHEN L4_Decision_Fusion 完成融合，THE L4_Decision_Fusion SHALL 在结果中完整保留 L1、L2、L3 各自的 Layer_Score 与 Hit_Detail，三层原始信息均不得为空或被截断。
8. IF L1、L2、L3 中任一层在 5 秒内未返回结果或返回错误，THEN THE L4_Decision_Fusion SHALL 仅基于其余已完成层的 Layer_Score 与命中类别按相同规则进行融合，在结果中将缺失层的 Layer_Score 与 Hit_Detail 标记为不可用，并将最终 Confidence_Score 限制为不超过 0.7。

### Requirement 5: 内容分级体系

**User Story:** 作为平台运营人员，我希望审核结果按统一的 4 级分级体系输出，以便对接下游的处置流程。

#### Acceptance Criteria

1. THE Audit_Platform SHALL 将所有审核结论的 Risk_Level 字段限定为以下 4 档枚举值之一，且互斥不可并存：`合规`、`提示`、`警告`、`违规`。
2. THE Audit_Platform SHALL 按以下含义解释 4 档分级：`合规` 表示无风险且可直接放行；`提示` 表示存在轻微风险但可放行并附风险标记；`警告` 表示存在明显风险需要折叠或转人工复核；`违规` 表示严重违规需要拦截或删除。
3. WHEN 一次审核未命中任何 L1 关键词、未命中任何 L2 关键词且 L3_Layer_Score 在 0.00 至 0.20（含）区间，THE Audit_Platform SHALL 输出 Risk_Level 为 `合规`。
4. WHEN 一次审核仅命中 L3 层级且最终 Confidence_Score 在 0.20（不含）至 0.50（不含）区间，THE Audit_Platform SHALL 输出 Risk_Level 为 `提示`。
5. WHEN 一次审核命中 L1 或 L2 层级且最终 Confidence_Score 在 0.50（含）至 0.85（不含）区间，THE Audit_Platform SHALL 输出 Risk_Level 为 `警告`。
6. WHEN 一次审核任一层级命中且最终 Confidence_Score 不低于 0.85（取值范围 0.00 至 1.00），THE Audit_Platform SHALL 输出 Risk_Level 为 `违规`。
7. IF 同一次审核同时满足多档分级条件，THEN THE Audit_Platform SHALL 按 `违规` > `警告` > `提示` > `合规` 的优先级取最高一档作为最终 Risk_Level。
8. IF 审核过程因评分缺失或异常无法判定 Risk_Level，THEN THE Audit_Platform SHALL 将 Risk_Level 默认置为 `警告` 并附带分级失败的错误标识，且不得返回 4 档枚举之外的值。

### Requirement 6: 违规类别标签

**User Story:** 作为平台运营人员，我希望违规内容按统一的 6 类标签输出，以便进行分类统计与差异化处置。

#### Acceptance Criteria

1. IF 一次审核结论的 Risk_Level 不为 `合规`，THEN THE Audit_Platform SHALL 将 Violation_Category 限定为以下 6 类枚举值之一：`涉政`、`暴恐`、`色情`、`辱骂`、`违法广告`、`其他`。
2. THE Sensitive_Word_Library 中每个词条 SHALL 标注一个属于上述 6 类枚举的 Violation_Category，且不允许为空或超出枚举范围。
3. WHEN L1_Rule_Engine 或 L2_Variant_Engine 命中一个敏感词，THE Audit_Platform SHALL 将该敏感词标注的 Violation_Category 作为该次命中的类别，并写入 Hit_Detail。
4. WHEN 一次审核存在多个命中且类别不一致，THE L4_Decision_Fusion SHALL 按 Requirement 4 的融合规则选取唯一最终 Violation_Category，并在 Hit_Detail 中完整保留每个命中的原始信息（含命中引擎、命中词、原始类别）。
5. IF 一次审核结论的 Risk_Level 为 `合规`，THEN THE Audit_Platform SHALL 输出 Violation_Category 为空字符串，且 Hit_Detail 中不包含任何带类别的命中条目。
6. IF L3_Semantic_Engine 返回的 `category` 缺失、为空或超出 6 类枚举范围，THEN THE Audit_Platform SHALL 将该次命中的类别回退为 `其他`。

### Requirement 7: 结构化处置建议

**User Story:** 作为 API 接入开发者，我希望审核响应包含可直接驱动下游处置的结构化建议，以便减少集成方的二次决策。

#### Acceptance Criteria

1. THE Audit_Platform SHALL 在每次审核响应中返回 Disposal_Suggestion，包含 `platform_action`、`user_message`、`operation_note` 三个字段，且每个字段去除首尾空白后长度均大于 0。
2. THE Disposal_Suggestion.platform_action SHALL 取值于以下枚举之一：`pass`、`fold`、`delete`、`block`、`manual_review`，不允许返回枚举外的任何值。
3. IF Risk_Level 为 `合规`，THEN THE Audit_Platform SHALL 设置 Disposal_Suggestion.platform_action 为 `pass`。
4. IF Risk_Level 为 `违规` 且 Violation_Category 属于 `涉政`、`暴恐`、`色情` 三类之一，THEN THE Audit_Platform SHALL 设置 Disposal_Suggestion.platform_action 为 `block`；IF Risk_Level 为 `违规` 且 Violation_Category 属于其余类别，THEN THE Audit_Platform SHALL 设置 Disposal_Suggestion.platform_action 为 `delete`。
5. IF Risk_Level 为 `警告`，THEN THE Audit_Platform SHALL 设置 Disposal_Suggestion.platform_action 为 `fold` 或 `manual_review`；IF Risk_Level 为 `提示`，THEN THE Audit_Platform SHALL 设置 Disposal_Suggestion.platform_action 为 `pass` 或 `fold`。
6. THE Disposal_Suggestion.user_message SHALL 为面向终端用户的中文提示文案，长度范围 1–100 个 Unicode 码点，且不得包含命中的具体敏感词或内部规则名。
7. THE Disposal_Suggestion.operation_note SHALL 为面向运营人员的中文备注，长度范围 1–500 个 Unicode 码点，必须包含本次审核的最终 Violation_Category、Risk_Level 以及触发处置的关键命中词或片段。
8. IF Audit_Platform 因内部错误无法生成符合上述规则的处置建议，THEN THE Audit_Platform SHALL 将 platform_action 回退为 `manual_review`，并在 operation_note 中说明回退原因。

### Requirement 8: 单条文本审核 API

**User Story:** 作为 API 接入开发者，我希望通过 REST API 提交单条文本进行审核，以便集成到自己的业务系统中。

#### Acceptance Criteria

1. THE Audit_Platform SHALL 提供 HTTP POST 接口 `/audit/text`，接收 Content-Type 为 `application/json` 的请求体 `{ "text": "<待审核中文文本>" }`。
2. IF `/audit/text` 接收的 `text` 字段长度超过 2000 个字符（按 Unicode 码点计数），THEN THE Audit_Platform SHALL 返回 HTTP 400 状态码及指明文本长度超出 2000 字符上限的错误信息，且不写入 Audit_Record。
3. IF 请求体不是合法 JSON、缺少 `text` 字段、`text` 字段类型不为字符串或为空字符串（长度为 0），THEN THE Audit_Platform SHALL 返回 HTTP 400 状态码及指明字段校验失败原因的错误信息，且不写入 Audit_Record。
4. WHEN `/audit/text` 处理成功（L1、L2、L3 三层均完成且未发生异常），THE Audit_Platform SHALL 返回 HTTP 200 状态码及 JSON 响应体，包含以下字段：`risk_level`、`violation_category`、`confidence_score`、`l1_score`、`l2_score`、`l3_score`、`hit_details`、`llm_explanation`、`disposal_suggestion`、`processing_time`（包含 `l1_ms`、`l2_ms`、`l3_ms`、`total_ms` 四个子字段）。
5. WHEN `/audit/text` 处理一条长度在 1 至 2000 字符之间的合法文本，THE Audit_Platform SHALL 在收到请求后 5000 毫秒内返回响应。
6. WHEN `/audit/text` 处理成功，THE Audit_Platform SHALL 在向调用方返回响应前将本次审核作为一条 Audit_Record 写入 SQLite 持久化存储。
7. IF `/audit/text` 在 L1、L2 或 L3 任一处理层发生不可恢复异常（L3 超时按 Requirement 3.5 兜底处理，不视为不可恢复异常），THEN THE Audit_Platform SHALL 返回 HTTP 500 状态码及指明内部处理失败的错误信息。
8. IF `/audit/text` 处理已完成但写入 SQLite Audit_Record 失败，THEN THE Audit_Platform SHALL 返回 HTTP 500 状态码及指明持久化失败的错误信息，且响应体不包含审核结果字段。

### Requirement 9: 批量文本审核 API

**User Story:** 作为 API 接入开发者，我希望通过单次请求审核多条文本，以便提升集成时的吞吐效率。

#### Acceptance Criteria

1. THE Audit_Platform SHALL 提供 HTTP POST 接口 `/audit/batch`，接收 Content-Type 为 `application/json` 的请求体 `{ "texts": ["<文本1>", "<文本2>", ...] }`，其中 `texts` 必须为字符串数组。
2. THE `/audit/batch` 接口 SHALL 限制单次请求中 `texts` 数组长度在 1 至 50 之间（含端点）。
3. IF `/audit/batch` 请求中 `texts` 数组为空（长度为 0）或长度超过 50，THEN THE Audit_Platform SHALL 返回 HTTP 400 状态码及说明 `batch size out of range (1..50)` 的错误信息，且不写入任何 Audit_Record。
4. IF `/audit/batch` 请求体不是合法 JSON、缺少 `texts` 字段、`texts` 字段类型不为数组或数组中存在非字符串元素，THEN THE Audit_Platform SHALL 返回 HTTP 400 状态码及指明字段校验失败原因的错误信息，且不写入任何 Audit_Record。
5. IF `/audit/batch` 请求中任一文本长度超过 2000 个字符（按 Unicode 码点计数），THEN THE Audit_Platform SHALL 返回 HTTP 400 状态码及包含越界文本索引的错误信息，且不写入任何 Audit_Record。
6. WHEN `/audit/batch` 处理成功，THE Audit_Platform SHALL 返回 HTTP 200 状态码及 JSON 响应体 `{ "results": [<审核结果1>, <审核结果2>, ...] }`，其中每个审核结果的字段结构与 Requirement 8.4 中 `/audit/text` 响应一致。
7. THE `/audit/batch` 响应中的 `results` 数组顺序 SHALL 与请求 `texts` 数组顺序一一对应。
8. WHEN `/audit/batch` 处理成功，THE Audit_Platform SHALL 在向调用方返回响应前将每一条文本作为独立的 Audit_Record 写入 SQLite 持久化存储；IF 任一条记录的写入失败，THEN THE Audit_Platform SHALL 回滚本次批量的所有写入并返回 HTTP 500 状态码。
9. WHEN `/audit/batch` 处理一个 50 条以内的合法批量请求，THE Audit_Platform SHALL 在收到请求后 30000 毫秒内返回响应。

### Requirement 10: 敏感词库管理 API

**User Story:** 作为平台运营人员，我希望通过 API 管理自定义敏感词库，以便在不重启服务的前提下扩展审核规则。

#### Acceptance Criteria

1. WHEN Audit_Platform 首次启动，THE Audit_Platform SHALL 从公开开源词库（参考 GitHub 上 TextFilter 或 sensitive-stop-words 类项目）导入不少于 1000 条敏感词作为 Sensitive_Word_Library 的初始数据，并将每条词条的 `word`、`category`、`level`、`source`（标记为 `builtin`）、`created_at` 字段持久化至 SQLite。
2. THE Audit_Platform SHALL 提供 HTTP POST 接口 `/words` 用于新增 Custom_Word_Entry，请求体包含 `word`、`category`、`level` 三个必填字段；处理成功时返回 HTTP 201 状态码及新建词条的 `id`。
3. THE Audit_Platform SHALL 提供 HTTP GET 接口 `/words` 用于查询词库列表，支持按 `category`、`level` 进行过滤，支持 `page`（默认 1）、`page_size`（默认 20，最大 100）参数分页，响应包含 `total`、`page`、`page_size`、`items` 四个字段。
4. WHEN HTTP DELETE 请求 `/words/{id}` 被处理成功，THE Audit_Platform SHALL 返回 HTTP 204 状态码并从 SQLite 中移除该 Custom_Word_Entry。
5. IF 新增 Custom_Word_Entry 时 `category` 不属于 6 类违规类别，THEN THE Audit_Platform SHALL 返回 HTTP 400 状态码及类别非法的错误信息，并 SHALL NOT 将该词条写入 SQLite。
6. IF 新增 Custom_Word_Entry 时 `level` 不属于 4 档风险等级，THEN THE Audit_Platform SHALL 返回 HTTP 400 状态码及等级非法的错误信息，并 SHALL NOT 将该词条写入 SQLite。
7. WHEN 一条 Custom_Word_Entry 被新增或删除，THE Audit_Platform SHALL 在 1 秒内令该变更对后续所有 `/audit/text` 与 `/audit/batch` 请求生效。
8. THE Audit_Platform SHALL 将所有 Custom_Word_Entry 持久化在 SQLite 中，至少包含 `id`、`word`、`category`、`level`、`source`、`created_at` 字段。
9. IF 新增 Custom_Word_Entry 时 `word` 字段缺失、为空字符串、仅含空白字符或长度超过 64 个 Unicode 码点，THEN THE Audit_Platform SHALL 返回 HTTP 400 状态码及指明 `word` 字段非法的错误信息，并 SHALL NOT 将该词条写入 SQLite。
10. IF DELETE `/words/{id}` 中的 `id` 在 SQLite 中不存在，THEN THE Audit_Platform SHALL 返回 HTTP 404 状态码及指明词条不存在的错误信息，且不修改 SQLite 中任何记录。

### Requirement 11: 历史记录查询 API

**User Story:** 作为平台运营人员，我希望按维度查询历史审核记录，以便回顾审核轨迹和分析问题。

#### Acceptance Criteria

1. THE Audit_Platform SHALL 提供 HTTP GET 接口 `/history` 用于查询 Audit_Record 列表，结果按 `created_at` 倒序排列。
2. THE `/history` 接口 SHALL 支持以下查询参数：`risk_level`（取值必须为 4 档枚举之一）、`category`（取值必须为 6 类枚举之一）、`start_time`（ISO 8601 时间格式）、`end_time`（ISO 8601 时间格式）、`page`（默认 1，正整数）、`page_size`（默认 20，最大 100）。
3. WHEN `/history` 请求成功，THE Audit_Platform SHALL 返回 HTTP 200 状态码及包含 `total`（总条数）、`page`、`page_size`、`items`（当前页记录数组）四个字段的 JSON 响应，并在 1 秒内返回。
4. THE `/history` 返回的每条 Audit_Record SHALL 包含审核 ID、原文、最终 Risk_Level、Violation_Category、Confidence_Score、各层 Layer_Score、Hit_Detail 摘要、创建时间。
5. IF `start_time` 严格晚于 `end_time`，THEN THE Audit_Platform SHALL 返回 HTTP 400 状态码及时间区间非法的错误信息；当 `start_time` 等于 `end_time` 时，THE Audit_Platform SHALL 视为合法查询并返回该时刻的记录。
6. IF `risk_level`、`category`、`start_time`、`end_time`、`page`、`page_size` 中任一参数取值不在合法枚举或合法格式范围内，THEN THE Audit_Platform SHALL 返回 HTTP 400 状态码及指明参数非法的错误信息。
7. WHEN `/history` 查询结果在指定筛选条件下为空，THE Audit_Platform SHALL 返回 HTTP 200 状态码，`total` 为 0，`items` 为空数组。

### Requirement 12: Web 控制台 - 单条审核 Tab

**User Story:** 作为演示查看者，我希望通过 Web 控制台体验单条文本审核效果，以便直观理解平台能力。

#### Acceptance Criteria

1. THE Web_Console SHALL 提供 `单条审核` Tab，包含一个最多输入 2000 字符的中文文本输入框、一个实时显示当前字符计数的指示器和一个 `提交审核` 按钮。
2. IF 用户在 `单条审核` Tab 提交时输入框为空或字符数超过 2000，THEN THE Web_Console SHALL 在客户端阻止提交并显示对应的提示信息，保留输入内容不清空。
3. WHEN 用户在 `单条审核` Tab 点击 `提交审核` 按钮，THE Web_Console SHALL 调用 `/audit/text` 接口，在等待响应期间禁用提交按钮并显示加载状态指示，并在收到响应后展示返回结果。
4. WHEN `/audit/text` 返回结果，THE Web_Console SHALL 在结果区域以带颜色区分的徽章形式显示最终 Risk_Level；当 Violation_Category 为空字符串时显示 `合规` 标签，否则以标签形式显示 Violation_Category。
5. WHEN `/audit/text` 返回结果包含至少一条 Hit_Detail，THE Web_Console SHALL 在原文展示区将所有命中片段以高亮颜色标出，并在 Tooltip 中显示命中所在层（L1/L2/L3）与命中词；若 Hit_Detail 为空数组，则原文展示区不进行任何高亮。
6. WHEN `/audit/text` 返回结果，THE Web_Console SHALL 渲染一个雷达图，三个轴分别为 L1_Score、L2_Score、L3_Score，每个轴的取值范围为 0 至 1；缺失的层分数按 0 渲染。
7. WHEN `/audit/text` 返回结果，THE Web_Console SHALL 在独立的展示区分别显示 LLM_Explanation 文本和 Disposal_Suggestion 的三个字段（platform_action、user_message、operation_note）。
8. IF `/audit/text` 接口调用失败、响应超过 10 秒未返回或返回非 200 状态码，THEN THE Web_Console SHALL 显示对应的错误提示信息，恢复提交按钮可用状态，且保留用户输入内容不清空。

### Requirement 13: Web 控制台 - 批量审核 Tab

**User Story:** 作为演示查看者，我希望通过 Web 控制台体验批量文本审核效果，以便快速评估平台对多条内容的处理能力。

#### Acceptance Criteria

1. THE Web_Console SHALL 提供 `批量审核` Tab，支持通过粘贴多行文本（每行一条，单行最多 2000 字符）或上传 UTF-8 编码的 `.txt` 文件（每行一条，文件大小不超过 1 MB）的方式输入待审核文本集合，且在解析时忽略空行与首尾空白字符。
2. WHEN 用户在 `批量审核` Tab 提交批量请求，THE Web_Console SHALL 调用 `/audit/batch` 接口，在等待响应期间显示加载状态指示，并在收到响应后以表格形式展示每一条结果。
3. THE 批量结果表格 SHALL 包含以下列：序号（从 1 开始连续编号，与提交顺序一致）、原文摘要（原文超过 50 字符时截断至前 50 字符并以省略号 `...` 结尾）、Risk_Level、Violation_Category、Confidence_Score、操作（查看详情）。
4. WHEN 用户点击表格中某行的 `查看详情`，THE Web_Console SHALL 弹出与单条审核结果展示一致的详情面板，包含雷达图、命中高亮、LLM_Explanation 和 Disposal_Suggestion 四项内容。
5. IF 用户提交时输入的有效文本数量超过 50 条或为 0 条，THEN THE Web_Console SHALL 在客户端阻止提交，并分别显示 `单次批量不超过 50 条` 或 `请至少输入一条待审核文本` 的提示，同时保留用户输入内容不清空。
6. IF `/audit/batch` 接口调用失败、响应超过 30 秒未返回或返回非 200 状态码，THEN THE Web_Console SHALL 显示错误提示信息说明失败原因类别，保留用户输入内容不清空，并提供重新提交入口。

### Requirement 14: Web 控制台 - 历史记录 Tab

**User Story:** 作为平台运营人员，我希望通过 Web 控制台浏览审核历史，以便快速排查问题与回看审核记录。

#### Acceptance Criteria

1. THE Web_Console SHALL 提供 `历史记录` Tab，默认展示最近 30 天内的 Audit_Record 列表（按创建时间倒序，每页 20 条），并在 1 秒内完成加载。
2. THE `历史记录` Tab SHALL 提供按 Risk_Level（4 档枚举下拉）、Violation_Category（6 类枚举下拉）、起止时间（日期时间选择器）进行过滤的筛选控件，时间区间最长不超过 90 天。
3. WHEN 用户在 `历史记录` Tab 修改任一筛选条件，THE Web_Console SHALL 调用 `/history` 接口并刷新列表。
4. THE `历史记录` 列表 SHALL 展示每条记录的创建时间（精确到秒）、原文摘要（超过 50 字符时截断并以 `...` 结尾）、Risk_Level 徽章、Violation_Category 标签、Confidence_Score（保留两位小数）。
5. WHEN 用户点击列表中某条记录，THE Web_Console SHALL 展示该 Audit_Record 的完整详情，包含各层 Layer_Score、Hit_Detail、LLM_Explanation、Disposal_Suggestion。
6. IF `/history` 接口调用失败、响应超过 5 秒未返回或返回非 200 状态码，THEN THE Web_Console SHALL 显示对应的错误提示信息，保留当前筛选条件不重置。
7. IF 用户设置的起止时间区间起始时间晚于结束时间或区间跨度超过 90 天，THEN THE Web_Console SHALL 在客户端阻止查询并显示对应提示。
8. WHEN `/history` 接口返回的 `items` 为空数组，THE Web_Console SHALL 在列表区显示空状态提示文案。

### Requirement 15: Web 控制台 - 敏感词管理 Tab

**User Story:** 作为平台运营人员，我希望通过 Web 控制台增删自定义敏感词，以便在演示环境中快速调整审核规则。

#### Acceptance Criteria

1. THE Web_Console SHALL 提供 `敏感词管理` Tab，分页展示当前 Sensitive_Word_Library 中的全部 Custom_Word_Entry 列表，每页最多 50 条。
2. THE `敏感词管理` 列表 SHALL 包含每条词条的词条文本、Violation_Category、Risk_Level、来源（`开源初始` 对应 builtin / `用户自定义` 对应 custom）、创建时间、操作（删除）。
3. THE `敏感词管理` Tab SHALL 提供新增词条的表单，包含 `词条文本`（1–64 个 Unicode 码点的非空字符串）、`违规类别`（6 类下拉）、`违规等级`（4 档下拉）三个必填输入项。
4. IF 用户在新增表单中提交的 `词条文本` 为空、仅含空白字符或长度超过 64 字符，THEN THE Web_Console SHALL 在客户端阻止提交并显示对应的字段校验提示。
5. WHEN 用户在 `敏感词管理` Tab 提交合法的新增词条，THE Web_Console SHALL 调用 `/words` POST 接口并在收到 201 响应后刷新列表。
6. IF `/words` POST 接口调用失败、响应超过 5 秒未返回或返回非 201 状态码，THEN THE Web_Console SHALL 显示对应的错误提示信息，保留表单内容不清空。
7. WHEN 用户在 `敏感词管理` Tab 点击某条词条的 `删除` 按钮，THE Web_Console SHALL 弹出二次确认对话框，仅在用户确认后调用 `/words/{id}` DELETE 接口并在收到 204 响应后从列表中移除该项。
8. IF `/words/{id}` DELETE 接口调用失败、响应超过 5 秒未返回或返回非 204 状态码，THEN THE Web_Console SHALL 显示对应的错误提示信息，且不从列表中移除任何条目。
9. THE `敏感词管理` Tab SHALL 支持按 Violation_Category、Risk_Level 单独或组合过滤，并提供清除全部过滤条件的快捷入口。

### Requirement 16: 数据持久化与存储

**User Story:** 作为平台运营人员，我希望审核数据与词库数据持久化，以便服务重启后数据不丢失。

#### Acceptance Criteria

1. THE Audit_Platform SHALL 使用 SQLite 作为唯一持久化存储后端。
2. THE Audit_Platform SHALL 维护以下数据表：`audit_records`（审核记录）、`sensitive_words`（敏感词库），并对其进行结构定义与索引创建。
3. THE `audit_records` 表 SHALL 包含字段：`id`（主键，非空）、`text`（非空）、`risk_level`（非空，4 档枚举之一）、`violation_category`（6 类枚举之一或空字符串）、`confidence_score`（非空，0.0–1.0）、`l1_score`、`l2_score`、`l3_score`、`hit_details_json`、`llm_explanation`、`disposal_suggestion_json`、`processing_time_json`、`created_at`（非空）。
4. THE `sensitive_words` 表 SHALL 包含字段：`id`（主键，非空）、`word`（非空，1–64 个 Unicode 码点）、`category`（非空，6 类枚举之一）、`level`（非空，4 档枚举之一）、`source`（取值 `builtin` 或 `custom`）、`created_at`（非空），且 `(word, source)` 组合唯一。
5. WHEN Audit_Platform 启动且 `sensitive_words` 表为空，THE Audit_Platform SHALL 在启动后 30 秒内自动从内置初始词库文件导入数据并将 `source` 标记为 `builtin`。
6. IF 内置初始词库文件不存在或解析失败，THEN THE Audit_Platform SHALL 终止启动并输出错误日志说明失败原因，且不创建任何带 `builtin` 标记的记录。
7. WHEN `/audit/text`、`/audit/batch`、`/words` 写入操作成功返回时，THE Audit_Platform SHALL 已将相应数据通过事务提交到 SQLite 文件。
8. WHEN 服务进程重启，THE Audit_Platform SHALL 在启动后能够通过 `/history` 与 `/words` 接口读取重启前已成功提交的全部记录，且记录数量与字段完整性与重启前一致。

### Requirement 17: 性能与处理时间记录

**User Story:** 作为 API 接入开发者，我希望响应中包含每层及总处理时间，以便分析瓶颈与监控服务质量。

#### Acceptance Criteria

1. THE Audit_Platform SHALL 在每次审核响应的 `processing_time` 字段中提供 `l1_ms`、`l2_ms`、`l3_ms`、`total_ms` 四个非负整数毫秒值，每个值的取值范围为 0 至 60000 毫秒，分别度量从该层接收输入到产出该层结果的时间。
2. WHEN L3_Semantic_Engine 在其超时阈值（默认 5000 毫秒）内未返回结果，THE Audit_Platform SHALL 将 `l3_ms` 设置为实际等待至超时被触发的毫秒数。
3. THE `total_ms` SHALL 不小于 `l1_ms`、`l2_ms`、`l3_ms` 中任一值，且不大于 `l1_ms + l2_ms + l3_ms + 100`（其中 100 毫秒为编排调度开销）。
4. WHILE 输入文本长度不超过 2000 个中文字符，THE Audit_Platform SHALL 满足以下性能预期：在 100 次连续请求样本中，`l1_ms` 的第 95 百分位值不超过 100 毫秒、单次最大值不超过 200 毫秒；`l2_ms` 的第 95 百分位值不超过 500 毫秒、单次最大值不超过 1000 毫秒；`l3_ms` 在 L3 成功返回的样本中第 95 百分位值不超过 3000 毫秒。
5. WHILE 输入文本长度不超过 2000 个中文字符且 L3_Semantic_Engine 在其超时阈值内成功返回结果，THE Audit_Platform SHALL 满足 `total_ms` 不超过 5000 毫秒。
6. IF 输入文本长度超过 2000 个中文字符（仅可能发生在内部调用，外部 API 已在 Requirement 8 中拒绝），THEN THE Audit_Platform 不再受 Requirement 17.4 与 17.5 的时延上限约束。
