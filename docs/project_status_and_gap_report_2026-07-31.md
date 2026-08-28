# Code2Paper 项目进度与目标差距报告

- `as_of`: 2026-08-02
- `status`: R8 六个真实项目 6/6 accepted；clean-checkout release freeze 待完成
- `analysis_basis`: R8 已实际通过，不再使用“假设通过”口径；权威摘要见
  [`r8_acceptance_status_2026-08-01.md`](r8_acceptance_status_2026-08-01.md)
- `scope`: 自主代码研究、Method 写作、证据约束、图示与产品切换
- `supersedes`: 仅取代旧报告中的“当前项目状态”表述，不改写其历史实验记录

## 结论

R8 六项目已经全部通过，但项目并不是“全部完成”，而是完成了最重要的一次
已知项目运行演练：live Agent、checkpoint、当前证据门、completion 和 readiness
能够在同一长流程中运行。它不能证明自主 Research Agent 已编译出最终证据，因为
R8 acceptance 旧产物中的四个 generic sidecar 没有 claims，最终事实仍来自具名 profile；
本报告下面的当前 generic V3 重放是后续独立证据，不改写 R8 历史结果。

补充执行证据：D3 已在两个冻结前未进入既有四项目 profile 的真实 Python 仓库上完成
一次无 profile 留出。两案均生成了 snapshot → behavior graph → validated evidence
packets → facts → Qwen Agent claim 的 digest 链，supported must-cover mainline 为
1/案，unsupported positive sentence 为 0；各案的文件移动、符号重命名和行为改变
mutation 均通过判别。可复核产物位于
`/tmp/code2paper-d3-real-20260802/`（`holdout_acceptance_report_v1.json` 与
`cli_acceptance_report_v1.json` 均为 `passed`）。这只闭合 D3，不覆盖 D5 Writer
内容质量、live resume 等价性或 D6 rollout 授权。

