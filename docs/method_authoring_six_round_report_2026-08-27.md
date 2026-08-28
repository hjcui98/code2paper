# Method Authoring 最近六轮产物、分析与修复汇报

- 日期：2026-08-27
- `as_of`：2026-08-27（绑定 2026-08-25 23:09 至 2026-08-26 23:23 的 gated replay）
- 性质：**带日期的工作汇报 / 证据报告**。只证明本窗口内的代码、冻结研究、模型与协议。
- **不是**新的总体架构规范，**不是** Method Authoring 执行权威（执行权威仍是
  `docs/method_intent_first_authoring_redesign_2026-08-22.md`），**不是**
  `publication_ready` / D5 / §8 PASS / default cutover / release freeze。
- 工作区：`/home/cuihengjia/agent/Code2Paper copy`（Post-R8 dirty tree；本窗口未
  `git reset` / commit / merge）。
- 金丝雀协议（六轮共用，除非该轮另注）：
  - 模型：`qwen38-27b-nvfp4` @ `http://127.0.0.1:8006`，`max_model_len=131072`
  - Profile：`tests/live/profiles/qwen38_vllm_budgeted.example.env`
  - `CODE2PAPER_MAX_CALLBACK_ROUNDS=0`
  - `CODE2PAPER_SECTION_REVISION_BUDGET=0`
  - 入口：`python -u scripts/run_authoring_replay.py <frozen> <fresh> --repo <repo> --rebuild-authoring --persist-authoring-rebuild-manifest --profile … --callback-rounds 0`
- 冻结研究（authoring 重放，不重跑 30-turn 研究）：
  - LinearRAG：`/tmp/c2p-fresh-linearrag-20260825-164605`
  - DyG：`.tmp/c2p-stage1-canary/run-dyg`
  - EBCAR：`.tmp/c2p-stage1-canary/run-ebcar`
- 原文对照（只作覆盖清单与 mismatch，**不授权实现事实**）：
  - LinearRAG / DyG / EBCAR 仓库内 `paperdraft.md`
- 协同记录：`.agent/implementation.md` 各轮 COMPLETE 段。本文件把六轮串成一份可汇报材料。

**阅读约定（与此前分析同一套方法）：**

1. `exit 0` 只表示 replay 写完 `/tmp`，不等于质量过关。
2. 对照 **Candidate** 与原文 Method，不拿 Verified 长短打 Writer。
3. Verified 短是 fail-closed：作者意图、语义许可、FAC 失败句不得进入。
4. 缺 H2 只在「Architect 计划了、Writer 起草了、harness 闸门丢掉」时算产品洞。
5. callback/rewrite `=0` 是金丝雀，不是 §1.6 写作期回搜已经完成。
6. FAC / 完整性门保持 fail-closed；不得靠删句、弱匹配或缩小义务过门。
7. 项目名、符号、已知答案不得进入 generic 生产逻辑。

---

## 0. 结论先行

六轮是同一条产品环上的 **诊断 → 修 generic 层 → 冻结重放** 循环，不是六次换架构。

```text
作者意图
  -> 冻结研究证据
  -> 论证包许可 + Architect 大纲
  -> Formalizer
  -> Writer
  -> callback/resume（本窗口关闭）
  -> Rewrite（本窗口关闭）
  -> Candidate + Verified + 质量报告
```

**已经推进的：**

- LinearRAG First-retrieval 从「仓库没有规格」空壳，变成有操作句的 H2。
- L2 检索黑话（`Child activation`）和 EBCAR 裸 `x+y` 从 Candidate 消失。
- STAGE leftover「Entity Activation」独立 H2 被折掉。
- DyG encoding 从「写出来又被 spam 丢掉」回到 Candidate。
- EBCAR leftover STAGE H2 从 8 收到 5；Architecture 覆盖原文的 augmentation + hybrid attention。
- 65 分钟 callback 长尾被 `callback=0` 关掉（约 8–12 分钟/篇）。

**仍然成立、对照原文仍失败的：**

