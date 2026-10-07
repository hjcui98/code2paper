# 04 · 持久运行控制、单 Writer 闭环与首次 live 门

> **2026-10-04 最新：** packet09已按明确授权完成一次真实调用，HTTP200、usage7359/891、tokenizer一致；预算结清、canonical backend正常释放。独立Gate-L仍FAIL：L01材料缺closed atom→detail归属及有效源语义锚，正在集中修复准备合同及乘法操作数反例，原门保留。完整certificate08及老占用退役已按各自身份PASS。当前24/49；C–F正式前置不变，旧具体授权均已消费。[实际记录与接续](stage04_L01_execution_protocol_20261004.md)。以下旧“当前”按历史身份解释。

> **2026-10-04 最新：** Stage A七项已独立验收；L01一次授权调用已消费，独立Gate-L FAIL，24/49不变。计量/工具编码提示/首因/后端完成生命周期正在同范围离线修复；[具体执行和失败记录](stage04_L01_execution_protocol_20261004.md)。C–F未正式准入，下列早期门状态保留历史身份。

> **2026-10-04 最新：[Stage A 独立验收](stage04_stageA_acceptance_20261004.md)，Gate-R、Gate-V PASS，七项全部done。** 当前24 done /1 in_progress /24 planned；L01仅离线执行包准备、真实推理0。QA读集已释放，沿原长期模块继续B；C–F保留原前置。以下早期“当前”均按各自冻结身份解释。

> **2026-10-04 当前：[Gate-C 已独立通过](stage03_gc_repair_acceptance_20261004.md)。** 本份纳入[第04–06份长期模块](stage04_06_long_module_execution_20261004.md)，默认一个主执行者、按需协作；七项离线任务具备前置，仍planned。[本份细则](stage04_batch_execution_instructions_20261004.md)§3–§5保留全部修改/反例/命令，长期模块§8为统一启动指令。本轮未实施本份，Gate-R/V待整包验收，L01仍需具体live授权。下方早期门状态按原时点解释。

> 2026-10-02当前：[返修差分与完整接续](stage_loop_origin_repair_acceptance_20261002.md)。本份仍排队，Gate-C后一次启用原R01–R04/V01/A01/V02完整离线阶段，窗口一Python/窗口二TS，正式Gate-R/V保留；L01仍需单独live授权。Gate-H仍CHANGES_REQUESTED，正式Gate-K未过。

> 2026-09-28 执行计划；所有实现和新测试均待实施。历史代码/环境证据不计为任务完成。

依据：总设计 §§11、15.4–15.5、20–21 WP4a/WP3a/WP3b。前后依赖以 [任务表](task_board.json) 为准；接口遵循 [interfaces.md](interfaces.md)。

先证明单 run、单 Writer、一个模型请求的真实 DSH mock 闭环；经独立 live 授权才验证一个 Qwen 请求。

### 单一运行权威

[unified_invocation_ledger](../../src/code2paper/agentic/unified_invocation_ledger.py) :722/1034 与 [reduce_invocation_recovery](../../src/code2paper/agentic/writer_attempt_ledger.py) :329 是预算与恢复 owner。扩版本化事件事实，不能在 TS、task_store 或 scheduler 存第二本余额。旧 sent_to_caller 仅证明 Python caller 边界；新 adapter attempt、transport dispatch、not-sent 与 unknown 分别有证据等级。

最低完整时序是：prepare持久合同 → outbox → claim/fence → child创建绑定 → 冻结实际请求复核 → Python lease内重读预算并reserve → DSH单次dispatch → terminal/Session落盘与flush → record_output → 同源ingest/局部commit → 读取receipt。仅工具成功不是领域成功。正常中断/恢复与故障恢复读取同一事实。

本阶段使用一个 run 和独占后端准入，不实现跨 run 公平调度。这个控制只能约束接入该锁的调用者，不能保证本机其他客户端不访问模型；live 前由操作者检查实际占用。默认parallel=false，开启返回unsupported，不能静默忽略开关。关闭retry、auto content repair、title、compaction和递归工具；任何第二请求在真实 seam 拒绝。

### 必须单独修复的准入缺口

[CLI _record_offline_receipt_main](../../src/code2paper/cli/agentic_run.py) :780/791/819 只运行可配置 pytest 目标，却不向 builder 传实际覆盖；[build_offline_suite_receipt](../../src/code2paper/agentic/live_admission_preflight.py) :149/157 默认填全四组 labels。现 matches :118 检查的是声明集合，test_plan_digest 没据真实执行重算；preflight :551 还传空 effective config。本轮仅静态核实，A01 先做最小 CLI 反例再修原 owner。

