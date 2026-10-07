# H01 · 验收修复证据（三条收口项）

> 2026-09-28 实际执行记录，对应 [首轮 H01 记录](H01_loader_evidence.md) 与独立复核结论
> CHANGES_REQUIRED。本文件只登记修复后的实际观测；首轮摘要仍绑定首轮字节，不在此改写。

| 项 | 值 |
|---|---|
| 任务 / 验收 | H01 / AT-H01（planned_test：`loader.test.ts`） |
| owner / reviewer | DSH / QA（窗口三复核）；本窗口只提交证据，等待 LEAD 裁决 |
| 前置 | B02（done）；首轮 H01 提交 + [独立复核](../../../docs/dsh_execution_20260928/01_baseline_and_dsh_compatibility.md) 缺口 |
| 授权 | offline_implementation；无 live、无 Git 提交、未改冻结 runtime 与日常 DSH |
| 本窗口职责 | H01 验收修复；本轮独占 build/stage，交付时释放（见 §8） |
| 写权交接 | 窗口三完成只读复核、LEAD 核对身份通过后，本窗口自窗口三接管写权；本轮只改测试文件，生产代码未扩大修改 |

## 1. 接管说明（保留既有修改，不重做不回溯）

进入本轮时工作树已含另一窗口的修复改动，本窗口**先审查、接管、只做补强**：

| 对象 | 进入时状态 | 本窗口处理 |
|---|---|---|
| `tests/loader.test.ts` | 已重构：私有 run root、`loadProfileDirectory` 只读消费、deployment/fixture 双真实 host、正式 `ctx.tools.execute`、失败无残留断言 | **保留**；补 5 处（见 §2/§3/§4） |
| `src/index.ts` | 已新增 `composedPreset(agentCtx)`（读 live scope chain，不读 session metadata） | **保留**，未改 |
| `src/task-tools.ts` | 探针改为返回 `bridge.composedPreset(exec.agent.ctx)` | **保留**，未改 |
| `cordis.patch.yml`、`presets/code2paper/agent.cordis.yml` | 与首轮一致 | 未改 |
| `H01_loader_evidence.md` | 已加“首轮提交快照 + CHANGES_REQUIRED”注记 | 未改；修复结果写入本文件 |

本窗口补强（`tests/loader.test.ts` `89566068…` → `dd269fd3…`）：

1. `protectedInputs()` 增加共享 profile 模块回退目录的顶层视图（名字 + 链接目标 + 顶层文件摘要）；
2. `bootHost()` 在 **boot 之后立刻**断言共享 profile 与模块回退未被写入（把写归因到 boot，而不是仅靠收尾对比）；
3. “新服务越域发布”用例改为**先建既有 Agent**，拒绝后断言原服务不存在、既有 Agent 仍在注册表、standing fiber 未变、该 Agent 仍能执行工具；
4. 收尾用例增加夹具私有性与共享根回归断言（私有根前缀、`@h01-fixtures` 不得出现在共享回退、共享 preset 根只含 `code2paper`）；
5. 逐字记录每个反例的拒绝原因并断言共 7 条，随测试输出打印。

### 1.1 第二轮补强：boot 后的清理责任（LEAD 复核发现）

LEAD 只读复核在 `bootHost()` 发现清理路径遗漏：`boot()` 已成功返回，但 `hosts.push(host)` 排在两个
共享输入保护断言**之后**；这两个断言一旦失败，已启动的 host 不会进入 `after()` 的释放列表，可能
留下服务并让测试进程无法退出。本轮最小修正（仅测试文件）：

- 把 host 构造、`hosts.push(host)` 与 bridge 存在性断言**前移到 `boot()` 返回之后立即执行**，保护断言
  移到其后：任何后续读取/断言失败都已被 `after()` 覆盖；
- 增加一次性故障注入（默认惰性）：`<run root>/h01-fault-after-boot.flag` 存在时，下一次 boot 在 host
  注册之后、保护断言之前注入失败，并把该 host 的 `webServer.port` 记到本次私有根；`after()` 在删除
  私有根之前连接该端口，证明释放；
- 标记在使用时即被消费，正常运行不触发；生产代码（`src/**`、patch、preset）未改。

