# loop-origin.1 独立差分验收与集中返修（2026-10-01）

**Gate-H：CHANGES_REQUESTED。** 新候选已实际落地并恢复合法 child；原 H-R4 公开
prepareCall 抢票变体独立通过，不能再使用“所有合法请求也拒绝”的旧状态。
新增普通公开调用、公开 NO_ADAPTER 语义及旧 manifest 兼容回归仍阻断本阶段。
源码、类型和私有消费接口也未兑现 [LEAD 裁决 §6](h04_loop_origin_escalation_20261001.md)。
内核 component PASS 保持；正式 Gate-K 和第03/04份仍等待 Gate-H。

LEAD 没有参与实现，本批只读验证候选、编写独立 QA 夹具和裁决记录；未改产品源码、
产品测试、peer、build/stage、runtime、Python validator 或原 owner 日志。
用户所述后台完成通知已经消费，本批不重新处理那些任务。

## 1. 环境、身份与有效进展

仓库 `/home/cuihengjia/agent/Code2Paper copy`；分支 `codex/agentic-p4-benchmark-cutover`；
HEAD `d48b4e4b22c94c82b45d2179ba452d72b164102d`。保留现有 dirty 工作树。
Python `/home/cuihengjia/miniconda3/bin/python`，Node 25.8.2/npm 11.11.1，沿用现有锁。

| 对象 | 本批实际身份 |
|---|---|
| 候选 ID | `0.2.0-rc.1+loop-origin.1`；上游版本仍 `0.2.0-rc.1` |
| 新 runtime 树 | `1e0e6fa28c93bca5d551299617247bcf319cab73cf7a0f12fdda3250f6536ac6` |
| 原 0.2 基树 | `43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c` |
| 旧默认 0.1.5 树 | `7e8f199b67027944d646e0c99f5041d4704360377e4d7466fce683c1d468d3ab` |
| request-accounting.ts | `1bc8d00b0ad81464bd12712fcabffb19f09d959d740764dd3a4d0fb8900d2455` |
| patch 脚本 | `26d1d835b18a2c817c98f95d9d749e2cbd3e5305c04c4f0ebedeac2cb21636c4` |
| build receipt | `b01543a96e4c9c470cdeb7528fadea1869dbf374df365eae4d8c602f765efb14` |
| build outputs | `68260b9d141f3c79654a60397fdef6e49b24082b8adf4475c281b34c74fa6f73` |
| staging tree | `241639f92c6617edbce649ed4899efadfafd289687a9395cc43bb2e8f90d5cbf` |

peer 实际指向新候选。新/基树各26149条，旧默认25478条，完整树独立复算并匹配。
本地 runtime 相对基树只改变 agent-loop/llm 两份 `lib/index.js`；类型文件没有变化。
旧环境文件未改，但新 launcher 拒绝其旧 manifest，见 LO-3；字节保护不能替代入口兼容。
日常 0.1.7 不在本批写入范围；历史安装前 hash 缺失仍不倒填。

| 验证来源 | 结果和边界 |
|---|---|
| owner 完整 check:compat | 原日志84 pass/0 fail/0 skip，退出0；不是独立 Gate-H PASS |
| owner B02/doctor | 原日志23 passed、doctor exit0；本批核对交付身份，未重复 B02 全目录 |
| 独立原11文件 | 83 pass/1 fail/0 skip，exit1；唯一失败是 QA 的 RUN_ROOT 与原环境路径断言不一致 |
| 路径断言纠正复验 | 只重放原 sandbox 文件，原 launcher 环境2 pass/exit0；不改原 exit1，不再跑已通过83项 |
| 独立原 H-R4 | 1 pass/exit0；32次公开 prepareCall 都拒绝，合法 child completed，R/D/S及adapter各1 |
| 独立新增功能探针 | 0 pass/2 fail/exit1；LO-1和LO-2各有合法对照和实际失败 |
| 独立旧 launcher 读取 | 默认0.1.5、原0.2拒绝；新补丁候选通过，具体异常见 LO-3 |

