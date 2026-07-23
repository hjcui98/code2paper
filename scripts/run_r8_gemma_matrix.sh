#!/usr/bin/env bash
# Run the current-protocol Gemma R8 acceptance matrix strictly serially.
#
# Usage:
#   bash scripts/run_r8_gemma_matrix.sh --background
#   CODE2PAPER_R8_PROJECTS=rap,lookahead bash scripts/run_r8_gemma_matrix.sh --background
#
# The script never starts vLLM.  It checks the already-running local API,
# records its response and GPU-process snapshot, then calls that API through
# the normal Code2Paper CLI.  Each project has an isolated output directory,
# stdout/stderr log, and post-run R8 scanner report.

set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PROFILE_PATH="${CODE2PAPER_R8_PROFILE:-${REPO_ROOT}/tests/live/profiles/gemma4_mtp_vllm.example.env}"
RUN_STAMP="${CODE2PAPER_R8_MATRIX_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
LOG_ROOT="${CODE2PAPER_R8_LOG_ROOT:-${REPO_ROOT}/logs/r8_gemma_${RUN_STAMP}}"
OUT_ROOT="${CODE2PAPER_R8_OUT_ROOT:-/tmp/code2paper-r8-matrix-${RUN_STAMP}}"
PROJECTS="${CODE2PAPER_R8_PROJECTS:-rap,ebcar,dyg,linearrag,lookahead,bootstrapping}"
MODE="${1:---foreground}"

if [[ "${MODE}" == "--background" ]]; then
  mkdir -p "${LOG_ROOT}"
  nohup setsid env \
    CODE2PAPER_R8_MATRIX_ID="${RUN_STAMP}" \
    CODE2PAPER_R8_LOG_ROOT="${LOG_ROOT}" \
    CODE2PAPER_R8_OUT_ROOT="${OUT_ROOT}" \
    CODE2PAPER_R8_PROJECTS="${PROJECTS}" \
    bash "${BASH_SOURCE[0]}" --foreground \
    >"${LOG_ROOT}/driver.log" 2>&1 &
  printf '%s\n' "$!" > "${LOG_ROOT}/driver.pid"
  # Wait up to 30 seconds for the foreground process to signal
  # readiness by writing status.env.  setsid(1) forks so the PID
  # captured by $! is not the long-lived process; therefore we
  # poll for the readiness marker instead of kill -0.
  waited=0
  while [[ "${waited}" -lt 30 ]]; do
    if [[ -f "${LOG_ROOT}/status.env" ]]; then
      printf 'started background matrix log_root=%s out_root=%s\n' \
        "${LOG_ROOT}" "${OUT_ROOT}"
      exit 0
    fi
    sleep 2
    waited=$((waited + 2))
  done
  printf 'background matrix failed to start within 30s; inspect %s/driver.log\n' "${LOG_ROOT}" >&2
  exit 1
fi

if [[ "${MODE}" != "--foreground" ]]; then
  echo "usage: $0 [--foreground|--background]" >&2
  exit 2
fi

mkdir -p "${LOG_ROOT}" "${OUT_ROOT}"
printf 'state=RUNNING\nstarted_at=%s\n' "$(date -u +%FT%TZ)" > "${LOG_ROOT}/status.env"
finish_matrix() {
  local exit_code=$?
  local state="COMPLETED"
  if [[ "${exit_code}" -ne 0 ]]; then
    state="FAILED"
  fi
  printf 'state=%s\nfinished_at=%s\nexit_code=%s\n' \
    "${state}" "$(date -u +%FT%TZ)" "${exit_code}" > "${LOG_ROOT}/status.env"
  exit "${exit_code}"
}
trap finish_matrix EXIT
exec 9>/tmp/code2paper-r8-gemma-matrix.lock
if ! flock -n 9; then
  echo "another R8 matrix is already active; exiting" >&2
  exit 3
fi

log() {
  printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "${LOG_ROOT}/matrix.log"
}

