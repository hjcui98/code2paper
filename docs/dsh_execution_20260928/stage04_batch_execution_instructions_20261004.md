# 第 04 份整批执行指令：持久运行控制、单 Writer 离线闭环与真实准入

> 2026-10-04 调度与范围接续：用户要求按需要决定并行，并扩大为长期模块。当前总派工为[第04–06份长期模块](stage04_06_long_module_execution_20261004.md)，共23项；本文件保留为其A段七项的完整落地细则。**默认一个主执行者可连续承担Python和TS全部责任，下列窗口一/二分工只在实际拆分协作时适用。** 原AT、Gate-R/V与L01条件不变。

2026-10-04。本指令承接 [Gate-C 独立复验](stage03_gc_repair_acceptance_20261004.md)，实施原第 04 份 **R01→R02→R03→R04→V01→A01→V02** 七项。第 03 份六项已通过独立验收；本文件只是下一批派工，七项目前仍 planned，不把指令发布记成实现完成。

本段终点：一个 run、一个 Writer、一个受预算保护的 DSH 请求，经真实 Python worker、持久 claim/reserve、实际 DSH 派发、原始 terminal/Session、同源 ingest 和原 publication reader 完成局部事务；正常/故障恢复使用同一事实；真实 CLI 和离线准入回执覆盖这条路径。主执行者汇总一个完整冻结包，独立裁决 **Gate-R、Gate-V**。随后依长期模块继续；领域仍保留 pending_validation，L01 真实模型调用遵守原具体授权条件。

## 1. 必读依据与已存在的实现

| 顺序 | 文档 | 约束 |
|---|---|---|
| 1 | [仓库文档入口](../README.md)及架构权威顺序 | DSH 执行 Agent，Python 保留事实、预算、验收及发布权威 |
| 2 | [DSH 总设计](../code2paper_dsh_plugin_design_20260922.md) §§11、15.4–15.5、20–21 | 持久运行、单 Writer 闭环、准入和阶段界限 |
| 3 | [本轮 Gate-C 裁决](stage03_gc_repair_acceptance_20261004.md) | 已通过输入、三组关闭范围及 QA 读集释放 |
| 4 | [原第 04 份](04_serial_writer_integration.md) R01–R04/V01/A01/V02；[task_board](task_board.json) | 七项原 AT 与正式依赖，不删减、不改成测试数量门 |
| 5 | [interfaces](interfaces.md) §§1–7、[verification](verification.md) Gate-R/V | caller/claim/fence、唯一账本、unknown、幂等、组成、真实覆盖回执 |
| 6 | [当前 H02 冻结](h02_interface_freeze_020.md)、[第 03 份原指令](stage03_batch_execution_instructions_20261003.md)及[GC 修复裁决](stage03_gate_c_review_and_batch_repair_20261003.md) | 真实 DSH API、已验材料/字符规则/依赖链/局部恢复合同 |

原第 04 份顶部 2026-10-02 的 H/K 未过提示属于历史。正式依赖仍按七项顺序完成；阶段内已有有意义的前置实现和本地合同后可连续推进，不要求每个 helper 单独等用户派工。

当前已有 `src/code2paper/integrations/dsh/{facade,worker,protocol,writer_contract,artifacts,result_ingest,local_meter,runtime_inventory}.py`；`integrations/dsh/src/{writer-request,wire,request-accounting,request-contract,session-binding,terminal-result,role-dispatch}.ts` 也已存在。早期任务卡曾把其中部分写成“拟新增”，本轮已按实际路径纠正；实施时扩展原 owner。

目前尚无本批 `task_store.py`、`invocation_adapter.py`、`kernel-client.ts`、`workflow-driver.ts`、`execution-policy.ts`、`cli.ts` 及对应七项完整接线。本阶段不得用第 03 份 `stage03-controlled-context` 或测试 recorder 代替持久 claim/预算权威。

## 2. 主执行者、按需协作与四次交接

保留当前 worktree、dirty 基线、`codex/agentic-p4-benchmark-cutover` 分支和 `d48b4e4b22c94c82b45d2179ba452d72b164102d` HEAD；不切分支、清理、提交或合并。

