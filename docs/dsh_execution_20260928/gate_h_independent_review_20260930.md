# 0.2 完整候选独立 QA · CHANGES_REQUESTED

日期：2026-09-30（Asia/Shanghai）。本报告只读审查窗口二候选，不修改产品、锁、peer、build/stage、接口、owner证据或LEAD台账，不登记正式Gate。

**结论：Gate-H 不具备通过条件。** 原71项Node独立复验通过、组成身份匹配；另外独立反例实际证明H03损坏日志仍能被接受/抛异常，H04公开来源票据能被抢占且合法兄弟被误拒，清理同步异常遗漏具名终态。B02真实CLI还进入历史workspace，普通Web未就绪。以下PASS是行为/组件证据，不能替代全部AT或正式Gate。

## 1. 冻结身份与运行

- 仓库 `/home/cuihengjia/agent/Code2Paper copy`，分支 `codex/agentic-p4-benchmark-cutover`，HEAD `d48b4e4b22c94c82b45d2179ba452d72b164102d`；保留dirty tree。
- QA根 `/home/cuihengjia/agent/Code2Paper copy/.dsh-dev/candidates/0.2.0-rc.1/run/qa-gate-h-3fohojpy`；报告/原始日志 `/tmp/c2p-gate-h-independent-20260930-zny3hfyo`。
- before.json冻结2618项源码/测试/scripts/integrations、声明合同、锁、worker、实际lib/build-receipt、profile/stage及peer链接（含inode/mtime）。目标runtime另外同算法inventory：26149项。
- 实算目标树 `43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c`；旧default `7e8f199b67027944d646e0c99f5041d4704360377e4d7466fce683c1d468d3ab`。兼容清单9项声明源码hash全部匹配；stage --check树 `8870372bd53182d043c208c264342860d12a457d68e7760832ed0b05264d1c80`，Node v25.8.2，peer仍指目标runtime。
- 独立运行 `npm --prefix integrations/dsh run test:compat`（显式两个候选env），不是会build/stage的check:compat。11个TS测试文件，71 pass/0 fail/0 skip，exit0，63.43s。原完整check:compat的build/typecheck只核回执/source/outputs身份，未重复构建。
- 首次外层sandbox无法建bwrap网络命名空间，exit1，保留test-compat.log；宿主授权后仍走原只读、断网bwrap，test-compat-escalated.log/.exit=0。无裸跑降级。

| 独立运行 | 真退出码 | 观测 |
|---|---:|---|
| test-compat-escalated | 0 | 71/71，含H01/H02、terminal、来源、取消、联合新进程 |
| strict-reader-probe | 0 | 探针完成；H03多个负向合同实际失败，见F1 |
| public-initiator-probe | 1 | QA夹具重复注册adapter导致before hook失败；不是产品缺陷；原日志保留 |
| public-initiator-probe-v2 | 0 | 修正仅QA夹具后，公开来源抢票实际成立，见F2 |
| accounting-edge-probe | 0 | 两等待点完整材料复制均拒绝/合法请求各成功；双child交错计量成立；实际清理分类失败，见F4 |
| overlap-preparation-probe | 0 | 合法B被正在准备的A误拒，见F3 |
| b02-candidate-pytest | 1 | 当前B02 Python原矩阵20 pass/2 fail；两项是候选夹具/API假设未迁移，见F5 |
| doctor-readonly | 0 | doctor(evidence=False)，没有覆盖owner的evidence；runtime、staging、worker/import就绪，日常比较applicable=false |
| web-readonly | 1 | 原smoke40秒未就绪、无startup输出；已terminate/wait，原因未定 |
| compat-readonly | 0 | 真CLI HTTP200、四资源200、端口关闭，模型turn0 |

所有命令、sandbox argv在同名.command.json，退出码在.exit。**探针exit0是观察与控制完成，不表示其负向产品合同通过。** QA探针只引用冻结staged模块、原helper/fixture、公开Host API；没有复制生产状态机、手发授权或改runtime。新鲜损坏日志使用同一个合法reader控制和原生产digest函数。

## 2. 必修发现

### F1 · H03 reader 未严格验证事件/成功事实（阻断）

`integrations/dsh/src/terminal-result.ts:779–807,819–821`。

冻结staged `rebuildTerminal` 的合法V4控制为committed；`isError:true`布尔对照为unresolved/no-successful-tool-result。然而相同控制的损坏变体：

- 新增 `tool/call data=null`：直接TypeError读取callId；未返回具名unresolved。
- V4 `message.isError='true'` 或1：仍committed。
- V4 `message.content=null`：仍committed。
- `data.error.code={broken:true}`：仍committed。

因为tool/call先cast后访问；V4仅将字面true解释成失败，未验证消息字段/错误结构。损坏成功事实可提升terminal，违反逐条结构验证/严格拒绝/reader不抛异常原要求。合法V4、V3版本分派、两种真实synthetic代码拒绝和现有record完整性测试继续保留有效。

