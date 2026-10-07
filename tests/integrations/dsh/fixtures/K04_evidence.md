# K04 · 发送前完整实际请求复核、真实材料摘要与 B01-D1 保序（证据与交接）

> 2026-09-28 窗口一实施记录。依据 [第 02 份 §当前启动安排](../../../../docs/dsh_execution_20260928/02_kernel_publication_and_request_guards.md)
> 与 K04 任务卡。状态以台账为准；本文件只登记本轮实际观测。

| 项 | 值 |
|---|---|
| 任务 / 验收 | K04 / AT-K04（owner CONTRACT，reviewer QA） |
| 开发前置 | B01（done）。原完成前置 `B01,H03,H04` 不变：H03/H04 未完成前 K04 最多 review，不登记 done、不通过 Gate-K |
| 授权 | offline_implementation；无 live、无 Git 提交、未改冻结 runtime/日常 DSH |
| 未触碰 | `integrations/dsh/`、package/lock、H01/H02 冻结文件、K01–K03 独占文件（`authoring_execution_identity.py` 仅按授权登记本任务落地的裁决来源） |

## 1. 改动文件与身份

| 文件 | SHA-256 | 改动 |
|---|---|---|
| `src/code2paper/agentic/page_contract_recheck.py` | `2e0c436baabb3a186416a32f0017608755ae4b8ffb62017508ab1d37b9313a13` | 公共复核新增 `actual_technical_bytes_digest`（调用方从**实际材料字节**重算）；不再读 payload 声明值；有冻结摘要而重算缺失 → `technical_bytes_unknown`（fail-closed） |
| `src/code2paper/agentic/unified_context_compiler.py` | `d02ee446e1cb1c5c480aa1d54a3d2889c3b4df623b8747282ab047743a4b791f` | B01-D1：分页累加器由 `set` 改为保序去重列表（`_ordered_unique_strings`），flush/合并全程保持 Narrative 顺序 |
| `src/code2paper/agentic/publication_method_writer.py` | `f4b2e04c6e44641373ae09a1503b94dae984fa2ec903ce3527f9011d62da3755` | 真实 Writer 调用点把 `actual_page_digest`（由 `shared_contexts` 实际字节重算）传给同一公共复核 |
| `src/code2paper/agentic/authoring_execution_identity.py` | `8d2718e27a2c51513b4fcc7794ec339e5bd2472780e3540ca77a4b0e00e6f9be` | `VALIDATOR_BUNDLE_SOURCES` 仅追加本任务落地的裁决来源 `page_contract_recheck.py` |
| `tests/regression_20260917/test_page_contract_recheck.py` | `02f3c4063c4a61e86f0dd36d18b4b4679acb69891c51b78e2e07d78756c89bf7` | 新增 5 项 K04 摘要矩阵；`_compare` 默认传重算值 |
| `tests/regression_20260922/test_authoring_contract_closure.py` | `41f980278884b6d057772e8b28a1722e6c17a780091ea9eefeeaa73bb55b827e` | 新增真实发送点零发送：冻结摘要与重算值不符 |
| `tests/integrations/dsh/test_legacy_characterization.py` | `485489adb0858dca8a7655b5d5dac6e096a3ce0103e8a2c669122bb4137e1343` | 反转 B01-G1 特征断言；B01-D1 改为跨 seed 稳定性回归 |
| `tests/integrations/dsh/fixtures/join_page_probe.py` | `3f5598ed66a4958419b0483d7fc78f1622127f16352069c5bfa1068ab1b771b3` | 默认计划改为**非字典序**（叙述 p2→p10）；输出 mode / 段落顺序 / 技术字节摘要 / page_id |
| `tests/integrations/dsh/fixtures/legacy_fixture_builder.py` | `4384d0e45ba04e9b8997b8a9ca43de34aca439b7dea049a77b3d254a7b7965eb` | provenance：`B01-D1` → `fixed_by_K04`、`B01-G1` → `fixed_by_K04`（保留原证据引用） |
| `tests/integrations/dsh/fixtures/golden/provenance.json` | `3d264afc6f696cd1f95ec9e3bfd4df4d435623849dd2a8f9e44fa00888764e13` | 重新生成；4 个页面 fixture 逐字节未变 |

## 2. 缺陷 1：技术字节摘要可被声明值替代、空值直接跳过

修前（`page_contract_recheck.py:319`）：
`actual_technical = payload.get("technical_bytes_digest") or payload.get("page_bytes_digest") or ""`，
随后 `if actual_technical and actual_technical != snapshot...` —— 两处缺口：**读的是声明值**（可随材料一起被改），
且**实际值为空时整段跳过**（unified V2 页请求不声明该字段）。

修后：公共复核接收 `actual_technical_bytes_digest`，由调用方从实际材料字节重算；冻结摘要存在而重算值缺失
→ `actual_page_contract_mismatch:technical_bytes_unknown`。冻结契约本身没有摘要（旧档案在注入字段之前捕获）
仍由 envelope digest 兜底放行——K04 关闭的是**实际侧**的空值跳过，不给旧契约追加追溯性必填字段。

| 反例（合法基准只改目标条件） | 修前 | 修后 |
|---|---|---|
| 缺重算值（材料已改） | 静默放行 `()` | `technical_bytes_unknown` |
| 材料已改 + 重算值随之改变 | `()`（payload 未声明） | `technical_bytes` |
| 材料已改 + 声明字段写旧 hash（伪造） | `()` | `technical_bytes`（声明不能替代重算） |
| repair 改材料 | `()` | `technical_bytes` |
| 合法旧请求（可信适配器从 bytes 补实测值） | 放行 | 放行（重算值与冻结值一致） |
| 真实发送点：冻结摘要与重算值不符 | 请求发出 | **零发送**，`content_acceptance_status=rejected`，`publication_ready=False` |

## 3. 缺陷 2：B01-D1 多段落页身份随 `PYTHONHASHSEED` 漂移

`extend_writer_worksets_from_narrative_plan` 的累加器 `current_paragraph_ids/detail_ids/obligation_ids/package_ids`
是 `set`，`_flush_current()` 把 `set(...)` 传进要求"保序去重"的 `_payload()`，合并时又用
`[*current_paragraph_ids, *paragraph_ids]` 迭代 set → 段落顺序取决于 hash seed。

修后：累加器改为 `list` + `_ordered_unique_strings()` 保序去重（不排序、不固定 seed、不改夹具材料）；
段数计数改用已去重的列表长度。

