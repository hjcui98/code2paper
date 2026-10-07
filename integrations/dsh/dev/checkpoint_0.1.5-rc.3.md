# 旧候选检查点（0.1.5-rc.3）与 0.2.0-rc.1 候选安装记录

> 2026-09-29，窗口二（B02/H01–H04 独占实现、launcher、TS、构建）。
> 本文件保存迁移前的旧候选检查点、S2 首次失败日志，以及新候选的独立安装身份。
> 依据：[第 01 份执行文档](../../../docs/dsh_execution_20260928/01_baseline_and_dsh_compatibility.md) 迁移批次。

## 1. 旧候选检查点（接管时刻，0.1.5-rc.3）

### 1.1 源码与测试集合

| 文件 | SHA-256 |
|---|---|
| `src/index.ts` | `4053ef1095c3753bcd7fda53feb2e2b1768379c20b8a7bdb8b9edded53fe3c65` |
| `src/session-binding.ts` | `404f7984d01b51073a6f8f5941f56c9f594161be563a215f09b4ff2403348952` |
| `src/role-dispatch.ts` | `c8758e10565531f36ca8e3c4732ac919f559209ef9869deeb13fe2a8100999b4` |
| `src/request-contract.ts` | `d133fc43dc58909b7b300c90edc989cdac4cbc233ba46bd0d34fb804bd7341bb` |
| `src/request-accounting.ts` | `1a7733478539bc479d4260584a43323975d3a3f2d49733adfd177ef47701de79` |
| `src/terminal-result.ts` | `3fcc5e9927eb0ca9ff1425b5a0cb33cc6ffa3dfa7e3a2f6838199d71b016cdea` |
| `src/task-tools.ts` | `0ed976fe58e527e1101cc94f4124f18460e65b0fcf4030eed78cd839665a37b9` |
| `tests/binding.test.ts` | `598359297f6e671ee82a3aa451d4513854c8fc4321fd33dc9a2d8039c6be9005` |
| `tests/loader.test.ts` | `4e6e6699864222fc0c18f3d57db0359a804eea131e387151468580d519821c24` |
| `tests/terminal.test.ts` | `86bb93ad4a1ccd2ac64afced6e6860e41f93e0ed9c1a4919ca6f1c8932191ccd` |
| `tests/provenance.test.ts` | `d7c0cc137bab1f9da7ac205cf9d8c7962ccc09ef369f8adb5d76aad8c6ac786d` |
| `tests/request-seam.test.ts` | `d1aa14a14723d997a770c6f0568d57101051726f1a69cdcc53f859a32cb74501` |
| `tests/cancellation.test.ts` | `3897620486a52a510d8617bdd85510666bd10abdee54a048d343a1c321afd335` |

`package.json 165d4452697b42c49a0a8c8cfdd9d43446cce17d04e95059e44f8730ae37d56e`、
`package-lock.json 6a747c1d0f2303042701a487e513b4b145a28833e3b9765ae944a0e99dfc0c55`、
`tsconfig.json 13bc8a14a75a374f15ad1529894c35d0c3900241a8eae294e3dd3f5de181333e`。

### 1.2 构建与 staging

| 项 | 值 |
|---|---|
| build receipt | `767339799e2af92cd407b7dc874615e12ed4b0fe25e8fdacd92ed02ca5f3b652` |
| outputs digest | `77b374ce7c008861dea6953eabc710d8e7334cfa0efb05164229379b4d24a9dd` |
| staging receipt | `b0729c01989d07e2aa8c201db31f586bb092e2a6d46e5aa0591d285b1874432d` |
| staged 树 | `6cb47a5e982020fdf7879c189119e337608e1f2a88a4ee128232145343423206`，18 文件 |

### 1.3 旧 runtime 身份（保持原样，不重封）

`dsh 0.1.5-rc.3`，`.dsh-dev/runtime/node_modules/@deepseek-ai/dsh/package.json`
`e6c20794b703b108de3d2e27c6201d21d76c979b7e153d0812c770dc4f5bb3d8`；
历史树摘要 `7e8f199b67027944d646e0c99f5041d4704360377e4d7466fce683c1d468d3ab`。
本次迁移**未触碰** `.dsh-dev/runtime`（mtime 保持 9 月 27）与 `.dsh-dev/home`，日常安装未动。

### 1.4 移交时的行为基线（旧候选，绑定上文身份）

| 套件 | 结果 |
|---|---|
| `terminal.test.ts` | 8 / 8 |
| `provenance.test.ts` | 13 / 13 |
| `request-seam.test.ts` | 6 / 6（S1 重做 + S2 授权门） |
| `cancellation.test.ts` | 6 / 6 |
| 合计 | **33 / 33**，`typecheck` exit 0 |

### 1.5 工作树差异（迁移起点）

已修改：`.agent/implementation.md`、`.gitignore`、`docs/README.md`、
`docs/code2paper_dsh_plugin_design_20260922.md`、`paperbanana_single_shot`（子模块）、
`src/code2paper/agentic/authoring_execution_identity.py`、`page_contract_recheck.py`、
`publication_method_writer.py`、`unified_context_compiler.py`、
`tests/regression_20260917/test_page_contract_recheck.py`、
`tests/regression_20260922/test_authoring_contract_closure.py`（K04 等他人工作，保持原样）。
未跟踪：`integrations/`、`scripts/dsh_dev*.py`、`tests/integrations/`、`docs/dsh_execution_20260928/`、
`artifacts/runs/2026-09-18-live-admission/`、`docs/1.txt`。

