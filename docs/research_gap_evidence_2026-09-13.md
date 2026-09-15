# Research 五缺口逐项分解与首轮定向证据（2026-09-13）

本文件由脚本从冻结产物与定向检索结果派生，不是人工转录：

- 分解：`.tmp/c2p-gap-evidence-20260913/decompose_gaps.py` → `gap-decomposition.{json,md}`
- 首轮定向检索：`.tmp/c2p-gap-evidence-20260913/probe_unresolved_targets.py` →
  `unresolved-target-evidence.json`

两次运行都 `model_calls_allowed=false`，只使用生产研究工具（确定性层）与冻结仓库快照。
本文件记录**已取得的证据与仍然未决的部分**；未取得关闭回执的条目一律保持 unresolved。

## 0. 身份

- run root：`/tmp/ebcar-live-terminal-disposition-fix-20260911-142500`
- repo root：`/data1/users/cuihengjia/code2paper/code_final/EBCAR - Embedding-Based Context-Aware Reranker`
- archive：`sha256:58ad15efbc1b497…`（887 atoms）
- offline report：`/home/cuihengjia/agent/Code2Paper copy/.tmp/c2p-unified-repair-20260913-r10/offline/offline-ebcar-r10.json`
- offline report sha256：`sha256:fb1d9da11c7f9af…`
- snapshot：`repo:9b4f1a34c70f10c2317f024df585e282c9d02371586a629e00ace26d8988c942` / `sha256:9b4f1a34c70f10c…`

准入失败码（离线重算，未变）：

- `mech_sym:9773c5add7af1f92:operation_disposition_unresolved`
- `mech_sym:f6cf5bdfe2ae16f0:operation_disposition_unresolved`
- `unified_core_intent_partial_without_terminal_gap:O-METHOD-MAINLINE-01-c8146479`
- `unified_core_intent_partial_without_terminal_gap:O-STAGE-01-039a963a`
- `unified_core_intent_partial_without_terminal_gap:O-STAGE-03-2c5bd758`

## 1. 两个 mechanism：`operation_disposition_unresolved`

| mechanism | 离线重算失败码 | 运行记录 detail |
|---|---|---|
| `mech_sym:9773c5add7af1f92` | operation_disposition_unresolved | — |
| `mech_sym:f6cf5bdfe2ae16f0` | operation_disposition_unresolved | core_detail_active_path_unknown:detail:mech_sym:f6cf5bdfe2ae16f0:22 |

状态：**未决**。两个 mechanism 的逐 operation 分解必须在 `artifacts/06_authoring/mechanism_context_set_v1.json`（digest `sha256:2479435fe9d0866…`）上重跑 completeness 编译器；离线报告只保留失败码，没有保留未处置 operation 清单。
注意 `mech_sym:f6cf5bdfe2ae16f0` 的运行记录 detail 是 `core_detail_active_path_unknown:detail:…:22`，与离线重算的 `operation_disposition_unresolved` 不是同一判定，重跑时必须同时解释两者。

### 1.1 逐 operation 分解（`current_compiler_rebuild`）

在冻结输入上重跑 completeness 编译器（`decompose_mechanisms.py`，模型调用 0）可稳定复现两个失败码：

| mechanism | 失败码 | operation 数 | `explicitly_unresolved` | terminal coverage |
|---|---|---|---|---|
| `mech_sym:9773c5add7af1f92` | operation_disposition_unresolved | 157 | 6 | 1.0 |
| `mech_sym:f6cf5bdfe2ae16f0` | operation_disposition_unresolved | 217 | 2 | 1.0 |

### 1.2 未处置 operation 的逐项证据

对每个未处置 operation 读取冻结 span、解析 enclosing symbol、检索其操作数/结果词，
并检索选择该路径的配置键；随后尝试关闭 search frontier（R9 账本回执）。

#### `mech_sym:9773c5add7af1f92`

