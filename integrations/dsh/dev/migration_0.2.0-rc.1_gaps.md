# DSH 0.2.0-rc.1 接入：迁移缺口清单（实测）

> 2026-09-29，窗口二。peer 已激活到候选 0.2.0-rc.1，`typecheck` 实跑取得下列缺口。
> 候选身份：runtime 树 `43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c`，
> peer 链接 `integrations/dsh/node_modules/@deepseek-ai → .dsh-dev/candidates/0.2.0-rc.1/runtime/...`。
> 默认 `.dsh-dev/runtime`（0.1.5-rc.3）**未改动**，历史 identity `7e8f199b…` 仍经历史算法复比通过。

命令：

```text
C2P_DSH_DEV_ROOT="$PWD/.dsh-dev/candidates/0.2.0-rc.1" npm --prefix integrations/dsh run toolchain:install
C2P_DSH_DEV_ROOT="$PWD/.dsh-dev/candidates/0.2.0-rc.1" npm --prefix integrations/dsh run typecheck
```

结果：**21 个类型错误**，四族。

## A. H01 —— preset 服务换代（实质改写，5 文件 / 6 错误）

| 位置 | 事实 |
|---|---|
| `dev/toolchain/peer-probe.ts:24` | `Cannot find module '@deepseek-ai/dsh-agent-presets'` |
| `src/index.ts:26` | 同上（import） |
| `src/index.ts:147` | `Property 'agentPresets' does not exist on type 'Context'` |
| `src/index.ts:166`、`182` | 同上（三处调用点） |
| `src/role-dispatch.ts:36` | 缺模块 |
| `tests/binding.test.ts:41`、`tests/loader.test.ts:28` | 缺模块 |
| `tests/loader.test.ts:403–405` | `ctx.agentPresets` 不存在 |

**旧 API（0.1.5，`dsh-agent-presets`）**——本单位实际用到的三个方法：

```ts
this.hostCtx.agentPresets.composedPreset(agentCtx)        // index.ts:147
this.hostCtx.agentPresets.mount(agentCtx, presetId)       // index.ts:166
this.hostCtx.agentPresets.composeFrom(agentCtx, parentCtx) // index.ts:182
```

**新 API（0.2.0-rc.1）**：包为 `dsh-agent-preset` + `dsh-agent-preset-registry`；
服务名仍是 `ctx.agentPresets`，但类型是 `AgentPresetRegistry`，远端面为
`agentPresets/list`、`agentPresets/read(agentPreset)`、`agentPresets/select(agentId, agentPreset)`
（`lib/types/index.d.ts:17`、`lib/typert.remote-client.d.ts:16–24`）。

⇒ H01 不是改 import 就能过：`mount`/`composeFrom` 这套命令式挂载语义在新版由
**声明式组成 + registry 选择**取代。需要按新语义重写 Host/preset 分权与挂载路径，
并复验 generation、override、销毁与拒绝路径。**这是本阶段最大的一块。**

## B. H02 —— `agent/created` 监听器签名变更（5 处 / 5 错误）

新版签名（实测）：

```ts
(this: Scoped<Agent>, payload: { agent: Agent; source: SessionStartSource; signal?: AbortSignal })
  => Promise<undefined> | undefined
```

返回 `void` 的箭头函数**不再可赋值**，须显式返回 `undefined`。命中：

- `src/request-accounting.ts:439`
- `tests/binding.test.ts:440`
- `tests/cancellation.test.ts:248`
- `tests/loader.test.ts:273`
- `tests/request-seam.test.ts:235`、`242`

这同时印证执行文档所述「`agent/created` 改为 awaited serial」：事件现在携带 `source` 与
可选 `signal`，即创建期绑定必须在 await 语义下完成。

## C. 机械项（3 错误）

- `tests/loader.test.ts:220`、`242`、`549`：回调参数隐式 `any`（`mount`、`live`），新类型下需显式标注。
- `tests/terminal.test.ts:353`：结构断言转型需经 `unknown`。

