# Code2Paper 结构化输出恢复策略

状态：规范性设计
生效日期：2026-07-28
上位原则：`agentic_error_feedback_and_self_repair_principle.md`

## 1. 目标

结构化输出恢复的目标不是让所有模型响应“看起来可用”，而是在不改变作者意图、
代码事实、引用对象和证据授权的前提下，最大化自主流水线从 provider 漂移、JSON
表示错误、schema 失配和模型重复中恢复的概率。

恢复机制必须同时满足：

- 简单且可证明语义不变的格式错误由 harness 自动修复；
- 内容、引用、证据和义务错误交给 producing/owning Agent；
- 同一失败不得用相同 prompt、schema 和上下文无信息重复；
- 每次策略变化、响应摘要和 validator 结果均可审计；
- 所有恢复结果重新经过原 schema、引用完整性、语义与证据硬门。

## 2. 错误分类

| 层级 | 示例 | 处理责任 |
|---|---|---|
| transport/provider | timeout、连接重置、空 content | provider retry policy |
| representation | fence、智能引号、尾随逗号、缺少外层 close token | deterministic harness |
| closed-set identifier presentation | 已知 id 后多出 prose 标点/空白 | deterministic harness，仅唯一精确命中 |
| schema | 字段缺失、类型错误、未知字段、半截 JSON | producing Agent |
| reference/semantic | 错 obligation/claim/evidence id、遗漏 mandatory token、空 executable target | owning Agent |
| evidence/authorization | unsupported claim、过期 snapshot、关系未证实 | Research/Writer/Verifier owning Agent |

任何跨层修复都必须采用更高风险层级：无法证明是 representation error 时，按
schema/semantic error 交 Agent，不能由规则猜测。

### 2.1 宽输出与传输超时

`max_output_tokens` 与 provider transport timeout 必须作为同一运行 profile
联合设计。对于非流式本地 API，服务端可能在完整响应闭合前不向客户端交付任何
body bytes；因此固定 300 秒 read timeout 会把仍在健康生成的 16K 响应误判为
网络故障，并以相同 prompt 重复提交昂贵请求。

运行 profile 必须：

- 根据模型实测的保守最低吞吐、thinking budget、最大 answer budget 与调度余量，
  为健康响应保留足够的墙钟时间；
- 将 transport retry 与 Agent semantic/format repair 分开计数和记录；
- 仅对真实连接失败、空闲超时或 provider 错误执行同请求 transport retry；
- 不得通过缩短正文、降低 schema、丢弃 `finish_reason=length` 响应或放宽硬门来
  规避超时；
- 记录每次请求的 resolved timeout、输出上限、耗时、finish reason 与 retry
  原因，使“慢生成”和“失联”可区分。

超时仍是必要的安全边界，但必须显著高于健康宽输出的实测完成时间。若同一请求
在超时边界反复重连且 provider 没有 stop/length/error 终态，应判定 profile
不匹配并调整 transport budget，而不是继续无信息重复。

已完成的 checkpoint replay 不属于结构化修复尝试。Terminal resume 必须复用
首轮已验证的 enriched Intent graph 与 proposal report，且在检查 pending node
之前不得重新采样模型。否则非零温度会使“恢复”变成一次新 proposal，既浪费预算，
也破坏 checkpoint digest 可复现性。

## 3. 通用恢复状态机

