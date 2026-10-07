# 模块级派发候选 Gate-H 独立完整差分审查（2026-10-02）

**裁决：Gate-H CHANGES_REQUESTED；正式 Gate-K 继续等待。** 本审查由当前 Codex chat 执行，未参与窗口二此次候选实现。原第 01 份返回窗口二连续整包返修；窗口一保留已验内核 component，不重跑 4129，不启动第 03–08 份或 live/default/daily cutover。本报告不更改任务台账、owner 接口/证据或候选字节，也不自行放行 Gate-K。

权威证据根：[独立 QA](../../.dsh-dev/run/qa-gate-h-static-entry-20261002-c44c4lep/)。审查输入为本轮完整冻结候选，旧报告按其旧树解释。集中发现见 §3；原三类反例已经关闭，不将其重新登记为未修。

## 1. 绑定身份与审查方法

| 对象 | 实际 SHA-256 |
|---|---|
| 交付 runtime | `392e4acff7b384f94620c450d6f3e220880e8352c8bd89a4ce361f322ca362df` |
| 源码构建 runtime | `301a5e230abc98db00fcf764dbcebdb2a474aa0fefac6c68f60162416abbbfb3` |
| pristine 0.2 runtime | `43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c` |
| 原 0.1.5 开发 runtime | `7e8f199b67027944d646e0c99f5041d4704360377e4d7466fce683c1d468d3ab` |
| 补丁脚本 | `eac2d8c56eca975ec947b9de59fe2b9f46902dde7ffd3c94ed1b9fb98bc53147` |
| 源码补丁 | `30133c39a04d88b7bc2210168e13479580d95417f471085f5662dd06f529eb2a` |
| 交付 build receipt | `352551dba0caab40808f7a285a55243526cb992e3b221261aefa6af6e50a82c3` |
| 交付 staging tree | `904f6ecf75c118928f4934069737a7aca7d4388ed582a00cfff1f83af248c934` |
| build outputs digest | `2aeceb7bbeb5e18a07ed6d4f01bf7b15c32d0cf9d3a846157c593eebebc1b620` |
| 源码构建侧 build receipt | `2d39b94995d3f2bbfddefcef49ce0632b6bcac1bb9be00f27190c9384206e369` |
| 源码构建侧 staging tree | `4900edd001bfa0f426879789ddb59ab37040238706efddbcc69237d685e3d0b0` |

固定源码 commit `4878cdabd87d4041bdaff61d04c966883b9fd07a`。源码补丁逐字节等于四文件实际 `git diff HEAD`；两包源码工作树 JS 与 `-built` JS 同字节，两个候选 JS 也同字节。兼容 JSON 的源码摘要全部匹配，manifest 与兼容 JSON 的 touched 均列齐实际差分的两份 JS 与两份 types。数值身份匹配不证明 types 来自源码，见 GHS-3。

不重新 build/stage、不切换宿主共享 peer。完整原套件沿原 `test_command`/bubblewrap launcher 执行，保留原 11 文件和全部断言。各候选的**实际已冻结 staged build receipt**与 peer 链接仅在独立 mount namespace 内映射到共享 package 的相应路径；工具链其它文件是原安装的逐字节副本。namespace 内原 `toolchain_state()` 与 `verify_staging()` 均通过后才启动原套件。这样源码构建侧 imports 解析到 `-built`，不借交付侧共享链接，不合成新 receipt。映射不修改宿主文件，也没有删除/绕过原 staging 断言。

完整 argv/cwd/candidate/退出码分别在 `.command.json`、`.exit`、`.result.json`；`review_driver.py` 是独立运行器，不能用其外层退出 0 代替 Node 内层退出。两侧探针有分别指向实际 runtime 的包解析链接。

## 2. 新鲜运行结果与完整 AT 覆盖

| 检查 | 交付侧 | 源码构建侧 |
|---|---|---|
| 原 launcher 全 11 文件套件 | 89 pass / 0 fail / 0 skip；Node exit 0 | 89 pass / 0 fail / 0 skip；Node exit 0，完整结束 |
| 新入口差分探针 | 10 项：8 pass / 2 fail / 0 skip；Node exit 1 | 同左 |
| 布尔入口因果负对照 | 2 pass / 0 skip；Node exit 0 | 同左 |
| 注册表销毁/重建探针 | 3 项：2 pass / 1 fail / 0 skip；Node exit 1 | 同左 |
| 原 B02 全目录 | 24 passed / 0 skip；pytest exit 0 | 22 passed / 1 failed / 1 skipped；pytest exit 1 |
| ordinary Web HTTP | HTML 200、非空 JS/CSS assets、关闭后端口关闭 | 同左 |
| compat HTTP | HTML 200、非空 JS/CSS assets、关闭后端口关闭 | 同左 |
| 当前日常安装无 shared inode | 0，实际遍历核查 | 0，实际遍历核查 |
| 只读 doctor | exit 0；隔离与 worker/lock/domain import 通过 | 未重复已明确缺 worker 的检查；不声称 doctor PASS |
| 两包独立声明生成 | 固定源码与锁，实际 tsc exit 0；产物不匹配候选 types | 同左 |
| patch hygiene | `git diff --check` exit 0 | 同一工作树 |

