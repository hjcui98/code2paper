# Code2Paper R8 推进报告（Gemma-4 适配版）

日期：2026-07-20  
当前基线：commit `8741536`  
适用模型：Gemma-4-31B-IT-NVFP4（物理 GPU 0/1，TP=2，max_model_len=131072）  
验收状态：代码回归通过，架构验收不通过；不建议启动正式 R8 实跑。  
关联文档：`docs/agentic_method_quality_next_execution_plan_2026-07-19.md`、`docs/agentic_robust_langgraph_research_writing_design_2026-07-19.md`

---

## 0. 本报告相对前序报告的变更

1. 引入按角色分级温度协议（writer ≠ 0），替代旧的单 `CODE2PAPER_LLM_TEMPERATURE=0`。
2. 将 24576 定义为整个 Method 的累计预算，而非单次生成上限；writer 单次默认 8192，仅在 `finish_reason=length` 时扩展到 12288。
3. 增加 `top_p` / `top_k` 采样参数支持（Gemma-4 推荐值）。
4. 新增 P0-0：按角色 LLM 配置与协议放宽（代码改造项，不只是改 env）。
5. 修正 R8 acceptance checker 协议（不再强制全局温度为 0，改为逐 role trace 核验；semantic verifier 为 0，deterministic authorizer/critic/gap gate 不调用 LLM）。
6. R8 summary/profile schema 扩展为按角色记录温度、top_p、top_k、max_output_tokens。

> 说明：Method 写作具有一定创造性（句法、叙述、figure 引用编排），强制 writer=0 会导致草稿机械化、与原始代码 evidence 风格不匹配；但 validator/authorizer 必须保持严格 0，以满足 executable-hard 事实授权协议。

---

## 1. Gemma-4 模型特性与配置基线

### 1.1 模型与硬件

| 项 | 值 |
|---|---|
| 模型路径 | `/data1/users/cuihengjia/models/Gemma-4-31B-IT-NVFP4` |
| 量化 | NVFP4（modelopt） |
| 物理卡 | 0、1 |
| Tensor parallel | 2 |
| max_model_len | 131072（128K） |
| max-num-seqs | 1（与项目内存约束一致） |
| served-model-name | `gemma4-31b-nvfp4` |

### 1.2 vLLM 启动命令（独立服务进程，固定 GPU 0/1）

```bash
CUDA_VISIBLE_DEVICES=0,1 \
  /data1/users/cuihengjia/models/Gemma-4-31B-IT-NVFP4/serve_2x5090_qwen36_env.sh
```

必须使用已验证脚本（或完整复制其中的 `--speculative-config`）；直接运行不带该参数的 `vllm serve` 会启动普通解码服务，MTP draft model/num_speculative_tokens 不会被加载，因此表现为“丢失 MTP”。

Code2Paper 编排进程只通过 `127.0.0.1:8000` 调用，不占 GPU。vLLM 日志中的 logical GPU 0/1 对应物理卡 0/1。

### 1.3 按角色 LLM 配置（Gemma-4 推荐值）

| 角色 | temperature | top_p | top_k | max_output_tokens | 用途 |
|---|---:|---:|---:|---:|---|
| intent_compiler | 0.20 | 默认 | 默认 | 4096 | 严格 JSON 的 typed target 提案 |
| code_intake | 0.20 | 0.90 | 40 | 2048 | 代码入口与检索计划 JSON |
| code_analyzer | 0.20 | 0.90 | 40 | 4096 | 代码结构分析 JSON |
| research_supervisor | 0.20 | 0.90 | 40 | 1536 | 结构化研究决策 |
| authoring_planner | 0.40 | 默认 | 默认 | 2048 | Method 规划 |
| method_writer | 0.70 | 0.95 | 50 | 8192；截断时 12288 | Method 分段写作 |
| local_rewrite | 0.35 | 默认 | 默认 | 3072 | 局部句子修复 |
| semantic_verifier | 0.00 | 默认 | 默认 | 1024 | 语义验证 |

理由：
- writer 0.70：保留叙述多样性，但 top_p=0.95 + top_k=50 抑制发散，保证与 evidence 对齐；
- supervisor 0.20：研究动作需要轻度探索（搜索策略/换工具），但批评/gap 必须严格；
- semantic verifier 为 0；authorizer/critic/gap finalizer 是 deterministic gate，不调用 LLM：所有事实授权与协议判断必须可复现；
- 24576 只作为整个 Method 跨 section/call 的累计上限；本机 capability report 已证明 12000-token 全局请求可能超时，strict-schema 还可能空白输出到上限，因此禁止把 24576 配成单次上限。

