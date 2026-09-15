#!/usr/bin/env bash
set -u
set -o pipefail

# Live P8 matrix launcher for the ten projects named by the unified-context
# execution plan.  The queue is intentionally serial by default: the
# designated qwen36 runtime is a single TP=1 service and the live profile
# declares one project at a time.  Set C2P_MAX_PARALLEL only after an
# explicitly approved resource check; the default remains 1.

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BATCH_ROOT="${1:-/tmp/c2p-unified-live-matrix-20260907-7701a7e}"
PROFILE="${C2P_PROFILE:-${REPO_ROOT}/tests/live/profiles/qwen36_vllm_budgeted.example.env}"
CALLBACK_ROUNDS="${C2P_CALLBACK_ROUNDS:-1}"
CALLBACK_TOOL_TURNS="${C2P_CALLBACK_TOOL_TURNS:-8}"

if [[ -e "${BATCH_ROOT}" ]]; then
  echo "refusing to reuse existing batch root: ${BATCH_ROOT}" >&2
  exit 2
fi
if [[ ! -f "${PROFILE}" ]]; then
  echo "profile not found: ${PROFILE}" >&2
  exit 2
fi

mkdir -p "${BATCH_ROOT}/logs"

HEALTH_FILE="${BATCH_ROOT}/preflight_health.json"
MODELS_FILE="${BATCH_ROOT}/preflight_models.json"
METRICS_FILE="${BATCH_ROOT}/preflight_metrics.txt"
GPU_FILE="${BATCH_ROOT}/preflight_gpu.txt"
STATUS_FILE="${BATCH_ROOT}/summary.tsv"
LAUNCHER_LOG="${BATCH_ROOT}/launcher.log"
RUN_MANIFEST_JSON="${BATCH_ROOT}/run_manifest.json"
BATCH_TERMINAL_EVENT="${BATCH_ROOT}/run_terminal_event.json"
SCRIPT_PATH="${REPO_ROOT}/scripts/run_unified_ten_project_live_matrix_20260907.sh"
SCRIPT_DIGEST="$(sha256sum "${SCRIPT_PATH}" | awk '{print $1}')"
PROFILE_DIGEST="$(sha256sum "${PROFILE}" | awk '{print $1}')"

write_terminal_event() {
  local target="$1"
  local run_id="$2"
  local project_id="$3"
  local terminal_stage="$4"
  local terminal_reason="$5"
  local exit_code="$6"
  local last_completed="$7"
  python - "${target}" "${run_id}" "${project_id}" "${terminal_stage}" \
    "${terminal_reason}" "${exit_code}" "${last_completed}" <<'PY'
import hashlib
import json
import os
import sys
import time
from pathlib import Path

target = Path(sys.argv[1])
payload = {
    "schema_version": "unified_run_terminal_event_v1",
    "event_kind": "run_terminal",
    "run_id": sys.argv[2],
    "project_id": sys.argv[3],
    "terminal_stage": sys.argv[4],
    "terminal_reason": sys.argv[5],
    "exit_code": int(sys.argv[6]),
    "last_completed_invocation_id": sys.argv[7],
    "recorded_at_unix": time.time(),
}
canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
payload["content_digest"] = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
target.parent.mkdir(parents=True, exist_ok=True)
temporary = target.with_name(f".{target.name}.tmp-{os.getpid()}")
temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(temporary, target)
PY
}

write_batch_terminal() {
  write_terminal_event "${BATCH_TERMINAL_EVENT}" \
    "unified-live-matrix-20260907" "batch" "$1" "$2" "$3" ""
}

trap 'write_batch_terminal "signal" "SIGINT" 130; exit 130' INT
trap 'write_batch_terminal "signal" "SIGTERM" 143; exit 143' TERM
trap 'write_batch_terminal "signal" "SIGHUP" 129; exit 129' HUP

health_http="$(curl -sS --max-time 8 -o "${HEALTH_FILE}" -w '%{http_code}' http://127.0.0.1:8003/health 2>/dev/null || true)"
models_http="$(curl -sS --max-time 8 -o "${MODELS_FILE}" -w '%{http_code}' http://127.0.0.1:8003/v1/models 2>/dev/null || true)"
curl -sS --max-time 8 http://127.0.0.1:8003/metrics >"${METRICS_FILE}" 2>/dev/null || true
nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader >"${GPU_FILE}" 2>&1 || true

