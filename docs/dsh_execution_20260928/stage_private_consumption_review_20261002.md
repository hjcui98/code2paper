# 私有消费候选独立差分复核与完整返修接续（2026-10-02）

> 本次由未参与该候选实现的 Codex 执行独立离线探针、冻结产物复验和身份核对。
> 未改产品代码、原测试、runtime、peer、build/stage、Python 内核或 validator。
> 当前执行入口为 [README §3.13](README.md)。原 8 份执行文档、49 单元、全部 AT、依赖和
> [来源接口裁决 §6](h04_loop_origin_escalation_20261001.md) 保持有效。

## 1. 结论与有效成果

**返修交付有真实进展，但仍须 CHANGES_REQUESTED：Gate-H 未通过，正式 Gate-K 未放行。**
删除公开 `admitLoopDispatchOrigin` 已关闭原 async-hook 的已观察预消费窗口；新 C21 在本次
独立原套件中通过。新的公开 `takeLoopDispatchEntry` 仍能在 NO_ADAPTER 回落的同步服务
查找 hook 内被预消费；公开流的 iterator 获取也没有完全隔离。两条独立反例在交付和
源码构建候选上均实际失败，各自都有合法 prepared/fallback 正对照。

| 对象 | 本次新观测与边界 |
|---|---|
| 原交付套件 | 独立验证已有 staging 后运行 11 文件，87 pass / 0 fail / 0 skip，exit 0；没有重建或重新 stage |
| B02 | 显式选择补丁候选后 24 passed，exit 0 |
| doctor | 显式候选、无 `--evidence` 写入，exit 0 |
| 独立新探针 | 每棵候选 4 项：2 合法正例 pass、2 边界反例 fail，真实 Node exit 1 |
| 同 child | 原 joint-child 在本次原套件中实际通过，保留 accounting→terminal→flush→新进程 committed 恢复证据 |
| 来源与构建 | source/patch/build receipt 摘要符合交付清单；源码构建两份 JS 与 `-built` 候选逐字节相同 |
| 封存 | 14 文件的 SHA-256 清单全部匹配；上一轮独立 QA 根未变；历史灭失如实保留，不补造 |
| 内核 | 对上一轮已验清单中的 791 条 source/test 逐字节核对，全部未变；既有 component PASS 保留，不重跑 4129 |

仓库仍是 `codex/agentic-p4-benchmark-cutover` / `d48b4e4b22c94c82b45d2179ba452d72b164102d`
的 dirty 树。原第 01 份仍返修中，第 02 份保持已验 component，第 03/04 份未开始实现。
台账 49 个原任务对象不变；当前形式状态为 2 done、9 in_progress、38 planned，不换算为产品完成率。

## 2. 必须返修的三个问题

### PC-1：同步 `internal/get` 公开观察者仍能取走 entry-ack

责任域：原 H04/LO-4，窗口二；阻断 Gate-H。

固定源码 `packages/core/agent-loop/src/agent.ts:450` 在 entry 子作用域内执行：

```ts
enterLoopDispatchOrigin(
  () => preparedCall?.stream(request) ?? this.loopCtx.llm.stream(request),
)
```

NO_ADAPTER 回落没有 prepared handle，因而此时读取 `this.loopCtx.llm`。Cordis 的公开
Context 服务属性读取会同步执行 `internal/get` waterfall；这段扩展代码发生在
`streamWithRegistration` 取 entry-ack **之前**。不创建 Promise、不出现 await，并不能
证明这段同步调用链没有公开 hook。

独立夹具仅通过公开 `deployment.on('internal/get', ...)` 观察服务读取，并在来源可见时
调用包根公开的 `peekLoopDispatchOrigin`、`takeLoopDispatchEntry`；随后原样 `next()`。
它不修改 runtime、ALS、loop factory、request 或 Host authorization，不替换 LLM 服务。

| 对照 | child | reserve / dispatch / settle / adapter | 公开 take |
|---|---|---|---|
| 交付候选，普通 prepared | completed | 1 / 1 / 1 / 1 | 无观察者 |
| 交付候选，合法回落 | completed | 1 / 1 / 1 / 1 | 无观察者 |
| 交付候选，回落 + 公开服务读取观察者 | error | 0 / 0 / 0 / 0 | 1 次成功 |
| 源码构建候选，普通 prepared / 合法回落 | 各 completed | 各 1 / 1 / 1 / 1 | 无观察者 |
| 源码构建候选，回落 + 相同观察者 | error | 0 / 0 / 0 / 0 | 1 次成功 |

这是新的真实公开预消费反例。把 `take` 称为 origin-neutral/entry-ack，并不能消除它对
合法派发的授权影响。本次证明合法 child 被阻断；没有宣称已证明裸模型发送或预算被盗。

### PC-2：`Symbol.asyncIterator()` 获取在清空作用域外执行

责任域：原 H04/LO-1，窗口二；阻断完整公开入口隔离合同。

固定源码 `packages/llm/llm/src/index.ts:1186` 当前为：

