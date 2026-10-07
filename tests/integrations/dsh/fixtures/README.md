# B01 夹具：合法正例与旧路径特征

> 任务：`B01 · 准备合法正例与旧路径特征测试`（owner QA / reviewer LEAD）。
> 验收：`AT-B01`。实现入口：`../test_legacy_characterization.py`。

本目录里除了 provider 的**答复策略**之外，没有任何手写的页、请求、parser、assessor
或 Binder 行为：页由真实候选页编译器分页，请求由真实请求 builder 生成，判定由真实
事务判定函数给出。这里没有第二套分页器。

## 1. 文件

| 文件 | 内容 |
|---|---|
| `legacy_fixture_builder.py` | 生成器：调用真实生产入口，产出下面三份冻结夹具 |
| `golden/legal_page_with_atoms.json` | 合法正例 1：Unified V2 技术页（含真实 atom 义务） |
| `golden/author_no_atom_page.json` | 合法正例 2：作者无 atom 段落页（真实 `page_kind="header"`） |
| `golden/completed_formalizer_page.json` | 新公式正例：真实 V2 Formalizer 完成、accepted 包进入 Writer 页及原 Binder |
| `completed_formalizer_fixture.py` / `synthetic_rescale.py` | 公式交接生成器和可读合成源码；只有 provider 答复被替换 |
| `golden/invalid_counterexamples.json` | 具名非法反例规格（冻结正例 + 一处改动） |
| `golden/provenance.json` | 来源清单：真实 owner、golden 摘要、`golden_historical_digests`（每个 golden 的独立旧摘要出处；无出处者记 `not_proven`）、已知缺陷与特征缺口 |
| `join_page_probe.py` | B01-D1 探针：多段落 join 页在不同 `PYTHONHASHSEED` 下的真实页身份；`family=` 取 `narrative` / `unit_details` / `unit_mechanisms` 之一时为 K04-G5 的单变量顺序对照（默认输出逐字未变） |
| `page_split_probe.py` | K04-G4 探针：部分 witness 覆盖的最小计划在页预算下真实分裂，比较输入行与所有分片的义务/公式包/明细多重集；`package_ids=` / `order=` 是 K04-GAP-2 的加法参数（默认输入逐字不变） |
| `formula_family_probe.py` | K04-GAP-2 探针：**非空** `formula_obligation_ids` / `formula_package_ids` 的单变量顺序对照，三层报告（Narrative 序与闭包关联 / 冻结与重算身份 / scope 与整体 binding contract 复核） |

再生成：

```bash
python -c "import sys; sys.path.insert(0,'src'); \
from tests.integrations.dsh.fixtures import legacy_fixture_builder as b; \
b.write_golden('tests/integrations/dsh/fixtures/golden')"
```

## 2. 真实 owner（不含测试替身）

* 归档/分页：`build_unified_context_archive_v2`、
  `build_consumer_workset_manifest_v2`、`extend_writer_worksets_from_narrative_plan`、
  `build_consumer_invocation_plan_v1`、`consumer_response_json_schema`
* writer 输入与请求：`_writer_section_inputs_v2`、`build_publication_writer_request`
* 判定：`assess_publication_writer_response`、`assess_publication_content_acceptance`、
  `assess_paragraph_transaction`（`writer_content` 与 `final_bound` 两个阶段）、
  `bind_paragraph_witnesses`
* 发送前复核：`page_contract_snapshot_from_payload`、
  `compare_actual_request_to_page_contract`、`page_output_cap_failures`
* 分句：`final_text_claims._sentence_spans`
* 页模型闭合：`ConsumerTechnicalPageV2`、`compute_technical_page_id`

唯一的替身是**离线确定性 provider**：它按实际请求里的页合同生成一条含 exact excerpt
的正文与 witness 声明，不联网、不调用真实模型，也不认识任何项目答案。

## 3. 确定性

* 每个 writer 页恰好一个语义段落，因此真实编译器内部累加顺序不影响夹具；
  `build_all()` 在 `PYTHONHASHSEED` 取 `0/1/7/random` 时字节完全一致。
* 多段落页的 Narrative 保序由 K04 修复（原缺陷 `B01-D1`），见下。

## 4. 已记录的生产缺陷与特征缺口

`golden/provenance.json` 里机器可读，测试里逐条断言。

### B01-D1（K04 已修复）

