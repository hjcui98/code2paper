# 第 03 份 r2 整包独立 Gate-C 验收与下一批集中返修指令

2026-10-03，独立 QA 裁决：**Gate-C = CHANGES_REQUESTED**。窗口一 I01/C01/C02–C04 与窗口二 C00/TS 已形成可运行实现；原回归和主要联合路径独立通过，但本轮补充反例确认 GC-1、GC-2、GC-3 三组合同缺陷。下一批一次完成这三组及整包验证，重新提交第 03 份，不启动第 04 份。

第 01/02 份已验 Gate-B/H/K 结论保留。49 项仍为 **11 done / 6 in_progress / 32 planned**；第 03 份六项不登记 done，后续 32 项保持 planned。局部 `pending_validation` 不等于 Candidate/Verified 完成，也不授予模型发送许可。本轮未调用真实模型。

## 1. 依据、验收对象与证据身份

按下列顺序执行；本报告补充当前反例和返修验收，不改原 AT、依赖或权威方向。

| 依据 | 本轮适用范围 |
|---|---|
| [docs 入口](../README.md)及其架构权威顺序 | Python 保留证据、预算、领域验收与发布权威 |
| [DSH 总设计](../code2paper_dsh_plugin_design_20260922.md) §§8–10、14、15.1/15.2/15.4 | 唯一合同、实际组成、原 owner 复用与短 RPC |
| [第 03 份](03_writer_contract_and_worker.md) I01/C01/C00/C02–C04 全部任务卡 | 原任务及完成条件 |
| [第 03 份整批指令](stage03_batch_execution_instructions_20261003.md) §§3–7 | 两窗口范围、完整材料、三路径解析、真实 worker、冻结顺序 |
| [interfaces](interfaces.md) §§2–5、7 | Unicode/wire、冻结对象及摘要、新提交的 revision/read-set、幂等顺序 |
| [verification](verification.md) Gate-C、测试层次与证据格式 | 原 AT 与跨任务真实接线，owner 结果和独立结果分开 |

被验 owner 包为 [r2 交付报告](stage03_delivery_evidence_20261003.md)对应的
`.dsh-dev/run/stage03-w1-20261003/final-delivery-r2/`，联合消费窗口二
`.dsh-dev/run/stage03-20261003-w2/final-window-two/`。
早期 final-delivery、开发 joint-* 及窗口二旧 r1 联合引用仅保留各自历史范围。

独立证据根：[stage03-gate-c-qa-20261003-w04q7791](../../.dsh-dev/run/stage03-gate-c-qa-20261003-w04q7791/EVIDENCE_SEAL.md)。
[review.json](../../.dsh-dev/run/stage03-gate-c-qa-20261003-w04q7791/review.json)登记裁决，
[SEALED_FILES.sha256.json](../../.dsh-dev/run/stage03-gate-c-qa-20261003-w04q7791/SEALED_FILES.sha256.json)封存 2,997 个文件/链接；清单 SHA-256：
`a897af2244e240b426c7199aaa0752e0064988c721c985da6847ca8e009beb58`。
它包含原始命令/日志、完整 RPC transcript、探针与改编差分、真实 worker/native 运行产物及本轮 2,110 项输入副本。

| 身份 | owner r2 | 独立 QA 新采集 |
|---|---|---|
| engine | `8be7feff4e6a1c32971df0b701cd359ed354604bc9a5f452f5180a65da3a299d` | `553b4c0eb7bc4f9da055f38b567703f8e2d31c1dc2d4804f087b7f611e84790f` |
| validator | `e18b1dd12ce0a872bb74ef64e051cc6a1c656e420c90efcb2a635bf03ed4fbc8` | 相同 |
| composition，4096 cap | `6cf5821ad1177320d29f0258cf6c7f8c7e328a0458a1e87b03a553e44f1483e1` | `f761983a6e142f1fc77471a6f5bfff43abf8214b2aa67cd3f685994bae57d711` |

摘要均为 SHA-256。两组身份差别来自 owner 封存后已声明的七份协调文件更新；代码、测试、fixture 与运行字节相同。QA 为当前读集重新捕获组成、重走投影和 prepare，没有把 r2 旧合同直接用于当前新提交。