本轮又闭合了 D5 的一个安全实现切片：Method Architect/argument graph、Formalization、
section Writer、Editor patch、writing-time callback 和最终反向验证已经接入同一
publication writer；反向验证失败现在会按 final claim 映射回 authored section，并同步
更新 Writer result 的终态。四项目真实 Writer 产物仍包含未被证据支持的正向句或 provider
截断，因此该切片只证明“失败可定位且不应继续发布”，不把 D5 质量门标记为完成。
本轮进一步把 writing-time callback 固化为
`writing_research_callback_artifacts_v1` sidecar：请求、authority lane、validated
artifact binding 和受影响 section 可跨 authoring stage 持久化；resume 会自动只选择
这些 section；owner fulfillment 会保留一次性 resume 标记，只有 Writer 成功消费受影响
section 后才清除。问题/目标/动机 move 不再把
`executable_hard` 当作默认权威，而是进入 author-attested/expository lane。
callback request 现在还要求非空的 request/section/unit binding 和 exact question，缺失时
在 Writer 生成前 fail closed。
本轮在本地 Qwen3.6 vLLM（`qwen36-27b-nvfp4`，`http://127.0.0.1:8003/v1`）上完成了
一次真实 RAP Writer 与 callback resume：首轮两节均通过 section binding/authorship，
并产生四个 `author_attested` request；作者目标由冻结的
`reference_method_agenda_v1.json` 以 digest-pinned callback artifact 回传。resume 只
重跑 `MA-S1`/`MA-S2`，最终两节均 accepted、无 binding failure、无 incomplete section，
四个 request 均为 `fulfilled` 且 `resume_section_ids=[]`。可复核产物为
`/tmp/code2paper-d5-live-writer-rap-20260802-v4/`（首轮）和
`/tmp/code2paper-d5-live-writer-rap-20260802-resume-v4/`（真实 resume）。该运行最终仍为
`incomplete`，因为 RAP 当前 argument graph 未覆盖全部 supported units，qualifier/完整性
门未通过且 final text validation 为 pending；这证明 callback/resume 安全闭环，不证明
RAP 已达到 D5 publication-ready。
随后对同一 live 正文按当前质量规则重算，`plan_gate=true`、
`supported_unit_recall=1.0`、`qualifier_coverage=1.0`、`utility_gate=true`；只提供最小
作者目标 MethodEvidence 后运行 reverse validator，得到 16 个 factual claims 中 2 个
supported、14 个 unsupported，最终重算报告为 `blocked`，而不是把 pending 当作通过。可
复核路径为 `/tmp/code2paper-d5-live-writer-rap-20260802-resume-v4/` 下的
`publication_quality_report_recomputed_v3.json`、`publication_quality_report_recomputed_v4.json`
和 `final-validation-v1/artifacts/07_validation/agentic_text_evidence_validation.json`。
这把 RAP 的剩余问题从“质量门失真”收敛为真实的 final prose/evidence mismatch，仍需
Writer/Rewrite 修复并重新验证。
随后修正了 final-text claim 的相似匹配：只保留最高 lexical score 的窄带，避免一个
无条件 claim 因共享标识符误继承另一条 conditional claim 的 qualifier。对同一 v4 正文
重算后为 `5/16` supported、`11/16` unsupported，安全门仍保持 blocked；这减少的是
验证器串线，不是放宽 evidence 要求；可复核的最新 v4 reverse artifact 位于
`/tmp/code2paper-d5-live-writer-rap-20260802-resume-v4/recomputed-final-validation-v7/`。
Writer skill 同步明确禁止模型自行加入源码行号、
证据 id 或聚合性机制句，并要求每个带条件 claim 在每个 factual sentence 中重复条件。
在该规则下又执行了一次真实 Qwen resume（仅 `MA-S1`/`MA-S2`，无新 callback），两节仍
通过 section binding/authorship、无 binding failure，产物位于
`/tmp/code2paper-d5-live-writer-rap-20260802-resume-v5/`；将其正文接入同一 reverse
validator 后为 `7/22` supported、`1/22` author-attested caveated、`14/22` unsupported，故仍 blocked，证明模型内容漂移
没有被新提示或 resume 路径掩盖；对应 reverse artifact 位于
`/tmp/code2paper-d5-live-writer-rap-20260802-resume-v5/recomputed-final-validation-v8/`。
随后把 Writer 请求改成最小授权投影：`reader_question`、`research_question`、
`design_objective` 和自由组织字段不再作为可复制正文输入；模型只看到闭集
`authorized_sentence_anchors`、required/anchored move 列表和明确的 callback JSON 形状。
在本地 Qwen 上的 v6/v7/v8 采样证明，正文从聚合模板句收敛到 anchor 近似复述；v8 首轮
还验证了当模型漏掉 callback 数组时，harness 只依据冻结 graph 恢复 typed request，
不补正文或完成 move。
最新 v9 初轮产物位于 `/tmp/code2paper-d5-live-writer-rap-20260802-v9/`：两个
organization-only required move 生成 open callback，正文只有 17 条 anchor 句；以同一
RAP V3 packets/claims 做独立 reverse validation，`status=passed`、`17/17 supported`、
`0 unsupported`。这是 Writer 安全/事实门通过的证据，但因 callback 尚未 fulfill，官方
publication quality 仍是 incomplete，不把它写成 D5 全部退出。
此前 v8 的真实 resume（`/tmp/code2paper-d5-live-writer-rap-20260802-resume-v8/`）已验证
fulfilled artifact 只重跑 `MA-S1`、无 binding failure、两个 request 均 fulfilled 且
`resume_section_ids=[]`；其独立反向统计仍有 5 条聚合/前缀句未支持，故 resume 质量门
继续保持 incomplete。该差异明确区分了 callback/resume 结构闭环与 publication prose
质量闭环。
为避免代码标识符 `f15` 的末位数字被误判为数值 claim，numeric validator 现在只提取与
字母/数字/下划线边界分离的独立数字；v9 17/17 复算 artifact 位于
`/tmp/code2paper-d5-live-writer-rap-20260802-v9/recomputed-final-validation-v2/`。
真实 Qwen 还暴露了两个表示层问题：JSON-object 省略空 `section_id`，以及 fulfilled
callback move 被消费但省略 `completed_rhetorical_moves`。现在只从 scoped call 恢复空
section ID，并只为 digest/section/unit/lane 对齐的 fulfilled callback 恢复 move metadata；
跨 section ID、重开 fulfilled request 和 artifact digest mismatch 仍 fail closed。文件型
callback ref 在进入模型前做 bounded preview 与 SHA-256 校验，`span:` 等 opaque ref
保持兼容。
本轮又把 callback sidecar 自身纳入 digest 校验：读取或 fulfill 前先验证 bundle 的
`content_digest`；绝对/路径型 artifact ref 缺失时 fail closed，而带 `span:`、`claim:`
等 typed 前缀的 opaque ref 仍不被误判为文件。对应 Writer callback 定向回归现为
`70 passed`（含篡改 bundle、缺失 artifact fixture 和 publication length retry 去重）。
在同一批当前 generic artifact 上运行的坏文本守门 fixture 也得到四案
`publication_writer_result_v1.status=blocked`、`publication_quality_report_v1.safety.final_text_validation_status=failed`，并
将每个 authored section 写入 `incomplete_sections`（RAP 2、EBCAR 3、DyG 4、LinearRAG
4 个 section）；对应产物位于
`/tmp/code2paper-d5-generic-guard-current-20260802/{rap,ebcar,dyg,linearrag}/`，证明 generic
packet/fact/claim 输入不会让 unsupported prose 绕过 Writer gate。该 fixture 是确定性
安全回归，不是模型质量或 D5 完成证据。
本轮又收紧了 Writer 的 move binding contract：`completed_rhetorical_moves` 只向模型暴露
有正向 evidence anchor 的必需动作，完整动作清单改放在 `required_rhetorical_moves`；
problem/local、design objective、intuition/rationale 和 transition 均统一按
organization-only 处理，未锚定动作必须走 scoped writing callback。这样 content-first
caller 即使直接复制 binding contract，也不会把 reverse gate 必须拒绝的组织动作误报成已
完成；对应 callback integration 回归覆盖了强制 required transition。这仍是 D5
安全/契约修正，不替代四项目真实模型质量、人工可编辑性和 live callback 退出条件。
质量报告现在额外输出 supported-unit completeness、section coherence、qualifier
coverage、information density，以及 agenda → argument unit → claim → final span 的
`coverage_matrix`；supported obligation 若未进入 argument graph 会使 plan gate 失败，
不再被 coverage 统计静默过滤。
结构化 Writer 响应现在还在非 `length` 路径验证 `section_id` 与当前调用的精确绑定；
跨小节响应会在进入 authored output 前 fail closed，而 ID/move 的 `unknown_*`、
`missing_*` 仍由 harness 保留为可定位质量 issue，重复 binding ID 也会 fail closed，
callback 仍可使用受限子集。
本轮又收紧了 Rewrite 的 lexical authorship：最终 ledger 现在按 Rewrite 返回的 exact
patch 重放，只将替换字节归给 Rewrite，未改动的 Writer/Editor 字节保留原 owner 与
response reference；对应回归验证了 `writer → rewrite` 的 span 链和 hard gate。
Editor 的 section-scoped patch 现在采用同一 exact-byte ledger 投影：未改动片段保留
Writer owner，replacement 才归 Editor；后续 Rewrite 从完整 incumbent ledger 投影，
不会把已有 Editor span 重新归为 Writer。
本轮最后一次完整静态回归为 `2206 passed, 3 skipped, 12 subtests passed`，并通过
`compileall` 与 `git diff --check`；
`git diff --check`；该数字是当前静态代码回归，不替代 D5 live 模型质量或 D6 rollout
验收。