- Candidate 多步机制仍是一段墙，不是原文那种分步 Method。
- LinearRAG prune 极性仍可能写反（低于阈值却写成 admit）。
- DyG Downstream 仍会被 `## heading**Body` 熔接标题丢掉。
- 公式经常没有 `$$`；L2 `normalize` / `topk` / `weighted_sum` 仍会贴到无关 SSM 段。
- Verified 仍是两三句或空；质量报告 `publication_ready=false`、`final_integrity` 不过。
- 写作期回搜代码（§1.6）在本窗口从未真正跑过。

**六轮进度一览（Candidate H2 数 / 相对原文的主洞）：**

| 轮 | 时间 | 产物 | LinearRAG H2 | DyG H2 | EBCAR H2 | 该轮相对原文的主结论 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 08-25 23:09 | `230920` | 5 | — | — | First-retrieval 有了，但 STAGE 证据仍绑错 H2（`bound_correct_h2=0`） |
| 2 | 08-26 01:17 | `011745` | 6 | — | — | 激活不再倒进 Motivation；多出一个 leftover `Entity Activation` H2 |
| 3 | 08-26 09:00 | `090052` | — | 8 | 7 | DyG 有 encoding 但重复 H2 + L2 黑话；EBCAR 有 Architecture，framework 空、`x+y` |
| 4 | 08-26 代码 + 21:17 活跑 | 四洞修复 + `211757` | 5 | 4 | 8 | L2/`x+y`/Linear leftover 好转；DyG encoding 被粘贴 spam 丢掉；EBCAR leftover 变多 |
| 5 | 08-26 对照原文 | 无新活跑 | — | — | — | 诊断：maxLength、整段 H3 粘贴、architecture 族不折并、空壳漏检 |
| 6 | 08-26 22:51 | `225116` | 5 | 4 | 5 | Encoding 回来；EBCAR 8→5；墙式段落、prune 极性、Downstream `**` 熔接仍在 |

---

## 1. 第 1 轮 — 合成合同 + LinearRAG `230920`（2026-08-25）

### 1.1 背景与要修的问题

前序冻结研究 `164605` 与意图优先 canary 暴露：First-retrieval 可以变成
「operational specification is not provided in the repository」空壳；PPR 会渗进
activation 节；callback 打开时出现约 65 分钟长尾；Formalizer 容易产出裸 `x*y`。

本轮把 Writer 规范 §1.3/§1.6 落到 **合成合同**：L0 仍严，L1 是执行到数学算子图，
L2 是 `f(L0, L1, intent)` 的技术语义，Writer 必须消费 L2，不得空壳。

### 1.2 修复（代码）

落点摘要（详见当时 `.agent/implementation.md`「Method synthesis contract」）：

- 漏斗夹具与打分：`tests/fixtures/method_synthesis_funnel/linearrag_method_propositions_v1.json`（43 命题，14 条 Stage-1）。
- Architect：STAGE 按 heading token 折并，Motivation denylist，Jaccard 地板 0.25；leftover STAGE 可单独成节。
- L2：`scientific_claim_ir.py` 编译 `technical_claims_v1.json`，无 LLM 摘要。
- WriterView：`technical_propositions` sidecar；空壳检测覆盖长 caveat；`ROUTING_CONFLICT` 可把未匹配 STAGE/L2 弹回空机制 H2，但禁止 sibling steal。
- Formalizer：单独 `x*y` 标 incidental；仅当 L1 链长度 ≥2 才走 LLM。
- Runtime：`callback=0` / revision budget `=0` 被遵守。

Focused pytest：合同套件 124 passed（另有 Writer/FAC 合同测试按「Rewrite 不再拥有 FAC」更新后通过）。

### 1.3 产物

| 项 | 值 |
| --- | --- |
| 时间 | 23:09:20→23:20:56 +08（约 12 min）exit 0 |
| 输出 | `/tmp/c2p-synth-linearrag-20260825-230920` |
| 日志 | `/tmp/c2p-synth-linearrag-20260825-230920.log` |
| Candidate | 7483 字符，5 个 H2：Motivation / Overview / Offline / First-retrieval / Second-retrieval |
| Writer | incomplete；`publication_ready=false`；`resumed=[]` |

