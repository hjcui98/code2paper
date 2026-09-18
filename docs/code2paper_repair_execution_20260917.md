# Code2Paper：运行身份、意图保真与页级交付修复执行方案

**审计日期：2026-09-17**  
**审计分支：** `codex/agentic-p4-benchmark-cutover-20260917`  
**固定代码基线：** `34ae0cf15f0ae200d863b63a8c912dc21b299626`  
**固定事故归档：** `artifacts/runs/2026-09-17-ebcar-intent-v4-p7-j9L1bn/raw_run/`  
**交付性质：** 静态代码审计与归档产物核对后的开发执行设计；不是已经合入的修复，不是 live 验收报告。

> 本次通过 GitHub 连接读取固定提交的代码、真实请求/响应、重试及验收记录。没有读取宿主 `/tmp`，没有退出用户描述的 bwrap 沙箱，没有调用真实模型，没有修改仓库或重启 run。下文新增类型、函数、参数、错误码及测试名称均为拟实现接口；已有接口另行标明。代码定位以“固定提交 + 文件 + 符号/唯一文本”为准，避免后续修改后依赖漂移的行号。

---

## 0. 执行结论

这次问题不是单纯的“最后一页太长”，也不是四套 V2/V3/V4 管线同时竞争。修复必须同时覆盖三个层次：

1. **运行有效性：** 严格区分新实验、同身份恢复、导入研究证据后重新写作，禁止把历史耗尽的 invocation 当成修复后的新测试。
2. **写作任务有效性：** 修复从作者意图到 Writer 实际请求的信息丢失、空槽段落扩张，以及 Writer/Binder witness 责任表达不一致。
3. **产物与质量有效性：** 用按角色、阶段、修订解析的产物索引代替文件名猜测；保留 fail-closed，但不把“段落数量齐全”“exact-text witness 齐全”误当成学术内容正确。

**建议顺序：事故回归固定 → 运行身份与恢复规则 → 作者意图传递/槽位整理 → witness 契约统一 → 输出工作量分页 → 产物索引与依赖验收 → 新身份 live 与质量对照。**

不建议先清空 ledger、加大重试次数或把 16 段机械分成 2–3 页。那样可以把失败位置后移，却不能消除错误写作任务。

---

## 1. 已核实事实、需要修正的判断与证据边界

### 1.1 固定事故身份与直接阻断

归档 `run_identity_v1.json` 的 `run_id` 为：

```text
ebcar-intent-v4-p7-current-20260916T165846Z
```

失败 invocation 为：

```text
inv:writer:MA-S3:page:751aa8b5352377a0766e7f7416c05553647380df74d5295f04d695646a47b815
```

它的第 4 次记录明确包含：

```json
{
  "attempt": 4,
  "sent_to_caller": false,
  "delivery_status": "rejected",
  "delivery_rejection_code": "attempt_limit_exhausted:inv:writer:MA-S3:page:751aa8b5352377a0766e7f7416c05553647380df74d5295f04d695646a47b815:4>2",
  "provider_usage": null
}
```

这足以证明：在相同 invocation 目录和 `max_attempts=2` 的条件下，这次重启没有形成新的模型内容试验。不能把这次拒发算成模型没有修好内容。**“不可写”只限定于当前身份和预算，不是页面在所有未来 run 中永久不可写。** [A1][A4][C1]

`writer_section_receipts_v2.json` 中，MA-S3 的 required invocation 有 16 个，completed invocation 有 15 个，缺少的就是上述页面。聚合 receipt 只有 MA-S1、MA-S2、MA-S4、MA-S5 完成，`all_required_sections_complete=false`。这里用 receipt 核对，而不是根据“目录存在”判断成功。completed、content accepted 和最终 verified 仍须分开理解。 [A5][A6]

### 1.2 重要纠正：287506e3 不是可直接与引擎 HEAD 比较的 SHA

`autonomous_method_agent.py` 在构造 `RunIdentityV1` 时，把：

```python
repo_root=repo_path
code_sha=str(getattr(runtime.repo_snapshot, "git_commit", "") or "") or None
```

传给 `build_run_identity()`。归档 RepoSnapshot 的目标是 EBCAR，`git_commit` 确实是：

```text
287506e3e2df30e3c840b8f6398b5010c25111e1
```

因此，合同内这个字段至少在该入口表示**被研究仓库的 Git 身份**，不能仅凭它不同于 Code2Paper 的 `2c290aa` 或本次固定的 `34ae0cf` 就证明引擎混跑。真正的问题是：**引擎身份、目标仓库身份没有明确分离，导致无法可靠解释恢复兼容性。** [A1][A2][C2][C3]

### 1.3 更深的质量问题：16 个交付段落中，15 个在 Writer 表面没有各自的写作内容

第 2 次 provider request 的 `narrative_plan.paragraphs` 显示：`MA-S3:P3` 至 `MA-S3:P17` 都有以下特征：

```json
{
  "mechanism_id": "",
  "required_detail_ids": [],
  "optional_detail_ids": [],
  "formula_obligation_ids": [],
  "formula_package_ids": [],
  "role": "step_sequence",
  "witness_contract": {"targets": []}
}
```

它们的 `reader_goal` 相同，都是 MA-S3 的 section 级架构问题。该模型可见段落对象没有各自的作者 statement、story 语义内容或差异化局部目标。**这不证明上游没有作者意图，而是证明意图没有在该 Writer 段落表面得到充分表达。** [A3]

第 2 次响应因此不是仅仅“补回了遗漏段落”：它在这些缺少局部约束的槽位中生成了大量架构、打分及推理描述。不能仅凭这些句子看似合理就视为有实现依据；本次没有把这些句子逐一与完整 EBCAR 原实现做语义验真，故不直接断言它们全部错误。另一个可见问题是，`P1__f1` 在架构输入编码叙述末尾被迫接入“训练损失取均值”，提示 detail 的事实授权与叙事位置需要分开检查。 [A7]

### 1.4 能定位到两个具体上游实现点

**第一处：`intent_narrative_compiler.py`。** `build_intent_narrative_plan_v4()` 按 story–mechanism slot 构造段落；`_best_slot()` 用 handle 交集计分，零交集也会选出一个 slot。代码记录 fallback，但仍把 detail 放入该 slot。输出阶段会逐个把 slot 转成段落，不以其是否具有独立语义材料作为准入条件。 [C4]

**第二处：`llm/section_writer.py`。** `_WRITER_PARAGRAPH_NARRATIVE_FIELDS` 和 `_compact_writer_narrative_plan_for_llm()` 的白名单保留 paragraph ID、role、detail IDs、reader_goal 等，但没有保留 V4 的 `ordered_story_node_ids`、`ordered_argument_unit_ids`、`intent_atom_ids`、`authority_surface` 等意图/权限元数据，更没有将它们解析成页内具体作者语义。`project_intent_plan_to_narrative_v3()` 在较早投影中明确保留过这些字段，因此“V4→V3 保真”不等于“Writer 实际请求保真”。 [C4][C5]

### 1.5 第 2 次失败的两个 witness 是 detail，不是笼统的 atom 缺失

第 2 次 content acceptance 明确拒绝：

```text
MA-S3:P1__f1:detail:detail:mech_sym:f6cf5bdfe2ae16f0:15
MA-S3:P1__f1:detail:detail:mech_sym:f6cf5bdfe2ae16f0:76
invalid_count
invalid_witness_count
```

响应包含多条 `witness_kind="atom"` 声明，但没有对应的两条 `detail` witness，且 `rendered_detail_ids` 为空。请求的 binding_contract 又声明 atom binding 由 Binder 完成，而 narrative witness targets 仍向模型暴露 required atom 项。**不同输入表面对责任的描述不够统一，是修复重点。** 日志中 `detail:detail:` 也可能只是 `kind + target_id` 的显示拼接，不应凭这个字符串直接认定存储 ID 双重加前缀。 [A3][A7][C5][C6]

### 1.6 有输出预留，不等于有输出任务可行性检查

该实际请求的预算记录已有 `output_reserve_tokens=8192`、`model_context_tokens=131072` 等字段。不能声称系统完全没有输出预算。缺的是**输出工作量与一次事务复杂度**的预检：段落正文、JSON 包装、witness 文字/引用、公式引用等是否能在输出额度内完成。 [A4]

`fit_narrative_plan_to_page_budget()` 和 `extend_writer_worksets_from_narrative_plan()` 已有输入闭包拆分、完整请求测量、witness/公式归属检查，应扩展现有实现，不另写平行分页器。`page_kind="join"` 在代码中主要由 mechanism 数量决定，不应理解成“必然只能有一个 section 收束调用”的特殊语义。 [C7]