D4 又完成了一个可验证的恢复安全切片：immutable checkpoint 现在通过原子
`fsync + replace` 写入；实际 driver 和多节点恢复在非空损坏/篡改 snapshot 时
fail-closed，不再静默退回 fresh loop；默认 immutable store 由 run/snapshot/tree
身份稳定命名，fresh runtime 可重新定位 payload。可复核 acceptance artifact 为
`/tmp/code2paper-d4-checkpoint-resume-20260802-v4/checkpoint_resume_acceptance_v3.json`，
其中 support boundary 等价、stable store、completed replay 零 turn、tamper reject
四项均为 `true`。这仍是 deterministic fixture 证据，不能替代 live provider 的
中断/恢复等价性。

Writer 的 section resume checkpoint 也改为 compact ref/digest manifest：完整
`PublicationMethodSectionOutputV1` payload 进入 content-addressed immutable store，
manifest 只保留相对 ref、output digest 和 response reference；store 或 manifest 篡改会在
任何新 Writer 调用前 fail closed，run root 复制后仍可定位 immutable payload，旧绝对/inline
checkpoint 仍只读兼容。
D4 的文本 repair/trace/best-state 路径也统一使用同一 `fsync + replace` 原子写入边界，
避免中断留下半个 candidate、transition 或 quality-state artifact。

