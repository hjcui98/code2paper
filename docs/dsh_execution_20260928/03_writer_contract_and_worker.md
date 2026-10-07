# 03 · 执行身份、唯一 Writer 合同与无模型往返

> **2026-10-04 当前：[GC 集中返修独立验收](stage03_gc_repair_acceptance_20261004.md)通过 Gate-C，GC-1/2/3全部关闭，I01/C01/C00/C02/C03/C04登记done。** 下一批见[第04份整批指令](stage04_batch_execution_instructions_20261004.md)；本份原AT及领域pending_validation义务保留，下方记录均为各自时点的历史状态。

> 2026-10-03 23:03 独立验收：[r2 Gate-C 裁决与下一批完整指令](stage03_gate_c_review_and_batch_repair_20261003.md)，**CHANGES_REQUESTED**。本份六项已实施，需一次关闭 GC-1 Unicode terminal、GC-2 旧材料 prepare、GC-3 投影引用完整性；按报告 §3–§6 分工、验证和重新封存。六项保持 in_progress，第04份未放行；下方提交记录是 owner r2 的历史状态。

> 2026-10-03 最终交付：[Stage03 r2证据索引](stage03_delivery_evidence_20261003.md)已 submitted_for_independent_qa。I01/C01/C00/C02–C04已实施与冻结联测，独立Gate-C待裁决；下方早期planned记录为历史。局部domain仍pending_validation，后续R/V/A未启动。

> 2026-10-03 18:03：[Gate-H 与正式 Gate-K 已通过](stage_four_group_repair_acceptance_20261003.md)，本份实施前置已满足。**I01、C01、C00、C02–C04仍全部 planned，本次QA未实施这些任务。**
> 下一批按新裁决§4连续推进整份：窗口一负责Python/validator及I01/C01/C02–C04，窗口二负责C00与TS消费者/独占build-stage；共享Python文件由窗口一单写。完成原AT和真实worker无模型联合往返后验Gate-C。以下“等H/K”记录属于历史检查点。

> 2026-10-03 下一批详细派工见[第03份整批执行指令](stage03_batch_execution_instructions_20261003.md)：§3/§4分别为两窗口全部实施要求，§5交接，§6验证，§7封存，§8为可直接转发的启动指令。本文六项原AT和任务依赖不变；发布指令不表示实现已启动。

> 2026-10-02当前：[返修差分与完整接续](stage_loop_origin_repair_acceptance_20261002.md)。本份仍排队，必须实际Gate-H与正式Gate-K放行。完整I01/C01/C02–C04窗口一、C00/TS窗口二及共享Python单写安排见新裁决§7；不重复复用调查，不提前实施。Gate-H仍CHANGES_REQUESTED，正式Gate-K未过。

> 2026-10-01 19:40接续：loop-origin.1虽已交付并恢复合法child，独立回归与接口交付缺口仍阻断Gate-H。当前按README§3.11与[本批裁决§4](stage_loop_origin_acceptance_20261001.md)保管已验内核；本份仍未授权实施，owner写权释放不等于Gate-H/K放行。

> 2026-10-01：本阶段尚未实施。窗口一真实owner复用调查已交付；启动仍等明确本地patch候选的Gate-H与正式Gate-K。当前分工/依赖见README§3.10及[接口裁决§6](h04_loop_origin_escalation_20261001.md)，不能把只读准备当作C/R实现或done。runtime来源补丁仍归第01份H04。

> 2026-09-28 执行计划；所有实现和新测试均待实施。历史代码/环境证据不计为任务完成。

依据：总设计 §§8–10、14、15.1/15.2/15.4、21 WP1b。前后依赖以 [任务表](task_board.json) 为准；接口遵循 [interfaces.md](interfaces.md)。

冻结一次局部 Writer 任务的可执行合同，复用原解析/验收逻辑，通过真实 worker 做无模型 prepare/ingest。

### 复用链与边界

实际 [build_publication_writer_request](../../src/code2paper/llm/section_writer.py) :1666、structured_caller :5172–5526 和 acceptance/progress :6314/6334 是输入/解析/评估 owner；[publication_method_writer](../../src/code2paper/agentic/publication_method_writer.py) :2043 是已落盘响应结算 owner。从这些 owner 抽纯函数，同时让旧同步 caller、本地恢复和新 facade 消费；不建立第二 parser/assessor。

