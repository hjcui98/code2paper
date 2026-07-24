#!/usr/bin/env bash
set -u
set -o pipefail

RESULT_ROOT="/data1/users/cuihengjia/result/batch_run_part_08_01_$(date +%Y%m%d_%H%M%S)"
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

idx=1
while IFS=$'\t' read -r project intent; do
  run_one "$idx" "$project" "$intent"
  idx=$((idx + 1))
done <<'EOF'
/data1/users/cuihengjia/code2paper/code_3/AutoFigure - Generating and Refining Publication-Ready Scientific Illustrations	/data1/users/cuihengjia/code2paper/paperyaml3/AutoFigure - Generating and Refining Publication-Ready Scientific Illustrations.yaml
/data1/users/cuihengjia/code2paper/code_3/CARD - Towards Conditional Design of Multi-agent Topological Structures	/data1/users/cuihengjia/code2paper/paperyaml3/CARD - Towards Conditional Design of Multi-agent Topological Structures.yaml
/data1/users/cuihengjia/code2paper/code_3/Captain Safari - A World Engine with Pose-Aligned 3D Memory	/data1/users/cuihengjia/code2paper/paperyaml3/Captain Safari - A World Engine with Pose-Aligned 3D Memory.yaml
/data1/users/cuihengjia/code2paper/code_3/Context Learning for Multi-Agent Discussion	/data1/users/cuihengjia/code2paper/paperyaml3/Context Learning for Multi-Agent Discussion.yaml
/data1/users/cuihengjia/code2paper/code_3/EBCAR - Embedding-Based Context-Aware Reranker	/data1/users/cuihengjia/code2paper/paperyaml3/EBCAR - Embedding-Based Context-Aware Reranker.yaml
/data1/users/cuihengjia/code2paper/code_3/EgoAVU - Egocentric Audio-Visual Understanding	/data1/users/cuihengjia/code2paper/paperyaml3/EgoAVU - Egocentric Audio-Visual Understanding.yaml
/data1/users/cuihengjia/code2paper/code_3/G-reasoner - Foundation Models for Unified Reasoning over Graph-structured Knowledge	/data1/users/cuihengjia/code2paper/paperyaml3/G-reasoner - Foundation Models for Unified Reasoning over Graph-structured Knowledge.yaml
/data1/users/cuihengjia/code2paper/code_3/GSI-Bench - Exploring Spatial Intelligence from a Generative Perspective	/data1/users/cuihengjia/code2paper/paperyaml3/GSI-Bench - Exploring Spatial Intelligence from a Generative Perspective.yaml
/data1/users/cuihengjia/code2paper/code_3/Imagine Before Concentration - Diffusion-Guided Registers Enhance Partially Relevant Video Retrieval	/data1/users/cuihengjia/code2paper/paperyaml3/Imagine Before Concentration - Diffusion-Guided Registers Enhance Partially Relevant Video Retrieval.yaml
/data1/users/cuihengjia/code2paper/code_3/IterResearch - Rethinking Long-Horizon Agents with Interaction Scaling	/data1/users/cuihengjia/code2paper/paperyaml3/IterResearch - Rethinking Long-Horizon Agents with Interaction Scaling.yaml
/data1/users/cuihengjia/code2paper/code_3/LUMINA - Detecting Hallucinations in RAG System with Context–Knowledge Signals	/data1/users/cuihengjia/code2paper/paperyaml3/LUMINA - Detecting Hallucinations in RAG System with Context–Knowledge Signals.yaml
/data1/users/cuihengjia/code2paper/code_3/LinearRAG - Linear Graph Retrieval-Augmented Generation on Large-scale Corpora	/data1/users/cuihengjia/code2paper/paperyaml3/LinearRAG - Linear Graph Retrieval-Augmented Generation on Large-scale Corpora.yaml
/data1/users/cuihengjia/code2paper/code_3/LongVT - Incentivizing Thinking with Long Videos via Native Tool Calling	/data1/users/cuihengjia/code2paper/paperyaml3/LongVT - Incentivizing Thinking with Long Videos via Native Tool Calling.yaml
/data1/users/cuihengjia/code2paper/code_3/M4-RAG - Benchmarking and Scaling Retrieval-Augmented Generation for Vision-Language Models	/data1/users/cuihengjia/code2paper/paperyaml3/M4-RAG - Benchmarking and Scaling Retrieval-Augmented Generation for Vision-Language Models.yaml
/data1/users/cuihengjia/code2paper/code_3/MARTI - A Framework for Multi-Agent LLM Systems	/data1/users/cuihengjia/code2paper/paperyaml3/MARTI - A Framework for Multi-Agent LLM Systems.yaml
/data1/users/cuihengjia/code2paper/code_3/MC-Search - Evaluating and Enhancing Multimodal Agentic Search with Structured Long Reasoning Chains	/data1/users/cuihengjia/code2paper/paperyaml3/MC-Search - Evaluating and Enhancing Multimodal Agentic Search with Structured Long Reasoning Chains.yaml
EOF

echo
echo "batch_run_part_08_01 完成，汇总文件：$SUMMARY_FILE"