| 观测（探针，独立子进程） | 修前 | 修后 |
|---|---|---|
| `PYTHONHASHSEED=0/1/2/3` 的 page_id | 互不相同（缺陷特征断言通过） | 四者一致 `page:806ec3e8…` |
| 段落顺序（默认非字典序计划 p2→p10） | 随 seed 变化 | 恒为 `MA-P1_p2,MA-P1_p10`（≠ 字典序） |
| 技术字节摘要 | 随 seed 变化 | 恒为 `sha256:d8776c5d…` |
| 字典序计划对照 | — | `MA-P1_p1,MA-P1_p2`，且与叙述计划的 page_id 不同（证明顺序参与身份） |

特征断言已**反转**为 `test_join_page_identity_and_narrative_order_are_stable_across_hash_seeds`
（跨 `0/1/2/3/random` 断言顺序、摘要与 page_id 一致）；原特征测试名与 B01 日志保持原字节，
`provenance.json` 的 `known_defects.B01-D1.status` 记为 `fixed_by_K04`。

## 4. 命令、退出码与结果

| # | 命令 | 退出码 | 结果 |
|---|---|---|---|
| 1 | `python -m pytest -q tests/regression_20260917/test_page_contract_recheck.py tests/regression_20260922/test_authoring_contract_closure.py tests/regression_20260917/test_formula_dependency_closure.py tests/integrations/dsh/test_legacy_characterization.py tests/regression_20260917/test_validator_bundle_identity.py tests/regression_20260917/test_execution_identity.py` | 0 | **120 passed** |
| 2 | `python -m pytest -q tests/regression_20260922/test_invariants_i1_i10.py` | 0 | 10 passed（含公共复核调用点） |
| 3 | 子进程探针 × 4 seeds（`python -m tests.integrations.dsh.fixtures.join_page_probe [lexicographic]`） | 0 | 顺序/摘要/page_id 逐字一致（§3 表） |
| 4 | `git diff --check` | 0 | 无空白问题 |
| 5 | `python -m pytest -q tests/integrations/dsh/test_legacy_characterization.py`（重生成 golden 后） | 0 | 43 passed（4 个页面 fixture 未变，仅 provenance 变） |

未运行（按卡）：整个发布/索引套件、K01–K03 独占测试、live、CLI/smoke、`integrations/dsh/` 的 TS 构建。

## 5. 边界与未决

1. **K04 未完成、不登记 done**：原完成前置含 H03/H04；本轮只交开发期证据。
2. **公共复核的"共用"范围**：`compare_actual_request_to_page_contract` 是唯一公共入口，Writer 调用点已接入；
   `formalization_agent.py` 仍持有自己的逐字比较（**不在本任务独占范围**），后续 DSH adapter 应按同一入口传
   `actual_technical_bytes_digest`；接线缺口需 LEAD 分配写权。
3. **未测**：真实 provider 发送点的 HTTP 层零发送（本单元在假 provider 边界之前断言）；zstd/发布索引路径；
   `sourceEventSeqs` 级的 callId 复用消歧（属 H03/H04 合同）。
4. **旧身份**：`0918ee7`、B00 清单与历史离线回执保持原身份；本轮不据旧回执批准新代码。
5. **provenance 变更面**：仅 `golden/provenance.json`；页面 fixture 与 B01 原日志未改标。

---

# K04 · 第二轮：G1–G7 收口（窗口一接班）

> 2026-09-29 接班窗口一实施记录。上文 §1–5 是**首轮**证据，保持原字节与首轮身份；
> 本节的哈希、命令与结论只绑定本轮字节，不覆盖首轮记录。状态仍以台账为准：K04 未 done，
> 原完成前置 `B01,H03,H04` 与目标 Gate-H 不变，K01 未开工。

## 6. 接管核对与本轮身份

接管前按第 02 份"最新检查点"逐项核对冻结清单：首轮 10 个文件哈希全部命中，
`publication_method_writer.py` = `92161500…`、`test_authoring_contract_closure.py` = `bfa9acd4…`
正是文档记载的 G1 修复检查点（首轮候选 `f4b2e04c…` / `41f98027…` 已被该检查点取代）。
本轮**保留 G1**，不回滚、不重做，按 §"最新检查点"的待复验状态留给 QA。

| 文件 | 本轮 SHA-256 | 改动 |
|---|---|---|
| `src/code2paper/agentic/unified_context_compiler.py` | `9855889eafa812f8ca521883290c7e72d9b9acf2e5e518cf3fa5b40d0cb296a5` | G4：分片义务/公式包多重集守恒，不守恒具名阻断 |
| `src/code2paper/agentic/formalization_agent.py` | `d847263419657dce2d992d5a0f20fc9bfafad8e317fbdec3e000ff57a8dca738` | G7：no-send 回执不再用存储摘要预填 actual；无请求不发行回执；reader 区分未实测 |
| `src/code2paper/agentic/unified_context_models.py` | `99fbce7e7532a3b399a152b48d4e499a3db08f30440df880fcde155eb1156340` | **范围偏差（见 §13）**：`actual_technical_bytes_digest` 仅对 accepted 必填 |
| `src/code2paper/agentic/page_contract_recheck.py` | `62a01ead78569966853f506eba19ca7c5f3dc9dc26b5bd79627f04ea62899e24` | G3：把"envelope 兜底"的注释改成可验证的 owner 层级与不可达结论（仅注释） |
| `tests/regression_20260922/test_authoring_contract_closure.py` | `5e9d278b6b2198f59782c3d54ff31c8c7bb8a543304574d0d5d9247ff3609d42` | G2 六例 + 正对照；G3 real-caller 两项；G6 生产 spy |
| `tests/regression_20260917/test_page_contract_recheck.py` | `bc0b5d2494bb97691e0fdc45b8572cbdb46a10452b31c74c41d0f25aff2150d5` | G5 家族顺序三项；G6 材料顺序=身份 |
| `tests/integrations/dsh/test_legacy_characterization.py` | `b54c73478963d23c1293f9c2251a7c37dedeb9c8f29bc7ec3107ad4f134e1d1c` | G3 构造拒绝；G4 守恒；G5 单变量家族；G6 旧摘要出处 |
| `tests/integrations/dsh/fixtures/page_split_probe.py` | `554fa1a7417f621c15dab17fff5bf69ff2c42293f50fbafc475d89959b2662e2` | 拟新增：G4 页预算分裂探针 |
| `tests/integrations/dsh/fixtures/join_page_probe.py` | `bfd6c8c266ad908d00a46fd244a8bb62e9daa52cdf65ed1dbf97dba672276739` | G5：新增 `family=` 单变量顺序；默认输出逐字未变 |
| `tests/integrations/dsh/fixtures/legacy_fixture_builder.py` | `c10673a99387e185501dfd6bfd58cb5839e1896928801c8b4b29446661a0645d` | G6：`golden_historical_digests` 登记 |
| `tests/integrations/dsh/fixtures/golden/provenance.json` | `0e3545979d0034d32bae7bd3454b4c550d9228cb2bc91b4ebc30676aac6b7cda` | 重新生成：4 个页面 fixture 逐字节未变（见 §10） |
| `tests/test_agentic_formalization_guards.py` | `374f4096042b528ea729c34e46d5b0922d1ebdc5fe2b78d35a56cc10c4add401` | G7 四项 |
| `tests/integrations/dsh/fixtures/README.md` | `f6a4d2fa77490e007cee92c2f015c914d248653bd9c987461bf668da7cdec464` | 登记新探针文件与 `golden_historical_digests` |