默认单主执行者完成全表职责；只有稳定接口、独立文件和资源允许时才拆分。表内“窗口一/二”是可选职责划分，不要求两个窗口同时工作。共享Python/validator和peer/build始终各只有一位实际写者，单人模式均由主执行者承担。四次交接在单人模式是内部接口检查点。

| 责任 | 窗口一 | 窗口二 |
|---|---|---|
| 主任务 | R01、R02、R04 Python 部分、A01 | R03、R04 TS/进程部分、V02 |
| 联合任务 | V01 的真实领域/worker/reader、恢复与预算断言 | V01 的 DSH/adapter/Session/真实 CLI 与 wire 断言 |
| 共享 Python | 独写 facade/worker/protocol/合同导出、原账本/身份/validator 清单、A01 CLI 原 owner | 提交接口和失败语义需求，由窗口一落地 |
| 共享 TS 与构建 | 接收最终构建身份；不改 peer/lib 或执行 build/stage | 独写 TS、测试与 package/toolchain；独占 peer/lib/build/stage |
| launcher 必要扩展 | 提供 worker/RPC 及准入机器报告要求 | 若 A01 需要新增 Node 结果路由，可由窗口二单写 `scripts/dsh_dev.py` 的开发 launcher 部分并保持 B02；窗口一不同时编辑该文件 |

四次交接必须有可执行材料：

1. **R01/R02→R03：**窗口一交持久 claim/事件/RPC schema、错误码、真实 worker argv、fixture、拒绝语义和本地回执；尚未完成的方法继续 unavailable。窗口二可先准备真实 API 接入和测试，不把假 reserve 的成功计为本地合同成立。
2. **R03→R04/V01：**窗口二交一次请求完整时序、实际 adapter/capture/accounting 证据、零发送负例、provider 清理所有权；窗口一把崩溃点接进原 reducer。
3. **V01→A01/V02：**共同冻结实际必测文件/节点、Node 发现规则、机器报告格式及 CLI 配置；A01 从真实结果构建回执，V02 用真实入口补齐最终计划。
4. **最终冻结→QA：**窗口二完成唯一最终构建并交当前 receipt/stage，随后两侧停止修改组成输入；窗口一汇总整包回归、完整矩阵和封存。最终 CLI 测试必须进入 A01 计划；不得拿 V02 落地前的回执给最终入口背书。

## 3. 七项具体实施要求

### 3.1 R01：持久任务、领取与独占

新建 `task_store.py`，扩展现有 facade/worker；复用原 `authoring_execution_identity.acquire_run_lease`、K02 publication/fence 原语。

1. 持久化稳定 execution/workflow/node/scope/task/epoch key、合同引用、outbox、claim owner/fence、epoch 起点、状态及终态 receipt 引用。重启、Host 换进程或重复 prepare 不生成重复任务、不清零 epoch。
2. 以实际原子写/锁/CAS 保护领取和终态；生产 Host context 来自持久领取及绑定，不能把 bootstrap 自报字符串升级为权限。第 03 份受控上下文只支持其明确测试用途。
3. run 独占和后端准入均可恢复；本阶段不支持第二个 DSH run 并发或跨 run 公平调度。PID 消失、TTL 到期、本地 idle 都不能证明 provider 静止并自动释放 unknown。
4. task_store 保存生命周期与引用，不记第二份可扣减余额。内容 revision 与 claim/reserve 的记账序号分开；领取本身不使刚准备的领域合同 stale。
5. 为 claim、取消、恢复读取定义私有 worker 方法，校验授权先于缓存；旧 fence 不能新建领域副作用，合法已提交重试仍可取回原不可变 receipt。

**必过：**两个独立 Host 进程以 barrier 抢同 task/epoch，恰好一个有效 claim；过期 Host、取消后的新 mutation、prepare/outbox 后崩溃、领取后崩溃均不重复任务/提交；新进程读回相同 epoch/起点；第二 run 与未静止 provider 拒绝。主测试 `test_task_recovery.py`。

### 3.2 R02：Python 唯一预算/发送账本与真实私有 RPC

