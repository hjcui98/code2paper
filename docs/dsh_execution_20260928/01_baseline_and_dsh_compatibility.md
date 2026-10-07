# 01 · 基线、开发工具链与实际 DSH 兼容性

> 2026-10-03 18:03：本份 B02/H01–H04 已独立验收，**Gate-B / Gate-H PASS**。
> 当前接受身份、四组关闭证据及正式 Gate-K 接续见[本次裁决](stage_four_group_repair_acceptance_20261003.md)。owner 冻结记录保持原字节；以下未通过/待返修表述为历史候选。

> 2026-10-03 16:05 [冻结整包独立审查](stage_whole_package_review_20261003.md)：原 GHS-1/GHS-2、两侧 93 项及独立来源/生命周期对照通过；保留现有 runtime 修复。
> 当前余项按该报告 §3–§4 一次完成：activate/audit 失败边界、正常 smoke 身份、真实生产入口回归、全文交付与输入冻结。Gate-H CHANGES_REQUESTED，QA 已释放；原任务与完成门不变。

> 2026-10-03 整阶段接续：[全部剩余工作与集中修改指导](remaining_work_and_batch_repair_guidance_20261003.md) §3 给出本份完整修复顺序、覆盖矩阵与一次交付条件。
> 第九轮代码已有改进，剩余确定缺陷与验证缺口分别列明；本指导不登记 Gate-H PASS，下列旧审查结论仍绑定各自候选。

> 2026-10-02 22:10 最新派工见 [README §3.15](README.md)（含依据与逐项对应）和 [模块级派发候选 Gate-H 独立审查](stage_static_entry_gate_h_review_20261002.md) §§3–5。
> 同一原第 01 份继续返修：公开布尔受信入口（GHS-1）、注册表生命周期（GHS-2）、types 来源与全文身份（GHS-3）、
> 源码构建侧 B02 声明范围（GHS-4）。两侧原 89/0skip 与原三类反例已独立通过；读集 22:10:34 已释放、相关验证进程 0。
> Gate-H 仍 CHANGES_REQUESTED，窗口一保持 component；14:48 及更早检查点按各自旧树解释。

> 2026-10-02 14:48 最新派工见 [README §3.14](README.md) 和 [2026-10-02 14:48 能力门控候选复核](stage_capability_entry_review_20261002.md) §4。
> 同一原第 01 份继续返修：resolver 实参泄漏/预消费、源码侧 iterator 隔离、身份/API 统一。
> 四文件 touched 和普通伪造能力观察者已通过；原交付套件独立 87/0skip、B02 24/doctor 通过。
> 本轮 QA 读集已释放，owner 仍有未结束源码构建验证；先收尾/释放候选再写 runtime/peer/stage。
> Gate-H 仍 CHANGES_REQUESTED，窗口一保持 component；更早检查点按各自旧树解释。


> 2026-10-02 12:12 当前：[私有消费候选独立复核及完整返修接续](stage_private_consumption_review_20261002.md)。
> 原套件独立 87/87、显式 B02 24/24、doctor 通过；同步 internal/get 预消费 entry-ack 与公开
> iterator 获取来源泄漏在交付/source-built 均有真实失败/合法正对照，manifest/生成器漏列 types。
> Gate-H 仍 CHANGES_REQUESTED，正式 Gate-K 未过。实际读集已明确释放，窗口二按 README §3.13
> 与本批 §4 连续完成原 B02/H01–H04 整包返修。下列 00:02 与更早裁决保持各自历史范围。

> 2026-10-02 00:02历史：[返修差分与完整接续](stage_loop_origin_repair_acceptance_20261002.md)。窗口二整包写权已恢复；继续原B02/H01–H04及§6窄源码，集中关闭公开admission预消费、完成原AT/联合恢复与稳定证据冻结。Gate-H仍CHANGES_REQUESTED，正式Gate-K未过。

> 2026-10-01 19:40当前：loop-origin.1已交付，合法child与原H-R4负例独立成立；新增LO-1–4普通公开流/公共NO_ADAPTER/旧manifest及源码/types/私有消费缺口见[集中裁决](stage_loop_origin_acceptance_20261001.md)。按README§3.11、原接口裁决§6继续本份完整阶段，QA实际读集已明确释放。原84项有效证据保留；Gate-H仍CHANGES_REQUESTED。以下FAIL-CLOSED及更早状态均属历史输入。

> 2026-10-01当前：FAIL-CLOSED候选71pass/13skip、合法child不完成；风险已抑制，H04仍CHANGES_REQUESTED。按README§3.10与[LEAD接口裁决§6](h04_loop_origin_escalation_20261001.md)继续完整阶段，授权新隔离runtime来源补丁候选；原43490765…树不改。新增窄源码写权仅见裁决，不削弱原AT或将skip算PASS。

> 2026-10-01 11:36当前：owner84项候选核对完成，原公开stream三个对照独立通过；公开prepareCall原反例仍取得闭包，H-R4真实exit1。按README§3.9与[本批裁决](stage_handle_acceptance_20261001.md)连续修原阶段；QA已明确释放。以下R2及更早结果绑定历史输入，Gate-H仍未通过。

> 2026-10-01最新R2候选实际验收见[R2裁决](stage_r2_acceptance_20261001.md)与README§3.8。旧listener变体已修，公开prepareCall和fallback首次认领仍失败；原83项通过不等于Gate-H。QA已明确释放，窗口二连续完成同一原阶段。

> 2026-09-29 迁移批次：**开发候选固定 0.2.0-rc.1，窗口二独占 B02/H01–H04、launcher、TS 与构建。** 旧 0.1.5 的 B02/H01/H02 验收保留，新版重新取证。连续完成环境/接口、来源证明和同 child 联合接线，交付一个完整运行阶段；不再为旧版补齐 Gate-H。各单元本地合同通过后继续，不逐项等独立审批。

> 2026-09-30 21:36 后：返修候选独立74项与B02原目录23项、普通Web/compatHTTP通过。
> 原F1/F3/F4同步/F5已修复，但H04公共同request引用和真实NO_ADAPTER回落仍可抢票，
> **CHANGES_REQUESTED，Gate-H 未过**。QA已结束并释放读集；窗口二直接连续完成
> 原阶段剩余AT，见[执行入口 §3.7](README.md)、[返修差分裁决](stage_repair_acceptance_20260930.md)
> 与[独立返修报告 §5](gate_h_repair_independent_review_20260930.md)。下列旧检查点按历史解释。

