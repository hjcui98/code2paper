#!/usr/bin/env bash
set -uo pipefail
ROOT="/home/cuihengjia/agent/Code2Paper copy"
PROFILE="tests/live/profiles/qwen38_vllm_budgeted.example.env"
STAMP="20260901"
BASE="/tmp/c2p-v34p0p3-8006-${STAMP}"
LOG="${BASE}/serial.log"
cd "$ROOT"
export PYTHONUNBUFFERED=1
{
  echo "===== SERIAL START $(date -Iseconds) ====="
  echo "code_state_digest sha256:64b7ab754a1ca5a9855271fab8f431eeb1da329dd42f54d47015af702eeb7cdc"
  curl -sS -m 5 http://127.0.0.1:8006/health || true
  echo
  curl -sS -m 5 http://127.0.0.1:8006/v1/models || true
  echo
  curl -sS -m 5 http://127.0.0.1:8006/metrics 2>/dev/null | rg "vllm:(num_requests_running|num_requests_waiting|kv_cache_usage_perc)\{" || true
} | tee -a "$LOG"

run_one() {
  local name="$1" frozen="$2" repo="$3" run_id="$4"
  local fresh="/tmp/c2p-v34p0p3-8006-${name}-${STAMP}"
  mkdir -p "$fresh"
  echo "===== START $name $(date -Iseconds) frozen=$frozen fresh=$fresh =====" | tee -a "$LOG"
  curl -sS -m 5 http://127.0.0.1:8006/metrics 2>/dev/null | rg "vllm:(num_requests_running|num_requests_waiting|kv_cache_usage_perc)\{" | tee -a "$LOG" || true
  python -u scripts/run_authoring_replay.py \
    "$frozen" \
    "$fresh" \
    --repo "$repo" \
    --run-id "$run_id" \
    --reuse-derived-authoring \
    --profile "$PROFILE" \
    --callback-rounds 1 \
    --callback-tool-turns 8 \
    > "$fresh/replay.stdout.log" 2>&1
  local ec=$?
  echo "===== DONE $name exit=$ec $(date -Iseconds) =====" | tee -a "$LOG"
  python3 - << PY
import json
from pathlib import Path
fresh=Path("$fresh")
rec_path=fresh/"execution_record.json"
print("execution_record", rec_path.is_file())
if rec_path.is_file():
    rec=json.loads(rec_path.read_text())
    se=rec.get("structural_exit") or {}
    print("exit_code", rec.get("exit_code"), "writer", rec.get("writer_status"), rec.get("writer_transaction_status"))
    print("structural eligible", se.get("eligible"), "paras", se.get("valid_required_paragraphs"), "/", se.get("required_paragraphs"),
          "slots", se.get("witnessed_slots"), "/", se.get("required_slots"),
          "formula", se.get("consumed_formula_packages"), "/", se.get("accepted_formula_packages"))
    print("terminal", rec.get("terminal_stage"), rec.get("terminal_reason"))
    print("digest", rec.get("code_state_digest"))
cand=fresh/"artifacts/06_authoring/publication_candidate_method.md"
if cand.is_file():
    text=cand.read_text()
    print("candidate_bytes", cand.stat().st_size)
    print("display_math", text.count("$$")//2)
    print("self_dot", text.count("self."))
    print("formula_placeholder", text.count("[[FORMULA:"))
PY
  echo "PROJECT_DONE name=$name exit=$ec"
  return 0
}

run_one ebcar \
  "/tmp/c2p-method-authoring-8006-direct-ebcar-v34-20260831" \
  "/data1/users/cuihengjia/code2paper/code_final/EBCAR - Embedding-Based Context-Aware Reranker" \
  "c2p-v34p0p3-8006-ebcar-20260901"

run_one dyg \
  "/tmp/c2p-method-authoring-8006-direct-dyg-v33-20260831" \
  "/data1/users/cuihengjia/code2paper/code_final/DyG-Mamba_ Continuous State Space Modeling on Dynamic Graphs" \
  "c2p-v34p0p3-8006-dyg-20260901"

run_one linearrag \
  "/tmp/c2p-method-authoring-8006-20260830-linearrag" \
  "/data1/users/cuihengjia/code2paper/code_final/LinearRAG - Linear Graph Retrieval-Augmented Generation on Large-scale Corpora" \
  "c2p-v34p0p3-8006-linearrag-20260901"

echo "===== SERIAL COMPLETE $(date -Iseconds) =====" | tee -a "$LOG"