扩展原 `unified_context_models.py`、`unified_invocation_ledger.py`、`writer_attempt_ledger.py`，新建 `invocation_adapter.py`。沿原 `read_run_budget_state`、`check_run_budget_before_send`、`reduce_invocation_recovery` 计算预算与恢复，不建立平行 reducer。

1. 明确版本化事件：reserve、adapter-attempt、dispatch-confirmed、proven-not-sent、send-outcome-unknown、usage、terminal、cancel、settlement。每个事实有稳定 ID、task/epoch/claim/fence、实际 request/attempt 绑定与证据引用。
2. 同一 ID 同一内容幂等；同 ID 不同内容、错 execution/epoch、未经授权来源拒绝。模型输出不能提交可信 usage、dispatch 或余额。
3. 在同一有效 lease 中重读当前 read-set、完整 C00 依赖、fence、已有 unknown、真实余额和 epoch 请求/input/output/工具/时限限制；持久 reserve 成功以后才返回可派发许可。
4. 旧 `sent_to_caller` 保留原边界语义。adapter 入口、`next()` 调用、HTTP 已送达分别记录；缺乏 transport 证据时保守 unknown，不能把 usage 缺失当零费用。
5. 已发送的格式失败、blocked/research_required、内容拒绝、取消仍保留实际费用；只有有正向证据的未发送才按原规则结算/释放。已有原始响应走本地 settlement，不重发来恢复。
6. 把 reserve/dispatch/settle/mark_unknown 接到真实 worker 方法 allowlist 和严格 schema；保持短 RPC、1MiB frame、artifact 句柄、stdout 协议/stderr 诊断。worker 不等待模型生成，也不在 Python 隐藏调用模型。

**必过：**prepare 后余额耗尽、零预算、reserve 落盘失败、读取依赖损坏、旧 fence、已有 unknown 均在实际 DSH seam 前零发送；重复 usage 不双扣；缺 usage/失联不退款；录下响应未结算仅本地恢复。用真 worker RPC 验，主测试 `test_invocation_events.py`。

### 3.3 R03：真实 Host 执行循环与发送前守卫

新建 `kernel-client.ts`、`workflow-driver.ts`、`execution-policy.ts`，扩展已有 `request-accounting.ts`，复用 session-binding、role-dispatch、request-contract、TerminalArgumentCapture 与已验 native Writer 注册。

1. 通过当前 H02 冻结的 DSH subprocess API，以固定 argv/env/cwd 启动真实 Python worker；采用独立受控 run/artifact 根，显式共享跨 namespace 路径。模型参数不能变成任意路径、命令或导入入口。
2. 完整时序：持久合同/outbox → claim/fence → 创建期绑定 child → 现场核组成及冻结实际请求 → 真实 worker reserve → 单次 DSH dispatch → 捕获/flush Session 与 raw terminal → record_output → ingest → 原 reader 读取 receipt。
3. `prepare` 与 projection 保持零发送。第 03 份预先观测的假 wire 属于 fixture/兼容证据；在新集成中单列其设置阶段，正式任务的请求必须经过 R02。不得把未入账的“探测请求”加到生产准备流程。
4. 发送前再次核实际 JS/依赖/Loader/renderer/schema/model/options/cap 和 prepared generation；等待 claim/reserve 后若配置、fence、信号或正文改变，拒绝发送。复用已验不可铸造的 loop 来源，capture 与 accounting 消费同一来源。
5. 首版 terminal-only、一次模型请求；关闭 adapter retry、自动内容修复、title、compaction、递归工具。第二次实际请求无论由哪条路径引起，都在 seam 拒绝；typed blocked/research_required 不自动重试。
6. Host 只转发事实和引用，沿原 parser/assessor/authorship/publication 结算；不补正文、不写 supported/accepted，不把 tool success 当领域完成。

**必过：**真实 child/Session/worker 完成合法闭环；未绑定、过期 claim、seam 前组成/配置漂移、第二请求零发送；流/terminal 不完整具名失败；原日常 profile 与默认入口不改写。主测试 `host.test.ts`。

### 3.4 R04：逐崩溃点跨进程恢复与取消

