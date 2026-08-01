# Code2Paper Agent 错误反馈与自主修复原则

状态：规范性架构约束
生效日期：2026-07-28
适用范围：Intent、Intake、Analyzer、Research Supervisor、Evidence/Claim Proposal、Authoring Planner、Writer、Rewrite、Verifier，以及它们之间的 deterministic validator/policy merge。

结构化输出的分层恢复状态机与 compact patch 规则详见
`docs/agentic_structured_output_recovery_strategy.md`。

## 1. 核心原则

Code2Paper 的目标是一个能够根据代码仓库与作者意图自主研究和写作的 Agent 系统。规则层的职责是验证、定位和解释错误，不是通过降级规则、静默过滤、截断内容或放宽硬门把失败伪装成成功。

当模型输出存在 schema、格式、证据、语义、完整性或授权错误时，系统必须优先执行闭环修复：

```text
Agent proposal
  -> deterministic validation
  -> typed repair issue
  -> return issue to the owning Agent
  -> bounded corrective retry
  -> deterministic re-validation
```

只有在修复预算耗尽、必要输入不可用、工具能力不足或证据确实不存在时，系统才允许进入显式 `explicit_gap` 或 `blocked`。这些终态必须记录已尝试动作、最后错误和未满足条件，不能伪装为 accepted。

## 2. Validator 与规则层职责

Validator/policy merge 必须：

- 保持 evidence、source authority、freshness、schema、protocol 和 final reverse validation 硬门；
- 返回稳定的 typed error code，而不是只有异常字符串；
- 指明失败的 role、artifact、字段、句子、claim 或 obligation；
- 返回 offending fragment、期望 contract、可用证据和允许的 repair scope；
- 区分可修复错误、需要补证错误和不可恢复错误；
- 在每次修复后重新执行同一硬门。

Validator/policy merge 不得：

- 把失败 criterion 固定写成 `passed`；
- 因模型或 provider 不同而无证据地放宽验收；
- 静默删除错误字段、事实句或 obligation 后声称输出完整；
- 用 regex/截断/默认空对象把无效结构转换成 accepted；
- 用 deterministic fallback 替代 Agent 输出后仍声称是 Agent 成功完成；
- 因达到输出上限就把不完整 JSON 当作有效结果；
- 通过降低 must-cover、unsupported、evidence 或 protocol 标准提高通过率。

规则层可以阻止危险或未授权内容进入可信状态，但“阻止”不是“修复成功”。被阻止内容必须形成 repair issue，并返回对应 Agent。

## 3. Agent 修复责任

错误必须路由给最接近根因的 owning Agent：

| 错误类型 | 默认修复 Agent |
|---|---|
| JSON/schema/字段缺失 | 产生该结构的 Agent |
| 作者意图遗漏或 typed target 错误 | Intent Agent |
| 仓库范围、符号候选或源码提取错误 | Intake Agent |
| 行为、调用、数据流或条件解释错误 | Analyzer / Research Supervisor |
| packet/fact/claim 缺证据或关系 | Evidence Proposal Agent / Research Supervisor |
| plan 缺 stage、重复或顺序错误 | Authoring Planner |
| 正文 unsupported、越界或原子性错误 | Writer / Rewrite Agent |
| verifier 输出无效 | Verifier Agent |

修复请求必须包含最小充分上下文，不应把整个历史重新塞给模型。至少包含：

- 原始 proposal 的稳定标识与 digest；
- typed error code 和 validator message；
- 精确失败位置与 offending fragment；
- 期望 schema/contract；
- 当前 authorized evidence 和禁止扩张的边界；
- 本轮允许修改的 scope；
- 剩余 retry/tool/token budget；
- 与前次不同的修复目标，防止原样重复。

## 4. 有界重试与升级

每类错误使用独立、可审计的修复预算。推荐状态机：

1. 首次失败：同一 Agent 根据完整 typed issue 修复；
2. 再次失败：缩小 repair scope，补充 validator 差异和缺失字段；
3. 需要证据：转 Research Supervisor 使用只读工具补证，再回原 Agent；
4. 连续无信息增益：改变策略，而不是重复同一 prompt；
5. 预算耗尽：形成 `explicit_gap` 或 `blocked`，保留最后有效 best state。

重试不得通过提高无限 token/loop、重复全流水线或丢弃 validator issue 实现。每次 retry 必须记录输入 digest、输出 digest、issue ID、attempt、实际配置、finish reason 和状态变化。

Provider transport timeout 不得与 Agent 修复预算混为一谈。宽输出 profile 必须
提供与最大输出规模、thinking budget 和本地模型保守吞吐相匹配的有限传输时间；
否则 Harness 会在健康生成完成前断开连接，并把同一 prompt 当成网络重试重复
执行。出现这种现象时应修正 profile 的 transport budget，并保留原内容约束与
硬门，不能以缩短输出、过滤响应或降低 schema/证据要求代替修复。