### 1.4 分析与讨论

对照 Stage-1 14 条命题（手标，不是 §8）：

| 条 | 结果 |
| --- | --- |
| First-retrieval H2 存在 | 是 |
| 不再是「仓库没有规格」空壳 | 是 |
| 阈值极性 = 低于则排除 | 部分：没有「低于则保留」抄写，但 First-retrieval 仍省略 prune/continue，Motivation 仍在讲 loop |
| Stage-1 used | 8/14（空壳基线 0，旧 binding-only 4，oracle 11） |
| `bound_correct_h2` | **0/14**：冻结 harvest 把 STAGE-02 标在 Motivation/Overview/Offline |
| 65 min 长尾 | 无 |

**讨论：** Architect 在干净夹具上能把 STAGE 绑到 First-retrieval；冻结 harvest 把激活事实标成 MAINLINE/COMPONENT，所以「绑对 H2」在这条冻结研究上仍是 0。问题在 **表示/harvest**，不是「没检索」。callback=0 证明可以在 12 分钟内拿到可读大纲，但不能当作写作期回搜已经闭环。

---

## 2. 第 2 轮 — WP-A–E + LinearRAG `011745`（2026-08-26 凌晨）

### 2.1 背景与要修的问题

`230920` 证明：把 STAGE 放到正确 H2 是必要的，不够。Compact WriterView 曾丢掉 L2；schema 体积被怀疑截断正文；Motivation 仍在讲 activation loop。

本轮拆成 WP-A 绑定实验、WP-B schema 体积、WP-C/D/E 路由与许可。

### 2.2 修复与实验

**WP-A（绑定-only MA-S4）。** 复制 `230920` 到 `/tmp/c2p-binding-only-mas4-20260826`，把 STAGE-02 L0+L2 绑到 MA-S4。47 秒、4 次 LLM。Stage-1 used 5/14（旧 binding-only 4/14）。正确 H2 上仍缺 τ/乘积。结论：绑对 H2 ≠ 写全机制。

**WP-B（schema 体积 A–E）。** 抓 `230920` MA-S1 请求（prompt 2820 + payload 14460 + schema 4987 字符）在 8006 上变体。报告：`/tmp/c2p-schema-volume-20260826/schema_volume_report.json`。当前 schema（C）完整、不截断；生产上的「从而防止 / extracted in」**不能**用字段个数解释。未扩大 schema，未落地变体 E。

**WP-C/D/E。** heading family 先于 covers；STAGE 永不折进 Motivation；修辞 H2 去掉 required `mechanism_overview`；空 local H2 可从 Offline 收回 STAGE/L2，仍不能偷 PPR；L2 极性从 `continue` / `<` 定为低于则排除；WriterView compact 发送 `technical_propositions`；Candidate FAC 对 E2 父链可标 caveated。Verified 仍 E0/E1 fail-closed。Skill `publication-method-writer/1.11`。

Focused pytest：134 passed。

### 2.3 产物 `011745`

| 项 | 值 |
| --- | --- |
| 时间 | 01:17:45→01:25:32 +08（约 8 min）exit 0 |
| 输出 | `/tmp/c2p-synth-linearrag-20260826-011745` |
| Candidate | 8951 字符，**6** 个 H2（5 个组织锚 + leftover `Entity Activation via Local Semantic Bridging`） |

| 条（本轮观察，非 §8） | 结果 |
| --- | --- |
| 激活在 First-retrieval，不在 Motivation | 是（另有 leftover MA-S6） |
| 空壳 | 否；MA-S4/MA-S6 有操作句 |
| L2 极性低于则排除 | sidecar 7× “fails the threshold”；MA-S6 写 `entity_score < iteration_threshold` |
| Stage-1 关键实现 ≥3 | 是；总体 ≥2 为 10/14；oracle 仍 11/14 |
| `publication_ready` | false |

### 2.4 分析与讨论