独立节点使用原 `scripts/dsh_dev.py` 的 bubblewrap/断网/只读 runtime launcher；没有裸跑或
live。首次 NETLINK 沙箱拒绝、QA 路径失败和 closing driver 语法失败均单独保留并纠正，
不是产品缺陷，也不改写真实退出码。新日志只脱敏临时本地 Web token。
原套件中的合法双 child、等待/取消/清理、terminal/flush及同 child 新进程恢复成功证据保留。

## 2. 一次集中反馈：原 owner 连续修复

### LO-1 · 普通公开派发继承 ambient 来源后被误拒（B02/H01/H04）

在真实 protected child 的 `llm/stream` listener 内，通过公开 API 请求另一个普通 mock
provider，不声称 protected session。三条入口为 `llm.stream`、预先取得的 prepared handle、
当场公开 prepareCall 返回的 handle。它们在 loop 外有成功对照，在 loop 内均抛
`DISPATCH_ORIGIN_CONSUMED`，普通 adapter 只收到外部对照一次。原合法 child 仍 completed，
protected R/D/S/adapter各1，故不是绑错 child 或挂起的夹具。

实际补丁把 ALS 留在全部 listener/iterator 执行中，再在公共 admission 以“已有且消费过”
全局拒绝。它没有兑现 §6.2-2 的公开入口隔离，也与接口差分所称“普通公开流量不受影响”矛盾。
修复须让所有公开等价入口隔离外层 loop 来源，同时保持受保护冒用零 reserve/adapter、
真实内部 prepared/fallback 合法一次及原注册/config/单次派发约束。

### LO-2 · 公共 prepareCall 改了 NO_ADAPTER 语义（H04/接口兼容）

原 owner 的真实 adapter 在 prepare 时抛一次 `LlmError(..., 'NO_ADAPTER')`。
公开 `prepareCall` 现在返回 fallback handle，不再原样拒绝，探针 `errorCode=null`、
`returnedHandle=true`。§6授权的是 loop 内部可信回落，不是全局改公共准备语义。
恢复公共 API 的原拒绝；内部回落单独持私有来源并保留合法回落/真无adapter对照。

### LO-3 · 新字段变成旧 manifest 的强制门（B02）

`read_manifest` 对所有版本无条件要求 `upstream_dsh_version`。未修改的默认0.1.5及
原0.2 manifest 都没有该字段，真实调用分别报：
`manifest upstream version None does not match candidate '0.1.5-rc.3'` / `'0.2.0-rc.1'`。
本地补丁候选通过。不能修改旧 manifest 或重封旧 runtime 来遮蔽此回归。
旧格式沿原 version/lock/CLI/完整树严格校验；补丁格式再要求其 source/base/patch/ABI身份。
保留 flag/env/root 不一致、缺新身份、错误版本和字节漂移的拒绝。

### LO-4 · 私有来源与源码/types交付未按原裁决兑现（H04/冻结接口）

patch 直接替换 npm 的两份编译 JS，没有交对应固定源码补丁、runtime 原生构建与类型差分。
新增三个 JS 导出均不在实际包的 `lib/types/index.d.ts`；Host以unknown断言读取新接口，
原 typecheck 通过不能证明该新 ABI 有真实类型合同。agent-loop 还公开导出了
`consumeLoopDispatchOrigin(request)`，与 §6.2-3 禁止公共consume的明确要求不符。
本批没有把这一静态合同差异宣称为已证明的新抢票漏洞。

按 §6.3 在对应固定 monorepo 源码及锁上完成窄改、声明类型和可重建产物；一次性消费留
runtime私有域，公共面只提供不可变核验。公开/src通配导出不泄露mint/run/consume；缺 ABI/
版本/实例明确拒绝。保持原基树、旧开发和日常环境；无法构建时交具体缺口，不能自行将
“编译JS hunk可重复”替代已裁决的源码交付。源码或接口必须扩域才需要一次实质裁决。

