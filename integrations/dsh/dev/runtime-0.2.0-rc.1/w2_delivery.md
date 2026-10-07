# 窗口二 0.2 阶段交付包

提交给独立 QA 的候选。本文不登记 Gate-H、不改 LEAD 台账、不把 71/71 写成阶段 PASS。

## 身份

- 分支 `codex/agentic-p4-benchmark-cutover`，HEAD `d48b4e4b22c94c82b45d2179ba452d72b164102d`
- 候选 `.dsh-dev/candidates/0.2.0-rc.1`
- runtime 树 `43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c`，doctor `bytes_match=true`
- peer 指向该候选的 `@deepseek-ai`
- 默认 `.dsh-dev/runtime` 仍是 `0.1.5-rc.3` / `7e8f199b…`
- 目标 pyworker：`.dsh-dev/candidates/0.2.0-rc.1/pyworker`，锁内 6 个包，`import code2paper` 成功
- 日志根：`.dsh-dev/candidates/0.2.0-rc.1/run/w2-020-20260930-175449/`

## 命令与退出码

| 日志 | 结果 |
|---|---|
| `check-compat.log` | 首次完整链 exit 1。工具链测试仍写死旧 `.dsh-dev/home` 与 `.dsh-dev/runtime`，5 项失败。已保留。 |
| `doctor.log` 被成功轮覆盖前 | 首次 doctor exit 1：`KeyError: source_installation`。npm 候选没有日常快照字段。 |
| `check-compat-final.log` | `check:compat` exit 0。typecheck、build、`stage --candidate 0.2.0-rc.1`、`stage --check`、11 个测试文件、71 pass / 0 fail。 |
| `doctor.log` | 修复后 doctor `--evidence` exit 0。runtime 字节匹配，compat 组成就绪，pyworker 在目标根。 |
| `pyworker-setup.log` | exit 0。pip 缓存警告指向不可写的默认缓存，缓存被禁用，没有写入。随后 `PIP_CACHE_DIR` 改到候选根。 |

最终链的每个 Python 子节点 argv 都带 `--candidate 0.2.0-rc.1`，并且 `C2P_DSH_DEV_ROOT` 与 `C2P_DSH_CANDIDATE` 不一致时 launcher 拒绝。

## AT → 节点

| AT | 真实节点 | 日志中的测试 |
|---|---|---|
| AT-B02 | 候选传递、错配拒绝、隔离 home、只读 runtime、断网、pyworker | `candidate-selection.test.ts`，`sandbox.test.ts`，`composition.test.ts`，doctor |
| AT-H01 | 声明式 preset、root/child、销毁、未 join 拒绝 | `loader.test.ts` 10 项，含在 71 项里 |
| AT-H02 | 先 claim 后创建、伪造 task、旧 fence、创建取消、awaited 创建 | `binding.test.ts` 11 项 |
| AT-H03 | V4 独立 tool 消息、V3 显式版本、来源、完整性、flush、新进程 | `terminal.test.ts`，`provenance.test.ts`，`joint-child.test.ts` |
| AT-H04 | 两 child 计量、准备期公开 signal、dispatch 等待期 fence、缺 usage、有界 return、prepared/direct 门 | `cancellation.test.ts` C0–C9，`request-seam.test.ts` S1/S2 |

同 child 联合：`joint-child.test.ts` 在一个真实绑定 child 上完成 reserve → dispatch → adapter → terminal commit → settle → flush → 新进程按 header.version 重建。裸请求不改已提交来源。追加的 `TOOL_OUTCOME_UNKNOWN` 使重建变为 unresolved。

## 组成

候选树里有 provider（`dsh-llm-deepseek` / `dsh-llm-pi-ai`）、title、retry、compaction、PTC、OTel、schedule。profile 白名单仍只有 base、web-app 和本 bundle。`offline.patch.yml` 关闭 llm-deepseek、llm-pi-ai、llm-retry、session-title-llm、session-telemetry-otel、web-search、web-fetch。没有 desktop 包。schedule 在树里，不在 base 依赖里。launcher 内对 `1.1.1.1:443` 的连接失败。

## 写权

上一轮交付后的写权释放已被本轮返修接回。本轮结束后再次释放 TS、peer、工具链、build、stage 和目标候选根写权。不改 LEAD 台账，不登记 Gate-H。