首轮已冻结、本轮**未改**：`page_contract_recheck` 之外的 `authoring_execution_identity.py`
（`8d2718e2…`，VALIDATOR_BUNDLE_SOURCES 本轮无新增落地裁决文件，故未追加）、
`unified_context_compiler` 的 B01-D1 保序逻辑（只加 G4 守恒）、`
test_legacy_characterization.py` 的原 B01 特征断言。`publication_method_writer.py` 本轮未改
（仍为 G1 检查点 `92161500…`）。

## 7. G2 · 六类实际请求变异（真实 Writer caller）

**关键修正已落实。** 六例都满足：冻结合同来自**合法 primary**且不随变异重算；变异只注入
**随后构造的 repair 请求**（同一真实 `LLMRequest` 构造点、同一 `_capturing_writer_caller`
复核点）；`primary_arrivals == 1` 与被变异的 `repair_arrivals == 0` **分开计数**。
不再使用首轮那次"在 `LLMRequest` 构造点无差别变异"的失败实验（它把 realizer 一起改了，
四例因此被无关预算失败截断；本轮按模板 + repair 包过滤，只落在目标请求上）。

harness：`tests/regression_20260922/test_authoring_contract_closure.py::_WriterSendBoundary`，
`observed` 是生产 `compare_actual_request_to_page_contract` 的**只读 spy**（记录冻结合同摘要、
调用方从 bytes 重算的实测摘要与返回的失败码，不改行为）。

| 例 | 实际侧单变量 | 具名目标拒绝 | provider |
|---|---|---|---|
| 正对照 | 无变异（同夹具同预算 `retry_reserve=20000`） | 合法 repair 失败码为空 | primary 1 次 + repair 1 次 |
| G2-1 缺重算值 | `shared_contexts` 置空 | `actual_page_contract_mismatch:technical_bytes_unknown` | primary 1 / repair 0 |
| G2-2 改材料保留旧声明 | 原子内容改 + 声明写回**冻结**摘要 | `actual_page_contract_mismatch:technical_bytes` | primary 1 / repair 0 |
| G2-3 伪造声明 | 原子内容改 + 声明伪造成与新实测**自洽** | `actual_page_contract_mismatch:technical_bytes` | primary 1 / repair 0 |
| G2-4 repair 改材料 | 只改页材料（payload 不声明摘要） | `actual_page_contract_mismatch:technical_bytes` | primary 1 / repair 0 |
| G2-5 空公式 scope 扩张 | 空白名单插入 1 个包 | `…:scope:allowed_formula_package_ids:expected=0:actual=1` | primary 1 / repair 0 |
| G2-6 作者目标变化 | `reader_goal` 改写 | `actual_page_contract_mismatch:author_surface` | primary 1 / repair 0 |

每例断言：`_payload_diff(built_repair, injected)` **恰等于**该例声明的单变量差异；
编译期/运行时 `frozen_technical` 在 primary 与 repair 上是同一个值且等于 primary 实测值
（证明合同没有被重算）；目标码同时出现在**公共复核返回值**与**不可变内容验收记录**；
`publication_writer_result_v1.publication_ready is False`（来自真实产品结果文件）。

修前（本轮 harness 建成之初）G2-1 的实测行为是：公共复核确实给出
`technical_bytes_unknown`，但 `ActualRequestReceiptV2` 以"缺 `actual_technical_bytes_digest`"
抛 ValidationError，拒绝变成 `section_writer_llm_error`，整轮随后被
`unified_consumer_request_rejected:realizer:…unified_invocation_budget_exceeded:…` 掩盖
（未结算的 started marker 保留了预留）。修复见 §13，修后该例零发送、具名、产品结果为
`publication_ready=False`。

## 8. G3 · 无 technical digest 的旧合同由谁承担比较

三项真实实验：

1. `test_g3_unified_contract_cannot_freeze_a_page_without_a_material_identity`
   （`test_legacy_characterization.py`）：**冻结侧确实无摘要**的 unified 形态
   **结构性不可达** —— `ConsumerTechnicalPageV2` 拒绝空 `technical_bytes_digest`，
   `ConsumerInvocationV1` 拒绝空 `expected_technical_bytes_digest`（两句具名报错都被断言）。
   因此不存在"冻结侧无摘要却仍被发送"的合法 unified 路径；旧档案必须走具名只读 reader。
2. `test_g3_primary_material_change_is_caught_by_the_frozen_page_identity`：primary 改材料 →
   **零发送**。生产 spy 证明冻结材料身份来自**冻结页**（等于变异前同页材料摘要），
   不等于变异后的实测值；三个 owner 各自点名：`unified_actual_page_bytes_mismatch`
   （逐字页字节）、`actual_page_contract_mismatch:technical_bytes`（冻结页摘要 vs 调用方重算）、
   `unified_actual_request_envelope_mismatch`（准入期冻结 envelope）。
3. `test_g3_legacy_envelope_without_a_declared_digest_is_verified_by_frozen_bytes`：真实请求
   逐字不声明任何材料摘要（legacy envelope 形态），合法请求仍被发送；spy 断言
   `frozen_technical == measured == payload_measured != ""`（从 bytes 重算）。

据此把 `page_contract_recheck.py` 里"由 envelope digest 兜底"的注释改写成可验证结论：
该分支只可能是具名 legacy reader 走的，unified lane 由冻结页供给冻结值；不再以注释宣称
支持一个不可达形态。**本轮没有为了兼容放松任何新合同。**

## 9. G4 · 分片义务多重集守恒（本轮新发现的产品缺陷）