## 2. 收口项一：重复注册 vs 越域发布，分别验证且失败后无影响

两条反例分别独立触发真实 Cordis/agent-presets 的**不同**守卫，且都验证“失败后原服务与已有 Agent 仍正常”：

| 反例 | 触发的守卫 | 逐字拒绝原因（本次运行） |
|---|---|---|
| 已有服务重复注册 | Cordis 服务注册表同名冲突 | `agent-presets: preset "h01-duplicate-service" failed to mount: failed to apply loader entry duplicate-service (@h01-fixtures/duplicate-service): service "code2paperBridge" has been registered at <Code2PaperBridge> (…/fixture-presets/h01-duplicate-service/agent.cordis.yml)` |
| 新服务越域发布 | preset mount 的 root-realm 泄漏守卫 | `agent-presets: preset "h01-leaked-service" failed to mount: row(s) published process-global service(s) [h01LeakedService]; a preset service must sit behind an \`isolate\` realm or move to the host composition (…/fixture-presets/h01-leaked-service/agent.cordis.yml)` |

两条用例的失败后断言（均为真实调用，非静态检查）：

- `ctx.get('h01LeakedService') === undefined`：越域服务被真正移除，而不是被遮蔽；
- 既有 Agent 仍在 `ctx.agents` 注册表（`agents.get(id) === agent`）；
- `standingMountFor(keeper).fiber` 与失败前相同：standing 组成未被替换或重建；
- `bridge.hostGeneration` 不变、bundle 行 fiber 不变（`assertMountFailure` 通用断言）；
- **既有 Agent 再次执行工具返回与失败前完全相同的值**（重复注册用例与越域用例各自都有 keeper）；
- 失败创建不产生 agent/session 公告、不留在注册表、不新增 standing mount（`assertMountFailure` 对每次拒绝都比对前后 `agents.list()`、`sessions.list()`、`livePresetMounts()`）。

## 3. 收口项三：探针返回实际挂载的 preset，正式 `ctx.tools.execute` 验证四类

- 探针实现读 `bridge.composedPreset(exec.agent.ctx)`（live scope chain），**不读** `meta.agentPreset`；
  测试故意给 root 与 child 写入伪造 metadata（`untrusted-metadata-is-not-composition` / `forged-metadata`），
  探针仍返回真实组成。
- 执行入口是正式 `ctx.tools.execute({callId, name, arguments, agent, signal})`，断言
  `isError === false`、渲染文本含 `Code2Paper bridge:`、并比对结构化 `result.value`。

| 场景 | 断言的实际结果 |
|---|---|
| root（deployment host，默认 preset） | `presetId = code2paper`，note 记入该 session 自己的 ledger |
| override（fixture host，`h01-drift`） | `presetId = h01-drift`（首轮缺陷：曾返回默认 `code2paper`） |
| child（`applyChildComposition`） | 返回父的 preset `h01-drift`；child 的 standing key/fiber 与父相同；父文件改动后新 root 换 generation，父与 child 不漂移；child 执行工具返回自己的 ledger |
| 未 join 的 Agent | `execute` 返回 `isError = true`、`error.info.code = UNKNOWN_TOOL`；`composedPreset` 抛 `requires an agent joined to a preset`；该 session 的 ledger 保持为空 |

## 4. 收口项二：只读消费共享 profile/staging，夹具私有，夹具存在时验证未变

- **共享输入只读**：`bootHost()` 用 `loadProfileDirectory()`（只读已初始化目录，不做 init/normalize/heal），
  profile root 字节复制到本次私有 config，裸包名经私有 `node_modules` 符号链接解析到冻结 peers 与 staged bundle，
  不调用 `healProfilesModuleFallback`，不向共享 profile/staging 写任何字节。
- **夹具私有**：`privateRoot = mkdtempSync(<run root>/h01-loader-)`；负例 preset 在
  `<privateRoot>/fixture-presets/`，fixture 包在 `<privateRoot>/node_modules/@h01-fixtures/`；
  负例 host 的 overlay 只把 roster/bridge 指向该私有根。
- **夹具存在时的断言**（收尾用例仍在夹具存在时执行）：私有根与夹具路径前缀正确、`@h01-fixtures` 存在于私有根、
  共享回退中不存在 `@h01-fixtures`、共享 preset 根只含 `code2paper`、`protectedInputs()` 与运行前快照全等。