record_env() {
  local name
  : > "${LOG_ROOT}/protocol.env"
  for name in \
    CODE2PAPER_LLM_PROVIDER CODE2PAPER_LLM_MODEL CODE2PAPER_OPENAI_BASE_URL \
    CODE2PAPER_LLM_CACHE CODE2PAPER_LLM_TEMPERATURE CODE2PAPER_LLM_MAX_OUTPUT_TOKENS \
    CODE2PAPER_TP_SIZE CODE2PAPER_NUM_GPUS CODE2PAPER_PARALLEL_PROJECTS \
    CODE2PAPER_AGENTIC_RESEARCH_V3 CODE2PAPER_R8_ACCEPTANCE \
    CODE2PAPER_PAPER_READ_ONLY_AT_END CODE2PAPER_LIVE_PROFILE \
    CODE2PAPER_LLM_TEMPERATURE_INTENT_COMPILER \
    CODE2PAPER_LLM_TEMPERATURE_CODE_INTAKE \
    CODE2PAPER_LLM_TEMPERATURE_CODE_ANALYZER \
    CODE2PAPER_LLM_TEMPERATURE_RESEARCH_SUPERVISOR \
    CODE2PAPER_LLM_TEMPERATURE_AUTHORING_PLANNER \
    CODE2PAPER_LLM_TEMPERATURE_METHOD_WRITER \
    CODE2PAPER_LLM_TEMPERATURE_LOCAL_REWRITE \
    CODE2PAPER_LLM_TEMPERATURE_SEMANTIC_VERIFIER \
    CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_INTENT_COMPILER \
    CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_CODE_INTAKE \
    CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_CODE_ANALYZER \
    CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_RESEARCH_SUPERVISOR \
    CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_AUTHORING_PLANNER \
    CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_METHOD_WRITER \
    CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_METHOD_WRITER_EXTENDED \
    CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_LOCAL_REWRITE \
    CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_SEMANTIC_VERIFIER; do
    printf '%s=%q\n' "${name}" "${!name-}" >> "${LOG_ROOT}/protocol.env"
  done
}

wait_for_existing_agentic_run() {
  local pids
  while true; do
    # Only match actual Python processes running the CLI, not the
    # pgrep/sandbox wrapper whose command line also contains the
    # search string.
    pids="$(pgrep -f 'python -m code2paper\.cli\.agentic_run' | while read -r pid; do
      cmd="$(ps -o comm= -p "${pid}" 2>/dev/null || true)"
      case "${cmd}" in
        python|python3|*/python|*/python3) echo "${pid}" ;;
      esac
    done || true)"
    if [[ -z "${pids}" ]]; then
      return 0
    fi
    log "waiting for existing serialized agentic run(s): ${pids}"
    sleep 60
  done
}

run_r8_recheck() {
  local project="$1"
  local project_root="$2"
  local resumed_root="${3:-}"
  local log_file="${LOG_ROOT}/${project}.r8_recheck.log"
  local recheck_tsv="${LOG_ROOT}/${project}.r8_recheck.tsv"
  local exit_code
  PROJECT_RUN_ROOT="${project_root}" \
  RESUMED_RUN_ROOT="${resumed_root}" \
  PYTHONPATH="${REPO_ROOT}/src" python - <<'PY' >"${log_file}" 2>&1
import json
import os
from pathlib import Path

from code2paper.agentic.r8_acceptance import (
    check_r8_acceptance_from_run_dir,
    write_r8_acceptance_report,
)

run_root = Path(os.environ["PROJECT_RUN_ROOT"])
resumed = os.environ.get("RESUMED_RUN_ROOT", "").strip()
resumed_dir = Path(resumed) if resumed else None
report = check_r8_acceptance_from_run_dir(run_root, resumed_run_dir=resumed_dir)
output = run_root / "artifacts" / "10_run" / "r8_acceptance_report_rechecked.json"
output.parent.mkdir(parents=True, exist_ok=True)
write_r8_acceptance_report(output, report)
print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
PY
  exit_code=$?
  # Extract key fields directly from the written rechecked JSON file.
  # Do NOT parse the pretty-printed log (the compact-string rfind approach
  # breaks on indent=2 output).  The report was written to:
  #   <project_root>/artifacts/10_run/r8_acceptance_report_rechecked.json
  local recheck_json="${project_root}/artifacts/10_run/r8_acceptance_report_rechecked.json"
  if [[ -f "${recheck_json}" ]]; then
    python3 -c "
import json, sys
try:
    with open('${recheck_json}') as f:
        data = json.load(f)
    accepted = data.get('accepted', False)
    protocol_ok = data.get('protocol_check_passed', False)
    criteria = data.get('criteria', {})
    completion = criteria.get('completion_complete', {}).get('status', 'unknown')
    readiness = criteria.get('readiness_passed', {}).get('status', 'unknown')
    print(f'{accepted}\t{protocol_ok}\t{completion}\t{readiness}')
except Exception as e:
    print(f'False\tFalse\terror\terror')
" > "${recheck_tsv}" 2>/dev/null || {
      printf 'False\tFalse\terror\terror\n' > "${recheck_tsv}"
    }
  else
    printf 'False\tFalse\terror\terror\n' > "${recheck_tsv}"
  fi
  return ${exit_code}
}

