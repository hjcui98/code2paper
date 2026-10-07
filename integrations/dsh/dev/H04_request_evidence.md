# H04 请求计量批次：联合接线与交接证据

> 批次：窗口二统一接管 H03/H04 实现与共享构建（[第 01 份“当前交付批次”](../../../docs/dsh_execution_20260928/01_baseline_and_dsh_compatibility.md)）。
> 本文件是 H04 的批次证据与交接记录；H03 历史证据见 [H03_terminal_evidence.md](H03_terminal_evidence.md)。
> **状态：进行中。** 联合基线已建立，H04 仍有 S1/S3–S6、路由门与同 child 联合接线未收口；
> AT-H03/AT-H04 均未成立，Gate-H 未通过。

## 1. 本批次受测输入身份

| 对象 | SHA-256 |
|---|---|
| `src/terminal-result.ts`（H03） | `3fcc5e9927eb0ca9ff1425b5a0cb33cc6ffa3dfa7e3a2f6838199d71b016cdea` |
| `tests/terminal.test.ts`（H03） | `86bb93ad4a1ccd2ac64afced6e6860e41f93e0ed9c1a4919ca6f1c8932191ccd` |
| `tests/provenance.test.ts`（H03） | `d7c0cc137bab1f9da7ac205cf9d8c7962ccc09ef369f8adb5d76aad8c6ac786d` |
| `src/request-accounting.ts`（H04） | `1a7733478539bc47…`（授权门 + signal 绑定准备；上一身份 `22886cef…`） |
| `tests/request-seam.test.ts`（H04） | `d1aa14a14723d997…`（S1 重做 + S2 授权门；上一身份 `54943fd9…`） |
| `tests/cancellation.test.ts`（H04） | `3897620486a52a510d8617bdd85510666bd10abdee54a048d343a1c321afd335` |
| H02 消费输入（只读） | `session-binding 404f7984…`、`role-dispatch c8758e10…`、`request-contract d133fc43…` |

构建（本次统一构建，7 个 `src_inputs` 与上表一致）：

| 项 | 值 |
|---|---|
| build receipt | `7eade607cccfcac436d0f68620dd0b8f948cdf5d87c0298be6666bb137e71e1e` |
| outputs digest | `030521bf386ea7ffd73a10e9ab8ed2e9426eefa477bc40ddc73aa282e2137f17` |
| staging receipt | `c4b759427ed5948909baf9fddd4c59e850894637cead7b1307d2c2ea6348bb37` |
| staged 树 / 文件数 | `e97b48a81344f3653c5e085604fb9043697db1946561831fafd72fb9368c1a76` / 18 |

## 2. 联合基线：同一 build/staging 下四套件实测

命令（隔离 launcher，逐文件）：

```text
python scripts/dsh_dev.py test -- <abs>/integrations/dsh/tests/<file>.test.ts
```

| 套件 | 结果 |
|---|---|
| `terminal.test.ts`（H03） | **8 / 8 pass** |
| `provenance.test.ts`（H03） | **13 / 13 pass** |
| `request-seam.test.ts`（H04） | **6 / 6 pass**（含 S1 重做与 S2 授权门） |
| `cancellation.test.ts`（H04） | **6 / 6 pass** |
| 合计 | **33 / 33**，exit 0 |

`npm --prefix integrations/dsh run typecheck` exit 0（全树，含 H01/H02/H03/H04）。

这证明同一构建产物下两套件互不干扰，**不**证明同一真实绑定 child 内的联合接线（见 §5）。

## 3. H04 已闭合项

| 编号 | 行为 | 证据节点 |
|---|---|---|
| C0 正常对照 | 真实绑定 child → `reserve → dispatch → adapter → settle(settled)`，adapter 恰好 1 次 | `cancellation.test.ts::C0` |
| §2.1 路由归因 | `agentOptions` 确实透传（`childOptions` 记录到 mock provider/model），H02 无缺陷 | `C0` 的 `DIAG` 记录 |
| S7-fixture | `refuseWith('')` 真正清除；reserve **进入 barrier** 后再取消；C2 见证真实拒绝 | `C1`、`C2` |
| 回执快照 | 接受时逐字段复制并冻结；等待期间改写原回执不替换依据 | `request-seam.test.ts::R-receipt`（3 项） |
| 摘要覆盖 | `messages`/`tools`/`config` 封闭覆盖，未知键 `contract-unsupported` | `request-seam.test.ts::R-cap` |
| **S1（重做，结论已改）** | 三个**同时存活**的绑定 child 下：A、B 都观测到兄弟 C 的派发；裸请求（冒用 A 的 session id）被 A/B/C 全部观测；root 观测一切。**该 seam 上没有任何 scope 隔离** | `request-seam.test.ts::S1` |
| 取消/清理 | 阻塞取消零派发零结算；终态记录失败具名 `unsettled` 不重试 | `C1`、`C4` |
| 资源范围 | adapter 观测为 oracle；无托管子进程记具名 N/A + 清单 | `C5` |