`fit_narrative_plan_to_page_budget` 只比较 **target** 多重集。真实反例
（`page_split_probe.py`，页预算 1300 → 段落分裂成 3 个分片）：

| 输入行 witness | 分片后的义务 | 修前 failures |
|---|---|---|
| 只有 `ob:g4:1` 的 formula target | `f1=[ob:g4:1]`、`f2=[]`、`f3=[]` → **`ob:g4:3` 消失** | `()`（静默丢义务） |
| 无 target | `f1=[ob:g4:1, ob:g4:3]` | `()` |
| 只有 detail target | `f1=[ob:g4:1, ob:g4:3]` | `()` |

修后同一输入产出
`paragraph_split_obligation_contract_not_conserved:MA-G4_p1:missing=1:duplicated=0`；
明细多重集不受影响；两个合法对照仍是零失败。生产 caller
（`publication_method_writer.py:3653`）把该失败升级为
`narrative_plan_page_budget_unresolved:…`，因此单次真实运行同样零发送。
函数 docstring 已写明退出条件：**合法排除义务需要显式合同前置与可验证的授权变更**，
当前合同没有这种前置，所以函数不放行"少一个义务"的结果，也不替上游兜底。

## 10. G5 · 顺序家族判定（不是"所有 sorted 都是缺陷"）

`join_page_probe.py` 新增 `family=` 单变量对照（默认输出逐字未变，仍为
`paragraph_ids=MA-P1_p2,MA-P1_p10`、`page:806ec3e8…`、`sha256:d8776c5d…`，
即首轮 QA 已验证的字节）：

| family | 实际页请求的 Narrative 段落序列 | 页身份 |
|---|---|---|
| `narrative`（计划段落序列反转） | `p10,p2` —— **跟着计划走**（顺序参与身份） | 改变（`page:ebe2e9d4…`） |
| `unit_details`（纯集合型 detail ID 反转） | `p2,p10` —— **未被重排** | 不变 |
| `unit_mechanisms`（纯集合型 mechanism ID 反转） | `p2,p10` —— **未被重排** | 不变 |

辅助判定（`test_page_contract_recheck.py`）：Narrative 段落序列重排 → `paragraph_ids`
与 `author_surface` 具名拒绝；纯集合族（detail/公式 ID）重排 → 逐项 scope 比较按**排序集合**
进行、不产生 `scope:` 失败，但绑定的整体合同摘要仍按序列化顺序参与身份（fail-closed）。
这是判定记录而非必须改代码：本轮没有为了"容忍重排"去放松冻结身份，也没有大范围去掉 sorted。

## 11. G6 · 实测摘要来源与旧摘要出处

* **生产 spy**（§7 harness）：断言实测摘要非空、等于调用方从 `shared_contexts` 实际字节
  重算的值，并与冻结值一致（合法路径）。这是"来源为 bytes"的可复核证据，不是 mock 推导。
* **同材料只换顺序**：`test_g6_material_order_is_part_of_the_measured_identity`
  在事故归档的真实 payload 上只反转 `shared_contexts[0].detail_ids`（7 项，多重集不变）→
  重算摘要改变、`actual_page_contract_mismatch:technical_bytes` 具名拒绝，冻结契约不变。
  （说明：unified writer 夹具的页材料没有 ≥2 项的标量列表，所以该对照落在同一公共复核的
  真实归档 payload 上，而不是削弱为"改一个字段"。）
* **四个 golden 的独立旧摘要出处**：`provenance.json` 新增 `golden_historical_digests`，
  每个条目绑定出处文件自身的 sha256。3 个 golden 的旧摘要独立登记在
  `B01_formalizer_repair_evidence.md`（`sha256:6efdcac9…`，裸 hex 形式）；第 4 个
  `completed_formalizer_page` **没有任何更早出处**（工作树与 git 历史均无），如实记为
  `not_proven` 并写明"不倒造历史 hash"。四个页面 fixture 本轮逐字节未变
  （`d1311afe…`/`fbcd999d…`/`edb25f5d…`/`d4c60b43…` 与首轮一致）。
* 夹具目录**未被 git 跟踪**：未执行 add/commit；未跟踪状态不作为测试失败。

## 12. G7 · Formalizer 发送前、no-send 回执与合法复用

依据第 02 份 §"Formalizer 的本轮窄写权"（本轮新增窄权：仅 G7 经复现的发送前校验、
no-send/缓存回执来源及其直接消费者），四项真实实验复用 `completed_formalizer_fixture`
的真实 material/manifest/plan，只替换 provider 答复：

1. `test_g7_mutated_actual_request_is_refused_before_the_formalizer_provider`：
   **发送前校验真实存在**（"先发后验"不成立）。只改实际请求的页材料 → provider **零调用**、
   `formalizer_pre_send_rejected:unified_actual_page_bytes_mismatch:…`、无 accepted 包；
   同一夹具不改动时恰好发送一次并被接受，回执实测摘要等于该页 `technical_bytes_digest`。
2. `test_g7_attempt_without_a_request_publishes_no_receipt_and_no_stored_digest`：
   **修前**该路径（缺 caller/config）发行一条 no-send 回执，其
   `actual_technical_bytes_digest` 是计划里的**存储**值 `page.technical_bytes_digest`，
   `actual_request_envelope_digest` 是存储 envelope；该回执随后在终局断言里按
   `actual == expected` 比较并**平凡通过**（存储值当然等于期望值）。修后：请求没构造出来
   就**不发行回执**（与本函数其他构造前失败一致），`actual_main_calls == 0`，
   终局断言只保留诚实的 `actual_main_calls_mismatch`，不再有"页材料已验证"的假象。
3. `test_g7_sent_but_unmeasured_receipt_is_not_read_as_verified`：已发送但 adapter 事后删掉
   页材料 → 回执 `rejected`、实际值记空（未实测）、reader 具名
   `actual_page_bytes_unmeasured`，不产生任何 accepted 包。
4. `test_g7_verified_cache_reuse_does_not_resend_or_reseal`：已验证缓存复用 **零 provider 调用**、
   恢复已接受包、沿用原回执字节（`content_digest` 一致），不重封成一条新的"本次实测"，
   也没有把合法复用变成重发。复用判定仍要求 accepted 回执且 digest/fragment/model 全部匹配，
   未验证的 no-send 回执不会被复用。

修前/修后对照：把 §12.2 的两行修复临时还原后，
`test_g7_attempt_without_a_request_publishes_no_receipt_and_no_stored_digest` 失败
（回执里出现存储摘要）；恢复修后版本同一测试通过。原始探针脚本与临时对照留在
`.dsh-dev/run/w1-k04-g2/`（未跟踪）。

