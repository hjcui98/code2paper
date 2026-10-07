# Stage03 · I01/C01/C00/C02–C04 待独立 QA 交付索引

> 后续独立裁决（2026-10-03 23:03）：[Gate-C CHANGES_REQUESTED，三组集中返修](stage03_gate_c_review_and_batch_repair_20261003.md)。下文保留 r2 owner 提交及其冻结身份；原封存包不改写。当前返修范围、全部反例、两窗口指令及新交付条件以该裁决为准。

本报告由窗口一汇总，窗口二负责 C00/TS 和唯一 typecheck→build→stage。
状态：**submitted_for_independent_qa**。r2 已完成冻结验证和封存；Gate-C 尚未独立裁决。
最终状态/组成/命令结果以外部 delivery-index.json 为准，预分配封存根：
`.dsh-dev/run/stage03-w1-20261003/final-delivery-r2/`；窗口二根为
`.dsh-dev/run/stage03-20261003-w2/`。原 Gate-H/K、旧 compatibility.json 与旧冻结包不改写。

## 实现与合同

| 单元 | 实际实现 | 验证入口/断言 |
|---|---|---|
| I01 | authoring_execution_identity.py、runtime_inventory.py、scripts/dsh_dev.py | test_composition_identity.py：实际 JS/peer/Node/renderer、依赖/链接/Loader位置漂移、缺源、validator变化、混合快照拒绝；真实 prepare 每次复算 full composition |
| C01 | protocol.py、writer_contract.py、wire-v1 导出；窗口二 wire.ts | test_wire_schemas.py / wire.test.ts：原字节 Unicode/null/union/extra/重复键/有限数/安全整数/严格数值词法，Python canonical 与 raw wire 身份分离 |
| C00 | 窗口二 writer-request.ts、stage03-project.mjs | writer-request.test.ts：公开 assemble/render、真实 loop、真实 pi-ai 假 HTTP/SSE 三层逐项等价；prepare发送0；cap/材料变化重取引用；动态内容拒绝 |
| C02 | section_writer.parse_publication_writer_response、publication_method_writer本地settlement、facade.py | test_writer_prepare_ingest.py：三路径正文/metrics/失败一致，合法非空atom/target+完成Formalizer技术页，无atom作者页；heading/extra/formula/atom反例；零 Python LLM/网络哨兵 |
| C03 | artifacts.py、result_ingest.py，原publication owner/reader | test_result_provenance.py：真实raw/normalized/parsed/prose分层、绑定/来源/完整流/Host补词拒绝、授权先缓存、新作用核revision/fence、同epoch唯一终态/合法丢回包恢复、same-generation读回 |
| C04 | worker.py，private stdio JSON-RPC2 JSONL | test_worker_protocol.py：真子进程、有界1MiB帧/64KiB chunk、allowlist/路径/scope/坏键拒绝、慢provider不占RPC、独立取消/cleanup；R claim/reserve/dispatch/settle unavailable |

新增裁决来源与共用原 owner/schema 都进入原 VALIDATOR_BUNDLE_SOURCES。Formalizer包按原adapter逐包比较，
不是“有一个accepted包”就接受任意公式。无模型准备不移除原语义义务；局部正文只保留 pending_validation，
不设置 candidate_complete、verified_complete、publication_ready，也不冒充最终全文Binder。

## 必需联合演示与精确证据

最终 delivery-index.json 索引：技术页、作者页、cap4096→1024原owner重编与新投影、协议/来源/冲突/
丢回包反例，逐项列输入/结果摘要、真实argv/cwd/runner/退出、原始日志、raw wire/Session/绑定、
worker transcript、K02 generation 和原reader成员。最终实物以索引的冻结路径为准，开发 joint-1…6 /
author-1…2、cap-recompile-1 只证明各自旧输入，不复用为修复后的新身份。