- frontier：`search_receipt_id=receipt:caf066735d668b4e, search_frontier_closed=false, search_result_truncated, unread_candidates:33`；回执 `search-receipt:receipt:caf066735d668b4e`

| operation | 谓词 | 冻结 span | enclosing symbol | 阻塞原因 | 配置键命中 |
|---|---|---|---|---|---|
| `239e368af271ea87` | LOAD | `span:src/model/transformer_encoder_hybrid_attention.py:160:160` | `symbol:src/model/transformer_encoder_hybrid_attention.py:TransformerEncoderWithHybridAttention.forward:144` | `unresolved_detail:detail:mech_sym:9773c5add7af1f92:68` | `use_dedicated_attention`=success, `dedicated_attention`=success_empty |
| `4ef9055671df436f` | CALL | `span:src/model/transformer_encoder_hybrid_attention.py:160:160` | `symbol:src/model/transformer_encoder_hybrid_attention.py:TransformerEncoderWithHybridAttention.forward:144` | `unresolved_detail:detail:mech_sym:9773c5add7af1f92:68` | `use_dedicated_attention`=success, `dedicated_attention`=success_empty |
| `537263d75c9950f6` | LOAD | `span:src/model/transformer_encoder_hybrid_attention.py:160:160` | `symbol:src/model/transformer_encoder_hybrid_attention.py:TransformerEncoderWithHybridAttention.forward:144` | `unresolved_detail:detail:mech_sym:9773c5add7af1f92:68` | `use_dedicated_attention`=success, `dedicated_attention`=success_empty |
| `751877c48e013740` | LOAD | `span:src/model/transformer_encoder_hybrid_attention.py:160:160` | `symbol:src/model/transformer_encoder_hybrid_attention.py:TransformerEncoderWithHybridAttention.forward:144` | `unresolved_detail:detail:mech_sym:9773c5add7af1f92:68` | `use_dedicated_attention`=success, `dedicated_attention`=success_empty |
| `7872fdd517802fb9` | WRITE | `span:src/model/transformer_encoder_hybrid_attention.py:160:160` | `symbol:src/model/transformer_encoder_hybrid_attention.py:TransformerEncoderWithHybridAttention.forward:144` | `unresolved_detail:detail:mech_sym:9773c5add7af1f92:68` | `use_dedicated_attention`=success, `dedicated_attention`=success_empty |
| `dfd7b2b0fe53f46a` | LOAD | `span:src/model/transformer_encoder_hybrid_attention.py:160:160` | `symbol:src/model/transformer_encoder_hybrid_attention.py:TransformerEncoderWithHybridAttention.forward:144` | `unresolved_detail:detail:mech_sym:9773c5add7af1f92:68` | `use_dedicated_attention`=success, `dedicated_attention`=success_empty |

#### `mech_sym:f6cf5bdfe2ae16f0`

- frontier：`search_receipt_id=receipt:bf299b111cb62287, search_frontier_closed=false, search_result_truncated, unread_candidates:6`；回执 `search-receipt:receipt:bf299b111cb62287`

| operation | 谓词 | 冻结 span | enclosing symbol | 阻塞原因 | 配置键命中 |
|---|---|---|---|---|---|
| `2871fbc13260e199` | WRITE | `span:src/model/ebcar_dedicated_attention_model.py:171:171` | `symbol:src/model/ebcar_dedicated_attention_model.py:EBCarRerankerHybridAttention.forward:97` | `unresolved_detail:detail:mech_sym:f6cf5bdfe2ae16f0:39` | `use_dedicated_attention`=success, `dedicated_attention`=success_empty |
| `f79507cf6754fefa` | CALL | `span:src/model/ebcar_dedicated_attention_model.py:171:174` | `symbol:src/model/ebcar_dedicated_attention_model.py:EBCarRerankerHybridAttention.forward:97` | `unresolved_detail:detail:mech_sym:f6cf5bdfe2ae16f0:40` | `use_dedicated_attention`=success, `dedicated_attention`=success_empty |