### 1.7 空基础 manifest 不应该被 Writer 真身直接覆盖

`publication_method_writer.py` 明确解释：基础 manifest 绑定 Formalizer 阶段；Writer 段落发现后建立 phase-specific composite manifest，目的是不修改已经绑定 Formalizer receipt 的对象。本 run 没有相应公式任务，基础 manifest 为空可以是合法阶段产物。 [C1]

真正需要修的是“读者如何找到某一阶段当前对象”，不是用 `.writer.2` 覆盖基础文件。类似地，schema 版本、阶段、修订需要分开命名，但不能删除历史对象或破坏 digest 引用。

### 1.8 两个附加的、可直接修复的身份/合同问题

`intent_narrative_compiler.py` 中 `source_intent_digest` 当前由 story ID 序列生成，未覆盖作者 statement 等内容。这不等于最终 plan digest 一定不变，但它不足以充当完整的上游意图内容身份。 [C4]

`authoring_context_contract.py` 中 builder 计算 missing 时排除 `not_applicable_artifact_keys`，而 `validate_authoring_run_contract()` 没有排除；其 `allow_blocked` 参数当前也未参与判断。两条路径可能对同一合同给出不同结果。另外，builder 的 actual 判定主要依赖文件存在，不能独立证明内容有效或属于当前阶段。 [C3]

---

## 2. 现有流程地图与本轮改造边界

### 2.1 需要保留的主链

```text
目标仓库 + 作者意图 + claims
    │
    ▼
autonomous_method_agent / ResearchGraphRuntime
    │ RepoSnapshot、SourceManifest、facts/claims、机制闭包、handoff
    ▼
unified archive + Formalizer worksets / invocation plan / admission
    │ 实际 Formalizer 调用、公式 package（无任务可显式 N/A）
    ▼
_build_narrative_plan_v3（当前先生成 legacy V3，再构造 V4 envelope）
    │ 选择 V4 时再 project_intent_plan_to_narrative_v3
    ▼
fit_narrative_plan_to_page_budget + Writer workset extension
    │ V3 budget revision；兼容 MethodSectionPlanV2 adapter
    ▼
_writer_section_inputs_v3 → _writer_section_inputs_v2
    │ 页内完整私有合同
    ▼
_llm_visible_section_payload / compact narrative + binding contract
    │ 实际模型表面（本次意图信息丢失的重要位置）
    ▼
Writer caller boundary + durable ledger + bounded content repair
    │ provider request/response、transport receipt、content acceptance
    ▼
Realizer / Binder / section composition / publication audit
    ▼
candidate / annotated evidence / verified（不同产品状态）
```

这是一条带兼容适配层的生产链，不应为了名字统一，再增加一个 V5 平行生成系统。目标是**一个语义计划、多个经过验证的投影、一个清晰的执行身份、一个每阶段权威的产物解析入口**。

### 2.2 明确不做

不替换整个 Research runtime；不同时引入新队列、数据库、workflow 框架；不取消 exact evidence、source manifest、公式唯一 consumer 等不变量；不让规则层生成科研正文；不将作者说明升级成 repository verified；不把旧 run 的成功段落直接复制为新 run 的 accepted receipt；不为了过测把所有失败 targets 标为 optional；不承诺这次 EBCAR 通过就代表全部 benchmark 通过。

### 2.3 修改落点索引

| 模块（现有，除非标注新增） | 精确落点 | 本轮职责 |
|---|---|---|
| `src/code2paper/agentic/autonomous_method_agent.py` | `build_run_identity(...)` 调用前后、研究 handoff 到写作入口 | new/resume/fork 决策；引擎与目标身份分离 |
| `src/code2paper/agentic/authoring_context_contract.py` | `RunIdentityV1`、`build_run_identity`、`dirty_manifest_digest`、合同 builder/validator/write 函数 | 新身份模型、恢复比较、N/A 一致性、写前身份保护 |
| `src/code2paper/agentic/intent_narrative_compiler.py` | `_assign_story_to_sections`、`_best_slot`、`build_intent_narrative_plan_v4`、`project_intent_plan_to_narrative_v3` | 槽位归并、局部意图材料、依据不足分流、完整 intent digest |
| `src/code2paper/agentic/intent_spine_models.py` | V4 paragraph/plan 的模型边界，新增字段前读取完整模型和校验器 | 页内 intent surface、状态与投影来源字段 |
| `src/code2paper/llm/section_writer.py` | `_WRITER_PARAGRAPH_NARRATIVE_FIELDS`、`_compact_writer_narrative_plan_for_llm`、`_compact_writer_binding_contract_for_llm`、`_llm_visible_section_payload` | 意图表面保真、Writer 专属 targets、单一输出正文表面 |
| `src/code2paper/agentic/publication_method_writer.py` | `_build_narrative_plan_v3`、V4 overwrite 分支、`_writer_section_inputs_v2`、`_capturing_writer_caller`、`_run_unified_v2_realizer_phase`、`writer_v2_invocation_acceptance_count` 分支 | 选择一次计划、契约装配、恢复/拒发语义、依赖门前置 |
| `src/code2paper/agentic/unified_context_compiler.py` | `fit_narrative_plan_to_page_budget`；`extend_writer_worksets_from_narrative_plan` 内 `_build_section_pages`、`_candidate_request_tokens` | 输入+输出任务量联合分页，保留原有闭包守恒 |
| `src/code2paper/agentic/unified_context_models.py` | page / invocation / budget / receipt 类型边界 | 加入契约指纹、任务工作量摘要；读取完整校验器后实施 |
| `src/code2paper/agentic/unified_invocation_ledger.py` | `last_started_attempt`、`publish_attempt_started/completed`、`publish_writer_content_acceptance`、`read_writer_content_acceptance`、`read_run_budget_state` | 分离事件号和实际发送计数、恢复选择、不可变记录 |
| `src/code2paper/agentic/publication_transaction_contract.py` | `assess_paragraph_transaction` 及 target/anchor 判定 | Writer/最终完整验证分层、精确错误码，保留内容语义约束 |
| `src/code2paper/cli/agentic_run.py` 与 `src/code2paper/cli/main.py` | 已安装入口对应的 parser/调用路径；实现前核实具体参数函数 | 用户可见 new/resume/fork 与 doctor；不增第二个产品入口 |
| **新增** `src/code2paper/agentic/authoring_artifact_index.py` | typed index、resolve、publish snapshot | 按阶段和角色定位产物，不猜文件名 |
| **新增** `tests/regression_20260917/` | 本文第 12 节测试矩阵 | 归档重放、结构性质、故障注入、禁止联网测试 |

`intent_spine_models.py`、`unified_context_models.py`、CLI 的具体新字段接入属于本方案指定开发落点；本次没有逐行读完这些模块的全部校验器，开发必须先读取其完整模型，不能把下文草案直接粘贴后跳过兼容性检查。

---

## 3. 全程必须保持的不变量

**I1 证据权威不变。** 作者意图用于组织和作者自述；实现事实仍由目标仓库/source manifest/研究证据支持。字段换名、slot 合并、语义改写不会增加证据等级。

**I2 语义计划只有一个当前选择。** V4/V3 selection 在构建前决定；兼容投影不得发起第二次独立规划。明确选择 V4 时，编译失败仍应失败，不能悄悄退回 V3。

**I3 段落与任务分离。** 一个作者 story 可以被合并到同一段；一个段落可因证据预算拆成连续片段；每个需要写正文的片段在当前 execution plan 中只能有一个 owner page。纯结构项不强制生成独立正文。

**I4 义务按 occurrence 守恒。** 校验键至少为 `(paragraph/fragment, target_kind, target_id, owner_stage)`。不能只比较全局 target ID 集合，因为同一 detail 可以在两个位置承担不同叙述义务。

**I5 split 不丢条件。** 输入拆分继续保留现有条件、极性、接口、公式依赖等分配检查。不能把跨细节公式切成缺少任一操作数的两页。

**I6 发送与内容接受分开。** 已发送且 schema 合法不等于内容 accepted；内容 accepted 不等于 section complete；section complete 不等于 verified。

**I7 恢复不重置成本。** 相同执行身份的重新启动不产生新的内容预算。新代码、新 plan 或新 prompt 的试验必须显式 fork/new，原 run 的成本和失败证据不可删除。

**I8 旧证据不可覆盖。** ledger、历史 plan、历史 manifest、旧 provider request/response 不原地重写。新增索引只引用和解释旧对象。