候选保持 `0.2.0-rc.1+loop-origin.1`；runtime 为 `671daa1a7a06728d69a4bdec6da3d33a3616c4e788f63579ed07f3ae81e0e16c`，receipt 为 `4b378ced6e73e5b2c3fd24854ba20546b0e0bc760f3903655c3193f1c4518fda`，stage 为 `08d40fb06972e2ec9ad0c8087277a7b8550c0de9396e37b63969f7a24256b128`；当前 peer 指向该候选。独立 audit exit 0。本轮没有执行 build/stage。

## 2. 独立观察与 Gate-C 覆盖结论

| 项目 | 本轮结果及其含义 |
|---|---|
| 五份 Python 专项 | 105 passed，exit 0；执行组成、wire、共用解析、来源/局部事务、真实 worker 原节点通过 |
| 七份原 owner 回归 | 265 passed，exit 0；保留原 caller、settlement、authorship、身份、publication 与 legacy 行为 |
| TS 兼容完整集合 | 123 passed，0 fail/skip；保留原 93 项及 22 个 wire、8 个 C00 节点 |
| B02 全目录 | 48 passed，exit 0 |
| 真 worker 技术页及作者页 | 两条 prepare→record_output→ingest→原 reader 均通过；同代成员与作者来源有效；局部状态 `pending_validation` |
| 真实 worker 原联合负例 | 34 次 RPC 通过，包括 scope/权限、不可用 R 方法、坏 cap、来源、终态冲突、合法缓存、组成漂移 |
| 原 owner cap 重编 | 4096→1024，重新编译/观测/封投影；旧 cap 拒绝；prepare 期间 Python LLM/网络哨兵有效，发送 0 |
| 独立 Unicode 对照 | 12 例中 2 例 Python/TS 判定不同；真实 native terminal 增补 3 例中 2 例失败，原 8 项仍通过；见 GC-1 |
| 独立旧材料 prepare | 当前状态对照正常；revision、fence、snapshot 三种旧输入仍返回合同，之后 ingest 正确拒绝；见 GC-2 |
| 独立引用损坏新 ingest | 无既有 receipt 的四组独立副本中，完整对照及三种缺失/损坏均发布 `pending_validation`；见 GC-3 |
| 全静态 4234/3 skip | 已核封存日志、命令及输入，是 **owner r2** 证据，本轮未重复执行；3 个 skip 均为未启用 live，不将其计作本批必需 AT 通过 |

精确 argv、cwd、runner、退出码及日志 SHA 见证据根 `*.command.json`、`joint-commands.json`、两组 `*-commands.json`。独立 pytest 使用 `-p no:cacheprovider` 和独立 basetemp；TS 通过现有 toolchain 的只读 test/stage:verify 与离线 launcher。

第一次 TS 启动在外层沙箱中遭 bwrap `NETLINK_ROUTE: Operation not permitted`，未执行测试；原日志 `ts.log` 保留为环境诊断。保留内部 `--unshare-net` 隔离并在获自动批准的沙箱外启动后，`ts-isolated.log` 完整 123 项通过。该环境错误不计产品缺陷或测试通过。

按六项原 AT 逐一复核后：I01 的组成及漂移拒绝本轮成立；C02 三路径解析和 cap 重编成立；C03 原始来源、唯一终态、原 reader 成立；C04 原有有界协议/权限/取消测试成立。GC-1 使 C01/C00 的跨语言终态合同不成立，GC-2 影响 C02/C04 的准备入口，GC-3 影响 C03/C04 的新提交完整性，故整包不放行。

## 3. 本轮全部已确认缺陷与集中修改要求

### GC-1 · P2：Unicode pattern 的 Python/TS 语义不同，真实 terminal 判定分叉

定位：[writer_contract.py](../../src/code2paper/integrations/dsh/writer_contract.py) 的 `Identifier`（当前第 19 行）；[wire.ts](../../integrations/dsh/src/wire.ts) 的 `new RegExp(pattern, 'u')`（第 213 行）；[writer-request.ts](../../integrations/dsh/src/writer-request.ts) 第 154–157 行的 full guard→callback→concludeTurn。

最小输入为 `WriterTaskResultV1` 的 blocked 分支，`recovery_action="new task"`，只改变 `reason`：

| reason | Python 实际模型 | TS full schema | 真 native terminal callback |
|---|---|---|---|
| 普通 ASCII 文本 | 接受 | 接受 | 触发，合法对照 |
| 单字符 U+0085 NEXT LINE | `schema_invalid` | 接受 | 触发，错误接受 |
| 单字符 U+FEFF BOM | 接受 | `schema_invalid` | 不触发，错误拒绝 |