### 1.3 阻塞 detail 与配置选择证据

未处置 operation 的阻塞点不是“没有证据”，而是承载它们的 supporting detail 的
`active_path_status=unknown`：

| mechanism | detail | importance | active path | span |
|---|---|---|---|---|
| `mech_sym:9773c5add7af1f92` | `detail:mech_sym:9773c5add7af1f92:68` | supporting | unknown | `span:src/model/transformer_encoder_hybrid_attention.py:160:160` |
| `mech_sym:f6cf5bdfe2ae16f0` | `detail:mech_sym:f6cf5bdfe2ae16f0:39` | supporting | unknown | `span:src/model/ebcar_dedicated_attention_model.py:171:171` |
| `mech_sym:f6cf5bdfe2ae16f0` | `detail:mech_sym:f6cf5bdfe2ae16f0:40` | supporting | unknown | `span:src/model/ebcar_dedicated_attention_model.py:171:174` |

本轮针对该 active-path 问题取得的配置选择证据：

- 定义：`conf/config.yaml:19` → `use_dedicated_attention: True`（span `span:conf/config.yaml:16:22`）
- override 链：`rel:83ef85703286c813`（kind `CONFIGURED_BY`）从 `span:src/model/ebcar_dedicated_attention_model.py:145:174` 的分支指向该键的 LOAD 节点，即 `if self.cfg.use_dedicated_attention:` 守卫了 mechanism 2 的掩码装配区间；
- 消费/入口：`flag_consumers` 命中 `conf/config.yaml:19`、`src/model/ebcar_dedicated_attention_model.py:145`、`src/train_ebcar.py:116`；`config_loader`（OmegaConf）命中 `main.py:15/25` 等；直接检索 `config.yaml` 为 `success_empty`（配置由 loader 按变量路径装配）。
- frontier：`search_receipt_id=receipt:3d0d25cc227b84e0, search_frontier_closed=false, unread_candidates:11`；回执 `search-receipt:receipt:3d0d25cc227b84e0`——未关闭，
  因此本文件只登记证据，不写回 claim/disposition；生产路径可用这些 span 重新解析该配置声明。


#### 1.3.1 两个 mechanism 的守卫链（冻结源码直读 + 工具证据）

| 环节 | 冻结位置 | 证据 |
|---|---|---|
| 入口装配 | `main.py:24` `@hydra.main(config_path="conf", config_name="config")` | 该装饰器把 `conf/config.yaml` 装配为 `cfg`（此前 claim 的 `entrypoint_span_ids` 为空） |
| 模型构造 | `src/train_ebcar.py:136` `reranker = EBCarRerankerHybridAttention(cfg, device)` | 无分支，直接构造 |
| 编码器构造 | `src/model/ebcar_dedicated_attention_model.py:22` | `__init__` 中无条件 `TransformerEncoderWithHybridAttention(...)` |
| 分支守卫 | 同文件 `145`–`174` | `if self.cfg.use_dedicated_attention:` （145–167，建掩码） / `else:`（168–174，消融分支 `torch.zeros`） |
| 配置取值 | `conf/config.yaml:19` | `use_dedicated_attention: True` |

由此得到的**有界结论**：

- mechanism 2 的 2 个未处置 operation 位于 `else`（**消融**）分支（171–174），在冻结配置 `True` 下**不活跃**；
- mechanism 1 的 6 个 operation 位于 `TransformerEncoderWithHybridAttention.forward`（`span:...:160`），该编码器由上述链条无条件构造并调用，因此在 train 入口下**活跃**；
- 两者都不是“证据不存在”，而是 completeness 无法仅从 evidence 判定 active path；判定所需的值/定义/入口/守卫四类证据本轮已经齐备。

仍未写回：frontier 未关闭（`search_receipt_id=receipt:9eb23389098ad608`, `search_frontier_closed=false`, `unread_candidates:4`；回执 `search-receipt:receipt:9eb23389098ad608`），且 scenario 绑定（Run E 是否走 `train_ebcar` 入口）需由运行侧确认；本轮只登记证据，不写 disposition、不改冻结产物。

