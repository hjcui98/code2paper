# Research → Method 执行中方向复核（2026-09-12）

结论：保留统一机制上下文、三层上下文与分权威 Writer 主方向；先纠正 R5 条件授权、
R7 叙事身份和 join 页路由，再完成段落预算。R6 的真实请求与整 run 预算合同须在 live 前补齐。
不建议此时继续扩大到 R8–R10，或用抬高页阈值推进链路。

本报告是执行中审查，不是新架构或完整验收。没有修改生产代码、测试、现有执行计划或实现记录；
只新增本报告与独立离线诊断脚本。没有调用模型、启动 live 或重跑全量静态。

## 1. 范围与证据等级

- 执行入口：[统一修复计划](research_to_method_unified_repair_execution_plan_2026-09-12.md)。
- 实施记录：[当前实现记录](../.agent/implementation.md)。
- 检查对象：当前 dirty worktree，HEAD `84371e4fee974071a580d7832af0ac14908c2d4b`。
  HEAD 不能单独代表本次代码；诊断结果另存七个相关文件的完整 SHA-256。
- 新观察：[探针结果](../.tmp/c2p-direction-review-20260912/probe-results.json)，
  [复现脚本](../.tmp/c2p-direction-review-20260912/review_probes.py)。
  使用现有项目中立测试 fixture 调用真实 compiler/validator，不启动 pytest 或模型。
- 已读取的阶段产物：[R6 冻结离线报告](../.tmp/c2p-unified-repair-20260912-r6/offline/offline-ebcar-r6-final.json)。
  这份报告绑定 R6 状态，不能替代正在变化的 R7 全链验收。
- `3316 passed, 3 skipped` 是实现记录中的 G2 历史结果，本轮没有重新验证该全量结论。

上位依据为总体架构、Writer 设计、08-22 Candidate 措辞权方案、09-08 Unified 修订与
当前执行计划 §10–12、§16。其证据、条件、作者约束、预算和恢复合同继续有效。

## 2. 已有进展应保留，但阶段通过不能扩写成产品通过

R6 产物实际显示：

| 对象 | 观察值 | 边界 |
|---|---|---|
| 核心 active path unknown | 0 | 支持 R1 原阻塞在这份离线重建上消失 |
| Source / archive | pass；887 atoms | 只证明该冻结输入的源码与归档阶段 |
| 基础 worksets | pass；113 页 | 不包括后来失败的完整 Writer workset 扩展 |
| Candidate Research admission | pass；handoff eligible；重验失败为空 | 不是整条 Candidate authoring admission PASS |
| Strict Research admission | 三条 partial 缺口 | 仍失败，不应改成 supported |
| completeness | 两机制 operation_disposition_unresolved | 仍有独立结构/研究证据缺口 |
| Formalizer | 65 个计划 invocation，status=fail | 是计划，不是 65 次真实执行 |
| Writer / Realizer | phase_not_compiled | 不能评价生成质量或声称正文已生成 |

实现记录报告 R7 已消除七条 `missing_core_detail`，最新离线失败推进到
`MA-S1 paragraph closure 25618>20000`。本轮在可访问的上述任务产物目录中未定位到这次
R7 全链报告文件，因此该数值保留为实施者记录；本轮独立复现的是下列代码偏差。

## 3. 必须纠偏的发现

### F1 / P1：R5 条件校验引入项目答案，并会错误放行扩大后的条件

位置：`publication_transaction_contract.py:621`、`:703`、`:716`、`:756`。

`_CONDITION_EQUIVALENCE_GROUPS` 把 `self.cfg.use_dedicated_attention` 和
`self.cfg.add_positional_encoding` 及其英文表述写入通用生产代码，违反项目符号不得进入
通用生产授权逻辑的边界。它也没有落实执行计划要求的语义 witness。

独立探针实际返回：

| 声明 | witness | condition / constraint 返回 |
|---|---|---|
| use_dedicated_attention | When dedicated attention is enabled **or disabled**, the mask is built. | true / true |
| alpha **and** beta | When alpha **or** beta holds, compute the output. | true / true |