首版输入为已经完成 Formalizer、冻结 Narrative/manifest/plan 的一个 Unified V2 页。prepare 不调用完整 authoring orchestrator，也不通过 binder_caller=None 消除本来需要的语义任务；需要独立模型验证时输出 pending_validation，留给 G06。C03 中的局部确定性绑定不等于 G05 的最终全文 Binder。

### 执行组成必须绑定实际字节

[capture_engine_source_snapshot](../../src/code2paper/agentic/authoring_execution_identity.py) :272 绑定 HEAD 和 Git 可见 dirty/untracked 内容；未忽略的 integrations 源码/lock 会纳入，但 ignored 构建 JS 和 .dsh-dev/runtime 不会。第01份已生成 integrations/dsh/lib 与0.2 staged bundle，实际构建/Loader解析字节须由 I01 composition 覆盖。_hash_file :246 对 symlink 只记链接字符串，不能证明解析目标字节。当前开发 read_manifest 已逐次核 runtime 全树，activate/audit/staging 也各自核受控输入；I01 应复用这些已验原语，并补齐生产 prepare/dispatch/resume 使用的实际 Loader、构建、renderer 与组成身份，不能把开发检查等同生产调用方接线。

I01先交付同一个composition构建/校验原语与合同，绑定实际Loader解析位置和字节、build/source/lock、DSH树、Node、preset/persona/terminal schema/renderer/config。真实接线由C02的prepare、R03的dispatch、R04的resume和A01的准入回执分别验收；这些后建调用者不是I01的反向依赖。复用环境inventory，不扫描home/session/cache。继续由原VALIDATOR_BUNDLE_SOURCES维护裁决来源；每个新增/抽取裁决任务同时更新清单并验证digest变化，只登记已落地文件，不能提前填未来路径触发validator_source_missing。共享清单写入由LEAD串行协调。

### 往返与权限

接口字段、frame 限制、原始来源和版本见 [interfaces.md](interfaces.md)。一个确定 fixture 先生成完整私有合同与派生 TaskView，再提交可信 raw terminal envelope，验证同一 parser/assessor/composer/发布 owner。展示内容不能被重新当成正式合同。remaining_content_attempts 是 prepare 快照，发送前 R02 在 lease 中重读真实余额。

C04 只实现已具备领域 owner 的短 RPC。R01/R02 未完成前不能对外提供假的 claim/reserve 成功；无模型往返可通过受控测试上下文，运行派发要等 Gate-R。模型工具、Host 私有方法、operator export 是三个不同入口。

测试需拦截所有 Python 模型/网络出口；对相同合法/非法响应比较旧 caller、新纯入口、response-unsettled 本地恢复结果。故障不得通过跳过 verifier/Binder、补写正文或降低 scope 消除。

## 实施单元

每单元由owner实施、reviewer独立复核；同一文件只能由一个活动任务写入。下列路径标“拟新增”的当前不存在，不是已有能力。

### I01 · 实际执行组成身份及运行字节校验

