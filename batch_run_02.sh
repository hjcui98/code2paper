#!/usr/bin/env bash
set -u
set -o pipefail


RESULT_ROOT="/data1/users/cuihengjia/result/batch_run_02_$(date +%Y%m%d_%H%M%S)"
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

idx=26
while IFS=$'\t' read -r project intent; do
  run_one "$idx" "$project" "$intent"
  idx=$((idx + 1))
done <<'EOF'
/data1/users/cuihengjia/code2paper/code/FPRL - Focus-to-Perceive Representation Learning for Endoscopic Video Analysis	/data1/users/cuihengjia/code2paper/paperyaml/FPRL - Focus-to-Perceive Representation Learning for Endoscopic Video Analysis.yaml
/data1/users/cuihengjia/code2paper/code/FaithC	/data1/users/cuihengjia/code2paper/paperyaml/FaithC.yaml
/data1/users/cuihengjia/code2paper/code/FastGS - Training 3D Gaussian Splatting in 100 Seconds	/data1/users/cuihengjia/code2paper/paperyaml/FastGS - Training 3D Gaussian Splatting in 100 Seconds.yaml
/data1/users/cuihengjia/code2paper/code/Flow3r - Factored Flow Prediction for Scalable Visual Geometry Learning	/data1/users/cuihengjia/code2paper/paperyaml/Flow3r - Factored Flow Prediction for Scalable Visual Geometry Learning.yaml
/data1/users/cuihengjia/code2paper/code/FlowMotion - Training-Free Flow Guidance for Video Motion Customization	/data1/users/cuihengjia/code2paper/paperyaml/FlowMotion - Training-Free Flow Guidance for Video Motion Customization.yaml
/data1/users/cuihengjia/code2paper/code/From Static to Dynamic - Exploring Self-supervised Image-to-Video Representation Transfer Learning _ Co-Settle	/data1/users/cuihengjia/code2paper/paperyaml/From Static to Dynamic - Exploring Self-supervised Image-to-Video Representation Transfer Learning _ Co-Settle.yaml
/data1/users/cuihengjia/code2paper/code/G2VLM - Geometry Grounded Vision-Language Model	/data1/users/cuihengjia/code2paper/paperyaml/G2VLM - Geometry Grounded Vision-Language Model.yaml
/data1/users/cuihengjia/code2paper/code/GGPT - Geometry-grounded Point Transformer	/data1/users/cuihengjia/code2paper/paperyaml/GGPT - Geometry-grounded Point Transformer.yaml
/data1/users/cuihengjia/code2paper/code/GThinker - Reasoning MLLM with Visual Cues and Visual Rethinking	/data1/users/cuihengjia/code2paper/paperyaml/GThinker - Reasoning MLLM with Visual Cues and Visual Rethinking.yaml
/data1/users/cuihengjia/code2paper/code/Goal Force - Teaching Video Models To Accomplish Physics-Conditioned Goals	/data1/users/cuihengjia/code2paper/paperyaml/Goal Force - Teaching Video Models To Accomplish Physics-Conditioned Goals.yaml
/data1/users/cuihengjia/code2paper/code/Group Editing	/data1/users/cuihengjia/code2paper/paperyaml/Group Editing.yaml
/data1/users/cuihengjia/code2paper/code/HetCache - Accelerating Diffusion-based Video Editing via Heterogeneous Caching	/data1/users/cuihengjia/code2paper/paperyaml/HetCache - Accelerating Diffusion-based Video Editing via Heterogeneous Caching.yaml
/data1/users/cuihengjia/code2paper/code/INSID3 - Training-Free In-Context Segmentation with DINOv3	/data1/users/cuihengjia/code2paper/paperyaml/INSID3 - Training-Free In-Context Segmentation with DINOv3.yaml
/data1/users/cuihengjia/code2paper/code/InfiniDepth	/data1/users/cuihengjia/code2paper/paperyaml/InfiniDepth.yaml
/data1/users/cuihengjia/code2paper/code/InvAD - Inversion-based Reconstruction-Free Anomaly Detection with Diffusion Models	/data1/users/cuihengjia/code2paper/paperyaml/InvAD - Inversion-based Reconstruction-Free Anomaly Detection with Diffusion Models.yaml
/data1/users/cuihengjia/code2paper/code/IsoCLIP - Decomposing CLIP Projectors for Efficient Intra-modal Alignment	/data1/users/cuihengjia/code2paper/paperyaml/IsoCLIP - Decomposing CLIP Projectors for Efficient Intra-modal Alignment.yaml
/data1/users/cuihengjia/code2paper/code/LMEE _ MemoryExplorer - Explore with Long-term Memory	/data1/users/cuihengjia/code2paper/paperyaml/LMEE _ MemoryExplorer - Explore with Long-term Memory.yaml
/data1/users/cuihengjia/code2paper/code/LaS-Comp - Zero-shot 3D Completion with Latent-Spatial Consistency	/data1/users/cuihengjia/code2paper/paperyaml/LaS-Comp - Zero-shot 3D Completion with Latent-Spatial Consistency.yaml
/data1/users/cuihengjia/code2paper/code/LitePT - Lighter Yet Stronger Point Transformer	/data1/users/cuihengjia/code2paper/paperyaml/LitePT - Lighter Yet Stronger Point Transformer.yaml
/data1/users/cuihengjia/code2paper/code/LucidFlux - Caption-Free Photo-Realistic Image Restoration	/data1/users/cuihengjia/code2paper/paperyaml/LucidFlux - Caption-Free Photo-Realistic Image Restoration.yaml
/data1/users/cuihengjia/code2paper/code/MEDIC-AD - Towards Medical Vision-Language Model’s Clinical Intelligence	/data1/users/cuihengjia/code2paper/paperyaml/MEDIC-AD - Towards Medical Vision-Language Model’s Clinical Intelligence.yaml
/data1/users/cuihengjia/code2paper/code/MOS - Mitigating Optical-SAR Modality Gap for Cross-Modal Ship Re-Identification	/data1/users/cuihengjia/code2paper/paperyaml/MOS - Mitigating Optical-SAR Modality Gap for Cross-Modal Ship Re-Identification.yaml
/data1/users/cuihengjia/code2paper/code/MVGGT - Multimodal Visual Geometry Grounded Transformer for Multiview 3D Referring Expression Segmentation	/data1/users/cuihengjia/code2paper/paperyaml/MVGGT - Multimodal Visual Geometry Grounded Transformer for Multiview 3D Referring Expression Segmentation.yaml
/data1/users/cuihengjia/code2paper/code/MedCLIPSeg - Probabilistic Vision–Language Adaptation for Data-Efficient and Generalizable Medical Image Segmentation	/data1/users/cuihengjia/code2paper/paperyaml/MedCLIPSeg - Probabilistic Vision–Language Adaptation for Data-Efficient and Generalizable Medical Image Segmentation.yaml
/data1/users/cuihengjia/code2paper/code/Mitigating Instance Entanglement in Instance-Dependent Partial Label Learning	/data1/users/cuihengjia/code2paper/paperyaml/Mitigating Instance Entanglement in Instance-Dependent Partial Label Learning.yaml
EOF

echo
echo "batch_run_02 完成，汇总文件：$SUMMARY_FILE"