工具证据：`read_symbol`（class+forward 的 span）、`find_references`（仅 `ebcar_dedicated_attention_model.py:13/22` 引用）、`search_code`（`hybrid_attention` 命中 `ebcar_dedicated_attention_model.py:13`、`train_ebcar.py:117`）、`inspect_configuration`（`use_hybrid_attention`/`hybrid_attention`/`use_transformer_encoder` 均 `success_empty`，即不存在独立开关）。

关键关联（本轮新增证据）：两个 mechanism 的 8 个未处置 operation 全部位于
“掩码装配/传入注意力层”的两处分支代码上，阻塞原因都是 `unresolved_detail:*`（对应 detail 的
active path 为 `unknown`）。冻结 Run E 的配置声明显示路径选择键
`self.cfg.use_dedicated_attention`：`value=None`、`state='unresolved'`、`definition_span_ids=[]`、`entrypoint_span_ids=[]`、override_chain 关系数 1，
这正是清单第 3 节的“配置选择证据”缺口，也是这两个失败码的直接上游。

本轮定向检索新拿到：`conf/config.yaml:19:use_dedicated_attention` 定义命中；两处 span 的读取证据；
`attn_mask`/`key_padding_mask`/`causal_mask`/`dedicated_attention_mask`/`torch.zeros` 的检索命中。
但 receipt 明确 `search_frontier_closed=false`（`search_result_truncated`、
`unread_candidates:33` / `unread_candidates:6`），所以
**仍未写回任何 disposition**：按 R9 规则，未读完命中不得写负结论，也不得把“未找到取值”当作不存在。


## 2. 三个 strict obligation：未满足 target 分解

### 2.1 strict 失败的精确条件（读 strict lane 实际读的 research agenda）

strict lane 判定的是 **agenda item**：`must_cover` 且 `partial` 时，必须同时具备
`supported_claim_ids` 与全部 `terminal == explicit_gap` 且带 `attempted_tools` 的
`gap_requirements`。冻结 Run E 的三条 must_cover 均为：

| obligation | agenda status | supported claims | gap requirements | terminal gap | 未满足 typed 要求 |
|---|---|---|---|---|---|
| `O-METHOD-MAINLINE-01-c8146479` | partial | 11 | 0 | False | `typed_semantic:transformations:scores`, `typed_predicate:FILTER`, `typed_predicate:SELECT` |
| `O-STAGE-01-039a963a` | partial | 1 | 0 | False | `typed_predicate:SELECT`, `typed_predicate:TRANSFORM` |
| `O-STAGE-03-2c5bd758` | partial | 8 | 0 | False | `typed_predicate:FILTER` |

因此三条失败的直接原因是 **partial 但没有 terminal gap 记录**（`gap_requirement_count=0`），不是“完全没有证据”：每条都已有 supported claim。
要转成 `supported` 需补齐上表未满足的 typed 要求；要保留 partial 则必须为剩余要求
写出带 `attempted_tools` 的 terminal `explicit_gap`。
结合 §1.2/§4：`FILTER` 一类要求在本轮编译探针中已能在冻结树内找到可编译证据，
`SELECT`/`TRANSFORM` 与 `transformations:scores` 仍需各自检索。


### 2.2 未满足 typed 要求的定向检索（含回执与未读 frontier）