外部独立前后对比（本窗口在测试进程之外做的第二次验证，覆盖一次完整 `test:compat`）：

```text
before: staged files 8 presets ['code2paper']
test:compat exit: 0   (ℹ tests 16 / ℹ pass 16 / ℹ fail 0)
shared inputs identical: True
private run dirs left: ['qa-w3-20260928']      # 仅窗口三的目录；本窗口测试目录已自清理
fixture namespace in shared fallback: False
```

对比覆盖：`staging.json` 摘要、staged 树 8 个文件摘要、profile 目录文件摘要、共享
`profiles/node_modules` 顶层名字/链接目标、共享 preset 根条目集合。

## 4.1 收口项四（第二轮）：boot 后失败仍释放 context 与端口

按 §1.1 的故障注入做一次真实验证（注入点位于 host 注册之后、保护断言之前，模拟 LEAD 指出的场景）：

```bash
printf '{}\n' > .dsh-dev/run/h01-fault-after-boot.flag
npm --prefix integrations/dsh run test:compat          # 预期非零退出
```

| 观测项 | 实际结果 |
|---|---|
| 退出码 | `1`（`before()` 内注入失败 → 10 项 H01 用例失败，6 项工具链用例仍通过） |
| 进程是否退出 | 9 秒内正常退出，无挂起（未触发 `timeout`） |
| context 是否释放 | `after()` 仍执行：`livePresetMounts` 为空、`code2paperBridge` 已撤销、`modelCalls=0` |
| 端口是否释放 | `H01 fault injection: port 45849 released after teardown: true`（`after()` 在删除私有根前连接该端口失败＝已关闭） |
| 注入标记 | 使用后即消费（`consumed`）；`ss -ltn` 中该端口无监听 |
| 清理 | 私有 run root、`fault-port.txt` 均已删除；run root 仅剩窗口三的 `qa-w3-20260928`；`stage --check` 通过 |

结论：清理责任在 `boot()` 返回后立即建立，`before()` 抛错时 `after()` 仍释放该 context；这正是修正前
会遗漏的路径（修正前该 host 未进入释放列表）。

## 5. 命令与退出码

在仓库根、当前 dirty 树执行（本窗口独占 build/stage 期间）：

| # | 命令 | 退出码 | 关键结果 |
|---|---|---|---|
| 1 | `npm --prefix integrations/dsh run check:compat` | 0 | typecheck→build→stage→test；**16/16**（10 项 H01 + 6 项工具链），7 条拒绝原因逐字打印 |
| 2 | `npm --prefix integrations/dsh run typecheck` | 0 | `tsc` 无诊断（含 `src/**`、`tests/**`、`dev/toolchain/**`） |
| 3 | `npm --prefix integrations/dsh run test:compat` | 0 | 16/16；stage `--check` 通过（测试未污染 staging） |
| 4 | `python scripts/dsh_dev.py doctor --evidence` | 0 | runtime 树未变、原安装只读、run root 可写、worker 正常；`compat_composition_ready=true` |
| 5 | `python -m pytest -q integrations/dsh/dev/tests/` | 0 | 22 passed（B02 隔离/工具链，无回归） |
| 6 | `python scripts/dsh_dev_smoke.py --composition compat` | 0 | 真实 CLI 启动 compat 组成：HTTP 200、4 资源 200、零模型请求、端口释放 |
| 7 | `python scripts/dsh_dev_smoke.py` | 0 | web 组成无回归 |
| 8 | `python -m pytest -q tests/regression_20260917/test_execution_identity.py` | 0 | 24 passed |
| 9 | `git diff --check` | 0 | 无空白/冲突标记 |
| 10 | `npm --prefix integrations/dsh run check:compat`（冻结后再跑一次） | 0 | 16/16；构建回执 `ea2289b1…` 与 `outputs_digest 6c1c6a08…`、staging 树 `abe6365d…`（8 文件）与 §7 **逐字相同**：同输入重复构建/打包可复现 |
| 11 | `printf '{}\n' > .dsh-dev/run/h01-fault-after-boot.flag` + `npm --prefix integrations/dsh run test:compat` | **1** | 注入的 boot 后失败；10 项 H01 用例失败、6 项工具链通过；`after()` 仍释放 context 且端口 45849 已关闭（见 §4.1） |
| 12 | `npm --prefix integrations/dsh run check:compat`（清理修正后重新冻结） | 0 | 16/16；`loader.test.ts` 摘要更新为 `4e6e6699…`，`src/**`、构建回执、staging 树不变 |
| 13 | `python scripts/dsh_dev.py doctor --evidence` / `python -m pytest -q integrations/dsh/dev/tests/` / 两个 smoke / identity pytest / `git diff --check`（重新冻结后复跑） | 0 / 0 / 0 / 0 / 0 | `compat_composition_ready=true`；22 passed；compat 与 web 入口正常；24 passed；无空白问题 |