## 2026-10-01 第四轮（H-R4 后 FAIL-CLOSED + 接口裁决申请）

本批 QA 重放确认：H-R1 相关对照可关闭；**H-R4 仍成立**——公开 `llm.prepareCall` 可取得 claiming 闭包（自有材料 R/D/S 各一次、合法 child error），证明"返回闭包"不证明调用者是 loop；`awaiting-prepare` 状态可被最外层 `agent/request` listener 的延迟续延窃取。

**处置**：prepareCall 不再武装、不再铸造任何 claiming closure；中间件 FAIL-CLOSED——受保护会话的一切分发具名拒绝（诊断 `no loop preparation for this request signal`，chunk `dispatch_origin_unproven`），公开 `llm.stream` 对 owned ticket 的一切直连分发在 listener/adapter 前拒绝。合法 child 与攻击者同闭：零 reserve、零 adapter、child 不完成。

**裁决申请**：`docs/dsh_execution_20260928/h04_loop_origin_escalation_20261001.md`——真实调用链（prepared/回落/窃取）、逐项排除的公开凭据、最小接口差异（runtime 私有 loop-origin ALS + 公开 `llm.stream` 退出标记 + loop 内部回落入口）及备选（维持 FAIL-CLOSED 并登记 R02 阻塞）。已停止一切时序/状态/材料类来源补丁。

验证（`w2-r2-20260930-224211/`）：

| 项 | 结果 |
|---|---|
| cancellation | 21 项：8 pass / 13 skip（具名原因=等待裁决）/ 0 fail。C0 fail-closed 控制；C9/C10/C13/C14/C14b 保留攻击拒绝与 fail-closed 断言 |
| joint-child | 同一真实绑定 child：seam/adapter/terminal 全闭、具名拒绝、flush 后新进程重建 `absent` |
| request-seam | S1 扇出、R-receipt、R-cap 不变；S2 合法 child 与冒充同拒 |
| 五文件聚焦 | 37 pass / 13 skip / 0 fail |
| 最终链 | `check:compat` exit 0（**71 pass / 0 fail / 13 skip**）；B02 dev 目录 23 passed；doctor `--evidence` exit 0 |

身份：`request-accounting.ts` `9c671806…`，build receipt `0c06c8f1…`，staging tree `6d1b6003…`，outputs `2a27b7b9…`。`_020` 已同步为 FAIL-CLOSED 合同 + 裁决指针。13 项 skip 是等待接口裁决的受影响 AT（等待期矩阵、取消、清理、usage 估量），不是通过。

## 写权

本轮结束后再次释放 TS、peer、工具链、build、stage 和目标候选根写权。不改 LEAD 台账，不登记 Gate-H。恢复派发能力需 LEAD 对 `h04_loop_origin_escalation_20261001.md` 裁决。

## 2026-10-01 第三轮（回落认领移入 prepareCall 返回值闭包；已被 H-R4 推翻，机制移除）

LEAD 指令：首个调用、微任务顺序、provider/model、signal、摘要、公开 setter 都不能作为授权；停止堆叠时序补丁。上一轮的回落认领依赖"fallback-ready 后第一个材料匹配的 `llm.stream`"——正是时序+材料授权，已废除。

**新机制**：owned `prepareCall` 捕获 NO_ADAPTER 后不再向 loop 抛出，而是通过**本调用返回值**交给 loop 一个 fallback handle（`config` = proposedConfig，`stream` 闭包花费同一次 claim）。loop 对它的使用形状与 prepared 完全一致；真正的适配器缺失在 `adapterStream` 按原名失败。公开扩展调用 `llm.prepareCall` 得到的是原样 NO_ADAPTER（C14b 实测），拿不到 claiming handle。公开 `llm.stream` 上，owned ticket 的一切直连分发一律拒绝。

不需要向 LEAD 提交接口差异裁决：`llm.prepareCall` 是公开服务方法，包装其返回语义在 owner 责任域内，未改 frozen runtime、未削弱门。若 LEAD 认定"中间件替换 prepareCall 返回语义"本身需要裁决，差异点仅此一处，已在 `_020` §派发来源合同单列。

