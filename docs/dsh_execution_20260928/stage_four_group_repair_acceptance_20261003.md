# 四组返修独立验收与阶段接续（2026-10-03 18:03）

**独立裁决：Gate-B / Gate-H PASS，上一轮四组返修关闭。** 本次未发现该冻结范围内的新阻断项。随后按既有内核独立验收、791 份未变输入和已经满足的 H03/H04 前置，完成 **LEAD 正式 Gate-K 登记**。第 01、02 份收口，第 03 份具备实施前置；本轮没有实施第 03–08 份。

对应 owner 提交：[四组返修批次](../../integrations/dsh/dev/gate_h_repair_batch_20261003.md)。前一独立裁决：[16:05 四组修改要求](stage_whole_package_review_20261003.md)。持久核查数据：[本次 JSON](stage_four_group_repair_acceptance_20261003.json)。历史报告继续约束各自的代码、输入与协议，不改写为本次结果。

## 1. 四组逐项裁决

| 原问题 | 本次独立证据 | 裁决 |
|---|---|---|
| QA-20261003-ACTIVATE | 未修改的 Node 入口与 Python CLI 使用真实冻结 runtime 的只读视图、真实安装工具链的临时副本。编译器/锁漂移、active/target 缺回执、错误 Node 版本/缺可执行文件/同版本不同字节 Node、错误 runtime 和候选身份共 18 次拒绝，链接及两份回执保持。合法两方向切换后 verify 均通过。注入回执 rename 失败，实际观察 peer 提交→回执失败→peer 回滚。原漂移在 activate 后仍被 verify 拒绝。 | PASS |
| QA-20261003-AUDIT | 原独立 CLI 对照保持：合法包 exit 0；漏新增声明 exit 1；同一漏声明且 pristine base 缺失仍 exit 1。B02 原目录实际执行 production setup/audit，覆盖少/多文件、缺 base/manifest、错 base/候选/receipt；setup 的 provisioning、audit 的 staging 仅在该聚焦夹具中替代，最终真实 doctor/audit/staging 另验。 | PASS |
| QA-20261003-SMOKE-IDENTITY | 未修改的正常 web/compat 脚本均 exit 0，HTML 与非空 assets HTTP 200，关闭后端口关闭、零模型 turn；输出正确非空 runtime/staging/build receipt。另运行仅环境选候选、不传 evidence-dir 的真实入口，产物落到候选默认证据路径的临时挂载，旧默认 smoke 文件不变。 | PASS |
| QA-20261003-DELIVERY | 当前交付与历史 92/24、round9 93/26 分开，旧日志缺失明确记录；当前 API、source 模块头及 source patch 一致。201 份封存登记项逐一校验。108,615 项 owner 输入前后无差异；归档 108,990 个成员逐个核字节/链接，含 52 个经内容验证的 tar 硬链接，无缺失或不匹配。93 个原源测试节点均在两侧日志出现，未匹配 0。 | PASS |

激活独立对照共记录 28 条实际命令，包含正例、18 次 Node/CLI 拒绝、漂移前后 verify 和提交失败；不把这些命令计成额外产品测试数量。所有错误注入仅发生于临时副本或只读 namespace 覆盖视图，原候选没有被修改。

源码构建候选继续只声明“源码等价证据”，不声明该侧 B02/doctor 或独立 worker 验收。

## 2. 本次实跑与保留证据