| obligation | 查询 | 状态 | 命中数 | 前几条命中 |
|---|---|---|---|---|
| `O-METHOD-MAINLINE-01-c8146479` | `topk` | success | 2 | `code:src/utils.py:41`, `code:src/utils.py:51` |
| `O-METHOD-MAINLINE-01-c8146479` | `top_k` | truncated | 8 | `code:conf/config.yaml:40`, `code:src/dataset/__init__.py:31`, `code:src/dataset/__init__.py:157` |
| `O-METHOD-MAINLINE-01-c8146479` | `scores` | truncated | 8 | `code:data/real/MS_MARCO_v2/preprocess.py:51`, `code:data/real/MS_MARCO_v2/preprocess.py:52`, `code:data/real/MS_MARCO_v2/preprocess.py:56` |
| `O-METHOD-MAINLINE-01-c8146479` | `transform` | truncated | 8 | `code:conf/retrieval_model/contriever.yaml:7`, `code:conf/retrieval_model/e5.yaml:7`, `code:paperdraft.md:11` |
| `O-METHOD-MAINLINE-01-c8146479` | `select` | success_empty | 0 |  |
| `O-METHOD-MAINLINE-01-c8146479` | `argsort` | success_empty | 0 |  |
| `O-STAGE-01-039a963a` | `select` | success_empty | 0 |  |
| `O-STAGE-01-039a963a` | `transform` | truncated | 8 | `code:conf/retrieval_model/contriever.yaml:7`, `code:conf/retrieval_model/e5.yaml:7`, `code:paperdraft.md:11` |
| `O-STAGE-01-039a963a` | `scores` | truncated | 8 | `code:data/real/MS_MARCO_v2/preprocess.py:51`, `code:data/real/MS_MARCO_v2/preprocess.py:52`, `code:data/real/MS_MARCO_v2/preprocess.py:56` |
| `O-STAGE-03-2c5bd758` | `mask` | truncated | 8 | `code:paperdraft.md:14`, `code:src/model/ebcar_dedicated_attention_model.py:139`, `code:src/model/ebcar_dedicated_attention_model.py:140` |
| `O-STAGE-03-2c5bd758` | `filter` | success | 1 | `code:main.py:34` |

回执与 frontier：

- `O-METHOD-MAINLINE-01-c8146479`：`search_receipt_id=receipt:282cb307beaea049, search_frontier_closed=false, search_result_truncated, unread_candidates:26, search_ledger_has_no_read_candidate`；回执 `search-receipt:receipt:282cb307beaea049`
- `O-STAGE-01-039a963a`：`search_receipt_id=receipt:f0337ea76f93a837, search_frontier_closed=false, search_result_truncated, unread_candidates:16, search_ledger_has_no_read_candidate`；回执 `search-receipt:receipt:f0337ea76f93a837`
- `O-STAGE-03-2c5bd758`：`search_receipt_id=receipt:a216cafff28d876c, search_frontier_closed=false, search_result_truncated, unread_candidates:9, search_ledger_has_no_read_candidate`；回执 `search-receipt:receipt:a216cafff28d876c`

可复核的线索与限制：

- `SELECT` 没有字面命中（`select`/`argsort` 均 `success_empty`），但 `topk` 命中
  `src/utils.py:41/51`——谓词到具体操作的映射应走 `topk`/排序类代码，而不是字面词；
- `TRANSFORM` 的命中主要是配置/依赖噪声（`conf/retrieval_model/*.yaml:7`、`requirements.txt:19`），
  尚未定位到可编译的变换操作；
- `typed_semantic:transformations:scores` 的线索集中在 `data/real/MS_MARCO_v2/preprocess.py`（8 条截断命中）；
- `FILTER` 命中 `main.py:34`（单条），`mask` 命中注意力模型 139–141 等（与 §1 同源）。
- 三组检索的 receipt 都报告 `search_frontier_closed=false`（`search_result_truncated`、
  `search_ledger_has_no_read_candidate`，未读 16/16/9）→ **不写回任何负结论**，
  这些只是下一轮读取与编译的候选。


### `O-METHOD-MAINLINE-01-c8146479`

- coverage：`partial`；matched claims：11；targets 8（未 resolved 2）