[完整覆盖矩阵](../../.dsh-dev/run/qa-gate-h-static-entry-20261002-c44c4lep/gate-h-at-matrix.json)与[逐测试节点映射](../../.dsh-dev/run/qa-gate-h-static-entry-20261002-c44c4lep/original-at-node-matrix.json)列出实际 89 个源节点及两侧输出匹配，未匹配 0。具体覆盖：

- H01：真实 Loader、缺包/inject/metadata、组成、root/child standing generation、preset 工具入口和会话隔离。
- H02：首请求可信绑定、未绑定零材料/零请求、旧 fence、创建取消、错误 provider 与伪协议标签。
- H03：原 terminal/provenance 完整性、V4 工具结果约束、原始参数来源、损坏拒绝、flush 失败及 partial 不冒充 durable。
- H04：request seam、prepared 配置及单次派发、两个等待点的取消/fence/材料漂移、usage/cap/unknown、同步/异步 cleanup 与有界 return、合法 sibling。
- `joint-child.test.ts:280`：同一真实绑定 child 走 reserve→dispatch→adapter→terminal→settle→flush，再由实际 `spawnSync` 新进程从落盘字节重建 committed；两侧均通过。裸请求不能污染来源。
- B02：全部原 Python isolation/discovery 测试与 Node sandbox/staging 测试；四次真实 HTTP smoke 没有提交模型 turn。源码构建环境的缺项如实失败/skip，不用交付结果覆盖。

原三类反例的独立差分均通过，且各有 prepared 与合法 NO_ADAPTER 正例：

1. public `internal/get` 返回转发 Proxy：真实 resolver lookup、prepareCall 包装均发生；包装检查全部实参，成功 admission 为 0；新 static-import entry 确实存在，旧 symbol export 确实不存在。合法 child completed，R/D/S/受保护 adapter 各 1。没有将旧 export 的 import error 当作攻击受阻。
2. 同步 resolver 观察者：在真实活跃 child resolver context 上，undefined/null/空对象/冻结 snapshot/副本/Proxy snapshot 六种伪造能力均无法 admission；实际调用当前 `runLoopDispatch` 被具名 `dispatch_origin_unproven` 拒绝，合法 child 四项各 1。
3. 自定义 public `Symbol.asyncIterator`：listener、iterator 获取与 next 都无来源；普通额外 provider 确实成功一次。合法 child R/D/S/受保护 adapter 仍各 1；另一个普通 provider 调用单独计量。源码构建侧也通过。

## 3. 集中发现集

### GHS-1 · P1：公开布尔参数可以获得受信派发身份（两侧）

位置：固定源码 `packages/llm/llm/src/index.ts:1243–1249`；Host `integrations/dsh/src/request-accounting.ts:348–354`。

模块级入口做 capability 同一性 admission，但仍调用普通实例方法 `streamWithRegistration(options, prepared, trustedLoopDispatch)`。该方法在 runtime JS 上可由公开服务对象取得；调用方传 `true` 就跳过清空来源，内部没有验证该调用是否经过模块入口。Host 仅凭当前 origin 的 session/signal 判定来源。

独立 `llm/stream` listener 在合法 child 来源作用域内，调用公开取得的服务方法，使用**同一 session/signal、替换 messages、undefined prepared、true**。prepared/fallback 两种合法路径及两侧候选都出现：

- 合法 child completed。
- 攻击流返回真实 mock adapter 的 usage 与 stop，adapter 实际看到替换材料。
- R/D/S/adapter 从应有的各 1 变为各 2，额外请求成功结算。

不是漏记账的证明，而是**非 loop 请求被错误授予 loop 来源且可发送任意替换材料**的证明。相同材料分别走 `llm.stream`、`streamWithRegistration(..., false)`、`runLoopDispatch(..., snapshot)`，均具名拒绝，合法四项仍各 1，锁定第三参数为因果差异。