Terminal checkpoint resume 必须优先加载首轮冻结的 Intent graph、proposal
provenance 与 checkpoint state，再判断是否存在 pending node。若 checkpoint 已
终止，resume 只能执行确定性的产物重建、digest 校验与兼容导出，不得在发现终态
之前重新调用 Intent、Research、Writer 或 Verifier。只有中断式 checkpoint
缺少终态冻结产物且确有 pending node 时，才允许恢复对应 owning Agent；该恢复
仍须沿用原 issue、attempt、budget 与 best state。

对于结构化输出，第一次完整 repair 再次出现 length/parse/no-progress 时，下一次
必须缩小为 issue-scoped compact patch schema；禁止使用完全相同的 prompt、
schema 和输入重复采样。若 compact native schema 出现 constrained-decoding
循环，必须切换到 prompt-only content-first 输出，由 harness 提取内容并在唯一
请求作用域内组合 binding，随后重跑原硬门；不得继续无上限增加 token。

当同一阶段存在多个失败 obligation/claim 时，修复预算属于各 owning item，
不得由固定全局 attempt pool 先到先得。调度器必须轮转执行：每项每轮至多一次，
动态总上限由项目数乘以单项有界次数得到，并在每轮后重跑整体原子验证。

## 5. 允许的 deterministic 行为

下列 deterministic 行为仍然必要：

- schema 解析与严格验证；
- source authority、snapshot、freshness 和 evidence binding；
- 安全边界、路径边界和工具权限；
- claim authorization 和 final reverse validation；
- best-state retention；
- 对已经由 Writer/Rewrite Agent 明确生成且 validator 认可的结构化 patch 进行
  机械定位与应用。

Deterministic 组件不得自行创作新的科研事实或替 Agent 猜测缺失内容。机械 JSON 修复只允许处理不改变语义的表示问题，并且必须保留 repair 记录；任何可能改变字段含义、事实边界或义务覆盖的修复都必须返回 Agent。

对最终正文采用更严格的边界：规则代码不得产生、改写、删除、补全或重排正文
lexical token，包括从 authorized claim 复制 canonical fragment、机械追加
qualifier、删除 unsupported 子句或插入 missing planned claim。规则层可以：

- 检测并定位错误；
- 生成 typed issue 和 closed repair scope；
- 调用 owning Writer/Rewrite Agent；
- 校验 Agent 返回的 patch；
- 按 Agent 明确给出的 span/operation 应用通过验证的 patch；
- 在 patch 无效时保留原 best state 并阻塞。

最终正文必须生成 `FinalTextAuthorshipLedgerV1`。除 Markdown 分隔符、空白和换行
外，每个 lexical span 都要回溯到 Writer 或 Rewrite 的 generation trace；
`deterministic_generated` 正文 span 是协议失败。应用 Agent patch 不等于规则
写作，前提是 patch 中的全部正文词句逐字来自该次 Agent 响应。

### 5.1 Harness 表示级兼容边界

Harness 在把错误返回 Agent 前，应先执行可证明不改变语义的表示级兼容：

- 去除 JSON 外层 Markdown fence、修正常见智能引号和闭合符号前的尾随逗号；
- 只在最后一个完整 JSON value 之后补齐缺失的外层 `]`/`}`；
- 对 obligation/claim/evidence 等引用 id，仅当去除尾随空白或 prose 标点后
  能在当前 closed allowed set 中唯一精确命中时，恢复为该已知 id；
- 修复后必须重新运行完整 schema、引用完整性和语义硬门；
- 每次修复必须记录 `repair_kind`、原值、修复值、字段位置以及
  `semantic_change=false`。

Harness 不得修复半截字符串、半截字段、缺失列表元素、未知引用、多个候选命中、
大小写或拼写猜测，也不得把 `finish_reason=length` 本身视为可接受。无法证明语义
不变时，必须生成 typed repair issue 交回 owning Agent。

这里的表示级兼容只适用于 Agent 响应容器和结构化 binding。即使 Harness 修复了
JSON 外层括号或尾随逗号，也不得据此改动 JSON 中的正文字符串；正文字符串若截断、
缺失或语义不完整，必须回到 Writer/Rewrite。

## 6. 验收要求

新增或修改 Agent/validator 时，测试必须至少证明：

- 无效 proposal 会产生 typed repair issue；
- issue 会回到正确 owning Agent；
- 第二次有效 proposal 能通过原硬门；
- 重试期间硬门没有被关闭或改写；
- 连续无效 proposal 最终为显式 gap/blocked，而不是 accepted；
- deterministic fallback、过滤或截断不会冒充 Agent 成功；
- deterministic 代码不能直接改变 final prose lexical token；
- final authorship ledger 能把每个正文 span 回溯到 Writer/Rewrite generation；
- checkpoint/resume 保留 issue、attempt、budget 和 best state；
- R8 报告区分“Agent 修复成功”“显式 gap”“blocked”和“协议失败”。