| target | status | predicates | unmatched predicates | unmatched relations | unmatched slots | scope-blocked |
|---|---|---|---|---|---|---|
| `target-ea364367e4d9` | resolved | CONSTRUCT, READ | — | — | target-ea364367e4d9:slot:transformation | 0 |
| `target-12488d4db899` | resolved | TRANSFORM | — | — | target-12488d4db899:slot:transformation | 0 |
| `target-d9c93c39b278` | partial | CALL, COMPUTE | — | — | target-d9c93c39b278:slot:transformation | 0 |
| `target-ed708b2e32f0` | resolved | SELECT, SORT, TOPK | — | — | target-ed708b2e32f0:slot:transformation | 0 |
| `target-28d15b78c376` | unresolved | FILTER, MASK | FILTER | — | target-28d15b78c376:slot:transformation | 0 |
| `target-166f0db0c840` | resolved | AGGREGATE, COMPUTE, REDUCE | — | — | target-166f0db0c840:slot:condition | 0 |
| `target-7b0da5299b1e` | resolved | CALL, RETURN | — | — | target-7b0da5299b1e:slot:transformation, target-7b0da5299b1e:slot:condition | 0 |
| `target-22340e7ccc67` | resolved | ATTEND, COMPUTE, MASK | — | — | — | 0 |

### `O-STAGE-01-039a963a`

- coverage：`supported`；matched claims：1；targets 3（未 resolved 0）

| target | status | predicates | unmatched predicates | unmatched relations | unmatched slots | scope-blocked |
|---|---|---|---|---|---|---|
| `target-c6e8f7d3966e` | resolved | CONSTRUCT, READ | — | — | target-c6e8f7d3966e:slot:transformation | 0 |
| `target-b893dce46655` | resolved | TRANSFORM | — | — | target-b893dce46655:slot:transformation | 0 |
| `target-850961f454f2` | resolved | SELECT, SORT, TOPK | — | — | target-850961f454f2:slot:transformation | 0 |

### `O-STAGE-03-2c5bd758`

- coverage：`partial`；matched claims：9；targets 3（未 resolved 1）

| target | status | predicates | unmatched predicates | unmatched relations | unmatched slots | scope-blocked |
|---|---|---|---|---|---|---|
| `target-bf37b467e173` | resolved | TRANSFORM | — | — | target-bf37b467e173:slot:transformation | 0 |
| `target-c56c2da81fd1` | unresolved | FILTER, MASK | FILTER | — | target-c56c2da81fd1:slot:transformation | 0 |
| `target-b28bcf95a54c` | resolved | ATTEND, COMPUTE, MASK | — | — | — | 0 |

交叉核对：`O-STAGE-01-039a963a` 的 coverage 为 `supported` 且没有未解析 target，
因此它的 strict `core_intent_partial_without_terminal_gap` **不是** target 证据缺口；
必须在 claim/qualifier/strict 重算一侧定位。不得为它编造 target 缺口。

## 3. 首轮定向检索（三个未 resolved target）

每个 target 用其自身 `search_terms`/`aliases` 检索，读取前两条命中，再用
`close_search_frontier` 从执行账本派生回执。

| target | predicates | queries（命中数） | 读取 | 回执 | frontier |
|---|---|---|---|---|---|
| `target-28d15b78c376` | FILTER, MASK | `masked`=5；`mask`=8；`filter`=1 | 5 spans | `search-receipt:receipt:9ac3b9003feaa083` | search_receipt_id=receipt:9ac3b9003feaa083；search_frontier_closed=false；search_result_truncated |
| `target-d9c93c39b278` | CALL, COMPUTE | `scores`=8；`predictor`=0 | 2 spans | `search-receipt:receipt:96f17be405a3df00` | search_receipt_id=receipt:96f17be405a3df00；search_frontier_closed=false；search_result_truncated |
| `target-c56c2da81fd1` | FILTER, MASK | `masked`=5；`mask`=8；`filter`=1 | 5 spans | `search-receipt:receipt:7ba3556e345449ac` | search_receipt_id=receipt:7ba3556e345449ac；search_frontier_closed=false；search_result_truncated |

### 3.1 关键命中（候选支持，尚未编译）