依据：总设计 §§2、7、8.3、11、20、21；[执行入口 §3.1](README.md)、[台账](task_board.json) 与 [接口合同](interfaces.md)。用户已授权选择 0.2 候选并据此分工；窗口二接管后可在下述隔离范围执行，无需再为每个目录、安装或聚焦测试申请开工。模型/live、日常安装、旧 runtime 修改不在本批次授权内。

## 版本身份与迁移裁定

| 对象 | 状态及约束 |
|---|---|
| Code2Paper | `0918ee7` 是历史代码对照；HEAD `d48b4e4` 之后还有 K04 与 TS 工作树改动，不能称当前代码仍等于基线。0918 的 4014 passed 回执不批准当前输入。 |
| 旧开发对照 | `.dsh-dev/runtime/` = `0.1.5-rc.3`，历史树摘要 `7e8f199b…8d3ab`；[B00 清单](source_inventory.json)、旧 manifest、H01/H02 验收与旧 H02 接口记录只读。源码 SHA 未认证。 |
| 日常安装 | 用户正在使用 `0.1.7-rc.2`；日常 home、安装、配置、凭据、会话和入口不参加迁移。历史 manifest 指向的原 npm 安装后来由用户升级，不能要求它退回 0.1.5 或改写历史 hash 使检查通过。 |
| 新开发候选 | 精确版本 `0.2.0-rc.1`，官方 tag `dsh-v0.2.0-rc.1` / SHA `4878cdabd87d4041bdaff61d04c966883b9fd07a`。已隔离安装，LEAD 只读确认实际包版本；未取得基础包运行验收；实际 npm lock、包树、Node、native deps 和 build 另记，不能只写源码 SHA。 |
| 静态比较 | 0.1.7→0.2 所查 91 个核心源码文件中 4 个变化：agent-loop 与 Session 的失败工具恢复；LLM、Agent 创建、subagent、tools、preset registry、persistence 所查源码未变。只证明源码差异，不证明本地安装兼容。 |

