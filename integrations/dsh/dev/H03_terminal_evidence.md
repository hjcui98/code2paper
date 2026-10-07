# H03 · terminal、原始参数来源、flush 与重启恢复（证据与交接）

> 2026-09-28 窗口一实施记录。依据 [H02 最终验收与 H03/H04 并行指令](../../../docs/dsh_execution_20260928/h02_acceptance.md)
> §3 与 [第 01 部分 H03 任务卡](../../../docs/dsh_execution_20260928/01_baseline_and_dsh_compatibility.md)。
> 状态以台账为准；本文件只登记本轮实际观测。

| 项 | 值 |
|---|---|
| 任务 / 验收 | H03 / AT-H03（`terminal.test.ts` `provenance.test.ts`） |
| owner / reviewer | DSH / QA（窗口三独立复核） |
| 前置 | H01、H02（均 done，接口 frozen） |
| 授权 | offline_implementation；无 live、无 Git 提交、未改冻结 runtime/日常 DSH |
| 独占文件（§6.2 收口轮，**未构建**） | `src/terminal-result.ts` `3fcc5e9927eb0ca9ff1425b5a0cb33cc6ffa3dfa7e3a2f6838199d71b016cdea`<br>`tests/terminal.test.ts` `86bb93ad4a1ccd2ac64afced6e6860e41f93e0ed9c1a4919ca6f1c8932191ccd`<br>`tests/provenance.test.ts` `d7c0cc137bab1f9da7ac205cf9d8c7962ccc09ef369f8adb5d76aad8c6ac786d` |
| 共享构建 / staging | **未由本窗口重建**：`lib/build-receipt.json` 仍为 `026f81e3…`、`.dsh-dev/staging.json` 仍为 `7009bee8…`（staged 树 `f2175e64…`）。按指令 §7.4，下一轮唯一 build/stage 写者是窗口二；正式聚焦套件须在其构建后的交接窗口运行 |
| 历史身份 | 首轮 `b8084ba8…`/`a98b75d7…`/`d63a4d84…`/回执 `3fa4c2e5…`/`55ab7e28…`/`bf2cb46c…`/`f441dbf3…`；修复轮 `c4a2d98b…`/`99b8b5b4…`/回执 `026f81e3…`/`2e66ab2e…`/`7009bee8…`/`f2175e64…`（窗口三 `H03_verification.json`、修复轮报告分别绑定） |
| package / lock | `165d4452…` / `6a747c1d…`（本轮未改，无新增 peer） |
| 冻结 runtime | DSH `0.1.5-rc.3`，树 `7e8f199b67027944d646e0c99f5041d4704360377e4d7466fce683c1d468d3ab` |

## 1. 真实调用路径

```text
scripted no-network LlmAdapter (H03 fallback provider)
  └─ llm/stream waterfall ──▶ TerminalArgumentCapture.observe()   # 原样透传并记录 tool-call-delta
        ▼
  agent loop（真实）──▶ tools registry 校验参数（object 根 + result.oneOf）
        ▼
  c2p_terminal.execute()（真实工具体）──▶ 暂存 parsed + exec.concludeTurn()
        ▼
  tools/result（权威成功）──▶ 读取 session 的 tool/call 归一化参数 + 本轮 prose
        ▼
  session.append('c2p/terminal', record)   # 落盘来源
        ▼
  await sessionPersistence.flush() ──▶ session.v3.jsonl（本 run 私有根）
        ▼
  新进程只读该文件字节 ──▶ rebuildTerminal(events) ──▶ 同一 record
```

只经公开 API 接入：`llm.registerAdapter`、`llm/stream` waterfall、`ctx.tools.register/guard`、
`tools/result`、`session.append`、`sessionPersistence.flush/stat`。**未替换 loop factory、未改
冻结 runtime、未导入私有 helper。**

## 2. 来源分类（互不冒充）