复现与对照（`w2-r2-20260930-224211/`，`cancel13.log` 21/21）：

| 项 | 结果 |
|---|---|
| prepared 认领复现（QA public-request-alias） | C13：listener 持真实 request 对象重入 → 拒绝；合法 child R/D/S 各一次 |
| 回落认领复现（QA public-fallback） | C14：listener 持 Agent/signal，经 `withInitiator` 以完整复制与不同材料重入 → 均拒绝；延迟重放拒绝；合法回落完成、恰计一次 |
| handle 不可获取 | C14b：扩展 `llm.prepareCall` 原样 NO_ADAPTER；真缺适配器时 child 具名失败、零 adapter 模拟、无成功结算 |
| 合法 A/B / 公开调用零 adapter | C9（A/B 各 R/D/S 一次）、C13/C14（公开调用 0 adapter） |
| 等待/取消/清理 | C10、C11、C15–C18、C6、C12、C12b 全绿 |
| H03 + 持久恢复 | strict reader、flush 失败、部分落盘、新进程按 header.version 重建（provenance/terminal/joint 52/52） |
| 最终链 | `check:compat` exit 0（**84 pass / 0 fail**，含 C14b）；B02 dev 目录 23 passed；doctor `--evidence` exit 0 |

身份：`request-accounting.ts` `a5b209db…`，build receipt `17272dc4…`，staging tree `3dba363b…`，outputs `10a3248e…`。`_020` 已同步（回落合同 + 状态机不可达性论证 + 唯一可能的裁决差异点）。

## 写权

本轮结束后再次释放 TS、peer、工具链、build、stage 和目标候选根写权。不改 LEAD 台账，不登记 Gate-H。

## 2026-09-30 第二轮（H-R1/H-R2 等待期来源 + 原 AT 收口）

日志根：`.dsh-dev/candidates/0.2.0-rc.1/run/w2-r2-20260930-224211/`。身份：`request-accounting.ts` `c2da50e2…`，build receipt `599a8d79…`，staging tree `32fad720…`，outputs `7731232f…`。

| 项 | 结果 |
|---|---|
| H-R1 同 request 引用重入 | 复现为 C13。一次性 dispatch claim 只在公开调用者到不了的闭合位置花费（prepared 闭包 / fallback wrapper）；accounting listener 只接受 `dispatched` 且 request 对象一致的请求。重入、延迟重放、同 signal 裸请求全部在进入 listener/adapter 前拒绝 |
| H-R2 NO_ADAPTER 回落抢票 | 复现为 C14。fallback claim 单次、绑定 prepared config 的 provider/model；full copy、不同 messages、延迟重放均拒绝；合法回落仍完成且恰计一次 |
| 等待期矩阵 | C15 结算等待期材料漂移（runtime 冻结 messages，原地漂移不是外部能力）、C16 dispatch 等待期 abort、C17 reserve 等待期 fence、C6 dispatch 等待期 fence、C18 cap 未建立拒绝、C10/C11 准备期公开 setter 与兄弟重叠、C9 双 child 交错 |
| 清理/结算终态 | C12 真实链同步 return 抛错→`iterator-return-threw` 诊断 + 不重复结算；C12b 异步拒绝 + 迭代异常（runtime 归一化 finish-error → 一次 `unfinished` 结算）；C8 250ms 截止 |
| H03 | 严格读取（null 事件/损坏 tool-call/非布尔 isError/null content/坏 error identity 全具名拒绝）、flush 失败对照、部分落盘 → 具名 unresolved/committed 分界、新进程按 header.version 重建 |
| 组成 | `config` dump 证据：`llm-deepseek`/`llm-pi-ai`/`llm-retry`/`session-title-llm`/`session-telemetry-otel`/`compaction-basic`/`command-compact`/`workflow-ptc` 均 `disabled: true`；无 schedule bundle、无 desktop 包；mock 白名单与断网在 83 项内 |
| 最终链 | `check:compat` exit 0（83 pass / 0 fail）；B02 原 dev 目录 pytest 23 passed；doctor `--evidence` exit 0，runtime 字节匹配 |

`_020` 接口候选已重写：完整导出清单、活跃 binding 生命周期示例、资源责任、纠正后的派发来源合同（不再引用 `currentInitiator` 作为授权），并如实声明残余边界（fallback claim 窗口、非 gated adapter 场景、H03 schema 覆盖范围）。