版本研究记录：[0.1.5→0.1.7](</tmp/c2p-dsh-017-compatibility-20260929-c_wur6ss/review.md>)、[0.1.7→0.2](</tmp/c2p-dsh-020-compatibility-20260929-zfbf_dge/review.md>)。持久结论、目标与验收均写在本文件，不依赖 /tmp 存活。官方依据：[0.2 发布](https://github.com/deepseek-ai/deepseek-harness/releases/tag/dsh-v0.2.0-rc.1)、[失败 step 恢复](https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/packages/core/agent-loop/src/agent.ts#L331)、[工具恢复表示](https://github.com/deepseek-ai/deepseek-harness/blob/4878cdabd87d4041bdaff61d04c966883b9fd07a/packages/core/session/src/repair.ts#L105)。

| 边界 | 从 0.1.5 到新候选必须做的适配 |
|---|---|
| H01 preset | 旧复数 `dsh-agent-presets` 和目录扫描配置不能照搬。按新 `dsh-agent-preset` / `dsh-agent-preset-registry` 声明式组成适配，复验 Host/preset 分权、scope、generation、override、销毁和拒绝路径。 |
| H02 创建 | 新版 `agent/created` 改为 awaited serial，旧“不 await”特征仅保留历史证据。继续先 claim 后创建、setup 内完成可信绑定；不因事件变化自动改回 stock spawn 或后置补绑。对象归属准入、旧 fence、创建取消和真实类型消费均重验。 |
| H03 Session | V3→V4；成功结果从旧嵌套 tool-result block 转为独立 tool 消息，校验对应的 callId/turn/step 与 `isError`。新旧记录明确分 reader/版本，不用宽松字段回退伪装兼容，不迁移日常 sessions。 |
| H04 派发 | 新版 `llm/stream` 仍由 LlmRuntime 自身 context 发射；没有 child 隔离保证。prepared 的单次/config 门不覆盖完整 messages/tools；来源、实收摘要、回执与取消仍由本接入证明。 |
| 0.2 恢复增量 | live step 失败时补出 `TOOL_NOT_STARTED` / `TOOL_OUTCOME_UNKNOWN` 的错误结果。两码在 0.1.7 已存在；不得将补记结果作为 terminal 成功、usage、已结算、可重试或预算可退的证明。 |
| 组成 | 重新盘点新 provider、title/retry/compaction/PTC、OTel/desktop 专属行和可选 Schedule bundle；显式 mock 白名单与网络隔离仍要成立，不能只复用旧 disabled 行。 |

## 持续任务合同：窗口二负责到 Gate-H 候选完整

“窗口二”沿用现有实施者身份，不要求同时维持三个窗口。按执行入口 §3.3 有独立工作才并行，
完整候选就绪后再安排独立 QA；没有候选时不配置常驻验收会话。本文整阶段责任与验收门不变。

**2026-09-30 前一检查点（历史，后续进度见下段）：** owner 的 [迁移检查点](../../integrations/dsh/dev/migration_0.2.0-rc.1_gaps.md)
（LEAD 只读摘要 `ae42e28c…`）报告 0.2 typecheck/build/stage、两种 config 装载通过；
outputs `979c75dd…`、staged tree `abcf9a44…`。Loader 为 1/10，当前实际失败为
`Unknown agent preset: code2paper`。这只是当前已定位的 Loader 首因，不是整个阶段唯一
剩余风险，也不是 B02/H01/H02 通过。H01/H02 的 import/签名适配已开始，台账改为 in_progress。

窗口二直接补齐声明生命周期：按本候选公开 `AgentPresetRegistry.register(definition)`
及 Host 组合 API，将现有 preset YAML 的 plugin 行注册为唯一受版本控制的声明源；在首次
mount/create 前 await 注册，Host 持有 disposer，失败与销毁按公共 API 清理。不要恢复已废弃
的 roots 扫描、复制第二份 plugin 清单或依赖私有 helper。复验 generation/override/销毁/
分权后继续 H02–H04 与联合接线，不把这次缺声明另拆成待审批任务。

**2026-09-30 恢复检查点 2（历史，接续见下段）：** 同一迁移记录当时更新为 `6fc3518d…`。owner 报告新版
H01 10/10、H02 11/11、provenance 13/13；request-seam 5/6、terminal 0/8、cancellation
超过 600 秒无结论。实现采用本 bundle 声明 patch `presets/code2paper.patch.yml`，由公开
`@deepseek-ai/dsh-agent-preset` 注册工具行；保留单一受版本控制的声明源即可，前段“root
自行 register”只是当时方案，不强迫回退已经工作的公开声明方式。旧扫描目录已移除属
新版本适配，旧冻结检查点仍保留。以上是 owner 聚焦结果，尚无独立目标 H01/H02 PASS。

窗口二继续完成整阶段，不交付“只需等更久”的取消结论：先重建 S2 合法绑定 child 的
正对照，逐阶段记录创建/agent-request/准备/reserve/dispatch/adapter/finish/dispose 到达
情况，定位第一处等待；再做授权反例、取消与 V4。取消测试用有界 barrier/每用例截止时间，
故障时保存诊断并按既有资源合同取消、独立 cleanup signal 清理。超时不能报静止/settled，
也不得无限放大 timeout。需要时在现有沙箱 runner 内增加最小聚焦/诊断参数，不能裸跑
Node、补装 vitest 或绕过 sandbox/staging/来源门。模拟模型本应有可解释的有界进展。

**2026-09-30 恢复检查点 3（历史，本次读取 `a528487e…`）：** owner 报告 request-seam
6/6、cancellation 6/6（1.70s），H01 10/10、H02 11/11、provenance 13/13；terminal 仍
0/8。S2 首个失败位于 reserve 前的 `contract-unsupported`，由新增 `toolHistory` 未纳入
封闭摘要覆盖引起；补入该 model-facing 字段后合法正例可派发，取消套件不再挂起。
LEAD 静态确认 `request-accounting.ts` 的覆盖清单含该字段，未运行复验。未知键仍拒绝，
不能排除工具材料来消除错误；旧的 600 秒无结论保留为历史失败，不再安排不变的长时重跑。

在同一阶段继续补齐 B02 候选传递与 worker，再完成 H03 V4 与下文完整 H04 AT、组成保护、
同 child 联合持久恢复和完整 check:compat。LEAD 14:41 静态核对发现 `toolchain.mjs`
虽然读取 `C2P_DSH_DEV_ROOT`，其 `launcherEnvironment()` 不传递候选选择，调用 Python
stage/test 也不带 `--candidate`；Python 默认只读 `C2P_DSH_CANDIDATE`，会选择旧默认根。
当前不能把带外层 env 的 npm 完整链当成显式 0.2 入口。由窗口二在原 owner 修复并验证
每个子节点，修好前使用显式 `python scripts/dsh_dev.py --candidate 0.2.0-rc.1 stage/test`；
不尝试重封旧 staging，也未声称旧环境被写过。目标根的 pyworker 本次不存在，旧 worker
不能替代 B02 目标交付。完整接续入口和命令见 [执行 README §3.5](README.md)。
原两个 child、等待期复制请求/同 signal、prepared/direct/回落、取消静止与 outstanding
清理均按真实节点补齐映射，不能因 6/6 自动判来源合同关闭。`TOOL_NOT_STARTED` /
`TOOL_OUTCOME_UNKNOWN` 仍不构成 terminal 成功、usage、结算、退款或可重发证明。
接口 `_020`、兼容清单、联合证明及独立 Gate-H 尚未交付/通过，完整候选才启动 QA。

**2026-09-30 完整候选交付与实际独立验收（当前）：** owner 完整 `check:compat`
exit 0（11 文件 71 pass）与 doctor exit 0；新 `_020` 接口、兼容清单、目标 worker、
V4 成功对应和同 child 联合恢复已经交付。候选子进程 argv/env 的传递缺口已补齐，
独立 test:compat exit 0 / 71 pass；不再把缺 worker 或旧 V4 0/8 当当前待办。
runtime 实算仍 `43490765…`，旧默认 `7e8f199b…` 不变。

本批实际反例集中返修：H03 损坏 tool/call/消息/错误结构的严格拒绝；H04 公开
withInitiator 在准备等待期抢票、全局 requestDepth 误拒合法兄弟、同步 return 异常
漏具名终态；B02 CLI cwd 仍选旧 workspace、普通 Web 未就绪/两项原 Python 隔离
夹具适配及日常可比较保护证据；原 active scoped 组成禁用映射仍要齐。逐项事实与
有效正向对照见独立报告 F1–F5 和裁决；这些均属原完整阶段，非新增任务/架构。
QA 19:01:54+08 已明确释放，窗口二直接沿原 owner 连续完成，再交完整冻结差分包；
不逐项停工或凭新计数自登 PASS。候选 profile 的两次 mtime 副作用另记，不恢复掩盖。

**本阶段只刷新 0.2 候选。** 当前源码/peer→目标 build→目标 stage→目标测试的身份必须
一致；显式用 `--candidate 0.2.0-rc.1` 与相应 `C2P_DSH_DEV_ROOT`。旧 QA 的无显式候选
staging 报错不能要求新旧两侧都重封，旧回执陈旧也不妨碍新版继续开发。生产 runner 本来
是沙箱内 `node --test`，不是 vitest。只有完整阶段包冻结后才交 QA，不为移动中的每次
build 请求验收；重建后旧 stage 被拒正是保护机制。

新版 roster 出现 `standard` 可以记录为真实组成事实，但成员断言不能折抵权限边界：
要证明 code2paper 工具只在目标组成、兄弟/未加入会话不泄漏，默认解析仍是期望 preset。
声明替换时旧父/child 保持同一 standing generation、新 root 使用新代；“先 dispose 再
register”须验证存活 Agent 不被错误撤销。`return undefined` 与 11/11 不自动证明新版
awaited serial，原 H02 barrier/失败/取消时序在最终阶段依然必验。

显式 `return undefined` 仅解决类型兼容；`agent/created` 的 awaited/取消/抛错和发布时序须由
真实事件 barrier 与创建期绑定证据另证。原 mock 白名单、断网、只读和日常保护矩阵也仍需
目标候选运行证据。保留单一 0.2 活动 peer；不带 env 的 toolchain:install 只能切换开发
peer/工具链，不能单凭它声称旧源码、bundle、receipt 已恢复，旧版完整复现仍按冻结检查点。

Python 旧 QA closing 与读集释放已登记于 [verification §8](verification.md)，窗口一已获
整阶段返修写权；窗口二继续本阶段全部任务。若身份检查确实读到对方变化中的
共享文件，协调该实际读集的短窗口或经校验快照，不以此暂停整个迁移，也不能隐去依赖。

本文件 B02→H01→H02→H03/H04 与最终联合接线是**一项持续阶段任务**；scope/AT 细节见下文
原卡。窗口二负责实现、测试、普通缺陷修复、证据、QA 返修，直到同一 0.2 候选可独立验收。
独立 Gate-H 仍由 QA/LEAD 裁决；不以内部顺利推进冒称 PASS。

1. **先做可运行的 B02。** 消化已 provision 的候选，固定安装/工具链/runtime/Node/peer 来源，
   实跑 readonly+断网+继承环境拒绝；默认环境和候选输入/输出身份不可串用。用户日常保护
   快照与旧复制源分开，安装前缺证保持具名记录，不重装来补证。仅“缺目录能拒绝”不算完成，
   合法候选 typecheck/build/stage/test/CLI mock 启动路径也要成功。
2. **连续迁 H01/H02。** 新声明式 preset、host/preset 分权、代次、创建期绑定/取消/provider
   归属和真实类型消费者逐项实现/聚焦验证。输出 `_020` 接口候选和 version/hash，既有首请求
   前硬门不改。卡片本地合同通过后继续 H03/H04，不等待一次额外 LEAD/QA 放行。
3. **完成 H03/H04，内部并行思考、单写者落地。** V4 terminal 来源、每调用完成事实、严格
   重建、flush/新进程恢复；真实准备与派发来源、完整请求摘要/回执、两个等待点、usage/cap、
   cancel/finalize/资源静止、四项禁用。direct/prepared/回落均须受控；S2 源证明不靠公开 ID、
   signal 或 digest 自报。保留真实合法正例和攻击反例；不能为齐测试改 runtime/private factory。
4. **完成联合与最终回归。** 同一可信绑定 child 的准备→reserve→dispatch→观察型 adapter→
   terminal→结算→持久化→新进程读回；至少两个活跃 child 的独立归属与冒用拒绝。0.2 合成
   error tool/result 不作为成功/退款/重发凭据。完整声明源/测试集合跑一次 check:compat，
   H01/H02 等底层变更后只重验影响面，最后统一候选验所有 AT。
5. **一次阶段交付。** runtime/source/lock/Node/peer/实际解析、build/outputs/staging、
   `_020` 接口、compatibility 候选、AT 映射、日志、边界与 read-set/写权释放一起交。
   基础包可以在内部作为稳定检查点供 QA 提前咨询，但不是 H03/H04 的停工点；最终完整包
   缺一项不得宣告 Gate-H。QA 有实质发现就自主修复并交差分，不请求再次派同一任务。

**共享 peer 链接处理已授权。** `integrations/dsh/node_modules/@deepseek-ai` 目前是单一
活动符号链接，两候选不能同时使用它。窗口二持唯一 install/build/stage 写权，本阶段明确
激活 0.2 工具链后持续完成迁移，**不要求每条实验后恢复旧链接**。旧 0.1.5 以不可变 runtime/
源码/lock/bundle/staging 检查点保留，不把“链接切回旧 runtime”称作已恢复旧版源码身份。
旧版复现实验只在暂停 0.2 后独占切换；每次切换用真实解析/摘要检查，receipt 属于具体候选。
无 flag 默认选择器和日常 DSH 不自动切新，活动构建链接不同于产品默认切换。
共享 `node_modules`/工作树 `lib` 不得覆盖唯一的旧冻结产物；正式候选 staging/build 回执在
候选根保存并绑定实际构建输入。若需要进一步隔离 peer，使用本阶段工具链范围内的最小方案，
无需新开环境工作者。两套 runtime 树本身都不得安装开发依赖。

**自主决定与停止条件。** 本阶段公开 API 的适配、函数拆分、测试修复、候选目录/参数等由
窗口二决定并登记；正常编译失败或未完成一条 AT 不能作为结束任务理由。只有公开能力确实
无法满足硬合同（附完整合法/反例和断点）、需要跨阶段持久协议、日常权限/live、或其他窗口
实际写权冲突才升级 LEAD。禁止切回自报 ID/后置绑定、放松来源或把 TS 做成持久余额权威。

## 当前迁移批次：窗口二的顺序与写权

**统一写权。** 本批次转交 B02/H01/H02/H03/H04 卡片列出的实现、测试与配置给窗口二：
`scripts/dsh_dev.py` / `dsh_dev_smoke.py`，`integrations/dsh/dev/` 工具链、隔离测试及证据，
`package.json` / lock / tsconfig，Host/preset、binding/provider/request-contract、terminal、accounting 及其测试。
新候选元数据用 `integrations/dsh/compatibility.0.2.0-rc.1.json`；新接口用
`docs/dsh_execution_20260928/h02_interface_freeze_020.md`，只由窗口二写此专属交付，LEAD/QA 冻结。
总执行文档和台账仍归 LEAD。旧 `h02_interface_freeze.md`（`0ba7f1ce…`）、旧验收/失败日志不覆盖；
H01/H02 实现可按本次迁移修改，原验收只能引用其原字节。若需调整新共享领域/RPC 语义，先交具体差异，不能借迁移发明 TS 持久余额。

### 本轮安装检查点与立即继续项

旧 [33/33 检查点](../../integrations/dsh/dev/checkpoint_0.1.5-rc.3.md) 已交付；候选根
`.dsh-dev/candidates/0.2.0-rc.1/runtime/` 已有精确依赖与实际 `@deepseek-ai/dsh@0.2.0-rc.1`。
LEAD 只读确认这两个 package.json，未复跑安装、计算整树或运行候选。owner 报告安装 exit 0、
546 packages、树 `797f9cb1…`；树值暂为报告值，交包须附算法/清单。B02 进入 in_progress，
不重装已经存在的同版候选；先核 lock/完整性，按下列原步骤补保护/选择器，再适配 H01/H02。
compatibility 候选清单及 `_020` 接口尚未交付，不能进入正式基础验收。

**保护检查的证据要求：**

- 旧 runtime 必须调用与历史 manifest 相同的只读 inventory/tree_digest 算法核对完整字节及链接目标；
  条目数、目录 mtime 或另一算法的新摘要不能证明未变。无需启动可能补写 profile 的 doctor 来取这个证明。
- 历史日常安装由 0.1.5 变为用户现用 0.1.7，是已知身份变化；不覆盖旧记录，也不默认所有 lock
  差异都是用户升级。候选/日常/历史复制源分别登记、分别比较，未知变化仍具名拒绝。
- 当前日常只读快照建立于何时必须写清。若本次 npm 安装前没有可比较的快照，就如实标记该段
  前后字节证明缺失，结合已有安装命令/写入约束日志说明可证明范围；现在的快照只覆盖后续操作。
  不倒填安装前状态，不为补证重装或要求用户回退日常版本。基础包需证明后续开发的只读边界、
  无共享可写 inode/写通路及漂移拒绝；既往缺证由 QA 具名判定，不用新快照自动抹去。
- 正常 guard 只比较已登记快照、不得遇到差异自动更新信任值；登记当前日常身份是本批已授权的
  显式步骤，留可审查清单与来源。安装后候选 runtime 在运行沙箱内只读，专属输出独立可写。

### 第一步：保存旧检查点，再安装独立候选（B02）

1. 记录接管时真实源码/测试集合、旧 lock/build/outputs/staging 与工作树差异；保留 S2 首次失败日志。
   owner 最新报告是旧版 terminal 8/8、provenance 13/13、cancellation 6/6、seam 6/6，共 33/33；源码 `1a773347…`、seam 测试 `d1aa14a1…`。prepared 绕门修复与 WeakSet 信号方案作为检查点保存，不等同独立来源证明。保留此前 5/6 的首次失败日志，不混合不同输入计数，不把新输入签回旧回执。保存后立即进入下面安装步骤；不等待旧版 S3–S6、K04 或 Gate-H 补齐。
2. 使用新根 `.dsh-dev/candidates/0.2.0-rc.1/` 容纳候选 runtime、锁文件、独立 home/profile/workspace/run/cache、工具链安装产物、lib 与 staging。复用现有 launcher/toolchain，增加显式候选选择；具体命令在 dev README 交付并实测。旧 `.dsh-dev/runtime`、manifest、home/profile 和 staging 身份不重封、不覆盖。若要复现旧版，消费其冻结源码/bundle 快照，不能加载新版源码冒充旧候选。
3. 安装精确 npm 版本并锁定依赖，安装操作仅写候选根及其专属缓存；不用全局安装、日常 npx 前缀或日常 profile 解析 peer。固定 Node/包版本、integrity、实际树摘要与 peer 解析路径；DSH/Cordis 仍是 runtime 外部 peer。不能把官方源码 SHA 当作发布 tarball 的可复现构建证明。
4. 安装结束后 runtime 只读；mock 子进程继续 bubblewrap 根只读、断网、清理继承密钥/代理/Node/Python 注入变量，HOME 保持原值；只允许专属 run/output 可写，保留端口不可占用。下载依赖与运行无网络 mock 是两个阶段。
5. 修正日常安装保护的身份比较：历史来源摘要原样保存；对用户现用安装单独登记当前只读快照，证明本次操作前后未改安装文件且无共享可写 inode。用户正常使用产生的会话活动不等同开发越界；不要读取/复制日常凭据或 session 内容。保护失败应区分用户升级、候选漂移和开发越界，不能删掉检查或自动重封通过。

### B02 新进展与尚缺的行为验证

owner 已用原 inventory/tree_digest 报告旧树 `7e8f199b…` 与历史 manifest MATCH；自拟
`f8bb6282…` 作废。日常安装缺安装前快照已如实登记，不追溯补证。检查点更新为 `706f4152…`。
launcher 已实现 `--candidate` / `C2P_DSH_CANDIDATE` / 只读 candidate 子命令，LEAD 静态
确认源码存在（本轮未执行）；仍不是基础包就绪。继续原 B02 保护/home/profile/只读沙箱和
工具链适配，再 H01/H02，不重复安装或旧版套件。

候选“报告路径”不能替代行为证明：build/stage/test/config 及 peer/native deps/缓存/pyworker
实际使用该候选；CLI 与环境变量优先级一致，非法/缺失候选拒绝且不悄悄回退旧环境。保护读集
包括真正的 build 输出和 manifest 路径，不能只重绑表面常量。此前 candidate_status 的
`default_runtime_untouched` 已由 owner 改为 default_runtime 的显式完整性状态：默认 not_checked，
只有历史同算法实算才 verified/drift，缺根/身份分别具名；LEAD 静态确认，正式行为归 B02 QA。
require_candidate_ready 已阻断缺候选 profile 的运行，属于负例进展，不等于候选已能运行。
窗口二直接继续 home/profile/workspace/run、只读隔离、日常保护身份、工具链及 H01/H02；
不再逐 helper 停下等待裁决，完整基础包一次交 QA。实际候选合法命令也必须成功，不能只证明拒绝。

### 第二步：迁移 H01/H02，交一个基础候选

按上表改 preset、peer、创建时序和消息类型。先使**正式完整源码及测试集合** typecheck/build/stage 通过；
不得从 glob/tsconfig 移除 H03/H04 来获得绿色。允许此时 H03/H04 行为测试尚未通过，但逐项列为未闭合，不能声称完整 check:compat 通过。

基础交付范围是 **新版 AT-B02 + AT-H01 + AT-H02**，用现有 runner 的聚焦选择执行工具链、隔离、Loader、绑定/取消与真实类型消费者；实际命令、目标候选选择、发现的测试集合必须写明。供后继消费的接口冻结记录包含完整真实导出、请求四方法、资源责任和活跃 binding 生命周期示例。旧 H02 的对象归属、撤销/同名替换、旧父不能借当前 hint 升权等反例不能删。

B02/H01/H02 的本地合同与聚焦测试通过后，窗口二登记版本化 `_020` 接口候选并直接进入下面接线；QA 可提前咨询，但不把独立 PASS 作为内部编码许可。接口变化同步真实消费者和身份，最终由同一阶段候选独立冻结。若已有正式 QA 正在读取，则只冻结其实际读集；阶段 Gate-H 仍独立验全部 H01–H04。

### 第三步：在新候选证明 H04 来源，再收口 H03/H04

**S2 最新检查点与尚缺证明。** owner 已复现并修复 prepared call 直接绕过 wrapper 门；当前
prepareCall 包装其返回的 stream，保留 model 和捕获代次。LEAD 静态核对实现，未运行复验。
新候选仍须观察真正的门入口、授权签发/消费和底层入口，direct/prepared/回落均不得绕门。

准备计数现改为 `WeakSet<AbortSignal>`，由 `agent/request` 的 payload.signal 登记、stream 请求
signal 消费。但信号引用出现在公开事件参数，**不能仅因 WeakSet 私有就断言 signal 不可取得**。
目前 S2 在合法请求结束后才插入不带 signal 的冒用，复制摘要与重放只直接测授权表；未证明
等待中的同一次真实调用不可被抢占。仅以 route+digest 排队的 token 也需绑定消费来源。
先明确普通调用方、可监听公开事件的 Host 扩展与受信任安装者的能力边界；测试只使用实际
公开访问能力，不读取私有 WeakSet。若某类可观察者被排除，须给组成权限依据，不以假定秘密
替代证明，也不声称能隔离拥有任意进程修改权的恶意插件。最小必测集合：

- 合法绑定 child 的准备→reserve→dispatch→授权消费→观察型底层 adapter→settle；至少两个 child 同时存活，A/B 交错且恰好各记一次。多个全局监听器不能误拒兄弟或重复记账。
- 在合法 A 已产生准备、尚未派发的 barrier 中，插入裸请求复制 A 的 sessionId、route、完整 messages/tools/config 和 digest；不得偷走准备或授权，释放后合法 A 仍成功。另在 reserve/dispatch 等待点插入同类请求。
- 若公开监听器能取得 A 的同一 signal，加入复制该引用的等待期反例；分别记录取得引用的位置、准备/授权消费与原请求后续结果。核对信号与可信 agent/session/binding/本次派发的关联、跨 step 复用及失败/取消后的残留；对象相同本身不是授权。拿不到引用也须由真实访问边界证明。
- 未产生准备、prepare 拒绝/取消后残留、合法完成后的重放、缺 ID、冒用 excluded ID、改变 route，以及 direct/prepared/回落路径分别拒绝；保留合法非保护诊断请求对照。
- 授权绑定具体调用与已接受回执，不能仅凭公开标记、Object.freeze、自报 ID 或相同 digest 授权。签发、消费、失效与 outstanding 清理分别观察；底层 mock 只记录，不代替门执行拒绝。
- 无权调用不能污染 H03 raw/normalized/parsed/prose。scope 扇出特征实验在未装 veto middleware 的对照中运行，避免把“前一监听器拒绝”误读成“scope 隔离”。

若公开接口仍无法闭合，交合法/冒用对照、准确断点和最小所需能力，阻断依赖接线；不改 frozen runtime、私有 helper、全局 loop factory 或后置补绑定。不在无新变化下反复等待测试变绿。

来源证明成立后自行完成 S3–S6 与其余 AT：两次回执等待后最后一次 abort/fence/完整摘要复核；
接受时 detached/deep-frozen 快照含 parts；缺 usage 保持缺失、未知 cap 拒绝、估量版本/来源明确；
next/iterator 创建/throw/break/abort/return/recorder 失败均一次本地终态尝试与有界清理。
AsyncIterator.return 没有通用 AbortSignal 参数，有界等待不等于底层静止；托管进程 waitForExit
用独立信号，仅 true 证明其范围静止。retry/title/compaction/PTC 四项实测关闭。

H03 按 V4 更新捕获/成功对应/恢复路径并保留所有旧反例的语义映射：每条 record 先结构、摘要和
工具对应校验，再比较重复；损坏报自身原因，有效但冲突才 conflicting-records。raw 完整性看该
调用匹配的 block-end，finish 另记；已完成 A 后 B 失败不否定 A，未完成 B 必须 incomplete。
0.2 的合成错误结果不可提交 terminal，也不可代替模型请求结算；正式正文权限不因恢复扩张。

### 第四步：同 child 联合候选与目标基线冻结

1. 在同一真实绑定 child 内接 terminal capture/tool 与 accounting：reserve→dispatch→底层 adapter→terminal→结算→flush→新进程从落盘字节重建。合法 A/B 与裸请求污染反例均使用已证明的共同来源；分套件通过不折抵本项。
2. 新增工具调度失败/结果记录失败/结果未知的恢复对照：会话可继续不等于领域成功；错误结果不提交、不退款、不自动重发。flush 必须有真实 listener 和持久字节，V4 同根格式固定，旧 V3 只读诊断不自动改写。
3. 完整 AT 均有证据后，针对**显式 0.2 候选**运行一次完整 check:compat（沿现有 typecheck→build→stage→test 链，实际候选选择参数由第一步实现）。全部 Node 测试都必须被发现；基础包的局部绿不替代本次全绿。
4. 提交同一 runtime/lock/composition/Node/源码及测试集合/接口文档/build/outputs/staging 身份、逐命令退出码、AT→正反例→节点→日志、未测项、写权释放。QA 冻结读集时停止这些写入；涉及 Python/identity 的检查提前约定短冻结。
5. 窗口三完成独立反例、同 child 联合与受影响 H01/H02 回归后，LEAD 才裁决 0.2 的 Gate-H。通过后登记新开发基线并显式切开发选择器/active compatibility，保留旧 compatibility 副本与 B00 原清单；不升级日常 DSH，不批准 live/默认业务切换。

窗口二证据可追加于 `integrations/dsh/dev/H04_request_evidence.md`，并在
`integrations/dsh/dev/runtime-0.2.0-rc.1/` 保存本迁移的清单与结果。旧证据正文原样保留或另存
带摘要的历史副本，不把旧版本通过数改标到新版本。原审查要求见 [H03/H04 指令](h03_h04_review_directive.md)，版本无关的产品不变量继续有效。

## 实施单元

每单元由owner实施、reviewer独立复核；同一文件只能由一个活动任务写入。下列路径标“拟新增”的当前不存在，不是已有能力。

### B00 · 冻结实际开发输入与差异清单

| 项 | 约定 |
|---|---|
| owner / reviewer | LEAD / QA |
| 前置 / WP | 规划交付被采用后启动 / WP0 |
| 独占编辑范围 | `docs/dsh_execution_20260928/source_inventory.json`（现有）<br>`integrations/dsh/compatibility.json`（B00已创建） |
| 步骤与交付 | 复核0918ee7与当前已跟踪业务字节；区分HEAD、dirty内容、环境脚本、历史回执；冻结实际DSH包树/lock/Node、模型配置来源和新增组成身份目录。compatibility.json是待新增交付，不伪造npm快照的源码SHA。 |
| 验收 AT-B00 | 任一代码、bundle构建、实际运行包或配置变化均能定位；0918ee7回执保持历史身份；源树或身份不可用时拒绝称为准入。 |
| 待形成测试/证据 | `baseline_identity_inventory` |

B00 的实际观测、独立复核及放行状态见 [基线冻结交接](b00_baseline_freeze.md)，任务状态以
[台账](task_board.json) 为准；此处任务卡定义验收条件，不以历史规划状态覆盖实际执行记录。

### B01 · 准备合法正例与旧路径特征测试

| 项 | 约定 |
|---|---|
| owner / reviewer | QA / LEAD |
| 前置 / WP | B00 / WP0 |
| 独占编辑范围 | `tests/integrations/dsh/fixtures/`（已新增）<br>`tests/integrations/dsh/test_legacy_characterization.py`（已新增）<br>`tests/integrations/__init__.py`、`tests/integrations/dsh/__init__.py`（LEAD 纳入本任务的包标记） |
| 步骤与交付 | 用真实编译器/请求builder建立一个已完成Formalizer且冻结Narrative的Unified V2页、作者无atom页与非法反例；证据含可读exact excerpt和逐句claim映射。保存真实parser/assessor/Binder行为，不构造第二分页器。 |
| 验收 AT-B01 | 正例可通过其声明的局部门，反例具名拒绝；其中公式正例必须由原 Formalizer parser/validator 产生非空 accepted package 与完成事实，再供真实 Writer 页和请求消费，不能只构造义务或手填 accepted。旧夹具Verified为空不能当作新桥已正确验证的证据；数据不含凭据或项目答案硬编码到生产逻辑。 |
| 待形成测试/证据 | `test_legacy_characterization.py` |

### B02 · 扩展隔离环境与独立构建工具链

| 项 | 约定 |
|---|---|
| owner / reviewer | ENV / QA |
| 前置 / WP | B00 / WP0 |
| 独占编辑范围 | `scripts/dsh_dev.py`、`scripts/dsh_dev_smoke.py`、`integrations/dsh/dev/`、`integrations/dsh/package.json`、`integrations/dsh/package-lock.json`、`integrations/dsh/tsconfig.json`（均现有）<br>`integrations/dsh/compatibility.0.2.0-rc.1.json`（拟新增）；候选运行产物仅写本文件规定的新根 |
| 步骤与交付 | 复用现有隔离器/工具链，增加显式0.2候选选择；精确安装并锁定runtime、Node和独立开发依赖，构建与staging另根，重验固定mock组成和peer解析。保留旧runtime/manifest/日常安装；日常保护区分用户升级与开发越界。冻结runtime不安装开发依赖，留明确可写run root；完整输入与拒绝证据见本文件第一步。 |
| 验收 AT-B02 | 可重复build/typecheck，正常Web入口仍工作；日常home/安装及 frozen runtime 在子进程内只读，HOME不重设，无全局安装/原runtime覆盖；错误组成、runtime/bundle漂移、API key继承、保留端口和无bubblewrap均拒绝。测试发现覆盖工具链及未来业务测试，缺失业务测试目录不导致空跑通过；worker/Node 测试入口同样清理继承环境并使用隔离，不受 PIP_TARGET/PREFIX/配置等重定向；mock 禁止外网及真实 provider。 |
| 待形成测试/证据 | `development_environment_isolation` |

### H01 · 真实 Loader、目标版本 preset 和作用域

| 项 | 约定 |
|---|---|
| owner / reviewer | DSH / QA |
| 前置 / WP | B02 / WP2 |
| 独占编辑范围 | `integrations/dsh/src/index.ts`、`integrations/dsh/src/task-tools.ts`、`integrations/dsh/cordis.patch.yml`、`integrations/dsh/presets/`、`integrations/dsh/tests/loader.test.ts`、`integrations/dsh/dev/README.md`<br>`integrations/dsh/package.json`、`integrations/dsh/package-lock.json`（窗口二与 B02 串行修改目标 peer，重验解析）<br>新版证据放 `integrations/dsh/dev/runtime-0.2.0-rc.1/`；旧 H01 证据只读保留 |
| 步骤与交付 | 用显式0.2.0-rc.1候选Loader加载本地bundle；适配单数preset声明和preset registry，在create.setup中await mount；旧目录扫描机制仅保留历史证据。Host service与preset工具分层；核验named exports/inject、resolved peer路径、销毁。 root setup await mount，child同步composeFrom继承同一standing generation；公开applyChildComposition可复用。 |
| 验收 AT-H01 | 根/child真实composition与工具集合符合合同；缺包/inject、重复服务、坏Config、default export丢metadata均明确失败；兄弟/日常会话无任务状态泄漏；不借上游未安装testkit。 父preset文件变化后child不能重新mount新generation造成父子组成漂移。重复服务与越域发布分别验证；通过正式工具入口核对实际preset身份及未join拒绝。测试只读消费共享profile/staging，变更夹具位于本轮唯一run目录，失败不得污染其他运行或吞掉清理错误。 |
| 待形成测试/证据 | `loader.test.ts` |

旧 0.1.5 的 H01 已通过，两遍独立 QA 与原 H02 放行见 [历史验收](h01_acceptance.md)；新版 H01 待复验。

### H02 · 首个prompt与请求前可信绑定

| 项 | 约定 |
|---|---|
| owner / reviewer | DSH / QA |
| 前置 / WP | H01 / WP2 |
| 独占编辑范围 | `integrations/dsh/src/session-binding.ts`、`integrations/dsh/src/role-dispatch.ts`、`integrations/dsh/src/request-contract.ts`、`integrations/dsh/tests/binding.test.ts`（旧版已验收，新版适配复验）<br>`docs/dsh_execution_20260928/h02_interface_freeze_020.md`（拟新增；旧冻结记录只读） |
| 步骤与交付 | 受控claim recorder只模拟本阶段权威回执，先回执后创建；持久接线归R01–R03。沿用已证明的窄provider与公开agents.create({setup})，不因新版agent/created变为awaited serial就改回stock spawn或后置补绑；保留loop factory并重验真实时序。交新版真实导出/类型、四方法request recorder、可编译生命周期示例、资源责任，owner版本化候选供H03/H04持续实施，QA/LEAD在阶段验收时独立冻结。 |
| 验收 AT-H02 | 故意阻塞绑定RPC时材料读取与adapter调用均为零；伪造prompt task ID、未绑定child、旧fence、创建取消均拒绝。旧父绑定在省略hint或提交当前hint时仍拒绝，provider覆盖（含仅仿冒协议标签）不能启动未绑定child；合法注册须匹配本Host/provider对象/绑定归属，真实导出类型与消费者一致。不在start返回后补绑，不import私有attachStructuredRuntime，不替换全局factory。 |
| 待形成测试/证据 | `binding.test.ts` |

旧 0.1.5 的 AT-H02 已通过，接口 `0ba7f1ce…` 和 [旧验收](h02_acceptance.md) 保留原身份；新版接口另交 `h02_interface_freeze_020.md`，本批次未冻结。

### H03 · terminal schema、原始来源和持久化

| 项 | 约定 |
|---|---|
| owner / reviewer | DSH / QA |
| 前置 / WP | H02 / WP2 |
| 独占编辑范围 | `integrations/dsh/src/terminal-result.ts`（候选）<br>`integrations/dsh/tests/terminal.test.ts`（候选）<br>`integrations/dsh/tests/provenance.test.ts`（候选）<br>`integrations/dsh/dev/H03_terminal_evidence.md`（本单元证据，已纳入写权） |
| 步骤与交付 | 验证object根包装result.oneOf的DSH schema子集与Python完整模型；若不可用明确冻结等义adapter。捕获arguments delta流、normalized terminal、parsed/prose各自来源；await sessions.flush并核查持久listener，child释放前留存。fallback provider单独实现并验证terminal终止/guard。 本spike使用最小schema/来源fixture，不能声称C01领域模型已实现；C01/C03另验Python完整结果模型。 |
| 验收 AT-H03 | 成功terminal可重建；closing text、双terminal、坏schema、错误参数、terminal后工具不能提交；空白/转义/键序原文与JSON.stringify不同仍正确溯源；缺raw不冒充取得；捕获后重启从落盘字节恢复。新版另验V4工具成功对应、0.2合成错误结果不得提交；与H04在同一真实绑定child内共享可信来源，冒用请求不得污染来源。 |
| 待形成测试/证据 | `terminal.test.ts provenance.test.ts` |

### H04 · 真实LLM seam与取消能力探针

| 项 | 约定 |
|---|---|
| owner / reviewer | DSH / QA |
| 前置 / WP | H02 / WP2 |
| 独占编辑范围 | `integrations/dsh/src/request-accounting.ts`（实施中，含必要的自有路由门）<br>`integrations/dsh/tests/request-seam.test.ts`（实施中）<br>`integrations/dsh/tests/cancellation.test.ts`（实施中） |
| 批次证据 | `integrations/dsh/dev/H04_request_evidence.md`（现有，追加新版索引并保留旧记录）；新版详细证据放 `integrations/dsh/dev/runtime-0.2.0-rc.1/` |
| 步骤与交付 | 消费H02本地验证并版本化的绑定和最小request recorder类型（独立冻结在阶段QA完成），不等待C/R生产RPC；真实loop配无网络mock adapter，验证llm/stream、prepared配置/单次dispatch及闭包。区分标记与冻结、prepared与direct通路；完整装配摘要含messages/tools，等待后重算并证明next前后不漂移，不冒充最终wire。逐一排除retry/title/compaction/PTC；验证cancel/dispose/whenIdle与subprocess.waitForExit。 |
| 验收 AT-H04 | 同一prepared二次dispatch或配置漂移被拒；reserve拒绝/等待时零dispatch，错配回执及messages/tools/config漂移不能发给adapter；direct/prepared捕获的stream/NO_ADAPTER回落均不得绕门。合法准备和两等待点期间的同ID同摘要裸请求不能抢占授权，合法A/B仍成功且恰计一次。裸API特征与受保护loop分别留证；next/adapter不冒充HTTP送达，生产持久性归R02/R03。abort后仍运行不能报quiescent，unknown不退款；waitForExit独立有界，仅true证明其范围静止。 |
| 待形成测试/证据 | `request-seam.test.ts cancellation.test.ts` |

## 验证、交接与完成门

以下为验收入口；实际已运行范围、输出及退出码另记验收记录。新增任务测试落地后按上表AT逐项登记实际节点/断言，不可只登记文件名。

```bash
python -m pytest -q tests/regression_20260917/test_execution_identity.py
npm --prefix integrations/dsh run check:compat
git diff --check
```

上列 npm 命令是原入口名，实施时必须使用窗口二交付并实测的**显式候选选择**，不能默认落回旧 runtime。check:compat 顺序保持 typecheck→build→stage→test；test:compat 只验证已有候选 staging 并拒绝漂移，不自动重封。Node 测试经隔离 launcher，不在日常 profile 启动。新增 Python/Node 测试仍落既有目录，修原 owner 的反例扩已有测试，不复制实现。

交接包包含任务ID、目标runtime与包/锁/组成身份、接口/存储版本、全部源码测试清单、真实接线与准确命令/退出码/日志、未测项及写权释放。独立 QA 按 [verification.md](verification.md) 复核；新 Gate-B 要求历史 B00/B01 合法证据、新候选身份清单与新版 B02，新 Gate-H 要求同一目标的 H01–H04。旧 [Gate-B](b01_b02_acceptance.md)、[H01](h01_acceptance.md)、[H02](h02_acceptance.md) 通过保持历史范围，不批准 0.2。

[返回总执行入口](README.md)