```text
S0 provider call
  -> transient/empty             -> S1 bounded provider retry
  -> non-empty response          -> S2 representation repair

S2 lossless harness repair
  -> parse/schema valid          -> S3 reference + semantic validation
  -> invalid                     -> S4 full typed Agent repair

S3 hard validation
  -> passed                      -> ACCEPT
  -> typed issue                 -> S4 full typed Agent repair

S4 full typed Agent repair
  -> passed original hard gate   -> ACCEPT
  -> length/parse/no progress    -> S5 compact patch strategy
  -> semantic issue changed      -> S5 compact patch strategy with delta

S5 compact patch Agent repair
  -> passed original hard gate   -> ACCEPT
  -> constrained decoding loop   -> S6 content-first + binding strategy
  -> other failed/no progress    -> S6 content-first + binding strategy

S6 prompt-only content-first repair
  -> harness extraction succeeds -> S7 unique-scope composition + hard validation
  -> length with complete prefix  -> extract first closed document -> S7
  -> vocabulary field mixed with analysis -> S6b exact-vocabulary Agent repair
  -> conflicting binding         -> BLOCKED
  -> invalid/failed/exhausted     -> BLOCKED or EXPLICIT_GAP

S6b prompt-only exact-vocabulary repair
  -> closed VOCABULARY block + exact registered tokens -> S7
  -> unknown/composite token, missing END, conflicting binding -> BLOCKED

S7 composed domain proposal
  -> passed original hard gate   -> ACCEPT
  -> failed                      -> BLOCKED or EXPLICIT_GAP
```

S5/S6 必须改变至少一个恢复维度：更小的 response schema、更窄的
obligation/claim 范围、更少的输入字段、更明确的 validator delta，或从存在
provider constrained decoding 的 native schema 切换到 prompt-only 内容输出。
不得只是增加 attempt counter。

多 obligation 修复必须采用按 obligation 独立计数的轮转调度。所有当前失败项先
各执行本轮的一次修复，再允许任何单项进入下一轮。整体安全上限动态计算为
`eligible_obligation_count × max_attempts_per_obligation`，不得使用固定全局次数，
否则前面的困难项会耗尽后续项的修复机会。每轮结束后必须重新执行完整 proposal
的原子 hard gate；单项修复成功不等于整体 accepted。

## 4. Compact patch 约束

Compact patch 仍由 Agent 生成，不是 deterministic fallback。它只允许修改当前
typed issue 指向的最小单元。

以 Intent 为例，compact schema 只接受：

- 一个逐字复制的 `obligation_id`；
- 有界的 `targets`；
- 每个 target 的 `role`、`desired_predicates`、`required_relations`、
  `search_terms`。

Harness 把 compact patch 转回完整 domain model 后，必须重新执行：

1. obligation id closed-set 校验；
2. predicate/relation vocabulary 校验；
3. mandatory predicate/relation preservation；
4. empty executable target 检查；
5. graph digest 与 R8 acceptance。

### 4.1 数量偏好与安全上限

结构化字段的“建议数量”不得直接充当语义验收硬门。例如 Intent target 通常以
1–4 个为宜，但作者意图确实包含第 5 个独立 actor/path 时，第 5 项不能仅因数量
被拒绝、截断或过滤。

实现必须区分：

- **concision preference**：用于 prompt 引导和质量审计，不阻塞合法内容；
- **pathological safety ceiling**：只防止重复循环、无限数组和失控 payload，默认
  应显著宽于常见输出；
- **domain validation**：根据 vocabulary、mandatory coverage、引用与证据关系
  判断每一项是否有效。

超过宽松安全上限时，Harness 必须把实际数量、允许上限和 validator error 返回
producing Agent，请 Agent 合并重复项或重新组织；不得静默截断，也不得为了通过
而删除语义上独立的项目。

## 5. 响应诊断与信息增益

每次结构化调用至少记录：

- `attempt`、`repair_strategy`、typed `repair_issue`；
- response hash、finish reason、token usage、实际 sampling/thinking/output budget；
- 字符数、是否以 JSON container 开始/结束；
- 非空行数、unique-line ratio；
- 有界 prefix/suffix excerpt；
- schema parse error 和下一次策略变化。

诊断 excerpt 只用于本地 debugging，不参与事实或授权。长度必须有硬上限。

以下情况视为无信息增益，下一次必须切换策略：

- `finish_reason=length` 且仍不可解析；
- 相同 typed issue 再次出现；
- empty content 已经过 provider retry；
- response hash、结构诊断或 validator delta 表明重复。

## 5.1 Content-first + binding

当 native compact schema 仍出现极长重复、非法开头或 constrained-decoding
循环时，系统不得继续扩大 token。第三层恢复改为：