本轮继续收回 D4 的运行时写入边界：V3 evidence/fact/claim、equation claims、intent /
coverage、behavior-template、source-authority、proposal、D25 方法 artifact 以及 generic
compilation manifest 不再直接调用 `Path.write_text`，统一经过同一 `fsync + replace`
helper；定向 evidence-chain 回归已在直接写入被阻断时验证这些 artifact 仍能完整落盘。

D5 的本轮写作 artifact 也统一改为同一原子持久化边界（repository/candidate、quality、
authorship、review、section checkpoint、callback、editor 与 Writer result）；重新运行
当前四项目坏文本 guard 后仍全部 `publication_writer_result_v1.status=blocked` 且
`publication_quality_report_v1.safety.final_text_validation_status=failed`，产物路径保持为
`/tmp/code2paper-d5-generic-guard-current-20260802/`。这证明原子写入没有放宽质量门，
仍不等于真实模型 Writer 质量达标。

D6 已完成可执行的配置切片而未宣告切换：JavaScript/TypeScript adapter 已在 registry
中走过 index → behavior graph → fact → claim 的静态主线，provider capability profile
也证明只改变 structured transport；shadow/opt-in/canary/rollback 与 digest 不变门均有
定向回归。当前正式 rollout 证据仍为 0 个 validated artifact、0/25 named review，
因此隐式默认继续 `legacy`，不创建 shadow/opt-in/canary 的伪成功记录。

本轮补齐了 D6 静态行为链的一个缺口：JavaScript/TypeScript adapter 现在会将仓库内
helper 调用编译为 `CALLS`，将 `factory()(...)` 等返回 callable 调用保留为
`UnresolvedRelationV1(dynamic_call)`，并跨 JS/TS 文件记录 import/usage reference
sites；可复核产物为
`/tmp/code2paper-d6-js-call-20260802/js_call_resolution_report_v1.json`，其中三个
不变量均为 `true`。这增强了第二语言的静态可审计性，但不替代真实第二语言仓库、
第二 provider/model 矩阵和 rollout 授权。

本轮又补齐了第二语言的配置/build graph 数据面：`inspect_configuration` 不再只接受
Python，而是对 JavaScript/TypeScript 的 `process.env`、`import.meta.env`、config/
options/CLI 访问、package manifest scripts/dependencies 以及 Vite/Webpack 等
`defineConfig` 入口产生带 exact line 的 `config:` observation；这些结果仍只是
discovery anchor，正向 configuration claim 仍必须经过 packet、behavior relation 和
generic fact/configuration compiler。可复核脚本与产物为
`scripts/evaluate_post_r8_js_adapter.py` 和
`/tmp/code2paper-d6-js-config-20260802/js_adapter_acceptance_report_v2.json`，其中
resolved helper call、dynamic callable gap、跨 JS/TS reference、build/runtime config
和 observation digest 六项不变量均为 `true`。这把 D6 的静态适配边界推进到“调用 + 动态
gap + 配置/build graph”，仍不替代真实多语言 provider 矩阵与 rollout。

同时补做了四项目当前 generic V3 research 运行（deterministic supervisor、无模型调用、
不读取 profile 事实）：RAP/EBCAR/DyG/LinearRAG 分别生成
18/32/11/28 个 evidence packets、86/148/74/169 个 facts、11/62/34/65 个 atomic
claims，packet/fact/claim 的 producer 均为
`code2paper-generic-research-data-plane-v1`。RAP 与 EBCAR 保留 4/2 个 explicit gaps，
四案的 must-cover obligation 都有 terminal 终态；可复核产物位于
`/tmp/code2paper-d1-{rap,ebcar,dyg,linearrag}-static-current-20260802/`。这证明 D1
generic data plane 可在已知项目上重放，但不替代真实模型 Writer 质量和 D6 rollout 验收。

