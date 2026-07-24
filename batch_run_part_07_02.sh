#!/usr/bin/env bash
set -u
set -o pipefail

RESULT_ROOT="/data1/users/cuihengjia/result/batch_run_part_07_02_$(date +%Y%m%d_%H%M%S)"
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

idx=24
while IFS=$'\t' read -r project intent; do
  run_one "$idx" "$project" "$intent"
  idx=$((idx + 1))
done <<'EOF'
/data1/users/cuihengjia/code2paper/code_2/Copy-Paste to Mitigate Large Language Model Hallucinations	/data1/users/cuihengjia/code2paper/paperyaml2/Copy-Paste to Mitigate Large Language Model Hallucinations.yaml
/data1/users/cuihengjia/code2paper/code_2/Cosmos Policy - Fine-Tuning Video Models for Visuomotor Control and Planning	/data1/users/cuihengjia/code2paper/paperyaml2/Cosmos Policy - Fine-Tuning Video Models for Visuomotor Control and Planning.yaml
/data1/users/cuihengjia/code2paper/code_2/CrossPL - Systematic Evaluation of Large Language Models for Cross Programming Language Interoperating Code Generation	/data1/users/cuihengjia/code2paper/paperyaml2/CrossPL - Systematic Evaluation of Large Language Models for Cross Programming Language Interoperating Code Generation.yaml
/data1/users/cuihengjia/code2paper/code_2/DASH - Deterministic Attention Scheduling for High-throughput Reproducible LLM Training	/data1/users/cuihengjia/code2paper/paperyaml2/DASH - Deterministic Attention Scheduling for High-throughput Reproducible LLM Training.yaml
/data1/users/cuihengjia/code2paper/code_2/Deep Think with Confidence	/data1/users/cuihengjia/code2paper/paperyaml2/Deep Think with Confidence.yaml
/data1/users/cuihengjia/code2paper/code_2/Detection of unknown unknowns in autonomous systems	/data1/users/cuihengjia/code2paper/paperyaml2/Detection of unknown unknowns in autonomous systems.yaml
/data1/users/cuihengjia/code2paper/code_2/DiffuDETR - Rethinking Detection Transformers with Denoising Diffusion Process	/data1/users/cuihengjia/code2paper/paperyaml2/DiffuDETR - Rethinking Detection Transformers with Denoising Diffusion Process.yaml
/data1/users/cuihengjia/code2paper/code_2/Discrete Diffusion for Bundle Construction	/data1/users/cuihengjia/code2paper/paperyaml2/Discrete Diffusion for Bundle Construction.yaml
/data1/users/cuihengjia/code2paper/code_2/Does FLUX Already Know How to Perform Physically Plausible Image Composition	/data1/users/cuihengjia/code2paper/paperyaml2/Does FLUX Already Know How to Perform Physically Plausible Image Composition.yaml
/data1/users/cuihengjia/code2paper/code_2/DriftLite - Lightweight Drift Control for Inference-Time Scaling of Diffusion Models	/data1/users/cuihengjia/code2paper/paperyaml2/DriftLite - Lightweight Drift Control for Inference-Time Scaling of Diffusion Models.yaml
/data1/users/cuihengjia/code2paper/code_2/Enhancing Visual Token Representations for Video Large Language Models via Training-free Spatial-Temporal Pooling and Gridding	/data1/users/cuihengjia/code2paper/paperyaml2/Enhancing Visual Token Representations for Video Large Language Models via Training-free Spatial-Temporal Pooling and Gridding.yaml
/data1/users/cuihengjia/code2paper/code_2/Error as Signal - Stiffness-Aware Diffusion Sampling via Embedded Runge-Kutta Guidance	/data1/users/cuihengjia/code2paper/paperyaml2/Error as Signal - Stiffness-Aware Diffusion Sampling via Embedded Runge-Kutta Guidance.yaml
/data1/users/cuihengjia/code2paper/code_2/ExPO-HM - Learning to Explain-then-Detect for Hateful Meme Detection	/data1/users/cuihengjia/code2paper/paperyaml2/ExPO-HM - Learning to Explain-then-Detect for Hateful Meme Detection.yaml
/data1/users/cuihengjia/code2paper/code_2/Exploring Interpretability for Visual Prompt Tuning with Cross-layer Concepts	/data1/users/cuihengjia/code2paper/paperyaml2/Exploring Interpretability for Visual Prompt Tuning with Cross-layer Concepts.yaml
/data1/users/cuihengjia/code2paper/code_2/Exploring the Potential of Encoder-free Architectures in 3D LMMs	/data1/users/cuihengjia/code2paper/paperyaml2/Exploring the Potential of Encoder-free Architectures in 3D LMMs.yaml
/data1/users/cuihengjia/code2paper/code_2/FAST‑DIPS - Adjoint‑Free Analytic Steps and Hard‑Constrained Likelihood Correction for Diffusion‑Prior Inverse Problems	/data1/users/cuihengjia/code2paper/paperyaml2/FAST‑DIPS - Adjoint‑Free Analytic Steps and Hard‑Constrained Likelihood Correction for Diffusion‑Prior Inverse Problems.yaml
/data1/users/cuihengjia/code2paper/code_2/FlashDLM - Accelerating Diffusion Language Model Inference via Efficient KV Caching and Guided Diffusion	/data1/users/cuihengjia/code2paper/paperyaml2/FlashDLM - Accelerating Diffusion Language Model Inference via Efficient KV Caching and Guided Diffusion.yaml
/data1/users/cuihengjia/code2paper/code_2/Flow Caching for Autoregressive Video Generation	/data1/users/cuihengjia/code2paper/paperyaml2/Flow Caching for Autoregressive Video Generation.yaml
/data1/users/cuihengjia/code2paper/code_2/Flow2GAN - Hybrid Flow Matching and GAN with Multi-Resolution Network for Few-step High-Fidelity Audio Generation	/data1/users/cuihengjia/code2paper/paperyaml2/Flow2GAN - Hybrid Flow Matching and GAN with Multi-Resolution Network for Few-step High-Fidelity Audio Generation.yaml
/data1/users/cuihengjia/code2paper/code_2/GEPA - Reflective Prompt Evolution Can Outperform Reinforcement Learning	/data1/users/cuihengjia/code2paper/paperyaml2/GEPA - Reflective Prompt Evolution Can Outperform Reinforcement Learning.yaml
/data1/users/cuihengjia/code2paper/code_2/Hallucination-aware Intermediate Representation Edit in Large Vision-Language Models	/data1/users/cuihengjia/code2paper/paperyaml2/Hallucination-aware Intermediate Representation Edit in Large Vision-Language Models.yaml
/data1/users/cuihengjia/code2paper/code_2/HiDrop - Hierarchical Vision Token Reduction in MLLMs via Late Injection, Concave Pyramid Pruning, and Early Exit	/data1/users/cuihengjia/code2paper/paperyaml2/HiDrop - Hierarchical Vision Token Reduction in MLLMs via Late Injection, Concave Pyramid Pruning, and Early Exit.yaml
EOF

echo
echo "batch_run_part_07_02 完成，汇总文件：$SUMMARY_FILE"
