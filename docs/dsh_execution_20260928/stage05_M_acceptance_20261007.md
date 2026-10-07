# M01–M03 独立验收与 P 段接续（2026-10-07）

Gate-M **PASS**，M01–M03 完成，进度 **28/49**。独立审查的全部直接、传递读集已释放，接续 P01–P04；后续保留 Gate-P、Gate-G0、Gate-G 各阶段验收。

M01 的具名读取保持原 read-set、原字节和读取额度；跨 session/snapshot/revision、摘要冒充完整材料均拒绝。原 Research 内核晋升后，由原 Python owner 持久撤销旧视图，运行中和重启 Worker 均拒绝旧材料；模型不能发行权限或晋升事实。

M02 实际 SDK 强制 compaction 后，通过 Session 正式恢复 Writer 必需原材料并重新计量。独立 compaction child 不取得事实权限，辅助请求经过原预算与原账本。未声明辅助预算时，实际辅助与末步 Writer 发送均为零，已经发生的费用保留。

M03 实际读取 → compaction → terminal 三请求原账本 usage 51/33，pending 0；完整父子 Session 的自然完成证明使原 owner 释放，新 Worker 恢复新增发送零。累计请求、输入/输出、工具量、时限及唯一 terminal 门均闭合，格式失败、unfinished、research_required 与 unknown 保留相应费用责任。

- [独立验收报告](/tmp/c2p-dsh-independent-m01-m03-final-20261007-01/review.md)、[验证记录](/tmp/c2p-dsh-independent-m01-m03-final-20261007-01/verification.json)、[读集释放](/tmp/c2p-dsh-independent-m01-m03-final-20261007-01/readset-release.json)：3462 个绑定输入，原 complete/cold 严格读取器实际接受。
- [当前完整03回执](/tmp/c2p-dsh-m-stage-admission-20261007-03/receipt.json)：1853 Python + 249 Node + 1 operator，共 2103 项通过；另有 56 Python subtests。原入口 session96522 实际 exit0、已回收。
- [Fresh cold 回执](/tmp/c2p-dsh-m-stage-admission-20261007-03/normal-use-receipt.json)：1 项通过。完整与 cold 同属 plan12、engine `sha256:1bc393db05dfe8e0c15ecab6b4db070fb4f1dd91f5d80ac30ca9aae0c50fbf90`、validator `sha256:a1819d47cf191cf4c3beca3646ee4209927719d22ef51acef9c73d7553b08aa9`。
- [当前四实际入口严格证明](/tmp/c2p-dsh-m-native-unique-nodes-20261007-01/strict-reader-proof.json)：V1、普通多步、强制压缩、未声明辅助预算，4 项通过、节点身份唯一。M-E1 仅修测试名称，原读取器未弱化；历史重复节点报告和中止的完整01/02不作为当前认证。

资格范围是显式 V2 Host API，normal JSON CLI 仍为 V1。此阶段使用隔离假 provider，没有新增 Qwen 请求或修改服务，不代表默认切换、正文 Verified、D5 或发布。Gate-L 原真实兼容验收保留，canonical 后端 EMPTY、13 条严格历史，旧 packet14 UNKNOWN 费用责任不变。

P 段直接实现同主机共享请求调度、显式 requested/effective 限额、固定 wave/join、实际多进程故障与公平性验收。调度只存队列与 permit 元数据，费用仍由原账本裁决；unknown 阻断整个 alias group，槽只能依据可信未发送或真实流终态释放。

## 提交前复核（2026-10-07）

本轮按用户“验收然后提交”的要求复核，确认 Gate-M PASS，提交截至 M 阶段的 DSH 代码、测试、工具链及文档依赖链，共 334 个文件。P01 调度器、后续 Worker/TS 协议修改和 P01 开发记录保留在工作区；共享文件只暂存已验收的 M 版本。

- 原始机器报告由原严格读取器再次读取：1853 Python、249 Node、1 operator，共 2103；cold 1、四实际入口 4。此处复算历史原始证据，没有重跑完整套件。
- 138 份计划测试输入逐字节一致；提交快照的 75 份 validator 来源重算仍为上述 `a1819d47…` 摘要。初次复核的 3462 份绑定输入中，3458 份一致，另 3 份为验收后状态文档、1 份为 P01 新增 validator 注册；该注册未纳入 M 提交。见[复核明细](/tmp/c2p-gate-m-commit-20261007/review.json)。
- 在独立副本 `/tmp/c2p-gate-m-commit-20261007/checkout` 对本次提交快照执行 6 份 M 专项测试，**87 passed / exit 0 / 312.57s**；原 pytest 严格读取器接受机器报告，334 份快照文件未漂移。见[命令与验证](/tmp/c2p-gate-m-commit-20261007/isolated-m-verification.json)、[原始日志](/tmp/c2p-gate-m-commit-20261007/isolated-m-output.log)。

此前在持续开发的共享树执行同一专项，得到 72 passed、15 setup errors，原样保留[失败记录](/tmp/c2p-gate-m-commit-20261007/workspace-focused-attempt.json)。期间 P 开发修改 Worker/RPC 及构建，触发 `composition_source_unstable` / `rpc_schema_mismatch`；该结果不计通过，随后使用上述独立 M 副本完成复验。

保留封存源字节：[暂存格式检查](/tmp/c2p-gate-m-commit-20261007/staged-whitespace-check.json) exit 2，提示两份原始 unified patch 的 8 个空上下文行及 3 处源码/测试 EOF 空行，作为非阻断格式项记录。未修改运行逻辑或既有验收证据。本轮没有新增模型、服务或占用恢复操作。

Git 提交会改变引擎身份；原完整回执继续保留其原 HEAD 和输入绑定。后续 P 阶段以新 HEAD 和实际工作树生成自己的构建、准入及验证证据，再交独立 Gate-P。