交付附带校正：`evidence.md`九行业务文件合计78，尚需列出另两份toolchain文件的6项，
才能对应真实11文件84项；所称cancellation/joint分文件日志不在 `w2-lo-final/`，可引用
完整日志中的实际节点或给出真实路径。完整84日志真实，不为补表重复测试或编造日志。
保留首次失败、历史接口身份和本次候选。

## 3. 给窗口二的完整接续指令

先读[仓库入口](../README.md)、[执行入口§3.11](README.md)、[台账](task_board.json)、
[第01份](01_baseline_and_dsh_compatibility.md)、[裁决§6](h04_loop_origin_escalation_20261001.md)、
[验证§14](verification.md)，再核本批新候选及本人责任路径。你仍独占原B02/H01–H04、
窄 runtime 来源源码、TS/peer/工具链/build/stage与新候选；LEAD不替你修产品。

```bash
cd '/home/cuihengjia/agent/Code2Paper copy'
export C2P_DSH_CANDIDATE='0.2.0-rc.1+loop-origin.1'
export C2P_DSH_DEV_ROOT="$PWD/.dsh-dev/candidates/$C2P_DSH_CANDIDATE"
```

本批 QA 读集已明确释放，直接在新鲜 rework 子根连续完成整包：
LO-3旧格式兼容 → 窄源码/私有来源/类型与公开入口隔离（LO-1/2/4一起）→ 原公开抢票与
普通公开 API 正反例 → 受影响等待/abort/fence/兄弟/清理及同child committed/新进程恢复 →
一次稳定目标 check:compat、原B02目录、doctor与原AT映射 → 统一冻结身份/写权释放。
顺序可按依赖调整；普通问题自主修复，不逐缺陷或测试等派工。

保留84项有效实现者记录、本批所有反例和原日志；正式Node仍隔离launcher的node --test，
不是vitest。共享peer只由你切换，只构建stage补丁候选，不重封原0.2/旧0.1.5，不触碰日常
0.1.7、Python内核/validator或LEAD台账。无reset/clean/换分支/commit/merge/push/live授权。
完整新候选再一次独立差分验收；QA不驻留等待。

## 4. 给窗口一与后续阶段

保管第02份已验内核和已交付复用清单。本批791条Python源码/测试和六份原内核运行文件
与已验快照一致；四个关键owner身份也一致。保留4129/3live skips/12subtests与component
PASS，不重新调查、不重跑全量，不改publication_method_writer/validator或创建C/R模块。
实现者记录“其他窗口可开始第03份只读准备之外工作”不能代替LEAD的实际Gate-H/K放行。

Gate-H满足后再裁定正式Gate-K，按原第03份 I01→C01→C00→C02→C03→C04 整包连续推进；
窗口一唯一Python/protocol/validator owner，窗口二C00/TS/唯一buildstage。再按第04份
R01–R04→V01→A01→V02做单run、串行、单Writer真实DSH mock。原8文档/49任务/AT不减少，
唯一builder/parser/assessor/账本/publication/registry/index继续复用；live/全文事务/默认切换后置。

## 5. closing 与明确释放

仓库可读独立证据根：
`.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1/run/qa-loop-origin-awkji3_e/`。
`inputs_before/after.json`绑定912输入及三棵完整runtime树，字节/mtime/inode/size与peer均未变。
精确读集在该清单；逐命令argv/log/.exit、独立probe、机器观察与纠正记录均保留。
宿主 `/proc` 独立检查1750进程，相关QA/候选CLI/仓库验证进程0、不可读0；3条进程在扫描中
正常消失。普通沙箱的空命名空间检查另存，未用其推定释放。

**LEAD于2026-10-01T19:40:04.447992+08:00明确释放本批实际读集。** 全部本批命令均已
返回、无pending输出；不是从idle或超时推断。窗口二直接接回上述写权，窗口一保持已验
候选；原release/报告不覆盖。以下LEAD文档/台账更新在释放后进行，不倒称其属于未变受测输入。