## 13. 范围偏差与需要 LEAD/R02 追认的一处产品改动

`src/code2paper/agentic/unified_context_models.py` 不在 K04 独占编辑范围（属 R02，状态
`planned`）。本轮对它做了一处**最小**改动，理由与影响如下，请 LEAD 登记到 R02：

* 改动：`ActualRequestReceiptV2._validate_receipt` 只把 `actual_technical_bytes_digest`
  从"无条件必填"移出；accepted 分支仍要求非空（原样保留），ledger 接受过滤器仍要求
  `delivery_status == "accepted"` **且** 该摘要等于冻结页摘要。
* 理由：发送前拒绝（缺可重算材料）需要一条**如实记录"未实测"**的回执；原模型使
  `technical_bytes_unknown` 这条 fail-closed 分支无法落盘，拒绝退化为 ValidationError，
  并把整轮引向无关的 realizer 预算失败（§7 末）。这是 AT-K04"缺 digest 具名拒绝"的必要条件。
* 未放松处：accepted 仍必须非空；rejected 行从不参与 accepted 过滤；没有新增旁路。
* schema/legacy reader 与受影响 consumer：`ActualRequestReceiptV2` 是 Python 内部回执模型
  （非跨语言合同，TS 侧不消费）；直接 consumer 为 `unified_invocation_ledger`
  的接受过滤器与 `_envelope_matches`（只在 `delivery_status == "accepted"` 的行上求值），
  以及 Writer/Realizer 的发送前后复核；本轮 481 项受影响套件通过。

## 14. 命令、退出码与结果（本轮）

| # | 命令 | 退出码 | 结果 |
|---|---|---|---|
| 1 | 第 02 份"验证、交接与完成门"所列 7 个文件（registry/publication/index/page recheck/formula closure/closure/legacy） | 0 | **140 passed** |
| 2 | `pytest -q tests/regression_20260917 tests/regression_20260922 tests/test_agentic_formalization_guards.py tests/test_agentic_publication_method_writer_unified.py tests/test_agentic_unified_context_compiler.py tests/test_agentic_third_review_integration.py` | 0 | **539 passed**（含第 1 行的 140 项，两行不相加） |
| 2b | `pytest -q <4 个测试文件> -k "g2_ or g3_ or g4_ or g5_ or g6_ or g7_"`（本轮新增/改写的定向选择器） | 0 | **20 passed**, 145 deselected（QA 可用同一选择器逐项复验） |
| 3 | 子进程探针 × `family∈{"",narrative,unit_details,unit_mechanisms}`（`PYTHONHASHSEED=0`） | 0 | 默认输出与首轮登记字节一致；家族对照见 §10 |
| 4 | `python -m tests.integrations.dsh.fixtures.legacy_fixture_builder`（重新生成夹具） | 0 | 仅 `provenance.json` 变（`3d264afc…`→`0e354597…`），4 个页面 fixture 逐字节未变 |
| 5 | `git diff --check` | 0 | 无空白问题 |

未运行（按卡）：`integrations/dsh/` 的 TS 构建、CLI/smoke、live、K01–K03 的独占实现、
`PublishArtifactTransaction`/索引路径（只读跑了它们的现有测试，未改其代码）。

## 15. 未测项、边界与恢复办法

1. **K04 未 done**：原完成前置 `B01,H03,H04` 与 Gate-H 不变；本轮不登记 done、不通过 Gate-K。
   K01 未开工（其启动条件要求 K04 全部 AT 与阻断项独立关闭）。
2. **G1 仍待 QA**：本轮只核对哈希并保留修复与两个形态的真实拒绝 + 显式 legacy 对照，未独立关闭。
3. **G2 的边界**：六例的第二道检测器是真实 `_capturing_writer_caller`，provider 边界是本测试
   的 caller；未断言 HTTP 层。`repair` 的第二条尝试在六例中不会发生（首次 repair 即被拒发），
   记录的是"被拒 repair 零发送"，不是"整轮零调用"。
4. **G3 的边界**：结论是"unified lane 不可达 + 真实 owner 由冻结页/逐字/envelope 三者承担"；
   若未来引入真正的 legacy reader，必须自带逐字/envelope 比较并经新回归验证，不能复用本结论。
5. **G4 的边界**：反例是"部分 formula target + 未覆盖义务"；修复选择**具名阻断**而不是
   自动改派（改派需要合同前置）。若后续要允许合法排除，须先给出可验证的授权变更再改本函数。
6. **G5 的边界**：单变量家族只在两段落 join 页探针上做；集合族的规范排序"允许"是判定，
   不代表任何入口都不得排序；Narrative 顺序由跨 seed 回归与本轮 family 对照共同固定。
7. **G6 的边界**：第 4 个 golden 的旧摘要**未证明**，不得倒填；出处文件若被改写，登记即失效。
8. **G7 的边界**：只覆盖本函数（Formalizer 计划执行）的发送前/no-send/复用路径；
   未迁移完整 Formalizer，未改模型预算，未弱化缓存验收。`actual_page_bytes_unmeasured`
   是新的具名 reader 结论，QA 可按 `tests/test_agentic_formalization_guards.py -k g7` 复验。
9. **恢复办法**：本轮所有改动都在未提交的工作树上；如需回到 G1 检查点，仅需要还原
   §6 表中 5 个源文件（其余为测试/夹具/证据）。临时探针位于 `.dsh-dev/run/w1-k04-g2/`（未跟踪）。

---

# K04 · 第三批：GAP-1 / GAP-2 / GAP-3 合并补证

> 2026-09-29 窗口一按第 02 份"片段 A / 片段 B"实施。上文 §1–15 保持原字节与第二轮身份；
> 本节只绑定本批字节。**本批没有生产改动**：只新增/修改两份账本**测试**、一个夹具探针与夹具
> README；`unified_context_compiler` / `formalization_agent` / `unified_context_models` /
> `page_contract_recheck` / `publication_method_writer` / `authoring_execution_identity`
> 的哈希与第二批**逐字相同**（§16.8 N4）。

## 16.1 片段 A：同一组真实持久产物，四个 node

`tests/regression_20260917/test_ledger_recovery_matrix.py::build_gap13_artifact_runs` 一次性生成，
把报告写到会话级基目录（`gap13_artifacts.json`）；`test_ledger_recovery.py` 复用**同一份**报告，
不重造账本。四个 node 的字节全部由生产 owner 写出：