激活终于离开 Motivation，这是相对 `164605`/`230920` 的主进步。新洞是 **leftover H2**：冻结 covers 仍把 STAGE-02 放在 MA-S6，Rebound 把 L2 写进 MA-S4，但大纲多出一节「Entity Activation」。MA-S4 仍可能用 author-intent brief 把 PPR 讲成 activation。`invalid_writing_research_callback` 在 rounds=0 时仍出现，但不再开研究长尾。

---

## 3. 第 3 轮 — DyG + EBCAR `090052`（2026-08-26 上午）

### 3.1 背景

WP-A–E 代码与 LinearRAG `011745` 同一 dirty tree。需要看同一套 generic 层在 DyG/EBCAR 冻结研究上是否通病。

### 3.2 产物

**DyG** `/tmp/c2p-synth-dyg-20260826-090052`
09:00:52→09:11:59（约 11 min）exit 0。Candidate **8** 个 H2：encoding 出现两次（长标题 MA-S1 与短标题 MA-S5），另有 Redesign / Downstream / Timespan-aware / Reviewing / Downstream prediction。Writer incomplete；`publication_ready=false`。

**EBCAR** `/tmp/c2p-synth-ebcar-20260826-090052`
09:11:59→09:23:54（约 12 min）exit 0。Candidate **7** 个 H2。Architecture 有 doc-id / sinusoid / hybrid attention。Framework 与部分 Inference 是空壳。MA-S6/S7 `headings_only` 被拒。出现 `hybrid_attention_` + `run_name` 被收成 `x+y`。

### 3.3 分析与讨论

| 条 | DyG | EBCAR |
| --- | --- | --- |
| Motivation 不是 Additional dump | 是（SSM 局限） | 是（效率 + cross-passage） |
| 机制是否在 Candidate 里 | encoding / Δt / A/B/C **有**，但拆在重复 H2 上 | Architecture **有**，STAGE leftover 并行 |
| L2 | `Child activation` / `Expansion excludes entities` 贴到 SSM | 空 sidecar，但 Formalizer `x+y` |
| 空 H2 | 非主问题 | Framework 空壳被当成一节 |
| 金丝雀时长 | ~11 min | ~12 min |

**讨论：** LinearRAG 上「绑节 + 空壳」的修在另外两篇上部分成立（Motivation 干净、有机制 H2），但暴露三类 **跨项目 generic 洞**：

1. L2 从 `elementwise_product` / `threshold_mask` 编出检索黑话，贴到无关 SSM。
2. Formalizer 把标识符拼接当成 `x+y`。
3. Architect leftover 与空 framework 壳：该折的不折，该拒的没收紧。

Gold alias 观察（非手标 Stage-1、非 §8）：DyG encoding 期望 H2 3/3；EBCAR stage-1 7/7 vs 旧 125126 的 4/7。不能用 alias 分数宣称论文覆盖。

---

## 4. 第 4 轮 — 四洞 generic 修复 + 三篇串行 `211757`（2026-08-26）

### 4.1 诊断（针对 `011745` / `090052`）

四条产品洞，全部按 **generic 层** 修，不写项目名进编译器：

1. L2 检索黑话（`mul` 误伤 `matmul`；`!= None` 当成 threshold）。
2. STAGE leftover 不按 heading/containment/词族折并，且会折进 Motivation。
3. WP-F 裸 `x OP y`；`attention` 误匹配 `hybrid_attention_`。
4. Writer seed 截断、句号熔接 heading、缺公式不贴、跨节 infer PPR。

### 4.2 修复（代码）

`code_state_digest sha256:a4e7f02efa30f133fbaffbe81b793ba7fb2e6d1c0f13d648005e32c04487e75c`