## D. 尚未触及的迁移面

- H03 Session V3→V4：成功结果由旧嵌套 tool-result block 改为独立 tool 消息，
  需按 `callId/turn/step/isError` 重接 reader，且新旧记录分版本、不做宽松字段回退。
- H04：在新候选重跑 S2（授权门已覆盖 direct 与 prepared）、S3–S6。
- 组成：重新盘点 provider、title/retry/compaction/PTC、OTel/desktop 行与可选 Schedule bundle；
  显式 mock 白名单与网络隔离需在新候选上重新成立，不能复用旧 disabled 行。
- 0.2 恢复增量：`TOOL_NOT_STARTED` / `TOOL_OUTCOME_UNKNOWN` 不得作为 terminal 成功、
  usage、已结算、可重试或预算可退的证明。

## E. 交付终点（尚未可达）

同一个真实绑定 child 上完成
`reserve → dispatch → adapter → terminal → settle → flush → 新进程恢复`。
当前 A/B 两族未修完，基础包（AT-B02/AT-H01/AT-H02）与
`compatibility.0.2.0-rc.1.json`、`h02_interface_freeze_020.md` 均未产出，Gate-H 未通过。


---

# 恢复检查点（同一任务接续，不视为任务结束）

## 已达状态（全部实测）

| 项 | 状态 |
|---|---|
| 候选 peer 激活 | `integrations/dsh/node_modules/@deepseek-ai → .dsh-dev/candidates/0.2.0-rc.1/runtime/...` |
| **typecheck（0.2）** | **exit 0**（起点 21 错误 → 0） |
| build | exit 0，`outputs=15`，`outputs_digest 979c75dd99d3a71fe3100b3e45ceb6fb2c46dbdcf09603d5e49892aece64855a` |
| stage（候选根） | exit 0，树 `abcf9a44d78600c9c2ef046a1930275d203c4f05ca924d5a417f9aac0d5336a8`，18 文件 |
| 候选 CLI 装载 | `config` 与 `config --composition compat` 均 exit 0（composition 可加载） |
| loader 套件 | **1 / 10**（其余 9 项由下面同一根因阻断） |
| 候选 runtime 树 | `43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c` |
| 默认 `.dsh-dev/runtime` | 未改动，历史 identity 仍 `7e8f199b…`（历史算法复比通过） |

## 已完成的迁移改动（本窗口）

1. **包名换代**：`@deepseek-ai/dsh-agent-presets` → `@deepseek-ai/dsh-agent-preset-registry`，
   5 处 import（`src/index.ts`、`src/role-dispatch.ts`、`tests/loader.test.ts`、
   `tests/binding.test.ts`、`dev/toolchain/peer-probe.ts`）；`AgentPresets` → `AgentPresetRegistry`。
2. **package.json peers** → 0.2.0-rc.1（cordis 4.0.4、schemastery 3.18.4、agent/llm/session/subagent/tools
   0.2.0-rc.1、registry 0.2.0-rc.1）。
3. **cordis.patch.yml**：行 id `agent-presets` → `agent-preset-registry`，config 由
   `{default, roots, includeShippedRoot, includeUserRoot}` 收敛为 `{default: code2paper}`
   （扫描模型在 0.2 已废弃）。
4. **H02 签名**：6 处 `agent/created` 监听器显式 `return undefined`
   （新签名 `(payload:{agent,source,signal?}) => Promise<undefined>|undefined`）。
5. **launcher 候选化**：`select_candidate` / `--candidate` / `C2P_DSH_CANDIDATE`；
   `DEV_ROOT` 贯穿 `safe_dev_root`、`child_env`（并导出 `C2P_DSH_DEV_ROOT` 给子进程）、
   `read_manifest`、sandbox `--bind`；`--candidate … candidate --provision` 建候选
   home/profile/manifest/依赖农场（`link_profile_peers()`，528 条符号链接，零字节复制）；
   `require_candidate_ready()` fail-closed。