if [[ "${health_http}" != "200" || "${models_http}" != "200" ]]; then
  echo "runtime preflight failed: health=${health_http} models=${models_http}" | tee -a "${LAUNCHER_LOG}" >&2
  write_batch_terminal "preflight" "health_or_models_failed" 2
  exit 2
fi
if ! grep -q 'qwen36-27b-nvfp4' "${MODELS_FILE}"; then
  echo "runtime preflight failed: qwen36-27b-nvfp4 is not served" | tee -a "${LAUNCHER_LOG}" >&2
  write_batch_terminal "preflight" "required_model_not_served" 2
  exit 2
fi

{
  printf 'code_state='; git -C "${REPO_ROOT}" rev-parse HEAD 2>/dev/null || true
  printf 'health_http=%s\n' "${health_http}"
  printf 'models_http=%s\n' "${models_http}"
  printf 'profile=%s\n' "${PROFILE}"
  printf 'profile_digest=%s\n' "${PROFILE_DIGEST}"
  printf 'script=%s\n' "${SCRIPT_PATH}"
  printf 'script_digest=%s\n' "${SCRIPT_DIGEST}"
  printf 'mode=unified\n'
  printf 'callback_rounds=%s\n' "${CALLBACK_ROUNDS}"
  printf 'callback_tool_turns=%s\n' "${CALLBACK_TOOL_TURNS}"
  printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
} >"${BATCH_ROOT}/run_manifest.txt"
git -C "${REPO_ROOT}" status --short >"${BATCH_ROOT}/worktree_status.txt" 2>&1 || true
printf 'index\tproject\tstatus\texit_code\tstarted_at\tended_at\tout_root\tlog_file\n' >"${STATUS_FILE}"

PROJECT_IDS=(
  dyg
  linearrag
  ebcar
  rap
  lookahead
  unimmad
  codequant
  domain_pruning
  fastgs
  learnat
)

FROZEN_ROOTS=(
  "/tmp/c2p-method-authoring-8006-direct-dyg-v40-20260831"
  "/tmp/c2p-method-authoring-8006-direct-linearrag-20260830"
  "/tmp/c2p-method-authoring-8006-direct-ebcar-v34-20260831"
  "/tmp/c2p-gpu1-cutover-remaining-20260906-r2/rap"
  "/tmp/c2p-gpu1-cutover-remaining-20260906-r2/lookahead"
  "/tmp/c2p-gpu1-cutover-remaining-20260906-r2/unimmad"
  "/tmp/c2p-gpu1-cutover-remaining-20260906-r2/codequant"
  "/tmp/c2p-gpu1-cutover-remaining-20260906-r2/domain_pruning"
  "/tmp/c2p-gpu1-cutover-remaining-20260906-r2/fastgs"
  "/tmp/c2p-gpu1-cutover-remaining-20260906-r2/learnat"
)

REPOS=(
  "/data1/users/cuihengjia/code2paper/code_final/DyG-Mamba_ Continuous State Space Modeling on Dynamic Graphs"
  "/data1/users/cuihengjia/code2paper/code_final/LinearRAG - Linear Graph Retrieval-Augmented Generation on Large-scale Corpora"
  "/data1/users/cuihengjia/code2paper/code_final/EBCAR - Embedding-Based Context-Aware Reranker"
  "/data1/users/cuihengjia/code2paper/code_final/RAP - Fast Feedforward Rendering-Free Attribute-Guided Primitive Importance Score Prediction for Efficient 3D Gaussian Splatting Processing"
  "/data1/users/cuihengjia/code2paper/code_final/Scaling Speculative Decoding with Lookahead Reasoning"
  "/data1/users/cuihengjia/code2paper/code_final/UniMMAD"
  "/data1/users/cuihengjia/code2paper/code_final/CodeQuant - Unified Clustering and Quantization for Enhanced Outlier Smoothing in Low-Precision Mixture-of-Experts"
  "/data1/users/cuihengjia/code2paper/code_final/Domain-Specific Pruning of Large Mixture-of-Experts Models with"
  "/data1/users/cuihengjia/code2paper/code_final/FastGS - Training 3D Gaussian Splatting in 100 Seconds"
  "/data1/users/cuihengjia/code2paper/code_final/LearNAT - Learning NL2SQL with AST-guided Task Decomposition for Large Language Models"
)