证据：`*-capability-boundaries.log` 的 `prepared-boolean-seam`/`fallback-boolean-seam` 与 `*-boolean-seam-controls.log`。修复必须让受信身份在 runtime 内不可由公开调用参数声明；仅把 TS 方法改 `private` 不会隐藏 JS 方法，不能关闭本项。保留正例与上述因果对照，不改变 Host/Python 权威或材料义务。

### GHS-2 · P1：已销毁 runtime 永久残留，合法新 deployment 回落失败（两侧）

位置：固定源码 `packages/llm/llm/src/index.ts:72,123–125,446–449`。

新模块私有 Set 只在构造时 `add(this)`，没有关联真实 service/deployment 销毁的注销路径；`singleLoopRuntime` 按 Set size≠1 fail-closed。

独立使用真实 Loader 启动 deployment A，先验证 prepared/fallback 均 completed、四项各 1；正常 dispose root 与 `deployment.fiber`，再以独立唯一 session ID 启动 deployment B。B 的 prepared 正例仍四项各 1；合法 NO_ADAPTER 回落却 error、R/D/S/adapter 全 0。两侧一致。

证据：`*-registry-lifecycle.log` 的 `initial-control`、`fresh-prepared`、`fresh-fallback-after-disposal`。不得通过移除 size 门、任选一个实例或无差别清空其它活跃实例来修复；须让注册归属/生命周期正确，完整保留 fail-closed 与合法回落合同。本测试是普通销毁/重建，不是攻击者故意同时注册两个活跃 runtime。

### GHS-3 · P2：源码构建 types 来源不成立，当前证据文本仍有旧值

两包各使用固定源码自带 TypeScript 执行 `tsc -p <原项目> --outDir <fresh /tmp> --tsBuildInfoFile <fresh /tmp> --emitDeclarationOnly`，未写源码工作区。实际退出均 0；分别保存 231/359 个声明编译依赖的 before/after，全部未变。独立产物分别逐字节等于源码工作树现有 tsc 声明，但**两个候选的声明都不同**。

LLM 声明的独立摘要 `b83da4bf02698a6c563c11d59f9e499905e6c307e7f5b43d9e299fd6bf3da25f`；候选摘要 `58babc840059bfd1e5632c955eef3f5c17fc9d19f69b038a60e8c1f249788d71`。源码生成声明公开列出 `streamWithRegistration(..., trustedLoopDispatch?: boolean)`，候选却仍为 `private streamWithRegistration`，属于可见性/接口差异，不只是布局。

agent-loop 独立声明摘要 `a3509f051a061ee2c6d6c7ac2fbf8f7d4a4acbce34dcfff9138557a84d7f2d40`；候选摘要 `c5b2ae00736e404bd57653782d2b872b4b81fdee682908334b31e0f642f62af3`。

证据：`independent-types-parity.json`、各 `*-independent-tsc.command.json/.exit` 与声明 `.diff`。当前只能证明 JS 来自这份源码输出；不能认定 `-built` types 是此固定源码的 tsc 输出。若存在合法后处理，须明示并交付可复现的转换、输入/输出身份；不能把手工 hunk 声明称为未经转换的源码编译产物。

此外，CAP-2 的当前数值表和 JSON 已匹配，但全文历史绑定仍未完成：`interface-diff.md:35,39` 的当前源码构建段落还写旧 patch `419d5a8d…`/旧 built tree `7ae6af55…`，§3/§4 仍描述已删除的 take/entry-ack 与公开 llm.stream 回落；`evidence.md:57–68` 将旧 receipt/stage 与 87 项列为本轮实测并指向 `w2-lo-repair3`，`:121` 仍把删除的 `takeLoopDispatchEntry` 当当前唯一有状态导出。须明确绑定旧树的历史段落或更新当前 API/证据，不能只更新顶部表。owner 原文未被本 reviewer 改写。

### GHS-4 · P2：源码构建环境不具备完整 B02 验收条件

实际运行原完整 B02 目录得到 exit 1、22 passed/1 failed/1 skipped。失败节点为 `test_python_worker_environment_matches_its_lock`，该侧缺 `pyworker/bin/python`；`test_python_worker_drift_is_refused` 因同一缺项 skip。没有安装/借用交付侧 worker、删除该测试或把 skip 计为 PASS。