6. **工具链候选化**：`toolchain.mjs` 的 `devRoot` 支持 `C2P_DSH_DEV_ROOT`；peer 链接不符时按名拒绝。
7. **测试隔离守卫候选化**：三处 `devRoot` 改为读 `C2P_DSH_DEV_ROOT`（守卫语义不变）。
8. **`default_runtime` 完整性**：只报实算结果（`not_checked` / `verified` / `drift` /
   `runtime_missing` / `identity_missing`）。

## 下一步（唯一阻断点，已定位到具体 API）

**症状**：`RemoteError: Unknown agent preset: code2paper`
（`dsh-agent-preset-registry/lib/index.js:643 retain` → `:694 mount`）。
9 个 loader 用例同因：patch 里 `default: code2paper`，但**没有任何地方声明** `code2paper` preset。
旧模型靠 `roots` 扫描 `presets/`，该配置在 0.2 已不存在。

**0.2 的声明式形状**（`dsh-agent-preset-registry/lib/types/definition.d.ts`）：

```ts
interface PresetDefinition {
  id: string;
  name?: string; description?: string; order?: number;
  plugins: readonly (Omit<EntryOptions,'id'|'disabled'> & {
    id?: string; disabled?: EntryOptions['disabled'] | JsExpr;
  })[];
}
// registry.register(definition): Promise<() => Promise<void>>  — 声明方拥有 disposer
```

**实施方向**：由本 bundle 的 root 行（`src/index.ts` 的 `apply`）调用
`ctx.agentPresets.register(...)`，把现有 `presets/code2paper/agent.cordis.yml` 的 plugin 行
作为 `plugins` 声明注册（保持该 YAML 为唯一事实来源），并按新语义复验 Host/preset 分权、
generation、override、销毁与拒绝路径。注册点必须与 `apply` 同一 Host 行，避免在
Host 行自身激活期调用会等待树稳定的审计接口。

## 接续后待办顺序

1. 声明 `code2paper` preset（上节）→ loader 套件转绿。
2. binding / cancellation / request-seam / terminal / provenance 在 0.2 下复跑与修复。
3. H03 Session V3→V4（独立 tool 消息、callId/turn/step/isError、按版本分 reader，
   不做宽松字段回退）。
4. H04：新候选重跑 S2（授权门已覆盖 direct 与 prepared）、S3–S6。
5. 组成重新盘点：provider、title/retry/compaction/PTC、OTel/desktop 行、可选 Schedule bundle；
   mock 白名单与断网在新候选重新成立。
6. 同 child 联合接线：`reserve → dispatch → adapter → terminal → settle → flush → 新进程恢复`。
7. 基础包 + `compatibility.0.2.0-rc.1.json` + `h02_interface_freeze_020.md`。

**环境状态**：peer 链接当前指向 **0.2 候选**（按授权持续激活开发用 0.2）；
默认 `.dsh-dev/runtime` 与日常安装未被改动。恢复默认对照只需
`npm --prefix integrations/dsh run toolchain:install`（不带 `C2P_DSH_DEV_ROOT`）。


---

# 恢复检查点 2（H01/H02 已在 0.2 通过）

## 当前实测状态（候选 0.2.0-rc.1）

| 套件 | 结果 |
|---|---|
| `loader.test.ts`（H01） | **10 / 10** |
| `binding.test.ts`（H02） | **11 / 11** |
| `provenance.test.ts` | **13 / 13** |
| `request-seam.test.ts`（H04） | **5 / 6**（S2 未过） |
| `terminal.test.ts`（H03 V4） | **0 / 8**（未迁移） |
| `cancellation.test.ts` | 超 600s 未出结论，需单独长时运行 |

typecheck / build / stage / CLI 装载均 exit 0。

## 本轮新增改动