run_project() {
  local name="$1"
  local project_root="$2"
  local author_path="$3"
  local project_id="$4"
  local run_root="${OUT_ROOT}/${name}"
  local run_id="${RUN_STAMP}-${name}"
  local checkpoint_db="${run_root}/checkpoint.db"
  local log_file="${LOG_ROOT}/${name}.cli.log"
  local resume_log_file="${LOG_ROOT}/${name}.cli.resume.log"
  local start_epoch end_epoch exit_code resume_exit_code

  start_epoch="$(date +%s)"
  log "project=${name} start run_id=${run_id}"
  PYTHONPATH="${REPO_ROOT}/src" python -m code2paper.cli.agentic_run \
    "${project_root}" \
    --author "${author_path}" \
    --out-root "${run_root}" \
    --project-id "${project_id}" \
    --llm-provider openai \
    --llm-model gemma4-31b-nvfp4 \
    --run-id "${run_id}" \
    --checkpoint-backend sqlite \
    --checkpoint-db "${checkpoint_db}" \
    --max-retrieval-rounds 1 \
    --max-evidence-revision-rounds 1 \
    --max-authoring-revision-rounds 2 \
    --max-semantic-verifier-calls 32 \
    >"${log_file}" 2>&1
  exit_code=$?
  end_epoch="$(date +%s)"

  # Checkpoint resume run (no LLM calls — replays the persisted state).
  # This exercises the ``checkpoint_resume_consistent`` R8 criterion so
  # it is ``passed`` rather than ``skipped``.  The resume run writes to
  # the SAME directory as the original because the checkpoint's
  # out_root overrides the CLI --out-root.  The summary's
  # ``resumed_from_final_state_digest`` field carries the original
  # digest so the R8 checker can verify consistency.
  if [[ -f "${checkpoint_db}" ]]; then
    log "project=${name} resume start"
    PYTHONPATH="${REPO_ROOT}/src" python -m code2paper.cli.agentic_run \
      "${project_root}" \
      --author "${author_path}" \
      --out-root "${run_root}" \
      --project-id "${project_id}" \
      --llm-provider openai \
      --llm-model gemma4-31b-nvfp4 \
      --run-id "${run_id}" \
      --checkpoint-backend sqlite \
      --checkpoint-db "${checkpoint_db}" \
      --resume \
      --max-retrieval-rounds 1 \
      --max-evidence-revision-rounds 1 \
      --max-authoring-revision-rounds 2 \
      --max-semantic-verifier-calls 32 \
      >"${resume_log_file}" 2>&1
    resume_exit_code=$?
    log "project=${name} resume finished exit_code=${resume_exit_code}"
  else
    log "project=${name} resume skipped: no checkpoint.db"
  fi

  # Pass empty resumed_root: the R8 checker uses the summary's
  # resumed_from_final_state_digest field when no separate dir is given.
  run_r8_recheck "${name}" "${run_root}" ""
  local recheck_exit_code=$?
  local recheck_accepted="unknown"
  local recheck_protocol="unknown"
  local recheck_completion="unknown"
  local recheck_readiness="unknown"
  local recheck_tsv="${LOG_ROOT}/${name}.r8_recheck.tsv"
  if [[ -f "${recheck_tsv}" ]]; then
    IFS=$'\t' read -r recheck_accepted recheck_protocol recheck_completion recheck_readiness < "${recheck_tsv}"
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${name}" "${run_id}" "${exit_code}" "${recheck_exit_code}" \
    "${recheck_accepted}" "${recheck_protocol}" \
    "${recheck_completion}" "${recheck_readiness}" \
    "$((end_epoch - start_epoch))" "${run_root}" \
    >> "${LOG_ROOT}/project_status.tsv"
  log "project=${name} finished exit_code=${exit_code} recheck_exit=${recheck_exit_code} accepted=${recheck_accepted} elapsed_seconds=$((end_epoch - start_epoch))"
  if [[ "${exit_code}" -ne 0 ]] || [[ "${recheck_exit_code}" -ne 0 ]] || [[ "${recheck_accepted}" != "True" ]] || [[ "${recheck_protocol}" != "True" ]]; then
    return 1
  fi
  return 0
}