两侧扩展上述 R01/R02/R03 文件；每个恢复场景启动新进程并读取落盘事实，不能只在同进程里调用两次函数。

| 注入点 | 应证明的恢复结果 |
|---|---|
| reserve 前 | 无发送/无已发送费用，按原任务状态恢复 |
| reserve 后、dispatch 前 | 不凭进程退出释放预留；确认未发送或保持 unknown |
| dispatch 后、响应未落盘 | unknown 保留预留与独占，不重发/退款 |
| terminal 已见、raw/Session 未 flush | 不用 closing prose 或 normalized 重序列化伪造 raw；从可信完整记录恢复，否则保持未解决 |
| record_output 后、ingest 前 | 只重放本地结算，不新增模型请求 |
| commit 后、回包丢失 | 同一授权重试取回原 receipt，无新 generation/二次扣费 |

取消先 abort，再用独立有界 cleanupSignal 等 provider 范围 `waitForExit`；只有实际返回 true 才证明静止，false/异常/超时保持阻断。不能复用已经 aborted 的请求 signal，也不能用 DSH idle 或父进程退出当 provider 退出。

覆盖父进程退而子进程仍活动、迟到原 epoch 响应、usage 后到、错误 epoch 响应、prepared dependency 缺失与变化、恢复时实际运行组成漂移。合法读取旧不可变 receipt 保持其权限规则；重新绑定旧任务继续派发须通过当前组成合同。主测试 `test_host_crash_recovery.py` 及对应 TS 生命周期测试。

### 3.5 V01：只有 provider 响应为假服务的完整闭环

共同新增 `test_serial_writer_e2e.py`、`serial-writer.test.ts`、`pi-ai-wire.test.ts`。输入复用已验非空 atom/target 技术页及合法无 atom 作者页、完成 Formalizer 与冻结 narrative/manifest/plan。

实际执行原 compiler/builder、C00 renderer、Python prepare、持久 task/claim/账本、真实 DSH Loader/child/loop、实际 pi-ai、native raw capture、原 assessor/authorship/publication/reader；仅 provider 接隔离 loopback 假 HTTP/SSE。不把 fake claim/reserve/stub assessor/手写页替换进被验链。

至少覆盖完整 draft→pending_validation、research_required→waiting、blocked、错误内容/公式/atom、Unicode 边界、缺失/损坏引用、unknown、cap 漂移、余量不足、取消和恢复。保存所有层的原始输入、wire、raw arguments delta、normalized、合同/账本/Session/回执及 reader 同代成员。Python 模型/网络出口拒绝哨兵必须有效。

本地假服务的 byte-id 计量及 usage 不能声明为真实 Qwen tokenizer/计量。实际 adapter 不支持某个 sampling/thinking 字段时登记未支持并阻断对应 L01 条件；不能静默删字段称为与 Python profile 等价。

### 3.6 A01：从真实执行覆盖生成离线准入回执

Python负责人（单人时为主执行者）先在原 `src/code2paper/cli/agentic_run.py::_record_offline_receipt_main` 和 `live_admission_preflight.py::build_offline_suite_receipt` 重现“只跑一个 pytest 节点仍默认填完整四组 labels”的问题，再修原入口。

1. 定义具名、版本化的 legacy 与 DSH 测试计划；实际 suite/目标/命令/runner/配置和报告组成 plan digest，不再把几个标签的排序摘要当作真实覆盖。
2. builder 不默认补齐未执行的计划；CLI 运行阶段要求的 Python、Node、跨进程及入口测试，并登记实际发现/执行的节点及 pass/fail/skip/cancel/零测试状态。
3. 每个子回执绑定实际 argv/cwd/runner、源/组成/validator/有效配置、机器报告及原日志摘要。测试前冻结身份，结束后重新核验；启动失败、超时、必测跳过不能生成全套通过。
4. consumer 从子回执/报告复算覆盖与 digest；同 label 换命令、伪填 label、篡改报告/输出、Node 未执行/失败/零测试、只有一个 Python 节点、空/错误有效配置、执行中身份漂移全部拒绝。
5. 旧模式不强行依赖 DSH；历史 0918、旧格式或局部回执只保留其明确范围，不能给当前 DSH 入口准入。记录真实有效配置，不持久化认证密钥。

