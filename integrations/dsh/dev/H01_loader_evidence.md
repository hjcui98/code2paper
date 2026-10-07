# H01 · 真实 Loader、复数 presets 和作用域（证据与交接）

> 2026-09-28 实际执行记录。任务卡见 [01 执行文档](../../../docs/dsh_execution_20260928/01_baseline_and_dsh_compatibility.md)；
> 状态以 [台账](../../../docs/dsh_execution_20260928/task_board.json) 为准。本文件只登记本单元实际观测到的结果。

> **首轮提交快照。** 独立 QA 复跑了本页的 13 项 Node 和 22 项环境测试，但发现覆盖与隔离缺口，
> 首轮结论为 CHANGES_REQUIRED。修复后的结果另见 [验收修复记录](H01_acceptance_fix_evidence.md)；
> 本页原测试数量、源码及构建摘要继续绑定首轮字节，不能代替修复后的身份。

| 项 | 值 |
|---|---|
| 任务 / 验收 | H01 / AT-H01（planned_test：`loader.test.ts`） |
| owner / reviewer | DSH / QA（本记录由实现者提交，等待独立复核） |
| 前置 | B02（done，另有 [交接修复记录](toolchain/B02_handoff_fix_evidence.md)） |
| 授权 | offline_implementation；未启动真实模型、未做 live 准入 |
| 输入身份 | HEAD `d48b4e4b22c94c82b45d2179ba452d72b164102d`（dirty 树保留）；冻结 runtime `0.1.5-rc.3`，树摘要 `7e8f199b…8d3ab`；Node `v25.8.2`；工具链 TypeScript `5.9.3` / `@types/node` `25.9.3` |
| 构建身份 | `lib/build-receipt.json` `cfe2edac8226e97a695a543a0038df4df0a59b84ccbd8a9f1521c20e3648e25e`；staging 树 `04efdf20420af751db11f0ba7fb62a68b2e4e66a5e82da852c567c639d613fd0`（8 个文件，entry/patch 均在） |

## 1. 改动范围

| 文件 | 状态 | 内容 |
|---|---|---|
| `integrations/dsh/src/index.ts` | 新增 | Host 平面：`code2paperBridge` 服务、`mountCode2PaperPreset`、`applyChildComposition`；无 default export |
| `integrations/dsh/src/task-tools.ts` | 新增 | preset 平面：`code2paper-tools` 行与 `c2p_bridge_probe` 工具；无 default export |
| `integrations/dsh/cordis.patch.yml` | 新增 | bundle patch：insert Host 行 + 整行替换 `agent-presets` config |
| `integrations/dsh/presets/code2paper/agent.cordis.yml` | 新增 | 目录扫描的 preset entry list（tools 行） |
| `integrations/dsh/tests/loader.test.ts` | 新增 | AT-H01 的 7 项真实 Loader/roster/scope 测试 |
| `integrations/dsh/package.json`、`package-lock.json` | 修改 | 增加 `@deepseek-ai/schemastery` peer（bundle 的 Config schema 依赖），重新生成 lock |
| `integrations/dsh/dev/README.md` | 修改 | 记录 bundle 两个平面、preset 与命令 |

**范围说明（须复核）**：任务卡只列了 `src/index.ts`，但设计 §7.1 的 bundle 需要 `./tools` 导出，
因此新增了 `src/task-tools.ts`；`package.json`/`package-lock.json` 属 B02 owned path，本次因新增
peer 而改动，已在 §6 记录对 B02 证据的影响。未触碰 B02 的启动器/工具链逻辑、H02/H03 的
`src/session-binding.ts`、`src/role-dispatch.ts`、`src/terminal-result.ts`。

文件摘要（SHA-256）：

