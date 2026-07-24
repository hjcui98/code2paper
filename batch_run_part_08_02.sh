#!/usr/bin/env bash
set -u
set -o pipefail

RESULT_ROOT="/data1/users/cuihengjia/result/batch_run_part_08_02_$(date +%Y%m%d_%H%M%S)"
LOG_ROOT="${RESULT_ROOT}/logs"
SUMMARY_FILE="${RESULT_ROOT}/summary.tsv"
mkdir -p "$RESULT_ROOT" "$LOG_ROOT"

printf "index\tstatus\tpaper\tout_root\tlog_file\n" > "$SUMMARY_FILE"

slugify() {
  printf '%s' "$1" | sed 's/[[:space:]]\+/_/g; s#[/:]#_#g; s/[^[:alnum:]_.-]/_/g'
}

run_one() {
  local idx="$1"
  local project="$2"
  local intent="$3"

  local name slug out_root log_file
  name="$(basename "$project")"
  slug="$(slugify "$name")"
  out_root="${RESULT_ROOT}/$(printf '%02d' "$idx")_${slug}"
  log_file="${LOG_ROOT}/$(printf '%02d' "$idx")_${slug}.log"

  echo
  echo "==== [$idx] START: $name ===="
  echo "project: $project"
  echo "intent : $intent"
  echo "out    : $out_root"
  echo "log    : $log_file"

  if [ ! -d "$project" ]; then
    echo "[$idx] 项目目录不存在，跳过"
    printf "%s\tskipped(missing_project)\t%s\t%s\t%s\n" "$idx" "$name" "$out_root" "$log_file" >> "$SUMMARY_FILE"
    return 0
  fi
  if [ ! -f "$intent" ]; then
    echo "[$idx] intent 文件不存在，跳过"
    printf "%s\tskipped(missing_intent)\t%s\t%s\t%s\n" "$idx" "$name" "$out_root" "$log_file" >> "$SUMMARY_FILE"
    return 0
  fi

  python3 -u -m code2paper.cli.run \
    "$project" \
    --intent "$intent" \
    --skip-draft-bootstrap \
    --out-root "$out_root" \
    --llm-provider openai \
    --llm-model "deepseek-v4-pro" \
    --figure-backend paperbanana \
    --paperbanana-root "/home/cuihengjia/agent/Code2Paper/Code2Paper/paperbanana_single_shot" \
    --retrieval-setting auto \
    --figure-model "kimi-k2.5" \
    --figure-retrieval-model "kimi-k2.5" \
    --figure-chat-api-url "https://aihubmix.com/v1" \
    --figure-retrieval-ref-limit 15 \
    --figure-image-model "gpt-image-2" \
    --num-candidates 1 \
    --aspect-ratio 3:2 \
    --exp-mode demo_stylist_once \
    --allow-fidelity-fail \
    --verbose 2>&1 | tee "$log_file"

  local cmd_status=${PIPESTATUS[0]}

  if [ "$cmd_status" -eq 0 ]; then
    echo "[$idx] 论文《$name》完成了"
    printf "%s\tsuccess\t%s\t%s\t%s\n" "$idx" "$name" "$out_root" "$log_file" >> "$SUMMARY_FILE"
  else
    echo "[$idx] 论文《$name》失败了，已跳过，继续下一篇"
    printf "%s\tfailed(%s)\t%s\t%s\t%s\n" "$idx" "$cmd_status" "$name" "$out_root" "$log_file" >> "$SUMMARY_FILE"
  fi
}

idx=17
while IFS=$'\t' read -r project intent; do
  run_one "$idx" "$project" "$intent"
  idx=$((idx + 1))
