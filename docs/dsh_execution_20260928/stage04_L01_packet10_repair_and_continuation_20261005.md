# Stage04–06：packet10 现状、L01 整批修复与长期接续指令

> **当前接续已更新至[原长期模块 §9 Gate-L 集中解阻](stage04_06_long_module_execution_20261004.md#gate-l-unblock-20261005)。** 最近实际请求为packet14，费用UNKNOWN且原owner held。本文件保留packet10历史与通用合同，不再作为当前五组返修派工入口；packet14的abort/unknown恢复不得套用这里的normal-finish授权。

> **2026-10-05 最新执行状态：** packet11 一次生成授权已消耗，普通文本 JSON/finish stop、tool_calls0，领域失败保留。文本结束返修及具名原费用恢复经独立代码/方案、实际结果两次 PASS；原费用 spent7596/pending0，canonical backend empty，35旧文件、原task/claim/正文及provider_quiescence null保持不变。实际读集已释放；新完整注册证书及fresh cold待最终冻结运行。Gate-L仍FAIL，24/1/24；新模型请求需fresh packet具体一次授权，不重发旧packet。详见 [文本结束返修证据](stage04_L01_text_stop_repair_evidence_20261005.md)。


> 后续实际执行更新：packet10 独立事后 FAIL 并释放读集；五组修复和具体历史恢复方案独立 PASS，exact owner 本地退役 exit0。原费用/任务/失败不变，新模型请求0。详见 [整批返修记录](stage04_L01_repair_batch_evidence_20261005.md)。下列00:27快照保留其原历史时点，不覆盖新的具名证据。

核对时间：2026-10-05 00:27（Asia/Shanghai）。这是现状核查与下一批派工，不是新的 Gate-L PASS，也不是新的模型调用授权。依据实际 packet、原 Session、原账本 reader 和当前原校验器；没有重跑产品套件或调用模型。

**执行起点是 L01 集中修复；A 已完成，C–F 尚未正式启动。** 本补充细化原长期模块，不增加第 50 项任务，不改变原 AT、depends_on、事实权威或默认入口。

## 1. 准确进度与当前阻塞

| 范围 | 当前状态 | 后续动作 |
|---|---|---|
| 原第 01–03 份，17 项 | 已有独立验收；保留各自绑定身份 | 按实际改动做回归，不重新从头派工 |
| A：R01–R04、V01、A01、V02，7 项 | 独立 Gate-R / Gate-V PASS | 保留 039 结论，不能给新源码回填旧身份 |
| B：L01，1 项 | in_progress；Gate-L 未通过 | 完成本文件 §4–§7；packet10 独立事后裁决尚未发现 |
| C：M01–M03，3 项 | planned；已有只读接口研究 | Gate-L PASS 且读集释放后整段实施 |
| D：P01–P04，4 项 | planned；已有只读调度研究 | Gate-M PASS 后整段实施 |
| E：G01–G03，3 项 | planned | Gate-P PASS 后整段实施 |
| F：G04–G08，5 项 | planned | Gate-G0 PASS 后整段实施，终点 Gate-G |

项目总计 **24 done / 1 in_progress / 24 planned**。长期模块自身 **7/23 done，1 项进行中，15 项 planned**。C–F 的研究不计实现或验收。长期模块全部通过后才到 40/49；余下 F01–F04、Q01–Q05 共 9 项另按原第 07/08 份执行。任务数不能换算成代码工作量或剩余工时百分比。

packet02、packet09、packet10 已分别实际发送一次，三个授权的 primary 均已消费。packet 编号不是调用次数。packet02 的旧费用结算和旧 owner 退役已完成并独立复核；不得继续沿用文档中“等结算批准”的旧状态。packet09 费用结清、正常释放，但内容绑定失败。packet10 是新的失败，不能继续用 packet09 的原因概括。

### packet10 已核实的事实

| 层次 | 实际结果 |
|---|---|
| 调用 | 1 次 primary，HTTP 200；input 7463 / output 1182 / total 8645；tokenizer 输入 7463，finish 为 tool_calls |
| 费用 | 原账本 call_count=1、completed_call_count=1、spent_input_tokens=7463、pending_input_tokens=0；已结清 |
| terminal | 原始顶层只有 result，缺必填 schema_version；真实 tool/result 为 Error: schema_invalid |
| Session | 对应真实 child 的 turn/end.reason.kind=blocked |
| 后端凭据 | 原 _verify_native_quiescence 在 task_store.py:290 因只接受 completed/error 拒绝；provider_quiescence 未持久登记 |
| 清理 | 最外层错误 backend_release_quiescence_unproven；随后 release 报 backend_release_owner_observation_required；canonical backend 仍归 packet10 |
| 领域 | task cancelled、receipt=null；尚无局部领域接收，更无 Verified / publication_ready |

原 raw 为 1584 bytes，SHA256 `335194b5e7ad149d022daada3110c35f15f0746ef26ed8a9d3e1667133c59c0c`。Session 参数分片与 raw **逐字节一致**；normalized block 为 1551 bytes，JSON 语义相同。因此当前已复现的拒绝点不是 raw 分片丢失或重序列化差异。

还发现两个需要同批处理的合同问题：实际 system prompt 同时包含旧 Writer 的“只返回 section 对象”和 DSH 的 terminal 包装要求；追加说明没有直接展示必填 schema_version 字段。此歧义是待修复的协议表达问题，不能据此断言它是模型漏字段的唯一原因。实际模型正文还用 `$$ y = a * x $$` 替换了要求的 `[[FORMULA:<package_id>]]`，仅保留 used_formula_package_ids 不够。本轮没有把该无效 terminal 绕过 schema 送入领域 assessor，后续须单独验证该内容拒绝面。

`completed_call_count=1` 只证明调用费用已结算，不证明领域成功。`reserved_input_tokens=10336` 是原账本累计字段，不是当前还有 10336 pending。cleanup 的 stream ended 文本、本地 worker 退出和后端空闲观测都不能替代受信持久完成凭据。

## 2. 文档依据与可复核证据

按 [docs 入口](</home/cuihengjia/agent/Code2Paper copy/docs/README.md>) 的原架构权威顺序解释，具体任务沿用：

1. [长期模块全文](</home/cuihengjia/agent/Code2Paper copy/docs/dsh_execution_20260928/stage04_06_long_module_execution_20261004.md>) §§1–7：23 项、阶段依赖、权威边界、一次整批交付。
2. [第 04 份](</home/cuihengjia/agent/Code2Paper copy/docs/dsh_execution_20260928/04_serial_writer_integration.md>) AT-R03/R04/V01/A01/V02/L01、[第 04 份细则](</home/cuihengjia/agent/Code2Paper copy/docs/dsh_execution_20260928/stage04_batch_execution_instructions_20261004.md>)、[L01 协议](</home/cuihengjia/agent/Code2Paper copy/docs/dsh_execution_20260928/stage04_L01_execution_protocol_20261004.md>)：原 owner、恢复和具体 live 准入。
3. [第 05 份](</home/cuihengjia/agent/Code2Paper copy/docs/dsh_execution_20260928/05_multistep_and_concurrency.md>)、[第 06 份](</home/cuihengjia/agent/Code2Paper copy/docs/dsh_execution_20260928/06_langgraph_workflow_migration.md>)、[interfaces](</home/cuihengjia/agent/Code2Paper copy/docs/dsh_execution_20260928/interfaces.md>)、[verification §2–3](</home/cuihengjia/agent/Code2Paper copy/docs/dsh_execution_20260928/verification.md>)：后续原 AT、门与接线要求。

主要证据：

| 证据 | 使用范围 |
|---|---|
| [Stage A 独立裁决](/tmp/c2p-dsh-independent-stageA-039/review.md) | 七项 PASS；仅其冻结身份 |
| [certificate09](/tmp/c2p-dsh-l01-admission-20261004-09/receipt.json) / [原完整 reader](/tmp/c2p-dsh-l01-admission-20261004-09/original-complete-reader-validation.json) / [cold reader](/tmp/c2p-dsh-l01-admission-20261004-09/managed/original-cold-reader-validation.json) | 当前已记录完整 1548：Python1336、Node211、operator1；fresh cold PASS。是历史已运行结果，本轮没有重新运行这些测试 |
| [packet10 执行包](/tmp/c2p-dsh-l01-packet-20261004-10/packet.json) / [具体授权](/tmp/c2p-dsh-l01-packet-20261004-10/user-authorization-record.json) | 一次调用及已观察费用结算、normal-finish release 的授权范围 |
| [失败](/tmp/c2p-dsh-l01-packet-20261004-10/failure.json) / [原读回](/tmp/c2p-dsh-l01-packet-20261004-10/owner-readback.json) / [原 Session](/tmp/c2p-dsh-l01-packet-20261004-10/sessions/--tmp-c2p-dsh-l01-packet-20261004-10--/4676560a-88ab-44c3-b35f-16b091f5ea49/session.v4.jsonl) | 当次失败、费用、占用与首个 terminal 拒绝 |
| [本次只读复核](</home/cuihengjia/agent/Code2Paper copy/.dsh-dev/run/l01-packet10-status-20261005/verification.json>) | 原 parser、原 quiescence verifier、原预算/backend reader 的新观察；不代签完整 Gate-L |

此次只读复核前后 engine 均为 `sha256:fb26901fed659b380896bfa0de4fee15c75f68ff38c35fb5a0039bdb3484698f`，与 packet10 相同；validator 为 `sha256:36fb99bdfd70f74cca28b80f078527962dc81b53355d38cf933b4f2f53228a7f`。原始输入 SHA/长度保存在 verification.json。

## 3. 立即可做与写入顺序

由一个主执行者连续负责本批 Python、TS、测试、历史占用恢复方案及封存；独立 QA 仍单独裁决，不要求维持两个实现窗口。保持现有 worktree 和全部 dirty 基线，不 reset/clean/切分支/commit。

当前外部 [执行索引](/tmp/c2p-dsh-l01-repair-execution-index-20261004-01.json) 仍记 `source_writes_allowed=false`，要求冻结到实际 live 及独立 Gate-L 复核完成，且 live10 字段还停在 running。该 running 与已落盘 exit1/失败证据不一致，**不得据此重启命令**。以原命令回收结果、failure/cleanup/Session/账本为准，先补具名事实记录。

1. 冻结期间可只读核实、准备本批修改、保存本文件和任务快照；不改当前代码、文档身份、runtime 或旧 packet。不能代别的 reviewer 宣布读集释放。
2. 原 packet10 独立 review 完成并明确释放后，同步本批文档/任务表，随后一次完成 §4–§6。同步本身会改变 engine 身份，应发生在下一份最终证书之前。
3. `pending-doc-sync.patch` 是已准备的主文档/任务表修订，不含生产代码。应用前比较 `doc-sync-inputs.json`；有其他窗口新记录时手工合并该事实增量，不能覆盖。先 `git apply --check`，再应用；校验通过不等于读集已释放。
4. 若独立 review 在本快照之后已有新裁决，先追加其路径、绑定身份和新增问题到本批矩阵，不把本文件的“尚未发现”当作永久状态。

本补充现在保存在 `.dsh-dev/run/l01-packet10-status-20261005/`，该目录已由现有 ignore 规则排除，不改变冻结 engine。本轮没有修改排除规则。主入口同步后它仍是原始观察证据。

## 4. L01 下一批完整修改范围

以下五组是同一 L01 返修包，不拆成五轮零散派工。依赖顺序为合同与生命周期修复 → 真实离线联测 → 历史恢复方案及独立复核 → 最终冻结和准入。

### 4.1 统一模型可见的 terminal / Writer / formula 合同

落点：现有 `src/code2paper/integrations/dsh/facade.py`、`writer_contract.py`，实际 `integrations/dsh/src/writer-request.ts` / `workflow-driver.ts` 中的消费入口，以及必要的 dev 材料投影。先以 `rg` 确认实际注册 owner；不要因为文件名相似只修改 H03 的最小测试 schema。

- 检查从原 Writer request → DSH input → native parameters → 实际 pi-ai messages/tools 的完整投影，保证只存在一种明确的最外层输出要求。旧 Writer 的 section 结构仍原样放在 result.draft；DSH 包装明确要求 `schema_version="WriterTaskResultV1"` 与 result。若原通用 prompt 必须保留，DSH 指令应明确原“section object”只指 result.draft，并用不含领域答案的结构说明消除歧义；不得静默改写已冻结 prompt。
- formula 只能消费已冻结 package 的原占位符；区分正文解释、公式占位符和 metadata，禁止 inline equation 替代消费、复制 package ID 冒充渲染、删除 formula obligation。
- 同时保留 detail witness 的唯一 exact_text、closed atom 所属 detail/source operation、author surface、required atoms、原 Binder/assessor。已有绑定修复和乘法错误操作数反例不能回退。
- Python/TS full schema 与 native schema 的结构义务要一致；缺 schema_version、result 为字符串、错分支/多字段等仍拒绝。**不得给 packet10 的旧原文补字段、换公式或改措辞后称为同一次成功。**
- 通用逻辑不得写入本次 rescale 的固定句子、符号、路径或“标准答案”；正例使用测试 fixture，真实模型仍自行产文。协议改动不承诺下一次模型必定遵守。

### 4.2 区分 provider 完成、terminal 接收和领域验收

落点：`task_store.py::SerialBackendAdmission._verify_native_quiescence/release_observed_finish`、`worker.py::backend.observe_quiescence`、`workflow-driver.ts::archiveProviderQuiescence/releaseBackend`。

- 先用真实 native adapter/Session 重放 packet10 的 schema 拒绝，得到自然流结束 + tool/result error + turn/end blocked。不能手工把 Session 的 blocked 改成 error/completed，或用 stub completion 替代实际链。
- 修复完成凭据校验，使**有完整受信自然结束证据的 terminal 拒绝**能够结清并释放自己的后端占用，同时仍无领域 receipt。不能仅把 blocked 加入白名单就结束：逐项证明实际 request/child/session/call/index、原 raw 分片、usage、finish、事件顺序、claim/fence 和持久登记边界。
- raw 与 normalized 各自保存；只在原严格 JSON 语义规则允许时承认表示差异，不以 JSON.stringify(parsed) 生成“原文”。重复 key、类型/数值差异、错请求/错 session、伪造 block-end、缺自然 finish 等继续拒绝。
- `provider_quiescence` 仍由活动 execute claim 的私有 owner 登记，随后原 reader/新 Worker 消费；recovery-only 不获得 mint 权限。登记与释放各有明确失败结果，不能把“有一个形状正确的 artifact”当作登记成功。
- 发布/领域接受不作为“费用已结算”的同义词；后端实际完成也不作为“领域通过”的同义词。未知发送仍 held，无 usage 不默认零，无完成凭据不按 TTL/PID/idle 释放。

### 4.3 保留最早错误及清理链，补齐可操作诊断

落点：`workflow-driver.ts` 的 terminal/observe/cancel/settle/finally 路径、`integrations/dsh/dev/l01.mjs` 的失败与读回报告；必要时原 worker 的错误码。

- failure 摘要保留真实 terminal 的 `schema_invalid` 及关联 call/Session 位置；provider 校验、cancel、settlement 和 release 错误分别登记。不要用后端清理错误遮住最早的合同失败。
- 正常 provider 完成但 terminal 无效：账本收实际费用，领域拒绝，后端按有效凭据释放；无证明时明确 held 及缺失事实。不得用统一 success/failed 布尔值代替这三层状态。
- 监控结束后必须回收原进程句柄并记录实际 exit，不能留 running 占位。超时只继续观察原句柄，不发起第二次任务。报告分别列 primary、tokenize、辅助请求、已付费用、pending、任务、backend、领域 receipt。

### 4.4 packet10 历史占用恢复：只处理原副作用

packet10 已 cancelled、费用已结清、provider_quiescence=null。它虽有当时写出的 DshProviderQuiescenceV1 artifact，但该 artifact **没有通过原 owner 登记**。因此不能修完现在的 verifier 后，伪装成旧 execute claim 再补登记；也不能重复 settlement。

- 先离线形成可审查的恢复方案：绑定旧 execution/resource/run/task/epoch、原 claim lineage、实际 session、raw/SSE/usage/finish、已结清账本、旧实现身份和新恢复实现身份，明确唯一预期写入是该 owner 的释放及不可变 history；不改原失败、正文、原 packet 或领域 receipt。
- 优先复用已有授权内的 original normal-finish release 能力；已有费用结算/normal-release 授权不用重复询问。若当前持久证明不足且必须新增历史迁移入口，先完成隔离实现、反例、独立代码/方案复核，再判断其具体副作用是否仍在原授权内。超出原授权时只提交这个完整、绑定字节/命令的迁移方案，不泛泛申请“清锁”。
- packet02 的 legacy retirement 专门校验 tokenizer mismatch 错误 Session，并拒绝 native block-end/completion；它不能原样处理 packet10。不得为省事去掉其旧限制或重跑 packet02 退役。需要新的具名恢复类别时版本化并保持旧类别严格性。
- 真实 canonical SQLite 只允许原 owner 事务操作，核对 exact owner 后写 history 与释放原子完成。必须证明重复调用幂等、新 owner 不受影响、错误 scope/fence/usage/history 全拒绝。绝不直接 DELETE、换 resource key、换私有库或看 idle 清锁。
- 无法形成足够证明就保留 held，并列出具体缺失证据；不伪造成功。即使合法释放成功，**packet10 的领域结果仍失败，不能因此让 Gate-L PASS**。

### 4.5 一次收齐文档、版本、准入和封存

- 更新实际修改的 validator 来源清单、schema/goldens、TS 声明和 runtime/build/stage 绑定；只列真实修改，不给旧证书换标签。
- 所有代码、测试、schema、提示和协调文档先集中收口，再冻结最终身份，生成一份当前注册完整 certificate 及其独立 fresh cold-normal companion。不能边写 docs 边跑绑定全 engine 的证书。
- task_board 的 L01 latest_attempt 切到 packet10，packet09 移入历史；当前状态写入原 engine/validator、授权已消费、费用 settled/backend held/domain none、独立事后 review 是否已有。计数保持 24/1/24。
- 修正 docs/README、执行 README、长期模块开头与 §8、L01 协议入口和 implementation 记录中仍指向 17/49、packet02/09、待旧结算批准的“当前”文字；旧历史记录保留原身份和日期。外部 execution-index 不由其他窗口覆盖，交实际主写者把 running 更新为 exit1 并索引这批证据。

## 5. 整批验收矩阵与实际入口

每行必须同时交原始 provider 到达数、原费用 reader、task/backend 读回和领域结果；只有 fixture provider 是假的，其余使用真实 DSH Loader/native adapter/Session/原 worker/parser/assessor。Python 模型/网络拒绝哨兵保持有效。

| 场景 | 一次验证的关键结果 |
|---|---|
| 合法 draft / research_required / blocked 三分支 | 分别得到原规定的局部 pending_validation / waiting / blocked 回执；所有调用有实际费用、完成凭据与正确释放 |
| packet10 原字节 | 原 schema 仍拒绝；真实 native blocked 不遮首因；修后完成证据充分则可清理隔离占用，无领域回执 |
| wrapper/formula/witness | 缺版本、错版本、result 字符串、内联公式替代占位符、只列 package ID、错误占位符、缺 detail witness、错 operand/condition/polarity 各自拒绝；合法原合同正例仍通过 |
| 自然结束但领域拒绝 | tool error、parser/Binder/assessor 拒绝均记费用；证明充分时释放，不把任何一种拒绝写成接受 |
| 来源/计量损坏 | raw/normalized 非等价、重复 key、错 session/request/call/index、乱序/重复/缺 usage、缺 finish、伪造完成 artifact；拒绝登记或释放，unknown 不重发不退款 |
| 崩溃切点 | usage 后、quiescence 登记前/后、terminal 后、settlement 后、release/history 事务边界；新进程恢复零发送、不重复费用、不重新占用已经退休的 owner |
| owner 安全 | recovery-only mint 拒绝、旧 fence、错 task/epoch、他人 owner、损坏 history、新 owner 已进入、重复恢复/释放；保持 exact owner 与幂等 |
| 旧协议保留 | packet02 legacy 类别、packet09 正常释放、Stage A/C 原合法回执读取及 Unicode、预算、来源、权限反例继续有效 |

聚焦验证扩现有 `tests/integrations/dsh/test_host_recovery_boundaries.py`、`test_l01_binding_contract.py`、`test_legacy_retirement.py`、`test_coverage_use.py`、`integrations/dsh/dev/tests/test_l01_meter.py` 及真实 `host-provider.test.ts` / `writer-request.test.ts` / `provenance.test.ts`。新用例须进入真实 discovery/机器报告，不以手写 passed 总数验收。

修改后先跑相应聚焦项，再走原 launcher 的 native 离线场景。以下是待执行命令模板，本轮没有运行；fresh 输出根不得沿用旧 packet：

```bash
python -m pytest -q tests/integrations/dsh/test_host_recovery_boundaries.py tests/integrations/dsh/test_l01_binding_contract.py tests/integrations/dsh/test_legacy_retirement.py tests/integrations/dsh/test_coverage_use.py integrations/dsh/dev/tests/test_l01_meter.py
export C2P_DSH_CANDIDATE='0.2.0-rc.1+loop-origin.1'
export C2P_DSH_DEV_ROOT='/home/cuihengjia/agent/Code2Paper copy/.dsh-dev/candidates/0.2.0-rc.1+loop-origin.1'
npm --prefix integrations/dsh run typecheck
npm --prefix integrations/dsh run build
npm --prefix integrations/dsh run stage
python integrations/dsh/dev/l01_launch.py offline --output /tmp/c2p-dsh-l01-repair-20261005-offline-01
python scripts/dsh_dev.py --candidate "$C2P_DSH_CANDIDATE" audit
git diff --check
```

只在实际 TS/构建输入变化后执行 build/stage；新增失败模式走隔离 provider，不能在 live 模式注入变造响应。最终原 `method-agent record-offline-receipt --suite-plan dsh-stage04` 沿用 certificate09 的已验证完整 argv、正常入口 companion 和共享 deadline，换 fresh 输出与当前身份；执行前核对当前 CLI 帮助/计划，不猜缺失参数。完整计划已包含的 suite 不无故再全量跑第二次。若影响扩到原领域核心或相应里程碑要求全静态，按影响补一次全静态并说明原因，不以旧 4355/4664 计数替代新证明。

交付包包含原 AT→节点→行为→证据矩阵、五组修复差分、历史恢复方案/授权适用判断/实际回执、原日志与准确 exit、组成和代码身份、全部读依赖 SHA/长度、未测项及清理。主执行者先自测完整包，独立 reviewer 同一冻结包集中审查；不是修一项就另派一轮。

## 6. Gate-L 的下一次实际准入

packet10 的 primary 已消费且内容无效。当前授权没有 retry/repair，**不得自动 packet11、重放真实请求或额外 probe**。先完成 §4–§5 和旧占用处理，才准备新的具体请求包。

新包应一次提交：fresh packet/输入/实际 wire、模型/profile、当前完整与 cold 回执、原 backend 已合法空闲证明、准确执行 argv、一次 primary/零 retry-repair、32768 输入/4096 总输出/180 秒及一 tokenize 的具体上限、监控和停止规则、与前次相比的实质变更及离线证据。用户若明确批准该新包就直接执行，不再为相同动作重复请示；本指导本身没有给出这项批准。

正常运行、被拒绝和 unknown 各按同一个实际生命周期收口，及时更新原句柄与读回。独立 Gate-L 必须覆盖真实 tool 参数/来源、usage/finish、原费用、合法后端释放、原局部接收；静态数量、HTTP200、事前 preflight CLEAR 或“占用已经清掉”均不够。通过后记录实际身份及读集释放，L01 才从 in_progress 改 done，项目成为 25/49，直接继续 C。

## 7. Gate-L 之后的大模块细化与预防返工

长期终点仍为原 Gate-G，无需逐 helper 重新派工。下面是已发现需要在下一整段开工时先解决的接口缺口，不授权现在跨 Gate-L 集成。

### C：一次完成 M01–M03，先定多请求合同再接压缩

复用 [已有 C 段只读研究](/tmp/c2p-dsh-stageC-native-context-research-20261004-01/research.json)，开工前复核其源码 SHA。当前 max_model_requests=1、单 reservation、单 captured_source/quiescence 和固定 Writer 两消息比较不能直接支撑多步。先版本化 c2p-dsh-task-loop-v1 的 request ordinal/purpose、每请求 wire/meter/usage/source/完成凭据与 epoch 总预算；旧单请求 reader 仍可读，unsupported migration 明确拒绝。

随后连贯实施：M01 授权句柄/限量读取/revision 失效 → M02 原生 compaction 事务与实际请求材料恢复 → M03 跨 child/进程费用及单 terminal 候选。标题/压缩不能因为不是正文而免费，也不能拿 purpose 字段铸造私有派发来源。

当前原生 BasicCompactionEngine 的 summarize 钩子可作为待验证接点，保留原选区、依赖检查、事件与 flush 事务；native compact/title 的公开 ctx.llm.stream 目前不能直接越过私有来源门。先在支持的原生钩子/受信执行路径证明来源与计量，未接通的直接 title provider 保持禁用并测试拒绝。自动 compaction 捕获错误后继续运行的原行为不能使产文跳过缺材料/unknown 门。

验收强制真实 compaction，再检查真正发送的产文 wire 含作者语义、exact excerpt、occurrence、公式消费材料；通过显式 Session 输入恢复并重新计量，装不下返回原分页 owner。导航摘要不升级证据。summary/title 的 plain text 完成证明使用具名类型，不伪装成 c2p_terminal 领域候选。提交完整 Gate-M 包后才进入 D。

### D：一次完成 P01–P04，承接 C 的每请求生命周期

复用 [已有 D 段只读研究](/tmp/c2p-dsh-stageD-scheduler-research-20261004-01/research.json)，先用 C 的版本化 request/finish 合同设计 permit，再接 shared SQLite/alias、两类限额、wave/join。原 SerialBackendAdmission 的单 task/单调用释放条件不能直接复制成多请求调度。

请求槽保留到该请求实际自然完成，在等待工具/child 前释放；不能等整个 task 完成导致父子互等，也不能 stream 对象返回就释放。队列等待不持 run/scheduler 长事务，费用继续原唯一账本。任一 unknown 阻断整个 resource group，包括容量 2 中看似空的另一个槽和全部 alias。

默认 parallel=false/run 请求总量1；显式开启叶任务默认2、backend1，所有 parent/child/verify/title/compact 均受 run/backend 双限。以真实多进程和不同 run/alias 验证原子容量、公平 FIFO/轮转、降低限额、取消、旧 permit/fence、新 owner、wave 丢结果和同 revision 单写者。离线假服务即可，不新增压力 live。Gate-P PASS 后继续 E。

### E/F：保留真实图与领域权威，整段收口

E 按原 G01–G03：真实 9 节点/条件边、稳定 thread_id、持久 saver、严格 serializer、逐字段持久来源及新 Python 进程恢复；列出 context closure 和 last_result 的替代来源。G0 是状态承载门，可用明确 fixture executor，但不能用同进程 round-trip/玩具图。Gate-G0 通过才接 F。

F 按原 G04–G08：Research 提案与工具、Authoring/Formalizer/Narrative/Writer/Realizer/Editor/Rewrite、独立 verify、typed gap 补证和全图恢复。16 节点逐条记录实际角色/handler、合法边、输入回执、失效范围、恢复点和副作用；不拿“注册了16个名称”替代执行。G08 必须复验 G0，并以真实 DSH 角色和隔离 provider 取代 E 的 fixture executor；隐藏 Python LLM 出口持续零调用。

每段内部连续实现和修复，独立门和读集释放后直接接下一段。F 交付 Gate-G 只证明完整离线流程接线，不宣布审计 L1/D5、最终质量、默认切换或 release。

## 8. 可直接交给主执行者的接续指令

```text
继续原 Stage04–06 长期模块；当前 24/49，A 七项 Gate-R/V 已通过，L01 in_progress，C–F 十五项未正式实施。先读本补充执行指令全文，原长期模块及第04/05/06份 AT/依赖不变。
packet10 已发送一次，7463/1182，费用已结清；raw 缺 schema_version，真实 terminal schema_invalid、Session blocked；quiescence 原校验拒绝，后端仍 held，领域无回执。不要自动重发或从头重做 A。
先完成并记录 packet10 独立事后复核及读集释放；冻结期间只写外部任务记录。释放后合并本包 pending-doc-sync.patch（先核对输入，不能覆盖其他窗口新记录），由实际主写者同步外部 running 状态。
一次完成五组修复：明确 DSH 包装与原 Writer/formula/witness 合同；真实 native 拒绝路径的受信完成与释放；首因和清理错误分层；packet10 历史 exact owner 的安全本地恢复方案；完整回归、当前 certificate/cold、版本与证据封存。
packet10 旧输出保持失败；不得补字段/换公式使其过关，recovery-only 不可补造 execute 来源，不能直接清 SQLite、改 resource 或按 idle 清锁。旧费用不能重复结算。已有 normal-finish release 授权按同一实际范围复用；若必须新增迁移副作用，先把方案与隔离验证做具体，再处理它的授权边界。
代码、测试、提示、文档一次收口后才跑最终注册完整证书；保留真实 native 正反例、三层结果、原 reader 和原始日志，不以自测或 preflight 代 Gate-L。所有新增模型调用都先准备最终 fresh packet，再取得该包具体一次授权；repair/retry 仍 0。
Gate-L PASS 且读集释放后，在原授权任务范围连续完成 C 整段 M01–M03（先版本化多请求/aux 来源与费用），Gate-M 后 D 整段 P01–P04（每请求 permit、共享队列和 wave），Gate-P 后 E 的 G01–G03，Gate-G0 后 F 的 G04–G08。每段完整交付，不逐 helper 请求新指令。目标 Gate-G / 40 of 49，默认入口及最终质量门不变。
```