run_static_tests() {
  local start_epoch end_epoch exit_code
  local -a clean_test_env
  clean_test_env=(
    -u OPENAI_API_KEY
    -u CODE2PAPER_LLM_PROVIDER
    -u CODE2PAPER_OPENAI_BASE_URL
    -u CODE2PAPER_LLM_MODEL
    -u CODE2PAPER_DEFAULT_LLM_MODEL
    -u CODE2PAPER_LLM_CACHE
    -u CODE2PAPER_LLM_TEMPERATURE
    -u CODE2PAPER_LLM_MAX_OUTPUT_TOKENS
    -u CODE2PAPER_AGENTIC_RESEARCH_V3
    -u CODE2PAPER_R8_ACCEPTANCE
    -u CODE2PAPER_TP_SIZE
    -u CODE2PAPER_NUM_GPUS
    -u CODE2PAPER_PARALLEL_PROJECTS
    -u CODE2PAPER_PAPER_READ_ONLY_AT_END
    -u CODE2PAPER_LIVE_PROFILE
    -u CODE2PAPER_EXPECT_INFERENCE_MODE
    -u CODE2PAPER_EXPECT_DEVICE_IDS
    -u CODE2PAPER_EXPECT_TP_SIZE
    -u CODE2PAPER_EXPECT_NUM_SPECULATIVE_TOKENS
    -u CODE2PAPER_EXPECT_DRAFT_TP_SIZE
    -u CODE2PAPER_EXPECT_MTP_ASSISTANT
    -u CODE2PAPER_LLM_TIMEOUT_SECONDS
    -u CODE2PAPER_LLM_RETRY_MAX_ATTEMPTS
    -u CODE2PAPER_RUN_LIVE_LLM
    -u CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_METHOD_WRITER_EXTENDED
  )
  local role
  for role in INTENT_COMPILER CODE_INTAKE CODE_ANALYZER RESEARCH_SUPERVISOR AUTHORING_PLANNER METHOD_WRITER LOCAL_REWRITE SEMANTIC_VERIFIER; do
    clean_test_env+=(
      -u "CODE2PAPER_LLM_TEMPERATURE_${role}"
      -u "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_${role}"
      -u "CODE2PAPER_LLM_TOP_P_${role}"
      -u "CODE2PAPER_LLM_TOP_K_${role}"
    )
  done
  start_epoch="$(date +%s)"
  log "static pytest start"
  env "${clean_test_env[@]}" PYTHONPATH="${REPO_ROOT}/src" pytest -q > "${LOG_ROOT}/pytest.log" 2>&1
  exit_code=$?
  end_epoch="$(date +%s)"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "static_pytest" "${RUN_STAMP}" "${exit_code}" "0" "N/A" "N/A" "N/A" "N/A" "$((end_epoch - start_epoch))" "${LOG_ROOT}/pytest.log" \
    >> "${LOG_ROOT}/project_status.tsv"
  log "static pytest finished exit_code=${exit_code} elapsed_seconds=$((end_epoch - start_epoch))"
  return "${exit_code}"
}