A01 的阶段回执从实际执行结果派生，记录每个 suite 的计划规格、argv/cwd/runner、实际目标/集合、退出码、机器报告和输出摘要；测试前冻结身份，结束后再核对。Node未启动/失败/零测试、必测被跳过、只有一个Python节点或伪填label都不获完整覆盖。合法非必测live deselect可以单列，不能借此跳过阶段必测项。旧模式与DSH模式使用具名计划；不要求旧CLI无条件加载DSH。

### 里程碑与有限 live

Gate-R 在 R01–R04 结束，只证明持久运行合同。Gate-V 还要求 V01真实全链、A01真实覆盖回执和V02操作入口；已有Python全离线与新增Node/桥接测试均按该阶段执行。L01 的回执必须在代码、配置和产物冻结后重新生成；文档提交也可能改变engine身份。

L01 需要用户对具体 live 范围另行授权。指定8006/qwen38-27b-nvfp4、131072 context，先核health/models/队列/KV、当前身份、有限输入/输出/token/时限、停止条件和fresh输出目录。primary最多一个实际请求，无自动retry；tool-calling probe同样是live，不能偷跑作为免费前置。先用mock核wire；本机DSH未直接暴露top_p/top_k，必须确认adapter实际能力、thinking字段及差异，不能声称与Python profile自动等价。

取消先中止请求，再等可观测静止。DSH idle、本地进程退、SDK ok、signal.aborted均不证明远端未发送或已停止。无法判断就保留unknown与预留，不重发；有原响应则本地结算。live失败按分类回原owner，修订后重新准入；不改变配置反复抽样。一次小live不等于审计L1、§16.3或主图迁移。

## 实施单元

每单元由owner实施、reviewer独立复核；同一文件只能由一个活动任务写入。下列“现有”路径包含第03份已验交付；“拟新增”路径仍待本批实施。原AT与依赖不变。

### R01 · 持久task/outbox/claim与单run租约

| 项 | 约定 |
|---|---|
| owner / reviewer | RUN / QA |
| 前置 / WP | C04 / WP4a |
| 独占编辑范围 | `src/code2paper/integrations/dsh/task_store.py`（拟新增）<br>`src/code2paper/integrations/dsh/facade.py`（现有）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有）<br>`tests/integrations/dsh/test_task_recovery.py`（拟新增） |
| 步骤与交付 | 用稳定execution/workflow/node/scope/epoch key持久准备和claim，复用K02 fence；run独占/后端独占，支持claim失效和receipt重放。task_store只保存生命周期与引用，不维护可扣减余额；未有共享调度时拒绝第二DSH run。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-R01 | 两个Host抢同epoch只有一个有效claim；旧Host回包、取消后mutation、prepare后崩溃都不重复提交；重启不清零epoch，不以PID/TTL证明旧执行已静止。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_task_recovery.py` |

### R02 · 扩Python唯一账本接收DSH事实

2026-09-29 阶段交接：窗口一在第 02 份持续内核阶段持 `unified_context_models.py` 的实际
回执表示，以及 `writer_attempt_ledger.py` / `unified_invocation_ledger.py` 原恢复/发送事实/
预留 owner 的必要修复权，包含最新补证暴露的拒发分类和 unknown 根因传播问题。R02 仍 planned，
其新 DSH RPC/事件协议/adapter 不提前实现；后续继承内核阶段受测字节，不回滚或重复修复。
正式 QA 期间这些实际输入只读。完成内核/兼容阶段后才按本文件进入持久运行集成。

| 项 | 约定 |
|---|---|
| owner / reviewer | RUN / QA |
| 前置 / WP | R01 / WP4a |
| 独占编辑范围 | `src/code2paper/agentic/unified_context_models.py`（现有）<br>`src/code2paper/agentic/unified_invocation_ledger.py`（现有）<br>`src/code2paper/agentic/writer_attempt_ledger.py`（现有）<br>`src/code2paper/integrations/dsh/invocation_adapter.py`（拟新增）<br>`tests/integrations/dsh/test_invocation_events.py`（拟新增）<br>`src/code2paper/integrations/dsh/facade.py`（现有）<br>`src/code2paper/integrations/dsh/worker.py`（现有）<br>`src/code2paper/integrations/dsh/protocol.py`（现有）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 版本化reserve/adapter-attempt/dispatch/not-sent/usage/terminal/cancel/unknown；稳定事件ID幂等，语义冲突拒绝。lease内重查预算、read-set、fence与unknown后持久reserve才放行；epoch请求/input/output/读取/时限进入同一权威及reducer。 将request.reserve/dispatch/settle/mark_unknown私有方法接到真实worker/facade，R03不得用假RPC代替。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-R02 | prepare后余额被耗、零预算、账本失败都零发送；重复usage不双扣，missing usage不归零；sent_to_caller保留旧语义，不能升级为HTTP证据；响应落盘未结算只本地复验，unknown保留预留。 从真实worker RPC复核零预算/账本记录失败零发送、重复事实不双扣。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_invocation_events.py` |