原因是 Pydantic 使用的 `\S` 字符语义与 ECMAScript RegExp 不同，导出 pattern 字符串不会自动统一两端解释器。完整 DSH、真实 pi-ai、隔离本地 HTTP/SSE 上复现，每例只有一个假 provider 请求。Python 没有因此接受非法领域结果；问题发生在 TS 宣告 terminal 与 Python 接受域不一致。

证据：`wire-cases.json`、`wire-differential.json`、`native-probe.log`、`native-probe.diff`，以及 `c00/stage03-writer-request-3OdwDK/qa-unicode-*.json`。native 探针 exit 1，11 项中 9 pass/2 fail；两项失败是验收发现，不能改标通过。

**一次修完整个规则族：**

1. 窗口一确定并导出明确的跨语言字符规则，以现有 Python 接受域为基准。覆盖所有使用 `Identifier`/同类 pattern 的字段；不能仅特判 blocked.reason 的两个字符。
2. 窗口二消费该规则，避免把未证明等价的宿主正则语义直接当合同。可以采用明确字符集合或有版本的规则描述；Python 保持唯一领域权威，TS 不新增摘要权威。
3. 同步 Python schema/goldens、TS 消费、native schema 的 enforcement 说明及实际构建。保留 min/max length、required/null/union/extra、重复键及数值词法断言。
4. 对 ASCII/CJK、U+0085、U+FEFF、NBSP、Unicode line/paragraph separator、纯空白及“空白+正文”、非 BMP 字符、长度边界形成双向 corpus；记录 Python 与 TS 的具体拒绝码，不能只比较“都抛异常”。
5. 在真实 native terminal 重放上述两个失败和合法对照：非法输入 callback/concludeTurn 不成功；合法输入可终止，且 Python 可 record_output。无第二次自动模型请求。不要只在 `wire.test.ts` helper 中关闭问题。

### GC-2 · P2：prepare 没有把冻结材料的 revision/snapshot/fence 与当前 Host 比较

定位：[facade.py](../../src/code2paper/integrations/dsh/facade.py) 的 `render_input`（第 184 行）与 `prepare`（第 269–310 行）。`check_current()` 只确认 Host context 与当前状态相等；读入 FrozenWriterInput 后没有检查它的 revision/snapshot/fence。末尾再次 `check_current()` 仍不能识别“新 Host + 旧 frozen_ref”。

真实 worker 反例保持原 scope、实际组成、合法 projection、cap=4096 和完整内容，只在新的 Host bootstrap 中分别把 content_revision 从 1 改为 2、fence 从 0 改为 1、snapshot 改为新摘要；每例使用独立 artifact root，未复制旧 publication/receipt。三例 `task.prepare` 均成功返回旧材料合同，revision 变体合同仍为 1；随后新 ingest 都以 `contract_revision_snapshot_or_fence_stale` 拒绝。未观察到旧材料越过 ingest 发布。

证据：`stale-prepare-results.json`、`stale-prepare-transcript.json`、`stale-prepare-commands.json`、`runs/stale-prepare/`。问题会把已经不可提交的材料封成待执行合同，留给后续执行层才发现；本阶段 prepare 应在自己的真实入口拒绝。

**一次修完整个准备生命周期：**

1. 窗口一抽取复用的 frozen-input 当前绑定检查，核 scope/epoch、content revision、snapshot、fence 和已规定的身份/引用一致性；在 render_input、首次 prepare、每次 recompile 返回新材料后、最终 seal/返回前消费。避免新建另一套领域 parser。
2. 同一调用过程中当前状态变化也须拒绝；不要把 prepare/claim 等记账序号误作内容 revision。
3. 拒绝过期材料后，要求 owner 正常重新冻结材料并重新取得匹配投影；不要改旧 frozen 对象的 revision/fence 后重新封印来掩盖来源。
4. 真 worker 覆盖三种独立漂移、组合漂移、准备期间漂移、recompile 返回过期输入；合法同状态 prepare、合法新冻结材料及新 cap 仍能通过，prepare 仍零发送。
5. 保留已验的 ingest 旧材料拒绝及授权先缓存规则。合法已提交请求丢回包后，在新 revision 下取回原 receipt 的路径必须继续通过。

### GC-3 · P2：新 ingest 未校验合同引用的投影、计量及 wire 证据完整性

定位：[facade.py](../../src/code2paper/integrations/dsh/facade.py) 第 303–305 行：`read_set` 只放领域 refs，`dsh_wire_contract_ref` 单列；`check_contract_current` 未消费这条投影引用。[result_ingest.py](../../src/code2paper/integrations/dsh/result_ingest.py) 第 174–175 行只校验该领域 read_set，然后新建局部 publication。

