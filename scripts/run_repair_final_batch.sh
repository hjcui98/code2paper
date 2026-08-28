#!/usr/bin/env bash
# Final same-code-state frozen authoring batch (plan 19.11 / review 2026-08-18).
# Runs the three authoring replays with Research-Graph callback continuation.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BATCH_ROOT=".tmp/c2p-repair-batch"
PROFILE="tests/live/profiles/qwen36_vllm_budgeted.example.env"

run_one() {
  local name="$1" frozen="$2" repo="$3" run_id="$4"
  echo "===== [$(date +%H:%M:%S)] $name replay start ====="
  python scripts/run_authoring_replay.py \
    "$frozen" \
    "$BATCH_ROOT/replay-$name" \
    --repo "$repo" \
    --run-id "$run_id" \
    --callback-rounds 2 \
    --callback-tool-turns 8 \
    --profile "$PROFILE" \
    2>&1 | tee "$BATCH_ROOT/replay-$name.log"
  echo "===== [$(date +%H:%M:%S)] $name replay exit=$? ====="
}

run_one dyg \
  ".tmp/c2p-stage1-canary/run-dyg" \
  "/data1/users/cuihengjia/code2paper/code_final/DyG-Mamba_ Continuous State Space Modeling on Dynamic Graphs" \
  "stage6-dyg"

run_one linearrag \
  ".tmp/c2p-stage1-canary/run-linearrag" \
  "/data1/users/cuihengjia/code2paper/code_final/LinearRAG - Linear Graph Retrieval-Augmented Generation on Large-scale Corpora" \
  "stage6-linearrag"

run_one ebcar \
  ".tmp/c2p-q5-batch3/run-ebcar-research" \
  "/data1/users/cuihengjia/code2paper/code_final/EBCAR - Embedding-Based Context-Aware Reranker" \
  "repair-ebcar-research"
