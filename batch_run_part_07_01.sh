#!/usr/bin/env bash
set -u
set -o pipefail

RESULT_ROOT="/data1/users/cuihengjia/result/batch_run_part_07_01_$(date +%Y%m%d_%H%M%S)"
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

idx=1
while IFS=$'\t' read -r project intent; do
  run_one "$idx" "$project" "$intent"
  idx=$((idx + 1))
done <<'EOF'
/data1/users/cuihengjia/code2paper/code_2/3D Aware Region Prompted Vision Language Model	/data1/users/cuihengjia/code2paper/paperyaml2/3D Aware Region Prompted Vision Language Model.yaml
/data1/users/cuihengjia/code2paper/code_2/A foundation model with multi-variate parallel attention to generate neuronal activity	/data1/users/cuihengjia/code2paper/paperyaml2/A foundation model with multi-variate parallel attention to generate neuronal activity.yaml
/data1/users/cuihengjia/code2paper/code_2/A$^2$Search - Ambiguity-Aware Question Answering with Reinforcement Learning	/data1/users/cuihengjia/code2paper/paperyaml2/A$^2$Search - Ambiguity-Aware Question Answering with Reinforcement Learning.yaml
/data1/users/cuihengjia/code2paper/code_2/Adapt Data to Model - Adaptive Transformation Optimization for Domain-shared Time Series Foundation Models	/data1/users/cuihengjia/code2paper/paperyaml2/Adapt Data to Model - Adaptive Transformation Optimization for Domain-shared Time Series Foundation Models.yaml
/data1/users/cuihengjia/code2paper/code_2/AgentGym-RL - An Open-Source Framework to Train LLM Agents for Long-Horizon Decision Making via Multi-Turn RL	/data1/users/cuihengjia/code2paper/paperyaml2/AgentGym-RL - An Open-Source Framework to Train LLM Agents for Long-Horizon Decision Making via Multi-Turn RL.yaml
/data1/users/cuihengjia/code2paper/code_2/AgentSynth - Scalable Task Generation for Generalist Computer-Use Agents	/data1/users/cuihengjia/code2paper/paperyaml2/AgentSynth - Scalable Task Generation for Generalist Computer-Use Agents.yaml
/data1/users/cuihengjia/code2paper/code_2/Agentic Reinforced Policy Optimization	/data1/users/cuihengjia/code2paper/paperyaml2/Agentic Reinforced Policy Optimization.yaml
/data1/users/cuihengjia/code2paper/code_2/Any-step Generation via N-th Order Recursive Consistent Velocity Field Estimation	/data1/users/cuihengjia/code2paper/paperyaml2/Any-step Generation via N-th Order Recursive Consistent Velocity Field Estimation.yaml
/data1/users/cuihengjia/code2paper/code_2/Attention as a Compass - Efficient Exploration for Process-Supervised RL in Reasoning Models	/data1/users/cuihengjia/code2paper/paperyaml2/Attention as a Compass - Efficient Exploration for Process-Supervised RL in Reasoning Models.yaml
/data1/users/cuihengjia/code2paper/code_2/Automated Stateful Specialization for Adaptive Agent Systems	/data1/users/cuihengjia/code2paper/paperyaml2/Automated Stateful Specialization for Adaptive Agent Systems.yaml
/data1/users/cuihengjia/code2paper/code_2/BFM-Zero - A Promptable Behavioral Foundation Model for Humanoid Control Using Unsupervised Reinforcement Learning	/data1/users/cuihengjia/code2paper/paperyaml2/BFM-Zero - A Promptable Behavioral Foundation Model for Humanoid Control Using Unsupervised Reinforcement Learning.yaml
/data1/users/cuihengjia/code2paper/code_2/BOAD - Discovering Hierarchical Software Engineering Agents via Bandit Optimization	/data1/users/cuihengjia/code2paper/paperyaml2/BOAD - Discovering Hierarchical Software Engineering Agents via Bandit Optimization.yaml
/data1/users/cuihengjia/code2paper/code_2/Be Careful When Fine-tuning On Open-Source LLMs - Your Fine-tuning Data Could Be Secretly Stolen!	/data1/users/cuihengjia/code2paper/paperyaml2/Be Careful When Fine-tuning On Open-Source LLMs - Your Fine-tuning Data Could Be Secretly Stolen!.yaml
/data1/users/cuihengjia/code2paper/code_2/Behavioral Embeddings of Programs - A Quasi-Dynamic Approach for Optimization Prediction	/data1/users/cuihengjia/code2paper/paperyaml2/Behavioral Embeddings of Programs - A Quasi-Dynamic Approach for Optimization Prediction.yaml
/data1/users/cuihengjia/code2paper/code_2/Best-of-Infinity - Asymptotic Performance of Test-Time LLM Ensembling	/data1/users/cuihengjia/code2paper/paperyaml2/Best-of-Infinity - Asymptotic Performance of Test-Time LLM Ensembling.yaml
/data1/users/cuihengjia/code2paper/code_2/Better Together - Leveraging Unpaired Multimodal Data for Stronger Unimodal Models	/data1/users/cuihengjia/code2paper/paperyaml2/Better Together - Leveraging Unpaired Multimodal Data for Stronger Unimodal Models.yaml
/data1/users/cuihengjia/code2paper/code_2/CARD - Towards Conditional Design of Multi-agent Topological Structures	/data1/users/cuihengjia/code2paper/paperyaml2/CARD - Towards Conditional Design of Multi-agent Topological Structures.yaml
/data1/users/cuihengjia/code2paper/code_2/CFT-RAG - An Entity Tree Based Retrieval Augmented Generation Algorithm With Cuckoo Filter	/data1/users/cuihengjia/code2paper/paperyaml2/CFT-RAG - An Entity Tree Based Retrieval Augmented Generation Algorithm With Cuckoo Filter.yaml
/data1/users/cuihengjia/code2paper/code_2/ChronoEdit - Towards Temporal Reasoning for In-Context Image Editing and World Simulation	/data1/users/cuihengjia/code2paper/paperyaml2/ChronoEdit - Towards Temporal Reasoning for In-Context Image Editing and World Simulation.yaml
/data1/users/cuihengjia/code2paper/code_2/CodeQuant - Unified Clustering and Quantization for Enhanced Outlier Smoothing in Low-Precision Mixture-of-Experts	/data1/users/cuihengjia/code2paper/paperyaml2/CodeQuant - Unified Clustering and Quantization for Enhanced Outlier Smoothing in Low-Precision Mixture-of-Experts.yaml
/data1/users/cuihengjia/code2paper/code_2/ComputerRL - Scaling End-to-End Online Reinforcement Learning for Computer Use Agents	/data1/users/cuihengjia/code2paper/paperyaml2/ComputerRL - Scaling End-to-End Online Reinforcement Learning for Computer Use Agents.yaml
/data1/users/cuihengjia/code2paper/code_2/Contact-guided Real2Sim from Monocular Video with Planar Scene Primitives	/data1/users/cuihengjia/code2paper/paperyaml2/Contact-guided Real2Sim from Monocular Video with Planar Scene Primitives.yaml
/data1/users/cuihengjia/code2paper/code_2/ContextIF - Enhancing Instruction-Following through Context Reward	/data1/users/cuihengjia/code2paper/paperyaml2/ContextIF - Enhancing Instruction-Following through Context Reward.yaml
EOF

echo
echo "batch_run_part_07_01 完成，汇总文件：$SUMMARY_FILE"
