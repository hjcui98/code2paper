#!/usr/bin/env bash
set -u
set -o pipefail

RESULT_ROOT="/data1/users/cuihengjia/result/batch_run_part_07_03_$(date +%Y%m%d_%H%M%S)"
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

idx=46
while IFS=$'\t' read -r project intent; do
  run_one "$idx" "$project" "$intent"
  idx=$((idx + 1))
done <<'EOF'
/data1/users/cuihengjia/code2paper/code_2/HippoTune - A Hippocampal Associative Loop–Inspired Fine-Tuning Method for Continual Learning	/data1/users/cuihengjia/code2paper/paperyaml2/HippoTune - A Hippocampal Associative Loop–Inspired Fine-Tuning Method for Continual Learning.yaml
/data1/users/cuihengjia/code2paper/code_2/Hyper-SET - Designing Transformers via Hyperspherical Energy Minimization	/data1/users/cuihengjia/code2paper/paperyaml2/Hyper-SET - Designing Transformers via Hyperspherical Energy Minimization.yaml
/data1/users/cuihengjia/code2paper/code_2/In Context Semi-Supervised Learning	/data1/users/cuihengjia/code2paper/paperyaml2/In Context Semi-Supervised Learning.yaml
/data1/users/cuihengjia/code2paper/code_2/Interleaving Reasoning for Better Text-to-Image Generation	/data1/users/cuihengjia/code2paper/paperyaml2/Interleaving Reasoning for Better Text-to-Image Generation.yaml
/data1/users/cuihengjia/code2paper/code_2/LLM-JEPA - Large Language Models Meet Joint Embedding Predictive Architectures	/data1/users/cuihengjia/code2paper/paperyaml2/LLM-JEPA - Large Language Models Meet Joint Embedding Predictive Architectures.yaml
/data1/users/cuihengjia/code2paper/code_2/Latent Speech-Text Transformer	/data1/users/cuihengjia/code2paper/paperyaml2/Latent Speech-Text Transformer.yaml
/data1/users/cuihengjia/code2paper/code_2/LearNAT - Learning NL2SQL with AST-guided Task Decomposition for Large Language Models	/data1/users/cuihengjia/code2paper/paperyaml2/LearNAT - Learning NL2SQL with AST-guided Task Decomposition for Large Language Models.yaml
/data1/users/cuihengjia/code2paper/code_2/Learning to Reason without External Rewards	/data1/users/cuihengjia/code2paper/paperyaml2/Learning to Reason without External Rewards.yaml
/data1/users/cuihengjia/code2paper/code_2/Less Gaussians, Texture More - 4K Feed-Forward Textured Splatting	/data1/users/cuihengjia/code2paper/paperyaml2/Less Gaussians, Texture More - 4K Feed-Forward Textured Splatting.yaml
/data1/users/cuihengjia/code2paper/code_2/Locality-Attending Vision Transformer	/data1/users/cuihengjia/code2paper/paperyaml2/Locality-Attending Vision Transformer.yaml
/data1/users/cuihengjia/code2paper/code_2/Lyra - Generative 3D Scene Reconstruction via Video Diffusion Model Self-Distillation	/data1/users/cuihengjia/code2paper/paperyaml2/Lyra - Generative 3D Scene Reconstruction via Video Diffusion Model Self-Distillation.yaml
/data1/users/cuihengjia/code2paper/code_2/MEM1 - Learning to Synergize Memory and Reasoning for Efficient Long-Horizon Agents	/data1/users/cuihengjia/code2paper/paperyaml2/MEM1 - Learning to Synergize Memory and Reasoning for Efficient Long-Horizon Agents.yaml
/data1/users/cuihengjia/code2paper/code_2/Manipulation as in Simulation - Enabling Accurate Geometry Perception in Robots	/data1/users/cuihengjia/code2paper/paperyaml2/Manipulation as in Simulation - Enabling Accurate Geometry Perception in Robots.yaml
/data1/users/cuihengjia/code2paper/code_2/MergePRAG - Orthogonal Merging of Passage-experts for Multi-hop Parametric RAG	/data1/users/cuihengjia/code2paper/paperyaml2/MergePRAG - Orthogonal Merging of Passage-experts for Multi-hop Parametric RAG.yaml
/data1/users/cuihengjia/code2paper/code_2/OmniMouse - Scaling properties of multi-modal, multi-task Brain Models on 150B Neural Tokens	/data1/users/cuihengjia/code2paper/paperyaml2/OmniMouse - Scaling properties of multi-modal, multi-task Brain Models on 150B Neural Tokens.yaml
/data1/users/cuihengjia/code2paper/code_2/PAT3D - Physics-Augmented Text-to-3D Scene Generation	/data1/users/cuihengjia/code2paper/paperyaml2/PAT3D - Physics-Augmented Text-to-3D Scene Generation.yaml
/data1/users/cuihengjia/code2paper/code_2/Practical estimation of the optimal classification error with soft labels and calibration	/data1/users/cuihengjia/code2paper/paperyaml2/Practical estimation of the optimal classification error with soft labels and calibration.yaml
/data1/users/cuihengjia/code2paper/code_2/ProxyAttn - Guided Sparse Attention via Representative Heads	/data1/users/cuihengjia/code2paper/paperyaml2/ProxyAttn - Guided Sparse Attention via Representative Heads.yaml
/data1/users/cuihengjia/code2paper/code_2/Q-RAG - Long Context Multi‑Step Retrieval via Value‑Based Embedder Training	/data1/users/cuihengjia/code2paper/paperyaml2/Q-RAG - Long Context Multi‑Step Retrieval via Value‑Based Embedder Training.yaml
/data1/users/cuihengjia/code2paper/code_2/ReasoningBank - Scaling Agent Self-Evolving with Reasoning Memory	/data1/users/cuihengjia/code2paper/paperyaml2/ReasoningBank - Scaling Agent Self-Evolving with Reasoning Memory.yaml
/data1/users/cuihengjia/code2paper/code_2/Reference-guided Policy Optimization for Molecular Optimization via LLM Reasoning	/data1/users/cuihengjia/code2paper/paperyaml2/Reference-guided Policy Optimization for Molecular Optimization via LLM Reasoning.yaml
/data1/users/cuihengjia/code2paper/code_2/Reinforcement Learning Fine-Tuning Enhances Activation Intensity and Diversity in the Internal Circuitry of LLMs	/data1/users/cuihengjia/code2paper/paperyaml2/Reinforcement Learning Fine-Tuning Enhances Activation Intensity and Diversity in the Internal Circuitry of LLMs.yaml
EOF

echo
echo "batch_run_part_07_03 完成，汇总文件：$SUMMARY_FILE"