| 项 | 约定 |
|---|---|
| owner / reviewer | CONTRACT / QA |
| 前置 / WP | K03, K04 / WP1b |
| 独占编辑范围 | `src/code2paper/agentic/authoring_execution_identity.py`（现有）<br>`src/code2paper/integrations/dsh/protocol.py`（拟新增）<br>`integrations/dsh/compatibility.json`（已存在的B00历史记录，保留；本批另写`compatibility.stage03.json`，见整批指令§1）<br>`tests/integrations/dsh/test_composition_identity.py`（拟新增） |
| 步骤与交付 | 保留engine source摘要，交付同一composition构建/严格校验原语，绑定实际Loader解析的bundle JS/DSH运行树/lock/Node/preset/persona/schema与构建输入；复用隔离环境inventory纯逻辑。只登记本任务已存在的裁决来源，后续任务按新增文件增补，不能提前登记不存在文件。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-I01 | 原语识别源码未变而构建JS变、依赖JS变但CLI/lock不变、链接目标字节变和Loader解析到别处；不扫描可变DSH_HOME，不借上游研究SHA。prepare/dispatch/resume/receipt真实接线分别由C02/R03/R04/A01验收，不作为I01反向前置。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_composition_identity.py` |

### C01 · 唯一WriterTaskContract与跨语言wire合同

| 项 | 约定 |
|---|---|
| owner / reviewer | CONTRACT / QA |
| 前置 / WP | I01 / WP1b |
| 独占编辑范围 | `src/code2paper/integrations/dsh/writer_contract.py`（拟新增）<br>`src/code2paper/integrations/dsh/protocol.py`（拟新增）<br>`tests/integrations/dsh/test_wire_schemas.py`（拟新增）<br>`integrations/dsh/tests/wire.test.ts`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 按interfaces.md冻结Python唯一私有合同、派生TaskView、结果schema和版本；组合真实请求、resolved read-set、三类页摘要、model/validator/composition/renderer身份及post-clamp cap与epoch有限额度。Python算canonical digest，TS消费引用。新增裁决源码进入validator清单。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-C01 | Python与TS goldens对Unicode/null/union/extra/整数范围一致；更改作者、材料、模型、工具schema或配置触发身份变化；prepare余额仅快照，记账不改变内容revision。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_wire_schemas.py wire.test.ts` |

### C00 · 真实请求renderer与无模型准备握手

| 项 | 约定 |
|---|---|
| owner / reviewer | DSH / QA |
| 前置 / WP | C01 / WP1b |
| 独占编辑范围 | `integrations/dsh/src/writer-request.ts`（拟新增）<br>`src/code2paper/integrations/dsh/protocol.py`（拟新增）<br>`integrations/dsh/tests/writer-request.test.ts`（拟新增） |
| 步骤与交付 | 定义新bridge私有prepare_projection(WriterInputRef, composition)接口，产出不可变WriterWireProjectionV1：实际文本/工具/模型选项投影、renderer版本、各组成摘要和计量输入；这是拟实现的自有接口，不声称DSH已有dry-run API。用公开SystemPrompt assemble/render与冻结native文本Writer组成，区分loop请求和adapter后provider wire，不访问私有helper。先形成可供Python冻结的投影，再由C02复核/clamp或重编后冻结唯一合同。 |
| 验收 AT-C00 | 真实DSH首请求及实际pi-ai连接隔离假HTTP/SSE服务时，作者/证据bytes、工具schema、model/sampling/thinking和post-clamp cap与投影一致；动态图片/文件及未覆盖转换首版明确拒绝。测试无真实模型，准备不产生send/content attempt；无法证明最终wire对应则阻断C02，不凭assemble结果猜测。 |
| 待形成测试/证据 | `writer-request.test.ts` |

### C02 · 纯prepare与共用解析评估抽取

| 项 | 约定 |
|---|---|
| owner / reviewer | CONTRACT / QA |
| 前置 / WP | C00 / WP1b |
| 独占编辑范围 | `src/code2paper/llm/section_writer.py`（现有）<br>`src/code2paper/agentic/publication_method_writer.py`（现有）<br>`src/code2paper/integrations/dsh/facade.py`（拟新增）<br>`tests/integrations/dsh/test_writer_prepare_ingest.py`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 从structured_caller抽取纯解析/表示恢复/公式splice/归一化入口，由旧caller、本地settlement和facade共用。单页prepare消费已冻结Unified V2材料和Formalizer回执；完成真实DSH wire计量/clamp/必要重编再冻结。隐藏模型Binder留显式外层角色边界。 prepare消费C00不可变projection并核I01组成；比较领域输入/实际投影、计量、clamp/必要重编后冻结。cap或输入变化需重取projection并核对，次数有界，不从源码猜token开销。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-C02 | 网络与所有Python LLM出口拒绝哨兵下prepare/parse可运行；相同输入/响应三条消费路径的正文/metrics/失败码一致；heading-only、extra paragraph、错误公式/atom绑定拒绝，不以None跳过语义门。 B01-G2 的 detail-only 样例不代表非空 atom 义务已验证；新增显式非空 atom/target 的正反例，区分技术页闭合与作者 header 无 atom 的合法路径。 真实prepare面对构建/runtime/renderer字节漂移必须拒绝，不能只在I01单测成立。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_writer_prepare_ingest.py` |

### C03 · 可信结果ingest与局部事务

| 项 | 约定 |
|---|---|
| owner / reviewer | CONTRACT / QA |
| 前置 / WP | C02 / WP1b |
| 独占编辑范围 | `src/code2paper/integrations/dsh/result_ingest.py`（拟新增）<br>`src/code2paper/integrations/dsh/facade.py`（拟新增）<br>`src/code2paper/agentic/final_text_authorship.py`（现有）<br>`tests/integrations/dsh/test_result_provenance.py`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 用真实Host绑定及原始terminal记录驱动共用parser/assessor/局部Binder/composer；映射JSON pointer到允许角色lexical span，通过K02发布正文/acceptance/authorship引用。语义验证未完成为pending_validation；research_required只等待。此阶段用受控调用上下文做无模型往返。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-C03 | 模型自报accepted、closing text替参数、Host补句、错误来源、同task不同结果重放均拒绝；commit后相同重试返回同receipt；局部接受不设置全文candidate_complete/verified_complete/publication_ready。 同task/epoch换有效idempotency key提交不同结果仍冲突；正式终态唯一且绑定实际重算结果与validator摘要。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_result_provenance.py` |