主测试 `test_dsh_admission.py` 及受影响的原 live_admission/CLI 回归。与窗口二一起提供完整的 Node 报告路由和确定性发现证明，不能靠手写“165 passed”文本代替实际执行。

### 3.7 V02：显式 opt-in CLI 及最终准入闭合

TS负责人（单人时为主执行者）新增 `cli.ts` / `cli.test.ts`。先固定入口与配置 schema：显式选择实验 DSH 路径，显示实际 parallel=false，true 明确 unsupported；原产品默认继续既有驱动。

真实入口消费同一 I01 组成和 A01 真实覆盖回执，执行 R03 完整 Host 流程。假/过期/局部回执、错误候选、错模型/配置、runtime 漂移均在启动派发前拒绝。将 CLI 正反例加入最终计划；先完成这些测试，再形成最终阶段回执，避免入口测试用旧回执自证。

## 4. 阶段验证命令与统一证据

开发中按各任务跑聚焦反例；稳定后完成全部原 AT 和真实跨进程/DSH 联合矩阵。本批新增 Python 文件的最终基本集合：

```bash
python -m pytest -q tests/integrations/dsh/test_task_recovery.py tests/integrations/dsh/test_invocation_events.py tests/integrations/dsh/test_host_crash_recovery.py tests/integrations/dsh/test_serial_writer_e2e.py tests/integrations/dsh/test_dsh_admission.py
python -m pytest -q tests/regression_20260917/test_ledger_recovery_matrix.py tests/regression_20260917/test_run_identity_content.py tests/regression_20260917/test_live_admission.py tests/test_agentic_unified_context_compiler.py
```

这些新增文件目前尚不存在，实施后必须真实发现运行；缺文件/零测试/skip 不计通过。同时保留第 03 份五文件专项及原 publication/authorship/身份等受影响回归，按实际改动选原 owner 节点，不减少义务。

唯一构建写者串行完成最终构建及验证：

```bash
export C2P_DSH_CANDIDATE='0.2.0-rc.1+loop-origin.1'
export C2P_DSH_DEV_ROOT='/home/cuihengjia/agent/Code2Paper copy/.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1'
npm --prefix integrations/dsh run typecheck
npm --prefix integrations/dsh run build
npm --prefix integrations/dsh run stage
npm --prefix integrations/dsh run test:compat
python -m pytest -q integrations/dsh/dev/tests
python scripts/dsh_dev.py --candidate "$C2P_DSH_CANDIDATE" audit
```

当前真实 `test:compat` 递归发现 `tests/` 与 `dev/toolchain/` 内 `.test.ts`，可包含新增 Host/serial/adapter/CLI 用例。**早期第 04 份曾列出的 `test:integration` 当前没有定义，本轮已纠正文档命令**；若本批确有拆分需求，先实现并测试其发现/报告和同一隔离 launcher，再纳入 A01 计划，不报告不存在的命令通过。

最终输入和构建稳定后跑一次全静态 `python -m pytest -q -rs`、适用的 `python -m compileall -q src tests`、`git diff --check`。保留三项真实 live 未启用的解释，必需阶段用例不跳过。A01 最终回执使用的实际执行证据按原计划生成，不能把测试中构造的样例回执复制成准入证书。

## 5. 一次交付和停止条件