python - "${RUN_MANIFEST_JSON}" "${BATCH_ROOT}" "${PROFILE}" \
  "${PROFILE_DIGEST}" "${SCRIPT_PATH}" "${SCRIPT_DIGEST}" \
  "${CALLBACK_ROUNDS}" "${CALLBACK_TOOL_TURNS}" <<'PY'
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

target = Path(sys.argv[1])
batch_root = Path(sys.argv[2])
profile = sys.argv[3]
profile_digest = sys.argv[4]
script = sys.argv[5]
script_digest = sys.argv[6]
callback_rounds = int(sys.argv[7])
callback_tool_turns = int(sys.argv[8])
repo_root = Path(script).resolve().parents[1]
dirty_lines = subprocess.run(
    ["git", "-C", str(repo_root), "status", "--short"],
    check=False,
    capture_output=True,
    text=True,
).stdout.splitlines()
profile_model = ""
try:
    for line in Path(profile).read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("export CODE2PAPER_LLM_MODEL="):
            profile_model = line.split("=", 1)[1].strip().strip("'\"")
            break
except OSError:
    pass
payload = {
    "schema_version": "unified_live_matrix_run_manifest_v1",
    "run_id": "unified-live-matrix-20260907",
    "mode": "unified",
    "batch_root": str(batch_root),
    "profile": profile,
    "profile_digest": "sha256:" + profile_digest,
    "profile_model": profile_model,
    "script": script,
    "script_digest": "sha256:" + script_digest,
    "code_commit": subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip(),
    "dirty_files": dirty_lines,
    "dirty_files_digest": "sha256:" + hashlib.sha256(
        ("\n".join(dirty_lines) + "\n").encode("utf-8")
    ).hexdigest(),
    "run_manifest_text": str(
        (batch_root / "run_manifest.txt").read_text(encoding="utf-8")
    ),
    "callback_rounds": callback_rounds,
    "callback_tool_turns": callback_tool_turns,
    "started_at_unix": time.time(),
}
canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
payload["content_digest"] = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
temporary = target.with_name(f".{target.name}.tmp-{os.getpid()}")
temporary.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
os.replace(temporary, target)
PY

write_project_terminal() {
  local out_root="$1"
  local project_id="$2"
  local run_id="$3"
  local stage="$4"
  local reason="$5"
  local status_code="$6"
  write_terminal_event \
    "${out_root}/artifacts/06_authoring/invocations/run_terminal_event.json" \
    "${run_id}" "${project_id}" "${stage}" "${reason}" "${status_code}" ""
}

