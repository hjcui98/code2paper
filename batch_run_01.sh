#!/usr/bin/env bash
set -u
set -o pipefail

RESULT_ROOT="/data1/users/cuihengjia/result/batch_run_01_$(date +%Y%m%d_%H%M%S)"
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
/data1/users/cuihengjia/code2paper/code/3DThinker - Think with 3D: Geometric Imagination Grounded Spatial Reasoning from Limited Views	/data1/users/cuihengjia/code2paper/paperyaml/3DThinker - Think with 3D - Geometric Imagination Grounded Spatial Reasoning from Limited Views.yaml
/data1/users/cuihengjia/code2paper/code/ACoT-VLA - Action Chain-of-Thought for Vision-Language-Action Models	/data1/users/cuihengjia/code2paper/paperyaml/ACoT-VLA - Action Chain-of-Thought for Vision-Language-Action Models.yaml
/data1/users/cuihengjia/code2paper/code/AOT - Token Reduction via Local and Global Contexts Optimization for Efficient Video Large Language Models	/data1/users/cuihengjia/code2paper/paperyaml/AOT - Token Reduction via Local and Global Contexts Optimization for Efficient Video Large Language Models.yaml
/data1/users/cuihengjia/code2paper/code/APPO - Attention-guided Perception Policy Optimization for Video Reasoning	/data1/users/cuihengjia/code2paper/paperyaml/APPO - Attention-guided Perception Policy Optimization for Video Reasoning.yaml
/data1/users/cuihengjia/code2paper/code/AReS - Prime Once, then Reprogram Locally	/data1/users/cuihengjia/code2paper/paperyaml/AReS - Prime Once, then Reprogram Locally.yaml
/data1/users/cuihengjia/code2paper/code/ApET - Approximation-Error Guided Token Compression for Efficient VLMs	/data1/users/cuihengjia/code2paper/paperyaml/ApET - Approximation-Error Guided Token Compression for Efficient VLMs.yaml
/data1/users/cuihengjia/code2paper/code/BiCo - Composing Concepts from Images and Videos via Concept-prompt Binding	/data1/users/cuihengjia/code2paper/paperyaml/BiCo - Composing Concepts from Images and Videos via Concept-prompt Binding.yaml
/data1/users/cuihengjia/code2paper/code/BiGain - Unified Token-wise Guidance for Diffusion Models	/data1/users/cuihengjia/code2paper/paperyaml/BiGain - Unified Token-wise Guidance for Diffusion Models.yaml
/data1/users/cuihengjia/code2paper/code/Bootstrapping Multi-view Learning for Test-time Noisy Correspondence	/data1/users/cuihengjia/code2paper/paperyaml/Bootstrapping Multi-view Learning for Test-time Noisy Correspondence.yaml
/data1/users/cuihengjia/code2paper/code/C-MET - Cross-Modal Enhancement Transformer	/data1/users/cuihengjia/code2paper/paperyaml/C-MET - Cross-Modal Enhancement Transformer.yaml
/data1/users/cuihengjia/code2paper/code/C3G - Learning Compact 3D Representations with 2K Gaussians	/data1/users/cuihengjia/code2paper/paperyaml/C3G - Learning Compact 3D Representations with 2K Gaussians.yaml
/data1/users/cuihengjia/code2paper/code/CLIPoint3D - Language-Grounded Few-Shot Unsupervised 3D Point Cloud Domain Adaptation	/data1/users/cuihengjia/code2paper/paperyaml/CLIPoint3D - Language-Grounded Few-Shot Unsupervised 3D Point Cloud Domain Adaptation.yaml
/data1/users/cuihengjia/code2paper/code/Calibri - Enhancing Diffusion Transformers via Parameter-Efficient Calibration	/data1/users/cuihengjia/code2paper/paperyaml/Calibri - Enhancing Diffusion Transformers via Parameter-Efficient Calibration.yaml
/data1/users/cuihengjia/code2paper/code/Circuit Tracing in Vision-Language Models - Understanding the Internal Mechanisms of Multimodal Thinking	/data1/users/cuihengjia/code2paper/paperyaml/Circuit Tracing in Vision-Language Models - Understanding the Internal Mechanisms of Multimodal Thinking.yaml
/data1/users/cuihengjia/code2paper/code/Concept-Guided Fine-Tuning - Steering ViTs away from Spurious Correlations to Improve Robustness	/data1/users/cuihengjia/code2paper/paperyaml/Concept-Guided Fine-Tuning - Steering ViTs away from Spurious Correlations to Improve Robustness.yaml
/data1/users/cuihengjia/code2paper/code/DiT360 - High-Fidelity Panoramic Image Generation via Hybrid Training	/data1/users/cuihengjia/code2paper/paperyaml/DiT360 - High-Fidelity Panoramic Image Generation via Hybrid Training.yaml
/data1/users/cuihengjia/code2paper/code/Dynamic erf _ Derf	/data1/users/cuihengjia/code2paper/paperyaml/Dynamic erf _ Derf.yaml
/data1/users/cuihengjia/code2paper/code/E-RayZer - Self-supervised 3D Reconstruction as Spatial Visual Pre-training	/data1/users/cuihengjia/code2paper/paperyaml/E-RayZer - Self-supervised 3D Reconstruction as Spatial Visual Pre-training.yaml
/data1/users/cuihengjia/code2paper/code/EDGS - Efficient 3D Gaussian Splatting	/data1/users/cuihengjia/code2paper/paperyaml/EDGS - Efficient 3D Gaussian Splatting.yaml
/data1/users/cuihengjia/code2paper/code/EmoStyle - Emotion-Driven Image Stylization	/data1/users/cuihengjia/code2paper/paperyaml/EmoStyle - Emotion-Driven Image Stylization.yaml
/data1/users/cuihengjia/code2paper/code/F2DC - Domain-Skewed Federated Learning with Feature Decoupling and Calibration	/data1/users/cuihengjia/code2paper/paperyaml/F2DC - Domain-Skewed Federated Learning with Feature Decoupling and Calibration.yaml
/data1/users/cuihengjia/code2paper/code/FLAC - Few-Shot Acoustic Synthesis with Flow Matching	/data1/users/cuihengjia/code2paper/paperyaml/FLAC - Few-Shot Acoustic Synthesis with Flow Matching.yaml
/data1/users/cuihengjia/code2paper/code/FORCE - Transferable Visual Jailbreaking Attacks via Feature Over-Reliance CorrEction	/data1/users/cuihengjia/code2paper/paperyaml/FORCE - Transferable Visual Jailbreaking Attacks via Feature Over-Reliance CorrEction.yaml
/data1/users/cuihengjia/code2paper/code/FOZO - Forward-Only Zeroth-Order Prompt Optimization for Test-Time Adaptation	/data1/users/cuihengjia/code2paper/paperyaml/FOZO - Forward-Only Zeroth-Order Prompt Optimization for Test-Time Adaptation.yaml
EOF

echo
echo "batch_run_01 完成，汇总文件：$SUMMARY_FILE"