测试节点（`check:compat` 的 `test` 阶段，`node --test --test-concurrency=1`）：

```text
✔ compat tests have an isolated DSH home, scrubbed credentials, and readonly runtime/source
✔ offline namespace still supports a local fixture server
✔ the bundle is staged at the profile install location with its build receipt
✔ every declared peer resolves from the staged bundle into the frozen runtime
✔ the staged package imports the shared cordis instance without shipping dev files
✔ development dependencies did not modify the frozen runtime
✔ real deployment patch and roster load from unchanged profile/staging inputs
✔ named exports preserve name/inject/Config on the actual Loader rows
✔ root setup awaits composition and the public ToolRuntime executes/renders its scoped tool
✔ sibling ledgers stay separate and the public ToolRuntime rejects a non-joined agent
✔ override and child report their actual preset and retain the parent standing generation after an edit
✔ missing package/inject, bad Config and one metadata-losing default export fail without live residue
✔ a new process-global service is rejected and fully removed after failed preset creation
✔ duplicate host service registration rejects without replacing the bridge or harming an existing agent
✔ agent disposal removes its live state but preserves the shared standing composition
✔ both real hosts remain model-free and shared profile/staging bytes stay unchanged with fixtures present
```

## 6. 反例结果（7 条，逐字）

```text
h01-missing-package:   agent-presets: preset "h01-missing-package" failed to mount: row "missing-package" names a plugin that cannot be resolved: @h01-fixtures/does-not-exist
h01-missing-inject:    agent-presets: preset "h01-missing-inject" failed to mount: 1 row(s) did not activate:
h01-bad-config:        agent-presets: preset "h01-bad-config" failed to mount: failed to apply loader entry bad-config (@h01-fixtures/bad-config): invalid config:
h01-bundle-bad-config: agent-presets: preset "h01-bundle-bad-config" failed to mount: failed to apply loader entry bundle-bad-config (@code2paper/dsh-bundle): invalid config:
h01-default-only:      agent-presets: preset "h01-default-only" failed to mount: failed to apply loader entry default-only (@h01-fixtures/default-only): cannot get property "h01NeverProvidedService" without inject (…/fixture-presets/h01-default-only/agent.cordis.yml)
h01-leaked-service:    agent-presets: preset "h01-leaked-service" failed to mount: row(s) published process-global service(s) [h01LeakedService]; a preset service must sit behind an `isolate` realm or move to the host composition (…/fixture-presets/h01-leaked-service/agent.cordis.yml)
h01-duplicate-service: agent-presets: preset "h01-duplicate-service" failed to mount: failed to apply loader entry duplicate-service (@h01-fixtures/duplicate-service): service "code2paperBridge" has been registered at <Code2PaperBridge> (…/fixture-presets/h01-duplicate-service/agent.cordis.yml)
```

另：`rootModule.Config({presetId:'x'})` 直接抛错（缺 `presetRoot`/`runRoot`）；未 join 的 Agent 经正式
`ctx.tools.execute` 返回 `UNKNOWN_TOOL`。全部 7 条拒绝后均无 agent/session 公告、无残留 mount、
无残留服务，且既有 Agent 与其工具调用保持原值。

## 7. 冻结输入与身份