**I9 failed content 可留存，但不能发布为成功正文。** 调试候选和 annotated failure 可以保留；clean publication candidate 与 verified 要遵守各自状态合同，不能把失败片段拼进去后隐藏缺口。

**I10 任一验收规则变更必须改变 validator/contract identity。** 不能在同一个 receipt digest 的名义下重新解释历史 accepted/rejected。

---

## 4. WP0：固定事故回归，先让“失败”可重复解释

**优先级 P0；不调用模型；不改变原归档。**

### 4.1 固定输入集

测试 fixture 不复制整个 5 MB archive 到多个文件。保留一个归档定位清单及所需小对象：失败页 attempt 1/2 request、response、acceptance；attempt 3/4 completion；Writer section/aggregate receipts；run identity；目标 RepoSnapshot；基础/Writer manifest 的 header 与必要页面；V4→V3→revision 的相关段落与 adapter。

测试从固定提交读取的版本制作脱敏 fixture，保留原 blob SHA、JSON content digest 与字段语义；fixture 文件不可引用生产 `/tmp`。若复制内容后脱敏，必须记录“原始 blob SHA”和“fixture bytes digest”两个不同字段，不能伪称脱敏文件仍是原始 digest。

### 4.2 首批必须得到的结论

- attempt 4 是拒发，不是一次新的模型失败；输出 usage 未知不能擅自补 0，但 `sent_to_caller=false` 可确定没有这次 provider send。
- `P3–P17` 在实际 Writer request 中均无 detail/formula targets，且不能恢复出各自作者语义。
- attempt 2 缺的是两个 detail witness，不可用其 atom witness 数量替代。
- MA-S3 receipt 是 15/16；整个 Writer aggregate 不是 complete。
- `run_identity.code_commit_sha == target_repo_snapshot.git_commit`；本字段不能代表已验证的引擎 HEAD。
- Formalizer 空 manifest 与 Writer manifest 必须可同时合法存在。

### 4.3 交付物与停止条件

新增 `tests/regression_20260917/test_archived_failure_facts.py`，全部使用本地 fixture；网络、真实 endpoint 和生产目录写入必须被测试禁用。任何事实测试与归档不符，先纠正诊断，不进入修复阶段。

---

## 5. WP1：运行身份、new/resume/fork 与目录准入

**优先级 P0；依赖 WP0。**

### 5.1 新身份结构（拟新增 `AuthoringExecutionIdentityV2`）

```python
class AuthoringExecutionIdentityV2(BaseModel):
    schema_version: Literal["2.0"] = "2.0"
    execution_id: str                 # 一次明确批准的执行身份
    parent_execution_id: str | None = None
    creation_mode: Literal["new", "fork_authoring"]

    engine_commit_sha: str           # Code2Paper 自身，而非 target repo
    engine_source_digest: str        # 实际相关源码/未提交内容指纹
    target_repo_snapshot_digest: str
    target_project_tree_hash: str
    target_source_manifest_digest: str

    intent_content_digest: str       # 作者语义内容，不只是 ID
    claims_digest: str
    profile_digest: str
    model_identity_digest: str
    prompt_bundle_digest: str
    tokenizer_contract_digest: str
    validator_bundle_digest: str
    research_import_digest: str | None = None
    content_digest: str
```

上述为接口草案，最终沿用现有 canonical JSON/digest 工具，不新引入第三种哈希序列化约定。`requested_mode=new/resume/fork_authoring` 属于本次打开请求，而不是可变的执行身份字段；resume 保留原 `creation_mode`、`execution_id` 和父身份。恢复比较使用版本化的兼容字段集合，不对一个新生成的随机 execution_id 与历史完整 identity digest 作相等比较。执行身份与后续 plan/phase snapshot 分开冻结：尚未编译的 plan 不填占位 digest，resume 必须再验证已冻结 plan 的原始身份。

### 5.2 引擎 dirty 指纹

`dirty_manifest_digest()` 当前哈希 porcelain 状态，不能识别“同一路径仍为 M，但内容变了”。改为内容寻址：相对路径、条目类型、文件内容 hash 或 symlink target；包含相关未跟踪源码；避免纳入 run 输出、缓存、secret。对比身份使用内容 digest，绝对路径仅作诊断元数据，不能让相同源码搬目录就失去兼容性。

需要明确输出目录排除策略，防止运行每写一个 JSON 都改变 engine identity。读文件过程中若 inode/size/mtime 改变，重新读取一次或返回 `engine_snapshot_unstable`；不能保存前后混合的快照。仅 Git SHA 不足以覆盖未提交改动。无法解析引擎根目录时返回 unknown 并禁止严格 resume，不能把 target root 作为替代。

### 5.3 目录准入状态机

| 请求 | 目录/身份 | 行为 |
|---|---|---|
| new | 不存在或允许的空目录 | 创建 identity，再进入流程 |
| new | 已有 run/ledger/plan | `run_directory_not_empty`，零模型调用 |
| resume | 身份、输入、prompt、validator、plan 等兼容 | 保留预算并恢复 |
| resume | 任一关键指纹改变 | `resume_identity_mismatch`，输出差异字段，不覆盖身份 |
| resume | 已耗尽目标 invocation | `resume_exhausted_invocation`，列历史最后有效尝试，零新增调用 |
| fork_authoring | 来源研究 checkpoint 完整且绑定目标一致，新目录为空 | 导入研究证据，重新编译全部写作计划与 receipt |
| fork_authoring | 来源只有文件名，没有可信 digest/manifest | `research_import_unverifiable`，停止 |
| 旧 V1 身份 | 缺少引擎指纹 | 允许只读诊断；不冒充严格 resume 兼容，可显式 fork |

### 5.4 修改位置与伪代码

在 `autonomous_method_agent.py` 中，**在任何 run identity、snapshot 或 authoring artifact 写入之前**执行目录准入；将当前 `write_run_identity()` 的无条件写入改成 create-or-validate。输出目录的研究阶段重用与 authoring 阶段重用必须受同一决策对象约束。

```python
# 拟新增：代码组织示意，不是现成函数
request_identity = build_execution_identity(engine_root, target_snapshot, inputs)
decision = validate_run_open(out_root, requested_mode, request_identity)
if not decision.allowed:
    return persist_external_diagnostic_without_mutating_run(decision)

with acquire_run_lease(out_root, execution_id=decision.execution_id):
    # 预检与加锁之间可能有另一个进程创建 run，必须在锁内复查。
    decision = validate_run_open(out_root, requested_mode, request_identity)
    if not decision.allowed:
        return persist_external_diagnostic_without_mutating_run(decision)
    identity = create_or_validate_identity(out_root, decision.identity)
    run_product(identity=identity, ...)
```

诊断写入 stdout 或用户指定的新诊断目录；不能为了报告“拒绝 resume”先覆盖旧 run summary。run lease 采用已有可复用的文件锁机制；若需创建 lock 文件，目录准入明确只忽略该保留锁文件，或者把锁放在父级专用锁目录。不可用“目录已存在”同时充当锁和完整执行身份。

### 5.5 fork 不等于复制旧写作结果

允许导入的最小集合是经过核对的 repo snapshot、source manifest、research checkpoint、facts/claims/closures 与其依赖。新 run 写入 `research_import_manifest`，记录 parent execution、源路径（诊断用）、源内容 digest、验证结果。

旧 Writer/Realizer acceptance 不自动导入为新 accepted。后续优化缓存复用时，需单独建立 imported-result receipt，验证 artifact、plan、prompt、validator、source identity 全部一致；本轮不为了省调用贸然实现跨身份内容复用。**既保留昂贵研究成果，又得到干净写作验证，才是 fork_authoring 的目的。**

### 5.6 测试

同目录 new 拒绝；原身份 resume 成功；引擎变、未提交内容变、作者 statement 变而 ID 不变、模型/prompt/validator 变分别拒绝；研究 fork 不携带任何旧 invocation attempts；fork 失败不留下“已授权可继续”的半成品身份；并发两个进程抢同一 run 只能一个进入。

---

## 6. WP2：作者意图真正到达 Writer，而不是只保留 ID

**优先级 P0/P1；依赖 WP0，live 依赖 WP1。**

### 6.1 修复不是只扩充白名单

把 `ordered_story_node_ids` 放进请求仍不够：ID 不是写作内容。需要在编译期把本页涉及的 story/argument/intent atoms 解析成小而完整的局部语义对象，Writer 不需要全书式全局 intent，也不应该只看到空 ID。

拟新增页内 `author_intent_surfaces`：