## 4. H04 未闭合项（本批次继续）

| 编号 | 缺口 |
|---|---|
| S1-B | 冒用 **excluded ID** 与**缺失 ID** 两类仍待单列（现存 protected ID 已由 S2 覆盖） |
| ~~§2.2 路由门~~ **已闭合** | 见 §6：授权门覆盖 direct 与 prepared 两条通路；来源由 loop 的 `agent/request` 信号对象身份绑定 |
| S3 | `dispatch` 等待后再做 abort/fence/摘要复核；两个等待点各布置反例 |
| S4 | finalize 覆盖 next 抛错/迭代器创建失败/break/abort；`inner.return()` 独立有界，超时 ≠ 底层已停 |
| S5 | 去掉 `?? 0`；stop 无 usage 保持缺失；估量器版本/来源与有效 cap 校验 |
| S6 | `digest.parts` 冻结；dispatch 传 detached 快照；`acceptDispatch` 自校验 |
| 矩阵 | prepared/direct/回落、四项禁用（retry/title/compaction/PTC）、资源 enter 与 exit 计数 |
| 联合接线 | terminal capture/tool 与 accounting 装入**同一**真实绑定 child |
| 可信来源 | capture 与 accounting 消费可验证的 Host 绑定/派发来源；裸请求冒用现存 child ID/同 callId 不得污染 terminal |

## 5. 边界声明

1. **同 child 联合接线尚未证明**：§2 的 32/32 是两套件在同一构建下各自通过，不是同一 child 内的共同工作证据。
0. **scope 隔离结论已撤回并改正**：本 seam（`llm/stream` 由 LlmRuntime 在 root context 上发射）**不提供任何 Cordis 上下文隔离**；注册点不能作为调用来源证明。初版“delegated child 隔离”是已销毁 child 造成的假象。
2. **未做 live**：全程 offline，无真实模型、无外网；mock adapter 只记录事实，拒绝逻辑在 middleware 内。
3. **recorder 是本阶段夹具**：不构成 durable balance；生产账本仍由 R02/R03 接线复验。
4. **可信来源未闭合**：`GenerateOptions.sessionId` 可由请求自报，且 scope 无隔离；来源证明只能由 Host 自有路由上的 adapter 门闭合（§4 §2.2 行），当前未实现。
5. **staging 守卫**：输入变动后必须重建；不得在移动输入上验收。


## 6. 优先复现与修复（0.2 迁移批次的前置）

### 6.1 `prepareCall()` 绕过门 —— 已复现并修复

LEAD 的假设成立。原 `gatedAdapter.prepareCall()` **直接返回底层 prepared call**，而拒绝逻辑只在
wrapper 的 `stream` 上；loop 走 `preparedCall.stream(request)`，因此门从未被进入：底层 adapter
被调用，`authorized:` 诊断缺失。这正是 `request-seam.test.ts::S2` 在“the gate authorized it”
中止的原因。

修复：`prepareCall` 现在 `await` 底层 prepared call，**保留其 `model`（registration/model
generation）**，但把它的 `stream` 换成经过同一 `gate()` 的入口；`gate()` 统一负责授权消费、
拒绝与诊断。direct 与 prepared 不再有差别。

### 6.2 裸请求抢占合法准备 —— 已复现并修复

原实现按 `sessionId` 记准备计数，裸请求复制 A 的 sessionId/route/完整装配即可
**消费掉 A 的准备**并取得授权，A 随后被拒——即“偷走准备”。

修复：准备改为按 **loop 自己的 `agent/request` 信号对象**（`WeakSet<AbortSignal>`）记录与消费。
裸请求可以复制 session id、route、messages、tools、config 与 digest，但**无法取得 loop 的 signal
对象**，因此既不能冒领也不能偷取；一次准备只允许一次派发。

### 6.3 S2 四类攻击的实测结论（全部具名拒绝）