交付侧 24/24 与只读 doctor 成立；源码构建側的完整 Node 套件与两种 HTTP 也成立。这些不能代替该侧 worker/lock/domain import 与 drift 拒绝证据。若该候选只声明 runtime 等价验证范围，应明确收窄**声明**，不声称两侧完整 Gate-H/B02 均通过；要满足本次要求的完整双侧矩阵，则由 owner 补齐冻结环境后再验。证据：`*-built-b02.log/.exit/.result.json`。

## 4. 准确命令、夹具纠正与实际边界

独立命令入口（所有 nested argv/cwd/实际版本保存在对应 command 文件）：

```bash
python .dsh-dev/run/qa-gate-h-static-entry-20261002-c44c4lep/review_driver.py '/home/cuihengjia/agent/Code2Paper copy/.dsh-dev/run/qa-gate-h-static-entry-20261002-c44c4lep' suite 0.2.0-rc.1+loop-origin.1
python .dsh-dev/run/qa-gate-h-static-entry-20261002-c44c4lep/review_driver.py '/home/cuihengjia/agent/Code2Paper copy/.dsh-dev/run/qa-gate-h-static-entry-20261002-c44c4lep' suite 0.2.0-rc.1+loop-origin.1-built
```

两侧各执行 `probe <candidate> capability-boundaries.test.ts`、`registry-lifecycle.test.ts`、`boolean-seam-controls.test.ts`；`ops_driver.py <candidate> b02/web/compat` 两侧全部运行，交付另执行 `doctor`。Python AT 的实际 payload 为 `python -m pytest -q -p no:cacheprovider integrations/dsh/dev/tests`，未改变测试集合。`types_audit.py` 保存两个实际完整 tsc 命令、锁与编译器版本/摘要；`final_audit.py` 派生身份与 89 节点矩阵。`git diff --check` 实际 exit 0。

初期 QA 夹具/执行环境错误均不计产品发现：外层 sandbox 禁止 bubblewrap NETLINK_ROUTE，改在获准执行环境中使用原离线 namespace；过窄 QA run-root 与原 sandbox 断言不符，恢复原要求；peer namespace 的 compiler symlink/候选选择/receipt view 前置纠正；同步 resolver 观察者改用真实 child resolver context；重建 fixture 重复 root ID 改为每代唯一 ID；smoke 显式选择目标候选。初始反例/套件/registry/smoke 文件与日志保留，后续正结果不倒改原失败。早期 preflight 错误以工具输出及本段为界，没有把所有前置失败包装成完整产品运行证据。

仅新增独立 QA 夹具/运行证据与本报告。Node fixtures 在 launcher 准许的 writable run root 创建各自新目录；owner source、原测试、runtime、共享 peer、build/stage、接口/证据文档、Python kernel/validator、台账均未修改。没有运行 pnpm install、完整 host rebuild、live API、4129 或后续文档实现。

## 5. Freeze → review → release

主 before/after 共 1134 个输入字节/metadata 完全相同，四 runtime inventory 与 manifest 摘要相同，宿主共享 peer 链接未变；额外补入 6 个真实 staging/toolchain receipt 的独立 before/after 也未变。声明编译依赖 separately bound，未以主 snapshot 漏含依赖冒充绑定。

791 份历史内核 source/test 摘要匹配，14 份 owner 封存文件摘要匹配，上轮 QA 根未改。CAP-3 原残留验证不再占有受测读集，最终宿主全局相关验证进程为 0。

[正式 release](../../.dsh-dev/run/qa-gate-h-static-entry-20261002-c44c4lep/closing_release.json)时间 **2026-10-02 22:10:34+08:00**：全部测试命令已经返回，真实宿主扫描 1778 进程，相关验证 PID 0、不可读 cmdline 0。第一次在外层 sandbox 只能看到 2 个 PID 的 close 未被接受为全局释放，原记录另存并纠正；最终在宿主进程视图重新核查才正式 release。只记录 PID/数量，不保存可能含凭据的进程命令行。

本报告写入发生在产品读集释放之后，新增报告不反写 before/after。不改历史台账或宣布任务 done。窗口二接回原第 01 份整包，连续修受信入口封闭、实例生命周期、源码产物与全文身份/环境，保留全部原 AT 和本批正反对照；稳定冻结完整新候选后再触发独立差分审查，不逐发现申请权限，也不以单个 helper 绿灯放行。

窗口一保持已验 component。只有实际独立 Gate-H PASS 后，LEAD 才能复核并释放正式 Gate-K，再启动原第 03 份 I01→C01→C00→C02→C03→C04；窗口一为 sole Python/validator writer，窗口二为 C00/TS wire/sole build-stage；Gate-C 后第 04 份。当前全部保持原门与依赖。
