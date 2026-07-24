#!/usr/bin/env bash
set -u
set -o pipefail

RESULT_ROOT="/data1/users/cuihengjia/result/batch_run_part_07_04_$(date +%Y%m%d_%H%M%S)"
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

idx=68
while IFS=$'\t' read -r project intent; do
  run_one "$idx" "$project" "$intent"
  idx=$((idx + 1))
done <<'EOF'
/data1/users/cuihengjia/code2paper/code_2/Rethinking LLM-as-a-Judge - Representation-as-a-Judge with Small Language Models via Semantic Capacity Asymmetry	/data1/users/cuihengjia/code2paper/paperyaml2/Rethinking LLM-as-a-Judge - Representation-as-a-Judge with Small Language Models via Semantic Capacity Asymmetry.yaml
/data1/users/cuihengjia/code2paper/code_2/ST-SimDiff - Balancing Spatiotemporal Similarity and Difference for Efficient Video Understanding with MLLMs	/data1/users/cuihengjia/code2paper/paperyaml2/ST-SimDiff - Balancing Spatiotemporal Similarity and Difference for Efficient Video Understanding with MLLMs.yaml
/data1/users/cuihengjia/code2paper/code_2/SYNC - Measuring and Advancing Synthesizability in Structure-Based Drug Design	/data1/users/cuihengjia/code2paper/paperyaml2/SYNC - Measuring and Advancing Synthesizability in Structure-Based Drug Design.yaml
/data1/users/cuihengjia/code2paper/code_2/Scalable Multilingual Multimodal Machine Translation with Speech-Text Fusion	/data1/users/cuihengjia/code2paper/paperyaml2/Scalable Multilingual Multimodal Machine Translation with Speech-Text Fusion.yaml
/data1/users/cuihengjia/code2paper/code_2/Scaling up Memory for Robotic Control via Experience Retrieval	/data1/users/cuihengjia/code2paper/paperyaml2/Scaling up Memory for Robotic Control via Experience Retrieval.yaml
/data1/users/cuihengjia/code2paper/code_2/Semantic Visual Anomaly Detection and Reasoning in AI-Generated Images	/data1/users/cuihengjia/code2paper/paperyaml2/Semantic Visual Anomaly Detection and Reasoning in AI-Generated Images.yaml
/data1/users/cuihengjia/code2paper/code_2/StreamingThinker - Large Language Models Can Think While Reading	/data1/users/cuihengjia/code2paper/paperyaml2/StreamingThinker - Large Language Models Can Think While Reading.yaml
/data1/users/cuihengjia/code2paper/code_2/Swap-guided Preference Learning for Personalized Reinforcement Learning from Human Feedback	/data1/users/cuihengjia/code2paper/paperyaml2/Swap-guided Preference Learning for Personalized Reinforcement Learning from Human Feedback.yaml
/data1/users/cuihengjia/code2paper/code_2/TSPulse - Tiny Pre-Trained Models with Disentangled Representations for Rapid Time-Series Analysis	/data1/users/cuihengjia/code2paper/paperyaml2/TSPulse - Tiny Pre-Trained Models with Disentangled Representations for Rapid Time-Series Analysis.yaml
/data1/users/cuihengjia/code2paper/code_2/Thicker and Quicker - The Jumbo Token for Fast Plain Vision Transformers	/data1/users/cuihengjia/code2paper/paperyaml2/Thicker and Quicker - The Jumbo Token for Fast Plain Vision Transformers.yaml
/data1/users/cuihengjia/code2paper/code_2/Toward Faithful Retrieval-Augmented Generation with Sparse Autoencoders	/data1/users/cuihengjia/code2paper/paperyaml2/Toward Faithful Retrieval-Augmented Generation with Sparse Autoencoders.yaml
/data1/users/cuihengjia/code2paper/code_2/UFO-4D - Unposed Feedforward 4D Reconstruction from Two Images	/data1/users/cuihengjia/code2paper/paperyaml2/UFO-4D - Unposed Feedforward 4D Reconstruction from Two Images.yaml
/data1/users/cuihengjia/code2paper/code_2/Understanding and Improving Hyperbolic Deep Reinforcement Learning	/data1/users/cuihengjia/code2paper/paperyaml2/Understanding and Improving Hyperbolic Deep Reinforcement Learning.yaml
/data1/users/cuihengjia/code2paper/code_2/Uniform Discrete Diffusion with Metric Path for Video Generation	/data1/users/cuihengjia/code2paper/paperyaml2/Uniform Discrete Diffusion with Metric Path for Video Generation.yaml
/data1/users/cuihengjia/code2paper/code_2/VADv2 - End-to-End Vectorized Autonomous Driving via Probabilistic Planning	/data1/users/cuihengjia/code2paper/paperyaml2/VADv2 - End-to-End Vectorized Autonomous Driving via Probabilistic Planning.yaml
/data1/users/cuihengjia/code2paper/code_2/VideoPhy-2 - A Challenging Action-Centric Physical Commonsense Evaluation in Video Generation	/data1/users/cuihengjia/code2paper/paperyaml2/VideoPhy-2 - A Challenging Action-Centric Physical Commonsense Evaluation in Video Generation.yaml
/data1/users/cuihengjia/code2paper/code_2/Vision-R1 - Incentivizing Reasoning Capability in Multimodal Large Language Models	/data1/users/cuihengjia/code2paper/paperyaml2/Vision-R1 - Incentivizing Reasoning Capability in Multimodal Large Language Models.yaml
/data1/users/cuihengjia/code2paper/code_2/WSVD - Weighted Low-Rank Approximation for Fast and Efficient Execution of Low-Precision Vision-Language Models	/data1/users/cuihengjia/code2paper/paperyaml2/WSVD - Weighted Low-Rank Approximation for Fast and Efficient Execution of Low-Precision Vision-Language Models.yaml
/data1/users/cuihengjia/code2paper/code_2/What Do Large Language Models Know About Opinions?	/data1/users/cuihengjia/code2paper/paperyaml2/What Do Large Language Models Know About Opinions?.yaml
/data1/users/cuihengjia/code2paper/code_2/When AI Agents Collude Online - Financial Fraud Risks by Collaborative LLM Agents on Social Platforms	/data1/users/cuihengjia/code2paper/paperyaml2/When AI Agents Collude Online - Financial Fraud Risks by Collaborative LLM Agents on Social Platforms.yaml
/data1/users/cuihengjia/code2paper/code_2/YoNoSplat - You Only Need One Model for Feedforward 3D Gaussian Splatting	/data1/users/cuihengjia/code2paper/paperyaml2/YoNoSplat - You Only Need One Model for Feedforward 3D Gaussian Splatting.yaml
/data1/users/cuihengjia/code2paper/code_2/YuE - Scaling Open Foundation Models for Long-Form Music Generation	/data1/users/cuihengjia/code2paper/paperyaml2/YuE - Scaling Open Foundation Models for Long-Form Music Generation.yaml
EOF

echo
echo "batch_run_part_07_04 完成，汇总文件：$SUMMARY_FILE"