| 层 | 文件 | 行为 |
| --- | --- | --- |
| L2 | `scientific_claim_ir.py` | 词边界乘/加；threshold 仅 filter/compare/mask 或数值比较；算子中性模板；单独算术不发 L2 |
| Fold | `method_architect.py` | leftover 用 heading、containment≥0.51、`activat`/`aggregat` 词族；Motivation −1；org⊕STAGE Jaccard≥0.45 或 containment |
| WP-F | `equation_claims.py` / `formalization_agent.py` | 缺 `formula_role` 的裸 `x OP y` 仍 incidental；整词 descriptor；确定性包跳过 incidental |
| Writer | `publication_method_writer.py` / `section_writer.py` | seed cap 4000；`## Heading. Body` 在句号切开；空操作壳拒绝；`used_claim_ids` 不跨节；粘贴 Formalizer `markdown_block`；`\t`+`ext{` → `\text{` |

Focused pytest：**369 passed**（约 7.1s）。

实现中的方向内修补：空 claim 组织桩曾误丢 `equation_or_derivation`（`formalization_required`），改为先给 problem/design 再走原有 role 逻辑。错误加入的 dummy `_bucket_has_stage_obligation` 已删。

### 4.3 产物 `211757`（LinearRAG → DyG → EBCAR）

```text
log /tmp/c2p-serial-20260826-211757.log
BATCH_DONE 2026-08-26T21:49:58+08:00
```

| 项目 | 墙钟 | 输出 | Candidate |
| --- | --- | --- | --- |
| LinearRAG | 21:17:58→21:29:00 ~11 min exit 0 | `/tmp/c2p-synth-linearrag-20260826-211757` | 12199 字符，**5** H2；leftover Entity Activation **消失**；First-retrieval 下仍有重复 `### Entity Activation` |
| DyG | 21:29:01→21:39:39 ~11 min exit 0 | `/tmp/c2p-synth-dyg-20260826-211757` | 11293 字符，**4** H2；**没有 encoding**（计划有，Writer 草稿有四通道，粘贴第二份 H3 后 `repeated_token_spam`） |
| EBCAR | 21:39:39→21:49:57 ~10 min exit 0 | `/tmp/c2p-synth-ebcar-20260826-211757` | 9191 字符，**8** H2；Architecture 有机制；framework 改成 “No repository-supported method operations…”，**没命中** 当时的 deferral 标记；STAGE leftover 因 fused-heading「有正文」反而留下 |

三篇 `publication_ready=false`，`resumed=[]`。

### 4.4 分析与讨论

相对 `011745`/`090052`：

| 洞 | LinearRAG | DyG | EBCAR |
| --- | --- | --- | --- |
| L2 黑话 | sidecar 中性；正文仍有 “scores fall below”（Writer 极性） | **击中**：Redesign 不再以 Child activation 开头 | **击中**：无 `x+y` |
| leftover H2 | **击中** 5 H2；H3 重复仍在 | 计划一份 encoding，Candidate **丢掉** | **未击中计数**：8 H2 |
| 裸 `x+y` | 作者意图图，不是 x+y | SSM aligned 块，不是 x+y | **击中** |
| Writer seed/熔接/粘贴 | First-retrieval 有操作句 | 草稿有四通道，spam 闸门扔掉整节 | MA-S6/S7 有正文（090052 是 headings-only） |

**讨论：** 第 4 轮是「修对了一半、修出了新失败模式」的典型轮。粘贴 Formalizer 全文是为了补公式，结果在 DyG 上用重复 5-gram（latex `n mathbf W e mathbf` 出现 ≥6 次）把 **整节 encoding** 从 Candidate 删除——比 090052 更糟。EBCAR fused-heading 修复让曾经的纯标题 leftover 变成「有一段正文」而被收下，leftover **变多**。对照原文，用户会感觉「内容更少」：DyG 从 encoding 起笔的故事没了。

---

## 5. 第 5 轮 — 对照原文的「薄内容」诊断与修复（2026-08-26，无新活跑）

### 5.1 分析方法

不拿 Verified（设计上就短）当 Candidate 失败。把 `211757` Candidate 直接对照三篇 `paperdraft.md` Method。