证据：strict-reader-probe.log/.exit、QA根strict-reader-probe.mjs。需原terminal owner完整校验已消费结构并保持unknown/synthetic不可成功，再重验多record/来源/真实新进程联合。

### F2 · H04 公开withInitiator被当成派发授权（阻断）

`integrations/dsh/src/request-accounting.ts:304–348,378–383`；公开API说明：目标 `dsh-agent/lib/types/index.d.ts:230–241`。

攻击者能力明确为：可以监听公开`agent/request`并调用Host公开`agents`/`llm`服务的扩展。不是任意改进程/源码、不是读取私有WeakMap、不是伪造claim/直接issue授权。真实公共事件提供exact Agent对象和signal；`agents.withInitiator`自身的文档说明presence不是liveness/authorization，只是公开driver归属边界。

真实合法child已触发agent/request并在adapter.prepareCall等待；waterfall已返回。此时上述扩展：

1. 持公共事件的同Agent、同signal、同session，调用公开 `agents.withInitiator(agent, ()=>ctx.llm.stream(bareOptions))`。
2. bareOptions使用不同未授权messages，gate实际允许到观察型adapter；得到reserve→dispatch→settle(settled)，adapterDelta=1。
3. 放开合法prepare后原合法child stopReason=error，diag来源未证明，原请求没再到adapter。

Preparation未绑定真实装配/本次可信派发，且currentInitiator可由公开setter建立；信号票据被裸请求先消费。若设计排除此类公开调用者，需要提供可执行的组成权限依据；当前源码和交付没有这样的限制，不能假定setter是秘密。

证据：public-initiator-probe-v2.log的QA_ORIGIN/QA_LEGAL_AFTER；同名.exit0。修复不得弱化原裸请求/同signal门或修改frozen runtime/私有helper，须在原公开Host入口闭合可信来源再重验三种等待期。

### F3 · H04 全局requestDepth误拒合法兄弟（阻断）

`integrations/dsh/src/request-accounting.ts:317,334–340`。

两个合法绑定child同时存活：A的公开agent/request waterfall暂时阻塞；此时启动B。B自己的preparation已经正常返回，但全局requestDepth仍为1：B直接来源拒绝，stopReason=error、adapterDelta=0、recorder=[]。放A后A正常completed并R/D/S各一次。

这不是来源攻击；是合法并行被跨child准备深度误拒。原C9先放A再创建B，不能折抵该反例。独立双child同时停在reserve的对照确实通过R(A),R(B),D(A),D(B),S,S，说明缺陷特指preparation重叠边界，不能抹掉已有交错通过。

证据：overlap-preparation-probe.log/.exit0；accounting-edge-probe.log的QA_DUAL正对照。

### F4 · H04 同步iterator.return异常遗漏具名终态（必修）

`integrations/dsh/src/request-accounting.ts:71–80,546–565`。

`boundedIteratorReturn`在try之前直接执行return()，同步throw会reject而不是返回'threw'。独立实际accounting节点也复现（不仅helper）：合法child过真实gated adapter且收到finish/usage；公开downstream middleware保持next来源，仅其iterator.return同步throw。child最终stopReason=error，但recorder已R/D/S(settled)，diagnostics=[]；没有iterator-return-threw/具名unsettled。

证据：strict-reader-probe.log最后一行、accounting-edge-probe.log的QA_CLEANUP。需在原owner保护同步call与异步reject/timeout，并厘清结算尝试与cleanup失败的终态；仍不得把250ms截止说成底层静止。

### F5 · B02 CLI候选cwd未传递，原Python矩阵尚未迁移（必修）

`scripts/dsh_dev.py:454,467–474`。

`sandbox_command(...,cwd=WORKSPACE)`的默认参数在模块加载时固定。select_candidate(0.2)后，真实 `command()` argv的--chdir仍为 `/home/cuihengjia/agent/Code2Paper copy/.dsh-dev/workspace`，预期为 `/home/cuihengjia/agent/Code2Paper copy/.dsh-dev/candidates/0.2.0-rc.1/workspace`。Node test传了显式package cwd所以71项不检测此问题。

`cli-selection.json`保存真实argv及两值。普通web-readonly.log还观测40秒没有就绪；compat同方式成功。Web失败原因未定，不将cwd问题推断为它唯一根因，不扩大timeout/重跑碰运气。

B02原Python矩阵以select_candidate在导入测试前选择实际目标，exit1：

- test_frozen_runtime_has_no_development_dependencies：npm-candidate `verify_original_installation`返回applicable=false、不含shared_inodes，旧测试假设KeyError。
- test_non_cli_runtime_drift_is_refused_before_launch：旧夹具只切DEV，不切DEV_ROOT，读取真实目标manifest使错误为runtime lock drift，期待runtime bytes drifted不匹配。