```ts
const inner = runIsolated(() =>
  this.ctx.waterfall(this, 'llm/stream', options, () => this.adapterStream(options, prepared)),
)[Symbol.asyncIterator]()
```

waterfall listener 创建在空 store 内，但对其返回 iterable 的 `Symbol.asyncIterator`
属性读取和方法调用发生在 `runIsolated` 返回之后。该方法可以是公开 listener 提供的
普通同步方法，不必是 async generator。

独立夹具在真实合法 child 的 listener 中发起另一 provider 的普通公开流；这个普通流的
公开 listener 返回自定义 iterable，分别记录 listener 与 iterator 获取时的只读来源。
两棵候选结果一致：listener 内 `seesOrigin=false`，iterator 获取时 `seesOrigin=true`。
合法 child 仍 completed、R/D/S 各 1；ordinary provider 成功一次，adapter 总计 2。
因此这不是全拒绝或普通流量回归，而是构造期确实重新暴露外层来源。

本次未将这条来源可见性反例扩大为已经证明额外预算/adapter 被冒用。它已足以否定
interface-diff 所称“整个构造与迭代都在空 store 内”。完整获取过程及惰性
next/return/throw 均须在同一隔离合同下验证。

### PC-3：实际 manifest 与生成器仍漏列两份 `.d.ts`

责任域：原 B02/LO-4 交付身份，窗口二。

对 pristine 基树与交付候选的完整 inventory 求差，实际修改 4 文件：两份
`lib/index.js` 与两份 `lib/types/index.d.ts`。兼容清单确实列齐了 4 文件。
但是实际候选 `manifest.json` 的 `loop_origin_patch.touched` 仍只有 2 个 JS；
`scripts/dsh_dev.py:276` 的 `loop_origin_setup` 生成器同样硬列这 2 文件。

因此“manifest touched 已列齐 4 文件”的交付说明目前不成立。须修生成器和新候选实际
manifest，并用真实 inventory 差分校验 touched 的一致性，不能只改文档或手改一次 JSON。
证据为本批 `delivery-audit.json`。runtime 树摘要本身正确，类型文件也实际存在；不要将
清单缺项误写为类型未交付或整棵 runtime 无法运行。

## 3. 本次绑定的候选身份

| 对象 | SHA-256 |
|---|---|
| 原 0.2 基树 | `43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c` |
| 交付 runtime | `a010ccdc690d738a4a26a77224774195c31a162f3c4c39230b5d93d87655f1b5` |
| 源码构建 runtime | `7ae6af55ac1509e1e7c4c7540f6050ee5613255ee4b8746492620bb3939911c8` |
| request-accounting.ts | `12f33263f16a26dc4c85c170e05fe3ce02fadd0cf6cb713db6be1c09d129d810` |
| runtime 补丁脚本 | `e2a8cd2ac9b8e627ba981ac344d49dd54697c454e919fbaacd1d30e70de2ead9` |
| 源码补丁 | `419d5a8dd5d9bdbc9ef5f7f8449de482e7f502246861d8b6680b9682dd1ecdbf` |
| build receipt | `85a37546efd74a33f5203d10168ee0e3e7347c68cdcae0b4d586813466281c69` |
| staging | `950ba6d42f5a50de2d62665acca2913b849bab3d7dc087589e3587a05542c5bd` |
| outputs | `2aeceb7bbeb5e18a07ed6d4f01bf7b15c32d0cf9d3a846157c593eebebc1b620` |

源码固定 `4878cdabd87d4041bdaff61d04c966883b9fd07a`。本次读取实际源码构建 JS 并对照
`-built`，没有重新运行 pnpm/native build，也没有把行为等价写成 npm 压缩字节相同。

## 4. 窗口二一次接回原第 01 份完整返修

本批实际读集已明确释放。窗口二接回原 B02/H01–H04、窄来源源码、TS、toolchain、
peer、build/stage 与补丁候选的原唯一写权，不逐反例另行申请。

1. 本次已将 `w2-lo-repair` 四份原交付日志复制到候选外独立根的 `owner-log-copies/`，
   以 `owner-log-copy-manifest.json` 绑定原路径/摘要；窗口二重建前补齐其完整源码构建命令、
   退出码和候选身份封存。本次独立根不能删除/覆盖，旧 14 文件封存和灭失登记保留。
2. 连续修 PC-1/PC-2/PC-3。entry 的可信建立/消费段须明确排除同步服务解析及其他公开
   callback；公开观察者不能预消费、铸造或复位授权。保持 §6 的 request/实际派发实例
   绑定与私有能力合同，不以改名、首调、信号、时间窗或补一个状态分支过门。
3. 将新的同步 service lookup 正反例、普通公开 custom iterable 获取正反例及 manifest
   inventory 一致性纳入原 owner 回归； prepared 与 NO_ADAPTER 回落、C21、C13/C14/C14b、
   原抢票、普通三入口、A/B、等待期取消/fence/漂移、usage/cap/cleanup/unknown 均保留。
   不通过跳过测试、删除正常流量或让合法 child 也失败来关闭反例。