| 来源 | 字段 | 实际取得方式 | 摘要 |
|---|---|---|---|
| provider raw（arguments delta 流） | `rawArguments` | `llm/stream` 的 `tool-call-delta` 文本，按到达顺序原样拼接 | `digestText(raw)`，附 `chunks`/`byteLength`；未观测则 `state:'not_observed'`（无 digest/text） |
| normalized terminal arguments | `normalizedArguments` | session 自己的 `tool/call.arguments`（adapter 可在 `toolcall_end` 重新序列化） | 单独 `digestText`；**不得**当作 raw |
| parsed 领域对象 | `parsed` / `parsedDigest` | 工具体收到的已校验 `result` | `digestJson`（键序无关的规范 JSON） |
| prose | `prose` | 同轮 `assistant/message` 文本块 | 单独 `digestText`，附块数 |

`terminal.test.ts` 的 fixture 故意让 adapter 在 `block-end` 用 `JSON.stringify` 归一化：raw
（含空白、`\u0021` 转义、非规范键序）与 normalized 文本、digest 均不同，且 raw digest ≠
`JSON.stringify(parsed)` 的 digest（测试断言）。

## 3. AT-H03 逐条对照

| 验收条款 | 实际观测（测试节点） |
|---|---|
| 成功 terminal 可重建 | `a successful terminal commits with separated sources and survives a restart`：record 落盘，`parsed.kind='draft'`，重启消费者从字节重建出同 digest 的 record |
| closing text 不能提交 | `closing text alone does not commit a terminal`：纯文本回复 → 无 record，rebuild `absent` |
| 双 terminal 不能提交 | `a second terminal in one response does not commit and is refused`：同一响应两个调用 → 仅 1 条 record，第二次 `terminal-already-recorded` 具名拒绝 |
| 坏 schema / 错误参数不能提交 | `a bad schema or wrong arguments never commits`：缺 `draft.body` 的调用被 registry 拒绝，无 record，rebuild `unresolved`（不从调用参数或 closing text 重建） |
| terminal 后工具不能提交 | `a tool call after the terminal is refused and cannot commit`：后续轮次再调用被单调 guard 拒绝，原 record 不变、无第二条 |
| 空白/转义/键序原文与 `JSON.stringify` 不同仍正确溯源 | `provenance.test.ts`：raw 原样保留、digest 与 normalized/parsed 均不同；两种写法（空白/转义/键序）raw digest 不同而 parsed 规范 digest 相同 |
| 缺 raw 不冒充取得 | `an unobserved raw source stays explicitly missing`：`not_observed` 且无 `digest`/`text` 字段；`terminal.test.ts` 的失败路径与 rebuild 同样保持缺失 |
| 捕获后重启从落盘字节恢复 | 见 §4 |
| fallback provider 的终止/guard | `the fallback path without an adapter produces no terminal`：未注册 adapter 的 provider 路由不产生任何 terminal；脚本化 adapter 单次应答 + `concludeTurn()` 使轮次终止（非一次性脚本会因脚本耗尽而显式报错，探针阶段已实测该循环风险） |
| schema 子集（object 根 + `result.oneOf`） | `the terminal schema keeps the union and its per-branch constraints`：3 分支、每支 `additionalProperties:false`、`kind` 与 `result` 均 required，且经真实 `defineTool` 校验通过 |

## 4. 持久化与重启恢复证据

- `await sessionPersistence.flush()`（真实后端），`stat(sessionId).sizeBytes > 0`。
- artifact：`<privateRoot>/sessions/<project>/<sessionId>/session.v3.jsonl`（本 run 私有根，未压缩）；
  字节中存在 `c2p/terminal` 记录。
- **重启**：`spawnSync(node --input-type=module -e …)` 新进程只读该文件，按行解析事件后调用
  staging 里的 `rebuildTerminal()`；输出与内存 record 的 `parsedDigest`/`rawDigest`/`normalizedDigest`
  逐字一致（测试断言），`state='committed'`、`rawState='captured'`。