假服务声明 UTF8 byte-id tokenizer；没有把这个计量或SSE usage当真实DeepSeek/Qwen测量。
整批仅隔离 `bwrap --unshare-net` namespace 的本地假HTTP/SSE；8006与外部provider未调用。
Host调用上下文明确 stage03-controlled-context；真实parent/child创建与Session标识均来自native路径，
不声称 R01持久claim、R02预算reserve或R03完整生产pump完成。

## 封存和复验边界

先冻结当前源码/测试/fixture/driver/schema/实际运行字节及组成，再生成该读集的证据。
原始运行根 `/tmp/c2p-stage03-w1-20261003/`；隔离联合共享根位于候选run目录，不能依赖私有/tmp跨namespace共享。
封存包含前后身份、源码/运行字节清单、每文件SHA-256/长度、实际command元数据和脱敏日志；
URL token/凭据不入包。正文/acceptance/authorship/raw/provenance由原owner同代发布并由原reader验证。

最终读集释放后可更新本报告/任务表/兼容状态；这些文档更新会改变当前engine摘要，必须明确与测试冻结身份区别。
独立QA消费封存输入，使用只读测试/验证入口，不能用含build/stage的check:compat冒称输入保持。
全部命令返回、worker组静止、假服务server关闭、parent/child/bindings释放后才能提交；独立Gate-C仍由QA裁决。
下一批R/V/A、真实live、多步/并发、主图迁移、默认切换、D5与release均未启动。

此前 final-delivery 包保留历史，因新作用合同绑定返修已被 r2 取代；其 91/265/4220 与联合结果不能给新代码背书。
新作用现在核 revision/snapshot/fence、实际完整 identity、refs/read-set、scope/plan cap、页摘要/model/options/schema/epoch。
合法已提交缓存先授权且允许当前状态更新后取回原receipt；新增14项精确反例/恢复测试。

## r2 最终观察与读集释放

- 新增 Python 集合105 passed；指定原 owner265 passed；全静态4234 passed /3 skipped /7 warnings /12 subtests。3个skip均为未启用的真实live测试，本批required AT零skip。
- TS最终123 passed /0fail /0skip；其最终构建/stage由窗口二生成，无Python返修后的TS变更。
- 技术/作者页经真实C00与worker完成prepare/record/ingest，原reader和封存reader均读到同generation五成员，authorship gate通过，domain保持pending_validation。
- cap4096→1024经原owner重编与新完整投影；两次C00 fake wire观测在领域prepare之前，prepare内网络/LLM拒绝哨兵开启，发送0。
- 真worker34次协议/权限/来源/cap/缓存/冲突/runtime pin反例与恢复往返通过，独立进程组退出、server关闭、parent/child/bindings释放。
- 五项检查exit0且源码前后一致；封存29279个文件/链接的长度与SHA-256全部复核，清单与delivery index绑定一致。

冻结engine：`sha256:8be7feff4e6a1c32971df0b701cd359ed354604bc9a5f452f5180a65da3a299d`；validator：`sha256:e18b1dd12ce0a872bb74ef64e051cc6a1c656e420c90efcb2a635bf03ed4fbc8`；composition：`sha256:6cf5821ad1177320d29f0258cf6c7f8c7e328a0458a1e87b03a553e44f1483e1`。

精确argv/cwd/runner/退出、AT node、源与运行bytes、raw/wire/Session、合同/回执/原reader结果、日志和释放证明见
`.dsh-dev/run/stage03-w1-20261003/final-delivery-r2/delivery-index.json`；独立清单复核见同稳定根的
`../archive-r2-verified.json`。旧final-delivery及开发包仅保留历史，被r2取代。

r2生成并核验后显式释放读集，仅更新本报告、03索引、README索引、任务表、compatibility.stage03、交接和implementation状态。
这些文档更新改变当前engine摘要；以上摘要绑定封存输入，不声明当前工作树与旧回执完全同身份。
代码/测试/fixtures和运行字节未改；独立QA应消费冻结输入/原始证据，或为当前新文档状态重新capture身份，
不把旧合同直接当新作用许可。只读复验不执行含build/stage的check:compat。
