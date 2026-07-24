#!/usr/bin/env bash
set -u
set -o pipefail

RESULT_ROOT="/data1/users/cuihengjia/result/batch_run_rerun32_partA_$(date +%Y%m%d_%H%M%S)"
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

idx=1
while IFS=$'\t' read -r project intent; do
  run_one "$idx" "$project" "$intent"
  idx=$((idx + 1))
done <<'EOF'
/data1/users/cuihengjia/code2paper/code_raw/CLIPoint3D - Language-Grounded Few-Shot Unsupervised 3D Point Cloud Domain Adaptation	/data1/users/cuihengjia/code2paper/paperyaml/CLIPoint3D - Language-Grounded Few-Shot Unsupervised 3D Point Cloud Domain Adaptation.yaml
/data1/users/cuihengjia/code2paper/code_raw/Calibri - Enhancing Diffusion Transformers via Parameter-Efficient Calibration	/data1/users/cuihengjia/code2paper/paperyaml/Calibri - Enhancing Diffusion Transformers via Parameter-Efficient Calibration.yaml
/data1/users/cuihengjia/code2paper/code_raw/Circuit Tracing in Vision-Language Models - Understanding the Internal Mechanisms of Multimodal Thinking	/data1/users/cuihengjia/code2paper/paperyaml/Circuit Tracing in Vision-Language Models - Understanding the Internal Mechanisms of Multimodal Thinking.yaml
/data1/users/cuihengjia/code2paper/code_raw/HetCache - Accelerating Diffusion-based Video Editing via Heterogeneous Caching	/data1/users/cuihengjia/code2paper/paperyaml/HetCache - Accelerating Diffusion-based Video Editing via Heterogeneous Caching.yaml
/data1/users/cuihengjia/code2paper/code_raw/MOS - Mitigating Optical-SAR Modality Gap for Cross-Modal Ship Re-Identification	/data1/users/cuihengjia/code2paper/paperyaml/MOS - Mitigating Optical-SAR Modality Gap for Cross-Modal Ship Re-Identification.yaml
/data1/users/cuihengjia/code2paper/code_raw/Mitigating Instance Entanglement in Instance-Dependent Partial Label Learning	/data1/users/cuihengjia/code2paper/paperyaml/Mitigating Instance Entanglement in Instance-Dependent Partial Label Learning.yaml
/data1/users/cuihengjia/code2paper/code_raw/MultiShotMaster - A Controllable Multi-Shot Video Generation Framework	/data1/users/cuihengjia/code2paper/paperyaml/MultiShotMaster - A Controllable Multi-Shot Video Generation Framework.yaml
/data1/users/cuihengjia/code2paper/code_raw/OrthoReg - Understanding and Enforcing Weight Disentanglement in Task Arithmetic	/data1/users/cuihengjia/code2paper/paperyaml/OrthoReg - Understanding and Enforcing Weight Disentanglement in Task Arithmetic.yaml
/data1/users/cuihengjia/code2paper/code_raw/PAM - A Pose–Appearance–Motion Engine for Sim-to-Real HOI Video Generation	/data1/users/cuihengjia/code2paper/paperyaml/PAM - A Pose–Appearance–Motion Engine for Sim-to-Real HOI Video Generation.yaml
/data1/users/cuihengjia/code2paper/code_raw/Particulate - Feed-Forward 3D Object Articulation	/data1/users/cuihengjia/code2paper/paperyaml/Particulate - Feed-Forward 3D Object Articulation.yaml
/data1/users/cuihengjia/code2paper/code_raw/PixARMesh - Autoregressive Mesh-Native Single-View Reconstruction _ Generation	/data1/users/cuihengjia/code2paper/paperyaml/PixARMesh - Autoregressive Mesh-Native Single-View Reconstruction _ Generation.yaml
/data1/users/cuihengjia/code2paper/code_raw/PointCNN++ _ Pointelligence	/data1/users/cuihengjia/code2paper/paperyaml/PointCNN++ _ Pointelligence.yaml
/data1/users/cuihengjia/code2paper/code_raw/PureCC - Pure Learning for Text-to-Image Concept Customization	/data1/users/cuihengjia/code2paper/paperyaml/PureCC - Pure Learning for Text-to-Image Concept Customization.yaml
/data1/users/cuihengjia/code2paper/code_raw/RAP - Fast Feedforward Rendering-Free Attribute-Guided Primitive Importance Score Prediction for Efficient 3D Gaussian Splatting Processing	/data1/users/cuihengjia/code2paper/paperyaml/RAP - Fast Feedforward Rendering-Free Attribute-Guided Primitive Importance Score Prediction for Efficient 3D Gaussian Splatting Processing.yaml
/data1/users/cuihengjia/code2paper/code_raw/ReDirector - Creating Any-Length Video Retakes with Rotary Camera Encoding	/data1/users/cuihengjia/code2paper/paperyaml/ReDirector - Creating Any-Length Video Retakes with Rotary Camera Encoding.yaml
/data1/users/cuihengjia/code2paper/code_raw/ReasonMap - Towards Fine-Grained Visual Reasoning Maps _ Transit Maps	/data1/users/cuihengjia/code2paper/paperyaml/ReasonMap - Towards Fine-Grained Visual Reasoning Maps _ Transit Maps.yaml
EOF

echo "batch_run_rerun32_partA 完成，汇总文件：$SUMMARY_FILE"