```json
{
  "surface_id": "稳定的局部对象身份",
  "story_node_id": "原作者 story 身份",
  "author_statement": "实际作者说明，非模板占位符",
  "intended_role": "architecture 或 training 等已有角色语义",
  "local_reader_goal": "该项需要回答的具体问题",
  "authority_surface": "author_specification",
  "implementation_status": "supported | partial | unresolved | mismatch",
  "supporting_detail_ids": [],
  "unresolved_points": [],
  "source_content_digest": "原始语义内容摘要"
}
```

字段名和枚举应与仓库现有 authority 类型对齐；不要为名称不同造第二套权威等级。

### 6.2 明确传递路径

`build_intent_narrative_plan_v4` 构造/引用局部 surfaces → `project_intent_plan_to_narrative_v3` 保留其引用和摘要 → 预算拆分按 ownership 分配 → `_writer_section_inputs_v2` 只解析本页所需 surfaces → `_compact_writer_narrative_plan_for_llm` 和 `_llm_visible_section_payload` 保留局部内容及权限，不只保留 section reader_goal → 实际 provider-request 测试断言。

完整作者意图仍留在上游 canonical artifact；页中只传所需条目。支持 Writer 的局部读取要通过有范围、有费用记录的 research callback，不直接塞全仓库或无界搜索。

### 6.3 槽位与可写段落分离

保留 story/argument coverage 表，但不要再默认“一 slot = 一个必须输出的 paragraph”。在 `intent_narrative_compiler.py` 内、生成最终 paragraph ID 之前新增拟议函数：

```python
compile_authoring_units(slots, *, intent_surfaces, detail_bindings)
```

将每个 slot 分类为：

- **grounded content：** 有具备有效来源的 detail/proposition 或可消费公式，生成具体局部写作任务。
- **author specification：** 有真实作者说明但实现依据不足；按输出策略生成明确限定的作者设计描述，或留在 annotated candidate，绝不能伪装成已验证实现。
- **expository bridge：** 仅承担上下文/过渡作用，允许不引用具体实现，但不得新增架构、数值、算子等事实。
- **structural-only / unresolved：** 仅目录、空槽或无法解析的作者项，不强制独立正文；保留在 coverage/unresolved 中，不能静默删除其 must-cover 义务。

合并规则：同 section、相容 authority、相近局部问题、可合并依赖的连续项才可合并；跨 training/architecture 等不同语义角色时，不因同一个 mechanism 就硬合并。合并后记录 `source_story_ids` 和 `source_slot_ids`；多条作者意图可以在一个段落共同实现。

### 6.4 处理零匹配 fallback

`_best_slot()` 可以继续用于确定性的组织 tie-break，但返回值必须同时带 `match_basis_ids` 和 `binding_status`。零匹配不能直接变成 required implementation paragraph。

建议将返回值变为内部 typed decision，而非裸 slot：

```python
@dataclass(frozen=True)
class SlotBindingDecision:  # 拟新增
    slot_id: str | None
    overlap_ids: tuple[str, ...]
    status: Literal["grounded", "organizational_fallback", "unresolved"]
    needs_research: bool
```

对 must-cover implementation detail：没有可解释归属时保留为 unresolved obligation，并进行一次有预算的定向绑定/研究；不是无限循环。对非必需细节可进入 supporting pool。source authority 与 narrative placement 分开存储：detail 可以是真的，但放在架构段落里讲训练损失仍然不合适。

### 6.5 权威判断不能只看 mechanism 是否存在

当前 `surface` 判定允许机制身份和 partial binding 影响 `repository_statement`。修复时应要求正文中实际实现性陈述有细粒度证据支持；`mechanism_id` 和 slot 命中本身不提供这种授权。

对于作者意图有但实现缺失的项，沿用 candidate/verified 边界：candidate 可以暴露缺口，verified 不可发布为实现事实。不得用“所有段落必须有 detail”这一过强门禁误杀合法过渡和问题定义；应按上面的 paragraph kind 分流。

### 6.6 意图 digest

替换当前 `_digest(story_node_id...)` 的不完整上游指纹，覆盖稳定序列中的 statement、role、priority、linked claims/obligations、有效 notes、组织顺序及所引用 intent atom 内容。排除运行时间、绝对路径等非语义项。`source_intent_digest_version` 要明确变化；历史摘要不原地改写。

### 6.7 验收

真实失败页的 15 个槽不再全部成为“相同 reader_goal + 空证据 + 必须补正文”的任务。每个 must-cover story 有且只有明确的 rendered / combined / author-specification / unresolved 等可审计去向。修改作者 statement、保留 story ID 时，intent digest 和相关请求 fingerprint 必须改变。用实际 provider-request fixture 验证，不能只测 V4/V3 模型里字段仍在。

---

## 7. WP3：统一 Writer、Binder 与 repair 的 witness 责任

**优先级 P0/P1；依赖 WP0/WP2 的字段边界。**

### 7.1 一个 canonical contract，两种有名投影

保留完整 `witness_contract` 作为最终事务权威，显式生成：

```text
CanonicalParagraphContract
    ├─ writer_projection：段落、detail 内容义务、公式消费、局部意图/权限
    └─ binder_projection：atom、condition、polarity、interface、exact spans、最终关系校验
```

修改 `section_writer.py` 的 `_compact_writer_witness_contract_for_llm()`，使其与 `_compact_writer_binding_contract_for_llm()` 采用同一个责任划分。不能一边提示“atom 由 Binder 负责”，一边把 atom 作为 Writer 必填 witness。

### 7.2 两阶段验收，而不是降低最终门禁

拟增加 `validation_stage`：

- `writer_content`：段落身份/范围正确，正文非空，detail 有内容实现及明确绑定，公式按消费协议处理，不引入无权事实；不要求 Writer 自己枚举全部 atom witnesses。
- `final_bound`：对实际最终正文执行完整 atom/条件/极性/接口/公式等校验，绑定必须来自确定性 Binder 或可审计的语义验证，不能仅采信模型自报。

Writer 通过第一阶段不允许绕过最终验证。最终验证规则变更要更新 validator digest。避免在现有调用点之外再串一个与 `assess_paragraph_transaction()` 重复且结果可能相反的判定器；统一实现并输出分层报告。

### 7.3 EBCAR 两个 detail 的定向修复语义

repair packet 至少包含：失败 paragraph、target kind、canonical target ID、缺失原因类别、同页授权语义/证据引用、原正文、允许修改的段落集合、不得改变的已接受段落 digest。

```json
{
  "repair_kind": "missing_detail_witness",
  "paragraph_id": "MA-S3:P1__f1",
  "missing_targets": [
    {"kind": "detail", "id": "detail:mech_sym:f6cf5bdfe2ae16f0:15"},
    {"kind": "detail", "id": "detail:mech_sym:f6cf5bdfe2ae16f0:76"}
  ],
  "allowed_edits": ["paragraph_content", "detail_witnesses"],
  "preserve_other_paragraphs": true
}
```

这只是结构示例，不能把本文英语描述写入程序当作自动修复正文。若 detail 76 的叙事归属本来不正确，先进行 plan revision，再 fork/recompile；不能硬让 Writer 在错误段落加一句话来过门。

### 7.4 不把 atom 声明自动升级成 detail 接受

可以使用 atom witness 帮助 Binder 定位候选 span，但仅从 `atom:` 字符串提取父 detail ID 不能证明 detail 的完整语义成立。需要对该 detail 的必要条件、操作、输出及方向做核对；无法确定则返回细分错误，让 owner 修复。不能“见到任一 atom 就认为 detail 已写”。

### 7.5 错误码结构化

替换只依赖拼接字符串的机器判断，新增对象字段：

```python
class ContractFailure(BaseModel):  # 拟新增
    code: str
    stage: str
    paragraph_id: str | None
    target_kind: str | None
    target_id: str | None
    expected: str | None
    observed: str | None
    repairable_by: str | None
```

至少区分 `paragraph_missing`、`detail_witness_missing`、`exact_span_not_in_body`、`detail_semantic_mismatch`、`target_out_of_scope`、`authority_surface_violation`、`formula_consumer_mismatch`、`input_material_missing`。显示层可以继续输出旧摘要字符串，执行层不要解析 `detail:detail:` 推断身份。

### 7.6 输出 schema 减负

当前响应可同时包含完整 `section_markdown` 与逐段 `paragraph_markdown`，存在正文重复输出。页级新协议建议以有序 paragraph 对象为唯一正文真源，section Markdown 由确定性 composer 拼接。兼容 `PublicationMethodSectionOutputV1` 的适配层可以派生 section text，但要声明是派生物，不让模型重复生成。

