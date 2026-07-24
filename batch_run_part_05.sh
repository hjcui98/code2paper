#!/usr/bin/env bash
set -u
set -o pipefail

RESULT_ROOT="/data1/users/cuihengjia/result/batch_run_part_05_$(date +%Y%m%d_%H%M%S)"
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

idx=50
while IFS=$'\t' read -r project intent; do
  run_one "$idx" "$project" "$intent"
  idx=$((idx + 1))
done <<'EOF'
/data1/users/cuihengjia/code2paper/code_raw/3DGen-R1 - Are We Ready for RL in Text-to-3D Generation?	/data1/users/cuihengjia/code2paper/paperyaml/3DGen-R1 - Are We Ready for RL in Text-to-3D Generation - .yaml
/data1/users/cuihengjia/code2paper/code_raw/MixerCSeg - An Efficient Mixer Architecture for Crack Segmentation	/data1/users/cuihengjia/code2paper/paperyaml/MixerCSeg - An Efficient Mixer Architecture for Crack Segmentation.yaml
/data1/users/cuihengjia/code2paper/code_raw/MoDES - Accelerating Mixture-of-Experts Multimodal Large Language Models via Dynamic Expert Skipping	/data1/users/cuihengjia/code2paper/paperyaml/MoDES - Accelerating Mixture-of-Experts Multimodal Large Language Models via Dynamic Expert Skipping.yaml
/data1/users/cuihengjia/code2paper/code_raw/MoVieS	/data1/users/cuihengjia/code2paper/paperyaml/MoVieS.yaml
/data1/users/cuihengjia/code2paper/code_raw/Mobile-VTON - High-Fidelity On-Device Virtual Try-On	/data1/users/cuihengjia/code2paper/paperyaml/Mobile-VTON - High-Fidelity On-Device Virtual Try-On.yaml
/data1/users/cuihengjia/code2paper/code_raw/MuViT - Multi-Resolution Vision Transformers for Learning Across Scales in Microscopy	/data1/users/cuihengjia/code2paper/paperyaml/MuViT - Multi-Resolution Vision Transformers for Learning Across Scales in Microscopy.yaml
/data1/users/cuihengjia/code2paper/code_raw/MultiShotMaster - A Controllable Multi-Shot Video Generation Framework	/data1/users/cuihengjia/code2paper/paperyaml/MultiShotMaster - A Controllable Multi-Shot Video Generation Framework.yaml
/data1/users/cuihengjia/code2paper/code_raw/Multinex - Lightweight Low-light Image Enhancement	/data1/users/cuihengjia/code2paper/paperyaml/Multinex - Lightweight Low-light Image Enhancement.yaml
/data1/users/cuihengjia/code2paper/code_raw/NeoVerse - Enhancing 4D World Model with In-the-Wild Monocular Videos	/data1/users/cuihengjia/code2paper/paperyaml/NeoVerse - Enhancing 4D World Model with In-the-Wild Monocular Videos.yaml
/data1/users/cuihengjia/code2paper/code_raw/OccAny - Generalized Unconstrained Urban 3D Occupancy	/data1/users/cuihengjia/code2paper/paperyaml/OccAny - Generalized Unconstrained Urban 3D Occupancy.yaml
/data1/users/cuihengjia/code2paper/code_raw/One-to-All Animation	/data1/users/cuihengjia/code2paper/paperyaml/One-to-All Animation.yaml
/data1/users/cuihengjia/code2paper/code_raw/Open-Vocabulary Domain Generalization in Urban-Scene Segmentation	/data1/users/cuihengjia/code2paper/paperyaml/Open-Vocabulary Domain Generalization in Urban-Scene Segmentation.yaml
/data1/users/cuihengjia/code2paper/code_raw/OrthoReg - Understanding and Enforcing Weight Disentanglement in Task Arithmetic	/data1/users/cuihengjia/code2paper/paperyaml/OrthoReg - Understanding and Enforcing Weight Disentanglement in Task Arithmetic.yaml
/data1/users/cuihengjia/code2paper/code_raw/PAM - A Pose–Appearance–Motion Engine for Sim-to-Real HOI Video Generation	/data1/users/cuihengjia/code2paper/paperyaml/PAM - A Pose–Appearance–Motion Engine for Sim-to-Real HOI Video Generation.yaml
/data1/users/cuihengjia/code2paper/code_raw/PF-RPN	/data1/users/cuihengjia/code2paper/paperyaml/PF-RPN.yaml
/data1/users/cuihengjia/code2paper/code_raw/PROMPTMINER - Black-Box Prompt Stealing against Text-to-Image Generative Models via Reinforcement Learning and Fuzz Optimization	/data1/users/cuihengjia/code2paper/paperyaml/PROMPTMINER - Black-Box Prompt Stealing against Text-to-Image Generative Models via Reinforcement Learning and Fuzz Optimization.yaml
/data1/users/cuihengjia/code2paper/code_raw/Particulate - Feed-Forward 3D Object Articulation	/data1/users/cuihengjia/code2paper/paperyaml/Particulate - Feed-Forward 3D Object Articulation.yaml
/data1/users/cuihengjia/code2paper/code_raw/PixARMesh - Autoregressive Mesh-Native Single-View Reconstruction _ Generation	/data1/users/cuihengjia/code2paper/paperyaml/PixARMesh - Autoregressive Mesh-Native Single-View Reconstruction _ Generation.yaml
/data1/users/cuihengjia/code2paper/code_raw/PointCNN++ _ Pointelligence	/data1/users/cuihengjia/code2paper/paperyaml/PointCNN++ _ Pointelligence.yaml
/data1/users/cuihengjia/code2paper/code_raw/ProM3E - Probabilistic Multi-Modal Masked Embedding Model	/data1/users/cuihengjia/code2paper/paperyaml/ProM3E - Probabilistic Multi-Modal Masked Embedding Model.yaml
/data1/users/cuihengjia/code2paper/code_raw/PureCC - Pure Learning for Text-to-Image Concept Customization	/data1/users/cuihengjia/code2paper/paperyaml/PureCC - Pure Learning for Text-to-Image Concept Customization.yaml
/data1/users/cuihengjia/code2paper/code_raw/RAP - Fast Feedforward Rendering-Free Attribute-Guided Primitive Importance Score Prediction for Efficient 3D Gaussian Splatting Processing	/data1/users/cuihengjia/code2paper/paperyaml/RAP - Fast Feedforward Rendering-Free Attribute-Guided Primitive Importance Score Prediction for Efficient 3D Gaussian Splatting Processing.yaml
/data1/users/cuihengjia/code2paper/code_raw/ReDirector - Creating Any-Length Video Retakes with Rotary Camera Encoding	/data1/users/cuihengjia/code2paper/paperyaml/ReDirector - Creating Any-Length Video Retakes with Rotary Camera Encoding.yaml
/data1/users/cuihengjia/code2paper/code_raw/ReasonMap - Towards Fine-Grained Visual Reasoning Maps _ Transit Maps	/data1/users/cuihengjia/code2paper/paperyaml/ReasonMap - Towards Fine-Grained Visual Reasoning Maps _ Transit Maps.yaml
/data1/users/cuihengjia/code2paper/code_raw/Retrieve and Segment - Are a Few Examples Enough to Bridge the Supervision Gap in Open-Vocabulary Segmentation?	/data1/users/cuihengjia/code2paper/paperyaml/Retrieve and Segment - Are a Few Examples Enough to Bridge the Supervision Gap in Open-Vocabulary Segmentation - .yaml
/data1/users/cuihengjia/code2paper/code_raw/Rewis3d - Reconstruction for Weakly-Supervised Semantic Segmentation	/data1/users/cuihengjia/code2paper/paperyaml/Rewis3d - Reconstruction for Weakly-Supervised Semantic Segmentation.yaml
/data1/users/cuihengjia/code2paper/code_raw/SEATrack - Simple, Efficient, and Adaptive Multimodal Tracker	/data1/users/cuihengjia/code2paper/paperyaml/SEATrack - Simple, Efficient, and Adaptive Multimodal Tracker.yaml
/data1/users/cuihengjia/code2paper/code_raw/SING - Analyzing Semantic Invariants in Classifiers	/data1/users/cuihengjia/code2paper/paperyaml/SING - Analyzing Semantic Invariants in Classifiers.yaml
/data1/users/cuihengjia/code2paper/code_raw/SelVA - Hear What Matters! Text-conditioned Selective Video-to-Audio Generation	/data1/users/cuihengjia/code2paper/paperyaml/SelVA - Hear What Matters! Text-conditioned Selective Video-to-Audio Generation.yaml
EOF

echo
echo "batch_run_part_05 完成，汇总文件：$SUMMARY_FILE"