| 原文 | 规模 | 211757 Candidate 为何显得「没写」 |
| --- | --- | --- |
| LinearRAG | 9169 字符，offline + seed 余弦 + 六步 activation + BFS/SpMM + hybrid PPR | 五个 H2 都在，但是 **一段墙**；First-retrieval 极性反，H3 重复；query-time 塞进 Offline |
| DyG | 8807 字符，四通道 encoding 开头 + Δt/A/B/C | **encoding 整节不在 Candidate**（草稿有、闸门丢） |
| EBCAR | 1486 字符，augmentation + hybrid attention | Architecture 有机制，但空 framework + 三个 STAGE leftover 把大纲撑散 |

### 5.2 根因（generic，非项目特化）

1. **`section_markdown` maxLength。** `max(paragraph_budget)`，地板 1400。Motivation/overview **1670**；First/Second retrieval **2560**。JSON schema 在多步 Method 写完前截住模型。
2. **`_paste_missing_formula_blocks` 粘贴完整 `markdown_block`（第二份 H3 + 散文）。** 与 Writer 已有公式叠加后触发 `repeated_token_spam`，**丢整节** 而不是回退到粘贴前正文。
3. **Fold 词族只有 local/global/offline。** Hybrid-attention / Structural augmentation 与 Architecture 对不上；「overall framework」不是修辞框，leftover 既折不进 Architecture，也不跳过空 framework。
4. **Deferral 标记漏了** “no repository-supported method operations”。
5. **Brief 压缩 200 字符**，许可措辞被截断。
6. **`\begin{` 的 `\b` → backspace** 未修（只修了 `\text{`）。

### 5.3 修复（代码）

`code_state_digest sha256:23e4ebf9eb54820dc3dd2679214d999a799ff1a1cc3a1d6809bc63aabfc308fb`

- 机制段 maxLength 地板 **4800**（上限 10000）；修辞段 2800。仍用最深 `paragraph_budget`，不把多 move 预算相加（避免再灌背景）。
- 粘贴 **只插 display math**；正文已有公式 token 则跳过；若仅粘贴导致 spam 则回退。
- Architecture 词族（encod/embed/attention/augment/hybrid/retriev…）可折进 Architecture；**永不**进 Motivation / overall framework / training；local/global/offline 仍不倾倒进 architecture。
- 空壳标记补上 live 用过的句子；licensed brief 压到 **800**；skill **1.12** 要求多步用空行分段；`\begin{` 与 `\text{` 一并修。

Focused pytest（unset 金丝雀 env 后）：**444 passed**。`python -m compileall -q src tests` 通过。

**讨论：** 第 4 轮的粘贴是「补公式」方向内修复，第 5 轮证明它与 spam 闸门组合是 **内容删除器**。maxLength 是另一条独立的「看起来没写完」原因：即便 H2 在，模型也只能挤一段。空壳漏检解释了 EBCAR framework 为何能以改写后的 no-ops 句混进 Candidate。

本轮 **没有** 再跑一遍未改代码的 211757。

---

## 6. 第 6 轮 — 三篇串行 `225116`（2026-08-26 夜）

### 6.1 产物

```text
log /tmp/c2p-serial-20260826-225116.log
BATCH 20260826-225116
BATCH_DONE 2026-08-26T23:23:45+08:00
pid 3879237
execution_record digest sha256:e89afdde7446c…（三篇 exit 0）
```

| 项目 | 墙钟 | 输出 | Writer | Candidate |
| --- | --- | --- | --- | --- |
| LinearRAG | 22:51:27→23:02:29 ~11 min | `/tmp/c2p-synth-linearrag-20260826-225116` | incomplete；MA-S1–S5 均 accepted | 9673 字符，5 H2；重复 H3 消失 |
| DyG | 23:02:29→23:14:33 ~12 min | `/tmp/c2p-synth-dyg-20260826-225116` | MA-S1 encoding **accepted**；MA-S4 Downstream `caveat_token_shell` | 8162 字符，4 H2，**以 encoding 开头** |
| EBCAR | 23:14:33→23:23:45 ~9 min | `/tmp/c2p-synth-ebcar-20260826-225116` | 5 节均 accepted | 8400 字符，**5** H2（8→5） |