动态 schema 应限制 paragraph ID 集合，并在本地校验每个 required ID 恰好一次。数组 `enum` 只限制元素取值，并不保证所有 ID 都出现。可选固定键对象 schema 或支持的数组 cardinality 约束；需要先针对实际 provider 能力做合同测试，不能假设所有 JSON Schema 关键字都生效。无论 provider 支持何种 schema，最终本地闭集校验都保留。

### 7.7 测试

缺 detail、有 atom 的真实响应不能被旧错误类别掩盖；Writer 视图不再要求 Binder-owned atom；最终 atom 缺失仍失败；错误 target、错 paragraph、非正文 substring、同句错误指代、否定/比较方向相反全部保留负例；repair 只改指定段落，其他正文 digest 不变。不要只新增两个“合法英语句子”的正例来放宽词法匹配。

---

## 8. WP4：联合输入与输出工作量的页契约

**优先级 P1；在 WP2 完成后定稿参数。**

### 8.1 扩展位置

在 `unified_context_compiler.py` 的 `extend_writer_worksets_from_narrative_plan()` 内，扩展 `_build_section_pages()` 的 candidate 评估；`fit_narrative_plan_to_page_budget()` 继续负责原子段落闭包是否需要 fragment。**先尝试拆 page，不先增加 paragraph fragments。**

不得仅在 V3 层拆段后让 packer 又把全部片段装回同一个 join page；新的 output workload 检查必须在最终 candidate page 和实际请求 surface 上运行。

### 8.2 新增纯函数（拟议）

```python
estimate_writer_output_workload(
    paragraph_contracts,
    *,
    response_protocol,
    calibrated_profile,
    tokenizer,
) -> WriterOutputWorkloadV1
```

结果至少包含：语义段落数、required detail occurrences、Writer-owned witness 数、公式消费次数、最低 JSON 编码开销、目标正文量、预计输出 tokens、估计依据/版本、置信/未知原因。Binder-owned atom 不应错误计入 Writer 输出负担。

估计可表达为：

```text
estimated_output = response_structure
                 + Σ(paragraph_prose + local_detail_bindings + formula_refs)
                 + safety_reserve
```

输入可计算开销与经验正文估计分开；初始经验系数是配置，不宣称数学保证。既保留 `input + output_reserve + safety <= context_window`，又检查预计输出工作量和事务复杂度。对于看似能容纳但历史漏段率高的页，可设置显式 `max_semantic_paragraphs_per_page`；初始 4–6 仅可作为待标定候选，不能写死成普遍正确值。

### 8.3 打包算法

```python
# 拟议算法；复用现有 closure、payload 与 input accounting 实现
for unit in ordered_authoring_units:
    proposed = current_page + [unit]
    check = evaluate_page_contract(proposed, input_budget, output_budget)
    if check.fits:
        current_page = proposed
        continue
    if current_page:
        flush(current_page)
        current_page = []
    single = evaluate_page_contract([unit], input_budget, output_budget)
    if single.fits:
        current_page = [unit]
    else:
        revise_atomic_unit_or_return_typed_block(unit, single)
flush(current_page)
```

纯结构项、author specification 项不因无 archive atoms 就被偷偷塞到第一页；其输出成本同样计量。原有 `_flush_current` 以 atoms 非空作为条件的路径需要覆盖“合法无实现 atom 的组织段落”测试，不能漏掉 header/bridge 页面。

### 8.4 排序与闭包

使用 narrative ordinal 保持 paragraph 顺序；不要用字符串排序决定 `P1/P10/P2` 的正文顺序。page metadata 可以保留排序后的 ID 集合作诊断，但正文组合只使用明确顺序。

公式依赖闭包不可拆；共用证据可以在不同页重复可见，但 source/authority 不增加。对同一 detail 在不同段落的独立义务按 occurrence 计数。新 page ID 及 plan digest 必须变化；旧页的预算不重置为同页新尝试，而作为旧 plan 留存。

### 8.5 全 run 预算重新准入

page 数增加会增加 Writer 和可能的 Realizer 调用量、输入重复和 retry reserve。分页成功后必须重新建立 invocation plan、lookahead reservation 和 admission，再允许第一条请求。不得以“只是拆页”为理由越过 whole-run budget；不足则返回 `run_budget_insufficient_after_repage`，而非截掉剩余页。

### 8.6 验收

EBCAR 事故 fixture 的空任务问题首先被 WP2 解决；剩余真实写作任务经联合评估形成可解释页面。不得把“固定等于 2 页或 3 页”写成正确性标准。正确标准是所有 live pages 满足声明预算，段落/义务/公式归属守恒，模型实际请求与预检输入同源。

---

## 9. WP5：重试、拒发和恢复的可解释账本

**优先级 P0/P1；依赖 WP1，保持现有 whole-run budget。**

### 9.1 已有行为与修复范围

`publication_method_writer.py` 的调用边界使用 `last_started_attempt(ledger_root, invocation_id) + 1` 决定 attempt，并检查 `max_attempts`。本次拒发仍形成后续 attempt 记录，使“事件序号”和“实际内容试验次数”混在同一个数中。`unified_invocation_ledger.py` 已有全 run 成本/未完成 reservation 的严格核算，不能绕过或推倒重写。 [C1][C8]

### 9.2 分开三个计数

保留不可变 `event_seq`；新增或派生：`provider_send_count`、`content_attempt_count`、`content_repair_count`。历史字段 `attempt` 原样保留并标明 legacy_event_ordinal。拒发可以记录诊断事件，但不能算作新的 provider send 或内容修复。

限流/网络重试不是“免费无限重试”：它应受单独 transport policy 和 run 费用/调用上限控制。已发送但超时且无确认属于 `send_outcome_unknown`，保留 reservation，不能当成未发送自动退款或重发。

### 9.3 恢复入口先做 preflight

在进入 Writer 主循环前，列出当前 plan 所有待执行 invocation 的：有效 accepted 结果、最后发送、最后内容失败、剩余内容尝试、pending/unknown 状态、身份匹配。发现已耗尽必需页时，直接返回包括原因的结构化阻断，不走到 `_capturing_writer_caller` 后才写 attempt-0005。

```json
{
  "code": "resume_exhausted_invocation",
  "execution_id": "...",
  "invocation_id": "...",
  "content_attempts_used": 2,
  "content_attempt_limit": 2,
  "last_content_failure_codes": ["detail_witness_missing"],
  "last_provider_attempt": 2,
  "rejected_before_send_events": [3, 4],
  "allowed_next_action": "fork_authoring_with_new_contract"
}
```

旧错误 `acceptance_count:0` 可以保留为低层不变量错误，但 run summary 要呈现上面的根因链。

### 9.4 接受结果选择

严格使用当前 execution、plan、archive、workset、page、prompt、validator 和对应 receipt/fragment 身份匹配。不能取“最新 JSON”“最后一个非空文本”或“任意 accepted=true”。有效内容接受结果有且只有一个被当前 resolved snapshot 选中；两条互不相同且都声称当前有效时，返回冲突，不随机选。

已有 `read_writer_content_acceptance()` 的检查继续保留，新增字段纳入同一比较；历史 records 缺少新字段时不能推断通过。旧 rejected 文本可用于新 fork 的诊断输入，但必须标记 `untrusted_prior_candidate`，不能充当代码依据。

### 9.5 持久化与崩溃点

保持单 run lease（本轮优先单写者，避免同时构建复杂分布式系统）。事件 reserve/start/request/response/completed/acceptance 的顺序明确；reservation 和发送前身份检查在同一个受锁临界区完成。

测试崩溃点：reservation 后未 send；send 后没有 response；response 后未 completed；completed 后未 acceptance；accepted 后尚未更新 index。恢复必须能够重建确定性验收或报告 uncertainty，不能重复计费/丢 reservation。对 corrupt JSON、unknown plan 和缺 receipt 不按空集合处理。

### 9.6 禁止的修复

禁止 `rm -rf invocations`；禁止直接把 `max_attempts` 从 2 改为 20 作为根因修复；禁止 SHA 自动改变就静默开新预算；禁止把 pre-send failure 改为 success；禁止用旧 provider response 手写 accepted receipt。

---

## 10. WP6：产物索引、修订与合同一致性

**优先级 P1；依赖 WP1。**

### 10.1 索引是新增解析层，不是重命名全部历史文件

拟新增 `authoring_artifact_index.py`，用 `(logical_role, phase, generation)` 作为记录键。**schema version 只描述数据格式，不描述新旧顺序。**

