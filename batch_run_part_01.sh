#!/usr/bin/env bash
set -u
set -o pipefail

RESULT_ROOT="/data1/users/cuihengjia/result/batch_run_part_01_$(date +%Y%m%d_%H%M%S)"
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
/data1/users/cuihengjia/code2paper/code_raw/3DThinker - Think with 3D: Geometric Imagination Grounded Spatial Reasoning from Limited Views	/data1/users/cuihengjia/code2paper/paperyaml/3DThinker - Think with 3D - Geometric Imagination Grounded Spatial Reasoning from Limited Views.yaml
/data1/users/cuihengjia/code2paper/code_raw/ACoT-VLA - Action Chain-of-Thought for Vision-Language-Action Models	/data1/users/cuihengjia/code2paper/paperyaml/ACoT-VLA - Action Chain-of-Thought for Vision-Language-Action Models.yaml
/data1/users/cuihengjia/code2paper/code_raw/AOT - Token Reduction via Local and Global Contexts Optimization for Efficient Video Large Language Models	/data1/users/cuihengjia/code2paper/paperyaml/AOT - Token Reduction via Local and Global Contexts Optimization for Efficient Video Large Language Models.yaml
/data1/users/cuihengjia/code2paper/code_raw/AReS - Prime Once, then Reprogram Locally	/data1/users/cuihengjia/code2paper/paperyaml/AReS - Prime Once, then Reprogram Locally.yaml
/data1/users/cuihengjia/code2paper/code_raw/ApET - Approximation-Error Guided Token Compression for Efficient VLMs	/data1/users/cuihengjia/code2paper/paperyaml/ApET - Approximation-Error Guided Token Compression for Efficient VLMs.yaml
/data1/users/cuihengjia/code2paper/code_raw/BiCo - Composing Concepts from Images and Videos via Concept-prompt Binding	/data1/users/cuihengjia/code2paper/paperyaml/BiCo - Composing Concepts from Images and Videos via Concept-prompt Binding.yaml
/data1/users/cuihengjia/code2paper/code_raw/BiGain - Unified Token-wise Guidance for Diffusion Models	/data1/users/cuihengjia/code2paper/paperyaml/BiGain - Unified Token-wise Guidance for Diffusion Models.yaml
/data1/users/cuihengjia/code2paper/code_raw/Bootstrapping Multi-view Learning for Test-time Noisy Correspondence	/data1/users/cuihengjia/code2paper/paperyaml/Bootstrapping Multi-view Learning for Test-time Noisy Correspondence.yaml
/data1/users/cuihengjia/code2paper/code_raw/C-MET - Cross-Modal Enhancement Transformer	/data1/users/cuihengjia/code2paper/paperyaml/C-MET - Cross-Modal Enhancement Transformer.yaml
/data1/users/cuihengjia/code2paper/code_raw/C3G - Learning Compact 3D Representations with 2K Gaussians	/data1/users/cuihengjia/code2paper/paperyaml/C3G - Learning Compact 3D Representations with 2K Gaussians.yaml
EOF

echo
echo "batch_run_part_01 完成，汇总文件：$SUMMARY_FILE"