**为什么用私有根 + `compression:'none'`**：共享 `$DSH_HOME/sessions` 已是 zstd 模式，后端会拒绝
同一根下混用压缩模式（实测报错 `uses .jsonl.zstd, but this backend is configured for compression
"none"`）。因此本 run 用私有根并显式不压缩：既是真实后端与真实格式，也让重启消费者能读取确切字节。
共享 sessions 根未被本单元写入（`find` 无 `h03-*` 会话）。

## 5. 命令与退出码

| # | 命令 | 退出码 | 结果 |
|---|---|---|---|
| 1 | `python scripts/dsh_dev.py test -- …/terminal.test.ts …/provenance.test.ts`（修复轮后） | 0 | **15/15**（7 terminal + 8 provenance）；首轮为 12/12，见 §6 |
| 2 | `npm --prefix integrations/dsh run typecheck` | 0 | 无诊断 |
| 3 | `npm --prefix integrations/dsh run build` | 0 | `outputs_digest 55ab7e28…` |
| 4 | `python scripts/dsh_dev.py stage` | 0 | staged 树 18 文件 |
| 5 | `npm --prefix integrations/dsh run check:compat`（含窗口二在写的 H04 输入） | **1** | 49 项中 **45 pass / 4 fail**；4 项失败全部属于 H04 的 `cancellation.test.ts`/`request-seam.test.ts`（C1/C3/C4/C5，窗口二在写），H03 的 12 项与 H01/H02 全部通过 |
| 6 | `python scripts/dsh_dev.py doctor --evidence` | 0 | runtime 树未变、只读边界成立 |
| 7 | `python -m pytest -q integrations/dsh/dev/tests/` | 0 | 22 passed |
| 8 | `python scripts/dsh_dev_smoke.py --composition compat` | 0 | 真实 CLI compat 入口正常 |
| 9 | `python -m pytest -q tests/regression_20260917/test_execution_identity.py` / `git diff --check` | 0 / 0 | 24 passed / 无空白问题 |

日志：`.dsh-dev/run/h02-logs/h03-tests.log`（12/12）、`h03-terminal.log`、`h03-check.log`（完整门）、`h03-verify.log`。

## 6. 复核修复轮（R-H03-1 / R-H03-2）

窗口三独立复核提出两项具名阻断，本轮在 H03 三个文件内修复，并各补反例测试：

| 发现 | 修前实测 | 修后行为与测试 |
|---|---|---|
| **R-H03-1a** 同一 call id 跨流被拼接 | 两次不同调用复用同一 id → `chunks=2`，text 被拼成 `{"result":{"kind":"draft"{"result":{"kind":"blocked"` | 捕获改为按 `(streamIndex, callId)` 建条目，`raw()` 只取**最近一条流**的条目并回报 `streamIndex`；测试 `a reused call id in a later stream does not merge two sources` 断言 text 等于第二条、`chunks=1`、长度不等于两段之和 |
| **R-H03-1b** 中途失败的流仍报 `captured`，无完整性标记 | 1 个 delta 后抛错 → `state=captured`（键含 text/digest/byteLength） | 新增 `incomplete` 状态：流抛错或消费者提前结束（`break`）时，其条目带**部分文本 + digest + reason** 明确标为不完整；只有正常结束的流才是 `captured`。测试 `a stream that fails or is abandoned yields an explicitly incomplete source` 覆盖抛错、提前 break、正常完成三种 |
| **R-H03-2** `rebuildTerminal()` 不校验取回的记录 | 版本错/缺字段/摘要矛盾/两条冲突/无对应调用 均返回 `committed`；冲突记录静默取最后一条 | 重建改为**校验**：schema 版本、必需字段、逐项重算 `parsed`/`normalized`/`prose`/`raw` 摘要、重复记录必须一致（否则 `conflicting-records`，不再 last-one-wins）、必须存在匹配的 `c2p_terminal` `tool/call` **且其 `tool/result` 成功**。`unresolved` 增加稳定 `reasonCode`（`schema-version-mismatch`/`record-missing-field`/`digest-mismatch`/`conflicting-records`/`no-matching-tool-call`/`no-successful-tool-result`/`terminal-call-without-record`）。测试 `the rebuild validates a stored record instead of trusting it` 逐条覆盖 + 一致记录的成功对照 |