- `target-28d15b78c376`：
  - `code:paperdraft.md:14`
  - `code:src/model/transformer_encoder_hybrid_attention.py:45`
  - `code:src/model/transformer_encoder_hybrid_attention.py:51`
  - `code:src/model/transformer_encoder_hybrid_attention.py:104`
  - `code:src/model/transformer_encoder_hybrid_attention.py:113`
  - `code:src/model/ebcar_dedicated_attention_model.py:139`
  - `code:src/model/ebcar_dedicated_attention_model.py:140`
  - `code:src/model/ebcar_dedicated_attention_model.py:141`
- `target-d9c93c39b278`：
  - `code:data/real/MS_MARCO_v2/preprocess.py:51`
  - `code:data/real/MS_MARCO_v2/preprocess.py:52`
  - `code:data/real/MS_MARCO_v2/preprocess.py:56`
  - `code:data/real/MS_MARCO_v2/preprocess.py:58`
  - `code:data/real/MS_MARCO_v2/preprocess.py:60`
  - `code:data/real/MS_MARCO_v2/preprocess.py:62`
  - `code:data/real/MS_MARCO_v2/preprocess.py:64`
  - `code:data/real/MS_MARCO_v2/preprocess.py:76`
- `target-c56c2da81fd1`：
  - `code:paperdraft.md:14`
  - `code:src/model/transformer_encoder_hybrid_attention.py:45`
  - `code:src/model/transformer_encoder_hybrid_attention.py:51`
  - `code:src/model/transformer_encoder_hybrid_attention.py:104`
  - `code:src/model/transformer_encoder_hybrid_attention.py:113`
  - `code:src/model/ebcar_dedicated_attention_model.py:139`
  - `code:src/model/ebcar_dedicated_attention_model.py:140`
  - `code:src/model/ebcar_dedicated_attention_model.py:141`

### 3.2 结论与 disposition

三条 target 都取得了**有界正向线索**（masked/mask/filter/scores 命中模型与入口文件），
但 `close_search_frontier` 明确报告 `search_frontier_closed=false`（`mask` 检索被截断、
命中未全部读取）。按 R9 负证据规则，这**不构成**关闭回执，因此：

- 三个 target 保持 `unresolved`；
- 已记录的查询、命中、读取 span、回执 id 与 stop reason 作为后续编译的输入；
- 下一步是读取剩余命中并把候选 span 交给确定性证据编译（packet → facts → claims），
  使 target 进入 partial/supported，或在读取全部命中后取得关闭回执再写有界负结论。

## 4. 第二轮：确定性编译探针（候选文件 → behavior graph → facts → 对齐）

_本节表格由 `close_unresolved_targets.py` 的 JSON 产物派生；产物缺失时保留标题与限制。_

| target | 期望谓词 | 对齐状态 | 命中谓词 | 未命中谓词 | 未命中 slot |
|---|---|---|---|---|---|
| `target-28d15b78c376` | FILTER, MASK | resolved | MASK | — | 1 |
| `target-d9c93c39b278` | CALL, COMPUTE | partial | CALL, COMPUTE | — | 1 |
| `target-c56c2da81fd1` | FILTER, MASK | resolved | MASK | — | 1 |

- behavior 节点 701，谓词 `BRANCH`, `CALL`, `COMPARE`, `COMPUTE`, `CONCAT`, `LOAD`, `LOOP`, `MASK`, `NORMALIZE`, `READ`, `REDUCE`, `RESHAPE`, `RETURN`, `SORT`, `TRANSFORM`, `WRITE`
- 事实 530（supported 530）

结论（有界，不得外推）：两个 `FILTER`/`MASK` 缺口在冻结树中已有可编译证据——候选文件里 MASK 操作被生产抽取器识别并编译为 supported fact，target 对齐状态为 `resolved`；Run E 未解决是因为搜索/读取覆盖没有落到这些 span，而不是仓库里不存在该操作。`target-d9c93c39b278`（`CALL`/`COMPUTE`）谓词全部命中但仍为 `partial`，差的是 slot 级绑定（该现象在其他已 resolved target 上也存在，属 coverage 阶段的一般行为，不能单独当作根因）。