第一例在 `startswith` 分支提前通过，绕过后面的否定/范围检查；第二例由于词法预处理删除
and/or 而丢失布尔结构。另一个带 `never built` 的探针也通过了仅含条件的约束；它说明该检查
不能承担完整操作语义判定，但本轮没有据此声称最终 Verified 已被穿透。

建议：撤回 R5 条件部分的接受结论，保留公式 lane/review/authority 接线成果。
条件身份、作用域、AND/OR、比较运算与极性由 typed 证据保留；自然语言措辞由既有独立语义
验证路径校验并绑定精确 witness、source/detail、正文/计划 digest。词法匹配只能辅助候选定位。
无法证明时返回 owning Agent 的有界修复，不增长项目白名单，也不改回原始源码逐字包含。

退出测试至少包括项目中立的 AND↔OR、嵌套否定、范围扩大、比较边界变化、前缀后追加反向条件，
以及独立验证失败/缺失时保持失败。须检查真实 transaction 路径，不能只测私有字符串函数。

### F2 / P1：R7 补齐 detail 数量，但仍按位置重分章节内容

位置：`method_architect.py:8208`–`:8219`。

当前实现把所有机制 detail 展平后按章节数均分，继续保留 prior section ID、heading 和段落 ID。
它没有用已有 owner/unit/facet/assignment 证明旧章节和新内容的对应关系。

独立探针使用现有两机制 fixture 与四个 prior sections：

- `MA-S2` 标题仍为 `Mechanism mech_beta`，owner 却由 beta 变为 alpha。
- `MA-S3` 标题仍为 `Mechanism mech_alpha`，owner 却由 alpha 变为 beta。
- `validate_narrative_plan` 返回空失败列表。

这说明 core detail 恰好覆盖一次只是必要条件，不能证明叙事/controller 身份正确。
R7 尚在实施中，因此不是要求中途具备所有能力；但不能继续以当前位置分配作为分页的正式输入。

建议先完成 §12.1 typed bridge：有来源的映射才复用旧 ID；实质 owner/要求变化形成明确 revision，
保留 rationale、dependencies、move authority 与必需目标。对歧义显式阻塞；LLM proposal 只拥有
组织和措辞权。之后才根据已正确归属的段落闭包做预算拆分。

### F3 / P1：合法 Writer join 页被误当作 Formalizer repair 页

位置：`unified_context_compiler.py:1959`、`:2798`–`:2808`。

`extend_writer_worksets_from_narrative_plan` 给多机制章节产生 `page_kind=join`；
`build_consumer_invocation_plan_v1` 却在区分 phase 之前遍历全部 join 页，并要求每页都有
`repair_obligation_id`。该字段属于公式 repair，普通 Writer join 页没有它。

本轮通过真实 archive→writer workset→writer invocation plan 的小型探针复现：

```text
writer page_kind = join
UnifiedCompilerError: unified_page_projection_incomplete:
join page ... has no repair obligation ID
```

所以段落页预算修好后，多机制章节仍会在下一层失败。这是现存 producer/consumer 合同不一致，
由 R7 更完整的多机制映射暴露，不应绕开 join 页或删机制。

建议明确 join 的用途与消费者身份：公式 repair 页继续检查 obligation；章节 join 页检查
section/paragraph/dependency proof，按所属 workset/phase 消费。不要只为过门补造 repair ID。
补合法双机制 Writer/Realizer 主路及伪造 repair/join 身份负例，串到请求截获与 receipt。

### F4 / P1（live 前）：R6 单请求检查已加上，总预算的上界仍未闭合

位置：`unified_context_compiler.py:3026`、`:2969`；
`publication_method_writer.py:3031`、`:16624`；
`tests/test_agentic_publication_method_writer_unified.py:649`。

两部分需要分开处理：

1. 计划计量的是 consumer envelope，Writer/Realizer 实际发送包含额外 scaffolding；发送端检查的是
   role request cap，而非该 invocation 的计划预留量。现有超限测试本身就构造了“计划通过、
   真实请求更大后被拒绝”。这证明发送前拒绝有效，也证明不能声称三种角色计划与实际字节完全同口径。
   实际请求即使小于 role cap，仍可能高于该次 reservation。
