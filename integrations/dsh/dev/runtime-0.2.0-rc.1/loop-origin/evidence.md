> 当前交付入口：`integrations/dsh/dev/gate_h_repair_batch_20261003.md`。
> 本文历史表与 take/entry-ack 叙述仅描述其绑定轮次，不作为当前 API 或当前候选身份。当前公开面为 frozen peek、对象同一性门控的 admit、clear-only runner；受信派发通过静态模块入口和私有 WeakMap，公开面不持有私有 capability。

# loop-origin.1 · 阶段证据（模块级能力门控派发版，CAP-1/PC-2 闭环）

> 2026-10-02 14:48 最新独立复核：[能力门控候选裁决](../../../../../docs/dsh_execution_20260928/stage_capability_entry_review_20261002.md)。
> 实际交付树 `0adaffc8…`、源码构建树 `dcf69658…`；公开 internal/get resolver 返回转发 Proxy
> 可截获实际 capability 并预消费，两侧合法 child error/零 RDS/adapter；源码侧 iterator 获取仍见来源。
> 四文件 touched 已修。下方 owner 身份/API/完整 soundness 声明存在旧值或未兑现部分，
> 原 87 项不能代替新边界验收，Gate-H 仍 CHANGES_REQUESTED。此前 12:12 补注绑定旧 v4 候选。
> 本批 QA 已释放自己的读集；另有 owner 源码验证进程未结束，先收尾后再重建。


> 独立复核补注（2026-10-02 12:12）：[本批报告](../../../../../docs/dsh_execution_20260928/stage_private_consumption_review_20261002.md)
> 实际复验交付原套件 87/87、显式 B02 24/24、doctor 通过；两棵候选新的同步服务读取预消费
> 与 iterator 获取来源可见性反例仍失败。实际 manifest/生成器尚未列齐 types；下方“touched
> 4 文件”和完整私有消费/构造隔离属于实现者交付声明，须按新反例修正，不登记 Gate-H PASS。

> 全部为本轮实测（fresh 输出），绑定候选 `0.2.0-rc.1+loop-origin.1`。
> 环境：`/home/cuihengjia/agent/Code2Paper copy`，分支 `codex/agentic-p4-benchmark-cutover`，
> HEAD `d48b4e4b`（dirty 树保留）。本版闭环 2026-10-02 返修差分的公开预消费反例
> （LO-4-PRECONSUME）与证据封存缺口。

## 0. 证据封存（返修指令第 1 项）

- 存活证据已封存至候选根之外：`.dsh-dev/run/w2-loop-origin-private-20261001-182722/`
  （14 文件 + `SEALED_FILES.sha256.json` + `EVIDENCE_SEAL.md`）。内容：返修轮交付候选
  日志（check-compat 86/86、b02 24、doctor、源码构建验证 86/86）、过程 stamp 日志、
  交付侧文档快照。
- **如实登记的灭失**：首轮交付日志 `run/w2-lo-final/` 与首轮 QA 权威根
  `run/qa-loop-origin-awkji3_e/` 因多轮候选重建（rm -rf + setup）灭失，不可恢复；
  历史文字记载保留并附注 raw 路径不可审计，不补造。本轮起候选重建只替换受控
  runtime/build/stage，`run/` 与封存根不随之删除（本轮 rebuild 前先将 run/ 移出、
  重建后原样移回）。
- 本批 QA 权威根 `.dsh-dev/run/qa-loop-origin-repair-0yrz6nyl/` 未触碰。

## 1. 历史 round9 93/26 身份（后续工具链返修前）