| 对象 | 值 |
|---|---|
| 仓库 HEAD | `d48b4e4b22c94c82b45d2179ba452d72b164102d`（dirty 树保留，未 commit/reset） |
| 冻结 runtime | DSH `0.1.5-rc.3`，树 `7e8f199b67027944d646e0c99f5041d4704360377e4d7466fce683c1d468d3ab`，Node `v25.8.2` |
| 工具链 | TypeScript `5.9.3` / `@types/node` `25.9.3`，lock `55ca97f5bc7391934640a6620bafe8ec70f4a7edb440557b1062bd2141f38f71` |
| 源码 | `src/index.ts` `4053ef10…`；`src/task-tools.ts` `0ed976fe…`；`cordis.patch.yml` `9aabad07…`；`presets/code2paper/agent.cordis.yml` `dff3b69b…`；`tests/loader.test.ts` `4e6e6699864222fc0c18f3d57db0359a804eea131e387151468580d519821c24`（第二轮清理修正后）；`package.json` `7878ee1d…`；`package-lock.json` `55ca97f5…`；`dev/offline.patch.yml` `5efac6d7…` |
| 构建回执 | `integrations/dsh/lib/build-receipt.json` `ea2289b147582a68cf284d7392a809261a97534cef18733396a5a70fb744a437`；`outputs_digest 6c1c6a08…`；`src_present/entry_present/patch_present = true/true/true` |
| staging | 树 `abe6365d55d4bc6af128aecfbe49da5ff1867201d727f95c177c53fd41304f5f`，8 个文件 |
| 证据产物 | `development-environment-isolation.json` `a8ed7b60…`；`compat-smoke.json` `2f86ac06…`；`web-smoke.json` `1a821a80…` |

## 8. 清理情况与构建窗口释放

- 测试自建的私有 run root（`<run root>/h01-loader-*`）在 `after()` 内删除；外部复核确认 run root 只剩
  窗口三的 `qa-w3-20260928`，本窗口无遗留。
- 共享 preset 根只剩 `code2paper`；共享模块回退中无 `@h01-fixtures`；`stage --check` 通过。
- 本轮同时清理了首轮遗留的空目录 `.dsh-dev/run/h01-loader/`（仅含空 `workspace`，无其他窗口引用）。
- **构建窗口释放**：本窗口不再执行 build/stage。后续任何 build/stage 会改变 §7 的构建回执、staging 树
  与 `lib/**` 摘要，必须重新登记身份并重跑 `check:compat`。
- 第二轮（清理修正）只改 `tests/loader.test.ts`：`src/**`、patch、preset、构建回执、staging 树在
  重新冻结后与第一轮逐字相同；故障注入的标记文件与端口记录均已清除。

## 9. 未测项与限制

1. 仍**未做**首请求绑定（H02）、terminal/原始来源（H03）、真实模型与取消（H04）；本单元全程 offline。
2. 探针 `c2p_bridge_probe` 只是组成探针，不是 C01/C03 领域工具。
3. 双 host 在**同一进程**内启动（各占一个随机 loopback 端口），与真实“每进程一个部署”不同；这是为了在同一
   测试内对比 deployment 与 fixture 组成，结论仅限组成/作用域语义。
4. 共享输入对比包含 profile 目录的 inode/mtime：若其他窗口在测试期间启动 CLI（`healProfilesModuleFallback`
   可能触碰共享回退），断言会失败并暴露共享状态变化，属预期行为而非测试不稳定。
5. 未验证 `default export` 丢失 `name`/`Config` 的所有组合，只证明 `inject` 丢失这一条路径（用例注释已声明）。
6. 清理路径的故障注入是**手动、标记触发**的验证路径（§4.1），不在 `check:compat` 的正常集合内；正常运行时
   标记不存在，注入代码不执行。注入只覆盖“boot 成功后、保护断言失败”这一场景，未覆盖 `boot()` 自身抛错
   （此时没有已启动的 context 需要释放，`after()` 只处理 `hosts`/`handles` 中已登记的项）。

## 10. 交接

本记录连同 §5 的命令/退出码、§6 的反例结果、§7 的冻结身份提交给**窗口三**独立复核；复核后由 **LEAD 裁决**。
第二轮补强（§1.1、§4.1）已按 LEAD 复核意见完成并重新冻结，写权随即交回窗口三。在裁决前本窗口**不开始 H02**，
也不再改动 H01 交付文件。