```text
066be147e1b7c11b760e2883ca7a73eb531e8847156cf8da37226b8df914beaa  integrations/dsh/src/index.ts
c4b569d1fb852559b9f8ee3e65167b06575d23fa804c02be555541a2203446ef  integrations/dsh/src/task-tools.ts
9aabad07dceaecca8b05ca61c606ac2fd1a2ea2c10efa02281263b8d48cb6e7d  integrations/dsh/cordis.patch.yml
dff3b69be1ecd6fffdf4305a7ff809746b2cb937230aa7732d10448a002a6e4e  integrations/dsh/presets/code2paper/agent.cordis.yml
c100b84ce607c5295355415b530ecdfe5aee177e6dd146074b5c23a2a7c38909  integrations/dsh/tests/loader.test.ts
7878ee1dcd7f776e27c837869d688c9cd6908b1656a3c46c6244e33b0f25e489  integrations/dsh/package.json
55ca97f5bc7391934640a6620bafe8ec70f4a7edb440557b1062bd2141f38f71  integrations/dsh/package-lock.json
```

## 2. AT-H01 逐条对照

| 验收条款 | 实际观测 | 测试节点 |
|---|---|---|
| 真实 Loader 加载本地 bundle | `boot()` 用真实 `@deepseek-ai/dsh-app-boot` 从 `code2paper-dev-compat` profile 组成 156 个 entry；本 bundle 行 `include:code2paper-bridge` 的 fiber 记录 `name=code2paper-bridge`、`inject=['agentPresets']`、`Config` 存在 | `named exports survive the Loader…` |
| 覆盖 agent-presets 行 | patch 整行替换后 `roster.roots == [{path: <staged>/presets, trust:'system'}]`，`includeShippedRoot/includeUserRoot` 关闭；`list()` 只返回 `code2paper` 且 `broken` 为空 | `the host plane publishes the bridge and the roster…` |
| 目录扫描 `agent.cordis.yml` | 发现的 preset path 以 `presets/code2paper/agent.cordis.yml` 结尾 | 同上 |
| create.setup 中 await mount | `setup` 内 `await mountCode2PaperPreset(...)` 之后立刻断言 agent scope 已有 `c2p_bridge_probe`；mount 失败会让整个创建回滚 | `a root agent is composed from the preset…` |
| Host service 与 preset 工具分层 | Host 平面 `ctx.tools.get(probe, undefined) === undefined` 且 bridge 服务存在；agent scope 内 `schemas(scopeOf(agentCtx))` 含 `c2p_bridge_probe`；preset 子树行 fiber 记录 `name=code2paper-tools`、`inject=['code2paperBridge','tools']` | 上述两项 |
| root setup await mount；child 同步 composeFrom | child 的 `standingMountFor().key` 与 `fiber` 与父完全相同（同一 standing generation） | `a child joins the parent standing generation…` |
| 父 preset 文件变化不漂移 | 改动父 preset 文件后：新 root session 组成新 generation（key/fiber 均不同），运行中的父与其 child 仍保持旧 generation | 同上 |
| 缺包明确失败 | `agent-preset/invalid: … row "h01-missing-package" names a plugin that cannot be resolved: @h01-fixtures/does-not-exist` | `missing package, missing inject, …` |
| 缺 inject 明确失败 | `… 1 row(s) did not activate: …` | 同上 |
| 全局服务越域发布明确失败 | `… row(s) published process-global service(s) [h01LeakedService]; a preset service must sit behind an \`isolate\` realm or move to the host composition`；此项不覆盖已有服务名重复注册，后者须单独补证 | 同上 |
| 坏 Config 明确失败 | fixture 与**本 bundle 自身**的行都报 `failed to apply loader entry …: invalid config: …`；`Config({presetId:'x'})` 直接抛错（缺 `presetRoot`/`runRoot`） | 同上 |
| default export 丢 metadata 明确失败 | 真实模块均无 default export；default-only 反例行报 `cannot get property "h01NeverProvidedService" without inject` —— 证明 `unwrapExports` 取了 default、丢掉 `inject`，且该丢失在此处**明确失败**而非静默降级 | 同上 |
| 兄弟/日常会话无任务状态泄漏 | 兄弟 agent 各自 ledger 独立；未 join preset 的 agent 看不到 `c2p_bridge_probe`（`get(...,scope)` 为 undefined）且 bridge 中无其状态 | `sibling sessions and non-preset sessions share no task state` |
| 不借上游未安装 testkit | 只用 Node 内置 `node:test` 与冻结 runtime 内已安装包；未引入 vitest/上游 testkit | 工具链 `compat-tests.mjs` 发现 `tests/**/*.test.ts` |
| 销毁语义 | 释放一个 agent 后 standing mount 仍 live，后续 agent 加入同一 fiber 且工具可见 | `disposing an agent leaves the shared standing composition…` |
| 正常 Web 入口仍工作 | `web` 组成 smoke 通过（首页 200、4 静态资源 200、端口释放） | `.dsh-dev/evidence/web-smoke.json` |
| compat 组成可真实启动 | 真实 CLI 启动 compat profile：首页 200、4 静态资源 200、`model_turns_submitted=0`、端口释放 | `.dsh-dev/evidence/compat-smoke.json` |

