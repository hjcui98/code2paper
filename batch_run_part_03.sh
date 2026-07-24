#!/usr/bin/env bash
set -u
set -o pipefail

RESULT_ROOT="/data1/users/cuihengjia/result/batch_run_part_03_$(date +%Y%m%d_%H%M%S)"
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
/data1/users/cuihengjia/code2paper/code_raw/FaithC	/data1/users/cuihengjia/code2paper/paperyaml/FaithC.yaml
/data1/users/cuihengjia/code2paper/code_raw/FastGS - Training 3D Gaussian Splatting in 100 Seconds	/data1/users/cuihengjia/code2paper/paperyaml/FastGS - Training 3D Gaussian Splatting in 100 Seconds.yaml
/data1/users/cuihengjia/code2paper/code_raw/Flow3r - Factored Flow Prediction for Scalable Visual Geometry Learning	/data1/users/cuihengjia/code2paper/paperyaml/Flow3r - Factored Flow Prediction for Scalable Visual Geometry Learning.yaml
/data1/users/cuihengjia/code2paper/code_raw/FlowMotion - Training-Free Flow Guidance for Video Motion Customization	/data1/users/cuihengjia/code2paper/paperyaml/FlowMotion - Training-Free Flow Guidance for Video Motion Customization.yaml
/data1/users/cuihengjia/code2paper/code_raw/From Static to Dynamic - Exploring Self-supervised Image-to-Video Representation Transfer Learning _ Co-Settle	/data1/users/cuihengjia/code2paper/paperyaml/From Static to Dynamic - Exploring Self-supervised Image-to-Video Representation Transfer Learning _ Co-Settle.yaml
/data1/users/cuihengjia/code2paper/code_raw/G2VLM - Geometry Grounded Vision-Language Model	/data1/users/cuihengjia/code2paper/paperyaml/G2VLM - Geometry Grounded Vision-Language Model.yaml
/data1/users/cuihengjia/code2paper/code_raw/GGPT - Geometry-grounded Point Transformer	/data1/users/cuihengjia/code2paper/paperyaml/GGPT - Geometry-grounded Point Transformer.yaml
/data1/users/cuihengjia/code2paper/code_raw/GThinker - Reasoning MLLM with Visual Cues and Visual Rethinking	/data1/users/cuihengjia/code2paper/paperyaml/GThinker - Reasoning MLLM with Visual Cues and Visual Rethinking.yaml
/data1/users/cuihengjia/code2paper/code_raw/Goal Force - Teaching Video Models To Accomplish Physics-Conditioned Goals	/data1/users/cuihengjia/code2paper/paperyaml/Goal Force - Teaching Video Models To Accomplish Physics-Conditioned Goals.yaml
/data1/users/cuihengjia/code2paper/code_raw/Group Editing	/data1/users/cuihengjia/code2paper/paperyaml/Group Editing.yaml
EOF

echo
echo "batch_run_part_03 完成，汇总文件：$SUMMARY_FILE"