2. `planned/reserved_calls` 每 invocation 加 1，tokens 每 invocation 加一次，未按 attempts
   计入上界。探针中两条声明 invocation（含条件 repair slot）预留 2 calls / 6586 tokens，
   `max_attempts=2` 对应 4 attempt slots / 13172 tokens 的理论上界。这不是实际超支证据，
   但当前 reservation 不能作为允许重试的最坏上界证明。

建议把生产请求构造器用于规划和发送的共同预算输入；对未知但允许的提示增量明确预留。
选择“预留可证明的 attempts 上界”或“每次发送前从剩余 envelope 原子扣账”的一致合同，
绑定 started/completed/resume。独立 semantic repair 与运输层 retry 不应混为一笔未计量调用。
这应在离线用超额拒绝、重试、中断恢复、phase revision 的反例闭合，不能留到 live 碰出超支再修。

## 4. 分页与研究证据的注意事项

- “每段最多 8 个 detail”不等于语义合理或闭包能装入页。应先确定 owner、逻辑单位和依赖，再测
  完整闭包；合法拆段形成 plan revision，必需目标与条件集合守恒、公式消费者明确。
- 若一个最小语义单位也超页预算，记录原子/依赖贡献并返回合法计划修订。不能截掉 source atom、
  省略 qualifier、把 requirements 放到 Writer 看不到的页，或只抬高 20000 阈值。
- `conservative_utf8_bytes_div_4` 是当前估算代理，本轮没有对实际模型 tokenizer 校准。
  同一公式两次计算一致只证明计量一致，不能单独证明不超过实际 context。模型 tokenizer 模式也需
  真正核对实现身份与发送序列化；当前 `measure_unified_tokens` 注释中的身份一致未见函数内校验。
- 配置 selected/default 的证据缺口须返回 Research；conditional 表达不授权分支已实际启用。
  completeness 与 strict/Candidate admission 分列，不能把 strict partial 或 entrypoint 外的未证操作
  混成 R7 分页问题，也不能因为 handoff eligible 就宣布可以进入所有生成阶段。
- Run D 原始响应未找到时仍是未复现缺口。R4 协议负例有价值，但不能宣称修复了同一个真实样本。

## 5. 建议执行顺序与退出证据

1. **R5 条件纠偏**：去项目答案与词法授权，绑定通用 typed 条件和独立语义 witness；先封住错误放行。
2. **R7 身份与 join 接线**：覆盖三种 sections/contexts 数量关系、反向排序、同名/同 ID owner 变化、
   合并/拆分、依赖保全与公式唯一消费者；真实 controller→request 截获必须一致。
3. **R7 合法分页 + R6 预算闭合**：在正确身份上做段落 revision，贯通 workset→plan→实际请求→receipt。
   覆盖每请求、全 run、retry/resume 三种预算，失败前不调用模型。
4. **新的冻结离线报告**：完整保存 R7 结果及当前文件摘要，分别列 source、strict Research、Candidate
   Research、mechanism、Formalizer、Writer、Realizer。对研究证据不足单独记录有预算的补证范围。
5. **再进入后续分片和分层验收**：R8 局部 callback 要建立在稳定的段落/revision 身份上；R9/R10
   保持既定终态与作者约束合同。满足既有 live 准入与授权后，做单项目诊断；正式扩项仍遵守矩阵门。

这属于现有计划内的纠偏，无需替换总体方向。当前最需要避免的是把“没有 missing_core_detail”
等同于叙事正确，或把“发送前能拒绝超限”写成整个运行已经有严格预算上界。

## 6. 本次验证记录

精确命令：

```bash
python .tmp/c2p-direction-review-20260912/review_probes.py > .tmp/c2p-direction-review-20260912/probe-results.json
```

首次脚本调用因脚本目录改变导入搜索路径报 `ModuleNotFoundError: code2paper`，exit 1；
仅在诊断脚本内显式加入仓库 `src` 路径后重跑，exit 0。四组诊断结果与代码摘要已保存。
此前交互式同等探针也均实际复现。本轮未跑全量 pytest、性能基准、provider 或真实 API。

状态文档存在小幅自相矛盾：顶部仍写“R7–R10 尚未开始”，后文已写 R7 进行中；
R6 的“超预算已消失”也需限定为基础 worksets。建议实施者下次更新时统一口径，
并把 R5 条件部分与 R6 预算上界改记为待修，保留已经成立的局部验证成果。