本轮继续收紧 D1 的 artifact replay 门：`validate_evidence_packet` 在重复验证时会把
持久化 validated packet 与 proposal/behavior graph 的重新编译结果逐项比较，不再静默
覆盖篡改 sidecar；`validate_code_facts` 同时重放 packet、proposal、graph 和 compiler
输入，并拒绝与重放 fact set 不一致的 artifact。新增 tampered packet/fact 回归均返回
typed `invalid_request`，相关扩展测试为 `70 passed`。这使 observation 中的
input/output digest、artifact path 和 validator report 具备可重放语义；仍不替代跨进程
live provider 的中断恢复验证。
本轮再补了一个无 profile 的 D1 纵向验收：fixture 先执行 fresh snapshot 上的
`search_symbols → read_symbol → build_behavior_subgraph`，再由 observation 更新行为图，
执行 `propose/validate packet → compile/validate facts → decompose/authorize claim`，并
对同一快照执行一次带真实 `train.py` scope 的 terminal gap 与幂等 replay。
`scripts/evaluate_post_r8_tool_data_plane.py` 的十项不变量全部为 `true`（报告为
`tool_data_plane_acceptance_v2.json`），持久化 evidence 位于
`/tmp/code2paper-d1-tool-data-plane-20260802/`；同时 integrity gate 改为只接受精确的
`code2paper-generic-research-data-plane-v1`，伪造 generic 版本会被拒绝。该 artifact
闭合了本地 positive claim replay 与 negative terminal-gap provenance/idempotence 证据，
但仍不替代 RAP 真实 search/read 主运行和 D1 live 中断恢复验收。

本轮进一步验证了 production LangGraph 主循环，而不只是旁路工具脚本：在无 profile 的
可执行 fixture 上，deterministic supervisor 先完成 `search_symbols → read_symbol`，再
由 `compile_candidate` 调用同一套 `propose/validate packet → compile/validate facts →
decompose/authorize claim` 数据面。`scripts/evaluate_post_r8_d1_research_loop.py`
的 `/tmp/code2paper-d1-research-loop-20260802-v5/d1_research_loop_acceptance_v1.json`
记录 3 个 supported obligations、19 个行为图
节点、3 套 generic packet/fact/claim artifact、28 个 tool-trace refs，8 类持久化链和
claim/fact/packet digest replay 均为 `true`；config/training 语义不会再在精确源码读取前
抢先转入 `INSPECT_CONFIG`。同一回归也确认 `pass`-only symbol 只能形成可信 explicit gap，
不会生成 synthetic positive claim。该结果闭合 D1 主循环的本地纵向切片，仍不宣称 RAP
真实主运行、live 中断恢复或 D1 全部退出条件完成。

本轮同时收紧了 D2 的 production profile boundary：registry 的普通 `select()` 现在只
返回没有 `compile` 属性的 discovery view；只有明确命名的 `select_legacy()` 和
`compile_legacy_profile_evidence_v3()` 才能读取历史 profile fixture。匹配 profile 的
canonical `compile_evidence_v3()` 仍返回 `None`，legacy 结果的 producer 也不会被识别为
generic authority。可复核报告为
`/tmp/code2paper-d2-profile-authority-20260802/profile_authority_acceptance_v3.json`，
五项不变量全部为 `true`。六个历史 profile 实现文件仍保留供迁移诊断，不能把该切片
误报为 D2 全部完成；registry 的生产列表现在只保存 discovery view，六个 profile class
也不再暴露公开 `compile()`，只有显式 diagnostics route 才能调用私有
`_compile_legacy()`，生产主链已不再从 profile 获取事实授权。

另外对四项目当前 generic V3 产物做了 D2.5 纵向审计：RAP/EBCAR/DyG/LinearRAG 共生成
54 个 equation claims；每案都有 reference agenda、completeness matrix 和 argument
unit section plan，配置产物实际观察到 `actual/default/conditional` 三类状态。报告为
`/tmp/code2paper-d25-method-research-20260802/d25_method_research_acceptance_v1.json`，
五项聚合不变量全部为 `true`。`unreachable` 的拒绝分支仍由
`tests/test_agentic_method_research_artifacts.py` 的 rejected-fact 回归覆盖；当前四个
generic run 没有真实 unreachable configuration，不能把“未观察到”写成已存在。