修复后：`python scripts/dsh_dev.py test -- …/terminal.test.ts …/provenance.test.ts` → **15/15，exit 0**
（7 terminal + 8 provenance），日志 `.dsh-dev/run/h02-logs/h03-fixes.log`。

## 8. §6.2 剩余边界收口轮（R-H03-1a/1b、2a/2b/2c）

按指令 §7.2 的顺序（先 2b → 2a → 2c，再 1b，最后 1a 与真实消费接线）在同一三个文件内收口。
**共享 build/stage 未由本窗口执行**（§7.4 指定窗口二为唯一写者）；下表“修后”列为私有编译
（`tsc --outDir .dsh-dev/run/h03-private/bundle/lib`，只写本 run 私有目录，未触碰 `lib/` 与
staging）上的预验证结果，正式证据在窗口二构建后的交接窗口复跑。

### 8.1 接口变化（H03 自有，未改 H02）

| 变化 | 说明 |
|---|---|
| `RawArguments` 新增 `ambiguous` | 同一 call id 命中多条流且未指明流时，列出 `candidates`，**不再猜最近一条** |
| `ObservedRawArguments` 增 `streamIndex`/`sessionId` | 来源可归属到具体流与会话 |
| `raw(callId, lookup?)` | `lookup: { sessionId?, streamIndex? }`：按**可信会话**过滤，或显式指定流；不再接受裸 reason 字符串 |
| `observe(chunks, ref?)` / `install()` | 从 `llm/stream` 的 `GenerateOptions.sessionId` 取会话身份；per-call 完成事实为**该调用的 `block-end`** |
| `TerminalRebuildReason` 扩展 | 新增 `record-malformed`/`parsed-invalid`/`raw-source-invalid`/`schema-digest-mismatch`/`arguments-mismatch`/`parsed-mismatch`/`ambiguous-call` |
| 提交端 | `capture.raw(exec.callId, { sessionId: session.id })` —— 捕获端与消费者持有同一可信会话引用 |

### 8.2 §6.2 逐条对照（修前 → 修后）

| 编号 | 修前观测 | 修后行为与测试 |
|---|---|---|
| R-H03-2b 表示与字段校验 | `normalized=null` 抛 TypeError；坏 `schemaDigest`/raw 状态/union、缺 `terminalId` 仍 committed；成功夹具用 `schemaDigest:'z'` | **先结构后取字段**：非对象→`record-malformed`；缺身份字段→`record-missing-field`；非法 union→`parsed-invalid`；非法 raw 状态/字段→`raw-source-invalid`；缺摘要字段→`record-missing-field`，摘要不符→`digest-mismatch`；`schemaDigest` 必须等于真实参数 schema 摘要→否则 `schema-digest-mismatch`。测试 `the rebuild refuses damaged structure by name and never throws`（null/非对象/空 id/负 turn/normalized=null/prose=null/raw=null/非法状态/错摘要/非 union/自洽但错 union）+ 真实摘要成功对照 |
| R-H03-2a 成功与对应关系 | 仅按 callId 匹配、以 `data.error` 缺失当成功；`isError:true` 仍 committed；turn/step、参数对应未验 | 成功判据改为 **tool-result block 的 `isError`**；要求同 id **且 turn/step 相符**的 `c2p_terminal` 调用（多义→`ambiguous-call`）；`normalized` 必须等于该调用日志文本（`arguments-mismatch`）；`parsed` 必须等于该调用 arguments 内 `result` 的语义值（`parsed-mismatch`，只比规范摘要，不比字节）。测试 `the rebuild attributes the record to a real successful call`（isError:true 无 error 元数据、错 turn、参数不同、同 id 同 turn 双调用、无调用） |
| R-H03-2c 每条记录均验证 | 只比首条的 `terminalId`/`parsedDigest`，其余字段不同的第二条被忽略 | **每条先校验**（损坏记录报自己的码），再判重复：完全相同→幂等接受；任一字段（raw/normalized/prose/callId/turn/step）不同→`conflicting-records`。测试 `the rebuild validates every record and treats disagreement as a conflict` |
| R-H03-1b 协议完整性 | `completed=true` 仅表示迭代正常结束；真实 adapter 抛错被 runtime 归一化后仍 `captured` | 完整性判据改为**该调用自身的 `block-end`**：有它即 `captured`（后续别的调用失败不回溯否定）；无它则 `incomplete` 并给出原因（流失败／归一化 error/aborted finish／消费者放弃／截断流）。测试：`completeness is the call's own completion fact, not iterator completion`（六种变体）+ **真实注册 adapter** 中途抛错 `a real adapter failing mid-arguments yields an incomplete raw source, never captured` |
| R-H03-1a 调用与流归属 | 存储已按 `(streamIndex, callId)` 拆开，但 `raw()` 仍取最近流；提交端只传 `exec.callId` | 捕获端记录每条流的**可信会话**（`llm/stream` 的 `sessionId`）与 per-call 完成事实；消费者以自身 session 查询。同 id 的 A/B 会话各自取回自身来源（交错流 + 延迟读取），未指明流且命中多条→`ambiguous`（列 candidates），指明会话但无命中→`not_observed`。测试 `attribution follows the trusted session, and an unattributable id is ambiguous` |