```json
{
  "schema_version": "1.0",
  "execution_identity_digest": "...",
  "index_revision": 3,
  "entries": [
    {
      "logical_role": "consumer_workset_manifest",
      "phase": "formalizer",
      "schema_version": "2.0",
      "generation": 1,
      "path": "06_authoring/consumer_workset_manifest_v2.json",
      "status": "valid_empty",
      "semantic_digest": "...",
      "file_bytes_digest": "...",
      "upstream_digests": {}
    },
    {
      "logical_role": "consumer_workset_manifest",
      "phase": "writer",
      "schema_version": "2.0",
      "generation": 2,
      "path": "06_authoring/consumer_workset_manifest_v2.writer.2.json",
      "status": "active",
      "semantic_digest": "...",
      "file_bytes_digest": "...",
      "upstream_digests": {"narrative_plan": "...", "archive": "..."}
    }
  ],
  "active": {
    "consumer_workset_manifest:formalizer": "记录身份",
    "consumer_workset_manifest:writer": "另一记录身份",
    "narrative_plan:authoring": "预算修订后的记录身份"
  }
}
```

示例中的路径是兼容旧布局，不代表新索引已经存在。两个 `digest` 的含义不同：语义模型自带 digest 与实际文件字节 digest 不应混用。

### 10.2 读取协议

新调用方统一使用 `resolve_artifact(index, role, phase, expected_digest=None)`。缺少 phase 时不得悄悄选择 Writer；存在多个 active generation 时错误；文件不存在、摘要不符、路径逃逸 root、upstream 不一致均阻断。不能用 mtime、无后缀文件名或目录字典序推断当前对象。

consumer 已持有精确 digest 时按 digest 解引用；当前指针只用于发现，不得替代已冻结的上游引用。生成新 plan/manifest 时先写不可变对象并验证，再原子发布 index revision；发布失败保留未引用对象，不让半写对象成为 active。

### 10.3 最终执行快照

每个阶段开始前生成 `resolved_authoring_snapshot`，固定本阶段使用的 plan、archive、manifest、prompt、budget、contract；reader 不在执行中反复读取可变 active pointer。完成后另写完成状态，不修改已执行的输入 snapshot。

### 10.4 历史迁移

旧 run 只读构建 `legacy_import_report`：根据文件内部 digest、parent/source 字段和 phase 检查推断关系；文件名仅作候选发现。出现歧义、同 revision 不同内容、无法验证上游时标 `ambiguous`，不替用户选一个。旧 `.legacy_source` 与正式文件字节相等不自动证明有害，但新 run 不再额外存储语义不明确的“备份”；必须注明其角色是 compat projection、source snapshot 还是历史引用。

### 10.5 合同统一

`build_authoring_run_contract()` 与 `validate_authoring_run_contract()` 共享一个 required-key evaluator：

```python
# 拟议规则
required = expected_keys_for(stage, selected_plan, output_lane)
validated_na = validate_not_applicable_proofs(not_applicable, required)
missing = required - actual_valid_entries - validated_na.keys()
```

N/A 必须有原因和 proof，例如“该正式公式义务集合为空”，不能调用方随便填字符串跳过要求。not-yet-produced、blocked、N/A 和 valid-empty 分开。`allow_blocked` 应明确用于“允许不完整状态被记录/展示”，不能作为“允许发布 verified”的后门；或弃用参数并迁移调用者，不能继续无效占位。

旧 builder 的 `Path.is_file` 可以用于发现，不能作为最终 valid 标准。stage-specific required keys 不再写死必须 `.writer.2` 或 `.v1.2`。

---

## 11. WP7：单次计划选择、依赖失败前置与有限代码拆分

**优先级 P1/P2；不作为新 live 前无限延伸的重构任务。**

### 11.1 计划选择在构建前完成

当前 `_build_narrative_plan_v3()` 先调用 legacy builder，随后创建 V4 envelope；主流程在 `selected_plan_version == "v4"` 时用投影覆盖前者。改为拟新增轻量选择入口：

```python
build_selected_narrative_plan(selection, *, contexts, story_spine, prior_plan, ...)
```

- selection=v4：只构建 V4，再做一次兼容 V3 projection。
- selection=v3：只构建 legacy V3。
- 显式 shadow 模式：两者都构建但仅一个可执行；shadow 所有 LLM 请求必须单独声明预算与 trace。

不要删除 legacy builder 作为兼容功能；删除的是默认 V4 路径上不需要的执行。当前 V4 编译遇 TypeError/ValueError 已按选中状态 re-raise，这一 fail-closed 行为要保留，不能重构后引入静默 fallback。

### 11.2 必需依赖失败尽早暴露

`publication_method_writer.py` 在 Writer aggregate 之后调用 `_run_unified_v2_realizer_phase()`，并执行后续 delivery/audit。将 Writer 必需页面的接受/缺口检查集中在明确的 phase boundary，避免最后才报 `writer_v2_invocation_acceptance_count`。

实现前区分 Realizer 两种真实任务：依赖 Writer 正文的处理，必须以有效 Writer content receipt 为前置；若是独立的 evidence realization，不能一概禁止提前执行，但必须标注为独立预计算并绑定 archive/plan，不能在 Writer 不完整时伪称全产品完成。本轮不凭文件存在断言全部 Realizer 调用都是浪费。

对局部失败，允许保留已接受的独立页及诊断，但 selected section output、clean candidate 和 verified 的发布策略必须明确。阶段阻断写 `blocked_by_stage`、`primary_cause`、`downstream_not_run`，而不是用缺失下游 receipt 覆盖根因。

### 11.3 修复已有点的回归保护

当前源码已有 `_canonical_realizer_detail_id()`、`_realizer_detail_scope()`、`_ordered_candidate_rows_preserving_input()` 等边界修复。不要把用户历史报告里的每个错误都当作当前 HEAD 尚未处理；保留并补测试。对于 Namespace/model_dump 故障，统一在模型边界转换：正式 typed model 或显式 Mapping adapter；不要在十几个消费点新增 `hasattr` 分支掩盖模型不一致。

### 11.4 有限拆分 publication_method_writer

只有在上述行为测试固定后，才把新 identity admission、artifact resolver、contract projection 或 shared send boundary 从大文件提取为小模块。优先单一职责、纯函数，保留公共入口。不要在同一个 PR 中同时移动数千行和改变内容语义，否则难以定位回归。

---

## 12. 回归与验收测试矩阵

以下均为**拟新增测试**；本次审计没有在 Code2Paper 源码上执行这些测试。