由于“项目完成度”取决于目标范围，不能用一个百分比概括：

| 目标口径 | 当前 R8 六项目通过后的工程完成度 | 仍需完成 |
|---|---:|---:|
| 已知项目当前协议/运行工程 | 约 80%–90% | 约 10%–20% |
| 可信自主、信息完整的 Method 研究写作核心 | 约 50%–60% | 约 40%–50% |
| 可作为默认产品交付的通用 Code-to-Paper | 约 35%–45% | 约 55%–65% |

以上是工程置信区间，不是验收指标。较早的 75%–85% 核心完成度估计在检查四项目
paper/claim/final-text artifact 后不再成立：旧 R8 generic sidecar 没有产出 claims、
历史 profile fixture 仍保留迁移编译实现、正文信息覆盖过低且 repair 不是 Agent-owned。R8 的
pass/fail 已由六份统一 17 项 rechecked report 确认。当前仍不得把该结论扩张为
“可投稿 Method 完成”或“默认产品可切换”。

四个已落盘项目与原论文的专项对照见
[R8 四项目 Method 与原论文覆盖审计](r8_method_paper_coverage_audit_2026-07-31.md)。
该审计表明当前 accepted 结果仍只有 8–9 条压缩 implementation claims、0 safe
equations/0 safe numerics，且三个项目的正文被 deterministic 规则直接修改而没有
Rewrite Agent trace。因此当前协议通过不能等同于“Method 已完整”或“Agent 已完成
自修复”。

## 真实目标

本项目的目标不是让固定模板在几个仓库上产出文字，而是形成一个可自主运行的
研究写作 Agent：

1. 接收作者意图和代码仓库，自主决定应该调查哪些实现行为；
2. 通过细粒度代码工具形成 `CodeBehaviorGraph`、evidence packet、fact 和
   atomic claim，而不是依赖项目名或手写答案；
3. 作者意图决定研究重点与组织方式，可执行代码决定哪些事实可以写入或绘制；
4. validator 发现问题后，把 typed error 返回 owning Agent 做局部、有界修复；
5. harness 只兼容括号、逗号、截断等简单结构损伤，不能通过过滤内容、放宽硬门
   或减少 obligation 冒充成功；
6. 最终文字、公式、图示和交付包中的事实均可追溯到相应冻结 authority；
7. 最终正文 lexical token 均来自 Writer/Rewrite 响应，规则只检测、反馈和复验；
8. atomic claims 只作为验证单元，经 argument graph 组织成原理、形式化、机制、
   实现和输出完整的论文小节；
9. 写作发现缺失信息时能返回 Research Agent、Formalization Agent 或作者确认，
   而不是把 Method 压缩成已知 claim 摘要；
10. 在未知仓库、不同模型、不同语言和中断恢复条件下仍保持上述性质。

## R8 通过能够证明什么

R8 通过后，可以正式声明：

- 六个项目均通过统一 17 项当前协议重检；结果来自两个串行 matrix，报告与 resume
  digest 已汇总持久化，不冒充一次单矩阵 clean-checkout freeze；
- 正式 API 调用、角色配置和 generation trace 可追踪，非缓存 live 路径成立；
- 当前 Python 运行能落盘 intent、obligation、evidence、claim、final text 和验收
  artifact；但旧 criterion 不证明它们来自同一 generic compiler provenance；
- 已知输入上的 unsupported leakage、completion/readiness、checkpoint digest
  等当前硬门全部通过；
- 有界 thinking/output 配置可在真实长流程上运行，不需要把规则降级为软检查。

这足以把项目从“只有架构和单元能力”推进到“真实长流程已被演练”，但还不足以
声明“自主研究到完整 Method 的可信主链路已经被验证”。

## R8 通过仍不能证明什么

R8 是必要条件，但不能单独证明：

- **更广泛的无项目特权泛化。** D3 已由两个冻结的真实未知仓库证明 generic
  packet/fact/claim 主线和 mutation 判别无需新增 profile；仍需扩展到更多仓库、
  语言和 provider 矩阵，不能把两案外推为全面泛化。