真实 worker 反例使用前面已经合法 prepare 的完整合同与真实 raw terminal。分别在 **QA 私有副本** 中删除 projection、删除 measurement、损坏 wire_equivalence 对象；不改合同、原包或原运行输入，不复制旧 receipt。ArtifactStore 直接读取分别报 `artifact_unavailable` / `artifact_bytes_mismatch`，但三个 `task.ingest` 均新生成 `pending_validation`，原 publication reader 均读回该回执和通过的 authorship。完整对照同样正常。

这说明新提交缺少其唯一合同所引用的请求/计量依据时仍可落盘。结果仍是局部 pending_validation；本轮没有证明全局 Verified 或模型发送绕过。

证据：`projection-closure-results.json`、`projection-closure-transcript.json`、`projection-closure-commands.json`，以及 `runs/projection-closure/` 四个独立副本。

**一次修完整个引用链：**

1. 窗口一在 **新提交** 路径验证 `dsh_wire_contract_ref` 及其必要引用：measurement、wire_equivalence、comparison、loop_request、provider_wire。每个对象检查实际存在、原字节长度/摘要、scope、schema/版本及规定的语义摘要。
2. 复用 C02 的投影核对逻辑，把投影的 input/material/schema/model/options/cap、composition/renderer/tokenizer、计量与合同重新关联；仅补一个文件存在性检查不足。该检查是本地读取/计量，不能为证明证据重新发送请求。
3. 在 read-set 或明确的有版本依赖集合中持久记录完整校验依据，并让局部 manifest 可以追溯。若调整合同表示，Python 单写 schema/validator，窗口二同步 TS 消费和必要的版本拒绝；不静默放宽旧版本。
4. 对每个必需引用做缺失、坏字节/长度/摘要、错 scope/版本、来自另一合法 projection 的错绑定反例；覆盖 draft、research_required、blocked。新 effect 必须具名拒绝，原 active/generation/receipt 不变，不生成伪成功回执。
5. 同时验证完整技术页/作者页成功、prepared 引用未变时的合法重试，以及已提交缓存语义。校验新提交 read-set 放在合法已提交缓存分支之后；缓存仍须先验实际授权、scope、输出内容及其不可变 receipt，不能把本修复变成丢回包恢复回归。

## 4. 两窗口合成一批的实施顺序

继续当前 worktree、分支 `codex/agentic-p4-benchmark-cutover` / HEAD `d48b4e4b22c94c82b45d2179ba452d72b164102d` 和既有 dirty 基线。以下均属原第 03 份返修；本报告不要求逐个 helper 再向用户请示。

| 顺序 | 窗口一 | 窗口二 | 交接物 |
|---|---|---|---|
| 1 | 承担 GC-2/GC-3；为 GC-1 交明确字符规则与扩展 corpus；单写全部 Python/protocol/validator | 从 GC-1 原始反例起步，检查全部 TS pattern/full terminal 消费；等待规则后接入 | 规则、schema/goldens、错误码和引用链约定 |
| 2 | 完成当前绑定及完整引用链校验；补纯入口和真 worker 反例 | 完成 TS 规则消费、真实 native 正反例、严格类型检查 | 双向 wire 结果和接口变更摘要 |
| 3 | Python/测试/fixture 最终稳定；提供新联合 driver 要求 | 独占 peer/lib/typecheck/build/stage，交最终 receipt/runtime/stage；构建后停止写共享输入 | 最终构建组成及代码冻结通知 |
| 4 | 按新组成重做技术页/作者页/新 cap/负例/原 reader 联测及回归，汇总单一交付包 | 协助真实 DSH/假 wire 联测，执行完整 TS 与受影响 B02 | 全部原 AT + GC-1/2/3 关闭矩阵、原日志与释放证明 |
| 5 | 两侧共同封存 `submitted_for_independent_qa` 包 | 保持包与运行字节冻结 | 独立 Gate-C 整包复验 |

窗口一的主要文件：`src/code2paper/integrations/dsh/{writer_contract,facade,result_ingest,worker,protocol}.py`、对应 `tests/integrations/dsh/`、已有 validator 来源清单与 schema/golden 生成逻辑。窗口二主要文件：`integrations/dsh/src/{wire,writer-request}.ts`、相应测试及其实际构建。具体无关文件不因列在目录中而必须改动。