| 测试文件 / 用例 | 输入 | 预期 |
|---|---|---|
| `test_archived_failure_facts.py::test_attempt4_is_not_a_new_content_trial` | 真实 attempt 4 | sent=false，原因4>2；不计内容试验 |
| `...::test_s3_is_15_of_16` | section/aggregate receipts | S3不完整，不因目录齐全变成功 |
| `...::test_attempt2_missing_detail_not_atom` | 真实 acceptance/response | 两 detail 未声明，不能用atom数替代 |
| `...::test_target_sha_is_not_engine_sha` | RunIdentity + RepoSnapshot | 正确区分目标/引擎 |
| `test_execution_identity.py::test_new_rejects_nonempty_root` | 已有 ledger | 零模型调用、旧文件不变 |
| `...::test_resume_preserves_budget` | 相同完整身份 | 不重置计数 |
| `...::test_dirty_content_changes_same_status` | 同路径均为M、内容不同 | engine digest不同 |
| `...::test_intent_text_change_same_ids` | story IDs不变、statement变 | intent/请求身份改变 |
| `...::test_fork_imports_research_not_acceptance` | 旧研究快照+失败写作 | 新执行没有旧attempt，证据可追溯 |
| `test_intent_writer_surface.py::test_actual_request_contains_local_intent` | V4→V3→page→LLM projection | 局部作者内容/权限保留，不是只保留ID |
| `...::test_empty_slots_not_forced_as_technical_paragraphs` | 事故15空槽 | 有明确分类/归并/缺口，无虚假完整正文任务 |
| `...::test_zero_overlap_not_repository_authorization` | 无handle交集 | 仅组织fallback，不升级证据 |
| `...::test_must_cover_survives_coalescing` | 多story合一段 | 每项都有明确归宿 |
| `...::test_training_detail_not_forced_into_architecture` | role冲突且同mechanism | 返回放置决策/缺口，不硬塞 |
| `test_witness_projection.py::test_writer_binder_ownership_consistent` | 全量canonical合同 | Writer两表面一致，Binder targets保留 |
| `...::test_atom_does_not_auto_complete_detail` | 仅一atom span | detail仍不足 |
| `...::test_final_bound_checks_polarity_and_conditions` | 方向/条件反例 | 最终失败，不因关键词重合通过 |
| `...::test_repair_keeps_unmodified_paragraph_digests` | 单段repair | 其他段落字节不变 |
| `test_output_feasibility.py::test_packing_checks_output_workload` | 多段低输入量 | 能因输出负担拆页 |
| `...::test_header_page_has_nonzero_output_workload` | 无atom合法bridge | 不漏页，不视为零成本 |
| `...::test_paragraph_order_is_numeric_ordinal` | P1/P2/P10 | 按计划ordinal，不字典序 |
| `...::test_occurrence_and_formula_closure_conserved` | 共享detail/跨操作公式 | 归属正确或明确不可拆阻断 |
| `...::test_repage_rechecks_whole_run_budget` | page数增加 | 不越过调用/输入/repair预算 |
| `test_ledger_recovery.py::test_presend_reject_is_diagnostic_event` | 耗尽resume | 不再产生伪provider attempt |
| `...::test_unknown_send_retains_reservation` | 发送后崩溃 | 不自动退款/重发 |
| `...::test_acceptance_crash_replays_validator_only` | completed存在acceptance缺 | 可重建验收，不重复模型调用 |
| `...::test_two_writers_one_lease` | 两进程同root | 单写者 |
| `test_artifact_index.py::test_formalizer_empty_and_writer_active_coexist` | 空基础+真实writer | 两角色各自可解析 |
| `...::test_ambiguous_active_or_bad_digest_fails` | 冲突/改坏文件 | 不猜current |
| `...::test_na_builder_validator_agree` | 正当N/A和假N/A | 同一评价、假N/A被拒 |
| `test_phase_boundaries.py::test_writer_failure_not_masked_by_realizer` | 必需writer拒绝 | 根因明确，不发布完成产品 |
| `...::test_v4_does_not_call_legacy_builder` | selection=v4+spy | legacy调用0次 |
| `...::test_selected_v4_compile_failure_stays_failure` | V4编译失败 | 不静默fallback |
| `test_authoring_end_to_end_offline.py` | 冻结证据+fake provider按页响应 | 从plan到candidate/verified状态全链一致 |

### 12.1 测试运行方式

仓库 `pyproject.toml` 已定义 `testpaths=["tests"]` 与 `live_llm` marker。实现后，在隔离工作树中运行：

```bash
python -m pytest -q tests/regression_20260917 -m 'not live_llm'
python -m pytest -q -m 'not live_llm'
```

新目录尚不存在时第一条不能执行；这些不是“当前已通过”的命令记录。marker 不是安全沙箱，offline tests 还必须让 provider stub 拒绝真实网络，并确认所选既有测试未通过其他路径调用 endpoint。环境缺依赖时记录准确阻断，不把 collect失败当作test通过。

### 12.2 冻结 oracle，避免为新规则改答案

真实 attempt 2 是“当时合同下拒绝”的历史事实，不应通过改 fixture 把它写成当时已经 accepted。新 owner 划分下可以生成新的 validation report，明确 new validator identity 和 new contract；新报告不覆盖历史 acceptance。

语义反例必须先建立再调规则，包括：相反 attention mask 方向、凭空引入 gating scalar、训练/推理路径混淆、平均损失与求和混淆、作者目标被当成实现事实、共享证据出现在错误段落。对原实现尚未完成核验的具体 EBCAR 句子，先取得 source span 再写 ground truth；不能根据本报告的怀疑直接标成 false。

---

## 13. 分阶段提交与验收门

| 阶段 | 建议独立提交主题 | 依赖 | 准出标准 |
|---|---|---|---|
| S0 | `test: freeze 20260917 authoring incident fixtures` | 无 | WP0事实回归固定、原归档不变 |
| S1 | `fix: separate engine identity and guard run resume` | S0 | new/resume/fork准入，旧身份不被覆盖 |
| S2 | `fix: preserve local author intent at writer boundary` | S0/S1 | 实际请求有局部意图；15空槽有明确处理 |
| S3 | `fix: unify writer and binder contract ownership` | S2 | detail/atom责任一致，最终负例不退化 |
| S4 | `feat: budget writer pages by input and output workload` | S2/S3 | 最终page联合预算、全run重新准入 |
| S5 | `feat: resolve authoring artifacts by phase and digest` | S1 | 空formalizer合法；writer current唯一；N/A一致 |
| S6 | `fix: expose retry exhaustion and phase dependency causes` | S1/S3/S5 | 拒发不伪装新试验；崩溃恢复与根因链通过 |
| S7 | `refactor: select one narrative planner per execution` | S2/S5 | V4路径legacy调用为0；无静默fallback |
| S8 | `test: validate fresh authoring and failure injection` | S0–S7 | offline端到端、性质与故障注入通过 |
| S9 | 新身份真实验证及质量评估（非代码提交名） | S8 + 明确授权 | 第14节条件全部满足 |

这些是准入关系，不是要求八个 agent 同时修改大文件。S2/S3/S4 都会触及 plan/Writer 字段，必须串行集成或明确唯一负责者，避免各自定义不同 contract。

---

## 14. 真实模型验证协议

### 14.1 允许进入 live 的必要条件

固定实现提交与 engine source digest；工作树修改已纳入身份；offline全链通过；doctor无critical阻断；模型、tokenizer、prompt、profile、validator身份冻结；完整run预算和失败停止条件明确；新out目录及execution_id；目标仓库和作者材料身份一致。

对于用户描述的 bwrap 环境，每一次需要访问宿主资源/沙箱外 endpoint 的命令单独走授权。不能认为前一条 `danger-full-access` 覆盖后续命令；本方案也不把“允许开发”当作无限 live 权限。

### 14.2 三层 live，而不是只跑整套看最后一个错误

**L1：失败局部任务重验。** 通过公开的同一 production input builder/contract 编译链，生成事故相关 paragraph/page 的新身份任务；不能手工造简化 prompt 绕过真实投影。测试确定性可行性、detail责任和局部意图，记录真实完整请求、返回、usage与验收。

**L2：EBCAR authoring fork。** 导入已校验研究证据，在新目录重做整个 authoring。检查所有section、所有writer和需要的realizer/binder依赖、composer、candidate/verified状态与索引。此层不等价于重新运行 Research。

**L3：端到端 fresh + 跨项目回归。** 重新Research到最终输出，并选择至少一种机制复杂/公式丰富、一种多作者组织节点、一种明确证据不足的案例。项目集合及预算在运行前冻结，不用只成功的项目证明泛化。

L1通过不能宣称L2/L3通过；L2失败不得清ledger继续把它标为同一修复验证的成功运行。保持失败身份，修复后再明确fork。

### 14.3 质量验证

同时报告运行正确性和学术质量，不能只报 `accepted_pages / pages`。

| 维度 | 建议测量 |
|---|---|
| 意图覆盖 | must-cover story 的有依据实现、作者限定描述、未解决、错误位置比例 |
| 信息利用 | 冻结的核心detail/条件/边/公式在最终正文中的实际消费与正确性 |
| 忠实性 | 无依据新增陈述、authority误升级、训练/推理混淆、公式/方向错误 |
| 叙事质量 | 段落局部问题清晰、角色位置正确、无15个模板填充段、重复率、连贯性 |
| 恢复健壮性 | 拒发/429/崩溃/预算不足后状态可解释，不重复送、不隐式刷新预算 |
| 效率 | 首次content接受率、repair收益、发送调用数、真实输入/输出tokens、无效调用量 |

质量比较至少包括同一冻结输入、同一模型配置的旧候选（若存在）、新候选和可取得的独立 baseline。事故归档缺少完整 clean candidate 时，不伪造旧完整输出；可以比较已存的局部响应，但必须标明范围不同。原论文作为组织/技术核对参考，不直接当作系统运行时输入，避免评测泄漏。

---

## 15. Doctor 与运行摘要：让下次不再靠读几十个 JSON 定位

### 15.1 拟新增产品 doctor

在现有 CLI 注册 `doctor` 或等价子命令，具体 parser接入由现有入口决定，不建立第二套 CLI 产品。其只读模式至少输出：execution身份是否完整、目标/引擎SHA含义、active artifacts、每阶段状态、每个待执行页的预算剩余、首个根因、downstream阻断、空语义段落数、detail/atom责任不一致数。

