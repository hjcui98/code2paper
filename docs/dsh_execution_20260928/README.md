# Code2Paper × DSH 分阶段执行计划

> **当前统一派工入口：[原长期模块 §9 Gate-L 集中解阻](stage04_06_long_module_execution_20261004.md#gate-l-unblock-20261005)。** 本批先完成非thinking完整请求/服务端兼容、packet14错误流计量与具名abort/unknown恢复包，再统一冻结验证；§9.8可直接转交。Gate-L独立PASS后连续推进M01–M03、P01–P04、G01–G08。状态仍24/1/24、费用UNKNOWN/原owner held；这是文档更新，不是新live或恢复授权。

> **packet14 最新：** 服务端grammar错误、实际usage/finish缺失、费用UNKNOWN/原owner held，Gate-L FAIL。错误流计量与首因返修进行中；[当前证据](stage04_L01_provider_error_repair_evidence_20261005.md)。下方packet13状态为历史。

> **2026-10-05 当前：** packet13 一次授权已消耗，普通文本/原生工具调用0，Gate-L FAIL；受信自然完成已登记、实际费用7699/pending0、原 owner 正常释放，canonical empty及六条严格history，独立生命周期PASS、实际读集释放。当前原生工具选择返修使用tool-choice.2开发候选；来源构建、wire对照、三项真实native及严格审计通过，统一关闭后冻结新完整/cold09。历史1803仅7f77/af9；24/1/24，M/P/G保持原阶段门。详见[原生工具选择返修证据](stage04_L01_native_tool_choice_repair_evidence_20261005.md)。

> **packet12历史执行状态：** packet12具体一次授权已消耗，UNKNOWN_TOOL领域FAIL保留。受信完成/诊断/历史退役经真实native及focused、原数据保护克隆；独立代码方案PASS/APPLIES和实际退役PASS，原费用7648/pending0、canonical empty，42非lease旧run文件及14原输入未变。读集已释放；当前关闭文档后冻结新完整/cold（05），历史1707仅9def/7b77。Gate-L FAIL、24/1/24；详见[未注册工具返修证据](stage04_L01_unknown_tool_repair_evidence_20261005.md)。


> **packet11历史恢复状态（后续packet13现状见上）：** packet11 一次生成授权已消耗，普通文本 JSON/finish stop、tool_calls0，领域失败保留。文本结束返修及具名原费用恢复经独立代码/方案、实际结果两次 PASS；原费用 spent7596/pending0，canonical backend empty，35旧文件、原task/claim/正文及provider_quiescence null保持不变。实际读集已释放；新完整注册证书及fresh cold待最终冻结运行。Gate-L仍FAIL，24/1/24；新模型请求需fresh packet具体一次授权，不重发旧packet。详见 [文本结束返修证据](stage04_L01_text_stop_repair_evidence_20261005.md)。


> **2026-10-05 现状核查：** Stage A 七项独立 Gate-R/V PASS，项目 24 done / 1 in_progress / 24 planned；长期模块 7/23 done。packet10 已消费一次具体授权，HTTP200、7463 输入/1182 输出、tokenizer 一致、费用结清；terminal 缺 schema_version 被拒，当次 Session blocked 触发旧完成凭据拒绝，原领域无回执。原 backend 的后续具名退役已完成，当前 empty。Gate-L 未通过：packet10 独立事后裁决 FAIL，读集已明确释放（/tmp/c2p-dsh-independent-packet10-postlive-20261005-01/readset-release.json）。五组代码及具体历史恢复方案已独立 PASS；原 exact owner 已按既有 normal-finish release 授权合法退役，canonical backend empty，费用不变且原领域失败保留。当前完整证书和新包具体授权仍待；证据见 [整批返修记录](stage04_L01_repair_batch_evidence_20261005.md)。Gate-L PASS 后连续推进 C–F。本指导不授权新的模型调用。
> [完整补充指令](stage04_L01_packet10_repair_and_continuation_20261005.md)；原长期模块及原 AT 不变。packet02 的旧结算/退役已完成，后续历史段落按各自日期和身份解释。

> **2026-10-04 当前独立裁决：[GC 集中返修验收](stage03_gc_repair_acceptance_20261004.md)，Gate-C PASS，GC-1/2/3 全部关闭。** 第01–03份完成，49项为 **17 done / 0 in_progress / 32 planned**；Gate-B/H/K 保持已验范围。
> 按用户随后要求，下一批扩大为[第04–06份长期模块](stage04_06_long_module_execution_20261004.md)，共23项（22离线＋1项单独准入的L01），**默认一个主执行者，按需协作**；§8可直接转交。先连续完成第04份七项离线工作，再经原Gate-R/V/L/M/P/G0/G接续到完整主流程接线，不逐helper重新派工。[第04份细则](stage04_batch_execution_instructions_20261004.md)保留，原两窗口表仅供可选拆分。23项仍planned，本轮只更新计划；QA先前已释放读集。下方带日期的“当前／下一批／待验”均保留各自历史范围。

> 2026-10-03 最新 owner：[第03份 GC-1/2/3 集中返修交付](stage03_gc_repair_delivery_20261003.md)。新包 submitted_for_independent_qa；226/265/4355、165 TS、48 B02及真实三终态99反例通过。原独立 CHANGES_REQUESTED 保留，待整包复验，六项仍 in_progress，第04份未启动。

> 2026-10-03 23:03 最新独立裁决：[第03份 r2 Gate-C 验收与集中返修指令](stage03_gate_c_review_and_batch_repair_20261003.md)。**Gate-C CHANGES_REQUESTED**：跨语言 Unicode terminal、旧材料 prepare、投影证据引用完整性三组反例已在真实入口复现。独立 105/265/123/48 原回归及技术页/作者页/新 cap 联测通过，保留其范围。
> 当前为 **11 done / 6 in_progress / 32 planned**，第03份已实施待返修；第01/02份 Gate-B/H/K 保持通过，第04份未启动。两窗口按新报告 §3–§6 一次修完整批并重新封存，QA 读集已释放。下方“ready／未实施／下一批”等旧记录按各自时点解释。

> 2026-10-03 18:03 最新：[四组返修独立验收与阶段接续](stage_four_group_repair_acceptance_20261003.md)。**Gate-B / Gate-H PASS，正式 Gate-K 已登记 PASS。**
> 四组原问题关闭；两侧原93、来源10/生命周期3、B02 48、身份24、正常smoke及默认输出路由独立通过。791份内核保持，109796项主读集及补充driver未变，18:03:42释放、相关验证PID 0。
> 第01、02份收口，49项为11 done / 0 in_progress / 38 planned。第03份具备实施前置但本轮未启动；按新报告§4整阶段推进。下方旧检查点均保持各自历史范围。

> 下一批完整派工：[第03份整批执行指令](stage03_batch_execution_instructions_20261003.md)。按 I01→C01→C00→C02→C03→C04 连续完成；包含依据、两窗口单写范围、全部正反例、四次交接、验证命令和一次封存要求。§8可直接转发。当前仅发布指令，未启动实现或改变任务状态。

> 2026-10-03 16:05 最新独立结论：[冻结整包 Gate-H 审查](stage_whole_package_review_20261003.md)。
> 两侧原套件各 93/0skip、来源边界各 10/10、生命周期各 3/3；交付 B02 26、身份 24、doctor、正常 Web/compat 通过，源码/types 同字节。
> GHS-1/GHS-2 原失败已关闭；Gate-H 仍 CHANGES_REQUESTED，余项集中为 activate 漂移重封/失败先改链接、audit 缺基树跳检、smoke staging 空值和交付/回归覆盖收口。
> 1275 输入与四 runtime/manifest/peer 未变，16:05:42 明确释放、相关验证 PID 0。窗口二按新报告 §3–§4 连续返修工具链与证据；窗口一保留 791 项未变内核，正式 K 和第 03 份继续等待。下方旧检查点保持原输入范围。

> 2026-10-03 集中修改指导：[全部剩余工作与整阶段修复指导](remaining_work_and_batch_repair_guidance_20261003.md)。
> 已核对原 8 份文档、49 项任务，集中列出当前确定缺陷、待补验证和第 03–08 份全部后续工作。
> 窗口二按指导 §3 连续完成原第 01 份整包；窗口一保留已验 K01–K04 component。任务状态与 Gate 不变。
> 本指导形成时参考的独立 Gate-H 裁决为下方 22:10 记录；现已由上方 16:05 冻结整包审查接续。指导 §1–§2 保留其核查时点，不能把旧缺陷直接视为新候选仍复现。

> 2026-10-02 22:10 当前执行入口：**§3.15** 与 [2026-10-02 模块级派发候选 Gate-H 独立审查](stage_static_entry_gate_h_review_20261002.md)，仍执行原第 01 份/接口裁决 §6。
> 两侧原套件各 89/0skip，原三类反例、Web/compat HTTP、交付 B02 24/doctor 独立通过。
> 公开 `streamWithRegistration(..., true)` 可取得受信派发并发送替换材料（四项各 1→2），
> 销毁重建后合法回落失败，候选 types 非源码 tsc 输出，源码构建侧 B02 缺 worker。**Gate-H CHANGES_REQUESTED，正式 K 等待。**
> 1134 输入/四 runtime/peer 未变，22:10:34 明确释放，相关验证进程 0。窗口二按原第 01 份整包返修，
> 窗口一保持 component，第 03–08 份继续排队。下方 §3.14 及更早“当前”均是历史候选记录。

> 2026-10-02 14:48 当前执行入口：**§3.14** 与 [2026-10-02 14:48 能力门控候选复核](stage_capability_entry_review_20261002.md)，仍执行原第 01 份/接口裁决 §6。
> 交付原 87/0skip、B02 24/doctor 独立通过；新边界探针交付 4/5、源码构建 3/5。
> 公开 resolver 转发 Proxy 能截获 capability 并预消费；源码侧 iterator 获取仍见来源，
> 当前交付身份声明仍引用旧树。四文件 touched 已修。**Gate-H CHANGES_REQUESTED，正式 K 等待。**
> 本轮 QA 1054 输入/四 runtime/peer 未变并释放；另有 owner 源码验证进程未结束，
> 窗口二先收尾该运行再续原整包；窗口一保持 component，第 03–08 份继续排队。
> 下方 §3.13 及更早“当前”均是历史候选记录；8 文档/49 任务与所有门不变。


> 2026-10-02 12:12 当前：私有消费候选已独立差分复核，见 **§3.13** 与
> [完整复核及返修接续](stage_private_consumption_review_20261002.md)。交付原套件独立 87/87、
> 显式候选 B02 24/24、doctor 通过；同步 `internal/get` 仍能预消费 entry-ack，公开 iterable
> 的 `Symbol.asyncIterator()` 获取仍见外层来源，两棵候选各有 2 个合法正例/2 个真实失败。
> 实际 manifest/生成器漏列两份 types。**Gate-H 仍 CHANGES_REQUESTED，正式 Gate-K 未过。**
> 本批 992 输入/四 runtime/peer 未变并明确释放；窗口二接回原完整返修，窗口一保持 component。
> 第 03/04 份继续按原门排队；下方更早“当前”表述均按各自候选时点解释。

> 2026-10-01 19:40当前：`loop-origin.1`已实际落地，owner84/0skip交付及原H-R4合法child/公开拒绝独立成立；普通公开流量、公共NO_ADAPTER和旧manifest入口出现真实回归，源码/types/私有consume交付未满足原裁决。**Gate-H仍CHANGES_REQUESTED**，内核component保留、正式Gate-K等待。按**§3.11**与[本批裁决](stage_loop_origin_acceptance_20261001.md)集中返修；实际读集已明确释放。以下§3.10及更早状态绑定历史候选。

> 2026-10-01当前：FAIL-CLOSED候选为owner71pass/13skip，合法child也拒绝，H-R4记风险抑制而非完整通过。LEAD已批准**新隔离runtime来源补丁候选**，按**§3.10**和[接口裁决§6](h04_loop_origin_escalation_20261001.md)连续实施；原43490765…树保留，Gate-H/K未过。§3.9及更早记录绑定历史输入。

> 2026-10-01 11:36最新：owner84项候选已核对；独立原公开stream三个对照通过，H-R3已观察变体关闭，但原公开prepareCall仍取得闭包，H-R4真实exit1。Gate-H仍CHANGES_REQUESTED，内核component PASS/正式Gate-K等待。QA已明确释放；窗口二续原第01份，窗口一只读准备已交付。当前派工见**§3.9**及[闭包候选差分裁决](stage_handle_acceptance_20261001.md)，§3.8及更早记录绑定历史候选。

> 2026-10-01最新：R2候选独立83/83、B02原目录23、受影响身份29通过；旧listener重入/延迟变体已拒绝，但公开prepareCall及排入微任务仍能先认领，Gate-H仍CHANGES_REQUESTED。内核component PASS保留，Gate-K等待。QA已结束并明确释放读集，窗口二直接续原整阶段；最快修复与第03/04份排队安排见**§3.8**及[R2验收裁决](stage_r2_acceptance_20261001.md)。8份执行文档、49任务不变。

> 2026-09-30 21:36 后最新状态与接续指令见 **§3.7** 和 [返修差分裁决](stage_repair_acceptance_20260930.md)。内核 K01–K04 component PASS，保持已验候选；DSH 74项与B02原目录23项独立通过，但公共同request引用及真实NO_ADAPTER回落仍可抢票，第01份仍 CHANGES_REQUESTED。QA已结束并释放读集，窗口二直接连续完成原阶段剩余AT。保留 **8份执行文档、49个单元，不固定窗口数量**；旧 `0.1.5-rc.3` 与日常 `0.1.7-rc.2` 保留；Gate-H/Gate-K 均未通过。

本计划实施 [总设计](../code2paper_dsh_plugin_design_20260922.md)，遵循 [仓库文档入口](../README.md) 的架构权威顺序。目标不变：**DSH执行Agent，Python内核裁决证据/状态/验收/提交，LangGraph保留默认业务流程。并发显式开关、默认关闭。** 本计划细化文件责任、依赖、接口、测试和交接；不削弱旧门，不把执行计划当进度证明。

## 1. 基线与本轮结论

| 项目 | 绑定事实 |
|---|---|
| 代码对照基线 | `0918ee76d079b9392ec03400c0c4c9fdff5bc784` |
| 本轮读取HEAD | `d48b4e4b22c94c82b45d2179ba452d72b164102d`；基线之后的提交仅文档 |
| 代码核对 | B00 核对的 802 个已跟踪 src/tests/scripts 文件与 0918 一致；B01/B02 此后新增并验收夹具、构建工具及隔离器，分别记录，不改写 B00 历史清单 |
| DSH 三种身份 | 旧对照 `.dsh-dev/runtime` 为 `0.1.5-rc.3`；用户日常安装为 `0.1.7-rc.2`；新开发候选为 `0.2.0-rc.1`，已隔离安装、基础包未验收。旧 npm 副本源码 SHA 未知；新候选官方源码 tag 指向 `4878cdabd87d4041bdaff61d04c966883b9fd07a`，安装树另验，不借源码 SHA 代替 npm 身份 |
| 历史测试 | 4014 passed / 3 deselected / exit0，12 subtests来自原日志；回执绑定0918，本轮未重跑，不可批准当前DSH live |
| 当前环境 | B02/H01/H02 的通过绑定旧 `0.1.5-rc.3`；旧 H02 冻结记录和验收日志保持原字节。新版必须重新验证隔离、Loader/preset、创建期绑定与接口；尚无新 runtime 的 Gate-B/Gate-H |
| 本轮证据 | [B00 冻结清单](source_inventory.json)、[B01 首轮交付](../../tests/integrations/dsh/fixtures/B01_evidence.md)、[B02 首轮交付](../../integrations/dsh/dev/B02_environment_isolation_evidence.md)；交付声明不替代独立验收 |

旧版实验定位了 preset API、创建期绑定、raw 参数与 flush 等边界；其中“agent/created 不 await”仅绑定旧版本，不能沿用为新版事实。新版迁移差异及来源门见第 01 份；运行组成身份与准入覆盖仍归 I01/A01。K04 的历史部分通过与补证保留；最新 K01–K04 阶段候选及独立复核安排见 §3.3，不用旧缺口状态覆盖新交付，也不据 owner 声明自动关闭缺口。

## 2. 分包与依赖

按风险先后和可验证的纵向增量拆分，先打通一个Writer。每包有单元/合同/接线/故障测试，最终质量验收另设门；不是先写完全部代码再测试。

| 部分 | 文件 | 单元 | 总设计WP |
|---|---|---|---|
| 01 | [基线、开发工具链与实际 DSH 兼容性](01_baseline_and_dsh_compatibility.md) | B00, B01, B02, H01, H02, H03, H04 | WP0/WP2 |
| 02 | [原内核的发布、注册与发送前边界](02_kernel_publication_and_request_guards.md) | K01, K02, K03, K04 | WP1a |
| 03 | [执行身份、唯一 Writer 合同与无模型往返](03_writer_contract_and_worker.md) | I01, C01, C00, C02, C03, C04 | WP1b |
| 04 | [持久运行控制、单 Writer 闭环与首次 live 门](04_serial_writer_integration.md) | R01, R02, R03, R04, V01, A01, V02, L01 | WP4a/WP3a/WP3b |
| 05 | [多步工具、压缩与显式并发](05_multistep_and_concurrency.md) | M01, M02, M03, P01, P02, P03, P04 | WP3c/WP4b |
| 06 | [默认 LangGraph 主流程与 Research 跨进程恢复](06_langgraph_workflow_migration.md) | G01, G02, G03, G04, G05, G06, G07, G08 | WP5 |
| 07 | [编辑、全文事务、方法图与交付展示](07_editor_figure_and_delivery.md) | F01, F02, F03, F04 | WP6 |
| 08 | [完整离线、真实质量与迁移评审](08_quality_and_rollout.md) | Q01, Q02, Q03, Q04, Q05 | WP7 |

集成与验收顺序固定为（两阶段的内部开发衔接见 §3.1；完成前置不变）：

```text
WP0 基线/工具链 → WP2 实际DSH mock兼容
 → WP1a 原发布/注册/发送门 → WP1b 执行身份+无模型Writer合同/往返
 → WP4a 单run持久运行 → WP3a 单Writer mock+真实离线回执
 → [单独live授权] WP3b 一次Qwen兼容
 → WP3c 多步/compaction → WP4b 共享调度/显式并发
 → WP5 严格主图/真实Research恢复/完整角色
 → WP6 编辑/全文事务/方法图/导出 → WP7 等价性/真实质量/迁移评审
```

依赖的唯一机器可读台账是 [task_board.json](task_board.json)，任务卡中的依赖须与它一致。I01是新增执行组成身份任务；A01是原准入owner的覆盖修复，均在首次live前完成。WP5先G01–G03修状态承载并验收，再G04–G08迁移执行；不因“入场门本身待修”造成循环依赖。

单Writer PoC仅接受已经冻结的局部材料；research_required只进入waiting。共享公平调度、完整Research和最终Verified不作为这个小闭环的前提，也不在其完成时宣称已经交付。live未授权时可做不依赖结果的离线研究，不能标live门已过或跳过集成依赖。

## 3. 人员职责与首次派工

owner是工程责任，不代表当前已启动对应编码Agent。执行容量是上限，不是需要占满的名额；同一工作者可按阶段转任下列职责。按独立工作与实际交付收益决定串行或并行，不因职责表列了 QA 就常驻一名等待者。生产Agent并发开关与工程团队并行工作是两回事。

| 职责 | 责任与文件域 | 本轮调查来源 |
|---|---|---|
| LEAD | 依赖、接口冻结、文件写入分配、风险/门裁决、总文档与台账；负责最终整合 | 主Agent |
| ENV | 隔离launcher、profile、独立TS/Python工具链，保障日常DSH | DSH调查组 |
| DSH | TypeScript bundle/preset/child/LLM seam/Host/展示 | dsh_compatibility_units |
| CORE | 原registry/publication/index、immutable manifest与CAS | kernel_execution_units |
| CONTRACT | 原Writer builder/parser/assessor、身份、Python facade/ingest | kernel_execution_units |
| RUN | 原invocation账本/reducer、task/claim/共享调度及准入执行owner | 内核组与DSH组共同提供输入 |
| FLOW | 实际LangGraph/Research/callback与跨进程恢复 | workflow_quality_units |
| CONTENT | Editor/Rewrite/authorship、Figure和正文版本 | 流程质量组 |
| QA | 独立反例、真实接线、故障矩阵、覆盖回执、质量/盲评 | 不由该单元实现者自批 |

以下保留首次拆分与依赖来源；当前领取和版本迁移以 §3.1 为准，不一次开全部49项：

1. LEAD先执行B00，冻结实测清单及兼容输入。该步骤现已完成并经独立QA复核，见 [B00交接记录](b00_baseline_freeze.md)。
2. 工作者A转ENV执行B02；工作者B转QA执行B01合法fixture/旧行为；工作者C独立复核两项产物及H02/H03实验设计。B01/B02文件域独立，可并行。
3. B02过门后，A转DSH执行H01→H02；H03/H04 初次拆为两个实施者。当前按 §3.1 合并到窗口二统一实施，随后 QA 复核 Gate-H。
4. 此处为初次派工历史，现由 §3.1 授权窗口一连续开发 K04→K01→K02→K03；QA 验证 g1→g2 真实 reader、零发送与恢复，Gate-K 后进入第 03 部分。

规划阶段三个协作者只读调查，主 Agent 统一撰写文档。随后 B00 经独立 QA 通过；B01/B02 补齐后均已独立验收通过，见 [阶段验收](b01_b02_acceptance.md)。H02 的实际导出、mock recorder 与资源处置责任已按 [交接要求](h02_h04_handoff.md) 复核并冻结；放行及受测身份见 [H02 最终验收](h02_acceptance.md)。后续领取必须报告任务ID、起点身份、owned files和依赖证据。

### 3.1 持续阶段任务分工（2026-09-29；窗口调度以 §3.3 为准）

**按用户要求，从零散补证/逐项等裁决，改为阶段负责到底。** 保留 8 份执行文档和 49 个任务
编号；任务卡是内部实施和验收清单，不再等同一次派工或一次暂停。以下安排替代前轮
“K01 仅只读”“K02/K03 必须等 Gate-H 才编码”“新 H02 独立 PASS 前不能实施 H03/H04”
等**开发排程**限制。原产品合同、各 AT、独立 QA、depends_on 完成前置和 Gate-H/K 不减少。

| 窗口 | 持续负责的阶段 | 主执行文件 | 交付终点 |
|---|---|---|---|
| 一 | Python 内核完整阶段：K04→K01→K02→K03，含现有账本/恢复缺陷修复 | [第 02 份](02_kernel_publication_and_request_guards.md) | 严格注册、不可变发布、真实索引读取、发送/恢复守卫全部接线及故障矩阵；可供 Gate-K 复核的完整内核包 |
| 二 | DSH 0.2 运行阶段：B02→H01→H02→H03/H04→同 child 联合接线 | [第 01 份](01_baseline_and_dsh_compatibility.md) | 同一 0.2 候选完整 check:compat 与全部 AT，通过独立 Gate-H 复核；默认入口/live 不切换 |
| QA（按需，不固定窗口） | 完整阶段包就绪后独立集中验收、差分回归；必要的提前风险审查单独按需安排 | [验证文档](verification.md) | 全 AT→真实节点/原始证据的判定，内核 component review 与 Gate-H review；反馈集中到各阶段 owner |
| LEAD | 架构、跨阶段接口/边界与最终门裁决 | 本入口、interfaces、台账 | 不写实现；不把正常缺陷修复、函数提取或测试夹具调整变成再次派工 |

**开发衔接自动进行。** 窗口一先消化本轮 K04 补证和两个已报告的账本问题，形成自己的完整
正反例基线，随后直接实施 K01→K02→K03。窗口二在 B02/H01/H02 的本地合同与聚焦测试通过后
登记版本化的 `_020` 接口候选，直接实施 H03/H04；内部 API 修改要同步消费者和身份，不冒称
接口已独立验收。前置单元实现/合同有证据即可继续开发，不必等它的任务状态变 done。
任务尚未独立通过时保持 in_progress/review，**不会因后继开工而自动 PASS**。

Python 阶段不依赖 DSH runtime 才能实现原 registry/publication/index，故 K01–K03 可在 Gate-H
前开发与 component review。Gate-K 正式通过仍要求目标 Gate-H 与全部 K01–K04 AT；完成依赖
不改。两阶段都通过后才进入第 03/04 份的 Writer 合同/worker/持久 RPC 集成，当前不一口气开全部49项。

**正常修复由阶段 owner 完成。** 范围内的发现→最小复现→修原 owner→回归→更新证据是一项
连续工作。包括不在旧卡片单个文件框内、但在本阶段明确责任域内的必要调用方/测试调整；写清
影响和原因即可，不再报“修到 owned path 边界就停止”。生产权限、未知发送、验收、来源与旧
归档门不能放松，不能建立平行账本/解析器。跨两窗口的文件或跨阶段公开合同须先协调。

**报告不等于交接。** 内部完成 B02、一个 G*、一个 helper 或一组测试时，只更新本阶段证据，
给简短进展后继续。正式交付只在：完整阶段候选可验收、QA 集中复验反馈、或出现下述真实阻断。
上下文不足先把任务阶段、起点/当前身份、已完成/剩余、命令与恢复入口写入持久记录，后续继续
同一任务；不把一次会话结束定义成阶段完成，不申请用户逐次续派。

只在这些情况升级：需改变领域权威/新持久协议或验收语义；公开 runtime 能力经合法/反例实测
仍无法满足硬合同；需要日常安装/凭据/live/发布权限；真实跨窗口写权冲突。普通编译错误、测试
失败、缺一条证据、缺目录或已报告的原 owner 缺陷，均由 owner 在阶段内继续处理。

**共享输入纪律。** 窗口一独占 Python 内核与其身份源清单，窗口二独占 launcher/TS/lock/build。
共享 `integrations/dsh/node_modules/@deepseek-ai` 单链接暂只允许窗口二切换；整个适配周期保持
明确的 0.2 构建选择，不每做一条实验退回旧 peer。旧版本以已冻结 runtime/源码/lock/bundle
保留，旧版复现需另约独占切换，不能混用新源码声称旧身份。日常 DSH 完全不参加开发。

**QA 按需启动，不逐缺口占窗。** 完整候选提交后建立或复用真实消费者、故障/恢复、跨进程和
来源探针，核对需求映射；只能对冻结输入给正式结论。确有具体风险时可提前安排一次审查，
不为维持并行而持续准备或轮询。可选基础包/接口的提前审查属于非阻塞咨询，不再成为继续
开发的额外许可点。正式阶段验收一次提交完整身份/read-set，验证期间冻结实际读集；允许未
被读集涉及的另一阶段继续。若有经过校验的隔离只读快照，可验快照，不能用移动源码配旧回执。
默认结束当前 QA 批次，再按就绪完整包排队，真正就绪的 Gate-H 优先；不让未来候选占位。

**2026-09-29 派工起点（历史；后续进度见 §3.2）。** K04 GAP-1/2/3 证据批已交付，生产代码未改，两个原 owner
问题（拒发原因分类丢失、unknown-send 被下游预算错误盖住）已报告待修。窗口一接回处理并
向 K01–K03 连续推进；窗口三纳入最终内核回归。DSH 候选已 provision、工具链候选验证 owner
报告通过；只读隔离/日常保护/H01/H02/联合门仍未完成。两阶段都未获 PASS，不通过测试总数
或阶段派工宣告已接入、已 Verified、已 live 或已切默认。

### 3.2 完整内核候选已提交，DSH 阶段继续（2026-09-30）

以下是本日第一次交接快照；其后 QA 报告的 LEAD 裁决与当前写权接续见 §3.3。

| 窗口 | 当前状态与连续责任 | 本次安排 |
|---|---|---|
| 一 | K01–K04 owner 实现交付、写权已释放，任务转 review；尚无 component PASS | 保护已交付输入，配合窗口三一次集中复核；收到集中问题并完成读集交接后，在原阶段内自主修复、提交差分，无需重新派工。未放行第 03/04 份实现 |
| 二 | 0.2 typecheck/build/stage/config owner 报告通过，Loader 1/10；其余运行语义待验 | 按第 01 份完成 preset 声明及 H01/H02，再连续完成 H03/H04、组成隔离与同 child 联合恢复。保留唯一 TS/peer/build 写权，不等内核 QA |
| 三 | 接收完整 Python 内核阶段候选；DSH 尚未提交完整候选 | 立即按 verification 的本批说明核对冻结输入并集中复核 K01–K04；DSH 只做独立准备，不为未就绪的 Gate-H 占位、不中断已经开始的内核批次 |

交付入口：[内核阶段证据](kernel_stage_evidence.md)（本次只读摘要 `76ae499b…`）与
[DSH 恢复检查点](../../integrations/dsh/dev/migration_0.2.0-rc.1_gaps.md)（`ae42e28c…`）。
LEAD 已静态核对内核证据表 12 个文件、最终 S7 的 12 个文件均与当前字节一致，S1–S5
日志摘要/退出码与 27/15/8/24/89 的记录一致；没有重跑实现测试。4114 项全量结果仍按
owner 报告记录，完整运行身份与 skip 范围由 QA 核对，不成为本次独立通过证据。

接收候选不表示全部证明已齐。真实多进程 CAS、旧格式真实字节、故障注入到新进程 reader
及完整 AT 映射在同一次内核复核中处理；详见 [本批验收要求](verification.md)。已有原 AT
仍是判据，未测与实测失败分开登记；不得用顺序调用冒充并发或用计数抵销缺口。
本阶段 component review 可以先完成，正式 Gate-K 仍等目标 Gate-H。另一窗口只有在实际
进入 QA 读集的共享输入上才需短暂冻结，不将整个 DSH 开发停下。

### 3.3 报告校正、连续返修与按需调度（2026-09-30；调度原则继续有效，当前状态见 §3.6）

**完整内核包 CHANGES_REQUESTED。** 旧窗口三的四项 PASS 未覆盖本批 §6 明确要求的冲突
发送事实、真实 1.0 档案、多进程 CAS/真实退出恢复与三方 active 分歧，因此不登记完整
component PASS。已实测局部行为按身份保留，详细依据见 [verification §7](verification.md)。
`6046464f…`/`c8412d00…`/`19ec39c5…` 已声明，撤销 QA 对它们的“未声明批后变化”条件。

**不再固定三个窗口。** 窗口编号只用于识别已有负责人，不要求三个会话同时工作。
目前保留两条实施线，是因为原 Python 内核返修与隔离 DSH/TS 适配各有可独立完成的工作，
且中途合并会丢失已掌握的上下文；这不构成后续继续双线的要求。

| 负责人/活动 | 整阶段接续任务 | 写权/交付边界 |
|---|---|---|
| 一（保留） | 按第 02 份 §4.2 连续完成可靠证据、冲突账本、真实 legacy、持久故障/竞争及索引权威的返修 | 本批 QA 读集已明确释放并核对，直接施工，不逐项等待；一次新候选和差分回归交付。C/R/F 后续实现仍未启动 |
| 二（保留） | H01/H02、S2 合法正例和 cancellation 已获 owner 聚焦通过，继续 V4、完整来源/取消合同、组成保护及同 child 联合恢复 | 唯一 TS/peer/build 写者，只 stage 当前 0.2；不为 QA 无显式候选的旧入口报错重封两侧环境 |
| 旧 QA（本批已收尾） | 原始证据与 closing 保留，本批 Python 读集释放已登记 | closing 摘要、八项输入身份及相关宿主进程已核对，见 §3.4；该批结束，不占位等待 DSH |
| 独立 QA（候选就绪后启动） | 继承旧证据，纠正覆盖矩阵，对冻结整包集中复验 | 不常驻第三窗口。验收替换受测阶段的实施活动；结束即释放读集，由原实施者继续返修 |

独立 QA 指审查人与被审实现者分开，不要求长期保留第三个会话。没有候选时不启动等待中的
QA；一个实施阶段完成后也不为占满窗口提前领取尚未放行的第 03/04 份。共享身份/构建或
正式验收确实读取双方输入时，安排一次明确的串行验证窗口；不删读集、不反复抢写。若
持续存在依赖或等待、并行无净收益，改由一个实施者推进当前任务，另一方保存检查点退出；
需要择先时优先完成 0.2 运行兼容，再接续内核剩余项。各 AT 与 Gate-H/K 不因人数减少而减项。

这是原阶段的集中返修，不再拆单点任务。旧 QA 的 blocked 是该会话状态，不能
登记成本计划整体 blocked，更不能让窗口一为等待窗口二而继续冻结。未交付阶段不轮询
staging/台账凑运行轮次；可做有用独立准备，无可做工作就保存检查点，收到候选再恢复。
此前 600 秒 mock cancellation 无结论须按挂起/超时定位，不能仅增加运行时间；owner 后续修复与结果见 §3.4。

LEAD 本轮只核对报告、声明及代码/测试结构并更新计划，没有执行复现/修复或产品套件。
4114 全量结果因 owner 确认无完整落盘日志，不再作为可审计全量通过；最终返修须保存一份
完整日志和 skip 原因。现存 S1–S5 聚焦日志不因此作废，历史报告及源码候选也不被覆盖。

### 3.4 LEAD 接管、读集释放与当次检查点（2026-09-30 13:20，历史）

**窗口一的写入交接阻塞已解除。** 旧 QA 的
`/tmp/c2p-dsh-h-qa-w3-20260928/reports/QA_W3_closing_20260930.md`
（`80b1a4af…`）§§2–4 明确无存活验证/待写缓冲区、释放本批 Python 读集并结束。
LEAD 复算其八项 closing 身份均匹配；13:20 的宿主只读检查覆盖本用户 122 个进程，
无相关 QA/项目验证匹配、无不可读项。完整摘要与保存位置见 [verification §8](verification.md)。
closing 中仍残留的“账本身份未声明”及旧 runner 建议沿 §3.3/verification §7 更正，
不重开争议、不覆盖原报告，也不撤销其明确释放声明。

**DSH 最新为恢复检查点 3。** [迁移记录](../../integrations/dsh/dev/migration_0.2.0-rc.1_gaps.md)
本次读取摘要 `a528487e…`；owner 报告 H01 10/10、H02 11/11、provenance 13/13、
request-seam 6/6、cancellation 6/6（1.70s），terminal 0/8；typecheck/build/stage/config
报告 exit 0。S2 首个失败为准备接受前的 `contract-unsupported`，补入 model-facing
`toolHistory` 的封闭摘要覆盖后合法正例与 cancellation 转绿。LEAD 静态确认该字段进入
`request-accounting.ts` 的覆盖清单，没有重跑产品套件；这些结果均为 owner 证据。

窗口一从第 02 份 §4.2 连续完成整阶段返修；窗口二继续 H03 V4、H04 的两个 child/等待期
冒用（含公开可取得的同 signal）/prepared-direct-回落及清理合同、组成保护，再交同 child
的 accounting→terminal→持久化→新进程恢复联合证明。旧 S2 合法正例通过不关闭完整来源
合同，分套件通过不替代联合证明。一次完整同候选验证后交冻结身份包，届时启动独立 QA。

本次只登记负责人交接、持续授权与检查点；尚未取得两个原实施窗口的接续回执或新完整候选。
K01–K04 仍为 in_progress/CHANGES_REQUESTED，B02/H01–H04 仍为 in_progress；
Gate-H/Gate-K 未通过，第 03/04 份及 live 未启动。原依赖、49 个 AT 与产品权威边界不变。

随后用户转回窗口二检查点 3 和窗口一的只读阻塞报告；后者引用的是释放前的旧台账。
窗口一现在直接使用 [verification §8.1](verification.md) 与台账内 33 条确切释放路径接续，
无需取得其他窗口私有 `/tmp` 的访问权。持续完成第 02 份 §4.2，不再交五个单点任务；
窗口二持续完成 V4→完整 H04 AT 映射/缺项→组成保护→同 child 联合恢复→冻结交付。
46/54 只描述现有六套件的 owner 结果；H03 是这些套件的剩余失败，整阶段未开始项仍须完成。

### 3.5 两名新实施者分别接手窗口一、二的完整指令（2026-09-30 17:07，交接历史；最新接续见 §3.7）

本节保留当次交接的代码/进度快照。分支、环境和原责任范围继续适用；其中尚缺 worker、
未迁移 V4、未交候选及启动回执等状态已被 §3.6 的实际交付/验收更新，不再据此派工。

用户已明确：**两名新实施者分别接手窗口一和窗口二，当前 LEAD 不变。** 本节沿用原两
阶段责任域，不增加执行阶段或另一套协作体系。窗口一新实施者负责原 Python 内核返修；
窗口二新实施者负责完整 DSH 0.2 阶段并独占 TS/peer/build/stage。两者可在各自授权范围
修改代码、测试和本阶段证据，不能改 LEAD 台账/裁决或自登 PASS/done，也不同时获得另一
线写权。原实施者应停止对应责任域写入并交当前未提交字节、运行进程和回执；目前没有
收到旧写者停止或新实施者启动的接续回执，不把本次安排记成已开工。

LEAD 继续负责设计、派工、接口/范围、文档台账和最终裁决，不自行修改产品代码。不为
保持窗口数提前启动第 03/04 份或常驻 QA；失去并行收益时按既有策略串行，优先0.2 runtime。

**仓库与版本。** 仓库为 `/home/cuihengjia/agent/Code2Paper copy`；实际分支
`codex/agentic-p4-benchmark-cutover`，HEAD `d48b4e4b22c94c82b45d2179ba452d72b164102d`。
本地 tracking 信息为 ahead 92 / behind 1，没有 fetch 验证远端。本阶段保留当前 dirty tree
及 `paperbanana_single_shot` 脏子模块、`docs/1.txt` 和原运行目录，不 pull/reset/clean、
切分支、提交、合并或推送。`0918ee7` 是接入前历史代码对照，不是当前实施树。

新目标为 `.dsh-dev/candidates/0.2.0-rc.1/`；安装包 `@deepseek-ai/dsh@0.2.0-rc.1`，
manifest 的 runtime 摘要为 `43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c`。
本次读取包/manifest/peer，未重算整棵 runtime 或重跑产品测试。当前
`integrations/dsh/node_modules/@deepseek-ai` 指向该候选的 runtime peers。
旧 `.dsh-dev/runtime` 为 0.1.5-rc.3，历史摘要 `7e8f199b…`；日常 DSH 按用户交接为
0.1.7-rc.2，二者受保护，不用新版源码重封旧 stage，也不切回旧 peer 后假称新版验证。

现有工具为 `/home/cuihengjia/miniconda3/bin/python`（3.13.9）、同目录的 Node v25.8.2 /
npm 11.11.1，`/usr/bin/bwrap`；TypeScript 5.9.3 / @types/node 25.9.3 由 package-lock
固定。旧 `.dsh-dev/pyworker` 存在，**新候选的 `pyworker` 当前不存在**，须由 B02 owner
在目标根补齐并验证，不能把旧 worker 通过视为目标交付。不得修改全局环境、日常 profile
或继承凭据；mock 经 launcher 的离线网络空间运行，本阶段无 live 授权。

**阅读顺序。** 先 [仓库文档入口](../README.md)，再 [DSH 总设计](../code2paper_dsh_plugin_design_20260922.md)，
本文件 §§3.3–3.5、[台账](task_board.json)、[共享接口](interfaces.md)、
[第 01 份](01_baseline_and_dsh_compatibility.md)、[第 02 份 §4.2](02_kernel_publication_and_request_guards.md)、
[verification §§7–8.1](verification.md)，最后读 [迁移记录末尾检查点 3](../../integrations/dsh/dev/migration_0.2.0-rc.1_gaps.md)
和 [内核证据](kernel_stage_evidence.md)。dev README 的开头仍描述 0.1.5 历史环境；其中
“H02 尚未实施”、旧扫描 preset、无候选的命令不得覆盖当前执行入口与实际代码。

**当前进度。** B00/B01 历史 done；B02/H01–H04 新版 in_progress；K01–K04 为
in_progress / CHANGES_REQUESTED；Gate-H/K 未过。检查点 3 的 owner 六套件结果是
loader 10/10、binding 11/11、request-seam 6/6、cancellation 6/6（1.70s）、provenance
13/13、terminal 0/8。46/54 不是完整 AT 或产品接入结论。本次没有重跑这些结果。
`toolHistory` 已进入封闭摘要、合法 S2 与原取消挂起已修；不要重新定位相同首因。
`terminal-result.ts` 已有 terminal tool、来源捕获、摘要、flush/新进程恢复测试；返修旧
`loggedCalls()` 的成功对应，不重写这套能力。Python 也已有请求复核、原 reducer、严格
注册、不可变 publication/CAS 与真实 index reader；继续修原 owner，不从零复制实现。

**给窗口一的新实施者。** 你接手第02份原 K04→K01→K02→K03 的完整返修，拥有该责任域
代码/测试/证据写权。与窗口二共用上述 dirty worktree，保留所有既有实现；不碰 TS、peer、
构建、staging、DSH runtime 或 LEAD 台账。先读仓库入口、本文件 §§3.3–3.5、台账、
第02份 §4.2、verification §§7–8.1、kernel_stage_evidence，核对真实代码与旧 owner 交接。
读集已明确释放，权威记录是 [verification §§8–8.1](verification.md)
与 `shared_workspace_handoff.read_set_release_record`（33 条路径）；无需跨窗口私有 `/tmp`
可见性，也无需再申请开工。连续完成第 02 份 §4.2 的证据/真实退出码、冲突发送事实、
冻结 0918ee7 owner 生成真实 1.0、真实持久写点/多进程 barrier CAS/子进程退出/新 reader、
发布 active/注册表 active/索引三方分歧及投影修复。当前 legacy 测试仍给新指针换版本，
“并发”测试仍顺序切两次，crash 测试仍本进程抛异常；这些局部绿不能折抵所缺行为。
保存原首次失败与有效聚焦证据，最终候选保存一次完整 `python -m pytest -q -rs` 日志和
退出码；旧 4114 数字缺完整日志，不采为全量证据。`w1-kernel-rework` 根尚未创建只是
当前观测，不是重新等待的门。阶段内持续返修，不逐缺陷汇报或派工。不等 Gate-H 才
返修或提交内核 component 候选；正式 Gate-K 仍受原集成前置与独立验收约束。

在仓库根使用 `/home/cuihengjia/miniconda3/bin/python`，先核分支/HEAD/dirty和自己的
责任路径，建立新鲜 `.dsh-dev/run/w1-kernel-rework/` 子根。聚焦 pytest 随受影响 owner
推进；稳定候选全量 `python -m pytest -q -rs` 只需留一份完整可审计日志，不因每个缺陷
重跑全套。统一交覆盖矩阵、完整输入身份、差分、命令/退出码/首次失败/skip原因和本批
写权释放；只在完整包完成或需 LEAD 裁决的实质接口/范围冲突时汇报。

**给窗口二的新实施者。** 你接手第01份 B02/H01–H04 的完整0.2阶段，独占上述TS/peer/
工具链/build/stage及目标环境写权。与窗口一共用dirty树，不覆盖其Python实现/测试或
改LEAD台账。先读仓库入口、总设计、本文件 §§3.3–3.5、台账/共享接口、第01份和
verification，再读迁移记录末尾检查点3；先保留并核对46/54已有证据、未提交源码、
manifest/peer/build/staging身份和旧owner运行状态。已有toolHistory、声明preset、来源
捕获和direct/prepared gate继续复用，不重做首因或重封历史环境。完整责任包内依次完成：

1. 补齐 **B02 候选传递**：`toolchain.mjs` 的 `devRoot` 读取目标 env，但
   `launcherEnvironment()` 不保留候选变量，`stage/test` 的 Python argv 也无 `--candidate`；
   Python 默认只读取 `C2P_DSH_CANDIDATE`，因而当前 npm 完整链会选择旧默认环境。
   这是静态确认的接线缺口，未运行以尝试写旧 stage，也未断言旧环境已被改写。
   在原 driver/launcher 修复、拒绝选择不一致，证明 check 的每个子节点实际落在 0.2。
   同时补目标 worker、组成/隔离和日常保护口径，不重装已存在 runtime，不运行默认 setup。
2. 修 **H03 V4**：`terminal-result.ts:732` 仍找旧嵌套 `message.content[0].toolCallId`；
   按版本及 callId/turn/step/isError 对应独立 tool 消息，严格完整性和损坏原因保持。
   原成功测试已有 flush、落盘字节和真实新进程 consumer，直接适配并保留各来源。
   `TOOL_NOT_STARTED`/`TOOL_OUTCOME_UNKNOWN` 不变成成功、usage、退款或重发授权。
3. 完成 **H04 原 AT 的真实缺项**：S1 已证明多 child 存活与全局扇出，不重造该实验；
   S2 的冒用发生在合法请求结束后且不带 signal，复制/重放用另一个授权对象，仍缺
   两个 child 实际计量交错、准备/reserve/dispatch 等待期复制完整材料及公开同 signal。
   现代码在第二次 receipt 等待后缺最后 abort/binding/fence/摘要复核，settled 把缺 usage
   补 0，`inner.return()` 没有显式截止；授权消费只以 provider+digest 排队。
   由 owner 在原位置修复/验证这些原合同，完整覆盖 prepared/direct/回落、失效清理与
   recorder/next/iterator/throw/break/abort/return；有界等待不得报底层静止。
4. 重验新组成的 provider/title/retry/compaction/PTC/OTel/desktop/可选 Schedule、
   mock 白名单和断网，并按旧 AT 语义重验 H01/H02 的生命周期与 awaited 串行绑定。
5. 在**同一个真实绑定 child**联证 accounting→adapter→terminal→settle→flush→
   新进程恢复，覆盖恢复错误、裸请求来源污染与合法对照；六套件分别通过不替代此项。
6. 完成全 AT、同候选完整 check:compat，交
   `integrations/dsh/compatibility.0.2.0-rc.1.json` 与
   `docs/dsh_execution_20260928/h02_interface_freeze_020.md`（本次均不存在）、完整身份/日志/
   AT→节点覆盖矩阵与写权释放。完整冻结候选才交独立 QA，由 LEAD 裁决；不自登 PASS/done。

**实施命令入口（只有窗口二/明确替代的 DSH owner 执行构建与 stage）。** 仓库已有
runtime/工具链，不把 install/setup/provision 当每轮前置。源码变化后 typecheck→build→
显式目标 stage→目标 Node 测试，测试不会自动重封。失败保留真实退出码并处理首因。

```bash
cd '/home/cuihengjia/agent/Code2Paper copy'
C2P_NEXT_CAND="$PWD/.dsh-dev/candidates/0.2.0-rc.1"
export C2P_DSH_DEV_ROOT="$C2P_NEXT_CAND"
export C2P_DSH_CANDIDATE='0.2.0-rc.1'

# 只读身份入口，不替代完整环境验收。
git branch --show-current
git rev-parse HEAD
git status --short --branch
python scripts/dsh_dev.py --candidate 0.2.0-rc.1 candidate
npm --prefix integrations/dsh run toolchain:verify

# 原 driver 的子命令候选传递修好前，以显式 launcher 保持目标选择。
npm --prefix integrations/dsh run typecheck
npm --prefix integrations/dsh run build
python scripts/dsh_dev.py --candidate 0.2.0-rc.1 stage
python scripts/dsh_dev.py --candidate 0.2.0-rc.1 test -- \
  "$PWD/integrations/dsh/tests/terminal.test.ts"

# 目标 worker 缺失时由 owner 创建；按现有 lock，不生成新 lock，不复制旧 worker。
python scripts/dsh_dev.py --candidate 0.2.0-rc.1 pyworker-setup

# 仅在子节点候选传递修复、AT 与联合证据齐备后跑最终完整链。
npm --prefix integrations/dsh run check:compat
python scripts/dsh_dev.py --candidate 0.2.0-rc.1 doctor --evidence
```

上述是入口清单，不是现在依次批量重跑的脚本；每次执行先选该步骤并在 fresh run root
保存 argv、日志及真实退出码，不用尾部 echo 判定、不静默忽略失败。check:compat 发现并
执行全部工具链与业务 Node 测试，六业务套件 54 项不是其完整发现总数。正式测试为离线
launcher 内 `node --test`；隔离失败不得裸跑或补装 vitest。原候选树/锁/源码/配置/组成/
validator/build/outputs/staging/接口/实际读集统一身份后停止写入，独立 QA 一次集中反馈。

两名新实施者的第一轮各自核对上述入口、原 owner 是否仍有写者/运行任务、释放记录和
实际代码起点，登记简短接管身份后持续完成各自**完整阶段**；不为单项绿或旧超时停工。
新实施者身份和实际启动/停止状态待接续回执，不借QA释放推定原实现进程已经结束。
保留 Python 唯一事实
权威、默认 LangGraph、Candidate/Verified 与独立 verifier/反向验证门、显式并发默认关闭。
两个阶段全部原验收满足后再放行第 03/04 份；单 Writer 串行真实 DSH mock 闭环是后续
首次产品目标，全文主图、真实质量、live 和默认切换没有提前授权。

### 3.6 两份完整候选已验收，集中返修与写权接续（2026-09-30 19:01 后，历史；接续见§3.7）

**两包 CHANGES_REQUESTED，Gate-H/K 未过。** 详细原始输出、身份、逐 AT 与裁决见
[本批验收裁决](stage_acceptance_20260930.md) 和 [DSH 独立报告](gate_h_independent_review_20260930.md)。
新版完整 check:compat、目标 worker、V4 正向成功与同 child 联合新进程恢复已经交付；
不得再派“修 terminal 0/8”“补候选子节点/缺失 worker”的旧任务。独立复跑 Node 71 pass、
内核聚焦 99 pass；owner 全量 4125/3 skips 的完整日志/退出码已核对。计数不抵销反例。

仓库仍是 `/home/cuihengjia/agent/Code2Paper copy`，分支
`codex/agentic-p4-benchmark-cutover`，HEAD `d48b4e4b22c94c82b45d2179ba452d72b164102d`，
保留 dirty 树。Python 3.13.9、Node v25.8.2/npm 11.11.1 和现有锁/工具链继续复用；
目标 `.dsh-dev/candidates/0.2.0-rc.1/` runtime 实算仍 `43490765…`，peer 指该候选，
目标 pyworker 已存在且 import 成功。旧默认 `0.1.5-rc.3 / 7e8f199b…` 与日常 0.1.7
保持；不重新安装或用新版源码重封旧环境，不 reset/clean/切分支/提交/合并/推送。

**给窗口一。** 先重读仓库入口、台账、第02份 §4.2–§4.3、verification §9、内核证据
§9 和本批裁决。你继续持有原 K04→K01→K02→K03 的完整责任域写权，保留所有既有实现：

1. 在原账本 owner 修复同 validator 验收重放覆盖矛盾发送事实，以及 corrupt 时 accepted
   标志/真实消费者的不一致；逐 attempt、invocation、resume/缓存与相位边界联合验证，
   保留正常 accepted/未发/unknown/预算耗尽对照。
2. 在原 publication/index reader 闭合“验证后重读 manifest”的字节一致性，不能消费 g2
   成员却标 g1 已验证摘要；保持发布权威、投影修复和新进程恢复的已通过行为。
3. 完成受影响原 AT、真实调用方与 validator 身份回归。真实 1.0、多进程 CAS、真实退出
   恢复、三方 active 与投影的本批有效证据直接继承，因实际变更受影响才复跑。

在既有 `.dsh-dev/run/w1-kernel-rework/` 下用新鲜子根，保留本轮实际失败。聚焦随修复
推进；最终稳定源码再保存一份完整 `python -m pytest -q -rs` 的 argv/日志/退出码/skip。
提交完整差分、统一身份、AT→节点、未测清单与写权释放。不要逐缺陷停下，不等 Gate-H，
不碰 TS/peer/build/stage、LEAD 台账或第03/04份。

**给窗口二。** 先重读仓库入口、台账/接口、第01份最新验收段、verification §9、
`w2_delivery` 和本批独立报告；你继续独占原 B02/H01–H04、TS/peer/工具链/build/stage/
目标候选根的写权，沿完整阶段一次集中返修：

1. H03 严格验证 tool/call、V4 成功消息/错误结构，损坏时具名 unresolved，不抛异常或
   将非布尔 isError/null content 当成功；保留合法 V3/V4、来源与真实新进程联合。
2. H04 修公开 withInitiator/signal 在合法 prepare 等待期抢票；修全局 requestDepth
   误拒合法兄弟；补同步 return 抛错的具名 cleanup/结算终态。准备/reserve/dispatch
   全部等待期都要有攻击拒绝与合法 A/B 恰计一次对照；不假定公开 setter 是秘密。
3. B02 修真实 CLI 默认 cwd 仍选旧 workspace，修两项候选 Python 隔离夹具/API 适配，
   定位普通 Web 未就绪首点，补原日常保护/无共享 inode 可证明范围及完整 active scoped
   组成/禁用行为。保留首次失败，不扩大 timeout 碰运气，不删测试或借旧快照过门。
4. 受影响 H01/H02 生命周期复验，同一真实 child 联合 terminal/accounting/settle/flush/
   新进程恢复；最终同目标完整 check:compat 与 B02 Python 原矩阵全部通过，更新 `_020`/
   兼容清单/全输入覆盖交付。不以 71/71 或任何新总数单独申报 Gate-H。

显式目标 `C2P_DSH_DEV_ROOT` 与 `C2P_DSH_CANDIDATE=0.2.0-rc.1` 始终一致；正式 Node
仍是隔离 launcher 的 node --test。现有 target worker 不需再次 setup。若公开 API 确实
无法闭合硬门，按第01份的实质升级条件交完整事实和最小接口差异，由 LEAD 裁决；
不能自行放松来源、改 frozen runtime/private helper 或把 TS 做成持久余额权威。

**本批 QA 已停止、明确释放实际读集。** DSH release=19:01:54+08，kernel 验证均已返回；
宿主 closing 精确匹配进程 0、无待写输出。仓库可见 closing/身份/日志位于
`.dsh-dev/run/qa-stage-review-20260930-izdz_5y3/`，见 verification §9 与台账新 release。
两个 profile 的 CLI mtime 副作用已如实单列，不恢复掩盖，不宣称 metadata 完全不变。
两位原阶段负责人可直接连续返修；普通问题不重新申请开工。完整新候选交付再按需 QA，
本轮不保留常驻审查、不启动第03/04份。共享输入短暂交叉或并行无净收益时按 §3.3 串行。

### 3.7 返修差分已验收，内核保持候选、DSH连续收口（2026-09-30 21:36 后，历史；接续见§3.8）

完整身份、原AT矩阵、行为、退出码与两个窗口可直接使用的接手指令见
[返修差分裁决 §§1–6](stage_repair_acceptance_20260930.md)；
[DSH独立报告](gate_h_repair_independent_review_20260930.md) §5逐项列已测、失败与未测范围。
K-1/K-2已实际闭合，K01–K04 component PASS；H03/H04和Gate-H前置未满足，
K01–K04不登记正式done，Gate-K未通过。第01份仍CHANGES_REQUESTED，不以74项绿过门。

双方继续在 `/home/cuihengjia/agent/Code2Paper copy`、
`codex/agentic-p4-benchmark-cutover` / `d48b4e4b22c94c82b45d2179ba452d72b164102d`
的未提交树工作。Python3.13.9、Node25.8.2/npm11.11.1、原锁/工具链/targetworker复用。
0.2树仍43490765…、peer未变；旧默认0.1.5/7e8f199b…与日常0.1.7保留。
先读仓库入口、当前台账/接口、本节、第01/02份最新节和verification §10；
无reset/clean/切分支/commit/merge/push、live、日常更新、旧环境重封或默认切换授权。

**窗口一：**核对内核证据§10、本批103/282独立原集合、4129完整静态日志与统一身份，
保持已验第02份候选冻结。当前没有新的内核返修项，不重做K-1/K-2或重复整套。
可只读准备第03份消费接口/依赖清单，尚不实施C/R新单元。实际共享输入变化或实质合同冲突
才报LEAD，由原owner作受影响修复/复验；Gate-H后再核对正式前置放行原下一阶段。

**窗口二：**直接接回原B02/H01–H04、TS/peer/工具链/build/stage/0.2候选根唯一写权。
保留原F1/F3/F4同步/F5、准备等待旧F2及74/23/真实CLI有效证据，连续完成一包：

1. 修公共同request引用重入抢prepared票、真实NO_ADAPTER回落同signal抢票；真实loop
   的单次能力不经公开对象/signal/setter重新取得，合法A/B独立成功恰计一次。
2. 真prepared第二派发/config漂移，两回执各自abort/fence/完整assembly与无法建立cap；
   实际async-return/timeout/iteration/break/throw/abort/next清理，结算一次、unknown不退款。
3. H03支持消息合同严格读取及flush失败/等待/缺字节恢复；同child等待期来源攻击、
   terminal/settle/flush/新reader联合。现有postcommit裸调用只证明其原范围。
4. scoped组成/禁止路径、完整_020真实导出/活跃binding示例与资源责任，纠正旧
   currentInitiator授权表述；具体原AT及额外损坏观察见本批裁决§4和独立报告§5。
5. 稳定完整候选再跑目标check:compat、原B02 dev目录与doctor--evidence，交准确
   argv/log/exit、首次失败、AT→实际节点/状态、差分/冻结身份/接口、未测项及写权释放。

显式 `C2P_DSH_DEV_ROOT=<仓库>/.dsh-dev/candidates/0.2.0-rc.1` 与
`C2P_DSH_CANDIDATE=0.2.0-rc.1` 一致；Pythonstage/test带--candidate，Node仍隔离node--test。
只重封0.2，不改Python核心/validator或LEAD台账。公开API确不能表达硬门时交公共调用事实
和最小接口差异给LEAD，不自行改frozen runtime/私有factory/验收门；普通问题自主连续修复。

DSH release=21:30:09+08，LEAD release=21:36:51+08；901输入/35owner日志及DSH2618输入/
runtime26149项前后相同，宿主精确QA/CLI匹配0、不可读0、全部命令返回、无pending。
证据 `.dsh-dev/run/qa-stage-repair-review-20260930-y7m330na/`，旧closing/history保留。
QA结束，完整新候选再按需差分验收；当前有效实施线为窗口二，不为维持窗口数扩范围。

### 3.8 R2实际验收、来源收口与后续完整阶段（2026-10-01，历史；接续见§3.9）

详细复现、身份、真实退出码、closing与可直接发给两个窗口的指令见[R2裁决](stage_r2_acceptance_20261001.md)。
独立原83项、B02目录23项、受影响identity29项通过；内核源码/测试/日志不变，不重复全量。
原H-R1/H-R2的listener及销毁后变体已闭合，但公开prepareCall能取得prepared闭包，
已排入回调能先消费fallback-ready：裸R/D/S/adapter一次，合法child失败。Gate-H/K未过。

窗口二接回原第01份全部写权，一次关闭两处首次认领；先以真实公共API证明loop来源能力，
再修原owner。不可表达时给LEAD真实调用链和最小接口差异，不再猜队列时序或以公开材料当授权。
修后聚焦原反例/正例，再完整目标check:compat、B02、doctor与身份/写权释放，集中差分验收。
窗口一保持已验内核，只读准备第03份真实消费/抽取清单，不新实现、不重跑4129。

Gate-H与正式Gate-K满足后启用原第03份完整阶段：窗口一I01/C01/C02–C04及共享Python/validator
单写；窗口二C00 renderer/TS wire及唯一build/stage，协议字段交窗口一合入。内部本地合同
连续衔接，整包验Gate-C。之后原第04份持久运行和串行mock连续推进，正式Gate-R/V不减少。
此安排当前仅排队，不提前授权C/R实现、live或默认切换。

QA于2026-10-01T00:54:43.353019+08:00释放903/27、2678与runtime26149实际读集，前后全同，宿主匹配进程0、不可读0、无pending。
证据 `.dsh-dev/run/qa-r2-acceptance-20261001-d4gkwv4k/`。QA结束不常驻，窗口二直接继续原阶段。

### 3.9 返回闭包候选实测与下一阶段入口（2026-10-01 11:36，历史；接续见§3.10）

当前状态以[本批差分裁决](stage_handle_acceptance_20261001.md)、台账和verification§12为准。
owner完整84/23/doctor记录已核对，本批未独立重跑；独立原公开stream三个对照exit0，
原公开prepareCall负例仍exit1：公开第1回调取得owned闭包，裸材料R/D/S各1、合法child error。
H-R3已观察stream变体关闭，H-R4及原AT/身份交付待收口，Gate-H未过；正式Gate-K仍等待。

窗口二继续原第01份完整写权，修普通prepared及NO_ADAPTER handle的获取来源。不可达性文字
不足，不能再用首次调用/时序/公开材料当来源；公共能力确不能表达时一次交真实调用链与最小
接口差异给LEAD。保留有效AT，同步_020旧身份表，稳定后一次完整验证/冻结，不逐项派工。
窗口一保留已验内核；第03份复用调查已交付，不重复调查/全量，不提前改Python/validator/C/R。

门满足后按原第03份I01→C01→C00→C02→C03→C04，窗口一Python/共享协议/validator，
窗口二C00 renderer/TS wire/唯一buildstage，内部连续衔接、整包Gate-C。之后原第04份离线R/V链；
live/默认切换另行。当前仍只排队，49原任务/依赖/AT不变。

本批2026-10-01T11:36:17.003480+08:00明确释放2692实际输入、34份owner文件及runtime26149项，
前后身份不变，宿主验证进程0/不可读0，全部命令返回。证据
`.dsh-dev/run/qa-handle-acceptance-20261001-wrkclu0q/`，QA结束，窗口二直接续原阶段。

### 3.10 FAIL-CLOSED检查点与runtime来源接口裁决（2026-10-01，历史；接口合同继续有效，当前接续见§3.11）

[接口裁决§6](h04_loop_origin_escalation_20261001.md)已生效，窗口二无需再等接口许可。
当前源码9c671806/build0c06c8f1/stage6d1b6003/outputs2a27b7b9匹配，未改runtime仍43490765…。
owner71pass/13skip、B02目录23/doctor exit0已核对，本轮未启动独立QA或产品验收。
合法child也被拒、联合重建absent，不是H-R4完整关闭或Gate-H通过；13项必须恢复真实执行。

窗口二继续原第01份完整阶段，额外授权窄runtime来源源码补丁与新候选
`.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1/`，原0.2树/旧0.1.5/日常0.1.7保留。
先封存FAIL-CLOSED源码/测试/receipt基线，修订接口：runtime私有实际loop派发，覆盖prepared与
回落；所有公开stream/prepared handle入口清除来源，不能只清公开llm.stream；不暴露可变
store或可mint/预消费票据的公开接口，真实同步/惰性/等待/清理均留证。Host仍只用公开核验。
ALS可以承载来源，§3原样方案未获soundness批准。细节、环境选择和完整交付见裁决§6.2–6.4。

由窗口二连续完成源码/可重建patch→新候选严格选择与隔离→Host接线→原反例及合法正例→
全部13skip/被改成合法拒绝的原正例恢复→同child committed新进程恢复→B02/H01/H02复验→
完整稳定check:compat/B02/doctor→统一base/patch/source/runtime/build/stage身份与写权释放。
候选ID和上游版本分开，缺patch回执/环境选择错配仍拒绝，不假改package.version。
新patched树必须报新身份，不能沿用43490765；补丁只在明示本地候选验Gate-H，不批准原npm树。

窗口一791个原Python源码/测试及原证据保持component，不重复调查或全量，不写C/R/validator。
正式Gate-K仍等Gate-H；之后按原第03份整包、再第04份串行mock。8份执行文档/49任务不变。
本轮没有新QA冻结；owner已释放写权，窗口二直接续完整阶段，QA仅完整候选时按需启动。

### 3.11 loop-origin.1独立差分已收口，窗口二集中返修（2026-10-01 19:40，历史；接续见§3.12）

[本批裁决](stage_loop_origin_acceptance_20261001.md)绑定新候选`0.2.0-rc.1+loop-origin.1`、
实际runtime `1e0e6fa2…`、当前peer及统一source/build/stage身份。原434基树和旧默认树未变。
owner84项0skip完整记录已核对，合法prepared/fallback/联合恢复已恢复；原H-R4公开prepareCall
32次均拒绝、合法child及R/D/S/adapter各一次独立通过。不要重开旧“所有合法child也拒绝”诊断。

独立原11文件83pass+1个QA输出根断言失败；按原launcher环境仅复验sandbox2项全部通过。
该驱动失败保留，不能作为产品问题，也不覆盖其原exit1。新增真实普通公开流误拒、公共
NO_ADAPTER语义变化及旧manifest加载拒绝，与源码/types/公共consume合同缺口集中列为LO-1–4。
Gate-H仍CHANGES_REQUESTED，不以原84总数宣布通过。

窗口二接回原第01份及裁决§6窄源码写权，一次完成旧格式兼容、实际源码/types/私有来源与
所有公开入口隔离、原攻击和普通公开正例、受影响等待/清理/联合committed新进程恢复，
最终稳定目标check:compat/B02/doctor与真实AT/身份交付。完整环境、路径及步骤见裁决§3。
不逐问题派工、不重封原0.2/旧0.1.5，不改Python/validator/LEAD或日常0.1.7，不用vitest/live。

窗口一791条Python源/测试及原六份日志保持同身份，保管已验component与复用清单；
无新返修、不重复调查或4129全量。第03/04份仍等明确本地patch的Gate-H及正式Gate-K；
原8份执行文档/49任务和领域唯一owner不变，owner写权释放不单独授权后续阶段。

QA全部命令返回，912输入/三棵runtime/peer字节及metadata未变；宿主1750进程中相关验证0、
不可读0，19:40:04+08明确释放实际读集，仓库可读closing见裁决§5与台账记录。
本批QA结束，窗口二直接连续返修，完整新冻结包再按需独立验收。

## 4. 单元工作方式

一个单元是可独立审查的改动，不强制对应一个Git提交。遵循现有owner、小步抽取和契约先行：定位真实边界 → 最小反例/旧行为特征 → 修改原owner → 单元及合同验证 → 真实产品接线 → 独立复核 → 交接。新的适配器不复制IR、parser、assessor、composer或账本。新增抽象必须有本阶段实际调用者。

Ready条件：开发前置有可复核证据；本轮两个阶段按 §3.1 的 `implementation_depends_on` 与前置实现/本地合同证据衔接，其他任务默认使用 `depends_on`；完成仍检查全部 `depends_on` 和原验收门。输入/协议/验收明确；责任文件无人同时写；所需工具链存在；live任务另有具体授权和额度。新版基础迁移完整源码/测试不能裁掉；H03/H04 消费 owner 版本化接口候选，独立冻结在阶段 QA 完成。实际状态以任务台账为准；planned不等于故障阻塞，也不等于已实现。

Done条件：任务卡全部AT通过，合法正例和具名反例、该单元范围内的真实调用者/恢复入口齐备；新增裁决来源进入validator identity；存储版本/legacy/恢复说明清楚；独立reviewer确认；准确记录命令、退出码、原始输出和身份。H03等compat spike及I01基础原语可以用明确fixture验本单元，后续产品接线必须落到指定C/R/V任务，不反过来成为它们的前置。不能以编译通过、工具成功、测试数量、DSH completed或mock accepted替代领域与质量结论。

状态使用planned→ready→in_progress→review→done；发现缺陷回in_progress；waiting_live只用于缺具体live授权；blocked应写明实际外部依赖与可解条件。台账与阶段文档同步，历史证据不可改标身份。

交接记录写入仓库已有.agent/implementation.md或对应证据文档，至少含：任务ID、输入/代码/config/composition/validator、owner/reviewer、改动范围、接口版本、复现/修复/接线结果、准确命令/退出码、产物引用、未测风险。运行原始输出使用fresh任务根；开发沙箱内需写显式挂载的run root，不依赖其私有/tmp持久化。凭据和认证URL不写入记录。

## 5. 并行编辑、版本和回退

共享大文件`publication_method_writer.py`按K04→C02→G05/G06→F01/F02交接，一次只有一个写者；registry/publication/index按K01–K03串行；身份文件I01与后续claim/fence按台账交接。DSH session-binding/role-dispatch/request-accounting及Python protocol的跨任务接口由LEAD统一冻结。准备同名新模块时先核当前树，不覆盖他人的改动。

不切分支、不reset/clean、不回滚不相关dirty内容、不自动commit/merge/push。保留paperbanana_single_shot脏子模块、docs/1.txt草稿和原始run目录。允许并行的是互不冲突且依赖满足的单元；无文件锁时宁可串行。

接口变化必须说明受影响task/read-set/epoch/receipt、兼容reader、迁移和重验范围；协议/工具renderer/模型能力/schema/预算版本变化均更新组成身份。旧档案只读，回退到固定旧引擎使用fresh root及已验证Research import，不拿新schema强制resume。开发profile不替换日常DSH profile，也不改变旧CLI默认。

## 6. 验收与当前状态

完整门和需求追踪见 [verification.md](verification.md)，共享合同见 [interfaces.md](interfaces.md)。规划与 B00 阶段只检查文档及输入身份；B01/B02 实施与验收阶段已运行各自聚焦的 Python/Node 检查及隔离探针。结果按实际执行身份登记，未调用真实模型、未重新生成 live 准入回执。

B00/B01 保持历史 done；B02/H01–H04 为新版 in_progress，Gate-H 仍 CHANGES_REQUESTED；
K01–K04 保持已验 component PASS，正式 in_progress/Gate-K 等待 Gate-H。
当前交付、独立反例和明确读集释放见 §3.15；产品测试由独立 reviewer 复跑，LEAD 仅登记，没有实现代码修复。
旧版 [H02 验收](h02_acceptance.md)、[H01 验收](h01_acceptance.md)、[Gate-B 验收](b01_b02_acceptance.md)
与 [B00 冻结](b00_baseline_freeze.md) 保留原身份，不能批准新版。首次能声称“已接入”的
范围仍止于 Gate-V 独立 Writer mock，主图、质量和默认切换另过门。

### 3.12 返修差分、公开预消费阻断与完整续派（2026-10-02 00:02，历史；接续见 §3.13）

[详细裁决与两窗口完整指令](stage_loop_origin_repair_acceptance_20261002.md)§§2–8包含仓库/分支/环境、当前身份、立即任务和第03/04份的排队分工。owner原86/0skip、B02dev24、doctor记录已核对；独立LO1普通三入口、LO2公共NO_ADAPTER/native回落、LO3旧manifest均通过，固定源码/types及源码构建JS实际交付。
但公开admit仍修改一次性状态：async_hooks公开观察者先拿admitted，合法child error、R/D/S/adapter全0，交付与真实source-built候选都复现；各有合法childcompleted/四项1的正对照。Gate-H仍CHANGES_REQUESTED，正式Gate-K未过。没有以86项宣告完成或重跑内核4129。

本批1023输入/四棵runtime/peer前后同，791Python源/测试及九份原运行文件不变；宿主1754进程相关0/不可读0、全部命令返回。LEAD于2026-10-02T00:02:16.056112+08:00明确释放实际读集，稳定权威根`.dsh-dev/run/qa-loop-origin-repair-0yrz6nyl/`。上批候选内QA/owner根当前不存在，原历史不伪补；窗口二先封存当前证据至候选外，再连续做私有native消费/全部公开入口隔离、原AT与同child恢复、source/build/完整验证/冻结交付。既有§6授权有效，不逐缺陷申请。
窗口一保管已验第02份和已交付复用清单，不重复调查/全量/提前C/R或validator改动。只有实际Gate-H及正式Gate-K满足才一次启用原第03份I01→C01→C00→C02→C03→C04：窗口一Python/协议/validator单写，窗口二C00/TS/唯一buildstage。Gate-C后原第04份完整串行mock，保留Gate-R/V和单独live授权。当前只有窗口二有必要施工，QA结束，无常驻第三窗口。

### 3.13 私有消费候选独立复核与完整返修接续（2026-10-02 12:12，历史；接续见 §3.14）

[本批复核](stage_private_consumption_review_20261002.md)绑定交付 runtime `a010ccdc…`、
源码构建 runtime `7ae6af55…`、source `12f33263…`、receipt `85a37546…`、stage `950ba6d4…`。
独立原 11 文件套件 87/87、显式候选 B02 24/24、doctor 通过；原 C21、C19/C20、同 child
committed 恢复保留。两棵候选各实际运行 4 个新探针：prepared/fallback 正对照通过，
同步 `internal/get` 公开 take 预消费导致合法 child error/零 RDS/adapter，自定义公开 iterable
获取看到外层来源，均真实 Node exit 1；实际 manifest 与生成器仅列 2 JS，漏列 2 types。
Gate-H 仍 CHANGES_REQUESTED，正式 Gate-K 未过，原 8 文档/49 任务与 AT/依赖不变。

本批实际读集于 12:12:01+08 明确释放：992 输入的字节/metadata、四 runtime 和 peer 未变，
宿主相关进程 0、不可读 0、全部命令返回。权威根 `.dsh-dev/run/qa-private-consume-20261002-7o8lt6bj/`。
窗口二按本批 §4 一次接回原第 01 份完整写权，连续修三个问题、原正反例/AT、源码双侧、
同 child 恢复和最终稳定验证/封存/冻结；不逐缺陷申请。窗口一保持 791 条 source/test
未变的已验 component，无新增内核返修或 4129 全量。下一完整冻结包再按需独立验收。

本批 §5 保留后续完整分工：实际 H/正式 K 后启用原第 03 份，窗口一 I01/C01/C02–C04
及共享 Python/validator 单写，窗口二 C00/TS/唯一 buildstage；Gate-C 后原第 04 份
R01→R02→R03→R04→V01→A01→V02，保留正式 R/V 门与单独 L01 授权。当前无 C/R 提前实现或 live。

### 3.14 能力门控候选差分与原阶段完整接续（2026-10-02 14:48，历史；接续见 §3.15）

[本批报告](stage_capability_entry_review_20261002.md)绑定实际交付树 `0adaffc8…`、
源码构建树 `dcf69658…`、patch `f1a310cd…`/`23ab6350…`、receipt `a6c69d83…`、stage `66458c03…`。
原交付 11 文件套件独立 87/87、0 skip，B02 24/24、doctor 通过。每侧 5 个独立探针：
prepared/fallback 和同步公开伪造能力观察者通过；公开 resolver 返回转发 Proxy 后，真实
capability 实参可被观察者 admission，合法 child error、R/D/S/adapter 全 0，两侧真实失败。
iterator 获取仅交付侧修好，源码/源码补丁/源码构建侧仍 seesOrigin=true。manifest 与生成器
四文件清单已修；兼容 JSON/当前接口表和 owner 声明仍引用旧树/API。Gate-H 仍 CHANGES_REQUESTED。

本轮 14:48:55+08 释放自己的实际读集：1054 输入/四 runtime/peer 未变，己方进程 0；
另有此前启动的源码构建全套验证进程 4 个，约 100 分钟未返回。**不登记全局清空或候选立即可写。**
窗口二先保存/收尾自己的该运行并确认释放候选/peer，再按本批 §4 连续原第 01 份整包返修：
能力不得经过公共 resolver 返回的方法、源码双侧隔离与构建、稳定原 AT/同 child 恢复、身份/API
一致及最终冻结。旧日志/QA 根先保存在候选外，不逐缺陷申请权限，不常驻第三窗口。

窗口一保持 791 源/测试未变的原第 02 份 component；实际 H/正式 K 后按本批 §5 启用原
第 03 份的既定分工，Gate-C 后原第 04 份；原第 05–08 份排队，无 live/default cutover。
原 49 任务对象保持 2 done/9 in_progress/38 planned，不以新增问题扩张任务拆分。

### 3.15 当前：模块级派发候选 Gate-H 独立审查与原第 01 份整包续派（2026-10-02 22:10）

[本批审查](stage_static_entry_gate_h_review_20261002.md)由未参与实现的独立 reviewer 执行，绑定交付树 `392e4acf…`、
源码构建树 `301a5e23…`、patch `eac2d8c5…`/`30133c39…`、receipt `352551db…`、stage `904f6ecf…`
（源码构建侧 receipt `2d39b949…`/stage `4900edd0…`）。两侧原 11 文件套件各 89/0/0skip、Node exit 0，
源码构建侧完整结束，89 个原节点两侧全部映射。原三类反例（resolver Proxy 截获、同步伪造能力观察者、
自定义 iterator 获取）两侧关闭且各有 prepared/fallback 正例；Web/compat HTTP、交付 B02 24/24、doctor 通过。

阻断项见报告 §3：GHS-1 公开 `streamWithRegistration(..., true)` 在合法 child 作用域内取得受信派发，
替换材料到达 adapter，R/D/S/adapter 各 1→各 2（两侧、两路径）；GHS-2 runtime 注册表只增不减，销毁重建
deployment 后合法 NO_ADAPTER 回落失败；GHS-3 两包候选 `.d.ts` 不等于固定源码独立 tsc 输出，interface-diff/
evidence 正文仍有旧树和已删 API；GHS-4 源码构建侧缺 Python worker，B02 22 passed/1 failed/1 skipped。
**Gate-H 仍 CHANGES_REQUESTED，正式 Gate-K 未过。** 1134 输入、四 runtime 与 peer 前后不变，
22:10:34+08 明确释放，宿主相关验证进程 0。权威根 `.dsh-dev/run/qa-gate-h-static-entry-20261002-c44c4lep/`。

窗口二按报告 §3–5 一次接回原第 01 份完整写权，连续修完再冻结一次，不逐发现申请。受信派发身份只由
runtime 私有通路建立：公开方法、公开参数和公开 resolver 可包装的对象都不得声明或携带它，实例解析与
prepared record 也不经包装对象（[14:48 复核](stage_capability_entry_review_20261002.md) §4 第 1 项）；仅加 TS `private` 不算修复。注册归属随真实
service/deployment 生命周期注销，保留 fail-closed 与合法回落，不删 size 门、不任选、不清除其他存活实例。
`-built` types 用固定源码 tsc 输出或可复现转换并绑定输入/输出身份，交付 hunk 的公开 API 与源码声明一致，
interface-diff/evidence 历史段落全文绑定旧树。正式 Gate-H 只批准交付的本地 patch 候选（接口裁决 §6.4）；源码构建侧默认明确收窄为
源码等价证据，不声称 B02/doctor，若要声称完整则补齐同锁 worker，不借用交付 worker、不删测试、不以 skip 计通过。
保留全部原 AT、本批正反/因果/生命周期对照和同 child 恢复；owner 每条验证命令的 argv/cwd/环境/退出码/日志
封存在 `/tmp` 之外。无 live、默认切换或 Python/validator 修改。

窗口一保持 791 份源/测试未变的已验 component，无新增内核工作或 4129 全量。下一完整冻结包由新的独立
reviewer 差分验收；实际 Gate-H PASS 后 LEAD 复核放行正式 Gate-K，再启用原第 03 份
I01→C01→C00→C02→C03→C04（窗口一 Python/协议/validator 单写，窗口二 C00/TS/唯一 buildstage），
Gate-C 后原第 04 份。原 8 文档/49 任务、AT 与依赖不变。

**依据与逐项对应。** 窗口二核对原文，不以本节摘要代替：[仓库入口](../README.md)与仓库根 `AGENTS.md` 边界；
[总设计](../code2paper_dsh_plugin_design_20260922.md) §8.2、§16.0；[接口裁决](h04_loop_origin_escalation_20261001.md) §6.2–6.4；
[第 01 份](01_baseline_and_dsh_compatibility.md) B02/H01/H02/H04 任务卡、第四步与「验证、交接与完成门」；
[interfaces](interfaces.md) §0–1；[verification](verification.md)「按需独立验收任务」§§4–5 与「测试层次与证据格式」；
[本批审查](stage_static_entry_gate_h_review_20261002.md) §§3–5；[14:48 复核](stage_capability_entry_review_20261002.md) §4。
GHS-1 依裁决 §6.2 第 1–3、5 项，14:48 §4 第 1 项，interfaces §0，总设计 §8.2；GHS-2 依裁决 §6.2 第 4–5 项与
H01/H04 任务卡；GHS-3 依裁决 §6.3–6.4，14:48 §4 第 2、4 项与 H02 任务卡；GHS-4 依裁决 §6.3–6.4、B02 任务卡与
verification「按需独立验收任务」§5；交付包依第 01 份第四步第 3–4 项与完成门、裁决 §6.4、14:48 §4 第 3–4 项与
verification「测试层次与证据格式」。现有 ABI 无法兑现裁决 §6.2 时，按 §6.4 一次提交具体调用链请 LEAD 裁决。

## 2026-10-03 四组集中返修 owner 提交

[本批当前交付记录](../../integrations/dsh/dev/gate_h_repair_batch_20261003.md)绑定新封存根，记录生产激活/审计/smoke入口修复、两侧93项与B02 48项、完整输入及原791份内核保持。owner submitted_for_independent_qa；Gate-H待独立复验，正式Gate-K等待；第03–08和49项计数不变。旧92/24、round9及历史API段落按其原范围保留。