限制（必须随结果一起引用）：

1. 本轮编译使用合成 obligation id（`gap-evidence`）并一次性编译三个文件的全部节点；它证明“冻结树中存在对应操作”，**不是**“Run E 的该 obligation 会被判为 supported”。
2. 关闭缺口仍需生产路径按该 obligation 读取这些 span、生成 packet、编译 fact 并授权 claim；本探针不写回任何 disposition，也不改动冻结产物。
3. 负证据规则不变：本探针没有关闭任何 search frontier。

## 4.1 未满足要求的编译探针（候选文件 → facts → 对齐）

候选文件：`src/utils.py`, `data/real/MS_MARCO_v2/preprocess.py`, `main.py`, `src/model/transformer_encoder_hybrid_attention.py`, `src/model/ebcar_dedicated_attention_model.py`；behavior 节点 1000，事实 761（supported 761）。

| obligation | target | 期望谓词 | 对齐状态 | 命中谓词 |
|---|---|---|---|---|
| `O-METHOD-MAINLINE-01-c8146479` | `target-12488d4db899` | TRANSFORM | resolved | COMPUTE, CONCAT, NORMALIZE, RESHAPE, TRANSFORM |
| `O-METHOD-MAINLINE-01-c8146479` | `target-ed708b2e32f0` | SELECT, SORT, TOPK | resolved | SORT |
| `O-METHOD-MAINLINE-01-c8146479` | `target-28d15b78c376` | FILTER, MASK | resolved | MASK |
| `O-METHOD-MAINLINE-01-c8146479` | `target-22340e7ccc67` | ATTEND, COMPUTE, MASK | partial | COMPUTE, MASK |
| `O-STAGE-01-039a963a` | `target-b893dce46655` | TRANSFORM | resolved | COMPUTE, CONCAT, NORMALIZE, RESHAPE, TRANSFORM |
| `O-STAGE-01-039a963a` | `target-850961f454f2` | SELECT, SORT, TOPK | resolved | SORT |
| `O-STAGE-03-2c5bd758` | `target-bf37b467e173` | TRANSFORM | resolved | COMPUTE, CONCAT, NORMALIZE, RESHAPE, TRANSFORM |
| `O-STAGE-03-2c5bd758` | `target-c56c2da81fd1` | FILTER, MASK | resolved | MASK |
| `O-STAGE-03-2c5bd758` | `target-b28bcf95a54c` | ATTEND, COMPUTE, MASK | partial | COMPUTE, MASK |

结果：7/9 个相关 target 在冻结树内即可对齐为 `resolved`；`TRANSFORM`、`SORT`（SELECT 家族）与 `MASK`（FILTER 家族）均取得可编译事实。
限制同 §4：合成 obligation id、整文件/整符号一次编译，只证明“冻结树中存在对应操作”，
不等于生产路径会把该 obligation 判为 supported；不写回 disposition、不关闭 frontier。

## 5. 仍未完成

1. 两个 mechanism 的逐 operation 分解（重跑 completeness 编译器）。
2. 三个未 resolved target 的剩余命中读取 + 确定性编译（packet/fact/claim）。
3. `O-STAGE-01-039a963a` 的 strict 失败在 claim/qualifier 侧定位。
4. 配置选择证据（`self.cfg.use_dedicated_attention` 类）：definition span、入口绑定与
   override chain，或明确记为未解析。
5. 提案调用计量：planned/reserved/measured/spent/unsettled 全链 + 真实 tokenizer 校准；插入点与约束见 `.agent/implementation.md` 的 2026-09-13（R10 第四片）小节（不能复用 `ActualRequestReceiptV2` 的 pipeline 身份）。

以上每一项都必须在本文件所在检查点的代码身份下重新执行并记录；
本文件不宣称 Run E 准入已通过，也不授权 live。