```text
EXECUTION       legacy identity; engine fingerprint unavailable
TARGET          EBCAR @ 287506e3...
WRITER          4/5 sections complete; MA-S3 incomplete
PAGE            751aa8b5... ; historical content attempts exhausted
LAST CONTENT    attempt 2 ; missing detail witnesses :15 and :76
LATEST EVENT    attempt 4 ; rejected before provider send
INTENT SURFACE  15 paragraph slots lack per-paragraph material
NEXT ACTION     read-only diagnosis or explicit authoring fork
```

上述是期待的诊断样式，不是本次执行了新 doctor 的输出。

### 15.2 摘要新增字段

`execution_id`、`run_open_mode`、`parent_execution_id`、engine/target/intent三类指纹、`resolved_snapshot_digest`、`primary_failure`、`failure_chain`、`sent_calls`、`content_attempts`、`rejected_before_send_events`、`unsettled_reservations`、`blocked_downstream_phases`、`artifact_index_path`、`quality_evaluation_status`。

记录真实时间使用带时区 ISO 8601 或原始unix time；不要把旧报告的“11:37”直接换算成用户当前时区。本报告未核验外部 Antigravity/task-3145 的实时状态，其429和恢复时间不进入新的run结论。

---

## 16. 风险、回滚与停止条件

**最高风险是“修好结构后放进错误事实”。** WP2 将更多作者材料送给Writer时，必须一起传authority；WP3减少Writer的atom元数据时，最终Binder必须仍校验；WP4缩小页面时，共享依赖必须保持完整。

**回滚单位是代码提交与执行身份，而不是把新产物搬回旧目录。** 在新执行尚未发布verified前，可回滚实现并新建执行；已发布对象继续保留其生产版本身份。新schema通过兼容reader读取旧对象，不原地升级历史文件。

必须停止并准确报告的情况：无法验证研究导入来源；身份不完整却请求严格resume；同一角色有多个active对象；真实输出需求无法在授权预算内分配；源代码与作者陈述冲突；required detail缺少证据；unknown send未对账；新规则导致既有语义负例通过；需要新的宿主/endpoint授权；执行文档和当前代码职责发生实质冲突。

停止不等于丢弃产物：保留已接受独立页、缺口和诊断，但不能将部分状态冒充完整候选或verified。

---

## 17. 最小完成定义与最终交接清单

本轮可宣布“修复完成”的最低条件是：新身份隔离得到测试证明；相同身份resume不刷新内容预算；EBCAR失败页的局部意图材料被保留；15空槽不再要求无依据填充；Writer/Binder责任一致且最终负例仍失败；输出工作量分页及全run预算准入生效；phase-aware产物解析不破坏Formalizer空manifest；合同N/A路径一致；单次planner选择落实；offline完整回归通过；获得授权后L1/L2完成并明确报告L3是否进行。

提交说明应包含固定代码SHA、测试命令和真实结果、未运行的测试/原因、归档不变证明、新产物位置及execution identity、失败链、真实token/call成本、质量审查发现、剩余限制。不要再写“修复后又碰到新bug”作为唯一结论；需要说明此次运行是resume还是fork，是否真的发生新的provider send，以及失败合同属于哪一个版本。

**首个开发行动：实现 WP0 的事故事实回归；随后做 WP1 与 WP2。不要先启动当前旧目录的下一轮续跑。**

---

## 附录 A：审计证据索引

所有代码链接固定到 `34ae0cf15f0ae200d863b63a8c912dc21b299626`。Artifact blob链接按Git对象内容寻址，不依赖宿主路径。编号用于本文就近引用。

### 代码

- **[C1]** [publication_method_writer.py](https://github.com/hjcui98/code2paper/blob/34ae0cf15f0ae200d863b63a8c912dc21b299626/src/code2paper/agentic/publication_method_writer.py)：规划覆盖、phase-specific manifest说明、页输入构造、调用边界、Realizer入口、acceptance count门。
- **[C2]** [autonomous_method_agent.py](https://github.com/hjcui98/code2paper/blob/34ae0cf15f0ae200d863b63a8c912dc21b299626/src/code2paper/agentic/autonomous_method_agent.py)：产品入口及target git_commit进入run identity。
- **[C3]** [authoring_context_contract.py](https://github.com/hjcui98/code2paper/blob/34ae0cf15f0ae200d863b63a8c912dc21b299626/src/code2paper/agentic/authoring_context_contract.py)：身份、dirty摘要、builder/validator N/A差异、合同写入。
- **[C4]** [intent_narrative_compiler.py](https://github.com/hjcui98/code2paper/blob/34ae0cf15f0ae200d863b63a8c912dc21b299626/src/code2paper/agentic/intent_narrative_compiler.py)：slot、零交集fallback、surface、source_intent_digest、V4→V3投影。
- **[C5]** [llm/section_writer.py](https://github.com/hjcui98/code2paper/blob/34ae0cf15f0ae200d863b63a8c912dc21b299626/src/code2paper/llm/section_writer.py)：`_WRITER_PARAGRAPH_NARRATIVE_FIELDS`及compact writer projections。
- **[C6]** [publication_transaction_contract.py](https://github.com/hjcui98/code2paper/blob/34ae0cf15f0ae200d863b63a8c912dc21b299626/src/code2paper/agentic/publication_transaction_contract.py)：paragraph transaction、exact witness、语义anchor与公式插入。
- **[C7]** [unified_context_compiler.py](https://github.com/hjcui98/code2paper/blob/34ae0cf15f0ae200d863b63a8c912dc21b299626/src/code2paper/agentic/unified_context_compiler.py)：archive、workset、输入预算修订、section packer及budget admission。
- **[C8]** [unified_invocation_ledger.py](https://github.com/hjcui98/code2paper/blob/34ae0cf15f0ae200d863b63a8c912dc21b299626/src/code2paper/agentic/unified_invocation_ledger.py)：实际请求、receipt、acceptance、whole-run budget state。
- **[C9]** [pyproject.toml](https://github.com/hjcui98/code2paper/blob/34ae0cf15f0ae200d863b63a8c912dc21b299626/pyproject.toml)：安装入口、Python与pytest配置、live_llm marker。
- **[C10]** [事故归档README](https://github.com/hjcui98/code2paper/blob/34ae0cf15f0ae200d863b63a8c912dc21b299626/artifacts/runs/2026-09-17-ebcar-intent-v4-p7-j9L1bn/README.md)：归档来源与范围。

### 真实产物

- **[A1] RunIdentity**：blob [`97ea90a58a9b48aab80f5de5ab3e2f3d1bc68135`](https://api.github.com/repos/hjcui98/code2paper/git/blobs/97ea90a58a9b48aab80f5de5ab3e2f3d1bc68135)。
- **[A2] 目标RepoSnapshot**：blob [`5dc686fbf60615d5a3167d347394b262c6b25d19`](https://api.github.com/repos/hjcui98/code2paper/git/blobs/5dc686fbf60615d5a3167d347394b262c6b25d19)。
- **[A3] 失败页attempt 2实际request**：blob [`f255dcecba1bc7be428af5b01629cdb7f394e324`](https://api.github.com/repos/hjcui98/code2paper/git/blobs/f255dcecba1bc7be428af5b01629cdb7f394e324)。
- **[A4] 失败页attempt 4 completion**：blob [`115380a8556a78bf96ee06fd03ebfb27fbbdb9f6`](https://api.github.com/repos/hjcui98/code2paper/git/blobs/115380a8556a78bf96ee06fd03ebfb27fbbdb9f6)。
- **[A5] Writer section receipts**：blob [`50bf4882d734e55cbabaad35469214f0572ff9a2`](https://api.github.com/repos/hjcui98/code2paper/git/blobs/50bf4882d734e55cbabaad35469214f0572ff9a2)。
- **[A6] Writer aggregate receipt**：blob [`0cebc1cf947b8d0d3653b855e79b9c3d3c14f039`](https://api.github.com/repos/hjcui98/code2paper/git/blobs/0cebc1cf947b8d0d3653b855e79b9c3d3c14f039)。
- **[A7] 失败页attempt 2 content acceptance及完整响应**：blob [`a53a31940e3b06480fde5f984ad66bd861b1a676`](https://api.github.com/repos/hjcui98/code2paper/git/blobs/a53a31940e3b06480fde5f984ad66bd861b1a676)。

### 证据使用限制

本报告核对了上述核心代码/产物及相关调用片段，但没有把整个仓库每个文件逐行读完，没有执行原始项目测试，也没有验证外部调度器当前状态。某些建议是从已核实的边界缺口推导出的设计，而不是已经动态复现的额外故障。新字段/新CLI/新测试均需按阶段实现，不能将它们当成固定HEAD已有能力。

---

模型：GPT-6 Astra Pro｜Reasoning level：高