| 范围 | 本次观察 |
|---|---|
| 原完整 launcher 集合 | 两侧各 11 文件，93 passed / 0 failed / 0 skipped，内层 Node exit 0；原断言未改 |
| 原独立来源边界 | 两侧各 10/10，exit 0；prepared/fallback 合法派发、resolver Proxy、伪能力观察、iterator 获取/迭代和公开布尔入口均复验 |
| 原独立生命周期 | 两侧各 3/3，exit 0；销毁 A 后新建 B 的 prepared/fallback 均 completed，reserve/dispatch/settle/受保护 adapter 各一次 |
| B02 原 Python 目录 | 48 passed，exit 0；包括真实入口修改后的拒绝及正常行为 |
| 执行身份原集合 | 24 passed，exit 0；不扩大成全部业务恢复验收 |
| 正常 doctor / audit | 交付候选真实入口 exit 0，worker 导入、隔离、最终 peer 和组合就绪成立 |
| 正常 smoke | web/compat 及环境选择＋默认输出的补充对照均通过；CLI 会写的 profile 仅映射到同字节临时副本，证据字段由原脚本生成 |
| 类型和源码 | 四棵 runtime 与前一独立审查同字节，三份 d.ts 与固定源码产物及两候选相同；保留前一轮独立 tsc 结论。本轮核对 owner 新 tsc 的 257/385 输入前后清单、封存日志及归档；未重复声称自行重跑 tsc。当前 source patch 与固定工作树四文件 full-index diff 完全相同 |
| 构建/staging | 实际 staged 文件与 source/config/build receipt 成组匹配；两侧原测试都先通过真实 toolchain/staging 校验。未 build/restage 或切宿主 peer |
| 内核 | 与原独立验收清单比较，791 份 src/tests 全匹配；保留 K01–K04 component，没有重跑历史 4129 |
| 补丁卫生 | `git diff --check` exit 0 |

H01 的 Loader、composition、generation/销毁与正式工具入口；H02 的创建期绑定、归属、旧 fence/provider 拒绝；H03 的 raw/V4/schema/terminal、flush 与新进程从落盘重建；H04 的完整材料、回执、两等待点、取消/资源及同 child 接线，均按原 AT 和原测试节点判定。矩阵见核查 JSON 及原始根的 `gate-h-at-matrix.json`、`original-at-node-matrix.json`。

## 3. 接受的开发候选身份

分支 `codex/agentic-p4-benchmark-cutover`，HEAD `d48b4e4b22c94c82b45d2179ba452d72b164102d`；既有 dirty 基线保留。

| 身份 | delivery | source-built |
|---|---|---|
| candidate | `0.2.0-rc.1+loop-origin.1` | `0.2.0-rc.1+loop-origin.1-built` |
| runtime SHA-256 | `671daa1a7a06728d69a4bdec6da3d33a3616c4e788f63579ed07f3ae81e0e16c` | `3076d2fcdbf6b2b49167e8132ce9b5801d95079a36f9bd05af17302e8482be97` |
| staged build receipt SHA-256 | `b6d57b715301ca503be7afa8eec3339cb734545f9edfcff17c31e977b59b6c86` | `3993378a51bcbd4d4c19f5a19dca2b8a3e7c2f511b3b8174833e0b1bec192c91` |
| staging SHA-256 | `30f18c5f31ed58a302c22d1996c699b45d2ab565325a57f92b1e8e9d50bfad98` | `15bc87da05654b625f9c430830a41371a300a0b7e96d9d3007b0ff66d8c6e631` |

共同 outputs digest：`9c00688b090ab3bb744ba83975e5ab447fe75fd61798906d15ba13fa4e750e95`。
runtime patch：`b36b887fc71e90de84080897169f79bddf370793a293ca1e54c03fbcb02c8e75`；source patch：`87941d847abb581abe65a924773b980b702b95f03cda4a23831bba9cce3bb46b`。
最终共享 peer 与 global build receipt 属于 delivery。旧默认 runtime、pristine base、日常安装保护范围保持；本裁决确认显式开发候选，未改变产品默认流程或日常安装。

[H02 接口冻结记录](h02_interface_freeze_020.md)由 reviewer 在读集释放后登记当前接受身份，旧第九轮表格保留历史范围。owner 的 sealed status 仍保留 submitted_for_independent_qa 原字节，独立裁决另记于本报告和台账。

## 4. Gate-K 登记与下一阶段完整安排

本 chat 在独立 H 验收完成后作 LEAD 衔接登记：原 K01–K04 独立结论已为 component PASS，台账 `remaining_by_task` 全空，B01-D1/K04-G1–G7 已关闭；791 份输入未变。现在 Gate-H、H03/H04 已满足，K01/K04→K02→K03 的正式完成前置闭合，**Gate-K PASS**。这是对已验成果的正式登记，不是新的全量内核测试或全文产品验收。