## 2. S2 首次失败日志（原样保留，不覆盖）

迁移前 `request-seam.test.ts::S2` 的首次失败：

```text
✖ S2: only a proven loop origin obtains a dispatch authorization
  AssertionError [ERR_ASSERTION]: the gate authorized it
      at TestContext.<anonymous> (integrations/dsh/tests/request-seam.test.ts:609:10)
```

当时事实：合法绑定 child 的派发**确实到达底层 adapter 恰好一次**，recorder 为
`['reserve:1','dispatch','settle:settled']`，但门侧 `authorized:` 诊断缺失。

**根因（已复现并修复）**：`gatedAdapter.prepareCall()` 直接返回底层 prepared call，
而拒绝逻辑只在 wrapper 的 `stream` 上；loop 走 `preparedCall.stream(request)`，门从未进入。

**第二个已复现缺陷**：准备记录原按 `sessionId` 计数，裸请求复制 session id/route/装配即可
抢走合法请求的准备。改为按 loop 自己 `agent/request` 的 **signal 对象**（`WeakSet<AbortSignal>`）
记录与消费后闭合。详见 [H04_request_evidence.md](H04_request_evidence.md) §6。

## 3. 新开发候选安装（0.2.0-rc.1，独立根）

| 项 | 值 |
|---|---|
| 候选根 | `.dsh-dev/candidates/0.2.0-rc.1/`（`runtime/`、`cache/`） |
| 安装命令 | `npm install --prefix .dsh-dev/candidates/0.2.0-rc.1/runtime --cache .dsh-dev/candidates/0.2.0-rc.1/cache --no-audit --no-fund` |
| 结果 | exit 0，`added 546 packages in 43s` |
| 精确版本 | `@deepseek-ai/dsh` `0.2.0-rc.1`（`dependencies` 精确固定，非 `^`） |
| `@deepseek-ai/*` 包数 | 289（旧候选 231） |
| lock | `.dsh-dev/candidates/0.2.0-rc.1/runtime/package-lock.json`，374,716 bytes |
| 网络阶段 | 仅此安装阶段联网；运行期仍为无网络 mock |

**H01 迁移目标已在候选树中确认**：`dsh-agent-presets` **不存在**；
`dsh-agent-preset`、`dsh-agent-preset-registry` 均为 `0.2.0-rc.1`。

写入边界：本次安装只写候选根与其专属缓存；未使用全局安装、未写日常 npx 前缀、
未改 `.dsh-dev/runtime`、`.dsh-dev/home` 或日常 DSH。

## 3.1 旧 runtime 复比（历史同一算法）

LEAD 指出条目数与 mtime 不足以证明完整，必须用历史同一摘要算法复比。已按
`scripts/dsh_dev.py` 自身的 `inventory()` + `tree_digest()` 复算：

```
historical algorithm : 7e8f199b67027944d646e0c99f5041d4704360377e4d7466fce683c1d468d3ab
manifest identity    : 7e8f199b67027944d646e0c99f5041d4704360377e4d7466fce683c1d468d3ab
MATCH                : True   (entries 25478)
```

结论：旧 `.dsh-dev/runtime` 与其记录身份**逐字节一致**。此前我给出的 `f8bb6282…`
是自拟算法（relpath + 逐文件 sha256）的结果，与历史算法不可比，已作废，不作为证据。

## 3.2 日常安装：证据缺口（如实登记，不追溯补证）

**缺口：本次候选安装之前，没有对用户日常安装取过安装前快照。**

因此**无法**用字节级证据证明"本次 `npm install` 前后用户日常安装未变"。按 LEAD 要求，
不得用事后快照追溯证明，故此处只登记可证事实与不可证边界：

可证（过程证据，非字节证据）：

* 安装 argv 仅指向候选根：`npm install --prefix .dsh-dev/candidates/0.2.0-rc.1/runtime
  --cache .dsh-dev/candidates/0.2.0-rc.1/cache --no-audit --no-fund`；
* 未使用全局安装、未以日常 npx 前缀为 prefix；
* 更早的 `npm view` 尝试写 `~/.npm/_cacache` 时**失败**（`EROFS: read-only file system`），
  说明该路径在本次沙箱内不可写。

不可证：用户日常安装在本次操作前后逐字节未变。
归因（非越界证据）：manifest 记录的来源 `/home/cuihengjia/.npm/_npx/1e7f6d9597241db0`
当时为 `0.1.5-rc.3`，**现为 `0.1.7-rc.2`**，即用户自行升级，属执行文档 B02 §5 的
"用户升级"类，而非候选漂移或开发越界。

后续按 B02 §5 处理：历史来源摘要原样保存；为**用户现用安装**另行登记当前只读快照
（只登记，不复制凭据/session）；保护失败区分用户升级、候选漂移、开发越界；不删除检查、
不自动重封通过。下一次涉及候选安装/升级的操作，必须先取日常安装的安装前快照再执行。

## 4. 未完成（下一轮）

1. 候选 runtime 安装后转只读（本轮尚未固化只读边界）。
2. `scripts/dsh_dev.py` 增加显式候选选择；候选专属 home/profile/workspace/run。
3. H01 preset 迁移（`dsh-agent-preset(-registry)` 声明式组成）、H02 创建时序复验
   （`agent/created` 已改为 awaited serial）、H03 Session V3→V4、H04 在新候选重跑 S2。
4. 工具链/lock/tsconfig 指向新候选；`compatibility.0.2.0-rc.1.json` 与
   `h02_interface_freeze_020.md` 待写。
