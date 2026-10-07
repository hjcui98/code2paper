# B01 Formalizer 正例补齐记录

2026-09-28。实施：kernel_execution_units；独立复核：LEAD（待复核）。
本文件补充原 [39 项历史报告](B01_evidence.md)，不把历史结果改记为修复后结果。
本次只修改 B01 夹具与 `test_legacy_characterization.py`；无生产代码、任务板或工具链修改。

## 缺口与交付

原正例虽然调用真实编译器、Writer builder/assessor/Binder，但 `formula_packages=()`，
`ob:rescale` 未有 Formalizer 完成产物，不能满足 B01 卡的“已完成 Formalizer”前置。
本次新增 `completed_formalizer_fixture.py`、可读合成源 `synthetic_rescale.py` 和
`golden/completed_formalizer_page.json`，原三份 golden 的字节保持不变。

新正例使用原 owner 的顺序为：

1. `RepositorySourceManifestV1` 绑定合成源的路径、SHA-256、可解析 span；operation/detail
   均有 `first_party_executable` 来源。`build_unified_context_archive_v2` 与 workset compiler
   构造真实 Unified V2 输入。材料只代表合成夹具，不宣称真实研究或产品事实已验证。
2. `build_consumer_invocation_plan_v1(phase="formalizer", max_attempts=1)` 冻结计划；
   `execute_formalizer_invocation_plan` 接收离线确定性 caller，保留默认
   `UnifiedFormalizerResponseV2` parser 和 `validate_mechanism_formula_package`。
   没有替换 parser、validator 或 acceptance，也没有手写 accepted/complete。
3. 原 executor 得到一个 accepted 包，覆盖 `ob:rescale`，绑定 `op:rescale`；实际观察为
   一个 main caller 调用、零 repair，receipt 为 delivery accepted、task complete，失败集为空。
   这里的 caller 调用是 fixture provider，不是模型网络请求。
4. 原 `adapt_mechanism_formula_package_to_legacy` 绑定段落，原 workset compiler 和
   `_writer_section_inputs_v2` 将包/义务送入真实 Writer request。Narrative 和页中保留公式路由。
5. 离线 Writer 给出 placeholder；原 `splice_formula_placeholders` 插入包的精确公式字节，
   原 Binder 附加来源 witness。真实 parser、内容 assessor 和段落两阶段判定接受；
   `formula_exact_body_count=1`、`formula_consumed_count=1`、局部失败集为空。

三个反例仍走同一 executor：注入 `accepted` 未知字段由默认 parser 拒绝；替换义务 ID
报告 `llm_result_missing`；乘法改加法报告 `missing_required_operator` 及公式表达式不一致。
三者均无 accepted 包、不进入 Writer、无自动 repair。

## 修前与修后执行

证据根：`/tmp/c2p-dsh-b01-fixture-repair-20260928-_viipk9a/`。
精确 argv/退出码分别保存在 `before.json`、`after-commands.json`；stdout/stderr 分开保存。
测试进程设置 `PYTHONDONTWRITEBYTECODE=1`，pytest 关闭 cacheprovider，测试产物位于新 `/tmp` 根。

| 检查 | 实际结果 |
|---|---|
| 新增验收测试，修前 `pytest ... -k 'completed_formalizer or formalizer_rejects'` | exit 1；4 failed、39 deselected；不存在完成 Formalizer 的 fixture API |
| `python -m pytest -q -p no:cacheprovider --basetemp <root>/focused-tmp tests/integrations/dsh/test_legacy_characterization.py` | exit 0；43 passed in 5.57s |
| `python -m pytest -q -p no:cacheprovider --basetemp <root>/related-tmp tests/test_agentic_mechanism_formalizer.py tests/test_agentic_unified_context_compiler.py tests/regression_20260917/test_page_contract_recheck.py tests/test_agentic_publication_method_writer_unified.py` | exit 0；84 passed in 8.49s |
| `PYTHONHASHSEED=0/1/7/random` 四次 `build_all()`，逐文件 SHA-256 比较 | 四次 exit 0，全部摘要一致，包括新公式正例 |

完整原执行结果在 `<root>/formalizer/formalizer_execution.json`，请求及离线原始答复在
`formalizer_provider_observations.json`。完整结果保留原 receipt 时钟及 content_digest。
golden 中 `formalizer.receipts` 则是明确标记的稳定观测投影，去掉时钟及其摘要，不重新封摘要；
它不是 durable receipt，也不能用作生产准入凭据。后续 C02 必须使用 `evidence_root` 保存的
完整真实 execution/receipt，或在相同冻结输入下重建；不得用该投影批准生产。
Writer 原始 placeholder 答复单列于
`formula_consumption.raw_writer_text`；`writer.offline_response.raw_text` 是 splice/Binder 后的
本地表示，不能冒充 provider raw HTTP/SSE 或 DSH terminal 来源。

## 原夹具和遗留事项

原无公式/无 atom 正例及空白名单扩张等反例继续运行。三个原 golden SHA-256：

- `legal_page_with_atoms.json`：`d1311afe693187d1455dec8cc7cd4511e294b5f18a4e21dcd49625c9a5e01a06`
- `author_no_atom_page.json`：`fbcd999db298437c3c39454f2a83e1e1c375bb2b69b33ba189bf2284aea59ddc`
- `invalid_counterexamples.json`：`edb25f5da93eeb772b5cb65124d77da538eca6f1802ca19a99bf3d8ae823d32e`

D1 不在 B01 修生产代码。它影响材料/页/任务合同身份及 Narrative 顺序，不是 runtime
composition 摘要自身变化。K04 负责 `unified_context_compiler.py` 与相应回归，在 Gate-K 前
改为跨 hash seed 保序、page_id/technical digest 稳定；届时反转当前故意记录缺陷的断言。
旧报告的 MA-S1 数值属于原观测；当前探针使用 MA-P1，独立 QA 记录在
`/tmp/c2p-dsh-b01-independent-qa-20260928-nmyskmf1/`。

G1 继续归 K04：helper 缺 actual digest 时跳过比较，生产外层真实字节检查仍在。
G2 已收窄：本例 witness targets 为空、required_atom_count 为 0，仅证明 detail-only 合同，
不证明非空 atom 闭包。C02 必须另补非空 atom 正反例，保留合法作者 header 无 atom 语义，
不能把 technical 页缺 atom 拒绝误说成所有作者段落均需 atom。

新公式正例也只证明声明的局部门；全局 Candidate/Verified 未运行，publication_ready 未获授权。
未运行 Node、DSH、真实模型或服务，未生成准入回执，未提交 Git。B01 状态由 LEAD 独立复核后决定。
