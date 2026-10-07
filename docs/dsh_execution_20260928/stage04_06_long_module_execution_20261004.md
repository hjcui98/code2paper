# 第 04–06 份长期模块：DSH 持久执行与主流程接线

> 当前接续（2026-10-07）：[独立 Gate-M PASS](stage05_M_acceptance_20261007.md)，28/49，M01–M03 完成；当前完整2103及 fresh cold1 经原严格读取器验收，全部独立读集释放。正式进入 P01–P04，保留 Gate-P/G0/G 阶段门；V2 Host API资格不代表默认CLI切换或Verified。下文早期状态按历史快照解释。

> **2026-10-06 当前接续：** 用户要求身份类差异不再重复确认、必要真实live直接执行。packet16已按原受信native stop具名退役，packet21/22各一次正常结算并释放；当前canonical empty，旧14费用UNKNOWN仍保留。完整15为1945/fresh cold1，独立材料CLEAR；packet22原生schema、工具、usage/finish闭合，但缺required-target witness，独立Gate-L FAIL。当前原Writer发射合同补齐显式paragraphs/witnesses，不改内容/来源/公式门，不修旧raw。先完成必要验证及独立验收后一次fresh变化请求；同一范围无需再次解冻/身份确认。Gate-L PASS后直接连续M01–M03→P01–P04→G01–G08，保留阶段独立门。以下早期“当前/尚未授权/owner held”均为所标日期的历史快照，以本条和[最新证据](stage04_L01_native_stop_repair_evidence_20261006.md)为准。