1. **preset 改为 0.2 声明式**：新增 `presets/code2paper.patch.yml`
   （`- insert: [ {id: preset-code2paper, name: '@deepseek-ai/dsh-agent-preset',
   config: {id: code2paper, order: 10, plugins: [code2paper-tools]} } ]`），
   `package.json` 的 `dsh.bundle.patch` 改为
   `["./cordis.patch.yml", "./presets/code2paper.patch.yml"]`；删除旧的
   `presets/code2paper/agent.cordis.yml`（0.2 无目录扫描模型）。
   → `Unknown agent preset: code2paper` 消除。
2. **loader 夹具迁移**：`writePreset` 由「写扫描文件」改为「调
   `ctx.agentPresets.register({id, name, plugins})`」，行定义由 YAML 文本改为对象数组；
   重复声明先释放上一次注册（0.2 拒绝重复，0.1.5 靠覆盖文件）；
   夹具 overlay 去掉已废弃的 `agent-presets` roots 行，改为设置
   `agent-preset-registry` 的 `default`。
3. **拒绝文案对齐 0.2 真实输出**：
   `never started`、`waiting for <service>`、`Preset services require isolate realms: <svc>`。
4. **roster 断言**：web-app 自带 `standard` preset，roster 断言改为按成员而非唯一性。
5. **staged preset 根**：断言由 `[presetId]` 改为 `['code2paper.patch.yml']`。
6. **隔离守卫候选化补齐**：`request-seam` / `terminal` / `provenance` 三处
   `devRoot` 也改为读 `C2P_DSH_DEV_ROOT`。

## 下一步（按序）

1. **S2 在 0.2 重做**：现状「合法绑定 child 的派发未到达 adapter」。
   已知 0.2 `llm/stream` 仍由 LlmRuntime 自身 context 发射、无 child 隔离，
   且 prepared 的单次/config 门不覆盖完整 messages/tools。
   需先判定是 `agent/request` 的 `signal` 绑定失效（准备记录未建立 →
   `dispatch_origin_unproven`）还是授权未被门消费；两条路径的具名诊断已就绪。
2. `cancellation.test.ts` 单独长时运行，定位是否是挂起（可能是 0.2 下
   delegate 未结束）还是仅超时。
3. **H03 Session V3→V4**：成功结果由旧嵌套 tool-result block 改为独立 tool 消息，
   按 `callId/turn/step/isError` 重接 reader，新旧分版本、不做宽松回退。
4. 组成重新盘点：provider、title/retry/compaction/PTC、OTel/desktop 行、
   可选 Schedule bundle；mock 白名单与断网在新候选重新成立。
5. 同 child 联合接线：`reserve → dispatch → adapter → terminal → settle → flush → 新进程恢复`。
6. 基础包 + `compatibility.0.2.0-rc.1.json` + `h02_interface_freeze_020.md`。

## 环境状态

peer 链接指向 **0.2 候选**；候选根 `.dsh-dev/candidates/0.2.0-rc.1/`
（runtime 树 `43490765…`、profile 依赖农场 528 链接、manifest 已写）。
默认 `.dsh-dev/runtime`（0.1.5-rc.3）与日常安装未改动，历史 identity 仍可复比。
恢复默认对照：不带 `C2P_DSH_DEV_ROOT` 运行 `npm --prefix integrations/dsh run toolchain:install`。

## 命令备忘

```text
CAND="$PWD/.dsh-dev/candidates/0.2.0-rc.1"
C2P_DSH_DEV_ROOT="$CAND" npm --prefix integrations/dsh run toolchain:install
C2P_DSH_DEV_ROOT="$CAND" npm --prefix integrations/dsh run typecheck
python scripts/dsh_dev.py --candidate 0.2.0-rc.1 stage
python scripts/dsh_dev.py --candidate 0.2.0-rc.1 test -- <ABSOLUTE test path>
python scripts/dsh_dev.py --candidate 0.2.0-rc.1 candidate --provision   # 首次
```