### 1.4 环境变量协议（Gemma-4 适配版）

新增按角色变量：

```
CODE2PAPER_LLM_TEMPERATURE_RESEARCH_SUPERVISOR=0.20
CODE2PAPER_LLM_TEMPERATURE_INTENT_COMPILER=0.20
CODE2PAPER_LLM_TEMPERATURE_CODE_INTAKE=0.20
CODE2PAPER_LLM_TEMPERATURE_CODE_ANALYZER=0.20
CODE2PAPER_LLM_TEMPERATURE_AUTHORING_PLANNER=0.40
CODE2PAPER_LLM_TEMPERATURE_METHOD_WRITER=0.70
CODE2PAPER_LLM_TEMPERATURE_LOCAL_REWRITE=0.35
CODE2PAPER_LLM_TEMPERATURE_SEMANTIC_VERIFIER=0.00

# 不设置全局 TOP_P/TOP_K；全局值会作为显式 base config 覆盖角色级值。
CODE2PAPER_LLM_TOP_P_METHOD_WRITER=0.95
CODE2PAPER_LLM_TOP_K_METHOD_WRITER=50
CODE2PAPER_LLM_TOP_P_RESEARCH_SUPERVISOR=0.90
CODE2PAPER_LLM_TOP_K_RESEARCH_SUPERVISOR=40

CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_INTENT_COMPILER=4096
CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_CODE_INTAKE=2048
CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_CODE_ANALYZER=4096
CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_RESEARCH_SUPERVISOR=1536
CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_AUTHORING_PLANNER=2048
CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_METHOD_WRITER=8192
CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_METHOD_WRITER_EXTENDED=12288
CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_LOCAL_REWRITE=3072
CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_SEMANTIC_VERIFIER=1024
```

保留：

```
CODE2PAPER_AGENTIC_RESEARCH_V3=1
CODE2PAPER_R8_ACCEPTANCE=1
CODE2PAPER_LLM_CACHE=0
CODE2PAPER_TP_SIZE=2
CODE2PAPER_NUM_GPUS=2
CODE2PAPER_PARALLEL_PROJECTS=1
CODE2PAPER_PAPER_READ_ONLY_AT_END=1
CODE2PAPER_LLM_PROVIDER=openai
CODE2PAPER_LLM_MODEL=gemma4-31b-nvfp4
CODE2PAPER_OPENAI_BASE_URL=http://127.0.0.1:8000/v1
```

废弃（保留兼容）：
- `CODE2PAPER_LLM_TEMPERATURE`：若仅设置此值且未设置任何角色级变量，则视为旧协议模式（所有角色 = 此值），R8 acceptance 仍按旧严格 0.0 校验。新协议必须使用按角色变量。

### 1.5 R8 summary/profile schema 扩展

R8 summary 应记录：

```json
{
  "physical_device_ids": [0, 1],
  "tensor_parallel_size": 2,
  "num_gpus": 2,
  "max_model_len": 131072,
  "quantization": "modelopt_nvfp4",
  "served_model_name": "gemma4-31b-nvfp4",
  "llm_cache": "0",
  "temperature_by_role": {
    "intent_compiler": 0.20,
    "research_supervisor": 0.20,
    "authoring_planner": 0.40,
    "method_writer": 0.70,
    "local_rewrite": 0.35,
    "semantic_verifier": 0.00
  },
  "top_p_by_role": {
    "intent_compiler": null,
    "research_supervisor": 0.90,
    "authoring_planner": null,
    "method_writer": 0.95,
    "local_rewrite": null,
    "semantic_verifier": null
  },
  "top_k_by_role": {
    "intent_compiler": null,
    "research_supervisor": 40,
    "authoring_planner": null,
    "method_writer": 50,
    "local_rewrite": null,
    "semantic_verifier": null
  },
  "max_output_tokens_by_role": {
    "intent_compiler": 4096,
    "research_supervisor": 1536,
    "authoring_planner": 2048,
    "method_writer": 8192,
    "method_writer_extended": 12288,
    "method_cumulative_budget": 24576,
    "local_rewrite": 3072,
    "semantic_verifier": 1024
  }
}
```

---

## 2. 当前基线状态（commit 8741536）

### 2.1 已完成并确认有效