done <<'EOF'
/data1/users/cuihengjia/code2paper/code_3/MedAgentGym - A Scalable Agentic Training Environment for Code-Centric Reasoning in Biomedical Data Science	/data1/users/cuihengjia/code2paper/paperyaml3/MedAgentGym - A Scalable Agentic Training Environment for Code-Centric Reasoning in Biomedical Data Science.yaml
/data1/users/cuihengjia/code2paper/code_3/MemGAS - From Single to Multi-Granularity: Toward Long-Term Memory Association and Selection of Conversational Agents	/data1/users/cuihengjia/code2paper/paperyaml3/MemGAS - From Single to Multi-Granularity: Toward Long-Term Memory Association and Selection of Conversational Agents.yaml
/data1/users/cuihengjia/code2paper/code_3/MetaEmbed - Scaling Multimodal Retrieval at Test-Time with Flexible Late Interaction	/data1/users/cuihengjia/code2paper/paperyaml3/MetaEmbed - Scaling Multimodal Retrieval at Test-Time with Flexible Late Interaction.yaml
/data1/users/cuihengjia/code2paper/code_3/MoECLIP - Patch-Specialized Experts for Zero-shot Anomaly Detection	/data1/users/cuihengjia/code2paper/paperyaml3/MoECLIP - Patch-Specialized Experts for Zero-shot Anomaly Detection.yaml
/data1/users/cuihengjia/code2paper/code_3/No Need For Real Anomaly - MLLM Empowered Zero-Shot Video Anomaly Detection	/data1/users/cuihengjia/code2paper/paperyaml3/No Need For Real Anomaly - MLLM Empowered Zero-Shot Video Anomaly Detection.yaml
/data1/users/cuihengjia/code2paper/code_3/PerfGuard - A Performance-Aware Agent for Visual Content Generation	/data1/users/cuihengjia/code2paper/paperyaml3/PerfGuard - A Performance-Aware Agent for Visual Content Generation.yaml
/data1/users/cuihengjia/code2paper/code_3/Q-RAG - Long Context Multi-step Retrieval via Value-based Embedder Training	/data1/users/cuihengjia/code2paper/paperyaml3/Q-RAG - Long Context Multi-step Retrieval via Value-based Embedder Training.yaml
/data1/users/cuihengjia/code2paper/code_3/ReVeal - Self-Evolving Code Agents via Reliable Self-Verification	/data1/users/cuihengjia/code2paper/paperyaml3/ReVeal - Self-Evolving Code Agents via Reliable Self-Verification.yaml
/data1/users/cuihengjia/code2paper/code_3/RoboAgent - Chaining Basic Capabilities for Embodied Task Planning	/data1/users/cuihengjia/code2paper/paperyaml3/RoboAgent - Chaining Basic Capabilities for Embodied Task Planning.yaml
/data1/users/cuihengjia/code2paper/code_3/Stop Wasting Your Tokens - Towards Efficient Runtime Multi-Agent Systems _ SupervisorAgent	/data1/users/cuihengjia/code2paper/paperyaml3/Stop Wasting Your Tokens - Towards Efficient Runtime Multi-Agent Systems _ SupervisorAgent.yaml
/data1/users/cuihengjia/code2paper/code_3/UI-AGILE - Advancing GUI Agents with Effective Reinforcement Learning and Precise Inference-Time Grounding	/data1/users/cuihengjia/code2paper/paperyaml3/UI-AGILE - Advancing GUI Agents with Effective Reinforcement Learning and Precise Inference-Time Grounding.yaml
/data1/users/cuihengjia/code2paper/code_3/VisualAD - Language-Free Zero-Shot Anomaly Detection via Vision Transformer	/data1/users/cuihengjia/code2paper/paperyaml3/VisualAD - Language-Free Zero-Shot Anomaly Detection via Vision Transformer.yaml
/data1/users/cuihengjia/code2paper/code_3/VoxTell - Free-Text Promptable Universal 3D Medical Image Segmentation	/data1/users/cuihengjia/code2paper/paperyaml3/VoxTell - Free-Text Promptable Universal 3D Medical Image Segmentation.yaml
/data1/users/cuihengjia/code2paper/code_3/Wanderland - Geometrically Grounded Simulation for Open-World Embodied AI	/data1/users/cuihengjia/code2paper/paperyaml3/Wanderland - Geometrically Grounded Simulation for Open-World Embodied AI.yaml
/data1/users/cuihengjia/code2paper/code_3/Widget2Code - From Visual Widgets to UI Code via Multimodal LLMs	/data1/users/cuihengjia/code2paper/paperyaml3/Widget2Code - From Visual Widgets to UI Code via Multimodal LLMs.yaml
/data1/users/cuihengjia/code2paper/code_3/Youtu-GraphRAG - Vertically Unified Agents for Graph Retrieval-Augmented Complex Reasoning	/data1/users/cuihengjia/code2paper/paperyaml3/Youtu-GraphRAG - Vertically Unified Agents for Graph Retrieval-Augmented Complex Reasoning.yaml
EOF

echo
echo "batch_run_part_08_02 完成，汇总文件：$SUMMARY_FILE"