if [[ ! -f "${PROFILE_PATH}" ]]; then
  log "missing profile: ${PROFILE_PATH}"
  exit 4
fi

set -a
. "${PROFILE_PATH}"
set +a
export CODE2PAPER_AGENTIC_RESEARCH_V3=1
export CODE2PAPER_R8_ACCEPTANCE=1
export CODE2PAPER_TP_SIZE=2
export CODE2PAPER_NUM_GPUS=2
export CODE2PAPER_PARALLEL_PROJECTS=1
export CODE2PAPER_PAPER_READ_ONLY_AT_END=1
record_env

curl --fail --silent --show-error \
  "${CODE2PAPER_OPENAI_BASE_URL%/}/models" \
  > "${LOG_ROOT}/gemma_models.json"
nvidia-smi --query-gpu=index,name,uuid,memory.total,memory.used \
  --format=csv,noheader > "${LOG_ROOT}/gpu_before.csv" || true

printf 'project\trun_id\tcli_exit_code\trecheck_exit_code\taccepted\tprotocol_check_passed\tcompletion\treadiness\telapsed_seconds\trun_root\n' \
  > "${LOG_ROOT}/project_status.tsv"
log "matrix start projects=${PROJECTS}"
if ! run_static_tests; then
  log "matrix stopped: static pytest failed; see ${LOG_ROOT}/pytest.log"
  exit 5
fi
wait_for_existing_agentic_run

IFS=',' read -r -a selected_projects <<< "${PROJECTS}"
matrix_failures=0
for name in "${selected_projects[@]}"; do
  case "${name}" in
    rap)
      run_project "rap" \
        "/data1/users/cuihengjia/code2paper/code_final/RAP - Fast Feedforward Rendering-Free Attribute-Guided Primitive Importance Score Prediction for Efficient 3D Gaussian Splatting Processing" \
        "/data1/users/cuihengjia/code2paper/paperyaml/RAP - Fast Feedforward Rendering-Free Attribute-Guided Primitive Importance Score Prediction for Efficient 3D Gaussian Splatting Processing.yaml" \
        "rap_current_protocol" || matrix_failures=$((matrix_failures + 1))
      ;;
    ebcar)
      run_project "ebcar" \
        "/data1/users/cuihengjia/code2paper/code_final/EBCAR - Embedding-Based Context-Aware Reranker" \
        "/data1/users/cuihengjia/code2paper/paperyaml3/EBCAR - Embedding-Based Context-Aware Reranker.yaml" \
        "ebcar_current_protocol" || matrix_failures=$((matrix_failures + 1))
      ;;
    dyg)
      run_project "dyg" \
        "/data1/users/cuihengjia/code2paper/code_final/DyG-Mamba_ Continuous State Space Modeling on Dynamic Graphs" \
        "/data1/users/cuihengjia/code2paper/paperyaml4/DyG-Mamba_ Continuous State Space Modeling on Dynamic Graphs.yaml" \
        "dyg_current_protocol" || matrix_failures=$((matrix_failures + 1))
      ;;
    linearrag)
      run_project "linearrag" \
        "/data1/users/cuihengjia/code2paper/code_final/LinearRAG - Linear Graph Retrieval-Augmented Generation on Large-scale Corpora" \
        "/data1/users/cuihengjia/code2paper/paperyaml3/LinearRAG - Linear Graph Retrieval-Augmented Generation on Large-scale Corpora.yaml" \
        "linearrag_current_protocol" || matrix_failures=$((matrix_failures + 1))
      ;;
    lookahead)
      run_project "lookahead" \
        "/data1/users/cuihengjia/code2paper/code_final/Scaling Speculative Decoding with Lookahead Reasoning" \
        "/data1/users/cuihengjia/code2paper/paperyaml4/Scaling Speculative Decoding with Lookahead Reasoning.yaml" \
        "lookahead_current_protocol" || matrix_failures=$((matrix_failures + 1))
      ;;
    bootstrapping)
      run_project "bootstrapping" \
        "/data1/users/cuihengjia/code2paper/code_final/Bootstrapping Multi-view Learning for Test-time Noisy Correspondence" \
        "/data1/users/cuihengjia/code2paper/paperyaml/Bootstrapping Multi-view Learning for Test-time Noisy Correspondence.yaml" \
        "bootstrapping_current_protocol" || matrix_failures=$((matrix_failures + 1))
      ;;
    "")
      ;;
    *)
      log "unknown project key=${name}; failing"
      matrix_failures=$((matrix_failures + 1))
      ;;
  esac