- gap finalizer 能将 obligation 推进到 `explicit_gap` 终态。
- R8 checker 已严格处理：skipped criterion 不再计为通过；temperature、TP/GPU、source authority 缺失会失败；`paper_read_only_at_end` 缺失会失败。
- 已建立 9 节点 LangGraph 拓扑代码（`build_research_subgraph`）。
- 已注册 26 个研究工具及 schema/executor。
- 当 `compiled_evidence` 已经存在时，可以写出 packets/facts/claims 并注入 legacy authoring。
- 完整回归：1575 passed, 3 skipped, 12 subtests passed。
- `pip check` 无依赖冲突。

### 2.2 验收状态

代码回归通过；架构验收不通过；不建议启动正式 R8 实跑。

### 2.3 与上一轮报告一致的代码层缺口（已在基线确认）

- [v3_runtime.py:268-285](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/agentic/v3_runtime.py#L268-285) `run_v3_research_phase()` 仍直接调用 `run_research_loop`，未走 LangGraph。
- [research_tools.py:1072](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/agentic/research_tools.py#L1072) `query_behavior_graph` 仅返回 `query:` 占位 ref。
- [research_tools.py:1336](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/agentic/research_tools.py#L1336) `compare_implementation_branches` 未比较 reachability/guard/output。
- [research_tools.py:1652](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/agentic/research_tools.py#L1652) `validate_evidence_packet` 仅做 `validated:` 前缀。
- [research_tools.py:1683](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/agentic/research_tools.py#L1683) `compile_code_facts` 未调用真实 compiler。
- [r8_acceptance.py:128](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/agentic/r8_acceptance.py#L128) `R8ProtocolSettings.temperature` 单值且强制 0.0。
- [client.py:163](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/llm/client.py#L163) `LLMClientConfig` 不支持 `top_p`/`top_k`。

---

## 3. 下一轮必须修改（P0）

### P0-0：实现按角色 LLM 配置与协议放宽（Gemma-4 适配）

**问题**：

- [client.py:163](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/llm/client.py#L163) 使用单一 `config.temperature`，无 `top_p`/`top_k`。
- [runner.py:813](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/agentic/runner.py#L813) `_collect_run_temperature()` 只读单一 `CODE2PAPER_LLM_TEMPERATURE`。
- [r8_acceptance.py:128](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/agentic/r8_acceptance.py#L128) `R8ProtocolSettings.temperature` 默认 0.0，强制单温度协议。
- [gemma_supervisor_backend.py:141](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/agentic/gemma_supervisor_backend.py#L141) 默认 `temperature=0.0`，未与 writer 分离。
- 各 provider 请求 payload（[client.py:163/208/237](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/llm/client.py#L163-237)）未传 `top_p`/`top_k`。

**修改要求**：

1. 在 `src/code2paper/llm/client.py` 扩展 `LLMClientConfig`：
   - 新增 `top_p: float = 1.0`、`top_k: int = -1`（-1 表示关闭）。
   - 各 provider payload 中加入这两个字段（OpenAI 兼容、Anthropic、Gemma Google API 均支持）。
2. 在 `src/code2paper/agentic/runner.py` 实现 `build_role_llm_clients()`：
   - 按 1.4 节环境变量构造 6 个独立 LLM client：supervisor / writer / validator / authorizer / critic / repair。
   - 替换当前单一 `llm_client` 注入路径。
3. 修改 `src/code2paper/agentic/r8_acceptance.py`：
   - `R8ProtocolSettings` 增加字段：`temperature_by_role: dict[str, float]`、`top_p_default`、`top_k_default`、`max_output_tokens_by_role`。
   - 默认期望值（与 1.3 节一致）：supervisor=0.20、writer=0.70、validator=0.00、authorizer=0.00、critic=0.00、gap_finalizer=0.00、repair=0.20。
   - 协议检查改为：
     - validator/authorizer/critic/gap_finalizer 必须 `== 0.0`；
     - writer ∈ [0.6, 0.8]；
     - supervisor ∈ [0.1, 0.3]；
     - repair ∈ [0.1, 0.3]；
     - 任何角色未记录 → 失败（不允许 skipped）。
   - run summary 必须记录 `temperature_by_role` 字典，否则 `temperature_not_recorded_by_role`。
4. 修改 `GemmaSupervisorBackend` 接受 `supervisor_temperature` 参数（默认 0.20，从环境变量读）。
5. 修改 `LocalRepairAgent` / writer agent 接受独立温度配置。
6. `build_agentic_run_summary()` 写入 `temperature_by_role`、`top_p_by_role`、`top_k_by_role`、`max_output_tokens_by_role`。

**退出测试**：

- R8 acceptance 用例：
  - writer=0.7, validator=0, authorizer=0 → 通过；
  - validator=0.1 → 失败（`validator_temperature_must_be_zero`）；
  - writer=0.0 → 失败（`writer_temperature_too_low_for_creative_method_writing`）；
  - writer=0.9 → 失败（`writer_temperature_too_high`）；
  - supervisor=0.5 → 失败；
  - 缺少 `temperature_by_role` 字段 → 失败。
- 单元测试覆盖 `LLMClientConfig.top_p` / `top_k` 字段，OpenAI / Anthropic / Gemma 三种 provider payload 包含这两个字段。
- 集成测试：run summary 写入完整按角色温度记录，并被 R8 checker 接受。

---

### P0-1：生产入口切换到真实 LangGraph

**问题**：

- [v3_runtime.py:268-285](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/agentic/v3_runtime.py#L268-285) `run_v3_research_phase()` 仍调用直接 Python driver，9 节点图未进入生产运行。

**修改要求**：

- 生产入口调用 `build_research_subgraph(runtime, checkpointer=...)`。
- 使用稳定的 V3 `thread_id` 和 checkpoint config。
- `V3GraphWrapper.get_state()` 不能只代理 legacy graph。
- V3 失败必须写入 summary/acceptance report，不能静默降级后仍允许验收。
- `run_research_loop()` 仅保留为单元测试便利入口。

**退出测试**：

- monkeypatch `run_research_loop` 使其抛错，生产 V3 运行仍应成功，证明生产入口没有调用 direct driver。
- 检查执行 trace 确实经过 supervisor、tool、observation、critic、compiler/gap 节点。

---

### P0-2：修通 observation → behavior graph → compiler

**问题**：

工具输出协议互不匹配：
- `search_symbols` 返回 `symbol:<path>:<symbol>:<line>`；
- `read_symbol` 只返回 span；
- `build_behavior_subgraph` 返回 `behavior:`；
- updater 只接受特定工具的 `symbol:` ref；
- agenda 的 `candidates` 和 `missing_information` 不随观测更新。

**修改要求**：

- 定义统一、可解析的 typed symbol/behavior reference（建议 schema：`symbol:<repo_snapshot_id>:<path>:<symbol>:<line>` 与 `behavior:<repo_snapshot_id>:<node_id>:<predicate>:<operand>`）。
- `observation_ingest_node` 根据有效搜索结果更新：
  - `candidate_symbol_ids`
  - `candidate_behavior_node_ids`
  - 已解决的 `missing_information`
- `behavior_graph_updater_node` 直接消费：
  - `read_symbol` 的 symbol identity；
  - `build_behavior_subgraph` 的结构化行为节点；
  - 必要时消费搜索后确认的 symbol。
- evidence critic 根据当前 behavior graph 和未解决缺口决定是否编译，不能依赖永远不清空的初始列表。

**退出测试**：

使用 `toy_train_project` 从作者 YAML 启动生产 V3 入口，必须满足：
- `behavior_graph.nodes > 0`
- `compiled_evidence` 非空
- 至少一个 obligation 为 `supported`
- packets、facts、claims 均非空
- 这些 artifacts 被 authoring projection 实际消费

---

### P0-3：实现可跨实例恢复的 checkpoint

**问题**：

- [research_graph.py:557](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/agentic/research_graph.py#L557) `_ResearchGraphContext` 保存关键运行对象，但不进入 checkpoint。重新构建图恢复时会在 supervisor 节点触发 `loop_state is None`。

**修改要求**：

- checkpoint state 保存恢复所需的序列化内容或 artifact refs：
  - behavior graph digest/path
  - gain history / no-progress counters
  - compiled evidence refs
  - active obligation
  - current/best quality state
  - turn accounting
- 节点不得依赖只能由首次 `linear_prefix` 初始化的 closure 状态。
- resume 时从 checkpoint/artifact refs 重建运行上下文。

**退出测试**：

- SQLite 图运行中断；
- 销毁 graph/runtime 实例；
- 重新创建实例并恢复；
- 不重复已完成工具调用；
- resumed final digest 与 uninterrupted control 相同。

---

## 4. 工具层整改

当前“26 个工具”只能视为 registry 覆盖，不能视为全部实现完成。优先修复：

- [research_tools.py:1072](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/agentic/research_tools.py#L1072) `query_behavior_graph`：查询真实行为图。
- [research_tools.py:1336](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/agentic/research_tools.py#L1336) `compare_implementation_branches`：比较 reachability、guard/config 和输出结构。
- [research_tools.py:1652](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/agentic/research_tools.py#L1652) `validate_evidence_packet`：加载真实 proposal 并验证 span、relation、authority、minimality。
- [research_tools.py:1683](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/agentic/research_tools.py#L1683) `compile_code_facts`：调用真实 generic compiler，返回持久化 fact artifact。
- `validate_code_facts` / `authorize_atomic_claims`：不得仅把输入 ID 改成 `validated`/`authorized` 前缀。
- [research_tools.py:1826](file:///home/cuihengjia/agent/Code2Paper%20copy/src/code2paper/agentic/research_tools.py#L1826) `check_obligation_coverage`：根据 claims/gaps 真实重算覆盖状态。
- 生产 runtime 的 `ready_tools` 应从经过实现级验证的 registry 生成，而不是固定为当前 5 个工具。

---

## 5. R8 验收推进顺序

建议严格按以下顺序推进（P0-0 为新增 Gemma-4 适配步骤，必须先做）：

1. **P0-0**：按角色温度协议与 LLM 配置改造（基础，影响后续所有运行）。
2. **P0-1**：修复生产 LangGraph 入口。
3. **P0-2**：修复 observation 和 behavior graph 协议。
4. **P0-3**：建立非 mock evidence 编译集成测试。
5. **P0-4**：修复跨实例 checkpoint/resume。
6. **工具层**：清理工具占位实现并开放生产工具集。
7. **toy/fixture 端到端验证**。
8. **串行执行** RAP、EBCAR、DyG-Mamba、LinearRAG。
9. **最后执行** Lookahead 和新的 holdout。
10. 每个项目执行 checkpoint/resume 对照运行。

正式 R8 环境保持：见第 6 节。

---

## 6. 正式 R8 环境（Gemma-4 适配版）

### 6.1 模型服务（GPU 0/1 独立进程）

```bash
CUDA_VISIBLE_DEVICES=0,1 \
  /data1/users/cuihengjia/models/Gemma-4-31B-IT-NVFP4/serve_2x5090_qwen36_env.sh
```

### 6.2 Code2Paper 编排进程环境变量

```bash
# V3 与验收开关
export CODE2PAPER_AGENTIC_RESEARCH_V3=1
export CODE2PAPER_R8_ACCEPTANCE=1
export CODE2PAPER_PAPER_READ_ONLY_AT_END=1

# 模型与硬件
export CODE2PAPER_LLM_PROVIDER=openai
export CODE2PAPER_LLM_MODEL=gemma4-31b-nvfp4
export CODE2PAPER_OPENAI_BASE_URL=http://127.0.0.1:8000/v1
export CODE2PAPER_TP_SIZE=2
export CODE2PAPER_NUM_GPUS=2
export CODE2PAPER_PARALLEL_PROJECTS=1
export CODE2PAPER_LLM_CACHE=0

# 全局值只用于兼容旧入口；R8 不以它判定采样质量，实际请求必须由下列角色值覆盖。
export CODE2PAPER_LLM_TEMPERATURE=0
export CODE2PAPER_LLM_MAX_OUTPUT_TOKENS=12000

# 按角色温度（Gemma-4 适配）
export CODE2PAPER_LLM_TEMPERATURE_RESEARCH_SUPERVISOR=0.20
export CODE2PAPER_LLM_TEMPERATURE_INTENT_COMPILER=0.20
export CODE2PAPER_LLM_TEMPERATURE_CODE_INTAKE=0.20
export CODE2PAPER_LLM_TEMPERATURE_CODE_ANALYZER=0.20
export CODE2PAPER_LLM_TEMPERATURE_AUTHORING_PLANNER=0.40
export CODE2PAPER_LLM_TEMPERATURE_METHOD_WRITER=0.70
export CODE2PAPER_LLM_TEMPERATURE_LOCAL_REWRITE=0.35
export CODE2PAPER_LLM_TEMPERATURE_SEMANTIC_VERIFIER=0.00

# 采样参数（Gemma-4 推荐默认值）
export CODE2PAPER_LLM_TOP_P_METHOD_WRITER=0.95
export CODE2PAPER_LLM_TOP_K_METHOD_WRITER=50
export CODE2PAPER_LLM_TOP_P_RESEARCH_SUPERVISOR=0.90
export CODE2PAPER_LLM_TOP_K_RESEARCH_SUPERVISOR=40

# 节点级短输出预算；Method 累计预算 24576 在代码内单独控制
export CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_INTENT_COMPILER=4096
export CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_CODE_INTAKE=2048
export CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_CODE_ANALYZER=4096
export CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_RESEARCH_SUPERVISOR=1536
export CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_AUTHORING_PLANNER=2048
export CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_METHOD_WRITER=8192
export CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_METHOD_WRITER_EXTENDED=12288
export CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_LOCAL_REWRITE=3072
export CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_SEMANTIC_VERIFIER=1024
```

注意：
- `CUDA_VISIBLE_DEVICES=0,1` 应设置在 Gemma/vLLM 服务进程上。
- Code2Paper 编排进程只通过 `127.0.0.1:8000` 调用，一般不需要占用 GPU。
- 设置可见设备后，vLLM 日志里的 logical GPU 0/1 对应物理卡 0/1。
- 正式六项目验收继续严格串行，避免两个 Code2Paper 任务同时请求这一个 TP=2 实例。

---

## 7. 下一轮提交完成定义

下一轮不能仅以测试总数或注册工具数作为完成依据，必须同时提供：

1. 生产入口节点执行 trace；
2. 非 mock packets/facts/claims；
3. writer 消费 V3 claims 的证据；
4. SQLite 跨实例恢复结果；
5. uninterrupted/resumed digest 对照；
6. 全量 pytest 结果；
7. 至少一个真实 Gemma 项目的 `accepted=true` 报告；
8. run summary 中完整记录 `temperature_by_role` / `top_p_by_role` / `top_k_by_role` / `max_output_tokens_by_role` 并通过 R8 protocol check（按角色协议）。

在 P0-0/P0-1/P0-2/P0-3 四个 P0 修复前，不建议消耗 GPU 进行六项目正式 R8。

---

## 8. 备注

- 用户已确认 Gemma 4 服务固定运行在物理 GPU 0、1。
- `CODE2PAPER_LLM_TEMPERATURE=0` 与 `CODE2PAPER_LLM_MAX_OUTPUT_TOKENS=12000` 是兼容哨兵，不是实际节点策略；R8 以每次调用的 role trace 核验温度、top-p、top-k 和输出上限。
- writer 0.70 / supervisor 与 intent 0.20 / planner 0.40 / local rewrite 0.35 / semantic verifier 0.00 是 Gemma-4-31B-IT 在 128K 上下文下，平衡“事实授权严格性”与“Method 写作创造性”的当前协议；deterministic gate 不调用 LLM。
- 若实际 R8 实跑中发现 writer 0.70 仍然发散（claim 与 evidence 对齐失败率 > 10%），下调至 0.60；若 supervisor 0.20 导致搜索策略单一（< 3 个不同工具被调用），上调至 0.30。调整需在 run summary 中记录并说明。

---

## 9. 2026-07-21 接管后的实施与验收增量

- 输出预算已收口为节点级 ceiling：intent full proposal 4096；每个被拒绝义务至多一次 1024 repair；supervisor 1536；planner 2048；writer 8192（仅 `finish_reason=length` 可到 12288）；local rewrite 3072；semantic verifier 1024；Method 累计 24576。128K 是输入上下文容量，绝不等价于 24576 单次安全输出。
- Intent Agent 对空 target、遗漏 deterministic predicate/relation 的响应原子拒绝；一次短 repair 仍无效时，精确恢复原 deterministic target，并把 `fallback_obligation_ids` 与理由写入 `intent_target_proposal_report_v1.json`。这满足设计要求的 deterministic fallback，且不把模型失败伪装成模型 enrichment。
- 旧 authoring wrapper 的 4096 stage clamp 已移除；role policy 现在能在生产 writer 实际生效。R8 不再把全局 temperature=0 当硬门槛，而是逐 trace 检查 role 温度、top-p/top-k 和不超过角色输出 ceiling。
- 当前代码回归：`1930 passed, 3 skipped, 12 subtests passed`（2026-07-21）。Bootstrapping 的完整修复版正式 holdout `bootstrapping-live-r13` 正在 GPU 0/1 的 TP=2/MTP 服务上运行；最终结果应以该运行的 summary、intent report 和 R8 recheck 为准。