### 实测到的 0.1.5-rc.3 Loader 行为（供 H02–H04 引用）

1. `Loader.unwrapExports`：`exports.default ?? exports`，非 null/undefined 的 default 优先作为
   插件对象；命名导出的元数据不会补回 default 对象上缺失的字段。本 bundle 因此不导出 default。
   首轮反例证明缺少 inject 时读取相应服务失败，不能外推为任意缺少 Config/name 都自动拒绝。
2. composed entry 的 `entry.id` 形如 `include:<row id>`；`entry.options.name` 是行里的包名；
   插件元数据在 `entry.fiber.runtime`（`name`/`Config`）与 `entry.fiber.inject`（解析后的依赖表）。
3. patch 列表中，`insert` 只承载**新增行**；覆盖既有行必须是同级（顶层）的 `- id: …` 条目。
   放错层级会产生重复 entry id 并在 boot 时报 `duplicate loader entry id: agent-presets`。
4. 预设行的裸包名按 `agentCtx.baseUrl`（组成目录 = profile 目录）解析；本部署的 bundle 位于
   `$DSH_HOME/profiles/node_modules`，因此 patch 用 `dshHomePath('profiles/node_modules/@code2paper/dsh-bundle/presets')`
   指向 preset root（profile 局部 `node_modules` 实测为空，`healProfilesModuleFallback` 只建了空的
   `.dsh-module-fallback`）。
5. 服务访问受调用方 `inject` 约束：agent scope 上下文不能直接读 `agentCtx.agentPresets`，
   组合入口必须以**声明了 inject 的调用方上下文**作为 caller（H02 的 binding 行需
   `inject: ['code2paperBridge', …]`）。

## 3. 实际命令与退出码

| # | 命令 | 退出码 | 关键结果 |
|---|---|---|---|
| 1 | `npm --prefix integrations/dsh run check:compat` | 0 | typecheck→build→stage→test；13 项测试全部通过（7 项 H01 + 6 项既有 B02） |
| 2 | `npm --prefix integrations/dsh run test:compat`（再次） | 0 | 13/13 通过；staging `--check` 仍通过（测试清理了自己的 preset/fixture） |
| 3 | `python scripts/dsh_dev_smoke.py --composition compat` | 0 | `passed=true`、`profile=code2paper-dev-compat`、HTTP 200、4 资源 200、端口释放 |
| 4 | `python scripts/dsh_dev_smoke.py` | 0 | web 组成未回归 |
| 5 | `python scripts/dsh_dev.py doctor --evidence` | 0 | runtime 树未变、原安装只读、run root 可写、worker 正常；`compat_composition_ready=true` |
| 6 | `python -m pytest -q integrations/dsh/dev/tests/` | 0 | 22 passed（B02 隔离/工具链测试，未回归） |
| 7 | `python -m pytest -q tests/regression_20260917/test_execution_identity.py` | 0 | 24 passed |
| 8 | `git diff --check` | 0 | 无空白/冲突标记 |

产物摘要：