| 攻击 | 结果 |
|---|---|
| 合法绑定 child | 授权签发 → 门消费 → 底层 adapter 恰好一次 → `reserve/dispatch/settle` |
| 冒用身份（裸请求复制存活 child 的 session id） | `dispatch_origin_unproven`，底层 adapter 0 次 |
| 复制摘要 | 材料不同 ⇒ 重算摘要不匹配 ⇒ 无授权 |
| 重放 | 授权已消费 ⇒ 拒绝，`outstanding` 归零 |
| 改 route | `protected_route_mismatch`，不能借换 provider 退出计量 |

### 6.4 未完成（迁移批次）

0.2.0-rc.1 候选安装（`.dsh-dev/candidates/0.2.0-rc.1/`）、H01 preset 适配、H02 创建时序复验、
H03 Session V3→V4、S3–S6、同 child 联合接线均**未开始**。本轮的 33/33 绑定 0.1.5-rc.3 旧候选，
不是 0.2 候选证据。

## 7. 历史记录：第九轮早期 92/24 快照（2026-10-03）

对应 2026-10-02 22:10 Gate-H 静态入口审查提出的 GHS-1～4 四项问题：

1. **GHS-1 闭环（受信派发身份不能被公开参数声明）**：
   - 彻底移除 `streamWithRegistration` 的公开布尔参数 `trustedLoopDispatch`；公开流入口无条件在存活来源下执行清空式隔离。
   - 受信派发入口严格收拢至 `AgentLoop` 内部通过静态模块导入调用的 `runLoopDispatch(options, preparedCall, capability)`，并通过模块私有 WeakMap `privateLoopDispatchers.get(runtime)` 获取私有派发器。
   - 解决 Cordis / resolver 转发 Proxy 导致的实例身份失配：在 `LlmRuntime` 构造器挂载模块私有 Symbol `kRootRuntime`，引入 `unwrapRuntime` 穿透任何 Proxy 包装，使 `preparedRecord.runtime` 与 `runLoopDispatch` 解析严格锚定于原始真实 `LlmRuntime` 实例。
   - 回归探针：C24（公开布尔参数与未授权调用拒绝）、C25（全链路成员被 resolver Proxy 包装时的安全隔离与合法派发完成）。
2. **GHS-2 闭环（注册表生命周期注销与多 deployment 语义）**：
   - 在 `LlmRuntime` 构造器中通过 `this.ctx.effect` 挂载销毁钩子，在 deployment / fiber dispose 时从 `loopDispatchRuntimes` 与 `privateLoopDispatchers` 自动注销。
   - 明确多 deployment 存活语义：prepared 派发按 prepare 时的 runtime 实例严格归属隔离派发；直接 fallback 回落因缺乏唯一 runtime 归属严格 fail-closed。
   - 回归探针：C26（验证销毁注销、双 deployment 下 fallback fail-closed 以及销毁恢复后单 deployment 的完整派发能力）。
3. **GHS-3 闭环（types 来源与全文身份）**：
   - 交付候选与 `-built` 候选中的 `.d.ts` 声明文件均来自源码真实 `tsc -p ... --emitDeclarationOnly` 编译输出。
   - `dsh-llm/lib/types/index.d.ts`（SHA-256 `320517790cd...`）、`dsh-agent-loop/lib/types/index.d.ts`（`a3509f051...`）与 `dispatch-origin.c2p.d.ts`（`baadf7575...`）逐字节 100% 对齐。
4. **GHS-4 闭环（源码构建侧 B02：LEAD 默认裁定）**：
   - 遵照 LEAD 裁决，`-built` 候选声明范围明确收窄为“源码等价证据”（JS/types 严格一致、92/92 测试全通），明确标注“不声称 B02/doctor”。
5. **套件实测结果**：
   - `cancellation.test.ts` 29/29 pass（C0～C26 全部通过）。
   - 交付候选 `0.2.0-rc.1+loop-origin.1`：`check:compat` **92/92 pass**（0 fail, 0 skip），B02 **24 passed**，`doctor` exit 0。
   - 源码构建候选 `0.2.0-rc.1+loop-origin.1-built`：`check:compat` **92/92 pass**（0 fail, 0 skip）。


> 历史范围纠正（2026-10-03）：上述 92/24 和旧 build/stage hash 是早期快照，不能引用后来覆盖为 93/26 的 round9 日志证明；原早期日志完整绑定不可恢复。本批当前交付以 gate_h_repair_batch_20261003.md 及其新封存输入为准。独立验收已保留 93/93、26 和来源/生命周期成果；Gate-H 仍待复验。
