# Research 定向补证清单（2026-09-13）

最新直接根因和执行顺序见 [产品主链诊断与推进指导](research_to_method_product_delivery_guidance_2026-09-13.md)：
当前两机制的 8 个未处置 operation 带 `path_polarity_conflict`，由跨 if/else 的 AST 顺序边触发，
优先修分支控制语义；配置补证不是其直接解除条件。Candidate Research gate 已通过，三项 strict partial
仍保留。正向证据可经真实 claim/fact 编译消费，负结论才要求对应范围的关闭回执。

本清单为冻结 Run E 现存五个准入失败码与一个配置证据缺口逐项列出：当前证据、缺失内容、
允许的查询范围与结束条件。它只规划补证，不授权模型调用；执行前必须满足该诊断自身的
前置条件（**不要求先满足依赖其结果的 Writer authoring admission**）。

权威顺序不变：总体架构（2026-07-19）→ Writer 设计（2026-07-31）→ Post-R8 执行计划 →
统一修复执行计划（2026-09-12）及其第二、三、四次方向复核。R10 正在实施（已进入循环，跨阶段边界见第四次复核后的修复记录）；本清单不改变任何门禁。首轮分解与定向检索结果见
[Research 五缺口逐项分解与首轮定向证据（2026-09-13）](research_gap_evidence_2026-09-13.md)。

## 0. 前置与共用规则

- 证据身份：冻结 Run E root 与 archive `sha256:58ad15ef…`（887 atoms；`6b2ec29d…` 是 R10 前
  的旧摘要，见第四次复核 §6）；任何结论必须绑定当时的 source/archive digest 与代码身份。
- 负证据规则（R9，第三次复核后）：只有当搜索回执由执行层账本派生、且消费端能用**当前 revision**
  的账本重新认证时，才允许写回“该范围内不支持”。损坏、删除、陈旧回执一律按未决处理。
- 每个条目必须记录：查询语句与范围、命中的文件/符号、读取证据、未读 frontier、停止原因
  （`unsupported_with_scoped_evidence` / `search_inconclusive` / `budget_exhausted`）。
- 结束条件只有三种：①取得可引用的正向证据并进入既有 claim/fact 编译；②取得关闭 frontier 的
  回执后写回有界负结论；③预算/证据不足时保留 `unresolved` 并记录原因。不得改写为“不存在”。

## 1. operation_disposition_unresolved（两个机制）

| 项目 | 内容 |
|---|---|
| 失败码 | `mech_sym:9773c5add7af1f92:operation_disposition_unresolved`、`mech_sym:f6cf5bdfe2ae16f0:operation_disposition_unresolved` |
| 当前证据 | 两机制分别 157/217 个 operation，6/2 个未处置，均带路径极性冲突；这是 Candidate 也需满足的结构完整性门；`unknown_core_active_path_count=0` 不代表全部 operation 已处置 |
| 缺失内容 | 首先修复 AST 顺序边与 branch dominance 对互斥分支的错误连接/传播；修复后若仍有未知路径，再按其真实 typed 原因定位入口或配置证据 |
| 允许查询范围 | 该机制已冻结的 candidate symbol/path 集合（`candidate_symbol_ids`）；如需越界必须先记录扩展理由 |
| 必查项 | ①入口点（`find_entrypoints`/`inspect_configuration`）②该 operation 的谓词在冻结树中的出现位置（`search_code` + `read_code_span`）③控制流/数据流关系（`trace_call_path`/`trace_data_flow`） |
| 结束条件 | 每个 operation 得到 disposition 或带关闭回执的负结论；否则保留 unresolved |
| 已有反例约束 | 不得把“未找到入口”当作 operation 不存在；配置选择证据缺失时继续标 `NEEDS_RESEARCH_EVIDENCE` |

## 2. strict `core_intent_partial_without_terminal_gap`（三条）

| obligation | 当前证据 | 缺失内容 |
|---|---|---|
| `O-METHOD-MAINLINE-01-c8146479` | strict partial，无终端 gap 证明 | 该 obligation 的 typed target 中哪些已被冻结事实部分满足、哪些仍缺关系/跨度证据 |
| `O-STAGE-01-039a963a` | 同上 | 同上 |
| `O-STAGE-03-2c5bd758` | 同上 | 同上 |

- 每条必须逐项列出：`typed_behavior_targets`（desired_predicates + scope）、已匹配事实、
  未匹配目标、以及“缺的是入口/配置/关系/跨度”中的哪一类。
- 允许查询范围：obligation 的 candidate scope；跨机制引用必须先经 owner 判定。
- 结束条件：取得可编译事实并进入既有 claim 编译（→ partial/supported），或在完整关闭回执后写回
  有界 gap（→ `explicit_gap`）；两者都不成立时保持 `unresolved` 并保留原始数据。
- 禁止：把 strict partial 通过放宽 qualifier、缩小 target 或改写 claim 的方式“解决”。

## 3. 配置选择证据（`self.cfg.use_dedicated_attention` 类）

| 项目 | 内容 |
|---|---|
| 当前证据 | 该配置在冻结树中被引用；本轮已取得 definition span、entrypoint 绑定与 override chain（详见下方“进展”） |
| 缺失内容 | 生产路径写回 `ConfigurationClaimV1`（当前 run 的 claim 仍为 `state=unresolved`，未自动消费新证据） |
| 允许查询范围 | 定义文件与入口文件（`inspect_configuration` 的 span 集合） |
| 结束条件 | 取得 `ConfigurationClaimV1` 级证据（key/value/state/definition+entrypoint spans）或明确记录为未解析；不得默认假定为 true/false |

### 进展（2026-09-13，离线定向检索；详见 [五缺口逐项分解与首轮定向证据](research_gap_evidence_2026-09-13.md) §1.3/§1.3.1）

- definition span：`conf/config.yaml:19` → `use_dedicated_attention: True`（span `span:conf/config.yaml:16:22`）；
- entrypoint 绑定：`main.py:24` `@hydra.main(config_path="conf", config_name="config")` 装配 `cfg`，
  消费点 `src/train_ebcar.py:116`、`src/model/ebcar_dedicated_attention_model.py:145`；
- override chain：`rel:83ef85703286c813`（`CONFIGURED_BY`）从 `if self.cfg.use_dedicated_attention:` 分支
  指向该键的 LOAD 节点；`inspect_configuration` 对 `use_hybrid_attention`/`hybrid_attention`/
  `use_transformer_encoder` 均 `success_empty`（无独立开关）；
- **仍未关闭**：frontier `search_frontier_closed=false`（`unread_candidates:11`，回执
  `receipt:3d0d25cc227b84e0`），且 Run E 是否经 `train_ebcar` 入口的 scenario 绑定未确认；
  因此本条仍保持未决，直到生产路径重新解析该 claim。

## 4. 执行顺序与产出

1. 先做 5.1/5.2 边界的回归确认（已完成：预执行冲突拒绝、消费端账本重验）。
2. 按第 1→2→3 节顺序做定向补证诊断；每项产出：查询清单、命中与读取证据、回执 id、
   disposition/gap 写入或被拒原因。
3. 补证完成后，将实际请求（planned/reserved/measured/spent/unsettled）与提案调用一起并入统一预算账本，
   再做 tokenizer 校准；校准结果绑定完整序列化请求。
4. 只有在上述证据齐备且 Writer 自身准入通过时，才讨论 authoring live。