### 8.3 私有预验证结果

| 命令（私有，非共享构建） | 退出码 | 结果 |
|---|---|---|
| `tsc --project dev/toolchain/tsconfig.build.json --outDir .dsh-dev/run/h03-private/bundle/lib` | 0 | 私有编译，`lib/` 与 staging 未动 |
| `node --test --test-concurrency=1 dev/h03-private/{terminal,provenance}.test.ts` | 0 | **21/21**（8 terminal + 13 provenance），日志 `.dsh-dev/run/h02-logs/h03-private-all.log` |
| `npm --prefix integrations/dsh run typecheck` | 0 | 交付源码的真实类型检查 |

私有测试副本（`dev/h03-private/`）与私有 bundle 仅为预验证而建，交付前已删除测试副本；
私有 bundle 位于 `.dsh-dev/run/h03-private/`，不参与共享身份。

### 8.4 交付与待办

1. 本窗口只写 H03 三个源码/测试文件与本文档；`package.json`/lock、H01/H02、preset、冻结
   runtime 未动（package/lock 摘要仍为 `165d4452…`/`6a747c1d…`）。
2. **共享 build/stage 交窗口二**：构建前双方暂停受测输入写入；构建后按交接窗口跑各自聚焦
   套件（H03 21 项）并登记新的 build/outputs/staging 身份。
3. 未变体仍未测：真实 `abort` 信号下的 per-call 完整性（单元矩阵已覆盖 `finish(aborted)` 与
   消费者放弃两条路径，真实取消路径属 H04 的取消矩阵）；zstd 共享根的重启读取仍为声明边界。

## 9. 边界与未决

1. **最小 fixture，不是领域模型**：`TerminalResult` 只是 H03 的三分支表示；完整
   `WriterTaskResultV1`、Python parser/assessor、生产 ingest 仍归 C01/C03。
2. **工具尚未接入 preset**：本单元按 owned paths 只在测试中把 `c2p_terminal` 装进 agent scope
   （`installTerminalTool`）。把它作为 preset 行接入 H01 的 `task-tools.ts`/`presets/` 属共享路径改动，
   按 H02 验收指令 §2 需 LEAD 分配写权后再做（影响 H01 冻结文件与构建身份）。
3. **adapter 是 H03 的 fallback provider**：脚本化、无网络，不是 H04 的请求计量 seam；真实
   `llm/stream → next → adapter` 的计量与取消由 H04 证明。
4. **prose 仅取同轮 assistant 文本**：未做 authorship/span 映射（属 C02/C03）。
5. **未测 zstd 根上的重启读取**：本单元用私有未压缩根；生产默认压缩下的读取走同一
   `sessionPersistence.open(...,'read')` 公共 reader（本单元只用 `stat`/`flush` 与文件字节）。