- **恢复等价性。** 代码已有 checkpoint、完成态恢复和 best-state 保留路径，
  但仍需 live 证明中断恢复与 uninterrupted run 等价，并确认完成态 replay
  是否真正零调用。
- **自修复覆盖充分。** packet-scoped repair、typed issue、按 obligation 预算和
  结构恢复已有实现基础；仍需用真实内容错误、引用错误、长输出截断和重复输出
  证明 Agent 能局部修正且不会污染已通过的义务。
- **研究与写作质量达到产品标准。** `unsupported=0` 证明安全边界，不自动证明
  Method 完整、准确、简洁、不重复、符合作者意图或优于人工基线。
- **可投稿 Writer 闭环。** Method Architect、argument graph、Formalization、
  Cross-section Editor、writing-time callback、owned Rewrite 和 reverse-gate 的
  代码切片已经接通；但四项目真实 Writer 产物仍有 unsupported prose/截断，尚未
  满足 D5 的完整性、可编辑性和 live callback 退出条件。
- **语言通用。** `JavaScriptBehaviorAdapter` 已进入 registry 并通过静态主线，
  但真实生产研究矩阵仍以 Python 为主，不能据此声明支持任意语言。
- **模型与部署通用。** 单一 Qwen/profile/API 的成功不能代表不同 provider、
  sampling、上下文长度和推理模式。
- **默认产品切换。** migration policy 明确要求 `shadow → opt-in → canary →
  default_ready`；R8 不会自动把 agentic route 设为默认。
- **完整论文自主生成。** 当前最强证据集中在 Method 和代码图示。Introduction、
  Related Work、Experiments 等章节需要论文、数据集和运行结果等不同证据源，
  不能用代码证据规则直接代替。

## 当前能力地图

| 能力 | 当前判断 | 说明 |
|---|---|---|
| Intent 与代码证据分权 | 已实现，R8 已验证 | 意图控制优先级，证据控制事实授权 |
| Python 行为图与细粒度工具 | 已实现，六项目已运行 | `LanguageBehaviorAdapter` 目前只有 Python 主实现 |
| Evidence/fact/claim/final-text 信任链 | generic data plane 已可重放，终态闭环仍在验收 | 四项目当前 deterministic 运行已生成 generic packet/fact/claim；旧 R8 产物仍是 profile 路径，registry production view 已收回 profile compile authority，仍需以新链重跑 Writer 和最终文本 |
| 公式授权 | 已实现 | 已有 `EquationClaimV1` 合同与投影/验证路径 |
| 图示与 post-render audit | 已实现，需产品级复验 | 与最终 package 的全场景一致性仍需持续验证 |
| Typed self-repair | owning Agent repair 路径已接入，历史产物未闭合 | 新 Writer 只接受 Writer/Editor/Rewrite 生成的正文并复验候选；旧三项目产物仍需真实重跑确认，不可回写为已修复 |
| 简单结构错误兼容 | 部分完成 | 需继续覆盖截断、重复 JSON、内容/格式分离组合 |
| 可投稿 Method Writer | 核心合同已接入，质量未闭合 | Architect、argument graph、Formalization、Editor、callback 和 reverse-gate 已接入；四项目真实 Writer 仍需解决 unsupported prose、截断与完整性 |
| Checkpoint/resume | 部分完成 | digest/恢复路径存在；live 等价与零调用 replay 待证 |
| Benchmark/cutover 工具 | 已实现 | rollout 证据和默认切换尚未完成 |
| 非 Python 语言 | adapter 已实现，生产矩阵未完成 | JavaScript/TypeScript adapter 已进入 registry，并覆盖静态 `CALLS`/动态 unresolved/reference 主线；仍缺第二语言真实仓库与 provider 矩阵 |
| 完整论文多章节 | 未完成/不在当前 R8 范围 | 需建立新的证据 authority 与验收协议 |

## R8 之后的优先执行顺序

具体模块、测试、依赖和退出条件见
[R8 后 Research Agent 具体开发执行计划](post_r8_research_agent_execution_plan_2026-07-31.md)。

### P0：完成“可信自主 Method”定义

1. **冻结 R8 release evidence。** 六项目 pass/fail 已确认；下一步提交当前修复并从
   干净检出归档 commit、matrix ID、API/profile、artifact manifest、摘要和 recheck，
   使证据不依赖临时 run root。