done

nvidia-smi --query-gpu=index,name,uuid,memory.total,memory.used \
  --format=csv,noheader > "${LOG_ROOT}/gpu_after.csv" || true

# ---------------------------------------------------------------------------
# Final post-checks: verify the matrix produced a complete, valid result.
# ---------------------------------------------------------------------------
post_check_failures=0

# 1. Static pytest must have completed (row exists with exit_code 0).
pytest_exit="$(awk -F'\t' '$1=="static_pytest"{print $3}' "${LOG_ROOT}/project_status.tsv")"
if [[ "${pytest_exit}" != "0" ]]; then
  log "post_check FAILED: static pytest did not complete cleanly (exit=${pytest_exit:-missing})"
  post_check_failures=$((post_check_failures + 1))
fi

# 2. Actual project row count must equal the number of requested projects
#    (excluding the static_pytest row and empty names).
requested_count=0
for n in "${selected_projects[@]}"; do
  [[ -n "${n}" ]] && requested_count=$((requested_count + 1))
done
project_row_count="$(awk -F'\t' 'NR>1 && $1!="static_pytest" && NF>0{c++} END{print c+0}' "${LOG_ROOT}/project_status.tsv")"
if [[ "${project_row_count}" -ne "${requested_count}" ]]; then
  log "post_check FAILED: expected ${requested_count} project rows, got ${project_row_count}"
  post_check_failures=$((post_check_failures + 1))
fi

# 3. Each project row: cli_exit_code=0, recheck_exit_code=0,
#    accepted=True, protocol_check_passed=True,
#    completion=passed, readiness=passed.
while IFS=$'\t' read -r p_name p_runid p_cli p_recheck p_accepted p_protocol p_completion p_readiness p_elapsed p_root; do
  [[ "${p_name}" == "project" || "${p_name}" == "static_pytest" || -z "${p_name}" ]] && continue
  row_err=0
  [[ "${p_cli}" != "0" ]] && { log "post_check FAILED: ${p_name} cli_exit_code=${p_cli}"; row_err=1; }
  [[ "${p_recheck}" != "0" ]] && { log "post_check FAILED: ${p_name} recheck_exit_code=${p_recheck}"; row_err=1; }
  [[ "${p_accepted}" != "True" ]] && { log "post_check FAILED: ${p_name} accepted=${p_accepted}"; row_err=1; }
  [[ "${p_protocol}" != "True" ]] && { log "post_check FAILED: ${p_name} protocol=${p_protocol}"; row_err=1; }
  [[ "${p_completion}" != "passed" ]] && { log "post_check FAILED: ${p_name} completion=${p_completion}"; row_err=1; }
  [[ "${p_readiness}" != "passed" ]] && { log "post_check FAILED: ${p_name} readiness=${p_readiness}"; row_err=1; }
  [[ "${row_err}" -ne 0 ]] && post_check_failures=$((post_check_failures + 1))
done < "${LOG_ROOT}/project_status.tsv"

log "matrix finished; failures=${matrix_failures}; post_check_failures=${post_check_failures}; inspect ${LOG_ROOT}/project_status.tsv and per-project *.r8_recheck.log"
if [[ "${matrix_failures}" -gt 0 ]] || [[ "${post_check_failures}" -gt 0 ]]; then
  exit 1
fi