write_project_manifest() {
  local out_root="$1"
  local project_id="$2"
  local run_id="$3"
  local frozen_root="$4"
  local repo="$5"
  python - "${out_root}/run_manifest.json" "${project_id}" "${run_id}" \
    "${frozen_root}" "${repo}" "${PROFILE}" "${PROFILE_DIGEST}" \
    "${SCRIPT_PATH}" "${SCRIPT_DIGEST}" "${REPO_ROOT}" <<'PY'
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

target = Path(sys.argv[1])
project_id, run_id, frozen_root, repo = sys.argv[2:6]
profile, profile_digest, script, script_digest, repo_root = sys.argv[6:11]

def json_mapping(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}

frozen = Path(frozen_root)
tree_values = []
for relative in (
    "artifacts/06_authoring/repo_snapshot_v2.json",
    "artifacts/repo_snapshot_v2.json",
    "artifacts/research_product/repo_snapshot_v2.json",
    "artifacts/06_authoring/repository_source_manifest_v1.json",
    "artifacts/repository_source_manifest_v1.json",
    "artifacts/research_product/repository_source_manifest_v1.json",
    "artifacts/06_authoring/repository_authoring_artifacts_v1.json",
    "artifacts/repository_authoring_artifacts_v1.json",
    "artifacts/research_product/research_continuation_seed_v1.json",
    "execution_record.json",
):
    payload = json_mapping(frozen / relative)
    if relative == "execution_record.json":
        payload = payload.get("research_continuation_seed", {})
    value = str(payload.get("project_tree_hash") or "").strip()
    if value:
        tree_values.append(value)
expected_hash = tree_values[0] if tree_values and len(set(tree_values)) == 1 else ""
actual_hash = ""
actual_error = ""
try:
    sys.path.insert(0, str(Path(repo_root) / "src"))
    from code2paper.agentic.repo_snapshot import build_repo_snapshot
    actual_hash = str(build_repo_snapshot(repo).project_tree_hash or "")
except Exception as exc:
    actual_error = type(exc).__name__ + ":" + str(exc)[:180]
tree_status = (
    "match" if expected_hash and actual_hash and expected_hash == actual_hash
    else "mismatch" if expected_hash and actual_hash
    else "unavailable"
)
repo_root_path = Path(script).resolve().parents[1]
dirty = subprocess.run(
    ["git", "-C", str(repo_root_path), "status", "--short"],
    check=False,
    capture_output=True,
    text=True,
).stdout.splitlines()
payload = {
    "schema_version": "unified_live_project_run_manifest_v1",
    "run_id": run_id,
    "project_id": project_id,
    "mode": "unified",
    "frozen_root": frozen_root,
    "repo": str(Path(repo)),
    "expected_project_tree_hash": expected_hash,
    "actual_project_tree_hash": actual_hash,
    "tree_hash_status": tree_status,
    "tree_hash_error": actual_error,
    "profile": profile,
    "profile_digest": "sha256:" + profile_digest,
    "script": script,
    "script_digest": "sha256:" + script_digest,
    "code_commit": subprocess.run(
        ["git", "-C", str(repo_root_path), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip(),
    "dirty_files": dirty,
    "started_at_unix": time.time(),
}
canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
payload["content_digest"] = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
target.parent.mkdir(parents=True, exist_ok=True)
temporary = target.with_name(f".{target.name}.tmp-{os.getpid()}")
temporary.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
os.replace(temporary, target)
PY
}

run_one() {
  local index="$1"
  local project_id="${PROJECT_IDS[$index]}"
  local frozen_root="${FROZEN_ROOTS[$index]}"
  local repo="${REPOS[$index]}"
  local out_root="${BATCH_ROOT}/${project_id}"
  local log_file="${BATCH_ROOT}/logs/${project_id}.log"
  local run_id="unified-live-${project_id}-20260907"
  local started_at ended_at status

  started_at="$(date --iso-8601=seconds)"
  printf 'run_start project=%s time=%s frozen=%s out=%s\n' "${project_id}" "${started_at}" "${frozen_root}" "${out_root}" >>"${LAUNCHER_LOG}"

  if [[ ! -d "${frozen_root}" ]]; then
    status=2
    printf 'frozen root missing: %s\n' "${frozen_root}" >"${log_file}"
    write_project_terminal "${out_root}" "${project_id}" "${run_id}" \
      "input" "frozen_root_missing" "${status}"
  elif [[ ! -d "${repo}" ]]; then
    status=2
    printf 'repository missing: %s\n' "${repo}" >"${log_file}"
    write_project_terminal "${out_root}" "${project_id}" "${run_id}" \
      "input" "repository_missing" "${status}"
  else
    mkdir -p "${out_root}"
    write_project_manifest "${out_root}" "${project_id}" "${run_id}" \
      "${frozen_root}" "${repo}"
    env -u AIHUBMIX_BASE_URL -u CODE2PAPER_LLM_CAPABILITY_PROFILE \
      CODE2PAPER_AUTHORING_CONTEXT_MODE=unified \
      python -u "${REPO_ROOT}/scripts/run_authoring_replay.py" \
      "${frozen_root}" "${out_root}" \
      --repo "${repo}" \
      --run-id "${run_id}" \
      --authoring-context-mode unified \
      --rebuild-authoring \
      --persist-authoring-rebuild-manifest \
      --profile "${PROFILE}" \
      --force-profile \
      --callback-rounds "${CALLBACK_ROUNDS}" \
      --callback-tool-turns "${CALLBACK_TOOL_TURNS}" \
      >"${log_file}" 2>&1
    status=$?
  fi

  ended_at="$(date --iso-8601=seconds)"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$((index + 1))" "${project_id}" "$([[ ${status} -eq 0 ]] && echo success || echo failed)" \
    "${status}" "${started_at}" "${ended_at}" "${out_root}" "${log_file}" >>"${STATUS_FILE}"
  printf 'run_end project=%s time=%s exit=%s\n' "${project_id}" "${ended_at}" "${status}" >>"${LAUNCHER_LOG}"
}

for index in "${!PROJECT_IDS[@]}"; do
  run_one "${index}"
done

printf 'batch_end=%s\n' "$(date --iso-8601=seconds)" >>"${LAUNCHER_LOG}"
write_batch_terminal "complete" "batch_finished" 0