`extend_writer_worksets_from_narrative_plan` 生成的多段落页，
`technical_payload["paragraph_ids"]` 的顺序曾来自 `set` 迭代：
`_flush_current()` 把 `set(current_paragraph_ids)` 直接传进 `_payload()`，而
`_payload()` 的注释明确要求"保序去重"。同一输入在不同 `PYTHONHASHSEED` 下因此得到不同的
段落顺序，从而得到不同的 `page_id` 与 `technical_bytes_digest`。

* owner 文件：`src/code2paper/agentic/unified_context_compiler.py`
* 修复（K04）：分页累加器改为**保序去重列表**（`_ordered_unique_strings`），flush 与合并
  全程保持 Narrative 顺序；未固定 seed、未按字典序重排、未改夹具材料。
* 证据：`test_legacy_characterization.py::test_join_page_identity_and_narrative_order_are_stable_across_hash_seeds`
  （跨 `PYTHONHASHSEED=0/1/2/3/random` 的独立进程断言段落顺序、`technical_bytes_digest`
  与 `page_id` 一致；探针默认计划是**非字典序**的 p2→p10）
* 原特征断言 `test_join_page_identity_is_not_stable_across_hash_seeds` 与 B01 日志保持原字节，
  作为历史证据；`golden/provenance.json` 的 `known_defects.B01-D1.status` 记为 `fixed_by_K04`。

### B01-G1（特征缺口，归 K04）

`compare_actual_request_to_page_contract` 只在**实际 payload 自己声明**技术字节摘要时
才比较它；unified V2 writer 页请求的 `input_payload` 不声明该字段，所以仅靠这个 helper
时"改技术材料但保留旧声明"不会被发现。生产接线里另有外层逐字比较兜底，K04 要把这件事
收敛到公共发送合同。

* 证据：`test_legacy_characterization.py::test_absent_actual_technical_digest_is_not_detected_by_the_helper`

### B01-G2（特征，归 C02）

当前 detail-only 样例的 `witness_contract.targets=[]`、`required_atom_count=0`；
只证明这份合同的 required target 集合，不证明非空 atom 义务已经闭合。C02 仍须添加
显式非空 atom 合同的正反例。缺 atom 的 technical 页被页模型拒绝；合法作者 header 页
允许无 atom，二者不得混淆，也不能据当前样例放松原 atom 内容门。

* 证据：`test_legacy_characterization.py::test_atom_obligation_is_carried_by_the_detail_not_a_separate_target`

## 5. AT-B01 的边界

合法正例只证明它们**自己声明的局部门**（`writer_content` + `final_bound` 页事务）。
旧路径的全局验证状态由真实产品运行记录为
`candidate_validation_status="not_run"`、`verified_validation_status="not_run"`、
`verified_complete=false`、`publication_ready=false`。**旧夹具的 Verified 为空，
不能当作新桥已正确验证的证据**；新桥是否成立由 Gate-H 及其后的 C/R/V 任务证明。

夹具材料是合成的 `rescale` 机制，不含凭据，也不含真实项目答案；测试会断言夹具里没有
`api_key`/`sk-`/`Bearer `/`/tmp/`/家目录路径。

## 6. Formalizer 补齐后的证据边界

新增公式正例调用真实 `execute_formalizer_invocation_plan`，保留默认
`UnifiedFormalizerResponseV2` parser 和 `validate_mechanism_formula_package`。
原 executor 生成 accepted package 与 complete receipt；provider 不能自报 accepted。
真实源清单绑定 `synthetic_rescale.py` 的路径、摘录和字节摘要。原 adapter、workset compiler、
Writer builder、`splice_formula_placeholders` 与 Binder 完成包的消费；未知字段、缺失义务及
乘法改加法均由原门拒绝。原三份 golden 字节未变，空公式白名单反例继续保留。

golden 中 receipts 是明确标注的稳定观测投影，省略时钟及其 content_digest，不能作为 durable
receipt 或准入凭据。调用 `build_completed_formalizer_fixture(evidence_root=...)` 可在新证据根保存
完整原执行结果（含真实回执摘要/时钟）。Writer 原始离线答复含 placeholder；golden 的
`writer.offline_response.raw_text` 是原 splice/Binder 之后的本地表示，来源在 `formula_consumption`
显式标记，不能冒充 provider HTTP/SSE 或 DSH terminal 字节。

原 39 项历史结果保存在 [B01_evidence.md](B01_evidence.md)，补齐结果单列于
[B01_formalizer_repair_evidence.md](B01_formalizer_repair_evidence.md)。