三篇 `publication_ready=false`，`resumed=[]`。LinearRAG 质量报告示例：`plan_gate_passed=true`，`final_integrity_gate_passed=false`，`unsupported_positive_claims=40`，`support_precision=0.0`，`equation_coverage=0.0`，`information_density≈0.10`。这些数字描述的是 **反向验证 / utility 分类**，不能用来证明 Candidate 没有 H2。

### 6.2 对照原文与 211757

| 条 | LinearRAG | DyG | EBCAR |
| --- | --- | --- | --- |
| 机制节是否还在 | First-retrieval 2508 字符保留；重复 H3 没了 | **击中：** encoding 2720 字符、四通道 Concat | Architecture 4238 字符：doc-id / sinusoid / hybrid |
| leftover STAGE | 仍 5 H2（本就合理） | 计划 5、Candidate 4（Downstream 丢） | **击中：** Retrieval/Structural/Hybrid 折进 Architecture |
| 空 framework | n/a | n/a | 改为组织性散文，不再是 no-ops 那句 |
| L2 / `x+y` | 无 Child activation | 无 Child activation | 无 `x+y` |
| 墙式段落 | 残留：每 H2 仍 1 段 | 残留 | Architecture 变长；Training 2 段 |

Verified：LinearRAG 547 字符（两句，含反了的 prune）；DyG **空**；EBCAR 318 字符（Architecture）。这是 fail-closed，不是第 6 轮 Writer 没写。

### 6.3 残留问题与原因分类

| 现象 | 对照原文 | 原因类 |
| --- | --- | --- |
| LinearRAG First-retrieval 仍无 seed / 六步 / BFS vs SpMM | 原文有完整逐步算法 | Writer 样本：加长 maxLength 后仍写一段 |
| “admits … when score falls below” | 原文低于 τ **丢弃** | Writer/L2 极性；Verified 还收了错句 |
| LinearRAG Second 无 hybrid PPR 公式 | 原文有 `passage_ratio` + log bonus / tier | 公式覆盖 0；LaTeX 未进 `$$` |
| DyG encoding 一段 + 未包 `$$` 的 Concat | 原文三个小节 + 对齐到 \(4d_c\) | 洞「缺节」已闭；深度/版式仍开 |
| DyG 无 Downstream | 原文有 cross-attention / readout | `## heading**Downstream prediction.**` 一行；去 `#` 后正文空 → `caveat_token_shell`。句号熔接已修，`**` 未修 |
| EBCAR 仍 5 H2（原文 2） | 原文只有 augmentation + hybrid | 大纲仍含 Motivation/framework/training/inference；framework 无许可操作 |
| 每节 `invalid_writing_research_callback` | §1.6 应回搜 | **金丝雀 callback=0**，不是崩溃 |
| 质量报告 blocked | — | FAC/完整性 fail-closed；不得靠删 Candidate 过门 |

---

## 7. 跨六轮讨论

### 7.1 什么在稳定变好

1. **空壳 → 有操作句的 H2。** LinearRAG First-retrieval 从 164605 空壳走到 230920/011745/211757/225116 都有 First-retrieval。
2. **金丝雀可重复。** 同一冻结根、同一 8006、callback=0，单篇约 8–12 分钟，不再 65 分钟长尾。
3. **跨项目黑话/裸公式。** Child activation 与 EBCAR `x+y` 在 211757 之后的 Candidate 里不再作为主失败模式。
4. **大纲折并。** LinearRAG leftover Entity Activation（011745 的第 6 H2）在 211757 去掉；EBCAR leftover 在 225116 从 8 收到 5。
5. **「写出来又被闸门删掉」被对准。** DyG encoding 在 211757 是这类洞的反例；225116 用「只贴数学 / 已有则跳过 / spam 则回退」把它救回 Candidate。

### 7.2 什么是来回摆的