| 产物 | SHA-256 |
|---|---|
| `.dsh-dev/evidence/development-environment-isolation.json` | `5d96dbaf6e0fd0eb2158d86a80a70f56ae4a838352cff883201bd210111d74b4` |
| `.dsh-dev/evidence/compat-smoke.json` | `64da6ab1cfc0724005e3a585ee9d59e0e86aff58a5647afb4f5898869cb505ae` |
| `integrations/dsh/lib/build-receipt.json` | `cfe2edac8226e97a695a543a0038df4df0a59b84ccbd8a9f1521c20e3648e25e` |
| `integrations/dsh/dev/README.md` | `2be575d910907e272d26025e01d37000739b67effb1fc70d8ced8e2335937770` |

## 4. 未测项与限制

1. **未做首请求绑定**：`agent/created` 异步观察、pre-step 时序、材料装配前绑定属 H02；
   本单元的 `setup` 只证明 mount 在 setup 返回前完成。
2. **工具是组成探针**：`c2p_bridge_probe` 只证明分层/作用域/注入，不是 C01/C03 的领域 terminal
   工具；H03 另建 `terminal-result.ts`。
3. **未验证真实模型与取消**：H04 范围；本单元全程 offline（测试沙箱 `--unshare-net`）。
4. **`@deepseek-ai/schemastery` peer 依赖**：bundle 的 Config schema 需要它，版本按 web-app 的
   `3.18.2` 固定；它已存在于冻结 runtime 与 profile 回退目录，未下载第二份。
5. **测试进程内的 boot**：`loader.test.ts` 在沙箱内以 in-process `boot()` 启动真实组成，会占用
   一个随机 loopback 端口并写入隔离 DSH home 的 session 日志；它不触碰日常 home 与仓库。
6. **首轮测试自建状态的缺陷**：测试在共享扫描根创建 `h01-*` preset、在共享 profile 回退目录
   创建 `@h01-fixtures/*`，还会无条件覆盖共享 `cordis.yml`。正常结束时字节恢复一致不证明
   非标准配置受保护，也不证明中途退出安全。若 staging 留下夹具，下一次 `test:compat` 会在
   `before` 之前持续拒绝；重复执行不能自愈。须按修复记录隔离夹具，不能移除 staging 漂移门。
7. **QA 复核建议**：重跑 §3 的 1–5；重点核对 `loader.test.ts` 的失败路径断言与
   `entry.fiber.runtime/inject` 元数据断言，并确认 staged 目录在测试后只剩 `code2paper`。

## 5. 对 B02 证据的影响

H01 只改了 B02 owned path 中的两个文件，B02 的验收行为未变：

- `integrations/dsh/package.json`：B02 最终获验 `d3358441…` → `7878ee1d…`（新增 `@deepseek-ai/schemastery` peer；旧稿 `38c483e5…` 不是本次前置身份）；
- `integrations/dsh/package-lock.json`：`abb78e43…` → `55ca97f5…`（重新生成，仍只锁定 3 个开发包）。

工具链已按新 lock 重新 `npm ci` 并刷新 `.dsh-dev/toolchain.json`（`lock_sha256 = 55ca97f5…`）；
`doctor`、22 项 B02 隔离测试、web smoke 均通过。原 [B02 报告](B02_environment_isolation_evidence.md)
及 [B02 最终验收](../../../docs/dsh_execution_20260928/b01_b02_acceptance.md) 保留各自历史身份；
文件未变的摘要可逐项复核，但旧整体回执不能作为新 package/lock/build 的身份。

## 6. 首轮独立复核

[独立记录](/tmp/c2p-h01-independent-qa-20260928-i7lpf1st/verification.json) 中准确记录命令、
退出码、25 个输入及共享 profile/staging 的前后摘要，原有测试全部通过且相关进程已退出。
独立最小探针另证实：重复 `code2paperBridge` 会被真实 Cordis 拒绝；正式 `ctx.tools.execute`
可执行 root/child 的工具，未 join 的 agent 返回 `UNKNOWN_TOOL` 且无 note 写入；override
child 实际位于 `h01-qa-drift`，工具却返回默认 `code2paper`。原测试遗漏了这些持久断言。
共享配置写入缺陷经代码审查确认，不能用本次默认配置前后字节恰好相同来否定。
