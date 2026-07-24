#!/usr/bin/env bash
set -u
set -o pipefail

RESULT_ROOT="/data1/users/cuihengjia/result/batch_run_part_06_$(date +%Y%m%d_%H%M%S)"
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

idx=79
while IFS=$'\t' read -r project intent; do
  run_one "$idx" "$project" "$intent"
  idx=$((idx + 1))
done <<'EOF'
/data1/users/cuihengjia/code2paper/code_raw/SenseNova-SI - Scaling Spatial Intelligence with Multimodal Foundation Models	/data1/users/cuihengjia/code2paper/paperyaml/SenseNova-SI - Scaling Spatial Intelligence with Multimodal Foundation Models.yaml
/data1/users/cuihengjia/code2paper/code_raw/SimScale - Learning to Simulate at Scale	/data1/users/cuihengjia/code2paper/paperyaml/SimScale - Learning to Simulate at Scale.yaml
/data1/users/cuihengjia/code2paper/code_raw/Spatial-SSRL - Enhancing Spatial Understanding via Self-Supervised Reinforcement Learning	/data1/users/cuihengjia/code2paper/paperyaml/Spatial-SSRL - Enhancing Spatial Understanding via Self-Supervised Reinforcement Learning.yaml
/data1/users/cuihengjia/code2paper/code_raw/StructXLIP - Enhancing Vision-language Models with Multimodal Structural Cues	/data1/users/cuihengjia/code2paper/paperyaml/StructXLIP - Enhancing Vision-language Models with Multimodal Structural Cues.yaml
/data1/users/cuihengjia/code2paper/code_raw/StyleExpert	/data1/users/cuihengjia/code2paper/paperyaml/StyleExpert.yaml
/data1/users/cuihengjia/code2paper/code_raw/SwitchCraft - Training-Free Multi-Event Video Generation with Attention Controls	/data1/users/cuihengjia/code2paper/paperyaml/SwitchCraft - Training-Free Multi-Event Video Generation with Attention Controls.yaml
/data1/users/cuihengjia/code2paper/code_raw/TAVP - Learning to See and Act — Task-Aware Virtual View Exploration for Robotic Manipulation	/data1/users/cuihengjia/code2paper/paperyaml/TAVP - Learning to See and Act — Task-Aware Virtual View Exploration for Robotic Manipulation.yaml
/data1/users/cuihengjia/code2paper/code_raw/U4D - Uncertainty-Aware 4D World Modeling from LiDAR Sequences	/data1/users/cuihengjia/code2paper/paperyaml/U4D - Uncertainty-Aware 4D World Modeling from LiDAR Sequences.yaml
/data1/users/cuihengjia/code2paper/code_raw/UCMNet - Uncertainty-Aware Context Memory Network for Under-Display Camera Image Restoration	/data1/users/cuihengjia/code2paper/paperyaml/UCMNet - Uncertainty-Aware Context Memory Network for Under-Display Camera Image Restoration.yaml
/data1/users/cuihengjia/code2paper/code_raw/UCPE - Camera-controlled Text-to-Video Generation	/data1/users/cuihengjia/code2paper/paperyaml/UCPE - Camera-controlled Text-to-Video Generation.yaml
/data1/users/cuihengjia/code2paper/code_raw/UPLiFT - Universal Pixel-dense Lightweight Feature Transforms _ Efficient Pixel-Dense Feature Upsampling with Local Attenders	/data1/users/cuihengjia/code2paper/paperyaml/UPLiFT - Universal Pixel-dense Lightweight Feature Transforms _ Efficient Pixel-Dense Feature Upsampling with Local Attenders.yaml
/data1/users/cuihengjia/code2paper/code_raw/USO - Unified Style and Subject-Driven Generation	/data1/users/cuihengjia/code2paper/paperyaml/USO - Unified Style and Subject-Driven Generation.yaml
/data1/users/cuihengjia/code2paper/code_raw/UltraFlux - Data-Model Co-Design for High-quality Native 4K Text-to-Image Generation across Diverse Aspect Ratios	/data1/users/cuihengjia/code2paper/paperyaml/UltraFlux - Data-Model Co-Design for High-quality Native 4K Text-to-Image Generation across Diverse Aspect Ratios.yaml
/data1/users/cuihengjia/code2paper/code_raw/UniComp - Rethinking Video Compression Through Informational Uniqueness	/data1/users/cuihengjia/code2paper/paperyaml/UniComp - Rethinking Video Compression Through Informational Uniqueness.yaml
/data1/users/cuihengjia/code2paper/code_raw/UniMMAD	/data1/users/cuihengjia/code2paper/paperyaml/UniMMAD.yaml
/data1/users/cuihengjia/code2paper/code_raw/UniTEX - Universal High Fidelity Generative Texturing for 3D Shapes	/data1/users/cuihengjia/code2paper/paperyaml/UniTEX - Universal High Fidelity Generative Texturing for 3D Shapes.yaml
/data1/users/cuihengjia/code2paper/code_raw/VANS - Video-as-Answer: Predict and Generate Next Visual States	/data1/users/cuihengjia/code2paper/paperyaml/VANS - Video-as-Answer - Predict and Generate Next Visual States.yaml
/data1/users/cuihengjia/code2paper/code_raw/VGGT-Det - Mining VGGT Internal Priors for Sensor-Geometry-Free Multi-View Indoor 3D Object Detection	/data1/users/cuihengjia/code2paper/paperyaml/VGGT-Det - Mining VGGT Internal Priors for Sensor-Geometry-Free Multi-View Indoor 3D Object Detection.yaml
/data1/users/cuihengjia/code2paper/code_raw/VIRST - Video-Instructed Reasoning Assistant for SpatioTemporal Segmentation	/data1/users/cuihengjia/code2paper/paperyaml/VIRST - Video-Instructed Reasoning Assistant for SpatioTemporal Segmentation.yaml
/data1/users/cuihengjia/code2paper/code_raw/ViT³ - Unlocking Test-Time Training in Vision	/data1/users/cuihengjia/code2paper/paperyaml/ViT³ - Unlocking Test-Time Training in Vision.yaml
/data1/users/cuihengjia/code2paper/code_raw/VideoCoF - Unified Video Editing with Temporal Reasoner	/data1/users/cuihengjia/code2paper/paperyaml/VideoCoF - Unified Video Editing with Temporal Reasoner.yaml
/data1/users/cuihengjia/code2paper/code_raw/Voxify3D - Pixel Art Meets Volumetric Rendering	/data1/users/cuihengjia/code2paper/paperyaml/Voxify3D - Pixel Art Meets Volumetric Rendering.yaml
/data1/users/cuihengjia/code2paper/code_raw/WaDi - Weight Direction-aware Distillation for One-step Image Synthesis	/data1/users/cuihengjia/code2paper/paperyaml/WaDi - Weight Direction-aware Distillation for One-step Image Synthesis.yaml
/data1/users/cuihengjia/code2paper/code_raw/Wan-Alpha - High-Quality Text-to-Video Generation with Alpha Channel	/data1/users/cuihengjia/code2paper/paperyaml/Wan-Alpha - High-Quality Text-to-Video Generation with Alpha Channel.yaml
/data1/users/cuihengjia/code2paper/code_raw/WeDetect - Fast Open-Vocabulary Object Detection as Retrieval	/data1/users/cuihengjia/code2paper/paperyaml/WeDetect - Fast Open-Vocabulary Object Detection as Retrieval.yaml
/data1/users/cuihengjia/code2paper/code_raw/When Safety Collides - Resolving Multi-Category Harmful Conflicts in Text-to-Image Diffusion via Adaptive Safety Guidance _ CASG	/data1/users/cuihengjia/code2paper/paperyaml/When Safety Collides - Resolving Multi-Category Harmful Conflicts in Text-to-Image Diffusion via Adaptive Safety Guidance _ CASG.yaml
/data1/users/cuihengjia/code2paper/code_raw/YOLO-Master - MOE-Accelerated with Specialized Transformers for Enhanced Real-time Detection	/data1/users/cuihengjia/code2paper/paperyaml/YOLO-Master - MOE-Accelerated with Specialized Transformers for Enhanced Real-time Detection.yaml
/data1/users/cuihengjia/code2paper/code_raw/tttLRM - Test-Time Training for Long Context and Autoregressive 3D Reconstruction	/data1/users/cuihengjia/code2paper/paperyaml/tttLRM - Test-Time Training for Long Context and Autoregressive 3D Reconstruction.yaml
EOF

echo
echo "batch_run_part_06 完成，汇总文件：$SUMMARY_FILE"