这两项为测试/API适配缺口，不是已证权限绕过；不可删测试/吞错。原71项TS发现不包含这两个Python文件。doctor的日常比较applicable=false表明没有日常安装比较快照；只读mount行为通过，但不能声称已做日常前后hash/无共享inode证明。按原保护合同诚实建立未来可比较身份/范围，不倒填安装前证据、不重装日常环境。

## 3. 原AT矩阵与有效证据

| AT | 独立结论 | 实际节点/局部证据及限制 |
|---|---|---|
| AT-B02 | CHANGES_REQUESTED | runtime/lock/tree/peer/build/stage/worker匹配；selector不一致拒绝、凭据/Python注入清理、只读runtime/src、独立lo断网、保留端口/无bwrap/漂移纯函数对照有效；真实compat HTTP有效。CLI cwd、普通Web未就绪与Python矩阵缺口见F5；日常hash比较未证明。 |
| AT-H01 | 现有行为独立复验通过；不替代完整阶段PASS | 10 Loader案例：真实声明/ToolRuntime/父子standing generation、新root换代、override、非join拒绝、兄弟ledger、坏Config/metadata/inject、服务越域/重复/销毁；原shared profile/stage保护断言有效。后来的真实CLI smoke引发两profile mtime副作用，见§4，不宣称全批metadata不变。 |
| AT-H02 | 现有行为独立复验通过；Gate仍阻断 | 11 binding案例，claim阻塞时零材料/adapter/创建，setup内绑定首发布、旧parent有/无hint拒绝、provider对象归属和仿冒tag、stale fence/创建取消/生命周期、真实四方法消费者。新版source与builder receipt匹配；独立没有重复typecheck。 |
| AT-H03 | CHANGES_REQUESTED | 8 terminal +14 provenance +同child共同来源/flush/新进程有效；raw调用完成/finish分开、缺raw显式not_observed、V4/V3分派及两synthetic拒绝有效。F1损坏结构/成功事实违反strict fail-closed。 |
| AT-H04 | CHANGES_REQUESTED | 6 seam +10 cancellation保留；独立补全材料同signal在reserve/dispatch等待期拒绝并放行原请求、两个child真计量交错；两次等待后recheck、缺usage、250mstimeout及一次settle尝试现有对照有效。F2抢票、F3合法兄弟误拒、F4cleanup同步异常阻断。 |
| 同child联合 | 合法路径独立通过；完整Gate联合待返修 | 真实绑定child reserve→dispatch→adapter→terminal→settle→flush→header-version新进程committed；completed后的bare请求不改raw/terminal ID；synthetic未知结果变unresolved。未覆盖F2中真实等待期来源污染；不能用联合合法例覆盖F1–F4。 |
| 组成/资源 | 有效局部证据，完整H04收口待返修 | 新版包inventory、profile whitelist与network rows、断网connection failure；code2paper preset只声明其工具，与standard roster分开。PTC/compaction/retry/title的全部原禁止行为需完整映射真实active scoped组成/请求；包存在和patch文本不单独等于运行关闭。托管子进程未由当前probe启动，waitForExit适用范围诚实N/A，不借AgentHandle.dispose证明全局静止。 |

未执行：live/真实provider、C/R/F产品RPC/全文事务、下一阶段Wire/tokenizer/领域验证、default业务切换。上述不是本阶段可用来免除AT的理由。本批不构建、不stage、不修改interfaces/compatibility/owner报告，不登记task done或Gate。

## 4. after、验证副作用与读集释放

after.json在2026-09-30T18:56:23+08实算：源码/测试/锁/peer/worker/lib/build-receipt/staging、两个runtime完整字节及链接未变。2618项的字节与inode保持，**只有两个候选profile cordis.yml的mtime改变**，字节sha均仍 `c300dcf2ebc5f02062d6591268d29d3db6fe45e0cb138f5467276fe2ba06076e`。这是本QA真实CLI smoke对已有候选profile的startup副作用；严格metadata冻结口径不能称完全一致。前后清单保留，没有恢复mtime来掩盖副作用。此处需LEAD按实际字节输入和场景裁决；独立反例的staged/source/runtime字节身份仍一致。

closing_process_check.json：2026-09-30T18:58:07+08宿主own-user121进程只读审计，精确QA根/目标实际CLI匹配0、不可读0；所有由本QA启动的subprocess已wait返回，Web未就绪进程已terminate并wait。该范围不宣称无LEAD自己的Python验证进程，没有对其他窗口发信号。

**本批独立QA到此结束。释放before.json所列本QA读集，停止Node/pytest/CLI与所有后续读取；无待写缓冲区或常驻等待。** 新鲜QA输出根也不再写入。是否返修、冻结新候选及台账/Gate登记均由LEAD协调。历史证据/首次失败不覆盖。Release登记时间：2026-09-30T19:01:54.377634+08:00。