| node | 真实形态 | 生成方式（owner） | 持久证据 |
|---|---|---|---|
| (a) | rejected + **空实测摘要** | 真实 Writer caller 在 repair 上因材料不可重算被拒发（K04-G2-1 同一变异） | `attempt-0002.completed.json`：`rejected` / `sent_to_caller=false` / `actual_technical_bytes_digest=""` / `provider_usage=null`，且**无** `attempt-0002.provider-request.json` |
| (b) | 请求未构造 / no-send **无回执** | 严格 unified 下缺 V2 页元数据 → 上游具名阻断 | writer invocation **目录不存在**；失败事实在产品结果 `blocked_reason` |
| (c) | 已发送但**结果不确定** | 真实子进程在 provider 边界 `os._exit(9)`（child rc=**9**） | 只有 `attempt-0001.started.json` + `attempt-0001.provider-request.json` |
| (d) | 已接受且摘要匹配（合法缓存对照） | 真实合法一轮（primary 直接通过内容验收） | `attempt-0001.completed.json`（accepted, `sent_to_caller=true`）+ `content-acceptance.json`（`accepted=true`） |

## 16.2 消费者结论矩阵（同一组产物）

| 消费者 | (a) 拒发+空摘要 | (b) 无回执 | (c) 未知发送 | (d) 合法接受 |
|---|---|---|---|---|
| `read_invocation_ledger_state` | sends=1 / content=1 / remaining=1 / accepted=false / exhausted=false | event_seq=0 / sends=0 / accepted=false | event_seq=1 / sends=0 / accepted=false | sends=2 / content=2 / accepted=true / primary_accepted=true |
| `read_attempt_outcomes` | a1 settled(R=false) / a2 **settled**(R=false, replayable=false) | `()` | a1 `send_outcome_unknown`(**R=true**) | a1 settled(R=false) |
| `reduce_invocation_recovery` | `reserved_not_sent`，accepted=false，unknown=()，forbidden=`count_it_as_a_content_failure` | `reserved_not_sent`，accepted=false | `send_outcome_unknown`，unknown=(1,)，forbidden=`assume_not_sent`+`silently_retry`，allowed=`reconcile_if_the_provider_supports_it` | `accepted_reusable`（contract_digests 取自真实 acceptance sidecar） |
| `build_resume_preflight` | allowed=true | allowed=true | allowed=true（相位级；未知发送由归约结论阻断） | allowed=true |
| `unsettled_reservations` | `()` | `()` | **(1,)** | `()` |
| `unsettled_started_attempt_records`（预算视角） | `[]` | `[]` | attempt=1，`planned_input_tokens=11155`（>0），`plan_source=recorded_plan` | `[]` |
| 真实入口重跑同一 root | 未跑（拒发不消耗尝试，另有矩阵记录） | — | **writer 零新增到达**；复用/拒发按 §16.5 | **writer 零新增到达**；接受回执 `content_digest` 不变；新增文件只能是 pre-send 拒绝 |

## 16.3 GAP-1：拒绝不计 accepted、不命中成功缓存、不被当完成

`test_gap1_rejected_empty_measured_digest_is_not_accepted_or_reusable`：
真实拒发回执的 `delivery_rejection_code` 以 `unified_actual_page_bytes_mismatch:` 开头；
账本只把 attempt-0001 算成一次真实内容尝试（`provider_send_count=1`、`content_attempt_count=1`、
`remaining=1`），`accepted=false`、`primary_accepted=false`、`unsettled_reservations=()`，
归约的 `accepted=false` 且不含未知预留。**缺回执/被拒发都没有被读成"接受"或"完成"。**

`test_gap1_accepted_receipt_is_reused_from_cache_without_resending`（合法对照）：
`accepted=true`、`primary_accepted=true`；`reduce` 在真实 acceptance sidecar 的 `plan_digest`
下给出 `accepted_reusable`、`contract_mismatch=()`；重跑同一 root 时 **writer provider 到达数=0**
（缓存复用而非重发），接受回执 `content_digest` 逐字不变（**不重封**），且新增文件不含任何
`provider-request`。合法复用没有被强制变成重发，也没有换来一次免费重发。

## 16.4 GAP-3：缺回执 ≠ 成功；明确未发送与 unknown-send 策略相反

`test_gap3_no_receipt_attempt_is_not_a_completion_and_failure_stays_audited`：
(b) 的 writer 账本为零事件、零发送、不可接受、**未耗尽**、`read_attempt_outcomes==()`；
产品结果 `status=blocked` 且 `blocked_reason` 含 `unified_unplanned_actual_request` ——
失败事实留在产品结果里，没有消失成"成功"，也没有被当作预算耗尽。

`test_gap3_unknown_send_keeps_reservation_and_blocks_a_blind_resend`（真实崩溃 rc=9）：
`read_attempt_outcomes` 给 `send_outcome_unknown` 且 `reservation_retained=true`；
归约给 `unknown_reservation_attempts=(1,)`、forbidden 含 `assume_not_sent` 与 `silently_retry`；
**预算视角仍保留 11155 tokens 预留**（`plan_source=recorded_plan`），即"缺 usage 不等于零成本"；
重跑同一 root 时 writer provider 到达数=**0**：不盲重发，新增的拒绝回执里具名
`send_outcome_unknown`。

`test_gap13_presend_refusal_and_unknown_send_keep_opposite_reservation_policy`：
同一组消费者上，(a) 明确未发送 → `release_the_reservation` 在 allowed、不保留预留、不进预算视角、
可重新准入（`content_attempts_remaining=1`，拒发不消耗内容尝试）；(c) 结果未知 → 只允许
`reconcile_if_the_provider_supports_it`，**不允许** `release_the_reservation`。两者结论相反，
不是笼统"都不许重发"，也没有把 unknown 改写成明确未发。

`test_gap13_preflight_alone_does_not_clear_an_unknown_send`：前置检查只回答"是否耗尽"（allowed=true），
未知发送必须由归约结论阻断——恢复入口不得只凭前置检查放行。

## 16.5 本批**已复现但未修**的两个缺口（最小反例 + owner）

按第 02 份"若证明需改其生产逻辑，先报告最小反例与具体 owner，不把 K04 扩成 R02"，本批**不改**
生产账本/reducer，只登记：

