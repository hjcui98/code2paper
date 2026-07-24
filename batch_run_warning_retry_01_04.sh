#!/usr/bin/env bash
set -u
set -o pipefail

RESULT_ROOT="/data1/users/cuihengjia/result/batch_run_warning_retry_01_04_$(date +%Y%m%d_%H%M%S)"
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
/data1/users/cuihengjia/code2paper/code_raw/APPO - Attention-guided Perception Policy Optimization for Video Reasoning	/data1/users/cuihengjia/code2paper/paperyaml/APPO - Attention-guided Perception Policy Optimization for Video Reasoning.yaml
/data1/users/cuihengjia/code2paper/code_raw/AReS - Prime Once, then Reprogram Locally	/data1/users/cuihengjia/code2paper/paperyaml/AReS - Prime Once, then Reprogram Locally.yaml
/data1/users/cuihengjia/code2paper/code_raw/Bootstrapping Multi-view Learning for Test-time Noisy Correspondence	/data1/users/cuihengjia/code2paper/paperyaml/Bootstrapping Multi-view Learning for Test-time Noisy Correspondence.yaml
/data1/users/cuihengjia/code2paper/code_raw/C3G - Learning Compact 3D Representations with 2K Gaussians	/data1/users/cuihengjia/code2paper/paperyaml/C3G - Learning Compact 3D Representations with 2K Gaussians.yaml
/data1/users/cuihengjia/code2paper/code_raw/CLIPoint3D - Language-Grounded Few-Shot Unsupervised 3D Point Cloud Domain Adaptation	/data1/users/cuihengjia/code2paper/paperyaml/CLIPoint3D - Language-Grounded Few-Shot Unsupervised 3D Point Cloud Domain Adaptation.yaml
/data1/users/cuihengjia/code2paper/code_raw/Circuit Tracing in Vision-Language Models - Understanding the Internal Mechanisms of Multimodal Thinking	/data1/users/cuihengjia/code2paper/paperyaml/Circuit Tracing in Vision-Language Models - Understanding the Internal Mechanisms of Multimodal Thinking.yaml
/data1/users/cuihengjia/code2paper/code_raw/Concept-Guided Fine-Tuning - Steering ViTs away from Spurious Correlations to Improve Robustness	/data1/users/cuihengjia/code2paper/paperyaml/Concept-Guided Fine-Tuning - Steering ViTs away from Spurious Correlations to Improve Robustness.yaml
/data1/users/cuihengjia/code2paper/code_raw/DiT360 - High-Fidelity Panoramic Image Generation via Hybrid Training	/data1/users/cuihengjia/code2paper/paperyaml/DiT360 - High-Fidelity Panoramic Image Generation via Hybrid Training.yaml
/data1/users/cuihengjia/code2paper/code_raw/Dynamic erf _ Derf	/data1/users/cuihengjia/code2paper/paperyaml/Dynamic erf _ Derf.yaml
/data1/users/cuihengjia/code2paper/code_raw/E-RayZer - Self-supervised 3D Reconstruction as Spatial Visual Pre-training	/data1/users/cuihengjia/code2paper/paperyaml/E-RayZer - Self-supervised 3D Reconstruction as Spatial Visual Pre-training.yaml
/data1/users/cuihengjia/code2paper/code_raw/F2DC - Domain-Skewed Federated Learning with Feature Decoupling and Calibration	/data1/users/cuihengjia/code2paper/paperyaml/F2DC - Domain-Skewed Federated Learning with Feature Decoupling and Calibration.yaml
/data1/users/cuihengjia/code2paper/code_raw/FLAC - Few-Shot Acoustic Synthesis with Flow Matching	/data1/users/cuihengjia/code2paper/paperyaml/FLAC - Few-Shot Acoustic Synthesis with Flow Matching.yaml
/data1/users/cuihengjia/code2paper/code_raw/FORCE - Transferable Visual Jailbreaking Attacks via Feature Over-Reliance CorrEction	/data1/users/cuihengjia/code2paper/paperyaml/FORCE - Transferable Visual Jailbreaking Attacks via Feature Over-Reliance CorrEction.yaml
/data1/users/cuihengjia/code2paper/code_raw/FOZO - Forward-Only Zeroth-Order Prompt Optimization for Test-Time Adaptation	/data1/users/cuihengjia/code2paper/paperyaml/FOZO - Forward-Only Zeroth-Order Prompt Optimization for Test-Time Adaptation.yaml
/data1/users/cuihengjia/code2paper/code_raw/FPRL - Focus-to-Perceive Representation Learning for Endoscopic Video Analysis	/data1/users/cuihengjia/code2paper/paperyaml/FPRL - Focus-to-Perceive Representation Learning for Endoscopic Video Analysis.yaml
/data1/users/cuihengjia/code2paper/code_raw/FaithC	/data1/users/cuihengjia/code2paper/paperyaml/FaithC.yaml
/data1/users/cuihengjia/code2paper/code_raw/FastGS - Training 3D Gaussian Splatting in 100 Seconds	/data1/users/cuihengjia/code2paper/paperyaml/FastGS - Training 3D Gaussian Splatting in 100 Seconds.yaml
/data1/users/cuihengjia/code2paper/code_raw/Flow3r - Factored Flow Prediction for Scalable Visual Geometry Learning	/data1/users/cuihengjia/code2paper/paperyaml/Flow3r - Factored Flow Prediction for Scalable Visual Geometry Learning.yaml
/data1/users/cuihengjia/code2paper/code_raw/FlowMotion - Training-Free Flow Guidance for Video Motion Customization	/data1/users/cuihengjia/code2paper/paperyaml/FlowMotion - Training-Free Flow Guidance for Video Motion Customization.yaml
/data1/users/cuihengjia/code2paper/code_raw/G2VLM - Geometry Grounded Vision-Language Model	/data1/users/cuihengjia/code2paper/paperyaml/G2VLM - Geometry Grounded Vision-Language Model.yaml
/data1/users/cuihengjia/code2paper/code_raw/GThinker - Reasoning MLLM with Visual Cues and Visual Rethinking	/data1/users/cuihengjia/code2paper/paperyaml/GThinker - Reasoning MLLM with Visual Cues and Visual Rethinking.yaml
/data1/users/cuihengjia/code2paper/code_raw/Goal Force - Teaching Video Models To Accomplish Physics-Conditioned Goals	/data1/users/cuihengjia/code2paper/paperyaml/Goal Force - Teaching Video Models To Accomplish Physics-Conditioned Goals.yaml
/data1/users/cuihengjia/code2paper/code_raw/Group Editing	/data1/users/cuihengjia/code2paper/paperyaml/Group Editing.yaml
/data1/users/cuihengjia/code2paper/code_raw/InvAD - Inversion-based Reconstruction-Free Anomaly Detection with Diffusion Models	/data1/users/cuihengjia/code2paper/paperyaml/InvAD - Inversion-based Reconstruction-Free Anomaly Detection with Diffusion Models.yaml
/data1/users/cuihengjia/code2paper/code_raw/LMEE _ MemoryExplorer - Explore with Long-term Memory	/data1/users/cuihengjia/code2paper/paperyaml/LMEE _ MemoryExplorer - Explore with Long-term Memory.yaml
/data1/users/cuihengjia/code2paper/code_raw/MOS - Mitigating Optical-SAR Modality Gap for Cross-Modal Ship Re-Identification	/data1/users/cuihengjia/code2paper/paperyaml/MOS - Mitigating Optical-SAR Modality Gap for Cross-Modal Ship Re-Identification.yaml
/data1/users/cuihengjia/code2paper/code_raw/MVGGT - Multimodal Visual Geometry Grounded Transformer for Multiview 3D Referring Expression Segmentation	/data1/users/cuihengjia/code2paper/paperyaml/MVGGT - Multimodal Visual Geometry Grounded Transformer for Multiview 3D Referring Expression Segmentation.yaml
EOF

echo
echo "batch_run_warning_retry_01_04 完成，汇总文件：$SUMMARY_FILE"
