#!/usr/bin/env bash
set -u
set -o pipefail

RESULT_ROOT="/data1/users/cuihengjia/result/batch_run_rerun32_partB_$(date +%Y%m%d_%H%M%S)"
LOG_ROOT="${RESULT_ROOT}/logs"
SUMMARY_FILE="${RESULT_ROOT}/summary.tsv"
mkdir -p "$RESULT_ROOT" "$LOG_ROOT"

printf "index	status	paper	out_root	log_file
" > "$SUMMARY_FILE"

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
  out_root="${RESULT_ROOT}/$(printf "%02d" "$idx")_${slug}"
  log_file="${LOG_ROOT}/$(printf "%02d" "$idx")_${slug}.log"

  echo
  echo "==== [$idx] START: $name ===="
  echo "project: $project"
  echo "intent : $intent"
  echo "out    : $out_root"
  echo "log    : $log_file"

  if [ ! -d "$project" ]; then
    echo "[$idx] 项目目录不存在，跳过"
    printf "%s	skipped(missing_project)	%s	%s	%s
" "$idx" "$name" "$out_root" "$log_file" >> "$SUMMARY_FILE"
    return 0
  fi
  if [ ! -f "$intent" ]; then
    echo "[$idx] intent 文件不存在，跳过"
    printf "%s	skipped(missing_intent)	%s	%s	%s
" "$idx" "$name" "$out_root" "$log_file" >> "$SUMMARY_FILE"
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
    printf "%s	success	%s	%s	%s
" "$idx" "$name" "$out_root" "$log_file" >> "$SUMMARY_FILE"
  else
    echo "[$idx] 论文《$name》失败了，已跳过，继续下一篇"
    printf "%s	failed(%s)	%s	%s	%s
" "$idx" "$cmd_status" "$name" "$out_root" "$log_file" >> "$SUMMARY_FILE"
  fi
}

idx=17
while IFS=$'\t' read -r project intent; do
  run_one "$idx" "$project" "$intent"
  idx=$((idx + 1))
done <<'EOF'
/data1/users/cuihengjia/code2paper/code_raw/SING - Analyzing Semantic Invariants in Classifiers	/data1/users/cuihengjia/code2paper/paperyaml/SING - Analyzing Semantic Invariants in Classifiers.yaml
/data1/users/cuihengjia/code2paper/code_raw/SelVA - Hear What Matters! Text-conditioned Selective Video-to-Audio Generation	/data1/users/cuihengjia/code2paper/paperyaml/SelVA - Hear What Matters! Text-conditioned Selective Video-to-Audio Generation.yaml
/data1/users/cuihengjia/code2paper/code_raw/SenseNova-SI - Scaling Spatial Intelligence with Multimodal Foundation Models	/data1/users/cuihengjia/code2paper/paperyaml/SenseNova-SI - Scaling Spatial Intelligence with Multimodal Foundation Models.yaml
/data1/users/cuihengjia/code2paper/code_raw/StructXLIP - Enhancing Vision-language Models with Multimodal Structural Cues	/data1/users/cuihengjia/code2paper/paperyaml/StructXLIP - Enhancing Vision-language Models with Multimodal Structural Cues.yaml
/data1/users/cuihengjia/code2paper/code_raw/U4D - Uncertainty-Aware 4D World Modeling from LiDAR Sequences	/data1/users/cuihengjia/code2paper/paperyaml/U4D - Uncertainty-Aware 4D World Modeling from LiDAR Sequences.yaml
/data1/users/cuihengjia/code2paper/code_raw/UCPE - Camera-controlled Text-to-Video Generation	/data1/users/cuihengjia/code2paper/paperyaml/UCPE - Camera-controlled Text-to-Video Generation.yaml
/data1/users/cuihengjia/code2paper/code_raw/USO - Unified Style and Subject-Driven Generation	/data1/users/cuihengjia/code2paper/paperyaml/USO - Unified Style and Subject-Driven Generation.yaml
/data1/users/cuihengjia/code2paper/code_raw/UltraFlux - Data-Model Co-Design for High-quality Native 4K Text-to-Image Generation across Diverse Aspect Ratios	/data1/users/cuihengjia/code2paper/paperyaml/UltraFlux - Data-Model Co-Design for High-quality Native 4K Text-to-Image Generation across Diverse Aspect Ratios.yaml
/data1/users/cuihengjia/code2paper/code_raw/UniMMAD	/data1/users/cuihengjia/code2paper/paperyaml/UniMMAD.yaml
/data1/users/cuihengjia/code2paper/code_raw/UniTEX - Universal High Fidelity Generative Texturing for 3D Shapes	/data1/users/cuihengjia/code2paper/paperyaml/UniTEX - Universal High Fidelity Generative Texturing for 3D Shapes.yaml
/data1/users/cuihengjia/code2paper/code_raw/VGGT-Det - Mining VGGT Internal Priors for Sensor-Geometry-Free Multi-View Indoor 3D Object Detection	/data1/users/cuihengjia/code2paper/paperyaml/VGGT-Det - Mining VGGT Internal Priors for Sensor-Geometry-Free Multi-View Indoor 3D Object Detection.yaml
/data1/users/cuihengjia/code2paper/code_raw/VIRST - Video-Instructed Reasoning Assistant for SpatioTemporal Segmentation	/data1/users/cuihengjia/code2paper/paperyaml/VIRST - Video-Instructed Reasoning Assistant for SpatioTemporal Segmentation.yaml
/data1/users/cuihengjia/code2paper/code_raw/WaDi - Weight Direction-aware Distillation for One-step Image Synthesis	/data1/users/cuihengjia/code2paper/paperyaml/WaDi - Weight Direction-aware Distillation for One-step Image Synthesis.yaml
/data1/users/cuihengjia/code2paper/code_raw/When Safety Collides - Resolving Multi-Category Harmful Conflicts in Text-to-Image Diffusion via Adaptive Safety Guidance _ CASG	/data1/users/cuihengjia/code2paper/paperyaml/When Safety Collides - Resolving Multi-Category Harmful Conflicts in Text-to-Image Diffusion via Adaptive Safety Guidance _ CASG.yaml
/data1/users/cuihengjia/code2paper/code_raw/YOLO-Master - MOE-Accelerated with Specialized Transformers for Enhanced Real-time Detection	/data1/users/cuihengjia/code2paper/paperyaml/YOLO-Master - MOE-Accelerated with Specialized Transformers for Enhanced Real-time Detection.yaml
/data1/users/cuihengjia/code2paper/code_raw/tttLRM - Test-Time Training for Long Context and Autoregressive 3D Reconstruction	/data1/users/cuihengjia/code2paper/paperyaml/tttLRM - Test-Time Training for Long Context and Autoregressive 3D Reconstruction.yaml
EOF

echo "batch_run_rerun32_partB 完成，汇总文件：$SUMMARY_FILE"