### R03 · Host私有pump与worker运行接线

| 项 | 约定 |
|---|---|
| owner / reviewer | DSH / QA |
| 前置 / WP | R02 / WP4a |
| 独占编辑范围 | `integrations/dsh/src/kernel-client.ts`（拟新增）<br>`integrations/dsh/src/workflow-driver.ts`（拟新增）<br>`integrations/dsh/src/execution-policy.ts`（拟新增）<br>`integrations/dsh/src/request-accounting.ts`（现有）<br>`integrations/dsh/tests/host.test.ts`（拟新增） |
| 步骤与交付 | 真实DSH subprocess启动固定argv/env/cwd的worker；按claim→create/bind→实际请求复核/reserve→DSH→flush/record_output→ingest执行。TS仅RPC/hook adapter；native tools仅terminal，单请求，无auto retry/compact/title/repair。 |
| 验收 AT-R03 | 真实Python worker与mock模型完成时序；未绑定/过期claim/第二请求零发送；失败来源可追踪，Host不增写领域内容；正常日常入口和工作区不受改写。 在真实dispatch前核I01组成，prepared call配置/generation改变拒绝；不以初始化时曾核对替代。 |
| 待形成测试/证据 | `host.test.ts` |

### R04 · 取消、失联与跨进程恢复

| 项 | 约定 |
|---|---|
| owner / reviewer | RUN / QA |
| 前置 / WP | R03 / WP4a |
| 独占编辑范围 | `src/code2paper/integrations/dsh/task_store.py`（拟新增）<br>`src/code2paper/integrations/dsh/invocation_adapter.py`（拟新增）<br>`integrations/dsh/src/kernel-client.ts`（拟新增）<br>`integrations/dsh/src/workflow-driver.ts`（拟新增）<br>`tests/integrations/dsh/test_host_crash_recovery.py`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 注入reserve前后/dispatch后/terminal后/record_output后/commit后崩溃，统一reducer读回。取消等待DSH dispose和worker provider范围waitForExit；无法证明远端停止进入unknown，迟到响应以原epoch结算。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-R04 | 每个断点在新进程恢复；已记录响应不再调用模型；unknown禁止重发和退款；回包丢失返回同receipt；父进程退但子进程仍活动不能释放独占权。 恢复时运行字节或组成改变拒绝绑定旧task/receipt。 waitForExit使用独立有界cleanupSignal，只有返回true才确认provider范围静止；false/抛错保留阻断，不能复用已aborted的请求signal。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_host_crash_recovery.py` |

### V01 · 串行单Writer真实DSH mock纵向闭环

| 项 | 约定 |
|---|---|
| owner / reviewer | QA / LEAD |
| 前置 / WP | R04 / WP3a |
| 独占编辑范围 | `tests/integrations/dsh/test_serial_writer_e2e.py`（拟新增）<br>`integrations/dsh/tests/serial-writer.test.ts`（拟新增）<br>`integrations/dsh/tests/pi-ai-wire.test.ts`（拟新增） |
| 步骤与交付 | 用B01合法材料、真实DSH Loader/child/LLM seam/terminal/Session及真实Python builder/parser/Binder/composer/publication走一次全链。仅provider响应mock；另跑research_required、坏内容、未知发送、cap漂移。 另用实际pi-ai adapter连接隔离loopback假OpenAI/SSE服务，捕获真实wire/arguments delta/normalized结果；这仍为离线fixture，不连接8006或外部模型。 |
| 验收 AT-V01 | 合法局部receipt和immutable成员完整；拒绝用stub assessor/手写假页管线达标；零隐藏Python LLM，正式发送前硬门有效；single Writer完成不冒充主图或Verified完成。 实际adapter的模型参数、thinking字段、tokenizer/cap与renderer计量匹配；仅自建mock adapter不能代替，所需sampling字段不支持时明确阻断L01。 |
| 待形成测试/证据 | `test_serial_writer_e2e.py serial-writer.test.ts pi-ai-wire.test.ts` |

### A01 · 修复实际测试覆盖回执并接入Node

| 项 | 约定 |
|---|---|
| owner / reviewer | RUN / QA |
| 前置 / WP | V01 / WP3a |
| 独占编辑范围 | `src/code2paper/cli/agentic_run.py`（现有）<br>`src/code2paper/agentic/live_admission_preflight.py`（现有）<br>`tests/integrations/dsh/test_dsh_admission.py`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 先复现CLI只跑单pytest节点仍默认登记四组label；在原record-offline-receipt入口执行阶段要求的Python/Node命令，以真实逐suite argv/runner/退出码/报告摘要派生覆盖，移除默认填满。读取复算计划及子回执，测试前后核同一engine/validator/config/composition。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-A01 | 单pytest节点、Node未启动/失败/零测试/必测skip、伪填label、同label换命令、报告篡改、测试期间身份漂移均不可完整准入；两类真实suite通过才成阶段回执；旧模式与DSH模式要求具名分开。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_dsh_admission.py` |