1. **发送前拒绝的诊断分类过窄。** 真实合同拒发（`sent_to_caller=false`，`delivery_rejection_code`
   不以 `attempt_limit_exhausted:` 开头）在 `writer_attempt_ledger` 里被读成 `settled`，
   `counters.rejected_before_send_events` 不含它、`last_rejection_code` 为空，
   invocation 级归约退化成 `reserved_not_sent` + `cause=no_events`（一个有两段真实事件的账本被
   总结成"没有事件"）。**安全结论不受影响**（不计发送/内容尝试、不保留预留、不命中缓存、
   不可接受、不阻断合法再准入）；`read_attempt_outcomes` 里 `settled` 与 `rejected_before_send`
   的 `reservation_retained` / `acceptance_replayable` 同为 false。
   最小反例：§16.1 (a) 的 `attempt-0002.completed.json`（真实字节）。
   具体 owner：`src/code2paper/agentic/writer_attempt_ledger.py`（R02 owned，本批未转交）。
2. **未知发送的重跑会把根因包成下游错误。** 崩溃预留（11155 tokens）保留后，realizer 的剩余
   预算被压成负数，整轮以 `unified_consumer_request_rejected:realizer:…:unified_invocation_budget_exceeded:run_reservation:3798>-3261`
   终止；writer 的真实根因（`send_outcome_unknown`）仍具名落在持久回执里，但运行级终止原因
   不指向它。最小反例：§16.1 (c) 的 root 重跑（N1 节点内断言）。
   具体 owner：writer 相位预检/下游预算（`publication_method_writer.py` 相位边界与 R02 预算归约）。

以上两条都属"覆盖缺口 + 可复核反例"，本批不声称已修，也不据此关闭任何阻断项。

## 16.6 片段 B：GAP-2 非空公式族的三层矩阵

夹具 `formula_family_probe.py`（与 G4 的 `page_split_probe.py` 同一份材料：单机制技术页、
`formula_obligation_ids` 与 `formula_package_ids` 各 **2** 个非空 ID；obligation 是真实
`MechanismFormulaObligationV1`，package 是与真实请求 payload 同形的序列化记录）。
节点：`test_gap2_nonempty_formula_families_order_contract_three_layers`。

| 变体（单变量） | ① 页/请求 Narrative 段落序 | ① package→source detail 闭包 | ② 页身份（page_id / 技术字节摘要） | ② 请求侧计划行顺序 | ③ 公共复核 |
|---|---|---|---|---|---|
| 基线 | `['MA-G4_p1']` | `{pkg1:(d:g4:1), pkg3:(d:g4:3)}` | `page:37a0a4b2…` / `sha256:b8522ca4…` | 计划顺序 | `()` |
| 计划层重排 `obligation` | **不变** | **不变** | **不变**（计划层重排被规范排序吸收） | 反转为 `(ob3, ob1)`；`allowed_formula_obligation_ids` 随之 | binding-only → `actual_page_contract_mismatch:binding_contract`；all-sites → 另加 `technical_bytes` |
| 计划层重排 `package` | **不变** | **不变** | **不变** | 反转为 `(pkg3, pkg1)`；`allowed_formula_package_ids` 取页材料规范顺序 | 同上 |

三条判定：

* **集合族允许规范排序。** 页材料构造点对两个家族显式 `sorted(set(...))`
  （`unified_context_compiler._section_page_payload`），因此计划层重排**不改变**页身份与摘要；
  这不允许被读成"顺序无关"：请求侧 Narrative 计划行确实保留了计划顺序（上表 ②）。
* **scope 是集合语义。** 两种重排都**没有**产生 `scope:allowed_formula_*` 失败：同一 ID 集
  不构成新的授权。
* **整体摘要仍按有序序列拒绝。** `binding_contract_digest` 顺序敏感 → 具名
  `actual_page_contract_mismatch:binding_contract`；连材料位点一起改时另加 `technical_bytes`。
  本批**没有**为了"通过"弱化摘要。
* 本用例只覆盖非空 formula obligation/package 家族；`unit_mechanisms` 对照（§10）不折抵它们。

## 16.7 命令、节点、退出码与日志摘要（本批新鲜补证根）

补证根：`/home/cuihengjia/agent/Code2Paper copy/.dsh-dev/run/w1-k04-gap/`（未跟踪；**不执行**
会覆盖第二批原日志的 `run_verification.sh`）。复现脚本 `run_gap_batch.sh`
SHA-256 `05c314f12f58be11352bd656950569ae84bbbe5fe09875fe0ff65eb31e2327fe`。

| 日志 | argv 要点 | 退出码 | 结果 | 日志 SHA-256 |
|---|---|---|---|---|
| `N1_gap_nodes.log` | `pytest -v` 两份账本套件 + legacy characterization，`-k "gap1 or gap2 or gap3 or gap13"` | 0 | **7 passed**（节点名逐条在日志里） | `9c2305be6e423fb49d1fa5da857fc36d3add303e56b363e5d164761c066f1213` |
| `N2_affected_regressions.log` | 两份账本套件 + legacy characterization + closure + page recheck | 0 | **145 passed** | `32754bf45f85690260f6a45e676916dd5aed7a4310ce0e8bc979a8265852fa1b` |
| `N3_docs_patch_check_v2.log` | `git diff --check` + 范围界定的本地链接存在性检查 | 0 | 空白 0；本批范围 3 链接 0 悬挂 | `182b97ffffcb95d2f73f588c25cea09afeb3836749d0c5be2493f2b416ac0d38` |
| `N4_identity.log` | 18 个文件 sha256 + K01–K03 空证明 + 5 个 golden | 0 | 产品文件与第二批逐字相同 | `14ada99ff1e67f8a07cb489e3dbefca0db8fc10ede4118d6bf949979d2de41bb` |

每个日志同目录另有同名 `.exit`（内容 `0`）。N3 的第一次运行（`N3_docs_patch_check.log`）保留：
它把 `.agent/implementation.md` 2026-09-14 历史节里 3 个 `/tmp` 链接点成悬挂——那些是本窗口之前
的旧会话临时证据根，历史记录不改标，因此第二次改为**范围界定**检查（两份夹具文档整篇 +
`.agent/implementation.md` 自本窗口首个 K04 节起）。两次日志都保留，不互相覆盖。

## 16.8 本批候选身份

