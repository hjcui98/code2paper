#!/usr/bin/env bash
set -u
set -o pipefail

RESULT_ROOT="/data1/users/cuihengjia/result/batch_run_warning_retry_strict_01_04_05_06_$(date +%Y%m%d_%H%M%S)"
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
/data1/users/cuihengjia/code2paper/code_raw/Concept-Guided Fine-Tuning - Steering ViTs away from Spurious Correlations to Improve Robustness	/data1/users/cuihengjia/code2paper/paperyaml/Concept-Guided Fine-Tuning - Steering ViTs away from Spurious Correlations to Improve Robustness.yaml
/data1/users/cuihengjia/code2paper/code_raw/FLAC - Few-Shot Acoustic Synthesis with Flow Matching	/data1/users/cuihengjia/code2paper/paperyaml/FLAC - Few-Shot Acoustic Synthesis with Flow Matching.yaml
/data1/users/cuihengjia/code2paper/code_raw/LMEE _ MemoryExplorer - Explore with Long-term Memory	/data1/users/cuihengjia/code2paper/paperyaml/LMEE _ MemoryExplorer - Explore with Long-term Memory.yaml
/data1/users/cuihengjia/code2paper/code_raw/MoDES - Accelerating Mixture-of-Experts Multimodal Large Language Models via Dynamic Expert Skipping	/data1/users/cuihengjia/code2paper/paperyaml/MoDES - Accelerating Mixture-of-Experts Multimodal Large Language Models via Dynamic Expert Skipping.yaml
/data1/users/cuihengjia/code2paper/code_raw/One-to-All Animation	/data1/users/cuihengjia/code2paper/paperyaml/One-to-All Animation.yaml
/data1/users/cuihengjia/code2paper/code_raw/RAP - Fast Feedforward Rendering-Free Attribute-Guided Primitive Importance Score Prediction for Efficient 3D Gaussian Splatting Processing	/data1/users/cuihengjia/code2paper/paperyaml/RAP - Fast Feedforward Rendering-Free Attribute-Guided Primitive Importance Score Prediction for Efficient 3D Gaussian Splatting Processing.yaml
/data1/users/cuihengjia/code2paper/code_raw/Rewis3d - Reconstruction for Weakly-Supervised Semantic Segmentation	/data1/users/cuihengjia/code2paper/paperyaml/Rewis3d - Reconstruction for Weakly-Supervised Semantic Segmentation.yaml
/data1/users/cuihengjia/code2paper/code_raw/SEATrack - Simple, Efficient, and Adaptive Multimodal Tracker	/data1/users/cuihengjia/code2paper/paperyaml/SEATrack - Simple, Efficient, and Adaptive Multimodal Tracker.yaml
/data1/users/cuihengjia/code2paper/code_raw/TAVP - Learning to See and Act — Task-Aware Virtual View Exploration for Robotic Manipulation	/data1/users/cuihengjia/code2paper/paperyaml/TAVP - Learning to See and Act — Task-Aware Virtual View Exploration for Robotic Manipulation.yaml
/data1/users/cuihengjia/code2paper/code_raw/VGGT-Det - Mining VGGT Internal Priors for Sensor-Geometry-Free Multi-View Indoor 3D Object Detection	/data1/users/cuihengjia/code2paper/paperyaml/VGGT-Det - Mining VGGT Internal Priors for Sensor-Geometry-Free Multi-View Indoor 3D Object Detection.yaml
/data1/users/cuihengjia/code2paper/code_raw/ViT³ - Unlocking Test-Time Training in Vision	/data1/users/cuihengjia/code2paper/paperyaml/ViT³ - Unlocking Test-Time Training in Vision.yaml
/data1/users/cuihengjia/code2paper/code_raw/tttLRM - Test-Time Training for Long Context and Autoregressive 3D Reconstruction	/data1/users/cuihengjia/code2paper/paperyaml/tttLRM - Test-Time Training for Long Context and Autoregressive 3D Reconstruction.yaml
EOF

echo
echo "batch_run_warning_retry_strict_01_04_05_06 完成，汇总文件：$SUMMARY_FILE"