## 写权

本轮结束后再次释放 TS、peer、工具链、build、stage 和目标候选根写权。不改 LEAD 台账，不登记 Gate-H。

## 2026-09-30 独立 QA 返修（第一轮，保留）

日志根：`.dsh-dev/candidates/0.2.0-rc.1/run/w2-repair-20260930-195254/`。

| 项 | 结果 |
|---|---|
| F1 损坏 tool/call、非布尔 isError、null content、坏 error | 具名 unresolved，不再抛异常或当成成功 |
| F2 公开 withInitiator + 不同材料 | 准备等待期不能抢走票据；原请求仍派发一次 |
| F3 全局 requestDepth | 已去掉。A 停在准备时 B 仍成功，之后 A 也成功 |
| F4 同步 `return()` | helper 返回 `threw`；真实链结算一次，并留下 `iterator-return-threw` |
| F5 CLI cwd | `sandbox_command` 在调用时读取当前 workspace。候选 chdir 已落到 `.../0.2.0-rc.1/workspace` |
| B02 pytest | 20 passed，exit 0。npm 候选无安装前 hash，`hash_compared=false`，并核对当前无共享 inode、日常路径不在可写候选根内 |
| check:compat | 74 pass / 0 fail，exit 0 |

普通 Web：QA 当时的 argv 把 `--chdir` 指到历史 `.dsh-dev/workspace`，40 秒没有 stdout。cwd 修好后 8 秒内第一段输出是 profile 目录的 HMR `ENOSPC`（file watchers 用尽），随后仍打出 `dsh web:`。这个 watcher 警告不是就绪失败本身；40 秒空日志的首个可观察断点是错误工作目录下的进程一直活着且没有就绪行。没有加大 timeout。日志：`web-ready-after-cwd.log`。

当前 web `config` 里实际 `disabled: true` 的相关行包括 `llm-deepseek`、`llm-pi-ai`、`llm-retry`、`session-title-llm`、`session-telemetry-otel`、`compaction-basic`、`command-compact`、`workflow-ptc`。`image-offload` 出现在 dump 中且该行没有 disabled。没有 schedule bundle；desktop 只是账号配置里的平台判断，不是已装 desktop 包。mock 白名单和断网测试仍在 74 项里。托管子进程的 `waitForExit` 仍是 N/A。

## 历史记录：2026-10-03 第九轮早期 92/24 快照

依据 2026-10-02 22:10 Gate-H 静态入口审查报告与 README §3.15 指令：

### 1. 四项问题修复

- **GHS-1（受信派发身份不能被公开参数声明）**：
  - 彻底移除 `streamWithRegistration` 的公开布尔参数 `trustedLoopDispatch`；公开流入口无条件在存活来源下执行清空式隔离。
  - 受信派发入口严格收拢至 `AgentLoop` 内部通过静态模块导入调用的 `runLoopDispatch(options, preparedCall, capability)`，并通过模块私有 WeakMap `privateLoopDispatchers.get(runtime)` 获取私有派发器。
  - 穿透 Cordis / resolver 转发 Proxy：在 `LlmRuntime` 构造器挂载模块私有 Symbol `kRootRuntime`，引入 `unwrapRuntime` 穿透任何 Proxy 包装，使 `preparedRecord.runtime` 与 `runLoopDispatch` 解析严格锚定于原始真实 `LlmRuntime` 实例。
  - 回归探针：**C24**（测试公开布尔控制、公开方法或未授权调用者无法铸造受信派发权）；**C25**（测试 resolver Proxy 包装受信路径涉及的全部成员时，无法截获或铸造派发权，且合法 child 正确完成）。
- **GHS-2（注册表生命周期跟随 deployment 销毁注销）**：
  - 在 `LlmRuntime` 构造器中通过 `this.ctx.effect` 挂载销毁生命周期钩子，在 deployment / fiber dispose 时自动从 `loopDispatchRuntimes` 与 `privateLoopDispatchers` 注销。
  - 销毁 Deployment A、新建 Deployment B 后，Deployment B 的 prepared 派发与 NO_ADAPTER 回落派发均正常完成且各计 1 次。
  - 两个 deployment 同时存活时的明确语义：prepared 派发按 prepare 时的 runtime 实例严格归属绑定派发，绝不跨 deployment 串号；无 prepared 记录的直接回落（fallback）因缺乏唯一 runtime 归属严格 **fail-closed**。
  - 回归探针：**C26**（验证 deployment 销毁后注销、并发双 deployment 下直接回落 fail-closed，以及销毁后恢复单个 deployment 时的完整派发能力）。