| 文件 | SHA-256 | 本批变化 |
|---|---|---|
| `tests/regression_20260917/test_ledger_recovery.py` | `d9d8d180cf3d764ed9356d537d9fa3073e9c5210a05b47bc0749ede369817132` | 新增 GAP-1/3 恢复策略两节点（+`pytest` 导入） |
| `tests/regression_20260917/test_ledger_recovery_matrix.py` | `605b3d772776b043fc3760f082997c439cc0ab1dc5037d28923b730a79a6381b` | 新增真实产物构造器 + GAP-1/3 消费者四节点（+`SEND_OUTCOME_UNKNOWN` 导入） |
| `tests/integrations/dsh/fixtures/formula_family_probe.py` | `547a5e672ca71c54cf82b269ebaec11ea8e0c5cfd287841011a10e362516a989` | 拟新增：GAP-2 三层探针 |
| `tests/integrations/dsh/fixtures/page_split_probe.py` | `23727000329b788859036de11fca5659a4d8fa518b1a87815ea487611dd83f64` | 加法参数 `package_ids=` / `order=`（G4 默认输入逐字不变） |
| `tests/integrations/dsh/test_legacy_characterization.py` | `5ac6690d055817f1458fce957775266a1b338db9760c5a211962b7611338e172` | 新增 GAP-2 三层节点 |
| `tests/integrations/dsh/fixtures/README.md` | `c4805fc912fcb30c7f07c6d66acdc0156935f9f4bd80b7065c5a687e3991479a` | 登记新探针与加法参数 |
| 产品文件（compiler / formalizer / models / recheck / PMW / identity） | 与第二批相同（见 §16.7 N4） | **零改动** |

四个页面 fixture 与 `provenance.json` 本批未变（N4 已列）。

## 16.9 未测与边界

1. 本批只覆盖账本计数/缓存选择/恢复 reader 与公式族顺序；未改生产账本/reducer（§16.5 两条
   缺口交 R02/后续批次）。
2. (b) node 的"无回执"由严格 unified 上游阻断产生；没有覆盖"进程在构造请求前被杀"的等价形态
   （同一结论由 (b) 的零事件账本代表，未另造第二套账本）。
3. (c) node 的崩溃点是 provider 调用入口；HTTP 层未观测（网络边界仍是观察型 fake provider）。
4. GAP-2 的 package 输入是与真实 payload 同形的**序列化记录**；本层只消费
   `package_id` / `satisfied_obligation_ids` / `source_detail_ids`，未经过真实 Formalizer 生成。
5. K04 仍未 done：原前置 `B01,H03,H04` 与目标 Gate-H 不变；本批不自批、不登记 component PASS。

## 16.10 AT / 意见 → 节点 → 证据 索引（含本批更新）

原 AT 与七项意见不因本批重开；下表给通过证据引用或明确未覆盖，不用总数宣布全项通过。

| AT / 意见 | 节点（真实 owner 接线） | 证据位置 | 状态 |
|---|---|---|---|
| G1 去页元数据 / 缺 manifest 零发送 + 显式 legacy 对照 | `test_missing_v2_page_metadata_under_unified_is_refused_before_the_provider`、`test_missing_writer_workset_manifest_under_unified_is_refused_before_the_provider`、`test_explicit_legacy_mode_still_sends_without_v2_page_metadata`（closure） | §7 | owner 提交；QA 待复验（本批未改） |
| G2 六类实际请求变异 + 合法正对照 | `test_g2_legal_primary_and_legal_repair_reach_the_provider_exactly_once` + 六例 `test_g2_*`（closure，`_WriterSendBoundary`） | §7 | owner 提交；QA 待复验 |
| G3 冻结侧无摘要不可达 + owner 层级 | `test_g3_unified_contract_cannot_freeze_a_page_without_a_material_identity`、`test_g3_primary_material_change_is_caught_by_the_frozen_page_identity`、`test_g3_legacy_envelope_without_a_declared_digest_is_verified_by_frozen_bytes` | §8 | 窗口三已独立关闭 |
| G4 分片义务多重集守恒 | `test_g4_partial_witness_split_must_conserve_the_obligation_multiset` + `fixtures/page_split_probe.py` | §9 | 窗口三已独立关闭 |
| G5 Narrative 请求层顺序 / 集合族 | `test_g5_order_families_are_classified_by_single_variable_reordering`、`test_g5_narrative_paragraph_sequence_is_an_ordered_contract`、`test_g5_set_family_reorder_is_not_a_scope_change` + `join_page_probe family=` | §10 | 请求层通过；**非空公式族**由本批 GAP-2 补齐 |
| GAP-2 非空 `formula_obligation_ids` / `formula_package_ids` 单变量顺序 | `test_gap2_nonempty_formula_families_order_contract_three_layers` + `fixtures/formula_family_probe.py` | §16.6 | **本批新增**，待 QA |
| G6 实测摘要 spy + 旧摘要出处 | 生产 spy（closure G2/G3 节点内）、`test_g6_material_order_is_part_of_the_measured_identity`、`test_g6_every_golden_registers_an_independent_historical_digest_source` | §11 | owner 提交；第四个 golden 保持"历史未证明" |
| G7 发送前/no-send/合法复用 | `test_g7_mutated_actual_request_is_refused_before_the_formalizer_provider`、`test_g7_attempt_without_a_request_publishes_no_receipt_and_no_stored_digest`、`test_g7_sent_but_unmeasured_receipt_is_not_read_as_verified`、`test_g7_verified_cache_reuse_does_not_resend_or_reseal` | §12 | 失败/缓存侧已通过；恢复侧由本批 GAP-3 补齐 |
| GAP-1 拒发+空实测摘要的账本/缓存/恢复 | `test_gap1_rejected_empty_measured_digest_is_not_accepted_or_reusable`、`test_gap1_accepted_receipt_is_reused_from_cache_without_resending` + `gap13` 产物 | §16.1–16.3 | **本批新增**，待 QA |
| GAP-3 无回执与未知发送的持久恢复 | `test_gap3_no_receipt_attempt_is_not_a_completion_and_failure_stays_audited`、`test_gap3_unknown_send_keeps_reservation_and_blocks_a_blind_resend`、`test_gap13_presend_refusal_and_unknown_send_keep_opposite_reservation_policy`、`test_gap13_preflight_alone_does_not_clear_an_unknown_send` | §16.1–16.5 | **本批新增**，待 QA |
| B01-D1 跨进程 Narrative 保序 | `test_join_page_identity_and_narrative_order_are_stable_across_hash_seeds` | §3、§10 | QA 首轮已证明；本批未改默认输出 |
| AT-K04 其余条款（cap 升降、真实计量门、validator 身份） | 见 §7、§13；身份面见 `test_validator_bundle_identity.py` / `test_execution_identity.py` | §13 | 通过证据引用；本批未改 |
| 明确未覆盖 | HTTP 层零发送；TS/CLI/live；K01–K03 实现；发布/索引路径（只读跑了现有测试） | §15、§16.9 | 保持未覆盖 |