---

# 恢复检查点 3（0.2 上除 H03 V4 外全部套件转绿）

## 实测状态（候选 0.2.0-rc.1，树 `43490765…`）

| 套件 | 结果 | 命令退出码 |
|---|---|---|
| `loader.test.ts`（H01） | **10 / 10** | 0 |
| `binding.test.ts`（H02） | **11 / 11** | 0 |
| `request-seam.test.ts`（H04） | **6 / 6** | 0 |
| `cancellation.test.ts`（H04） | **6 / 6**（1.70s） | 0 |
| `provenance.test.ts` | **13 / 13** | 0 |
| `terminal.test.ts`（H03 V4） | **0 / 8** | 1 |

合计 **46 / 54**。typecheck / build / stage / CLI 装载均 exit 0。

## 本轮两项决定性修复

### 1. S2 首个失败点 = `contract-unsupported`（已修）

到达事实追踪（新增，常驻于 S2 失败路径）给出：

```
agent/created, agent/request, agent/created, agent/request, …
accounting:pre-dispatch-refused:contract-unsupported
recorder events: []                       ← reserve 都没发生
route diagnostics: unauthorized:no live dispatch authorization for this assembly
run result: {"output":[],"stopReason":"error"}
```

即**来源证明本身已工作**（`agent/request` 触发、准备记录建立），失败在 accept 之前的
摘要覆盖面：0.2 的 `GenerateOptions` 新增 **`toolHistory`**，落在封闭覆盖集之外，
按设计被拒为 `contract-unsupported`。

修复：把 `toolHistory` 加入 `COVERED_KEYS`（它是 model-facing 工具材料，必须在摘要内，
不能排除；封闭集不放开，未知键仍拒绝）。

### 2. 600 秒挂起 = 同一根因的次生现象（已消失）

加入 `toolHistory` 覆盖后，`cancellation.test.ts` 由「>600s 无结论」变为
**6/6 / 1.70s**。解释：受保护请求被拒 → 0.2 的失败步骤恢复路径反复重试，
表现为无结论的长时间运行。**未通过放大 timeout 掩盖**，也未把超时当静止或结算。

## 唯一剩余缺口：H03 Session V3→V4

`terminal.test.ts` 首个断言即失败：

```
AssertionError: a restarted consumer must rebuild the committed terminal
  actual: 'unresolved'
```

根因与执行文档一致：0.2 的成功结果由旧**嵌套 tool-result block** 改为**独立 tool 消息**，
`rebuildTerminal()` 仍按旧形状找成功事实，因而重建不出 committed。

**下一步**：按 `callId/turn/step/isError` 重接 reader，新旧记录按版本分派，
**不做宽松字段回退**；覆盖真实工具成功对应、raw/normalized/parsed/prose 来源、
完整性、损坏日志具名拒绝、`sessions.flush` 与新进程恢复；并注意 0.2 恢复增量
（`TOOL_NOT_STARTED` / `TOOL_OUTCOME_UNKNOWN`）不得当作 terminal 成功、usage、
已结算、可重试或预算可退的证明。

## 尚未开始

组成重新盘点（provider、title/retry/compaction/PTC、OTel/desktop 行、可选 Schedule bundle；
mock 白名单与断网在新候选重新成立）、同 child 联合接线
（`reserve → dispatch → adapter → terminal → settle → flush → 新进程恢复`）、
`compatibility.0.2.0-rc.1.json` 与 `h02_interface_freeze_020.md`、完整 `check:compat`。
Gate-H 未通过；QA 只在完整候选提交后启动。

## 环境

peer 指向 0.2 候选；默认 `.dsh-dev/runtime`（0.1.5-rc.3，identity `7e8f199b…`）与日常
DSH 0.1.7-rc.2 未改动。恢复默认对照：不带 `C2P_DSH_DEV_ROOT` 运行
`npm --prefix integrations/dsh run toolchain:install`。