4. 同步固定源码、编译 hunk、runtime 类型和真实 Host 消费者；在交付与源码构建两侧运行
   新反例及原合法链。保持 registration/config/单次 dispatch 和公共 NO_ADAPTER 原语义。
5. 保留原全部 AT 与同 child accounting→adapter→terminal→settle→flush→新进程
   committed 恢复。按影响重验 H01/H02/B02，交一次完整稳定 check:compat、显式候选 B02、
   doctor、patch hygiene；保存准确 argv/cwd/选择环境、退出码、原日志及首次失败。
6. 形成同一份 source/patch/lock/runtime/peer/build/outputs/staging/interface 身份、
   AT→真实节点/证据、未测项与明确写权释放，再启动一次按需独立差分验收。

这是原阶段持续返修，不新建产品任务、第二本账本或另一个执行架构。
本次没有重复普通 Web HTTP smoke、完整 native 构建或完整正向 Gate-H 的所有独立 AT；
这两条反例已经足以阻断本候选，最终正向过门仍按原 verification 全合同执行。

## 5. 窗口一与后续统一分工

窗口一保持原第 02 份的已验 K01–K04 component 和已交付复用清单；无新增内核返修、
重复调查或 4129 全量任务，也不提前修改共享 Python/validator 或开始 C/R 实现。

实际 Gate-H 与正式 Gate-K 满足后，再一次启用原第 03 份整阶段：

| 窗口 | 原任务与单写责任 |
|---|---|
| 一 | I01、C01、C02、C03、C04；Python 协议和 validator 唯一写者 |
| 二 | C00、TS wire 消费者、唯一 peer/build/stage；向窗口一提交必要的共享 Python 合同需求 |
| 按需 QA | 真实 worker 的无模型 prepare/ingest 联合包齐备后，独立验原 AT 与 Gate-C |

阶段内按 I01→C01→C00→C02→C03→C04 的有意义本地合同持续衔接；正式依赖和 Gate-C 不减项。
Gate-C 后启用原第 04 份整阶段：窗口一负责 R01/R02、Python R04 与 A01，窗口二负责
R03、TS R04、V02 与 build/stage；两位联合 V01，依序 R01→R02→R03→R04→V01→A01→V02。
Gate-R/V 保留，之后才形成可单独申请 L01 的候选。当前没有 live、全文迁移或默认切换授权。

## 6. 原始证据、准确命令与明确释放

权威新鲜根：`.dsh-dev/run/qa-private-consume-20261002-7o8lt6bj/`。

- `probes/<candidate>/private-boundaries.test.ts`：两棵候选各 4 项，真实进程原日志/exit/result。
- `*-private-boundaries.command.json`：使用现有 `sandbox_command`；runtime 只读、断网、
  独立可写 candidate run 子根，probe 源码在候选外；模块明确解析到各自 candidate。
- `0.2.0-rc.1+loop-origin.1-original-suite.*`：按当前已有 stage 复验后，用原
  `test_command` 运行实际发现的 11 文件；87/0/0，exit 0。
- `b02.*`：`C2P_DSH_CANDIDATE=0.2.0-rc.1+loop-origin.1`、匹配的 `C2P_DSH_DEV_ROOT`，
  `python -m pytest -q integrations/dsh/dev/tests`，24 passed、exit 0。
- `doctor.*`：`python scripts/dsh_dev.py --candidate 0.2.0-rc.1+loop-origin.1 doctor`，exit 0。
- `delivery-audit.json`：实际 4 文件差分、manifest/兼容清单、封存、源码和 build 摘要核对。
- `kernel-preservation.json`：791 原 source/test 摘要未变，component 保持。
- `review_driver.py` 和 `owner-log-copies/`：本次实际 driver 与四份原交付日志的稳定副本，
  后者以 `owner-log-copy-manifest.json` 绑定；复制发生在读集释放后。

系统沙箱首轮阻止 bubblewrap 的 NETLINK_ROUTE socket，未进入产品探针；保留
`.sandbox-bootstrap`，在自动审查允许的系统沙箱外继续使用原断网/只读 bubblewrap 后，
得到上述真实 Node 失败。B02 首轮 runner 漏传候选环境，落入历史默认根而出现 peer
不匹配；保留 `.default-selection-first-attempt`，修正选择后 24/24。二者不计产品缺陷，
不把 wrapper exit 0 冒充其 inner exit，也不覆盖首次输出。

本批于 **2026-10-02T12:12:01.298025+08:00** 明确释放实际读集：992 项输入的
hash/inode/mtime/size 完全一致，四棵 runtime inventory 和 peer 不变；宿主扫描 1780
进程，相关验证为 0、不可读为 0；本批全部启动命令已返回，无 pending。
`before-inputs.json`、`after-inputs.json`、四树清单、`closing_input_check.json`、
`closing_process_check.json`、`closing_release.json` 保留原样。

后续本报告、入口和台账更新发生在释放后，属于裁决记录，不冒称仍是未变的受测输入。
QA 批次结束，窗口二按 §4 连续返修；下一完整候选就绪后再独立验收，无常驻 QA。