2. **闭合 generic evidence compiler 并收回 profile 事实权限。** 未知项目必须由
   search/read 形成 packet/fact/claim，profile 只能提供 discovery hint。
3. **Reference Method 覆盖与质量门。** 论文/作者输入只生成搜索义务，不授权
   实现事实；逐项建立 supported/partial/mismatch/external-evidence/gap 矩阵，
   并评价重复率、结构连贯性和人工可编辑性。
4. **可投稿 Writer 工作流。** 将 atomic claim 与论文论证单元分离，开发 Method
   Architect、Section Research Writer、Formalization、Cross-section Editor 和
   写作中返回研究；多权威事实经匹配验证后才能进入 publication candidate。
5. **真实自修复、authorship 与恢复矩阵。** 每个正文 lexical span 回溯到
   Writer/Rewrite generation；同时覆盖 JSON 损伤、长输出截断、内容/引用错误、
   公平轮转、best-state、中断恢复和完成态 replay。
6. **无特权 holdout。** 已完成两个未进入既有四项目 profile 的真实 Python 仓库与
   必要 mutation；后续仍需将该证据纳入 clean-checkout release freeze，并扩展行漂移、
   文件拆分及多语言/provider 矩阵，禁止新增 project-specific profile、项目名分支和
   symbol literal。

完成 P0 后，才适合声明“可信自主 Method 核心完成”。

### P1：证明通用性

6. **跨模型/provider 矩阵。** 以 capability profile 表达差异，不把某模型的
   sampling 或 token 数写死成全局协议。
7. **第二语言适配器。** 实现并验证至少一种非 Python 语言，包括调用关系、
   配置/build graph、动态行为的 evidence/gap 表达。
8. **最终图示与交付包复验。** 保证文字、公式、图节点/边、TeX/PDF 和 manifest
   使用同一证据链，且 post-render audit 在真实项目上通过。

### P2：完成产品化和默认切换

9. **正式 rollout。** 依次收集 shadow、opt-in、canary 证据，演练 incident 与
   rollback，最后由 cutover gate 产生 `default_ready`。
10. **运行治理。** 补齐版本迁移、可观测性、并发与成本上限、失败归因、artifact
   保留策略和可复现实例。
11. **若目标包含完整论文，扩展证据域。** 为文献、数据集、实验结果和外部事实
    建立独立 authority、引用和验收机制，再扩展到 Method 之外的章节。

## “真实目标完成”的判定标准

只有同时满足以下条件，才应把整个项目标记为完成：

- 当前协议 R8 从干净检出正式通过；
- 未见仓库不依赖项目特权即可通过；
- 内容错误能由 Agent 修复，简单格式错误由 harness 恢复，二者边界有回归测试；
- 中断/恢复、best-state 和 replay 在 live 条件下可复现；
- 至少两个模型/provider profile 和两个语言 adapter 通过各自真实矩阵；
- Method 质量/可用性评价通过，而不仅是 unsupported 为零；
- shadow、opt-in、canary 完成，cutover 决策达到 `default_ready`；
- 若承诺完整论文，则非代码证据域与多章节验收也已完成。

在此之前，最准确的项目表述是：**自主可信 Method 主链路接近闭环，通用化与
产品化仍在进行。**

## 文档阅读顺序

1. [文档导航](README.md)
2. [自主错误反馈与自修复原则](agentic_error_feedback_and_self_repair_principle.md)
3. [结构化输出恢复策略](agentic_structured_output_recovery_strategy.md)
4. [鲁棒 Research Agent 总体设计](agentic_robust_langgraph_research_writing_design_2026-07-19.md)
5. [R8 四项目 Method 与原论文覆盖审计](r8_method_paper_coverage_audit_2026-07-31.md)
6. [可投稿 Method Writer Agent 设计](publication_ready_method_writer_design_2026-07-31.md)
7. [R8 后具体开发计划](post_r8_research_agent_execution_plan_2026-07-31.md)
8. [Method 质量历史执行计划](agentic_method_quality_next_execution_plan_2026-07-19.md)
9. [迁移与切换指南](agentic_migration_guide.md)

旧审计和 JSON 证据的分类见[文档导航](README.md)。它们用于追溯历史，不覆盖
本报告的当前状态。
