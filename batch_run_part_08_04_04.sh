#!/usr/bin/env bash
set -u
set -o pipefail

RESULT_ROOT="/data1/users/cuihengjia/result/batch_run_part_08_04_04_$(date +%Y%m%d_%H%M%S)"
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

idx=20
while IFS=$'\t' read -r project intent; do
  run_one "$idx" "$project" "$intent"
  idx=$((idx + 1))
done <<'EOF'
/data1/users/cuihengjia/code2paper/code_4/SeRL_ Self-play Reinforcement Learning for Large Language Models	/data1/users/cuihengjia/code2paper/paperyaml4/SeRL_ Self-play Reinforcement Learning for Large Language Models.yaml
/data1/users/cuihengjia/code2paper/code_4/Thinkless_ LLM Learns When to Think	/data1/users/cuihengjia/code2paper/paperyaml4/Thinkless_ LLM Learns When to Think.yaml
/data1/users/cuihengjia/code2paper/code_4/Towards Unsupervised Open-Set Graph Domain Adaptation via Dual	/data1/users/cuihengjia/code2paper/paperyaml4/Towards Unsupervised Open-Set Graph Domain Adaptation via Dual.yaml
/data1/users/cuihengjia/code2paper/code_4/UFO_ A Unified Approach to Fine-grained Visual Perception via	/data1/users/cuihengjia/code2paper/paperyaml4/UFO_ A Unified Approach to Fine-grained Visual Perception via.yaml
/data1/users/cuihengjia/code2paper/code_4/UI-Genie_ A Self-Improving Approach for Iteratively Boosting	/data1/users/cuihengjia/code2paper/paperyaml4/UI-Genie_ A Self-Improving Approach for Iteratively Boosting.yaml
/data1/users/cuihengjia/code2paper/code_4/Zooming from Context to Cue_ Hierarchical Preference Optimization	/data1/users/cuihengjia/code2paper/paperyaml4/Zooming from Context to Cue_ Hierarchical Preference Optimization.yaml
EOF

echo
echo "batch_run_part_08_04_04 完成，汇总文件：$SUMMARY_FILE"