### C04 · 有界worker协议与最小权限facade

| 项 | 约定 |
|---|---|
| owner / reviewer | CONTRACT / QA |
| 前置 / WP | C03 / WP1b |
| 独占编辑范围 | `src/code2paper/integrations/dsh/worker.py`（拟新增）<br>`src/code2paper/integrations/dsh/protocol.py`（拟新增）<br>`src/code2paper/integrations/dsh/facade.py`（拟新增）<br>`tests/integrations/dsh/test_worker_protocol.py`（拟新增）<br>`src/code2paper/agentic/authoring_execution_identity.py`（现有） |
| 步骤与交付 | 定义短调用JSONL RPC、固定method集合、artifact句柄、stdout协议/stderr日志、有界帧和读取；授权先于幂等缓存，再判新提交revision。prepare/record_output/ingest为Host私有，模型只窄读/terminal。尚未完成R01的持久claim不得占位成功。 同步维护原VALIDATOR_BUNDLE_SOURCES版本化来源清单，仅添加本任务已落地的裁决文件；由LEAD串行分配该共享文件写权。 |
| 验收 AT-C04 | 跨run/task/任意路径、重复键、非有限数、未知schema/字段、超帧、坏idempotency均拒绝；慢模型不占worker调用；取消与进程静止合同可测，所有方法无隐藏LLM。 仅改变新增/抽取的裁决逻辑即可使validator身份变化，缺来源文件明确拒绝。 |
| 待形成测试/证据 | `test_worker_protocol.py` |

## 验证、交接与完成门

以下是实施后的执行命令，本轮未运行；所列旧文件已确认存在。新增任务测试落地后按上表AT逐项运行并登记实际节点/断言，不可只登记文件名。

```bash
python -m pytest -q tests/test_llm_section_writer.py tests/test_agentic_publication_method_writer_unified.py tests/regression_20260922/test_authoring_contract_closure.py tests/test_agentic_final_text_authorship.py
npm --prefix integrations/dsh run typecheck
npm --prefix integrations/dsh run build
npm --prefix integrations/dsh run test:compat
git diff --check
```

Node脚本由B02/H01先定义并锁定，实际运行必须经隔离launcher，不能因脚本缺失而直接在日常profile启动。新增Python测试在tests/integrations/dsh/，Node测试在integrations/dsh/tests/；修原owner的反例也扩已有测试，不复制其实现。

交接包包含：任务ID、输入/代码/配置身份、接口及存储版本差异、改动文件、最小反例修前/修后结果、真实接线证据、准确命令/退出码/原始输出引用、未测项与恢复办法。独立reviewer依据 [verification.md](verification.md) 复核；Gate-C要求I01和C00–C04；C01先定schema，C00验renderer，再C02消费实际投影。 各门要求对应AT及跨任务接线，不凭一个helper单测结案。

[返回总执行入口](README.md)