> **2026-10-05 当前执行依据：本文件 [§9 Gate-L 集中解阻](#gate-l-unblock-20261005)。** 一批完成显式非 thinking 的完整 wire/服务端兼容验证、packet14 错误流计量与诊断、具名 abort/unknown 恢复包，再统一冻结当前完整/cold 并交独立 QA。方案待实施，费用 UNKNOWN、原 owner held、Gate-L FAIL 与 24/1/24 不变；本次不增加真实执行授权。§8 已同步派工入口，§9.8 可直接转交。下方旧 packet 摘要保留历史范围。

> **packet14 最新：** 服务端grammar错误、实际usage/finish缺失、费用UNKNOWN/原owner held，Gate-L FAIL。错误流计量与首因返修进行中；[当前证据](stage04_L01_provider_error_repair_evidence_20261005.md)。下方packet13状态为历史。

> **packet13 历史状态：** packet13 一次授权已消耗，普通文本/原生工具调用0，Gate-L FAIL；受信自然完成已登记、实际费用7699/pending0、原 owner 正常释放，canonical empty及六条严格history，独立生命周期PASS、实际读集释放。当前原生工具选择返修使用tool-choice.2开发候选；来源构建、wire对照、三项真实native及严格审计通过，统一关闭后冻结新完整/cold09。历史1803仅7f77/af9；24/1/24，M/P/G保持原阶段门。详见[原生工具选择返修证据](stage04_L01_native_tool_choice_repair_evidence_20261005.md)。

> **packet12历史执行状态：** packet12具体一次授权已消耗，UNKNOWN_TOOL领域FAIL保留。受信完成/诊断/历史退役经真实native及focused、原数据保护克隆；独立代码方案PASS/APPLIES和实际退役PASS，原费用7648/pending0、canonical empty，42非lease旧run文件及14原输入未变。读集已释放；当前关闭文档后冻结新完整/cold（05），历史1707仅9def/7b77。Gate-L FAIL、24/1/24；详见[未注册工具返修证据](stage04_L01_unknown_tool_repair_evidence_20261005.md)。

> **packet11历史恢复状态（后续packet13见上）：** packet11 一次生成授权已消耗，普通文本 JSON/finish stop、tool_calls0，领域失败保留。文本结束返修及具名原费用恢复经独立代码/方案、实际结果两次 PASS；原费用 spent7596/pending0，canonical backend empty，35旧文件、原task/claim/正文及provider_quiescence null保持不变。实际读集已释放；新完整注册证书及fresh cold待最终冻结运行。Gate-L仍FAIL，24/1/24；新模型请求需fresh packet具体一次授权，不重发旧packet。详见 [文本结束返修证据](stage04_L01_text_stop_repair_evidence_20261005.md)。


2026-10-04，按用户“并行按需要决定、布置更大的长期模块”的要求调整任务组织。本模块覆盖原第 04–06 份 **23 项：22 项离线实现/验证及 1 项有独立准入条件的 L01 live**。默认由一个主执行者连续负责 Python、TS、联测与交付；有稳定、独立的工作面时再拆出协作。

目标是从已通过 Gate-C 的 Writer 合同，完成持久运行、真实 Host 闭环、多步工具、共享调度及 Research/Authoring 主流程的 DSH 接线。交付终点为 **Gate-G 的完整离线迁移验证**，保留原默认业务拓扑和显式 opt-in 入口。第 07 份全文编辑/发布/Figure/导出以及第 08 份质量评测/默认切换另属后续模块。

首次派发本模块时为 **17 done / 0 in_progress / 32 planned**；该数字仅说明起点。2026-10-05 已完成 A 七项，当前为 **24 done / 1 in_progress / 24 planned**，接续点是 B 段 L01 集中返修。

> **2026-10-05：[packet10 现状与整批接续指令](stage04_L01_packet10_repair_and_continuation_20261005.md)。** Stage A 七项独立 Gate-R/V PASS，项目 24 done / 1 in_progress / 24 planned；长期模块 7/23 done。packet10 已消费一次具体授权，HTTP200、7463 输入/1182 输出、tokenizer 一致、费用结清；terminal 缺 schema_version 被拒，当次 Session blocked 触发旧完成凭据拒绝，原领域无回执。原 backend 的后续具名退役已完成，当前 empty。Gate-L 未通过：packet10 独立事后裁决 FAIL，读集已明确释放（/tmp/c2p-dsh-independent-packet10-postlive-20261005-01/readset-release.json）。五组代码及具体历史恢复方案已独立 PASS；原 exact owner 已按既有 normal-finish release 授权合法退役，canonical backend empty，费用不变且原领域失败保留。当前完整证书和新包具体授权仍待；证据见 [整批返修记录](stage04_L01_repair_batch_evidence_20261005.md)。Gate-L PASS 后连续推进 C–F。本指导不授权新的模型调用。 旧 packet02 的待结算批准状态已经结束。冻结读集释放后才同步并修改下一批输入；本报告不代替原 reviewer 的释放记录。

## 1. 文档依据与接续规则

| 依据 | 本模块如何使用 |
|---|---|
| [docs 入口](../README.md)及其架构权威顺序 | Python 保留事实、预算、裁决和发布权威；DSH 执行模型角色；质量门不改弱 |
| [DSH 总设计](../code2paper_dsh_plugin_design_20260922.md) §§6.3–6.5、11–16、20–22 | 实际业务拓扑、持久执行、恢复、多步、调度和角色迁移顺序 |
| [Gate-C 独立裁决](stage03_gc_repair_acceptance_20261004.md) | 第 01–03 份已验范围，GC-1/2/3 已关闭；继承实际代码与证据 |
| [原第 04 份](04_serial_writer_integration.md)和[第 04 份详细指令](stage04_batch_execution_instructions_20261004.md) | R01–R04/V01/A01/V02 全部修改、反例和命令；L01 的具体准入 |
| [原第 05 份](05_multistep_and_concurrency.md) | M01–M03/P01–P04；L01 是 M01 的真实前置 |
| [原第 06 份](06_langgraph_workflow_migration.md) | G01–G08；G0 状态承载通过后才接领域角色 |
| [interfaces](interfaces.md)、[verification](verification.md)、[task_board](task_board.json)、[H02](h02_interface_freeze_020.md) | 原接口、23 项 AT/依赖、独立验收门与实际 DSH API |

本指令调整交付模块和人手安排，不更改原任务 ID、depends_on、AT 或产品默认值。前置阶段已验收、读集已释放、所需授权已存在时，主执行者直接继续本模块下一段，无需逐 helper 或逐任务重新请示。阶段内按已成立的前置本地合同连续推进。

原总设计 §20.2 与第 04 份 L01 明确要求具体 live 范围另行授权；本次扩大工作量没有给出这次 live 的输入、额度和时限。因此先完成并验收离线链、准备可审查的 live 执行包，再处理该唯一的模型调用准入。不得把 Gate-L 省略，或把后续离线实验登记为已越过 Gate-L。其余正式门是独立技术验收，不新增用户开工确认。

## 2. 人手与写入安排

**默认一个主执行者。** 接收本指令的执行者持有本模块当前已激活阶段的完整实现责任，可以串行修改 Python、TS、测试和相关文档；不再因为“窗口一/窗口二”标签等待另一窗口。第 04 份原两窗口表只在实际拆分协作时适用。

仅在接口已可执行、文件责任不重叠、没有共享构建或模型资源争用，且能减少总交付时间时拆出协作者。主执行者记录交出的具体路径与责任，协作者保留他人 dirty 基线；退出协作后明确交还写权。没有稳定分工就继续单人串行，不制造占位工作。

无论多少人，同时只保留一个共享 Python 协议/validator 来源清单写者，以及一个 peer/lib/build/stage 写者。单人模式两种职责均由主执行者承担；拆分模式通常按 Python 和 TS 分工，跨文件需求先交实际合同。研究图与 Authoring 共享入口、发布 owner 等重叠文件按任务顺序交接，不让两个实现者同时编辑。

实现者的人手并行与产品 `execution.parallel_agents` 是两件事。用户允许串行实施，不删除 P01–P04 原产品合同；产品默认仍 false，后端请求默认仍 1。共享调度和并发能力使用确定性的离线多进程测试验收。

独立 QA 按里程碑冻结包启动，可以与实施串行进行；不保留常驻第三窗口。实现者自测不登记独立 PASS。真实读集包括 docs 时按完整身份冻结，不删除文档来逃避漂移；QA 明确释放后再修改被验输入。

## 3. 一项长期责任，六个阶段检查点

| 检查点 | 原任务和完成结果 | 进入下一段的条件 |
|---|---|---|
| A：可恢复的单 Writer 离线运行 | R01→R02→R03→R04→V01→A01→V02，7 项 | 完整包独立 Gate-R、Gate-V PASS |
| B：限定真实兼容验证 | L01，1 项；一次 primary 的具体准入/运行/证据 | 具体 live 授权、当前回执与 Gate-L PASS |
| C：有界多步执行 | M01→M02→M03，3 项 | 独立 Gate-M PASS |
| D：同主机共享调度 | P01→P02→P03→P04，4 项 | 独立 Gate-P PASS |
| E：真实图状态承载 | G01→G02→G03，3 项 | 独立 Gate-G0 PASS；此门不要求尚未实施的 G04–G08 |
| F：完整角色和主流程接线 | G04→G05→G06→G07→G08，5 项 | 独立 Gate-G PASS，复验 G0，完成本长期模块 |

A 中 Gate-R/V可用同一冻结包审查并分别裁决。C、D和E、F各保留原前置门，不能为了减少交接而先跨门集成再补证。每个检查点内部集中完成原 AT、真实联测、缺陷修复和封存，不按单个报错拆小批。

## 4. 每段完整实施内容

### A：持久运行到实际 CLI，一次完成七项

逐项实现要求完整沿用[第 04 份详细指令 §3](stage04_batch_execution_instructions_20261004.md#3-七项具体实施要求)。主执行者连续拥有以下端到端结果：

1. **R01/R02：**稳定 task/epoch/outbox/claim、有效 fence、可恢复独占；扩原 Python 唯一账本和 reducer，真实 worker 私有 reserve/dispatch/settle/unknown RPC。不可用受控 fixture claim 或假 reserve 冒充生产授权。
2. **R03/R04：**真实 DSH subprocess 启动 worker，创建期绑定 child；实际组成/材料复核后 reserve 再派发；Session/raw 先落盘 flush，再 record_output/ingest/receipt。逐崩溃点用新进程恢复，unknown 保留预留且禁止盲重发。
3. **V01：**技术页/作者页、三终态、预算耗尽、cap/组成漂移、取消、丢回包恢复走同一真实链；仅 provider 为隔离假 HTTP/SSE，Python 模型出口拒绝哨兵有效。
4. **A01/V02：**修原 CLI “只跑单 pytest 节点仍填完整覆盖”的问题；回执来自真实 Python/Node/CLI 发现和机器报告。新增显式 opt-in 操作入口，默认串行，最终 CLI 测试进入最终计划后重新生成准入回执。

新增主体为 `task_store.py`、`invocation_adapter.py`、`kernel-client.ts`、`workflow-driver.ts`、`execution-policy.ts`、`cli.ts`；facade/worker/protocol/request-accounting 等是现有 owner。持久格式和 RPC 在本段版本化，并为后续 scoped read、epoch 多请求、wave 和 workflow receipt 保留清晰接口；此时只兑现单 run/单请求能力，不提前插入尚未准入的调度或图逻辑。

验收必须包含真实 provider 到达计数和原 reader 读回；不能只检查方法返回值或伪造终态文本。GC-1/2/3 原断言继续保留，旧合法 receipt 恢复不得被新任务权限检查误伤。

### B：先准备完整执行包，再进行 L01

当前具体执行按 [stage04_L01_packet10_repair_and_continuation_20261005.md](stage04_L01_packet10_repair_and_continuation_20261005.md) §§3–6：packet10 原文保持失败，先收齐五组修复和历史 owner 恢复证据，再准备新包的具体一次准入。不得复用旧 primary 授权。下述为长期通用规则。

完成 A 后先准备可直接审查的 `live` 执行记录：冻结的一页输入/合同、候选和实际 wire、模型与 profile、tokenizer/sampling/thinking 差异、精确命令、一个 primary 请求、总输入/输出/token/时限上限、停止条件、独占检查和新的输出根。完整数值由实际合同和 adapter 能力得出，不填写未校验的承诺。

原目标为 `http://127.0.0.1:8006/v1`、`qwen38-27b-nvfp4`、131072 context。具体授权已存在则引用其范围，不重复询问；缺少时在离线工作和执行包就绪后一次提交具体范围。真正发送前按原规则记录 health/models/队列/KV及当前执行身份。tool-calling probe 同样计入授权，不能作为额外免费请求。

一次失败按原 owner 定位和有变化的修复回路处理，禁止无变化重复采样。usage 缺失、发送未知或资源未静止时保留事实与占用，不声称成功或自动续多步。L01 只验证该限定集成能力，不证明 Method 质量或 rollout。

若暂未得到具体授权，可完成 C–F 的只读接口核对、节点/持久字段清单和离线研究材料；不把这些研究记成 M/P/G 正式集成、独立通过或 done。保留精确接续点，不循环等待或重跑已经通过的 A。

### C：M01–M03 有界读取、多步上下文与账本

| 任务 | 修改落点与交付 | 一次覆盖的关键反例 |
|---|---|---|
| M01 | 扩现有 `facade.py`、`task-tools.ts`，按 task read-set 授权限量句柄读取；原内核晋升新观察并产生 revision | 越界路径、跨 snapshot、摘要冒充完整 span、超读取量、旧 TaskView；合法定位仍可用 |
| M02 | 新 `context-policy.ts`，扩现有 request-accounting；冻结版本化导航/产文材料规则；实际 compaction 后恢复必要原文并重新计量 | 只剩摘要、exact excerpt/occurrence/作者语义丢失、偷偷 provider 注入、装不下仍强发、免费 title/compact；容量不足回原分页 owner |
| M03 | 真 DSH 多步与 Python 账本联测；一个 epoch 最多一个 terminal candidate；同 reducer 跨 child/进程恢复 | 换 child 清零、重复终态、已发送格式失败/unfinished/research_required 费用消失、排队取消误算内容尝试、辅助请求绕额度 |

必测文件：`test_scoped_reads.py`、`test_multistep_context.py`、`test_multistep_accounting.py`、`context-replay.test.ts`、`multistep.test.ts`。记录导航与产文请求的实际字节及每次费用事实，不能用“最终上下文看起来完整”替代发送时材料证据。

**C 段独立验收（2026-10-07）：** Gate-M PASS，M01–M03 完成，28/49。实际 SDK读取→独立compaction child→Writer terminal、Session原材料恢复和重新计量、原账本3请求usage51/33/pending0、整epoch原owner释放及新Worker零发送恢复均闭合；旧视图持久撤销与重启拒旧已验证。当前完整2103/fresh cold1、四实际入口strict4及独立审查全部读集释放，详见[验收与P接续](stage05_M_acceptance_20261007.md)。隔离假provider资格限显式V2 Host API，normal JSON CLI仍V1，不代表Qwen live、默认切换或Verified。

### D：P01–P04 调度、wave 和真实多进程故障

| 任务 | 修改落点与交付 | 一次覆盖的关键反例 |
|---|---|---|
| P01 | 新 `backend_scheduler.py`，扩 invocation_adapter；同主机唯一 SQLite/backend_state_root，alias归并，短事务原子检查 run/backend，run轮转及run内FIFO | 两进程/两run/两alias；私有库假限流、配置不一致、零额度、排队取消、unknown靠TTL释放；一个unknown阻断整个resource group |
| P02 | 扩 execution-policy/CLI，新增 artifact-view 时只承担原P02显示范围；显示requested/effective；默认关闭，开时叶任务2/后端请求1 | 混合开关、run上限2/backend4加父/辅助仍总在途≤2；stream对象返回后过早释放；降低限额未排空；未接入客户端不能承诺全局限流 |
| P03 | 扩task_store/workflow-driver；冻结wave集合，单一join，父等待child/verify不占叶slot；同section revision单写者 | 漏结果即完成、父子死锁、兄弟失败删除独立成果、旧revision迟到、新Research revision未使受影响read-set失效 |
| P04 | 独立进程检验混合配置、停止/重启、迟到结果、账本与permit归属、公平性 | 双发、超额、饿死、旧permit/fence重放、停止后新发；容量2而一个unknown时另一空slot仍不得发 |

必测文件：`test_backend_scheduler.py`、`test_execution_policy.py`、`test_task_waves.py`、`test_scheduler_multiprocess.py`、`concurrency.test.ts`。调度库只存队列/permit，不建第二本费用账。使用有限确定任务序列和离线假服务，不以这段测试启动模型压力运行。

### E：G01–G03 先证明真实图可以恢复

1. **G01：**扩实际 `product_authoring_graph.py`、`checkpointing.py`，新增 `workflow_adapter.py`。DSH路径要求真实LangGraph、完整handler、持久saver、稳定thread_id和严格serializer；未知route/缺handler/缺依赖明确失败；唯一合法后继由内核直接推进。
2. **G02：**扩 `research_graph.py` 现有 snapshot/immutable payload/strict restore 与 `autonomous_method_agent.py` 实际入口。逐字段登记 pending/merged decision、route、termination、trace、revision budget、deadline和verifier配置的持久来源；运行对象从校验过的引用重建，结果从manifest读取。
3. **G03：**按真实9节点及条件边逐处启动全新Python进程恢复，比较状态、支持边界、预算、下一节点、发送账和副作用。必须包含 supervisor 的 partial_gap/compile/no_tool_calls 与 compile 的 compiled/partial/rejected/blocked 路由。

必测文件：`test_workflow_admission.py`、`test_research_state_hydration.py`、`test_research_process_resume.py`。本段外部提案允许确定fixture executor来隔离状态承载；同进程round-trip、库级玩具图、`last_result`恢复或默认选第一分支均不能通过G0。G0通过才实施F段领域角色。

### F：G04–G08 接通真实角色、独立验证和补证续作

| 任务 | 原 owner 和产品入口 | 完成要求及反例 |
|---|---|---|
| G04 | research_nodes/research_graph、autonomous_method_agent 的实际 Research runtime、facade/task-tools | supervisor提案由DSH，policy/critic/compile在原内核；enrichment与有限模型修复实际移出Python；unknown tool/跨snapshot/伪造权限/耗尽拒绝；确定性critic不增加模型调用 |
| G05 | publication_method_writer、workflow_adapter、role-dispatch及实际planning入口 | 原顺序 plan→Formalizer→版本化Narrative→Writer/Realizer→verify→最终Binder；16节点合同全部注册，Editor/Rewrite最小真实调用与重验本段完成；错atom/detail、sum→mean、丢条件拒绝；Realizer不新增措辞权 |
| G06 | 原语义validator与publication owner、result_ingest、role-dispatch | proposition/reverse/Research语义revision成为独立verify任务；冻结正文/evidence/validator/task；缺验证保持pending，Writer自报supported不能通过，编辑后旧回执失效 |
| G07 | writing_callback_fulfillment、workflow_adapter | typed gap/lineage→Research→受影响依赖重编→新Writer；沿同outbox/interrupt/receipt/resume；保留history/预算；无新证据不fulfilled，同路径新字节使旧依赖失效 |
| G08 | 真实产品入口、完整图及独立恢复测试 | 复验G0并覆盖全部16节点真实角色；outbox/commit/checkpoint各交界崩溃，新进程幂等恢复；停止后不新发，原响应只本地结算；不再用E段fixture executor替代已要求的角色 |

必测文件：`test_research_dsh_execution.py`、`test_authoring_role_workflow.py`、`test_independent_verifier.py`、`test_callback_workflow.py`、`test_full_workflow_recovery.py`、`test_no_hidden_python_llm.py`。主图节点从真实构图常量/边读取建立矩阵，不按docstring猜测，也不能只数到16个就通过。

所有角色通过实际DSH与隔离假provider完成原builder/parser/assessor链，Python出口拒绝哨兵保持。G05尚待G06/G07的分支可具名pending；G08不得仍拿“未实现pending”作为完整迁移通过证据。领域的pending_validation仅在原独立验证与硬门满足时更新，不能随Gate名称提升。

## 5. 验证、变更影响和实际命令

每段先运行聚焦测试与必需真实场景，再进行该段影响范围回归；完整里程碑按原验证要求执行全静态。长模块最终重新覆盖全链和当前全静态，不把每个helper都变成全量重跑。已验旧模块按实际差分复核，未变证据可以引用但保留其身份。

现有测试脚本仍是 `test:compat`，递归发现 `tests/` 与 `dev/toolchain/` 下 `.test.ts`；目前没有 `test:integration`。第04份详细指令§4列出真实构建/测试命令，本轮同步纠正第05/06份的旧命令；若实现新runner，先验发现/失败/零测试/机器报告，再纳入A01覆盖计划。

阶段基本执行入口（新增测试落地后才运行，不以缺文件跳过）：

```bash
python -m pytest -q tests/integrations/dsh/
export C2P_DSH_CANDIDATE='0.2.0-rc.1+loop-origin.1'
export C2P_DSH_DEV_ROOT='/home/cuihengjia/agent/Code2Paper copy/.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1'
npm --prefix integrations/dsh run typecheck
npm --prefix integrations/dsh run build
npm --prefix integrations/dsh run stage
npm --prefix integrations/dsh run test:compat
python -m pytest -q integrations/dsh/dev/tests
python scripts/dsh_dev.py --candidate "$C2P_DSH_CANDIDATE" audit
git diff --check
```

上方是owner构建顺序；已有冻结构建就绪时，独立QA只读验证，不无故重build/stage。真实Node执行必须经同一隔离launcher。原第06份列出的旧Research/Authoring/callback回归保留；新增裁决源落地时同步实际 `VALIDATOR_BUNDLE_SOURCES`，缺文件或规则变化却身份不变均拒绝。

A01计划随M/P/G实际范围扩展；按当前阶段要求解释覆盖，不能拿A段或旧4355日志给后续代码背书。记录精确命令/cwd/runner、实际节点、退出码、原日志、组成、有效配置和未测项。原未启用live可以单列，阶段必测不得skip或零测试通过。

## 6. 长期进度与证据管理

保留当前worktree、dirty基线、分支/HEAD和第01–03份owner/QA封存。每段使用新的运行根和独立冻结包，不覆盖历史候选；在 `task_board.json` 和 `.agent/implementation.md` 记录当前任务、实际文件、已实现合同、可复现失败、测试、未测项、下一条可执行动作及写权/进程释放。

中途换会话从上述实际记录恢复；先确认正在运行的命令及文件归属，接着未完成步骤，不重做已接受阶段、不只转述上个窗口自报成功。测试冻结期间进度写入外部run根；协调文档更新在释放后登记，不给旧合同回填新engine身份。

每个阶段包必须包含原AT→实际节点→真实行为→证据矩阵，源码/lock/schema/goldens、实际runtime/bundle/receipt、driver及变更、原日志、所有读写依赖和产物的SHA/长度清单。先脱敏后封存，内外清单的转换关系明确。合法/拒绝/unknown/恢复/清理都交原始记录，不能只交passed总数。

独立审查发现的同范围问题由主执行者集中修复并重交该段，不等逐条新派工。只有改变架构/权限合同的真实冲突、无法满足原API合同的可复现证据、缺少具体live授权等才需要决策；先交现有成果、影响范围和可执行选项。

## 7. 长模块完成标准

23项原AT全部有独立裁决，Gate-R/V/L/M/P/G0/G均按其真实范围通过；单Writer、多步、共享调度、真实9节点恢复和16节点角色接线有完整证据。静态全部通过仍不替代L01或独立领域验证。

此时可将本模块全部23项登记done，项目任务计数才会从最初17推进到40/49；当前为24/49，剩余L01和C–F十六项须逐门独立接受。余下9项F01–F04/Q01–Q05仍按第07/08份执行。Gate-G只交付流程和角色迁移，不宣布全文publication_ready、Figure质量、默认切换、D5或发布冻结。

## 8. 可直接交给主执行者的完整指令

```text
执行 docs/dsh_execution_20260928/stage04_06_long_module_execution_20261004.md 全文，并遵循其索引的原第04/05/06份、interfaces、verification和49项任务表。
承担“DSH持久执行与主流程接线”完整长期模块，23项：R01→R02→R03→R04→V01→A01→V02→L01→M01→M02→M03→P01→P02→P03→P04→G01→G02→G03→G04→G05→G06→G07→G08。
默认由你一个主执行者连续完成Python、TS、测试和交付；无需维持两窗口或并行。有独立稳定工作面再按实际需要分工，明确路径/写权，不回滚其他人的基线；共享协议/validator和peer/build各始终只有一位写者。
第01–03份和A七项已独立通过，当前24/49完成；L01 in_progress，最近实际请求为packet14。先按本文件§9完整执行Gate-L解阻批次：显式非thinking与强制原生terminal、完整wire/grammar验证、错误流计量和诊断、packet14具名abort/unknown恢复包；统一收口后冻结完整/cold并交独立QA。§9.8是本批可直接转交指令，packet10文档仅保留通用约束与历史证据。保留冻结和具体live授权边界；不要重做已验A，也不要每完成一个helper就交回等下一条指令。
A段Gate-R/V已通过；接续交B段Gate-L、C段Gate-M、D段Gate-P、E段Gate-G0、F段Gate-G的完整冻结包；保留独立QA，不自行宣称PASS。前置已过且读集释放后按此指令接着下一段，无需重新布置同范围工作。
L01保持原具体live授权条件：先做完离线链和可审查执行包，冻结输入/模型/wire/额度/时限/停止条件。已有明确授权直接引用；没有则集中提交具体范围，不提前调用8006或以probe偷跑。Gate-L未过不开展M/P/G正式集成或标done，可做具名离线研究准备。
每段复用原Python预算/恢复/解析/发布owner；unknown保留占用、不盲重发，源码与运行组成现场校验，材料/Unicode/引用链保持已验规则。产品默认parallel=false；实施人手串行不删除P01–P04产品验收。
G01–G03先证明真实Research9节点新进程恢复；G0通过再做G04–G08。最终16节点有真实角色、独立verify和callback，不能靠默认handler/last_result/fixture executor伪装完整迁移。
每个阶段保存原AT矩阵、精确命令/退出、运行字节、请求/费用/恢复事实及清理，更新任务表与实施记录；中途换会话从真实记录接续。完成到Gate-G整模块交付，第07/08份另属后续模块，不切默认入口、不自动宣布D5或发布。
```

<a id="gate-l-unblock-20261005"></a>

## 9. Gate-L 集中解阻与后续连续执行（2026-10-05）

证据核验时点为 2026-10-05 21:35–21:41（Asia/Shanghai）；本节按用户要求于 2026-10-05T21:50:19.465341+08:00 纳入原执行文档。原[诊断指令快照](</home/cuihengjia/agent/Code2Paper copy/.dsh-dev/run/gate-l-unblock-20261005/gate-l-unblock-instructions.md>)和探针保留原字节，后续派工以本节为准。本文是下一批执行指导，不是 Gate-L 裁决、服务重启许可或新模型调用授权。

### 9.1 当前结论和本批目标

项目实际为 **24 done / 1 in_progress / 24 planned**；长期模块 **7/23 done**。L01 已实际调用 7 次（packet02、09、10、11、12、13、14），不是调用了 14 次。Gate-L 仍 FAIL；M01–M03、P01–P04、G01–G08 共 15 项保持 planned。

当前有两个必须一起解决的阻塞：

1. **当前请求配置仍使用发生错误的服务端组合。** packet14 已真正传递强制具名工具，但服务在 reasoning 输出期间 grammar FSM 失败。再修一个清理 helper，并不能解决生成失败。
2. **packet14 无真实 usage、无合法 finish，原后端 owner 仍 held。** 历史正常结束退役合同不能直接处理它；主执行者最新报告也明确本批尚不执行原14迁移。仅完成当前 P1/P2 和完整测试，仍无法准入下一次请求。

本批统一目标是：**限定 L01 显式关闭 thinking，保留强制原生 c2p_terminal 和全部内容门；完成错误流计量/诊断；做完 packet14 可审查的恢复方案；一次性冻结验证后，准备一个有实质变化的新执行包。** 不再把每个小修复当成一次完整交付。

### 9.2 依据及证据边界

- 主执行合同：[长期模块 §B–F](</home/cuihengjia/agent/Code2Paper copy/docs/dsh_execution_20260928/stage04_06_long_module_execution_20261004.md>)、[L01 协议](</home/cuihengjia/agent/Code2Paper copy/docs/dsh_execution_20260928/stage04_L01_execution_protocol_20261004.md>)。
- 恢复及封存原则：[整批接续指令 §4–§7](</home/cuihengjia/agent/Code2Paper copy/docs/dsh_execution_20260928/stage04_L01_packet10_repair_and_continuation_20261005.md>)。其中 packet10 等具体状态和旧 candidate 命令属于历史，不能覆盖当前 packet14。
- 最新实现者记录：[provider-error 修复报告](</home/cuihengjia/agent/Code2Paper copy/docs/dsh_execution_20260928/stage04_L01_provider_error_repair_evidence_20261005.md>)。
- 独立结论：[packet14 事后 QA](/tmp/c2p-dsh-independent-l01-packet14-postlive-20261005-01/review.md)：实际436项输入，Gate-L FAIL；P1 默认零计量、P2 错误首因；normal-finish 授权 DOES_NOT_APPLY，实际审查读集已释放。
- 本次新观察：[原适配器零网络对照](</home/cuihengjia/agent/Code2Paper copy/.dsh-dev/run/gate-l-unblock-20261005/nonthinking-wire-result.json>)。仅证明客户端序列化；不是实际 Host、完整领域 schema、服务端 grammar 或 Gate-L 证明。

| 最近失败 | 已证明的事实 | 下一批应处理的层 |
|---|---|---|
| packet10 | 模型 terminal 缺 schema_version，后续清理问题遮住首因 | 保留已修合同及拒绝分支，不重修旧输出 |
| packet11/13 | 普通文本，没有原生工具调用；13已正确结费/释放 | 保留已实现 named tool_choice，不能退回普通文本解析 |
| packet12 | 非法/未注册工具名 | 保留 unknown-tool 拒绝与已验历史退役 |
| packet14 | HTTP200 内 SSE error500，无 usage/合法 finish/tool；服务日志同请求 grammar FSM 拒绝 [13,198,248069] | 优先验证 reasoning→grammar 兼容，同时处理 error/unknown 生命周期 |

本机 tokenizer 中 248069 对应 `</think>`，13/198 对应句点/换行。这支持“reasoning 结束边界与 grammar 不兼容”的排查方向，**尚不证明唯一根因**。当前 on-disk scheduler 已有结束 token 特判，不能继续通过吞 token、忽略 grammar 错误或伪造 finish 来放行。

### 9.3 第一项：用现有适配器实现明确的非 thinking L01

本次使用当前 tool-choice.2 的原 PiAiAdapter 做了两次 fake-fetch 对照，实际网络/模型/tokenize 均为0。结果：可以发送 `chat_template_kwargs.enable_thinking=false`，去掉 reasoning_effort/thinking_token_budget，并保持 tool_choice、tools、messages、温度、输出限额等其他字段一致。**仅为关闭 thinking，不需要再打新的 DSH runtime 补丁。**

vLLM 官方也提供请求级 [enable_thinking 控制](https://docs.vllm.ai/en/stable/features/reasoning_outputs/)；实际兼容仍以本机安装版本、模板和完整 native 请求的验证为准。

必须在同一修改批次处理三处，不能只改 JSON：

| 文件 | 具体修改 | 必须验证 |
|---|---|---|
| `tests/live/profiles/qwen38_dsh_l01.json` | provider.reasoning 改 off；删除 thinkingBudgets；compat 增加 thinkingFormat=`chat-template`、chatTemplateKwargs={`enable_thinking`:false}；更新 thinking_scope | named c2p_terminal、模型、温度0.6、32768/4096、180秒、0 retry、原 backend 根全部保留 |
| `integrations/dsh/dev/l01_worker.py::prepare` | 去掉硬编码 reasoningEffort=low；从冻结 profile 取实际选择，显式生成 off 的 model.options；对应 Writer thinking reserve 按该模式生成；有效配置进入 composition/model/profile 身份 | 不再由 worker 把 off 覆盖回 low；不要顺手改写已有 Formalizer fixture 预算或原领域义务 |
| `integrations/dsh/dev/l01.mjs` 的 prepare/calibration | 将写死 low/1024 的断言改为按冻结 profile 精确验证；对本模式要求 explicit false，禁止 reasoning_effort/thinking_token_budget 残留 | 实际 native 校准 wire、tokenizer 投影和最终发送材料相同；不能删除断言后让任意配置通过 |

目标 wire 的相关字段如下，完整 tools/schema/messages 仍由原链生成：

```json
{
  "tool_choice": {"type": "function", "function": {"name": "c2p_terminal"}},
  "chat_template_kwargs": {"enable_thinking": false},
  "max_tokens": 4096,
  "temperature": 0.6
}
```

只写 `reasoning=off` 不够：适配器可能只是省略 effort，而服务模板默认 thinking=true。必须检查上述显式 false 最终出现在真实序列化请求中。输入 tokenizer 必须消费完全相同的模板字段；不能沿用 packet14 的旧 token 数或旧校准 receipt。

#### 服务端只读确认与零生成验证

先使用现有记录，不再寻找旧 GPU6 脚本作为当前事实：

- [实际8006进程记录](/tmp/c2p-dsh-l01-packet13-tool-choice-investigation-20261005-01/current-server-process-readback.json)：记录时 PID3597064/GPU2，model `/data1/users/cuihengjia/qwen3.8-modelopt`，tool-call-parser `qwen3_xml`，reasoning-parser `qwen3`，未显式指定 chat-template。它是观测快照，不保证此刻 PID 仍相同。
- [安装版本记录](/tmp/c2p-dsh-l01-packet13-tool-choice-investigation-20261005-01/current-installed-vllm-readonly.json)；editable source 为 `/data1/users/cuihengjia/qwen3.6/vendor/vllm-cu128-src`。
- [packet14 同请求错误记录](/tmp/c2p-dsh-l01-packet-20261005-14/server-error-readonly-log.json)；原日志 `/data1/users/cuihengjia/qwen3.8/logs/vllm-qwen38-nvfp4-gpu2-8006-script.log`。
- [本机模板](/data1/users/cuihengjia/qwen3.8-modelopt/chat_template.jinja) 支持 enable_thinking；文件路径和当前磁盘字节不等于实际已加载字节。

用本机 tokenizer/template 与安装的 grammar 编译器，在不连接8006、不加载模型权重的独立进程中验证：① 当前完整 c2p_terminal schema 能编译；② 非 thinking 提示前缀已关闭思考区；③ 当前 reasoning/parser 能识别该前缀状态；④ 结构约束进入工具参数阶段。记录版本、模板/schema/tokenizer 摘要和实际结果。合成参数只作 grammar 测试，不能作领域或模型输出证据。

这项静态检查应有界完成；若安装/API/依赖使其无法执行，提交具体缺口，不能拿客户端小 schema 探针代替。先集中核实实际 parser/模板/structured-output 和 speculative 配置，不再改题目、换模型或无证据切 named→required。磁盘存在 MTP 启动脚本不能证明8006开启了 MTP。

**出口：** 一份完整 native prepare 的 wire 对照、模板/grammar 报告及未证实项。非 thinking 是限定 L01 的新配置，不声称验证原 low-thinking 或 Python profile 等价。

### 9.4 第二项：把 packet14 的错误流修复一次收全

沿主执行者已有 P1/P2 修改继续，不另起一套 accounting、TaskStore 或 reader。最新68项聚焦、native错误流等结果属于实现者报告；必须保留各自身份，不冒充本次独立验收或当前完整证书。

本批最小统一状态矩阵：

| 实际 provider 结果 | 计量/占用应有行为 | 领域行为 |
|---|---|---|
| 合法工具 + 真实usage + 合法完成 | 原账本计费；受信完成登记；原owner正常释放 | 原 parser/assessor 决定 receipt |
| 合法完成，但普通文本、未知工具或 schema/content 拒绝 | 真实费用仍收；满足已验完成合同可释放 | 保留具体拒绝，不补正文/工具名/字段 |
| partial reasoning + error + DONE，无usage/finish | actual usage UNKNOWN；新运行保留reservation/owner；无自动重发 | 首因 provider_sse_error，无领域receipt |
| SDK fallback usage0/0 + error | 不能成为受信usage或stream_complete | 保留错误事实 |
| 真实usage input0/output>0 | 保留真实计量；无完成凭据仍不能释放 | 不因cached输入零值误判所有usage无效 |
| 有usage但无合法finish / 有finish但无usage / 断流 / timeout | 按原合同保留相应不确定性；不得提前退款、完成或释放 | 无伪造成功 |

每行都走真实 Loader/native adapter/Session/原 Python worker；只有 provider 为隔离 fake。每行输出真实到达数、原 budget reader、task、backend、receipt 和新进程读回。追加重放/重复settle、错误 owner/fence、未知凭据、后续owner保护等已有反例，保留旧 packet 类别及三终态正例。

测试落点优先复用 `integrations/dsh/tests/writer-provider-error.test.ts`、`cancellation.test.ts`、`host-provider.test.ts`、`writer-request.test.ts`，以及 `tests/integrations/dsh/test_host_recovery_boundaries.py`、`test_l01_binding_contract.py`、`test_coverage_use.py`、`integrations/dsh/dev/tests/test_l01_meter.py`。补齐新增模式及实际遗漏场景，不复制已经证明且未变的整套测试。

**出口：** 当前源码对上述矩阵闭合；第一错误、费用可信度、provider完成与领域结果分别可读。历史 packet14 的七条账本事实不被新 reducer 标签静默改写。

### 9.5 第三项：先做完 packet14 具体恢复包，再集中申请必要操作

这不是“清锁”。packet14 的真实 usage 缺失，原reader的 spent0/pending0 是 SDK 默认零造成的历史观察；不能称实际费用已结清。当前 `release_observed_finish` 要求 validated usage 和受信自然完成，故改 profile、静态PASS、idle、DONE、本地进程退出都不足以解除原owner。

主执行者先只读查找是否已有绑定同 request/session/server instance 的受信服务端结束与usage记录。若能够补齐，仍须按可追踪历史恢复合同处理，不能伪造旧 execute claim 登记。

若实际 usage 无法恢复，必须提交**版本化 abort/unknown 恢复合同提案和隔离验证**，不要再尝试复用正常结束退役。完整提案一次回答：

1. **原执行确已停止的权威从哪里来？** 优先服务所有者提供可验证、绑定原请求与服务实例的终止确认；若当前服务无此能力，准备具名 drain/stop/restart 方案，列明实际受影响进程/共享用户、全进程范围与GPU执行排空证明、新server epoch。单条日志、PID消失或空闲指标单独不够，也不直接执行重启。
2. **未知费用如何保留约束？** 明确“execution已被确认终止”和“实际usage仍未知”是不同事实；保留原失败账本和unknown审计，不补造数值、不退款、不让旧run续跑。若需新增保守预算记账/隔离处置，必须明文定义其权威、余额约束、原reader兼容与准入影响；不能把估算标为provider实测。
3. **何时允许退役 permit？** 现行合同要求unknown阻断整个resource group；不能在unknown标签未解决时直接删owner。只有上述新合同得到独立审查并获得具体授权后，才能按其足够的终止及预算证据执行具名迁移。合同证据不足就保持held，明确缺口。不要把本指导写成已获得该例外。
4. **唯一写入范围是什么？** 绑定 exact14 execution/resource/task/epoch、旧六条history、原七条费用事实、输入和实现摘要；原库事务内校验owner及追加不可变恢复凭据。若合同确需新增费用记录，逐项列出，不能暗含在“release”里。旧task/正文/receipt/失败记录不变；重复执行幂等，新owner不受影响。
5. **隔离证明是否完成？** 用原材料的保护副本演练成功、缺证、错owner、旧server epoch、重复操作、事务中断及新owner竞争；独立review同一个完整包。只审查文字、不验证事务不算可执行方案。

这是当前最容易被继续遗漏的交付物。先完成代码/方案/隔离证明与准确命令，再向用户提交**一个完整的具体操作包**；不得先问笼统的“能否清锁/继续”。授权不同副作用可在同一包中分别列明前置，执行时仍按先恢复、后复核、再新请求的顺序。自动审批或新授权尚未发生，本次没有任何真实释放操作。

**出口：** 合法恢复后的独立读回与共享后端准入证明；或具体到缺失权威的恢复方案，等待一次必要决策。没有此出口，新模型请求不能启动，但§9.3–§9.4的离线工作不必等待。

### 9.6 第四项：停止逐点重跑，集中冻结一次完整包

1. 将§9.3–§9.4代码、测试、profile、schema/来源清单及§9.5恢复合同先全部收口。维护当前 tool-choice.2 的实际来源/构建回执；不要把代码写死为旧 candidate。新runtime补丁只有在确有必要且有单独证据时才增加。
2. 最终完整前先做小成本检查：typecheck、测试discovery/NodeID唯一性、动态candidate选择、完整schema编译、实际native矩阵。此前完整06–08的中断/fixture candidate/重复ID不应再次消耗整轮验证。
3. TS/构建输入变化后统一 build/stage/audit 一次；只改 profile/文档不无故反复构建。所有身份输入关闭后执行当前注册 `dsh-stage04` 完整证书及fresh cold-normal companion。复用现有launcher和计划，核对当前 core/offline版本（当前报告为8）及实际CLI，沿用最后成功完整命令结构，换fresh目录和当前candidate；不要照抄历史packet02命令。
4. 主执行者统一更新 README、L01协议、长期模块当前摘要、task_board和implementation；L01.current_instructions及current_long_module_progress.as_of不能继续指向旧状态。**这些更新必须在最终身份冻结前完成。** 执行中只写外部日志/sole-writer execution-index。最初的诊断指令保存在忽略的run目录；本次按用户要求并入原长期模块。写前已核对独立读集释放、execution-index允许source writes且当前完整尚未执行。主执行者将本次文档修改纳入下一份当前身份，不复用更新前的证书。
5. 完整矩阵/全量报告和所有句柄exit、代码/validator/runtime/wire/模板绑定一次交独立QA。已有读集未释放不能边审边改；已释放且同范围工作无须逐helper请求开工许可。
6. 若当前完整10已经在跑，回收原句柄并保留实际结果，不为采用本文盲目杀进程；它仅证明所绑定版本。最终必要验证按实质变更重做，不能改标签复用，也不能无变化连续重跑。

新包准入应同时具备：原owner合法恢复、完整/cold当前身份、显式非thinking完整wire和真实tokenizer投影、1 primary/1 tokenize/0 retry-repair-aux、32768/4096/180秒、health/models/queue/KV和fresh输出监控、精确停止条件、独立审查、针对该新包的具体授权。旧七次primary授权均不能复用。

如果一次新授权请求仍出现同类 grammar 错误，立即转入8006服务端专项修复，绑定实际加载版本、reasoning结束边界、grammar编译/推进和（若实际启用）speculative decoding；先隔离复现、再准备具名服务改动。不得继续微调提示、自动重试，或在Code2Paper吞token/放松usage与领域门。

### 9.7 Gate-L 后直接推进较大的完整模块

真正取得合法原生参数、有效usage/finish、来源/内容合同、局部receipt及生命周期证据，并经独立 Gate-L PASS、释放审查读集后，L01 才改done：25/49。

随后同一主执行者连续实施原长期模块，不必再逐小项请示：

| 整段 | 一次交付范围 | 独立退出门 |
|---|---|---|
| C | M01 授权限量读取/revision → M02 compaction后恢复原材料并重新计量 → M03 每请求身份、总账本、单terminal及跨进程恢复 | Gate-M |
| D | P01–P04 同主机共享调度、wave、公平性、两进程故障与unknown组级阻断 | Gate-P |
| E | G01–G03 真实LangGraph九节点持久状态及逐节点新进程恢复 | Gate-G0 |
| F | G04–G08 Research/Writer/独立verify/callback及完整16节点接线恢复 | Gate-G |

现在就可准备 C 的只读接口/持久字段/反例清单，正式M/P/G集成仍遵守原Gate-L前置。保留默认单Writer及parallel=false；限定L01非thinking通过不等于全文质量、D5、默认切换或发布。

### 9.8 可直接转交主执行者的指令

> 请按本指导做一个完整 Gate-L 解阻批次，不再按小缺陷逐次冻结。保留 packet14 P1/P2 修复，新增“显式非thinking + 强制原生c2p_terminal”的限定L01配置，并同时修复profile、worker、prepare三处一致性；先做完整wire/模板/grammar与真实native隔离矩阵。把packet14的abort/unknown历史恢复方案、事务实现与保护副本验证纳入本批；缺usage保持UNKNOWN，现行normal-finish授权不可套用，先形成可审查的具体操作包。所有改动和文档一次收口后再冻结当前完整/cold并交独立QA。新模型调用只在原owner合法恢复、当前证据与新包具体授权齐备后执行一次，无自动重试。若仍为同类grammar错误，进入具名8006服务端兼容修复，停止提示层试错。Gate-L独立PASS且读集释放后，直接完成C段M01–M03，再依原长期合同连续推进D–F。

诊断验证范围：原适配器序列化零网络探针 exit0；[绑定检查记录](</home/cuihengjia/agent/Code2Paper copy/.dsh-dev/run/gate-l-unblock-20261005/diagnosis-verification.json>)证明其当时输入。文档同步记录保存在 `.dsh-dev/run/gate-l-unblock-20261005/doc-integration/`。本次只修改执行文档及任务接续字段，没有新增模型/tokenize、执行旧owner迁移或修改8006服务，也不宣称当前整包QA通过。

[返回执行入口](README.md) · [第04份详细落地要求](stage04_batch_execution_instructions_20261004.md)

### 9.9 本批实施收口与冻结验证入口

主执行者已实现显式非thinking/profile–worker–wire–原发送门绑定，Writer独立reserve0且原Formalizer1024保持；错误流UNKNOWN计量、首因报告、operator-only恢复合同与严格history原reader、保护原14七场景及真实native错误生命周期矩阵已实施。首次集中独立审查1104输入提出U1–U3，实际读集释放后同批修复；详见[本批实施证据](stage04_L01_provider_error_repair_evidence_20261005.md)。

完整10实际1867/fresh cold1及两个原读取器通过，fced96d6…/f466801c…身份稳定。最终独立QA实际1606输入，U1–U3闭合，CHANGES_REQUIRED仅U4嵌套授权/终止字段bool–integer弱等值；全部本人实际读集已释放。主执行者已集中改为类型保真的canonical JSON结构绑定并补拒绝路径，10保留原身份历史，不重贴当前。下一步冻结新版本10完整/fresh cold到 `/tmp/c2p-dsh-l01-admission-20261006-11`，之后原两读取器与独立QA；本文收口时11未开始。结果与运行句柄写外部sole-writer execution-index，验证/审查期间本文与源码一起冻结。实际服务兼容尚未通过；packet14实际UNKNOWN/held、24/1/24、七次live、Gate-L FAIL不变。

具名整epoch stop/restart及UNKNOWN迁移方案已提供精确epoch/process/GPU/shared-client影响、非秘密配方观测和保守费用政策；真实终止、owner配方确认、独立操作审查和distinct授权仍缺。未修改服务、未释放canonical、未生成packet15或新模型授权；正常结束授权不适用。


## §9.9 packet16 后解除冻结的接续范围（2026-10-06）

当前原执行已独立裁决 Gate-L FAIL：packet16 有真实 native stop 与已结算 usage，
领域内容拒绝且原 owner held。用户已授权按具体方案开发验证，原完整11仅历史身份。
本批完成登记、Writer可见 canonical 语义与 exact-owner历史恢复合同，详见
[返修记录](stage04_L01_native_stop_repair_evidence_20261006.md)。新完整/cold与独立审查后，
先形成恢复具体包与 fresh live包；此开发回复不授权直接释放占用或新模型请求。
项目24/49、L01实际8次生成；Gate-L实际独立PASS后继续原M→P→G整段并保留阶段门。
不要应用旧packet10同步补丁，不重发失败包、不降低 Formula/语义/atom门。