| 对象 | SHA-256 |
|---|---|
| base runtime 树（pristine `0.2.0-rc.1`，未动） | `43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c` |
| patched runtime 树（交付候选） | `671daa1a7a06728d69a4bdec6da3d33a3616c4e788f63579ed07f3ae81e0e16c` |
| 补丁脚本 `loop-origin.patch.py` | `b36b887fc71e90de84080897169f79bddf370793a293ca1e54c03fbcb02c8e75` |
| 源码补丁 `loop-origin-source.patch` | `0db693e794feea78f8087198078df04d41614804898aec329cf5628a45987512` |
| 源码绑定 | tag `dsh-v0.2.0-rc.1` = commit `4878cdabd87d4041bdaff61d04c966883b9fd07a` |
| build receipt（交付候选） | `ea004d4592ce67bdeb26017eb4556e3f6fb601f375b2f7b8f3d32b9af33c4e89` |
| build outputs digest | `9c00688b090ab3bb744ba83975e5ab447fe75fd61798906d15ba13fa4e750e95` |
| staging tree（交付候选） | `60acfbb2ec14fedca2880eb6a40b035ccb4df15851b175eb09a6741f9b1bb304` |
| 源码构建验证候选树（-built） | `3076d2fcdbf6b2b49167e8132ce9b5801d95079a36f9bd05af17302e8482be97` |
| build receipt（-built 候选） | `78292cbed43d15d4c436601e784de68934cf49bd27ecd95a9328e3e8b5fc6250` |
| staging tree（-built 候选） | `b4c9e4454b8ba6b223b38861dbb9b91def444da12bd3dc9c67b95b9008a6b229` |

源码（`integrations/dsh/src/`）：index/task-tools/session-binding/role-dispatch/
request-contract/terminal-result 六份与上轮一致（未变）；`request-accounting.ts` =
`efaa899ce0950a317ea0ab90d6581ea9811755980b1c9538c3048242a4ee0453`（只读快照核验）。

## 2. 历史 round9 命令与退出码（非本批结果）

| 命令 | 退出码 | 结果 |
|---|---|---|
| `loop-origin-setup`（重建候选） | 0 | 补丁域 5 文件；run/ 证据未触碰 |
| `npm run typecheck` / `build` / `stage` | 0/0/0 | receipt `ea004d45…`，staging `60acfbb2…` |
| `npm run check:compat`（交付候选） | 0 | **93 tests / 93 pass / 0 fail / 0 skipped** |
| `python -m pytest -q integrations/dsh/dev/tests`（B02） | 0 | **26 passed / 0 failed / 0 skipped** |
| `doctor --evidence` | 0 | 隔离证据 JSON 更新（`bytes_match=true`，`compat_composition_ready=true`） |
| `smoke-web` / `smoke-compat` | 0/0 | 真实 HTTP 200，assets 200，端口释放，0 模型 turn |
| `audit-delivery` / `audit-built` | 0/0 | PASS |
| `git diff --check` | 0 | 干净 |
| `pnpm install --frozen-lockfile`（源码树） | 0 | pnpm 11.7.0 |
| `tsc -b packages/llm/llm`、`tsc -b packages/core/agent-loop` | 0/0 | 源码类型检查（与候选 types 逐字节对齐） |
| `pnpm run build:lib:host` | 0 | 完整 host 构建 |
| `check:compat`（源码构建候选 `-built`） | 0 | **93/93 pass**（源码等价证据，不声称 B02/doctor） |

日志（封存根 `.dsh-dev/run/w2-loop-origin-private-20261003-round9/`）：`check-compat-delivery.log`、`check-compat-built.log`、
`b02-pytest.log`、`doctor.log`、`smoke-web.log`、`smoke-compat.log`、`audit-delivery.log`、`audit-built.log`。逐套件结果：

| 文件 | pass | 覆盖要点 |
|---|---|---|
| `tests/cancellation.test.ts` | 30 | C0–C18、C12b、C14b、C19/C20 + C21（公开 async-hook 预消费回归）+ C22（转发 Proxy capability 截获回归，CAP-1）+ C23（listener 提供的自定义 `Symbol.asyncIterator` 构造期隔离回归，PC-2）+ **C24（GHS-1 公开参数与未授权调用回归）** + **C25（GHS-1 全链路成员 Proxy 包装回归）** + **C26（GHS-2 注册表生命周期注销与双 deployment fail-closed 回归）** + **C27（GHS-2 deployment 生命周期序列 A->B 与幂等注销回归）** |
| `tests/joint-child.test.ts` | 1 | 同 child：reserve→dispatch→adapter→terminal→settle→committed→新进程恢复 |
| `tests/request-seam.test.ts` | 6 | S1/S2/复制 digest/重放/外路由 |
| `tests/terminal.test.ts` | 10 | 终端提交/重建/合成未知 |
| `tests/provenance.test.ts` | 14 | H03 严格读取/完整性/flush/新进程恢复 |
| `tests/loader.test.ts` | 10 | Loader/peer 解析 |
| `tests/binding.test.ts` | 11 | 绑定/fence |
| `tests/composition.test.ts` | 3 | 组成 |
| `tests/candidate-selection.test.ts` | 2 | 候选 id 动态选择 |
| `dev/toolchain/sandbox.test.ts` | 2 | 沙箱合同 |
| `dev/toolchain/staging.test.ts` | 4 | staging/peer/开发依赖不污染 frozen runtime |