schema/golden 当前有 `tests/integrations/dsh/test_wire_schemas.py::export_wire_package`；它不是所有 wire 文件的完整导出入口。返修时确认并记录实际导出命令，必要时集中完整导出流程，防止仅更新一部分 schema/fixture。不要引用不存在的 `export-wire.py` 或未经发现执行的测试脚本。

协调状态同步为本报告裁决：task_board 顶层派工/阶段状态不能继续写“ready_not_started”而六张任务卡写“submitted”；保留 r2 交付历史与旧封存字节。本轮 QA 已更新这些协调入口，owner 后续只登记新批实际状态。

## 5. 必过验证、冻结及再次交付条件

既有 [整批指令 §6](stage03_batch_execution_instructions_20261003.md#6-实施后验证命令与结果记录)仍有效。新增反例并入正式测试，最终稳定版本运行下面的集合，数字可以增长，不得删原断言凑同样计数。

窗口一，仓库根：

```bash
python -m pytest -q tests/integrations/dsh/test_composition_identity.py tests/integrations/dsh/test_wire_schemas.py tests/integrations/dsh/test_writer_prepare_ingest.py tests/integrations/dsh/test_result_provenance.py tests/integrations/dsh/test_worker_protocol.py
python -m pytest -q tests/test_llm_section_writer.py tests/test_agentic_publication_method_writer_unified.py tests/regression_20260922/test_authoring_contract_closure.py tests/test_agentic_final_text_authorship.py tests/regression_20260917/test_execution_identity.py tests/integrations/dsh/test_publication_generation.py tests/integrations/dsh/test_legacy_characterization.py
```

窗口二，串行执行，实际参数不得混入其他候选：

```bash
export C2P_DSH_CANDIDATE='0.2.0-rc.1+loop-origin.1'
export C2P_DSH_DEV_ROOT='/home/cuihengjia/agent/Code2Paper copy/.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1'
npm --prefix integrations/dsh run typecheck
npm --prefix integrations/dsh run build
npm --prefix integrations/dsh run stage
npm --prefix integrations/dsh run test:compat
python -m pytest -q integrations/dsh/dev/tests
python scripts/dsh_dev.py --candidate "$C2P_DSH_CANDIDATE" audit
```

所有生产输入冻结后，由窗口一汇总一次全静态 `python -m pytest -q -rs`，再做适用的 `python -m compileall -q src tests` 和 `git diff --check`。本批修改裁决路径，r2 的 4234 不能替代新候选全静态；全部通过且未再改代码后，不重复无依据的全量运行。必需测试零 skip/timeout/零发现；未启用的三个真实 live 测试单列保留。

完整联合验证仍须走真实 DSH、实际 pi-ai 隔离假 HTTP/SSE、真 Python worker 和原 reader，补入三组反例。以本轮探针语义为基准，不能删除失败输入或只测 helper。QA driver 是冻结身份的重现材料，owner 新代码须按新身份生成新 fixture/合同，不能原样提交旧 bootstrap 后把 composition_drift 当作修复通过。

一次交付必须包含：

1. GC-1/2/3 修前/修后行为与精确 test node；整个 I01/C01/C00/C02–C04 AT 矩阵，明确保留项和新增项。
2. 最终 Python/TS 源码、schema/goldens、测试、driver/config、实际 runtime/build/stage/Loader/peer 及组成；新增裁决 helper 已入 validator 来源。
3. 技术页、作者页、新 cap、真实 terminal Unicode、旧材料 prepare、引用链损坏新 ingest、合法已提交恢复的全部原始证据与稳定错误码。
4. 同一新冻结输入上的专项、原 owner、TS、B02、全静态和 audit 命令/退出/原日志；模型调用 0，prepare send 0，领域结果仍 pending_validation。
5. 新封存根和 SHA/字节清单；不覆盖 r2 或本轮 QA 包。证据脱敏在封存前完成；engine/composition 不写回其自身输入造成循环摘要。
6. 所有命令返回、worker/child/Session/假服务关闭、相关进程静止及端口释放。冻结后协调文档变化明确另记读集释放，不能把旧身份改标给新工作树。

owner 自测完成时仍为 `submitted_for_independent_qa`。只有独立 Gate-C 检查原 AT 与三组反例全部通过，才能把本阶段六项登记 done。

## 6. 可直接转发的两份指令

### 窗口一

```text
继续原第03份集中返修，依据 docs/dsh_execution_20260928/stage03_gate_c_review_and_batch_repair_20261003.md 全文，重点 §3 GC-2/GC-3、§4–§5；同时承担 GC-1 的 Python 字符规则与 schema/goldens。
独立 Gate-C 已 CHANGES_REQUESTED；r2 原回归/主链通过保留，不重做第01/02份。
你单写 Python/protocol/validator；窗口二单写 TS 并独占 peer/lib/build/stage。
一次完成旧 frozen 输入在 prepare 全生命周期的拒绝、新 ingest 完整投影/计量/wire 引用链校验、跨语言明确字符规则，以及真实 worker 正反例。
保留原 caller/settlement/assessor、授权先缓存、同 epoch 唯一终态、合法丢回包恢复和 pending_validation。
与窗口二先固定接口，再固定构建，按新组成联合验证技术页/作者页/新 cap 与全部新反例；完成 §5 全套稳定候选验证和新封存后一次交付。
不要逐个 helper 停工；不提前 R01–R04/V/A、真实模型、默认切换或 release。交付状态 submitted_for_independent_qa，等整包 Gate-C。
```

### 窗口二

```text
继续原第03份集中返修，依据 docs/dsh_execution_20260928/stage03_gate_c_review_and_batch_repair_20261003.md 全文，重点 §3 GC-1、§4–§5。
真实 native terminal 已复现 reason=U+0085 被 TS 错收、U+FEFF 被 TS 错拒；原123兼容回归通过，仍不足以关闭这个合同差异。
消费窗口一明确的 Unicode 规则和扩展 goldens，修整个 Identifier/pattern 规则族，保留现有严格 schema、数值词法、重复键等约束；补真实 native terminal 正反例和 Python record_output 对照。
你独占 TS、peer/lib/typecheck/build/stage；共享 Python/validator 交窗口一单写。
协同窗口一完成 GC-2/GC-3 所需 wire 引用/类型及新组成联合证据，按 §5 跑完整兼容/B02/audit，保留原93项断言和全部新增 C00/C01 断言。
最终构建后冻结并交实际身份，再共同完成真 worker/假 HTTP/SSE 联测与整包封存。prepare仍零发送，不调用真实模型。
一次交齐本批全部结果，不提前第04份；状态 submitted_for_independent_qa，等独立 Gate-C。
```

## 7. Gate-C 之后的阶段顺序与本轮读集释放

本轮立即执行的是上述第 03 份三组返修。Gate-C 通过后才启动 [原第 04 份](04_serial_writer_integration.md)整批 **R01→R02→R03→R04→V01→A01→V02**：

| 后继任务 | 要交付的实际能力 |
|---|---|
| R01 | 持久 task/outbox/claim/epoch，复用原 fence，多 Host 只有一个合法领取者 |
| R02 | 原 Python invocation 账本真实 reserve/dispatch/unknown/settlement，发送前 lease 内重查余额/read-set/fence |
| R03 | TS Host 与真 worker 的完整单 Writer pump，先 reserve 后派发，一次请求，真实来源/capture/accounting 接线 |
| R04 | 跨进程故障恢复、unknown 保守处理、旧 epoch 迟到结果、取消后正向证明 provider 退出 |
| V01 | 整条链仅 provider 使用假服务的串行集成正反例，实际 pi-ai wire |
| A01 | 离线准入回执只覆盖真实执行的 Python/Node/入口测试和同一组成；漏测/伪造/零测试拒绝 |
| V02 | 显式 opt-in CLI 入口及有效配置，默认流程保持；接入回执的真实入口证明 |

第 04 份仍需 Gate-R/V，L01 真实模型运行另按其授权/额度/准入。第 05–08 份、多步并发、主图迁移、默认切换、D5/发布不由本轮代验。

本轮 QA 于 **2026-10-03 23:03:47 +08:00** 释放读集：2,110 项输入字节/metadata 未变，最终 full composition 相同；r2 29,279 个文件/链接、窗口二 135 个封存文件和 72 项当前输入均核验无差异；全部行为验证命令已返回，相关宿主验证进程 0，native 假服务及句柄释放记录已封存。分支/HEAD、生产代码及 owner 封存未改动。

释放后只更新本报告、索引/任务/兼容与实施记录。这些协调文件更新会改变后续 engine identity；不得继续用本轮旧合同创建新 effect。两窗口按本报告接回原第 03 份的返修写权，无需等待常驻 QA 或为每个内部步骤重新派工。