### V02 · opt-in操作入口与阶段准入接线

| 项 | 约定 |
|---|---|
| owner / reviewer | DSH / QA |
| 前置 / WP | A01 / WP3a |
| 独占编辑范围 | `integrations/dsh/src/cli.ts`（拟新增）<br>`integrations/dsh/tests/cli.test.ts`（拟新增） |
| 步骤与交付 | 提供显式实验入口和显示的parallel=false；此时true返回unsupported。消费I01实际组成身份和A01原准入owner回执；登记并实际执行该入口的新增必测用例，再生成当前阶段回执。默认产品入口保持旧驱动。 |
| 验收 AT-V02 | 同命令默认串行，错误配置拒绝；伪造/过期/局部回执不能放行；原CLI默认不切换；真实操作入口走完整Host合同，historical 0918回执不能替代。 |
| 待形成测试/证据 | `cli.test.ts` |

### L01 · 单独授权的小型Qwen兼容live

| 项 | 约定 |
|---|---|
| owner / reviewer | QA / LEAD |
| 前置 / WP | V02 / WP3b |
| 独占编辑范围 | `tests/live/profiles/`（现有）<br>`integrations/dsh/dev/`（现有）<br>`/tmp/<fresh-task-run>/live-evidence/`（拟新增） |
| 步骤与交付 | 仅在另获明确live授权后，核实8006 health/models/queue/KV，固定qwen38-27b-nvfp4及实际adapter wire、tokenizer、thinking/sampling差异；匹配新离线回执，fresh输出，独占后端，一个primary请求，无自动retry。 |
| 验收 AT-L01 | 有限请求/token/时限/停止条件齐备；tool参数、usage/finish/原文来源与局部接收有证据；capability probe也计live；不兼容则停止不换模型。此次通过仍不等于审计L1或§16.3。 |
| 待形成测试/证据 | `authorized_single_writer_live_protocol` |

授权边界：该任务的模型/服务调用须单独live授权；本执行计划不是调用批准。

## 验证、交接与完成门

以下是实施后的执行命令，本轮未运行；所列旧文件已确认存在。新增任务测试落地后按上表AT逐项运行并登记实际节点/断言，不可只登记文件名。

```bash
python -m pytest -q tests/regression_20260917/test_ledger_recovery_matrix.py tests/regression_20260917/test_run_identity_content.py tests/regression_20260917/test_live_admission.py tests/test_agentic_unified_context_compiler.py
npm --prefix integrations/dsh run typecheck
npm --prefix integrations/dsh run build
npm --prefix integrations/dsh run stage
npm --prefix integrations/dsh run test:compat
git diff --check
```

Node必须显式选择已验候选并经现有隔离launcher运行，完整环境和命令见[整批指令§4](stage04_batch_execution_instructions_20261004.md#4-阶段验证命令与统一证据)。当前test:compat递归发现新增测试，test:integration尚未定义；如确需拆分，先实现其发现/机器报告再纳入A01，不因脚本缺失直接在日常profile启动。新增Python测试在tests/integrations/dsh/，Node测试在integrations/dsh/tests/；修原owner的反例也扩已有测试，不复制其实现。

交接包包含：任务ID、输入/代码/配置身份、接口及存储版本差异、改动文件、最小反例修前/修后结果、真实接线证据、准确命令/退出码/原始输出引用、未测项与恢复办法。独立reviewer依据 [verification.md](verification.md) 复核；Gate-R要求R01–R04；Gate-V另要求V01/A01/V02；Gate-L仅在L01获独立live授权并通过后记录。 各门要求对应AT及跨任务接线，不凭一个helper单测结案。

[返回总执行入口](README.md)
