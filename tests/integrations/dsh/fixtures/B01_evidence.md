# B01 证据记录与交接

> 任务 `B01 · 准备合法正例与旧路径特征测试`（owner QA / reviewer LEAD / 验收 `AT-B01`）。
> 本文件是任务交接记录；验收状态由 LEAD 更新 `task_board.json`，此处只登记实际观测。
>
> 历史记录说明：以下 39 项是补齐前的观测，不证明 Formalizer 已完成。后续独立复核及修复见
> [B01_formalizer_repair_evidence.md](B01_formalizer_repair_evidence.md)。该补充纠正本页旧 D1/G2
> 表述：D1 影响材料/页/任务合同身份，归 K04 在 Gate-K 前修复；G2 只证明空 witness targets
> 样例，不能推导非空 atom 闭包。本文旧 seed/页ID举例仅按原记录解释，当前探针使用 MA-P1。

## 1. 改动范围（只碰 B01 分配的路径）

| 路径 | 状态 | 说明 |
|---|---|---|
| `tests/integrations/__init__.py` | 新增 | 让 `tests/integrations` 成为包（与 `tests/regression_*` 同一约定） |
| `tests/integrations/dsh/__init__.py` | 新增 | 同上 |
| `tests/integrations/dsh/fixtures/__init__.py` | 新增 | 夹具包 |
| `tests/integrations/dsh/fixtures/legacy_fixture_builder.py` | 新增 | 真实编译器/请求 builder 生成器 + 离线确定性 provider |
| `tests/integrations/dsh/fixtures/join_page_probe.py` | 新增 | B01-D1 子进程探针 |
| `tests/integrations/dsh/fixtures/golden/*.json` | 新增 | 冻结夹具与来源清单（4 个文件） |
| `tests/integrations/dsh/fixtures/README.md` | 新增 | 夹具说明与缺陷/缺口记录 |
| `tests/integrations/dsh/fixtures/B01_evidence.md` | 新增 | 本文件 |
| `tests/integrations/dsh/test_legacy_characterization.py` | 新增 | 特征测试（39 个用例） |

**未修改任何生产代码**，未修改其他任务的文件（`src/`、`scripts/`、`docs/`、
`integrations/` 均无 B01 改动）。

## 2. 真实接线（不是测试替身）

页与请求来自生产入口：`build_unified_context_archive_v2` →
`build_consumer_workset_manifest_v2` → `extend_writer_worksets_from_narrative_plan` →
`build_consumer_invocation_plan_v1` → `_writer_section_inputs_v2` →
`build_publication_writer_request`（`prompt_template_id == "unified_writer_page_v2"`）。

判定来自生产入口：`try_parse_structured_response_with_trace`、
`_normalize_publication_paragraph_transaction`、`assess_publication_writer_response`、
`assess_publication_content_acceptance`、`assess_paragraph_transaction`
（`writer_content` / `final_bound`）、`bind_paragraph_witnesses`、
`page_contract_snapshot_from_payload`、`compare_actual_request_to_page_contract`、
`page_output_cap_failures`、`ConsumerTechnicalPageV2`、`compute_technical_page_id`。

唯一替身是离线确定性 provider：按实际请求里的页合同生成正文与 witness，不联网、
不调用真实模型。测试用 autouse fixture 拒绝一切 socket 连接。

## 3. 验收 AT-B01 逐条

| AT-B01 要求 | 证据 |
|---|---|
| 正例可通过其声明的局部门 | `legal_page_with_atoms`：`content_accepted=True`、`failures=[]`、`writer_content`/`final_bound` 均 valid；`author_no_atom_page`（真实 `page_kind="header"`）同样通过 |
| 反例具名拒绝 | 20 个具名反例覆盖 5 个面：`page_contract`、`response_parser`、`paragraph_assessor`、`binder`、`page_model` |
| 旧夹具 Verified 为空 ≠ 新桥已验证 | `verified.global_verified_status="not_run"`；真实产品路径实测 `candidate_validation_status="not_run"`、`verified_validation_status="not_run"`、`verified_complete=false`、`publication_ready=false` |
| 无凭据 / 无项目答案硬编码 | 断言夹具不含 `api_key`/`sk-`/`Bearer `/`/tmp/`/家目录；材料是合成 `rescale` 机制 |
| 不构造第二分页器 | 生成器只调用生产入口；未实现任何分页/解析/判定逻辑 |

