#!/usr/bin/env bash
set -u
set -o pipefail

RESULT_ROOT="/data1/users/cuihengjia/result/batch_run_part_08_04_02_$(date +%Y%m%d_%H%M%S)"
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

  if [ ! -d "$project" ]; then
    echo "[$idx] 项目目录不存在，跳过"
    printf "%s\tskipped(missing_project)\t%s\t%s\t%s\n" "$idx" "$name" "$out_root" "$log_file" >> "$SUMMARY_FILE"
    return 0
  fi
  if [ ! -f "$intent" ]; then
    echo "[$idx] intent 文件不存在，跳过"
    printf "%s\tskipped(missing_intent)\t%s\t%s\t%s\n" "$idx" "$name" "$out_root" "$log_file" >> "$SUMMARY_FILE"
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
    printf "%s\tsuccess\t%s\t%s\t%s\n" "$idx" "$name" "$out_root" "$log_file" >> "$SUMMARY_FILE"
  else
    echo "[$idx] 论文《$name》失败了，已跳过，继续下一篇"
    printf "%s\tfailed(%s)\t%s\t%s\t%s\n" "$idx" "$cmd_status" "$name" "$out_root" "$log_file" >> "$SUMMARY_FILE"
  fi
}

idx=8
while IFS=$'\t' read -r project intent; do
  run_one "$idx" "$project" "$intent"
  idx=$((idx + 1))
done <<'EOF'
/data1/users/cuihengjia/code2paper/code_4/Efficiently Scaling LLM Reasoning Programs with Certaindex	/data1/users/cuihengjia/code2paper/paperyaml4/Efficiently Scaling LLM Reasoning Programs with Certaindex.yaml
/data1/users/cuihengjia/code2paper/code_4/Exploring Diffusion Transformer Designs via Grafting	/data1/users/cuihengjia/code2paper/paperyaml4/Exploring Diffusion Transformer Designs via Grafting.yaml
/data1/users/cuihengjia/code2paper/code_4/First SFT, Second RL, Third UPT_ Continual Improving Multi-Modal LLM Reasoning via Unsupervised Post-Training	/data1/users/cuihengjia/code2paper/paperyaml4/First SFT, Second RL, Third UPT_ Continual Improving Multi-Modal LLM Reasoning via Unsupervised Post-Training.yaml
/data1/users/cuihengjia/code2paper/code_4/Gated Attention for Large Language Models_ Non-linearity, Sparsity,	/data1/users/cuihengjia/code2paper/paperyaml4/Gated Attention for Large Language Models_ Non-linearity, Sparsity,.yaml
/data1/users/cuihengjia/code2paper/code_4/GuardReasoner-VL_ Safeguarding VLMs via Reinforced Reasoning	/data1/users/cuihengjia/code2paper/paperyaml4/GuardReasoner-VL_ Safeguarding VLMs via Reinforced Reasoning.yaml
/data1/users/cuihengjia/code2paper/code_4/LLM-Explorer_ A Plug-in Reinforcement Learning Policy Exploration	/data1/users/cuihengjia/code2paper/paperyaml4/LLM-Explorer_ A Plug-in Reinforcement Learning Policy Exploration.yaml
EOF

echo
echo "batch_run_part_08_04_02 完成，汇总文件：$SUMMARY_FILE"