1. 模型先输出一个或多个 target 的语义内容；
2. 模型可在末尾输出 binding id；
3. provider 不启用 native JSON schema；
4. harness 从短 JSON 或 `TARGET/ROLE/PREDICATES/RELATIONS/SEARCH_TERMS`
   marker blocks 中提取内容；
5. 若 binding id 存在，必须经 closed-set 唯一精确校验；
6. 若 binding id 缺失，只允许在请求作用域恰好包含一个 obligation 时由 harness
   组合，并记录 `request_scoped_identifier_binding`；
7. 组合后的 proposal 重新执行完整 domain/R8 硬门。

Harness 可以兼容缺少最后一个外层 `}`/`]`、尾随标点、大小写不同的 marker
名称和常见列表分隔符，但不得猜测未知 predicate/relation、冲突 id 或缺失的语义
target。作用域绑定只附加路由 id，不创作科研内容。

`finish_reason=length` 只是生成终止原因，不得在解析前自动判定整份响应无效。若
响应前缀已经包含第一个闭合 JSON，或完整的
`CONTENT/TARGET/BINDING/OBLIGATION_ID` 文档，Harness 可以提取该最早闭合文档，
忽略其后的重复自检尾巴，并记录 `length_terminated_candidate_recovered`。提取物
必须重新通过原 schema、closed-set id、mandatory coverage 和 domain hard gate；
任何未闭合结构、缺字段或冲突 binding 仍按 `output_budget_exhausted` 失败。

若 content-first 把自我分析混入 predicate/relation 字段，Harness 不得从混杂
句子中挑选看似已知的 token。错误必须交回 owning Agent，切换到
exact-vocabulary 策略：只输出带 `VOCABULARY` 与 `END` 边界的 predicate、
relation 和 binding，各内容行必须逐字属于注册词表。Harness 只做闭合文档提取、
closed-set 校验与作用域绑定，之后仍重跑 mandatory coverage 和完整 domain gate。

## 6. 不变量

- 不允许删除 must-cover、claim 或 evidence reference 来通过；
- 不允许 fuzzy id matching、大小写猜测、编辑距离或最近邻替换；
- 不允许把截断 JSON 的缺失语义字段用默认值补齐后 accepted；
- 不允许 compact patch 绕过原完整 schema/domain validator；
- 不允许 deterministic fallback 被记录为 Agent success；
- 失败终态必须保留 best state、typed issue、attempts 和最后策略。

## 7. 验收测试

实现必须证明：

- fence、尾随逗号、缺失外层 close token 可无损恢复；
- 已知 id 尾随标点只在唯一精确命中时恢复，错误 id 被拒绝；
- full repair 截断后第二次调用使用不同 compact schema；
- compact patch 成功后仍经过原 mandatory coverage gate；
- compact patch 连续无效时显式失败；
- 5 个独立 Intent targets 不因 1–4 个的 concision preference 被拒绝；
- 超过宽松 safety ceiling 时不截断，并产生可反馈给 Agent 的 typed error；
- native compact decoding 循环后切换为 prompt-only content-first，而不是增加 token；
- content-first JSON 缺失外层 close token或 marker 格式可被提取；
- content-first 在完整文档后重复至 length 时提取首个闭合文档并通过原硬门；
- length 响应只有半截 marker 时保持失败，不补造语义字段；
- content-first 词表字段混入分析时交 Agent 生成 exact-vocabulary 闭合块；
- exact-vocabulary 中未知复合 token 保持失败，不由 Harness 过滤；
- 单 obligation 缺失 id 可审计组合，冲突 id 必须拒绝；
- response diagnostics 有界且进入 artifact；
- checkpoint/resume 保留 repair strategy、issue 和 attempt；
- 多 obligation 场景按轮次公平调度，前项不得耗尽后项预算；
- 报告记录 eligible 数、单项上限和动态总上限；
- R8 对 fallback、协议越界和未接受 Intent proposal 保持硬失败。