- **粘贴公式：** 不贴则缺公式；整段贴则 spam 删节。第 4 轮与第 5–6 轮是同一杠杆的两端。
- **leftover：** 折太弱则多 H2（011745、090052、211757 EBCAR）；fused-heading「有正文」会让本该死掉的标题活下来。
- **maxLength：** 曾经担心相加预算灌背景（所以用 max 而非 sum）；后来地板太低导致一段墙。第 5 轮抬地板，第 6 轮模型仍不换行。

### 7.3 不要混的三件事（汇报时建议原样保留）

1. **进程结束** ≠ 质量过关。六轮活跑全部 exit 0，全部 `publication_ready=false`。
2. **Candidate 有 H2** ≠ 原文 Method。还要看步骤、极性、公式、是否被闸门删节。
3. **Verified 短** ≠ Writer 没写。看 `publication_candidate_method.md`。

### 7.4 本窗口刻意没做的

- 打开 callback/rewrite 做 §1.6 写作期回搜。
- 重跑 30-turn 研究或换冻结根。
- 放宽 L0/FAC/完整性。
- 把 DyG/LinearRAG/EBCAR 字符串写进 generic 编译器。
- 宣称 D5、default cutover、release freeze。

---

## 8. 若继续做：方向内下一刀（不是本汇报的验收）

按同一套「对照原文 + generic 层」方法，**不要原样重跑 225116**：

1. 熔接标题：在已有 `## Heading. Body` 之外，拆 `## heading**Body`（DyG Downstream）。
2. 多步机制分段：不要指望 maxLength 单独换行；应用 facet/步骤约束或确定性分段提示，仍禁止灌背景。
3. Prune 极性：Writer/L2 模板与正文「低于阈值」必须同向（排除，不是 admit）。
4. L2 注入范围：`normalize` / `topk` / `weighted_sum` 不要贴到无关 encoding/SSM 节。
5. Display math：未包环境的公式做表示层修复，而不是再贴第二份 H3。
6. 仅当产品环需要证明 §1.6 时，再打开有界 callback——那是另一协议，不能和本窗口 `=0` 金丝雀混报。

---

## 9. 产物与日志索引（仅本窗口）

| 轮 | 路径 |
| --- | --- |
| 1 LinearRAG | `/tmp/c2p-synth-linearrag-20260825-230920` |
| 2 LinearRAG | `/tmp/c2p-synth-linearrag-20260826-011745` |
| 3 DyG / EBCAR | `/tmp/c2p-synth-dyg-20260826-090052`，`/tmp/c2p-synth-ebcar-20260826-090052` |
| 4 串行 | `/tmp/c2p-serial-20260826-211757.log`；`/tmp/c2p-synth-{linearrag,dyg,ebcar}-20260826-211757` |
| 5 代码 | dirty worktree；digest `sha256:23e4ebf9eb54820dc3dd2679214d999a799ff1a1cc3a1d6809bc63aabfc308fb` |
| 6 串行 | `/tmp/c2p-serial-20260826-225116.log`；`/tmp/c2p-synth-{linearrag,dyg,ebcar}-20260826-225116` |
| 冻结研究 | LinearRAG `/tmp/c2p-fresh-linearrag-20260825-164605`；DyG/EBCAR `.tmp/c2p-stage1-canary/run-{dyg,ebcar}` |
| 实现流水账 | `.agent/implementation.md`（本窗口各 COMPLETE 段） |

每篇 Candidate 相对路径：`artifacts/06_authoring/publication_candidate_method.md`
Verified：`artifacts/06_authoring/repository_verified_method.md`
Writer：`artifacts/06_authoring/publication_writer_result_v1.json`
质量报告：`artifacts/07_validation/publication_quality_report_v1.json`

---

## 10. 汇报可用的一句话

> 在冻结研究、callback=0、qwen38@8006 的同一协议下，六轮把 Method Candidate 从「空壳 / 黑话 / 裸 x+y / 整节被 spam 删除」推到「三篇都有正确机制 H2、DyG encoding 与 EBCAR Architecture 能对照原文」。它仍然不是原文 Method：多步写成一段墙、部分极性写反、Downstream 会因熔接标题被拒、Verified 与 `publication_ready` 按设计未过。exit 0 不能当验收。