沿用 [第 03 份冻结规则](stage03_batch_execution_instructions_20261003.md#7-一次性交付清单与停止位置)：先固定输入、再构建/捕获身份、再测试和生成证据；协调文档若需在测试后更新，明确释放读集并登记身份变化。新裁决文件落地即进入原 validator 来源集合，不登记不存在的未来路径。

一个整包必须包含：七项代码/接口差分与原 AT 矩阵；真实 claim/reserve/dispatch/终态事件、请求字节和费用恢复；每个崩溃点的新进程证据；正常/拒绝/unknown/取消/合法重试；实际 CLI 与完整 A01 计划/子回执/原报告；前后组成与全部原始日志/输入/driver/runtime/bundle 的 SHA/长度清单；worker/child/provider/假服务关闭和端口释放。

运行与封存使用新的任务专属根，不覆盖第 01–03 份 owner/QA 包。跨 namespace 的产物目录显式共享。先脱敏再封存；如果把子包日志重新脱敏，保留变换规则、原件摘要与最终总清单的对应关系，区分子包历史清单和最终包摘要。

普通实现缺陷由主执行者及按需协作者在本段持续修复。实际公开 API 或现有 owner 无法兑现合同，集中给出真实最小反例、受影响 AT、已尝试办法及可行决策；不绕开门继续声称成功。

停止于完整 `submitted_for_independent_qa` 包。独立验收分别记录 Gate-R 与 Gate-V；全部对应 AT 及七项依赖满足才登记 done。后续 L01 单独获得具体模型/额度/时限授权后再核 health/models/队列/KV 和当前准入；本指令不触发任何真实模型或 tool-calling probe，不授权多步并发、主图迁移、默认切换、D5 或发布。

## 6. 主执行者指令与可选职责拆分

默认直接转交[长期模块§8完整指令](stage04_06_long_module_execution_20261004.md#8-可直接交给主执行者的完整指令)，一个执行者连续承担本份全部职责。仅确有需要拆分时使用下面两段；它们不设固定窗口数，也不替代长期模块的阶段接续。

### 可选Python职责（窗口一）

```text
执行 docs/dsh_execution_20260928/stage04_batch_execution_instructions_20261004.md 全文，连同原第04份、interfaces和verification。
第03份及GC-1/2/3已独立Gate-C通过，保留已验代码、原始封存和dirty基线；下一批按R01→R02→R03→R04→V01→A01→V02完整离线阶段推进。
你负责R01持久task/outbox/claim与独占、R02原Python唯一账本和真实worker私有RPC、R04 Python跨进程恢复、A01真实测试覆盖回执，联合V01。
独写Python领域/protocol/schema/validator/原CLI准入；窗口二独写TS和唯一peer/lib/build/stage。先交可执行claim/事件/RPC合同，不能用stage03-controlled-context或假reserve进入正式Host流程。
零预算/旧fence/unknown/坏read-set必须实际零发送；unknown保留预留；有原响应只本地结算；合法已提交重试读原receipt。逐崩溃点新进程验证，原三组GC回归保持。
修A01默认填满覆盖的问题，消费真实Python和Node/CLI机器报告；V02测试加入最终计划后，按新冻结组成生成最终回执。
内部合同成立即继续本批，不逐helper停工。与窗口二交一个完整冻结包，等独立Gate-R/V；不调用真实模型/8006、不提前L01或默认切换。
```

### 可选TS职责（窗口二）

```text
执行 docs/dsh_execution_20260928/stage04_batch_execution_instructions_20261004.md 全文，连同原第04份和当前H02实际接口冻结。
Gate-C已独立通过，继续原第04份整批；你负责R03真实Host/worker执行接线、R04 TS取消和provider清理、V02显式opt-in CLI，联合V01及A01的Node覆盖证明。
消费窗口一实际R01/R02 RPC，不用mock claim/reserve代替。复用已有session-binding/request-accounting/request-contract/terminal捕获，不另建预算账本。
通过固定argv/env/cwd的真实DSH subprocess启动worker；按claim→创建期绑定→实际组成/请求复核→reserve→单次dispatch→Session/raw落盘flush→record_output→ingest→原reader执行。
关闭retry/title/compaction/自动内容修复/递归工具；第二请求在seam拒绝。取消用独立有界cleanupSignal，仅waitForExit返回true才证明provider静止。
真实pi-ai只接隔离假HTTP/SSE；把合法/拒绝/unknown/崩溃恢复/CLI准入全部接入实际测试发现和机器报告。当前test:integration不存在，按文档§4处理，不能报告未执行命令通过。
你独占TS/peer/lib/typecheck/build/stage；共享Python协议和validator交窗口一。按§5一次封存完整包，等Gate-R/V；不启动L01真实模型或默认切换。
```

[返回原第 04 份](04_serial_writer_integration.md) · [返回执行入口](README.md)