（11 文件合计 93 项全部通过；逐项权威见封存日志。）

## 3. 历史 LO-4-PRECONSUME 方案（87 项时期，非当前 API）

- **反例机理（QA 实测）**：`AsyncLocalStorage.run(..., async () => …)` 创建 Promise
  时公开 async hook 同步执行，此时快照未消费；观察者取快照中的真实 request 调用
  公开 `admitLoopDispatchOrigin(request)` 得 `admitted` 并置位，loop 自身 admission
  被拒，合法 child error、R/D/S/adapter 全 0。
- **修复**：删除公开 `admitLoopDispatchOrigin`；一次性状态只存在于模块私有域——
  来源作用域由 loop 私有 establish 建立（建立即权威，无独立消费步骤）；loop 自己
  的同步 stream entry 经模块私有 `enterLoopDispatchOrigin` 子作用域标记；dsh-llm
  仅读判定（peek + take entry-ack），对来源零变更。entry 调用链从子作用域进入到
  判定全程同步、不创建 Promise，任何 hook/listener 都无法先于 loop 取走 ack。
- **回归 C21**（只用剩余公开面，非 import error）：公开 async-hook 观察者在每个
  hook 里 peek + take + 以受保护会话发起公开派发——实测 `takeSucceeded=0`、观察者
  派发具名 `dispatch_origin_unproven`、合法 child completed 且 R/D/S/adapter 各 1。
  交付候选与源码构建候选（`-built`）均 87/87 通过同一回归。

## 4. 其余保持项（本轮复验通过）

- LO-1 三入口（C19）、LO-2 公共 NO_ADAPTER/内部回落（C20）、LO-3 旧 manifest
  （B02 `test_unpatched_manifests_keep_the_original_format`，0.1.5-rc.3 与 0.2.0-rc.1）。
- 原抢票（C10 预持 handle）、同 request 重入（C13，具名 `dispatch_origin_unproven`，
  零 reserve/adapter）、复制/延迟重放（C14/C14b）、等待期 abort/fence（C1/C6/C16/C17）、
  usage 缺失（C7）、同步/异步 return 与 250ms 截止（C8/C12/C12b）、未知发送
  （C15）、cap（C18）、兄弟（C9/C11）。
- H03 严格读取/完整性/flush/新进程恢复（provenance 14 项 + joint-child）。
- manifest `touched` 按实际差分列齐 5 文件；`sandbox.test.ts`/`staging.test.ts`
  按实际文件名列齐。

## 5. 边界与未测风险

- 未跑 live API，未登记 Gate-H PASS；候选待独立差分验收。
- `packages/llm/llm` 的独立 tsdown 步骤走 monorepo 根管线；本批以
  `pnpm run build:lib:host` 完成整链构建并做行为等价验证；npm 发布压缩变体的
  逐字节形态未单独复刻（逐字节权威 = hunk 补丁）。
- 当前派发来源机制：保留 capability-gated `admitLoopDispatchOrigin`，仅在 capability 与私有来源对象同一时一次消费；删除历史 `takeLoopDispatchEntry`/entry-ack，
  受信派发仅由 loop 派发点建立来源并持有私有 capability，通过静态模块导入调用 `runLoopDispatch`；
  通过对象同一性门控后，由模块私有 WeakMap 获取派发器；实例解析通过 `kRootRuntime` / `unwrapRuntime`
  穿透任何 Proxy 包装，杜绝任何外部拦截或公开篡夺。
- 写权范围：本候选目录、`integrations/dsh/src/request-accounting.ts`、
  `integrations/dsh/tests/*`、`integrations/dsh/dev/toolchain/staging.test.ts`、
  `integrations/dsh/dev/tests/*`、`integrations/dsh/dev/runtime-0.2.0-rc.1/loop-origin/*`、
  `scripts/dsh_dev.py`、源码工作树、本文档与 `_020`。原 0.2 树、旧 0.1.5、日常
  0.1.7、Python 内核/validator、LEAD 台账与 QA 权威根未动。