## 4. 实测命令与结果

| 命令 | 结果 |
|---|---|
| `python -m pytest -q tests/integrations/dsh/` | exit 0，`39 passed in 5.30s` |
| `python -m pytest -q tests/regression_20260917/test_page_contract_recheck.py tests/regression_20260922/test_invariants_i1_i10.py tests/test_agentic_publication_method_writer_unified.py` | exit 0，`60 passed in 6.77s`（相邻既有套件未被破坏） |
| `python -m compileall -q tests/integrations` | exit 0 |
| `git diff --check` | exit 0 |
| 夹具再生成 + 逐字节比较 | `build_all()` 与 `golden/*.json` 完全一致 |
| `PYTHONHASHSEED` 取 `0/1/7/random` 重算夹具 | 四次 SHA-256 前缀均为 `545f3fca7e9629a2`（夹具本身与 hash seed 无关） |

## 5. 发现的生产缺陷（B01 只记录，不越界修复）

### B01-D1 — 多段落页身份随 `PYTHONHASHSEED` 变化（阻断级）

* owner 文件：`src/code2paper/agentic/unified_context_compiler.py`
* 位置：`extend_writer_worksets_from_narrative_plan` 内层 `_flush_current()` 把
  `set(current_paragraph_ids)` 直接传进 `_payload()`；`_payload()` 的注释明确写着
  “段落顺序是**叙述顺序**，必须保序去重”。
* 实测：同一份输入、同一进程外的一次运行，`PYTHONHASHSEED=0` 得到
  `paragraph_ids=["MA-S1_p2","MA-S1_p1"]`、`page:c071fa01…`；`PYTHONHASHSEED=1`
  得到 `["MA-S1_p1","MA-S1_p2"]`、`page:8c302ce2…`。
* 影响：`page_id`、`technical_bytes_digest`、以及发送前 page contract 的段落顺序
  在等价输入下不稳定；I01/C01 要求的“同一 composition 摘要用于
  prepare/dispatch/resume/离线回执”在多段落页上不成立。
* 证据：`test_legacy_characterization.py::test_join_page_identity_is_not_stable_across_hash_seeds`
* 处理建议：由 `unified_context_compiler.py` 的 owner 在分页 flush 处保持插入顺序
  （例如用有序结构或 `list(dict.fromkeys(...))`），随后把该测试改写为“页身份稳定”并
  同步更新 `provenance.json` 的 `known_defects`。

### B01-G1 — 实际请求缺技术字节摘要时该步比较被跳过（归 K04）

`compare_actual_request_to_page_contract` 只在实际 payload **自己声明**技术摘要时才比较。
unified V2 writer 页请求的 `input_payload` 不声明该字段，因此单独看这个 helper，
“改技术材料但保留旧声明”不会被发现（生产接线另有外层逐字比较兜底）。
证据：`test_absent_actual_technical_digest_is_not_detected_by_the_helper`。

### B01-G2 — atom 义务由 detail 语义闭包承担（归 C02）

`required_targets_from_plan_row` 只在没有 `required_detail_ids` 时才返回
facet/field/slot/edge 集合；“作者段落无 atom”的拒绝发生在页/workset 闭合层
（`consumer page {id} must carry atom IDs`），不在段落事务层。
证据：`test_atom_obligation_is_carried_by_the_detail_not_a_separate_target`。

## 6. 未测项与恢复办法

* 未跑 Node 侧（B02/H01 范围）、未启动 DSH、未调用真实模型、未生成准入回执。
* 夹具**不**提供真实 provider HTTP/SSE 字节；H03/V01 若需要原始来源，必须另行捕获，
  本夹具不得冒充。
* 重新生成夹具：见 `README.md` §1；生成后必须重新登记 `provenance.json` 摘要，
  否则 `test_golden_files_are_byte_identical_to_the_real_compiler_output` 会失败。
* 若下游任务（K01/K04/V01）需要夹具增加场景，请在**本目录**内扩展生成器，
  不要复制其实现。