49 项台账更新为 **11 done / 0 in_progress / 38 planned**。新增完成的是 B02、H01–H04、K01–K04；原 B00/B01 保持。原依赖、AT 与后续 38 项任务内容不变，第 03–08 份没有因门通过而自动变成已实施。

下一实施批次为[原第 03 份](03_writer_contract_and_worker.md)，按以下一整阶段推进：

1. **I01**：绑定实际 Loader 解析的 JS、DSH 运行树、Node、锁、schema/renderer/config；覆盖源码未变而构建/依赖/链接目标变化。同步原 validator 来源清单，只登记已经实现的裁决文件。
2. **C01 → C00**：先定唯一 WriterTaskContract 与 Python/TS wire 合同，再完成真实 renderer/无模型准备握手；隔离假 HTTP/SSE 验最终请求投影与计量，投影无法证明对应时不得进入 C02。
3. **C02 → C03 → C04**：复用原 owner 抽纯 prepare/parse，再做可信 raw ingest 和幂等局部事务，最后通过真实 worker 完成有界、最小权限的无模型往返。三条消费路径结果一致，跨 task/epoch、伪造接受、错误来源和坏协议均拒绝。
4. **窗口一**负责 I01/C01/C02–C04 的 Python、领域验收与 validator 来源清单；**窗口二**负责 C00 renderer、TS wire/consumer 与唯一 build/stage 操作。共享 `protocol.py` 和 `authoring_execution_identity.py` 由窗口一单写，窗口二交接口需求；共享 peer/lib 操作串行。
5. 阶段内沿本地合同连续推进，最终交 I01、C00–C04 全部原 AT、跨语言/真实 worker 联合证据和冻结输入，独立验 **Gate-C**；之后才进入第 04 份。沿用[集中指导 §5–§10](remaining_work_and_batch_repair_guidance_20261003.md)的其余 38 项安排，不重做已验 kernel，也不提前伪造 R 阶段 claim/reserve 成功。

本次未启动模型 live、并发运行器、全文默认切换、D5、rollout 或 release freeze；这些仍按原阶段和独立授权边界执行。

## 5. 原始证据、运行边界与释放

本次独立根：`/tmp/c2p-gate-h-four-review-20261003-ciy9r4fd/`。owner 稳定封存根保持 `.dsh-dev/run/w2-gate-h-repair-20261003-final-r2/`，归档 SHA-256：`49d0c2ba3c3264fc9cdb49d7083f62b358346615a92eb05d5c947427d6dd0a73`。

实际主要入口：

```text
review_driver.py <QA根> suite <candidate>
review_driver.py <QA根> probe <candidate> capability-boundaries.test.ts
review_driver.py <QA根> probe <candidate> registry-lifecycle.test.ts
ops_driver.py <delivery> b02 / identity / doctor / web / compat
activation-complete-fixture/ops_driver.py <delivery> activation-independent
audit_failure_probe.py
smoke_default_route_probe.py
input_audit.py owner / archive / before / after
```

`*.command.json` 保存具体 argv/cwd/候选选择，`.exit/.result.json/.log` 保存内层退出与原始输出。原 stage/peer 只读 mount 视图保持项目自身断网隔离；所有产品修复反例都同时核对合法控制，未以自定义脚本改写生产结果。

如实保留 reviewer 设置诊断：归档检查器最初未识别 tar 硬链接，补目标字节验证后全部一致；独立激活临时 CLI 夹具缺 home/profiles，被就绪门正确拒绝，新的完整只读 profile 夹具通过原断言；source patch 首次比较使用短 index，改为交付采用的 full-index 格式后同字节。这些均未改生产实现或弱化断言。普通沙箱只有三个进程的视图未用于全局释放，最终使用宿主视图核验。

**正式释放：2026-10-03 18:03:42+08。** 主读集 109,796 项 bytes/link/inode/mtime 前后一致；补充 3 份实际验证 driver 前后一致；四棵 runtime 与 manifest、原 source/tests、peer、两侧 stage/receipt、owner 封存均保持。宿主扫描 1765 进程，相关验证 PID 0、不可读 cmdline 0，已启动命令全部返回。

上述读集释放后才写本报告、H02 接口冻结、导航和任务状态。生产代码、原测试、候选及 owner 封存保持未改；没有安装、原包重建、Git 提交或合并。