- **GHS-3（types 来源与全文身份）**：
  - 交付候选与 `-built` 候选中的 `.d.ts` 声明文件均来自源码真实 `tsc -p ... --emitDeclarationOnly` 编译输出。
  - `dsh-llm/lib/types/index.d.ts`（SHA-256 `320517790cd...`）、`dsh-agent-loop/lib/types/index.d.ts`（`a3509f051...`）与 `dispatch-origin.c2p.d.ts`（`baadf7575...`）在 delivery 候选、`-built` 候选与源码 tsc 独立产物之间逐字节 100% 对齐。
- **GHS-4（源码构建侧 B02：LEAD 默认裁定）**：
  - 遵照 LEAD 裁决，`-built` 候选声明范围明确收窄为“源码等价证据”（JS/types 严格一致、92/92 测试全通），明确标注“不声称 B02/doctor”。

### 2. 身份与测试结果

| 对象 | SHA-256 |
|---|---|
| `integrations/dsh/src/request-accounting.ts` | `efaa899ce0950a317ea0ab90d6581ea9811755980b1c9538c3048242a4ee0453` |
| `integrations/dsh/dev/runtime-0.2.0-rc.1/loop-origin/loop-origin.patch.py` | `b36b887fc71e90de84080897169f79bddf370793a293ca1e54c03fbcb02c8e75` |
| `integrations/dsh/dev/runtime-0.2.0-rc.1/loop-origin/loop-origin-source.patch` | `0db693e794feea78f8087198078df04d41614804898aec329cf5628a45987512` |
| build receipt (`build-receipt.json`) | `c10d1bcaf0ca0a508cda255795609688f3d0824420733baa8cac7ee8fc722285` |
| staging tree | `6f0c39cb850f16abc00cbdbe2a7474463e1b37e1159a31f4887421070f4c7546` |
| runtime tree (`0.2.0-rc.1+loop-origin.1`) | `671daa1a7a06728d69a4bdec6da3d33a3616c4e788f63579ed07f3ae81e0e16c` |
| runtime tree (`0.2.0-rc.1+loop-origin.1-built`) | `3076d2fcdbf6b2b49167e8132ce9b5801d95079a36f9bd05af17302e8482be97` |
| outputs_digest | `9c00688b090ab3bb744ba83975e5ab447fe75fd61798906d15ba13fa4e750e95` |

- **交付候选 `0.2.0-rc.1+loop-origin.1` 实测**：
  - `check:compat`：**92 tests / 92 pass / 0 fail / 0 skipped**（exit 0）。
  - B02 `pytest`：**24 passed in 12.68s**（exit 0）。
  - `doctor`：exit 0（`bytes_match=true`，`compat_composition_ready=true`）。
  - `test_execution_identity.py`：**24 passed in 10.60s**（exit 0）。
  - `git diff --check`：exit 0（干净）。
- **源码构建候选 `0.2.0-rc.1+loop-origin.1-built` 实测**：
  - `check:compat`：**92 tests / 92 pass / 0 fail / 0 skipped**（exit 0）。

### 3. 写权释放

窗口二完成上述返修，封存全套证据至 `.dsh-dev/run/w2-loop-origin-private-20261003-round9/`。
明确释放全部写权（TS、peer、工具链、build、stage、补丁脚本及候选根），不修改 LEAD 台账，不登记 Gate-H PASS，等待独立 QA 复核。


> 历史范围纠正（2026-10-03）：上述 92/24 和旧 build/stage hash 是早期快照，不能引用后来覆盖为 93/26 的 round9 日志证明；原早期日志完整绑定不可恢复。本批当前交付以 gate_h_repair_batch_20261003.md 及其新封存输入为准。独立验收已保留 93/93、26 和来源/生命周期成果；Gate-H 仍待复验。
