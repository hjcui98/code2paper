#!/usr/bin/env python3
"""Replay the authoring/validation surface on frozen research artifacts.

Plan 16.3.1/16.3.2: reuse frozen research evidence (snapshot + digest
checks enforced by the writer's own gates), regenerate Writer/Editor/
Rewrite, candidate, verified and validation artifacts in a fresh root.
The read-only summarizer is ``scripts/run_agentic_product_probe.py
--summarize-only``.

R3/R4 contract:
- a persisted callback bundle is only a list of digest-pinned refs; every
  referenced file is copied into the fresh root (traversal-safe), its
  digest revalidated, and its relative reference rebased.  Reuse is
  reported distinctly (``reused_fulfilled_callback_ids``) from a new
  resume event (``writer_resumed_section_ids``).  Any missing, escaping,
  symlinked, or digest-mismatched artifact fails the replay closed.
- every replay writes ``execution_record.json`` (exact command, exit code,
  code-state digest, pre/post runtime ledger keys) next to the fresh root.
- the shared product-authoring overlay is persisted as
  ``artifacts/06_authoring/product_authoring_state_v1.json`` and its digest is
  included in replay telemetry.

WP0 (2026-08-20): clean replays copy only research/author authority and
rebuild derived authoring when ``--rebuild-authoring`` is set.  Old plan,
concept cards, and callbacks are not silently copied unless explicitly
requested via ``--reuse-authoring-callbacks``.

Usage: run_authoring_replay.py <frozen-root> <fresh-root> [--resume MA-S2]
       [--repo <repo-path>] [--callback-rounds N] [--callback-tool-turns N]
       [--profile <env-file>] [--force-profile]
       [--authoring-stage {full,prepare,execute-prepared}]
       [--rebuild-authoring] [--reuse-authoring-callbacks]
       [--persist-authoring-rebuild-manifest] [--deterministic-preflight-only]

When ``--repo`` is given and the replay exposes an open authoring issue, local
callbacks are fulfilled through the Research LangGraph.  A persisted
``research_stage_checkpoint_v1.json`` restores the original thread; otherwise
the replay records a ``ResearchContinuationSeedV1`` reconstructed from frozen
authority and starts a new, explicitly scoped continuation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import sys
from urllib.error import HTTPError, URLError
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
_SCRIPTS = _ROOT / "scripts"
for _entry in (_SRC, _SCRIPTS):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

# Research / author authority copied by default (WP0 copy boundary).
RESEARCH_COPY_ARTIFACTS = (
    "intent_obligation_graph_v2",
    "research_agenda_v1",
    "method_evidence",
    "claim_evidence_map",
    "obligation_coverage_v2",
    "reference_method_agenda_v1",
    "method_completeness_matrix_v1",
    "equation_claims_v1",
    "configuration_claims_v1",
    "evidence_packets_v3",
    "code_facts_v1",
    "atomic_claims_v3",
)

# Derived authoring artifacts: never copied unless legacy compatibility is
# explicitly requested (tests guard this list).
DERIVED_AUTHORING_ARTIFACTS = (
    "authoring_projection_v1",
    "method_section_plan_v2",
    "method_argument_briefs_v1",
    "method_concept_cards_v1",
    "method_propositions_v1",
    "method_proposition_bindings_v1",
    "method_proposition_clusters_v1",
    "writing_research_callback_artifacts_v1",
    "method_argument_facets_v1",
    "facet_evidence_alignments_v1",
    "candidate_facet_policies_v1",
    "publication_field_candidates_v1",
    "typed_field_deferred_v1",
    "method_argument_facet_alignment_trace_v1",
    "publication_paragraph_transaction_assessments_v1",
    "authoring_structural_exit_v1",
)

# Back-compat alias used by focused tests.
FROZEN_ARTIFACTS = RESEARCH_COPY_ARTIFACTS

OPTIONAL_RESEARCH_ARTIFACTS = (
    "behavior_graph_v1",
    "research_stage_checkpoint_v1",
    "repo_snapshot_v2",
    "repository_source_manifest_v1",
    "symbol_index_v2",
    "implementation_scope_v1",
    "repository_authoring_artifacts_v1",
    # Candidate-lane Research authority.  The production Writer rebuilds
    # Candidate eligibility from these frozen artifacts (agenda + promotion
    # ledger + retry ledger + handoff); without them in the fresh root its
    # preadmission falls back to the strict terminal proof and blocks a run
    # whose authenticated Candidate handoff was already accepted.  They stay
    # optional here because the Writer itself revalidates them: a frozen root
    # that has none keeps the previous, stricter behaviour.
    "candidate_handoff_v1",
    "observation_promotion_ledger_v1",
    "candidate_retry_ledger_v1",
    "research_revision_journal_v1",
)

OPTIONAL_FROZEN_ARTIFACTS = OPTIONAL_RESEARCH_ARTIFACTS

# A prepared authoring root carries this exact frozen Formalizer phase.  The
# phase is deliberately copied as a separate closure: execute-prepared must
# never regenerate it merely because an older replay layout placed files in a
# different artifact directory.
FORMALIZER_PHASE_COPY_ARTIFACTS = (
    "unified_context_archive_v2",
    "consumer_workset_manifest_v2",
    "run_invocation_budget_envelope_v1",
    "consumer_invocation_plan_v1.1",
    "formalizer_plan_execution_v2",
    "mechanism_formula_obligations_v1",
    "mechanism_formula_packages_v2",
    "unified_live_admission_v1.formalizer.1",
    "mechanism_context_set_v1",
    "mechanism_evidence_closures_v1",
    "mechanism_context_page_manifest_v1",
)

RESEARCH_STAGE_CHECKPOINT_CANDIDATES = (
    "artifacts/research_product/research_stage_checkpoint_v1.json",
    "artifacts/research_stage_checkpoint_v1.json",
)


_METHOD_UNIT_FREEZE_ARTIFACTS = (
    "method_section_plan_v2",
    "method_argument_briefs_v1",
    "method_argument_facets_v1",
    "facet_evidence_alignments_v1",
    "candidate_facet_policies_v1",
)


def _persist_reused_method_unit_surface(fresh: Path) -> None:
    """Write the Writer-loaded MethodUnit freeze into ``06_authoring``.

    ``--reuse-derived-authoring`` copies plans into ``artifacts/*.json``.
    The Writer rehashes ``MethodSectionPlanV2`` on load, and Architect or
    callback persist write a second copy under ``06_authoring``.  Persist
    the loaded (rehashed) plan bytes in both places so assessment and Writer
    digests match, and mirror the frozen briefs/facets beside it.
    """

    artifacts = fresh / "artifacts"
    authoring = artifacts / "06_authoring"
    authoring.mkdir(parents=True, exist_ok=True)
    plan_path = artifacts / "method_section_plan_v2.json"
    authoring_plan = authoring / "method_section_plan_v2.json"
    if plan_path.is_file():
        try:
            from code2paper.agentic.method_argument_models import MethodSectionPlanV2

            plan = MethodSectionPlanV2.model_validate_json(
                plan_path.read_text(encoding="utf-8")
            )
            loaded = plan.model_dump_json(indent=2) + "\n"
            plan_path.write_text(loaded, encoding="utf-8")
            authoring_plan.write_text(loaded, encoding="utf-8")
        except (OSError, TypeError, ValueError):
            shutil.copy2(plan_path, authoring_plan)
    for name in _METHOD_UNIT_FREEZE_ARTIFACTS:
        if name == "method_section_plan_v2":
            continue
        source = artifacts / f"{name}.json"
        if source.is_file():
            shutil.copy2(source, authoring / f"{name}.json")


def _build_replay_auxiliary_budget_envelope(
    *,
    llm_config: Any,
    run_digest: str,
) -> Any | None:
    """Build the opt-in envelope for non-page authoring calls.

    The normal qwen38 profile declares only the four page roles, so this
    returns ``None`` and replay uses the deterministic authoring fallbacks.
    An auxiliary role is enabled only when its complete budget declaration is
    present in the same profile; the caller wrapper then applies the same
    envelope to planner, verifier and proposal requests.
    """

    from code2paper.agentic.unified_context_compiler import (
        build_run_invocation_budget_envelope_v1,
        read_unified_budget_profile,
        read_unified_extra_roles,
        declared_extra_roles,
    )
    from code2paper.agentic.unified_context_models import sha256_digest
    from code2paper.agentic.mechanism_context_models import canonical_json_bytes

    profile_budget = read_unified_budget_profile(os.environ)
    profile_budget.update(read_unified_extra_roles(os.environ))
    if not declared_extra_roles(profile_budget):
        return None
    context_tokens = 0
    try:
        context_tokens = int(
            os.environ.get("CODE2PAPER_MODEL_CONTEXT_TOKENS", "") or 0
        )
    except ValueError:
        context_tokens = 0
    if context_tokens <= 0:
        from code2paper.llm.capabilities import load_capability_profile

        capability = load_capability_profile(
            provider=getattr(llm_config.provider, "value", str(llm_config.provider)),
            model=str(getattr(llm_config, "model", "") or ""),
        )
        context_tokens = int(getattr(capability, "max_model_len", 0) or 0)
    if context_tokens <= 0:
        return None
    profile_digest = sha256_digest(canonical_json_bytes(profile_budget))
    model_digest = sha256_digest(
        str(getattr(llm_config, "model", "unknown") or "unknown").encode("utf-8")
    )
    return build_run_invocation_budget_envelope_v1(
        profile_budget=profile_budget,
        model_capabilities={"context_tokens": context_tokens},
        run_digest=str(run_digest),
        profile_digest=profile_digest,
        model_identity_digest=model_digest,
    )


def _digest_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _digest_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _capture_authoring_transaction_snapshot(fresh: Path) -> dict[str, bytes]:
    """Capture the direct publication files before a callback resume.

    A callback may create new Research evidence, but its resumed Writer view
    is still one paragraph transaction.  The publication/checkpoint files
    therefore need an incumbent snapshot so a regressing resume can be
    rejected atomically.  Nested immutable stores are intentionally excluded:
    the restored direct checkpoints continue to authenticate their original
    immutable refs, while the Research continuation trace remains available
    for diagnosis.
    """

    snapshot: dict[str, bytes] = {}
    for dirname in ("06_authoring", "07_validation"):
        base = fresh / "artifacts" / dirname
        if not base.is_dir():
            continue
        for path in base.iterdir():
            if not path.is_file():
                continue
            try:
                snapshot[str(path.relative_to(fresh))] = path.read_bytes()
            except OSError:
                continue
    return snapshot


def _restore_authoring_transaction_snapshot(
    fresh: Path,
    snapshot: Mapping[str, bytes],
) -> None:
    """Restore the direct publication files captured before a resume.

    Restore is atomic with respect to the captured file set: files created
    after the snapshot (for example a callback-reminted MethodUnit plan)
    are deleted, then snapshot bytes are written back.  Leaving post-snapshot
    files in place would mix a 6-unit plan with 7-unit assessments.
    """

    snapshot_paths = set(snapshot)
    for dirname in ("06_authoring", "07_validation"):
        base = fresh / "artifacts" / dirname
        if not base.is_dir():
            continue
        for path in list(base.iterdir()):
            if not path.is_file():
                continue
            relative = str(path.relative_to(fresh))
            if relative in snapshot_paths:
                continue
            try:
                path.unlink()
            except OSError:
                continue
    for relative, content in snapshot.items():
        path = fresh / relative
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        except OSError:
            # The caller will keep the callback failure visible; a partial
            # restore must not turn the original failure into a false pass.
            continue


def _structural_quality_vector(payload: Mapping[str, Any] | None) -> dict[str, int]:
    """Return the paragraph transaction dimensions used for callback commits."""

    payload = payload if isinstance(payload, Mapping) else {}
    keys = (
        "required_paragraphs", "valid_required_paragraphs", "invalid_paragraphs",
        "required_targets", "valid_targets", "required_slots", "witnessed_slots",
        "required_edges", "witnessed_edges", "accepted_formula_packages",
        "consumed_formula_packages", "blocked_representation", "invalid_witnesses",
    )
    return {key: int(payload.get(key) or 0) for key in keys}


def _callback_transaction_decision(
    incumbent: Mapping[str, Any] | None,
    candidate: Mapping[str, Any] | None,
) -> tuple[bool, str]:
    """Decide whether a resumed callback view may replace its incumbent.

    The decision is intentionally based on the same structural receipt used
    by acceptance.  Denominators may change after a scoped Research recompile,
    so target/slot/edge/formula comparisons use coverage cross-products, not
    raw counts alone.  A no-gain resume is rejected as well as a regression:
    evidence can remain in Research history without replacing usable prose.
    """

    before = _structural_quality_vector(incumbent)
    after = _structural_quality_vector(candidate)
    ratios = (
        ("targets", "valid_targets", "required_targets"),
        ("slots", "witnessed_slots", "required_slots"),
        ("edges", "witnessed_edges", "required_edges"),
        ("formulas", "consumed_formula_packages", "accepted_formula_packages"),
    )
    improvements: list[str] = []
    for label, numerator, denominator in ratios:
        before_den = before[denominator]
        after_den = after[denominator]
        before_num = before[numerator]
        after_num = after[numerator]
        if before_den and not after_den:
            return False, f"{label}_coverage_regressed:{before_num}/{before_den}->0/0"
        if before_den and after_den:
            before_product = before_num * after_den
            after_product = after_num * before_den
            if after_product < before_product:
                return False, (
                    f"{label}_coverage_regressed:{before_num}/{before_den}->"
                    f"{after_num}/{after_den}"
                )
            if after_product > before_product:
                improvements.append(f"{label}_coverage_gain")
        elif after_den and not before_den:
            if after_num:
                improvements.append(f"{label}_coverage_gain")

    lower_is_better = (
        ("invalid_paragraphs", "invalid_paragraphs_increased"),
        ("blocked_representation", "blocked_representation_increased"),
        ("invalid_witnesses", "invalid_witnesses_increased"),
    )
    for field, reason in lower_is_better:
        if after[field] > before[field]:
            return False, f"{reason}:{before[field]}->{after[field]}"
        if after[field] < before[field]:
            improvements.append(f"{field}_reduced")

    higher_is_better = (
        ("valid_required_paragraphs", "valid_paragraphs"),
        ("valid_targets", "valid_targets"),
        ("witnessed_slots", "witnessed_slots"),
        ("witnessed_edges", "witnessed_edges"),
        ("consumed_formula_packages", "consumed_formulas"),
    )
    for field, label in higher_is_better:
        if after[field] < before[field]:
            return False, f"{label}_count_regressed:{before[field]}->{after[field]}"
        if after[field] > before[field]:
            improvements.append(f"{label}_gain")

    if not improvements:
        return False, "no_safe_quality_gain"
    return True, ";".join(dict.fromkeys(improvements))


def _read_json_mapping(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _code_state_digest() -> str:
    """Deterministic read-only binding of the code state used for this batch.

    Hashes the sorted relative path plus content digest of every ``.py``
    file under ``src/``; no git command and no working-tree mutation.
    """

    digests: list[str] = []
    for path in sorted((_ROOT / "src").rglob("*.py")):
        if not path.is_file():
            continue
        relative = str(path.relative_to(_ROOT))
        content_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        digests.append(f"{relative}:{content_digest}")
    payload = "\n".join(digests).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _execution_manifest_digest(
    *,
    profile_path: Path,
    frozen: Path,
    copied_artifact_names: tuple[str, ...],
    authoring_context_mode: str = "legacy",
) -> str:
    """Bind replay script, profile, frozen inputs, and code manifest."""

    parts = [
        f"replay_script:{_digest_file(Path(__file__).resolve())}",
        f"code_state:{_code_state_digest()}",
        f"authoring_context_mode:{str(authoring_context_mode or 'legacy')}",
    ]
    if profile_path.is_file():
        parts.append(f"profile:{_digest_file(profile_path)}")
    else:
        parts.append("profile:missing")
    for name in sorted(copied_artifact_names):
        source = _frozen_artifact_path(frozen, name)
        if source is None:
            parts.append(f"frozen:{name}:missing")
        else:
            parts.append(f"frozen:{name}:{_digest_file(source)}")
    return _digest_text("\n".join(parts))


_BOUNDED_PREPARED_CONTINUATION_FAILURES = frozenset({
    "realizer_response_not_json",
    "realizer_response_not_object",
})
_BOUNDED_CHAINED_CONTINUATION_FAILURES = frozenset({
    "realizer_witness_text_missing",
    "realizer_required_witness_missing",
})


def _prepared_continuation_execution_digest(
    *,
    fresh: Path,
    current_execution_digest: str,
    telemetry: dict,
) -> str:
    """Admit bounded code-repair continuations for a failed prepared run.

    ``authoring_prepare_result_v1`` remains the immutable material contract.
    A code change after preparation normally makes ``execute-prepared`` fail
    closed.  The only exception is a prior failed execution whose durable
    failure artifact identifies the known representation-only Realizer JSON
    failure.  If that repair parses but exposes a witness-binding failure, a
    second explicitly recorded continuation may hand the frozen excerpts back
    to the Realizer.  This is deliberately narrow: it cannot start a new
    primary page, change the prepared material, or be used more than once per
    continuation stage for the same root.
    """

    if current_execution_digest == "":
        return current_execution_digest
    prepare_path = (
        fresh / "artifacts" / "06_authoring" / "authoring_prepare_result_v1.json"
    )
    stored_prepare = _read_json_mapping(prepare_path)
    parent_digest = str(stored_prepare.get("execution_manifest_digest") or "")
    if not parent_digest or parent_digest == current_execution_digest:
        return current_execution_digest

    continuation_dir = fresh / "artifacts" / "06_authoring"
    continuation_path = continuation_dir / "authoring_prepare_continuation_v1.json"
    chained_continuation_path = (
        continuation_dir / "authoring_prepare_continuation_v2.json"
    )
    budget_continuation_path = (
        continuation_dir / "authoring_prepare_continuation_v3.json"
    )
    post_budget_continuation_path = (
        continuation_dir / "authoring_prepare_continuation_v4.json"
    )
    if post_budget_continuation_path.is_file():
        return current_execution_digest

    execution_record = _read_json_mapping(fresh / "execution_record.json")
    prior_structural_exit = execution_record.get("structural_exit") or {}
    prior_terminal_complete = (
        str(execution_record.get("terminal_stage") or "") == "complete"
        and not str(execution_record.get("terminal_reason") or "").strip()
        and str(execution_record.get("writer_status") or "") == "success"
        and str(execution_record.get("writer_transaction_status") or "") == "success"
        and isinstance(prior_structural_exit, Mapping)
        and bool(prior_structural_exit.get("eligible"))
    )
    if (
        str(execution_record.get("authoring_stage") or "") != "execute-prepared"
        or (
            int(execution_record.get("exit_code") or 0) == 0
            and not prior_terminal_complete
        )
    ):
        return current_execution_digest

    def _write_continuation(
        *,
        path: Path,
        failure_codes: list[str],
        reason: str,
        parent_continuation_digest: str = "",
    ) -> str:
        continuation = {
            "schema_version": "1.0",
            "kind": "bounded_code_repair_continuation",
            "stage": "execute-prepared",
            "parent_prepare_result_digest": str(
                stored_prepare.get("content_digest") or ""
            ),
            "parent_continuation_digest": parent_continuation_digest,
            "parent_execution_manifest_digest": parent_digest,
            "current_execution_manifest_digest": current_execution_digest,
            "prior_execution_record": str(fresh / "execution_record.json"),
            "prior_execution_record_exit_code": int(
                execution_record.get("exit_code") or 0
            ),
            "prior_execution_code_state_digest": str(
                execution_record.get("code_state_digest") or ""
            ),
            "failure_codes": failure_codes,
            "reason": reason,
            "model_calls_before_continuation": int(
                stored_prepare.get("model_calls") or 0
            ),
        }
        continuation["content_digest"] = _digest_text(
            json.dumps(
                continuation,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(continuation, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        telemetry["authoring_prepare_continuation"] = {
            "status": "admitted",
            "path": str(path),
            "content_digest": continuation["content_digest"],
            "failure_codes": failure_codes,
            "parent_execution_manifest_digest": parent_digest,
            "current_execution_manifest_digest": current_execution_digest,
            "reason": reason,
        }
        return parent_digest

    if chained_continuation_path.is_file():
        prior_continuation = _read_json_mapping(chained_continuation_path)
        prior_continuation_digest = str(
            prior_continuation.get("content_digest") or ""
        )
        prior_continuation_body = {
            key: value
            for key, value in prior_continuation.items()
            if key != "content_digest"
        }
        if (
            not prior_continuation_digest
            or _digest_text(
                json.dumps(
                    prior_continuation_body,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ) != prior_continuation_digest
        ):
            return current_execution_digest
        # The completed structural run may have exposed a separate, bounded
        # F6 defect: local Rewrite received the full immutable V2 page bytes
        # and every auxiliary attempt was rejected before transport by the
        # declared request cap.  Admit one continuation for the production
        # context projection repair.  Require every recorded Rewrite row to
        # be pre-send rejected so this branch cannot replay a provider result
        # or hide an actual content failure behind a code-only continuation.
        rewrite_payload = _read_json_mapping(
            fresh / "artifacts/07_validation/publication_rewrite_transitions_v1.json"
        )
        rewrite_accounting = _read_json_mapping(
            fresh
            / "artifacts/06_authoring/proposal_call_accounting_local_rewrite.json"
        )
        rewrite_failures = tuple(
            str(item) for item in (rewrite_payload.get("failures") or ())
        )
        rewrite_cap_reasons = tuple(
            str(item.get("reason") or "")
            for item in (rewrite_payload.get("transitions") or ())
            if isinstance(item, Mapping)
        )
        rewrite_result_reasons = tuple(
            str((item.get("result") or {}).get("blocked_reason") or "")
            for item in (rewrite_payload.get("results") or ())
            if isinstance(item, Mapping)
            and isinstance(item.get("result"), Mapping)
        )
        rewrite_rows = tuple(
            item for item in (rewrite_accounting.get("rows") or ())
            if isinstance(item, Mapping)
        )
        observed_cap_reasons = tuple(
            item
            for item in (*rewrite_cap_reasons, *rewrite_result_reasons)
            if item
        )
        rewrite_cap_only = bool(observed_cap_reasons) and all(
            "unified_auxiliary_request_cap_exceeded:" in item
            for item in observed_cap_reasons
        ) and bool(rewrite_rows) and all(
            not bool(item.get("sent_to_caller"))
            and "unified_auxiliary_request_cap_exceeded:" in str(
                item.get("error") or ""
            )
            for item in rewrite_rows
        )
        if (
            prior_terminal_complete
            and prior_continuation.get("failure_codes")
            == ["deterministic_projection_code_repair"]
            and rewrite_cap_only
        ):
            return _write_continuation(
                path=budget_continuation_path,
                failure_codes=["rewrite_auxiliary_context_compaction"],
                reason="resume_after_pre_send_rewrite_context_cap_repair",
                parent_continuation_digest=prior_continuation_digest,
            )
        latest_failure_parts = [
            str(execution_record.get(key) or "")
            for key in ("terminal_reason", "writer_blocked_reason")
        ]
        for relative in (
            "artifacts/06_authoring/publication_writer_result_v1.json",
            "artifacts/06_authoring/realizer_plan_execution_v2.json",
        ):
            payload = _read_json_mapping(fresh / relative)
            latest_failure_parts.extend(
                str(payload.get(key) or "")
                for key in ("blocked_reason", "terminal_reason", "failure")
            )
            for trace in payload.get("traces", ()) or ():
                if isinstance(trace, Mapping):
                    latest_failure_parts.extend(
                        str(trace.get(key) or "")
                        for key in ("blocked_reason", "failure", "draft_blocked_reason")
                    )
        usage = _read_json_mapping(
            continuation_dir / "token_usage_summary_v1.json"
        )
        latest_failure_text = " ".join(latest_failure_parts)
        if (
            (
                "planned_request_input_tokens" in latest_failure_text
                or "attempt_limit_exhausted" in latest_failure_text
            )
            and int(usage.get("total_tokens") or 0) == 0
            and int(usage.get("calls") or 0) == 0
        ):
            next_path = (
                post_budget_continuation_path
                if budget_continuation_path.is_file()
                else budget_continuation_path
            )
            next_failure_codes = (
                ["realizer_attempt_limit_after_pre_send_rejection"]
                if budget_continuation_path.is_file()
                else ["realizer_planned_request_input_tokens"]
            )
            next_reason = (
                "resume_after_unmetered_attempt_limit_rejection"
                if budget_continuation_path.is_file()
                else "retry_reserve_capability_repair_after_pre_send_rejection"
            )
            return _write_continuation(
                path=next_path,
                failure_codes=next_failure_codes,
                reason=next_reason,
                parent_continuation_digest=prior_continuation_digest,
            )
        return current_execution_digest

    if budget_continuation_path.is_file():
        prior_continuation = _read_json_mapping(budget_continuation_path)
        prior_continuation_digest = str(
            prior_continuation.get("content_digest") or ""
        )
        prior_continuation_body = {
            key: value
            for key, value in prior_continuation.items()
            if key != "content_digest"
        }
        if (
            not prior_continuation_digest
            or _digest_text(
                json.dumps(
                    prior_continuation_body,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ) != prior_continuation_digest
        ):
            return current_execution_digest
        latest_failure_parts = [
            str(execution_record.get(key) or "")
            for key in ("terminal_reason", "writer_blocked_reason")
        ]
        usage = _read_json_mapping(
            continuation_dir / "token_usage_summary_v1.json"
        )
        if (
            "attempt_limit_exhausted" in " ".join(latest_failure_parts)
            and int(usage.get("total_tokens") or 0) == 0
            and int(usage.get("calls") or 0) == 0
        ):
            return _write_continuation(
                path=post_budget_continuation_path,
                failure_codes=["realizer_attempt_limit_after_pre_send_rejection"],
                reason="resume_after_unmetered_attempt_limit_rejection",
                parent_continuation_digest=prior_continuation_digest,
            )
        return current_execution_digest

    if continuation_path.is_file():
        prior_continuation = _read_json_mapping(continuation_path)
        prior_continuation_digest = str(
            prior_continuation.get("content_digest") or ""
        )
        prior_continuation_body = {
            key: value
            for key, value in prior_continuation.items()
            if key != "content_digest"
        }
        if (
            not prior_continuation_digest
            or _digest_text(
                json.dumps(
                    prior_continuation_body,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
        ) != prior_continuation_digest
        ):
            return current_execution_digest
        # A completed prepared execution may still need a deterministic
        # projection repair (for example, promoting complete paragraph
        # transactions over an incomplete legacy section summary) after the
        # first bounded code-repair continuation.  Admit exactly one chained
        # continuation only when the prior run reached the complete terminal
        # boundary, its Writer transaction and structural exit both passed,
        # and no earlier failure was recorded.  No new input, request, or
        # provider result is authorized by this branch.
        if (
            prior_terminal_complete
            and not str(execution_record.get("first_failed_reason") or "").strip()
        ):
            return _write_continuation(
                path=chained_continuation_path,
                failure_codes=["deterministic_projection_code_repair"],
                reason="resume_after_completed_structural_projection_repair",
                parent_continuation_digest=prior_continuation_digest,
            )
        latest_failure_parts: list[str] = []
        for relative in (
            "artifacts/06_authoring/publication_writer_result_v1.json",
            "artifacts/06_authoring/realizer_plan_execution_v2.json",
        ):
            payload = _read_json_mapping(fresh / relative)
            latest_failure_parts.extend(
                str(payload.get(key) or "")
                for key in ("blocked_reason", "terminal_reason", "failure")
            )
            for trace in payload.get("traces", ()) or ():
                if isinstance(trace, Mapping):
                    latest_failure_parts.extend(
                        str(trace.get(key) or "")
                        for key in ("blocked_reason", "failure", "draft_blocked_reason")
                    )
        chained_codes = sorted(
            code for code in _BOUNDED_CHAINED_CONTINUATION_FAILURES
            if code in " ".join(latest_failure_parts)
        )
        if not chained_codes:
            return current_execution_digest
        return _write_continuation(
            path=chained_continuation_path,
            failure_codes=chained_codes,
            reason="witness_repair_after_response_format_repair",
            parent_continuation_digest=prior_continuation_digest,
        )

    # A prepared root may be resumed after a deterministic production-code
    # repair that happened after ``prepare``.  The material contract remains
    # immutable; the failed attempt below is admitted only when the sole
    # failure was the execution-manifest code binding itself and the attempt
    # provably made no provider call.  This is narrower than accepting an
    # arbitrary code drift: content/input/request digests are still checked by
    # ``run_publication_method_writer`` against the stored prepare result, and
    # the continuation is single-use through ``continuation_path``.
    zero_call_usage = _read_json_mapping(
        continuation_dir / "token_usage_summary_v1.json"
    )
    manifest_binding_failure = "authoring_prepare_result_binding_mismatch:execution_manifest_digest"
    prior_failure_text = " ".join(
        str(execution_record.get(key) or "")
        for key in ("terminal_reason", "writer_blocked_reason", "first_failed_reason")
    )
    if (
        manifest_binding_failure in prior_failure_text
        and int(zero_call_usage.get("calls") or 0) == 0
        and int(zero_call_usage.get("total_tokens") or 0) == 0
        and int(stored_prepare.get("model_calls") or 0) == 0
    ):
        return _write_continuation(
            path=continuation_path,
            failure_codes=["prepared_execution_manifest_code_repair"],
            reason="resume_after_zero_call_prepare_binding_repair",
        )

    failure_candidates = (
        fresh / "artifacts" / "06_authoring" / "authoring_failure_v1.json",
        fresh / "authoring_failure_v1.json",
    )
    failure_path = next((path for path in failure_candidates if path.is_file()), None)
    failure = _read_json_mapping(failure_path) if failure_path is not None else {}
    failure_text = " ".join(
        str(failure.get(key) or "")
        for key in ("terminal_reason", "direct_reason")
    )
    failure_codes = sorted(
        code for code in _BOUNDED_PREPARED_CONTINUATION_FAILURES
        if code in failure_text
    )
    if not failure_codes:
        return current_execution_digest
    return _write_continuation(
        path=continuation_path,
        failure_codes=failure_codes,
        reason="representation_only_realizer_response_format_repair",
    )


DEFAULT_LIVE_PROFILE = Path("tests/live/profiles/qwen38_vllm_budgeted.example.env")
TOKEN_USAGE_SUMMARY_FILENAME = "token_usage_summary_v1.json"
#: 复用证据索引的文件名/读写实现由产品侧统一定义（见 reused_evidence_index）。
REUSED_EVIDENCE_RECEIPTS_FILENAME = "reused_evidence_receipts_v1.json"


def _is_custom_env_configured() -> bool:
    """Return True if the user has already configured LLM endpoint/model in environment."""
    return bool(
        os.environ.get("CODE2PAPER_OPENAI_BASE_URL")
        or os.environ.get("AIHUBMIX_BASE_URL")
        or (os.environ.get("CODE2PAPER_LLM_PROVIDER") and os.environ.get("CODE2PAPER_LLM_PROVIDER") != "none")
        or os.environ.get("CODE2PAPER_LIVE_PROFILE")
    )


def _snapshot_active_env_profile(target_path: Path) -> Path:
    """Persist active LLM and CODE2PAPER_* environment variables to a reproducible profile file."""
    lines = [
        "# Auto-captured ambient environment profile for replay execution",
        "# Digest-bound for provenance; secrets are redacted.",
    ]
    for key in sorted(os.environ):
        if key.startswith("CODE2PAPER_") or key in {
            "OPENAI_API_KEY",
            "AIHUBMIX_API_KEY",
            "ANTHROPIC_API_KEY",
            "GOOGLE_API_KEY",
            "OPENROUTER_API_KEY",
        }:
            raw = os.environ[key]
            if any(secret_marker in key for secret_marker in ("KEY", "SECRET", "TOKEN")):
                val = "<redacted>"
            else:
                val = raw
            lines.append(f"export {key}={val}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target_path


def _resolve_profile_path(profile_arg: str | Path | None, *, fresh: Path) -> Path:
    """Resolve the live profile to load and bind into the execution manifest."""
    # 1. Explicit /dev/null request: snapshot active environment into fresh artifacts
    if profile_arg and str(profile_arg).strip() in {"/dev/null", os.devnull}:
        return _snapshot_active_env_profile(fresh / "artifacts" / "06_authoring" / "ambient_profile.env")

    # 2. Explicit profile path given
    if profile_arg:
        p = Path(profile_arg).expanduser()
        if p.is_file():
            return p
        return p

    # 3. No profile argument passed: check if environment is already configured
    if _is_custom_env_configured():
        return _snapshot_active_env_profile(fresh / "artifacts" / "06_authoring" / "ambient_profile.env")

    # 4. Fallback to default local Qwen profile
    return DEFAULT_LIVE_PROFILE.expanduser()


def _apply_live_profile(profile: str | Path | None, *, overwrite: bool = False) -> None:
    """Load a live ``.env`` profile without expanding secrets-bearing ``$`` values.

    Existing environment variables take precedence unless overwrite is True.
    """

    if not profile:
        return
    path = Path(profile).expanduser()
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        line = line.removeprefix("export ").strip()
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key == "CODE2PAPER_LLM_CAPABILITY_PROFILE" and value:
            # This is a tracked, non-secret path.  Resolve only the profile
            # directory token used by qwen36 and relative capability paths;
            # never evaluate arbitrary shell expressions from a profile.
            value = value.replace(
                "${_CODE2PAPER_PROFILE_DIR}",
                str(path.parent),
            )
            value = value.replace(
                "$_CODE2PAPER_PROFILE_DIR",
                str(path.parent),
                1,
            )
            capability_path = Path(value).expanduser()
            if not capability_path.is_absolute():
                profile_relative = path.parent / capability_path
                capability_path = (
                    profile_relative
                    if profile_relative.is_file()
                    else Path.cwd() / capability_path
                )
            value = str(capability_path.resolve())
        if key and not key.startswith("_") and value and (
            "$" not in value or key == "CODE2PAPER_LLM_CAPABILITY_PROFILE"
        ):
            if overwrite or key not in os.environ:
                os.environ[key] = value


def _apply_replay_profile(
    profile: str | Path | None,
    *,
    force: bool = False,
) -> None:
    """Apply a replay profile, optionally making it authoritative.

    The normal loader preserves ambient configuration so an already selected
    provider is not silently changed.  ``--force-profile`` is the explicit
    operator escape hatch for live replays: it also removes the legacy
    ``AIHUBMIX_BASE_URL`` alias, which otherwise takes precedence over the
    selected OpenAI-compatible base URL.
    """

    if force:
        os.environ.pop("AIHUBMIX_BASE_URL", None)
        os.environ.pop("CODE2PAPER_LLM_CAPABILITY_PROFILE", None)
        _apply_live_profile(profile, overwrite=True)
    else:
        _apply_live_profile(profile)


def _build_replay_unified_tokenizer(
    *,
    llm_config: Any,
    fresh: Path,
) -> Any:
    """Compatibility wrapper around the shared product/replay tokenizer gate."""

    from code2paper.llm.tokenizer import prepare_vllm_openai_chat_tokenizer

    return prepare_vllm_openai_chat_tokenizer(
        llm_config=llm_config,
        out_root=fresh,
        require_loopback_8006=True,
    )


def _positive_int(value: object) -> int | None:
    """Return a non-negative integer token count when ``value`` is usable."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float) and value.is_integer():
        return max(0, int(value))
    if isinstance(value, str) and value.strip().isdigit():
        return max(0, int(value.strip()))
    return None


def _usage_count(usage: Mapping[str, Any], keys: tuple[str, ...]) -> int | None:
    """Read the first provider usage alias present in a normalized payload."""

    for key in keys:
        count = _positive_int(usage.get(key))
        if count is not None:
            return count
    return None


_INPUT_TOKEN_KEYS = (
    "prompt_tokens",
    "input_tokens",
    "prompt_token_count",
    "input_token_count",
    "promptTokens",
    "inputTokens",
)
_OUTPUT_TOKEN_KEYS = (
    "completion_tokens",
    "output_tokens",
    "generated_tokens",
    "completion_token_count",
    "output_token_count",
    "completionTokens",
    "outputTokens",
)
_TOTAL_TOKEN_KEYS = (
    "total_tokens",
    "total_token_count",
    "totalTokens",
)
_REASONING_TOKEN_KEYS = (
    "reasoning_tokens",
    "thinking_tokens",
    "thinking_token_count",
    "completion_tokens_details.reasoning_tokens",
    "completion_tokens_details.reasoningTokens",
)


def _summarize_token_usage(calls: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
    """Aggregate provider-reported token usage without double-counting breakdowns.

    ``total_tokens`` is authoritative when a provider returns it.  For older
    OpenAI-compatible responses that expose only input/output counts, the
    summary derives a per-call total and marks the run as estimated.  Thinking
    and reasoning counts are retained as a breakdown; they are not added a
    second time when already included in completion tokens.
    """

    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "reasoning_tokens": 0,
    }
    by_role: dict[str, dict[str, Any]] = {}
    raw_usage_totals: dict[str, int] = {}
    calls_with_usage = 0
    explicit_total_calls = 0
    estimated_total_calls = 0
    cached_calls = 0
    blocked_calls = 0
    models: set[str] = set()
    endpoint_origins: set[str] = set()
    reused_totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "reasoning_tokens": 0,
    }
    reused_calls = 0
    reused_calls_with_usage = 0
    reused_estimated_total_calls = 0

    for call in calls:
        raw_usage = call.get("token_usage")
        usage: Mapping[str, Any] = raw_usage if isinstance(raw_usage, Mapping) else {}
        reused = bool(call.get("reused_evidence"))
        if reused:
            # 复用冻结证据的用量单独记账：它既不是本次发送，也不能被静默丢掉。
            reused_calls += 1
            reused_calls_with_usage += int(bool(usage))
        else:
            if usage:
                calls_with_usage += 1
            if bool(call.get("cached")):
                cached_calls += 1
            if str(call.get("blocked_reason") or "").strip():
                blocked_calls += 1
        model = str(call.get("model") or "").strip()
        endpoint = str(call.get("endpoint_origin") or "").strip()
        if model:
            models.add(model)
        if endpoint:
            endpoint_origins.add(endpoint)

        input_tokens = _usage_count(usage, _INPUT_TOKEN_KEYS) or 0
        output_tokens = _usage_count(usage, _OUTPUT_TOKEN_KEYS) or 0
        explicit_total = _usage_count(usage, _TOTAL_TOKEN_KEYS)
        if explicit_total is None:
            total_tokens = input_tokens + output_tokens
            total_class = "estimated" if (input_tokens or output_tokens) else "absent"
        else:
            total_tokens = explicit_total
            total_class = "explicit"
        if reused:
            if total_class == "estimated":
                reused_estimated_total_calls += 1
            reused_totals["input_tokens"] += input_tokens
            reused_totals["output_tokens"] += output_tokens
            reused_totals["total_tokens"] += total_tokens
        else:
            if total_class == "explicit":
                explicit_total_calls += 1
            elif total_class == "estimated":
                estimated_total_calls += 1
            totals["input_tokens"] += input_tokens
            totals["output_tokens"] += output_tokens
            totals["total_tokens"] += total_tokens
        reasoning_tokens = _usage_count(usage, _REASONING_TOKEN_KEYS) or 0
        if reused:
            reused_totals["reasoning_tokens"] += reasoning_tokens
        else:
            totals["reasoning_tokens"] += reasoning_tokens

        for key, value in usage.items():
            count = _positive_int(value)
            if count is not None:
                raw_usage_totals[str(key)] = raw_usage_totals.get(str(key), 0) + count

        role = str(call.get("role") or "unknown").strip() or "unknown"
        role_totals = by_role.setdefault(
            role,
            {
                "calls": 0,
                "calls_with_usage": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "reasoning_tokens": 0,
            },
        )
        role_totals["calls"] += 1
        role_totals["calls_with_usage"] += int(bool(usage))
        role_totals["input_tokens"] += input_tokens
        role_totals["output_tokens"] += output_tokens
        role_totals["total_tokens"] += total_tokens
        role_totals["reasoning_tokens"] += reasoning_tokens

    call_count = len(calls)
    sent_count = call_count - reused_calls
    return {
        "schema_version": "1.0",
        "artifact": "token_usage_summary_v1",
        "accounting": (
            "top-level calls/*_tokens count only provider calls this run sent; "
            "reused_evidence_* carries frozen receipts copied into the root; "
            "all_receipts_* is their sum; sum provider total_tokens and derive "
            "input+output only when total_tokens is absent; reasoning_tokens is "
            "a non-additive breakdown"
        ),
        "status": (
            "no_calls" if sent_count == 0
            else "complete" if calls_with_usage == sent_count
            else "partial"
        ),
        "calls": sent_count,
        "calls_with_usage": calls_with_usage,
        "calls_without_usage": sent_count - calls_with_usage,
        "explicit_total_token_calls": explicit_total_calls,
        "estimated_total_token_calls": estimated_total_calls,
        "cached_calls": cached_calls,
        "blocked_calls": blocked_calls,
        "usage_available": calls_with_usage > 0,
        "total_tokens_is_estimate": estimated_total_calls > 0,
        **totals,
        "provenance": {
            "sent": sent_count,
            "reused_evidence": reused_calls,
            "unclassified": 0,
        },
        "reused_evidence": {
            "calls": reused_calls,
            "calls_with_usage": reused_calls_with_usage,
            "estimated_total_token_calls": reused_estimated_total_calls,
            **reused_totals,
        },
        "all_receipts": {
            "calls": call_count,
            "calls_with_usage": calls_with_usage + reused_calls_with_usage,
            "input_tokens": totals["input_tokens"] + reused_totals["input_tokens"],
            "output_tokens": totals["output_tokens"] + reused_totals["output_tokens"],
            "total_tokens": totals["total_tokens"] + reused_totals["total_tokens"],
            "reasoning_tokens": (
                totals["reasoning_tokens"] + reused_totals["reasoning_tokens"]
            ),
        },
        "by_role": dict(sorted(by_role.items())),
        "raw_usage_totals": dict(sorted(raw_usage_totals.items())),
        "models": sorted(models),
        "endpoint_origins": sorted(endpoint_origins),
        "source": "code2paper.llm.generation_trace",
    }


def _write_token_usage_summary(fresh: Path) -> dict[str, Any]:
    """Persist the aggregate usage sidecar and return its execution-record view."""

    ledger_root = fresh / "artifacts" / "06_authoring" / "invocations"
    calls: list[Mapping[str, Any]] = []
    source = "code2paper.llm.generation_trace"
    if ledger_root.is_dir():
        from code2paper.agentic.unified_context_models import ActualRequestReceiptV2

        reused_index = _load_reused_evidence_receipts_index(fresh)
        provenance_mismatches: list[str] = []
        seen: set[tuple[str, int]] = set()
        corrupt: list[str] = []
        for receipt_path in sorted(ledger_root.glob("*/attempt-*.completed.json")):
            try:
                receipt = ActualRequestReceiptV2.model_validate_json(
                    receipt_path.read_text(encoding="utf-8")
                )
            except Exception:
                corrupt.append(str(receipt_path.relative_to(ledger_root)))
                continue
            key = (receipt.invocation_id, receipt.attempt)
            if key in seen:
                continue
            seen.add(key)
            if not receipt.sent_to_caller:
                continue
            relative = str(receipt_path.relative_to(ledger_root)).replace(os.sep, "/")
            expected = reused_index.get(relative)
            # 索引里声明为"复制自冻结根"且内容仍与复制时一致 → 复用证据；
            # 摘要不符说明文件在复制后被改写，按本次发送保守计入并留痕。
            reused = bool(expected) and expected == _digest_file(receipt_path)
            if expected and not reused:
                provenance_mismatches.append(relative)
            calls.append({
                "role": receipt.consumer_role,
                "token_usage": dict(receipt.provider_usage or {}),
                "model": receipt.model_identity_digest,
                "reused_evidence": reused,
                "blocked_reason": (
                    receipt.delivery_rejection_code
                    if receipt.delivery_status == "rejected" else ""
                ),
            })
        if corrupt:
            raise ValueError(
                "durable_usage_receipt_corrupt:" + ",".join(corrupt[:5])
            )
        if provenance_mismatches:
            # 复制后内容被改写：如实记录，且这些回执按"本次发送"保守计入。
            provenance_mismatches_note = list(provenance_mismatches)
        else:
            provenance_mismatches_note = []
        source = "durable_unified_invocation_receipts"
    else:
        provenance_mismatches_note = []
        try:
            from code2paper.llm.generation_trace import get_run_generation_traces

            calls = list(get_run_generation_traces())
        except Exception:
            calls = []
    summary = _summarize_token_usage(calls)
    summary["source"] = source
    if provenance_mismatches_note:
        summary["provenance"]["content_changed_after_copy"] = len(
            provenance_mismatches_note
        )
        summary["provenance"]["content_changed_after_copy_receipts"] = list(
            provenance_mismatches_note[:5]
        )
    path = fresh / "artifacts" / "06_authoring" / TOKEN_USAGE_SUMMARY_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    result = {**summary, "path": str(path)}
    reused = summary["reused_evidence"]
    print(
        "[replay] token usage: "
        f"sent_calls={summary['calls']} "
        f"sent_total={summary['total_tokens']} "
        f"input={summary['input_tokens']} "
        f"output={summary['output_tokens']} "
        f"usage_calls={summary['calls_with_usage']} "
        f"| reused_evidence_calls={reused['calls']} "
        f"reused_evidence_total={reused['total_tokens']} "
        f"| all_receipts_total={summary['all_receipts']['total_tokens']} "
        f"path={path}"
    )
    return result


def _authoring_failure_path(fresh: Path) -> Path:
    return fresh / "artifacts" / "06_authoring" / "authoring_failure_v1.json"


def _safe_failure_text(value: Any, *, limit: int = 320) -> str:
    """Keep failure diagnostics useful without persisting credentials."""

    text = str(value or "")
    for marker in ("api_key", "access_token", "authorization", "bearer"):
        text = re.sub(
            rf"(?i)({re.escape(marker)}\s*[:=]\s*)[^,;\s]+",
            r"\1<redacted>",
            text,
        )
    return text[:limit]


def _failure_scope_from_artifacts(
    *,
    fresh: Path,
    structural: Mapping[str, Any] | None,
    terminal_reason: str,
) -> dict[str, Any]:
    """Resolve the first concrete paragraph/target failure for diagnostics."""

    structural = structural if isinstance(structural, Mapping) else {}
    reasons = [
        str(value).strip()
        for value in (structural.get("reasons") or ())
        if str(value).strip()
    ]
    priority = (
        "required_paragraph_invalid:",
        "required_paragraph_unassessed:",
        "required_paragraph_not_rendered:",
        "required_target_uncovered:",
        "required_formula_unresolved:",
        "formula_packages_unconsumed:",
    )
    direct_reason = next(
        (reason for prefix in priority for reason in reasons if reason.startswith(prefix)),
        _safe_failure_text(terminal_reason),
    )
    section_id = ""
    paragraph_id = ""
    target_kind = ""
    target_id = ""
    if direct_reason.startswith("required_target_uncovered:"):
        payload = direct_reason.removeprefix("required_target_uncovered:")
        section_id, _, payload = payload.partition(":")
        target_kind = payload.rsplit(":", 1)[-1].strip()
        paragraph_id = payload[:-(len(target_kind) + 1)] if target_kind else payload
    elif direct_reason.startswith((
        "required_paragraph_invalid:",
        "required_paragraph_unassessed:",
        "required_paragraph_not_rendered:",
    )):
        payload = direct_reason.split(":", 1)[1]
        section_id, _, paragraph_id = payload.partition(":")

    assessment_path = fresh / "artifacts" / "06_authoring" / (
        "publication_paragraph_transaction_assessments_v1.json"
    )
    try:
        assessment_payload = json.loads(assessment_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        assessment_payload = {}
    for row in assessment_payload.get("assessments", ()) if isinstance(
        assessment_payload, Mapping
    ) else ():
        if not isinstance(row, Mapping):
            continue
        if section_id and str(row.get("section_id") or "") != section_id:
            continue
        if paragraph_id and str(row.get("paragraph_id") or "") != paragraph_id:
            continue
        missing = row.get("missing_by_kind") or {}
        if target_kind:
            values = missing.get(target_kind) or () if isinstance(missing, Mapping) else ()
            target_id = str(next(iter(values), "") or "").strip()
        elif isinstance(missing, Mapping):
            for kind in ("formula", "slot", "edge", "facet", "field"):
                values = missing.get(kind) or ()
                if values:
                    target_kind = kind
                    target_id = str(values[0]).strip()
                    break
        break
    cascade = [reason for reason in reasons if reason != direct_reason]
    if not section_id or not paragraph_id:
        # Writer boundary messages carry a paragraph id even when the
        # structural receipt was not generated.  Recover it only from the
        # stable typed prefixes; never guess a section from prose text.
        match = re.search(
            r"(?:required_target_contract|witness_not_unique_substring|missing_exact_witness):"
            r"([^;]+)",
            str(terminal_reason or ""),
        )
        if match:
            token = match.group(1)
            parts = token.split(":")
            if len(parts) >= 2 and parts[0].startswith("MA-"):
                section_id = section_id or parts[0]
                paragraph_id = paragraph_id or ":".join(parts[1:-1])
                target_id = target_id or parts[-1]
    return {
        "section_id": section_id,
        "paragraph_id": paragraph_id,
        "target_kind": target_kind,
        "target_id": target_id,
        "direct_reason": direct_reason,
        "cascade_reasons": cascade,
    }


def _remember_first_failure(
    telemetry: dict[str, Any],
    *,
    stage: str,
    reason: str,
    error_code: str = "authoring_failure",
) -> None:
    """Keep the first failed boundary stable across later cleanup gates."""

    if telemetry.get("first_failed_stage"):
        return
    telemetry["first_failed_stage"] = str(stage or "replay")
    telemetry["first_failed_reason"] = _safe_failure_text(reason)
    telemetry["first_failed_error_code"] = str(error_code or "authoring_failure")


def _write_authoring_failure(
    *,
    fresh: Path,
    terminal_stage: str,
    terminal_reason: str,
    error_code: str = "",
    section_id: str = "",
    paragraph_id: str = "",
    target_kind: str = "",
    target_id: str = "",
    direct_reason: str = "",
    cascade_reasons: tuple[str, ...] | list[str] = (),
    exc: BaseException | None = None,
) -> str:
    """Persist one typed terminal failure for replay/evaluator consumers."""

    path = _authoring_failure_path(fresh)
    path.parent.mkdir(parents=True, exist_ok=True)
    stage_order = ("research", "formalizer", "writer")
    stage_index = {
        stage: index for index, stage in enumerate(stage_order)
    }
    terminal_index = stage_index.get(str(terminal_stage or ""), -1)

    def stage_status(stage: str) -> str:
        if terminal_index < 0:
            return "not_run"
        index = stage_index[stage]
        if index < terminal_index:
            return "completed"
        if index == terminal_index:
            return "failed"
        return "not_run"

    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "artifact": "authoring_failure_v1",
        "terminal_stage": str(terminal_stage or "replay"),
        "error_code": str(error_code or "authoring_failure"),
        "terminal_reason": _safe_failure_text(terminal_reason),
        "section_id": str(section_id or ""),
        "paragraph_id": str(paragraph_id or ""),
        "target_kind": str(target_kind or ""),
        "target_id": str(target_id or ""),
        "direct_reason": _safe_failure_text(direct_reason or terminal_reason),
        "cascade_reasons": [
            _safe_failure_text(value)
            for value in (cascade_reasons or ())
            if str(value).strip()
        ],
        "input_summary": {
            "fresh_root_name": fresh.name,
            "exception_type": type(exc).__name__ if exc is not None else "",
            "exception_message": _safe_failure_text(exc) if exc is not None else "",
        },
        "downstream_stages": {
            stage: stage_status(stage) for stage in stage_order
        },
    }
    payload["content_digest"] = _digest_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _write_execution_record(
    *,
    frozen: Path,
    fresh: Path,
    arguments: argparse.Namespace,
    exit_code: int,
    runtime_start: dict | None,
    runtime_end: dict | None,
    telemetry: dict,
) -> None:
    """Persist the durable R4 execution record without secrets."""

    record = {
        "schema_version": "1.0",
        "run_id": arguments.run_id,
        "command": " ".join(sys.argv),
        "argv": list(sys.argv),
        "exit_code": exit_code,
        "frozen_root": str(frozen),
        "fresh_root": str(fresh),
        "authoring_stage": telemetry.get(
            "authoring_stage", getattr(arguments, "authoring_stage", "full")
        ),
        "resume_section_ids": list(arguments.resume),
        "code_state_digest": _code_state_digest(),
        "execution_identity": telemetry.get("execution_identity", {}),
        "authoring_context": telemetry.get("authoring_context", {}),
        "preflight_only": bool(telemetry.get("preflight_only")),
        "deterministic_preflight": telemetry.get(
            "deterministic_preflight", {}
        ),
        "runtime": {
            "start": runtime_start or {},
            "end": runtime_end or {},
        },
        "reused_fulfilled_callback_ids": telemetry.get(
            "reused_fulfilled_callback_ids", []
        ),
        "writer_resumed_section_ids": telemetry.get(
            "writer_resumed_section_ids", []
        ),
        "writer_status": telemetry.get("writer_status", ""),
        "writer_transaction_status": telemetry.get(
            "writer_transaction_status", telemetry.get("writer_status", "")
        ),
        "publication_status": telemetry.get("publication_status", ""),
        "candidate_completion_status": telemetry.get(
            "candidate_completion_status", ""
        ),
        "candidate_complete": bool(telemetry.get("candidate_complete")),
        "verified_complete": bool(telemetry.get("verified_complete")),
        "writer_blocked_reason": telemetry.get("writer_blocked_reason", ""),
        "terminal_stage": telemetry.get("terminal_stage", ""),
        "terminal_reason": telemetry.get("terminal_reason", ""),
        "terminal_error_code": telemetry.get("terminal_error_code", ""),
        "first_failed_stage": telemetry.get("first_failed_stage", ""),
        "first_failed_reason": telemetry.get("first_failed_reason", ""),
        "first_failed_error_code": telemetry.get("first_failed_error_code", ""),
        "failure_artifact": str(
            _authoring_failure_path(fresh)
            if exit_code != 0 and _authoring_failure_path(fresh).is_file()
            else ""
        ),
        "candidate_digest": telemetry.get("candidate_digest", ""),
        "research_continuation_seed": telemetry.get(
            "research_continuation_seed", {}
        ),
        "callback_fulfillment": telemetry.get("callback_fulfillment", {}),
        "product_authoring_state": telemetry.get(
            "product_authoring_state", {}
        ),
        "content_chain": telemetry.get("content_chain", {}),
        "structural_exit": telemetry.get("structural_exit", {}),
        "token_usage": telemetry.get("token_usage", {}),
        "repository_source_rehydration": telemetry.get(
            "repository_source_rehydration", {}
        ),
        "invocation_terminal_event": telemetry.get(
            "invocation_terminal_event", {}
        ),
    }
    fresh.mkdir(parents=True, exist_ok=True)
    (fresh / "execution_record.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _candidate_digest_for_root(fresh: Path) -> str:
    from code2paper.agentic.publication_method_writer import _incumbent_candidate_digest

    return _incumbent_candidate_digest(fresh)


def _record_product_authoring_state(
    *,
    fresh: Path,
    paths: dict[str, str],
    telemetry: dict,
) -> None:
    """Expose the shared product graph checkpoint in replay telemetry."""

    path_value = str(
        paths.get("product_authoring_state_v1")
        or _find_fresh_artifact(fresh, "product_authoring_state_v1")
        or ""
    ).strip()
    if not path_value:
        return
    path = Path(path_value)
    if not path.is_file():
        return
    telemetry["product_authoring_state"] = {
        "path": str(path),
        "digest": _digest_file(path),
    }


def _record_method_content_trace(
    *,
    fresh: Path,
    artifact_paths: dict[str, str],
    telemetry: dict[str, Any],
) -> str:
    """Persist the source-to-render ledger for a replay after its final writer state.

    The autonomous runner writes this ledger itself, but ``run_authoring_replay``
    calls the Writer directly.  Keeping the same builder here makes replay
    artifacts comparable without copying a stale trace from the frozen root.
    """

    from code2paper.agentic.method_content_trace import write_method_content_trace

    trace_path = fresh / "artifacts" / "research_product" / "method_content_trace_v1.json"
    trace_artifact_paths = dict(artifact_paths)
    if str(
        (telemetry.get("authoring_context") or {}).get("effective_mode") or ""
    ) == "unified":
        # The compatibility MethodSectionPlanV2 is still needed by legacy
        # helpers, but the replay trace must use the final NarrativePlanV3
        # paragraph identity after page splitting.  Otherwise the trace and
        # transaction assessment compute different target sets.
        for name in ("narrative_plan_v3.revision.2", "narrative_plan_v3"):
            narrative_path = Path(
                trace_artifact_paths.get(name) or _find_fresh_artifact(fresh, name) or ""
            )
            if narrative_path.is_file():
                trace_artifact_paths["method_section_plan_v2"] = str(narrative_path)
                break
    trace = write_method_content_trace(trace_path, trace_artifact_paths)
    telemetry["content_chain"] = {
        **trace.summary,
        "content_digest": trace.content_digest,
        "trace_path": str(trace_path),
    }
    return str(trace_path)


def _load_artifact_payload(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _record_authoring_structural_exit(
    *,
    fresh: Path,
    paths: dict[str, str],
    telemetry: dict[str, Any],
) -> dict[str, Any]:
    """Persist the fail-closed callback=1 structural authorization receipt."""

    from code2paper.agentic.callback_semantic_contract import (
        evaluate_authoring_structural_exit,
    )
    from code2paper.core.output_names import method_output

    plan_path = paths.get("method_section_plan_v2") or _find_fresh_artifact(
        fresh, "method_section_plan_v2"
    )
    if str(
        (telemetry.get("authoring_context") or {}).get("effective_mode") or ""
    ) == "unified":
        for name in ("narrative_plan_v3.revision.2", "narrative_plan_v3"):
            narrative_path = Path(
                paths.get(name) or _find_fresh_artifact(fresh, name) or ""
            )
            if narrative_path.is_file():
                plan_path = narrative_path
                break
    trace_path = paths.get("method_content_trace_v1") or _find_fresh_artifact(
        fresh, "method_content_trace_v1"
    )
    writer_path = paths.get("publication_writer_result_v1") or _find_fresh_artifact(
        fresh, "publication_writer_result_v1"
    )
    formalization_path = paths.get("formalization_section_results_v1") or _find_fresh_artifact(
        fresh, "formalization_section_results_v1"
    )
    assessment_path = paths.get(
        "publication_paragraph_transaction_assessments_v1"
    ) or _find_fresh_artifact(
        fresh, "publication_paragraph_transaction_assessments_v1"
    )
    callback_path = paths.get("writing_research_callback_artifacts_v1") or _find_fresh_artifact(
        fresh, "writing_research_callback_artifacts_v1"
    )
    quality_path = paths.get("publication_quality_report_v1") or _find_fresh_artifact(
        fresh, "publication_quality_report_v1"
    )
    adapter_path = paths.get("method_section_plan_adapter_v1") or _find_fresh_artifact(
        fresh, "method_section_plan_adapter_v1"
    )
    candidate_path = method_output(fresh, "publication_candidate_method")
    try:
        candidate_markdown = candidate_path.read_text(encoding="utf-8")
    except OSError:
        candidate_markdown = ""
    decision = evaluate_authoring_structural_exit(
        plan_payload=_load_artifact_payload(plan_path),
        trace_payload=_load_artifact_payload(trace_path),
        writer_payload=_load_artifact_payload(writer_path),
        formalization_payload=_load_artifact_payload(formalization_path),
        callback_payload=_load_artifact_payload(callback_path),
        assessment_payload=_load_artifact_payload(assessment_path),
        quality_payload=_load_artifact_payload(quality_path),
        adapter_payload=_load_artifact_payload(adapter_path),
        candidate_digest=str(telemetry.get("candidate_digest") or ""),
        candidate_markdown=candidate_markdown,
    )
    exit_path = method_output(fresh, "authoring_structural_exit_v1")
    exit_path.parent.mkdir(parents=True, exist_ok=True)
    exit_path.write_text(decision.model_dump_json(indent=2) + "\n", encoding="utf-8")
    paths["authoring_structural_exit_v1"] = str(exit_path)
    telemetry["structural_exit"] = {
        "path": str(exit_path),
        **decision.model_dump(mode="json"),
    }
    print(
        "[replay] structural exit: "
        f"eligible={decision.eligible} reasons={list(decision.reasons)} "
        f"targets={decision.valid_targets}/{decision.required_targets} "
        f"formula={decision.consumed_formula_packages}/{decision.accepted_formula_packages}"
    )
    return decision.model_dump(mode="json")


def _write_authoring_rebuild_manifest(
    *,
    fresh: Path,
    entries: list[dict[str, Any]],
    execution_digest: str,
    refused_reason: str = "",
) -> None:
    payload = {
        "schema_version": "1.0",
        "execution_digest": execution_digest,
        "refused_reason": refused_reason,
        "artifacts": entries,
    }
    payload["content_digest"] = _digest_text(
        json.dumps(
            {key: value for key, value in payload.items() if key != "content_digest"},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    path = fresh / "artifacts" / "authoring_rebuild_manifest_v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _manifest_entry(
    *,
    name: str,
    path: Path,
    authority_class: str,
    decision: str,
    reason: str = "",
) -> dict[str, Any]:
    schema = name
    digest = _digest_file(path) if path.is_file() else ""
    return {
        "artifact_name": name,
        "path": str(path),
        "digest": digest,
        "schema": schema,
        "authority_class": authority_class,
        "decision": decision,
        "reason": reason,
    }


def _frozen_artifact_path(frozen: Path, name: str) -> Path | None:
    """Resolve a frozen artifact without depending on one historical layout."""

    candidates = (
        frozen / "artifacts" / "06_authoring" / f"{name}.json",
        frozen / "artifacts" / f"{name}.json",
        frozen / "artifacts" / "research_product" / f"{name}.json",
        frozen / "06_authoring" / f"{name}.json",
        frozen / "research_product" / f"{name}.json",
        frozen / f"{name}.json",
    )
    return next((path for path in candidates if path.is_file()), None)


def _copy_frozen_formalizer_phase(
    *,
    frozen: Path,
    fresh: Path,
    artifacts: Path,
    copied: list[str],
    manifest_entries: list[dict[str, Any]],
) -> tuple[str, ...]:
    """Copy and inventory the immutable Formalizer phase for prepare mode."""

    authoring = artifacts / "06_authoring"
    authoring.mkdir(parents=True, exist_ok=True)
    missing: list[str] = []
    for name in FORMALIZER_PHASE_COPY_ARTIFACTS:
        source = _frozen_artifact_path(frozen, name)
        if source is None or source.is_symlink():
            missing.append(name)
            continue
        target = authoring / f"{name}.json"
        shutil.copy2(source, target)
        if name not in copied:
            copied.append(name)
        manifest_entries.append(_manifest_entry(
            name=name,
            path=target,
            authority_class="formalizer-phase",
            decision="copied",
            reason="prepare_checkpoint",
        ))

    source_invocations = next(
        (
            candidate
            for candidate in (
                frozen / "artifacts" / "06_authoring" / "invocations",
                frozen / "artifacts" / "invocations",
            )
            if candidate.is_dir()
        ),
        None,
    )
    target_invocations = authoring / "invocations"
    if source_invocations is None:
        missing.append("formalizer_phase_invocations")
    else:
        invocation_digests: list[str] = []
        for source_path in sorted(source_invocations.rglob("*")):
            relative = source_path.relative_to(source_invocations)
            if source_path.is_symlink():
                raise ValueError(
                    f"formalizer_phase_checkpoint_symlink:{relative}"
                )
            if not source_path.is_file():
                continue
            target_path = target_invocations / relative
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
            invocation_digests.append(
                f"{relative}:{_digest_file(source_path)}"
            )
        if not invocation_digests:
            missing.append("formalizer_phase_invocations")
        else:
            manifest_entries.append({
                "artifact_name": "formalizer_phase_invocations",
                "path": str(target_invocations),
                "digest": _digest_text("\n".join(invocation_digests)),
                "schema": "unified_invocation_ledger_v1",
                "authority_class": "formalizer-phase",
                "decision": "copied",
                "reason": "prepare_checkpoint",
            })
            # 证据来源索引：这些回执是**复用的冻结用量**，不是本次 run 的花费。
            # token 汇总据此把"本次发送"与"复用证据"分开（§14.3 效率口径）。
            _write_reused_evidence_receipts_index(
                authoring=authoring,
                frozen=frozen,
                receipts=tuple(
                    sorted(
                        str(path.relative_to(target_invocations)).replace(os.sep, "/")
                        for path in target_invocations.rglob("*")
                        if path.is_file()
                    )
                ),
            )
    return tuple(dict.fromkeys(missing))


def _write_reused_evidence_receipts_index(
    *,
    authoring: Path,
    frozen: Path,
    receipts: tuple[str, ...],
) -> Path:
    """记录"哪些回执是从冻结根复制来的"（路径 + 复制时摘要），供用量汇总分类。"""

    from code2paper.agentic.reused_evidence_index import write_reused_evidence_index

    return write_reused_evidence_index(
        root=authoring.parent.parent,
        frozen_root=frozen,
        ledger_dir=authoring / "invocations",
        relative_paths=receipts,
    )


def _load_reused_evidence_receipts_index(fresh: Path) -> dict[str, str]:
    """读取复用证据索引：``相对路径 -> 复制时摘要``（缺失/不可读时按空处理）。"""

    from code2paper.agentic.reused_evidence_index import load_reused_evidence_index

    return load_reused_evidence_index(fresh)


def _frozen_project_tree_hash(frozen: Path) -> tuple[str, str]:
    """Return the single tree hash asserted by trusted frozen evidence.

    New runs persist the hash in the repository snapshot and source manifest.
    Older replay roots may only have the same immutable identity in the
    continuation seed or the execution record.  Those two locations are
    accepted only at their typed, fixed paths; arbitrary diagnostic JSON is
    deliberately not searched so a stale nested value cannot authorize a
    different repository.
    """

    values: list[tuple[str, str]] = []

    def _record(name: str, payload: Mapping[str, Any]) -> None:
        value = str(payload.get("project_tree_hash") or "").strip()
        # Diagnostic placeholders such as ``tree:unknown`` must never
        # authorize a repository.  Only the exact digest form emitted by the
        # repository snapshot builder is a valid migration anchor.
        if re.fullmatch(r"sha256:[0-9a-f]{64}", value):
            values.append((name, value))

    for name in ("repo_snapshot_v2", "repository_source_manifest_v1"):
        path = _frozen_artifact_path(frozen, name)
        if path is None:
            continue
        payload = _read_json_mapping(path)
        _record(name, payload)

    continuation_candidates = (
        (
            "research_continuation_seed_v1",
            _frozen_artifact_path(frozen, "research_continuation_seed_v1"),
        ),
        (
            "execution_record.research_continuation_seed",
            frozen / "execution_record.json",
        ),
    )
    for source_name, path in continuation_candidates:
        if path is None or not path.is_file():
            continue
        payload = _read_json_mapping(path)
        if source_name == "execution_record.research_continuation_seed":
            payload = payload.get("research_continuation_seed", {})
        if isinstance(payload, Mapping):
            _record(source_name, payload)

    contract_path = _frozen_artifact_path(frozen, "authoring_run_contract_v1")
    if contract_path is not None:
        _record("authoring_run_contract_v1", _read_json_mapping(contract_path))

    # V1 authoring outputs can be the only surviving immutable identity in a
    # historical root.  They are accepted solely as a migration anchor; the
    # caller still rebuilds and exact-hash-checks the supplied repository using
    # the shared source builder before any model boundary.
    for name in ("mechanism_context_set_v1", "formalization_result_v1"):
        path = _frozen_artifact_path(frozen, name)
        if path is not None:
            _record(name, _read_json_mapping(path))
    if not values:
        raise ValueError("unified_project_tree_hash_missing")
    hashes = {value for _name, value in values}
    if len(hashes) != 1:
        detail = ",".join(f"{name}={value}" for name, value in values)
        raise ValueError("unified_project_tree_hash_mismatch:frozen_artifacts_disagree:" + detail)
    return values[0][1], values[0][0]


def _frozen_authoring_scope_hints(artifacts: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Extract only explicit author/scope hints for the shared source builder."""

    author_texts: list[str] = []
    for name in ("intent_obligation_graph_v2", "research_agenda_v1"):
        payload = _read_json_mapping(artifacts / f"{name}.json")
        if not payload:
            continue
        for key in (
            "project_goal", "method_goal", "implementation_scope", "author_text",
            "author_statement", "description", "rationale", "question", "query",
        ):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                author_texts.append(value.strip())

        def visit(value: Any, key: str = "") -> None:
            if isinstance(value, Mapping):
                for child_key, child_value in value.items():
                    child_name = str(child_key)
                    if child_name in {
                        "author_text", "source_text", "description", "question",
                        "query", "method_goal", "project_goal",
                    } and isinstance(child_value, str) and child_value.strip():
                        author_texts.append(child_value.strip())
                    visit(child_value, child_name)
            elif isinstance(value, list):
                for child in value:
                    visit(child, key)

        visit(payload)

    entry_ids: list[str] = []
    scope_payload = _read_json_mapping(artifacts / "implementation_scope_v1.json")

    def collect_entries(value: Any, key: str = "") -> None:
        key_lower = key.casefold()
        if isinstance(value, Mapping):
            for child_key, child_value in value.items():
                collect_entries(child_value, str(child_key))
        elif isinstance(value, list):
            for child in value:
                collect_entries(child, key)
        elif isinstance(value, str) and value.strip() and key_lower in {
            "target_entry_symbol_ids", "target_entry_symbol_id", "entry_symbol_ids",
            "entry_symbol_id",
        }:
            entry_ids.append(value.strip())

    collect_entries(scope_payload)
    intent_payload = _read_json_mapping(artifacts / "intent_obligation_graph_v2.json")
    collect_entries(intent_payload)
    return (
        tuple(dict.fromkeys(author_texts)),
        tuple(dict.fromkeys(entry_ids)),
    )


def _rehydrate_repository_source_artifacts(
    *,
    frozen: Path,
    fresh: Path,
    artifacts: Path,
    repo: Path,
) -> tuple[tuple[str, ...], list[dict[str, Any]], str]:
    """Rebuild the source closure from ``--repo`` after an exact tree check.

    Product and replay use the same deterministic builder.  The replay never
    accepts a current repository merely because it is readable: its tree hash
    must equal the hash asserted by the frozen run before any Writer/model
    boundary is reached.
    """

    from code2paper.agentic.repository_authoring_artifacts import (
        rebuild_repository_authoring_artifacts,
        repository_authoring_identity_payload,
    )

    expected_tree_hash, hash_source = _frozen_project_tree_hash(frozen)
    author_texts, entry_symbol_ids = _frozen_authoring_scope_hints(artifacts)
    rebuilt = rebuild_repository_authoring_artifacts(
        repo,
        expected_project_tree_hash=expected_tree_hash,
        author_texts=author_texts,
        entry_symbol_ids=entry_symbol_ids,
    )
    # The frozen behavior graph is a historical Research observation.  Keep a
    # byte-preserving copy for audit, then derive the graph from the same
    # current source closure the Writer will consume.  The old graph is never
    # allowed to remain under the live ``behavior_graph_v1`` name.
    historical_graph = None
    historical_graph_load_failure = ""
    historical_graph_path = artifacts / "behavior_graph_v1.json"
    historical_copy_path = artifacts / "behavior_graph_historical_v1.json"
    if historical_graph_path.is_file():
        if not historical_copy_path.is_file():
            shutil.copy2(historical_graph_path, historical_copy_path)
        try:
            from code2paper.agentic.behavior_graph import CodeBehaviorGraphV1

            graph_payload = json.loads(
                historical_graph_path.read_text(encoding="utf-8")
            )
            if isinstance(graph_payload, Mapping):
                graph_payload = (
                    graph_payload.get("behavior_graph")
                    or graph_payload.get("graph")
                    or graph_payload
                )
            historical_graph = CodeBehaviorGraphV1.model_validate(graph_payload)
        except Exception as exc:  # noqa: BLE001 - history is diagnostic only
            historical_graph_load_failure = (
                f"{exc.__class__.__name__}:{str(exc)[:160]}"
            )

    from code2paper.agentic.mechanism_context_compiler import (
        build_current_behavior_graph,
    )

    entry_roots = tuple(
        str(item).strip()
        for item in (getattr(rebuilt.implementation_scope, "target_entry_symbol_ids", ()) or ())
        if str(item).strip()
    )
    current_graph = build_current_behavior_graph(
        symbol_index=rebuilt.symbol_index,
        source_provider=rebuilt.files,
        entry_symbol_ids=entry_roots,
    )
    if historical_graph is not None and current_graph is None:
        raise ValueError("unified_behavior_graph_rebuild_missing")

    from code2paper.agentic.publication_method_writer import (
        _behavior_graph_rebuild_report,
    )

    graph_report = _behavior_graph_rebuild_report(
        historical_graph,
        current_graph,
        entry_symbol_ids=entry_roots,
        snapshot_id=rebuilt.snapshot.snapshot_id,
        project_tree_hash=rebuilt.snapshot.project_tree_hash,
        historical_load_failure=historical_graph_load_failure,
    )
    graph_report_path = artifacts / "behavior_graph_rebuild_v1.json"
    graph_report_path.write_text(
        json.dumps(graph_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    payloads: dict[str, Any] = {
        "repo_snapshot_v2": rebuilt.snapshot.model_dump(mode="json"),
        "symbol_index_v2": rebuilt.symbol_index.model_dump(mode="json"),
        "implementation_scope_v1": rebuilt.implementation_scope.model_dump(mode="json"),
        "repository_source_manifest_v1": rebuilt.source_manifest.model_dump(mode="json"),
        "repository_authoring_artifacts_v1": repository_authoring_identity_payload(
            snapshot=rebuilt.snapshot,
            symbol_index=rebuilt.symbol_index,
            implementation_scope=rebuilt.implementation_scope,
            source_manifest=rebuilt.source_manifest,
        ),
    }
    # ``behavior_graph_v1`` is derived from the rebuilt source closure, not a
    # copied Research artifact.  Keep the historical copy out of the normal
    # artifact path map so no consumer can accidentally load it.
    if current_graph is not None:
        payloads["behavior_graph_v1"] = current_graph.model_dump(mode="json")
    names: list[str] = []
    entries: list[dict[str, Any]] = []
    for name, payload in payloads.items():
        target = artifacts / f"{name}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        names.append(name)
        entries.append(_manifest_entry(
            name=name,
            path=target,
            authority_class="repository-source",
            decision="rehydrated_from_repo",
            reason=(
                "exact_project_tree_hash:" + expected_tree_hash
                + ":frozen_hash_source:" + hash_source
            ),
        ))
    if historical_copy_path.is_file():
        entries.append(_manifest_entry(
            name="behavior_graph_historical_v1",
            path=historical_copy_path,
            authority_class="research-history",
            decision="preserved_historical_observation",
            reason="not_consumed_by_unified_writer",
        ))
    entries.append(_manifest_entry(
        name="behavior_graph_rebuild_v1",
        path=graph_report_path,
        authority_class="derived-source",
        decision="recorded_current_graph_identity",
        reason="current_graph_rebuilt_from_verified_source",
    ))
    return tuple(names), entries, ""


def _method_evidence_rebuild_template(
    *,
    artifacts: Path,
    intent_graph: Any,
    claims: Any,
) -> Any:
    """Build the MethodEvidence identity template for authoring rebuild.

    Frozen research may already carry a valid ``method_evidence.json``.  Snapshot
    fields ``repo_snapshot_id`` / ``project_tree_hash`` are claims identity, not
    MethodEvidence fields, and must never be passed through as extra inputs.
    """

    from pydantic import ValidationError

    from code2paper.core.schemas import MethodEvidence

    method_name = str(
        getattr(intent_graph, "method_goal", "") or getattr(intent_graph, "project_goal", "") or "Method"
    ).strip() or "Method"
    method_goal = str(
        getattr(intent_graph, "method_goal", "")
        or getattr(intent_graph, "project_goal", "")
        or "Describe the repository implementation."
    ).strip() or "Describe the repository implementation."
    implementation_scope = str(
        getattr(intent_graph, "implementation_scope", "") or "current repository implementation"
    ).strip() or "current repository implementation"
    project_id = str(getattr(claims, "repo_snapshot_id", "") or "").strip() or "repo:unknown"
    copied_path = artifacts / "method_evidence.json"
    if copied_path.is_file():
        try:
            raw = json.loads(copied_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            raw = None
        if isinstance(raw, dict):
            adapted = dict(raw)
            snapshot_id = str(
                adapted.pop("repo_snapshot_id", "") or project_id
            ).strip()
            adapted.pop("project_tree_hash", None)
            if not str(adapted.get("project_id") or "").strip():
                adapted["project_id"] = snapshot_id
            adapted.setdefault("method_name", method_name)
            adapted.setdefault("method_goal", method_goal)
            adapted.setdefault("implementation_scope", implementation_scope)
            try:
                return MethodEvidence.model_validate(adapted)
            except (TypeError, ValueError, ValidationError):
                pass
    return MethodEvidence(
        project_id=project_id,
        method_name=method_name,
        method_goal=method_goal,
        implementation_scope=implementation_scope,
        author_logic_priority=True,
        writing_constraints=[
            "Author intent may determine scope and organization, but only projected V3 claims authorize repository-positive prose.",
            "Unverified author intent, explicit gaps, external literature needs, and formalization needs must remain caveated or review-bound.",
        ],
    )


def _rebuild_derived_authoring(
    *,
    fresh: Path,
    artifacts: Path,
    llm_config: Any,
    llm_caller: Any = None,
    auxiliary_envelope: Any | None = None,
    auxiliary_tokenizer: Any | None = None,
) -> tuple[dict[str, str], list[dict[str, Any]], str]:
    """Rebuild derived authoring from frozen research authority only."""

    from code2paper.agentic.authoring_projection import (
        build_authoring_projection,
        projected_writer_inputs,
    )
    from code2paper.agentic.claim_verifier import ClaimVerificationReport
    from code2paper.core.schemas import ClaimEvidenceMap
    from code2paper.agentic.evidence_compiler_v3 import (
        load_atomic_claims_v3,
        load_code_facts_v1,
        load_evidence_packets_v3,
    )
    from code2paper.agentic.equation_claims import load_equation_claims
    from code2paper.agentic.intent_compiler_v2 import (
        IntentObligationGraphV2,
        build_story_spine_from_intent_graph,
    )
    from code2paper.agentic.method_argument_models import (
        ConfigurationClaimSetV1,
        MethodCompletenessMatrixV1,
    )
    from code2paper.agentic.method_architect import (
        build_method_section_plan_with_product_readiness,
    )
    from code2paper.agentic.method_argument_brief_compiler import compile_method_argument_briefs
    from code2paper.agentic.method_argument_brief_planner import build_mechanism_draft_planner
    from code2paper.agentic.method_argument_facet_aligner import (
        bind_facets_to_argument_briefs,
        decompose_and_align_argument_facets,
    )
    from code2paper.agentic.method_product_models import build_default_method_output_policy
    from code2paper.agentic.obligation_fact_alignment import ObligationCoverageReportV2
    from code2paper.llm.providers import has_provider_api_key
    from code2paper.llm.role_config import (
        METHOD_MECHANISM_DRAFT_PLANNER,
        METHOD_PROPOSITION_ARCHITECT,
        SEMANTIC_VERIFIER,
    )
    from code2paper.agentic.proposal_call_accounting import (
        build_budgeted_auxiliary_llm_caller,
        proposal_call_meter_from_envelope,
    )

    auxiliary_llm_caller = None
    if auxiliary_envelope is not None:
        auxiliary_llm_caller = build_budgeted_auxiliary_llm_caller(
            llm_config,
            auxiliary_envelope,
            accounting_root=fresh,
            tokenizer=auxiliary_tokenizer,
            base_caller=llm_caller,
            revision_id="replay-derived-authoring",
        )

    def _auxiliary_role_enabled(role: str) -> bool:
        return (
            auxiliary_envelope is not None
            and auxiliary_llm_caller is not None
            and proposal_call_meter_from_envelope(
                auxiliary_envelope,
                consumer_role=role,
                tokenizer=auxiliary_tokenizer,
            )
            is not None
        )

    claims = load_atomic_claims_v3(str(artifacts / "atomic_claims_v3.json"))
    facts = load_code_facts_v1(str(artifacts / "code_facts_v1.json"))
    from code2paper.agentic.scientific_claim_ir import (
        append_technical_claims,
        write_technical_claims_sidecar,
    )

    claims = append_technical_claims(claims, facts)
    (artifacts / "atomic_claims_v3.json").write_text(
        json.dumps(claims.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_technical_claims_sidecar(artifacts / "atomic_claims_v3.json", claims)
    equations = load_equation_claims(str(artifacts / "equation_claims_v1.json"))
    packets = load_evidence_packets_v3(str(artifacts / "evidence_packets_v3.json"))
    completeness = MethodCompletenessMatrixV1.model_validate_json(
        (artifacts / "method_completeness_matrix_v1.json").read_text(encoding="utf-8")
    )
    configurations = ConfigurationClaimSetV1.model_validate_json(
        (artifacts / "configuration_claims_v1.json").read_text(encoding="utf-8")
    )
    intent_graph = IntentObligationGraphV2.model_validate_json(
        (artifacts / "intent_obligation_graph_v2.json").read_text(encoding="utf-8")
    )
    coverage = None
    coverage_path = artifacts / "obligation_coverage_v2.json"
    if coverage_path.is_file():
        coverage = ObligationCoverageReportV2.model_validate_json(
            coverage_path.read_text(encoding="utf-8")
        )
    method_template = _method_evidence_rebuild_template(
        artifacts=artifacts,
        intent_graph=intent_graph,
        claims=claims,
    )
    story_spine = build_story_spine_from_intent_graph(
        intent_graph,
        claim_set=claims,
    )
    planner = None
    require_planner = False
    planner_enabled = _auxiliary_role_enabled(METHOD_MECHANISM_DRAFT_PLANNER)
    if (
        llm_config is not None
        and has_provider_api_key(llm_config)
        and planner_enabled
    ):
        planner = build_mechanism_draft_planner(
            llm_config,
            claims=claims,
            equations=equations,
            llm_caller=auxiliary_llm_caller,
        )
        require_planner = True
    argument_briefs = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=coverage,
        intent_graph=intent_graph,
        story_spine=story_spine,
        equations=equations,
        configurations=configurations,
        planner=planner,
        require_planner_for_unlicensed=require_planner,
    )
    facet_llm_enabled = (
        _auxiliary_role_enabled(METHOD_PROPOSITION_ARCHITECT)
        and _auxiliary_role_enabled(SEMANTIC_VERIFIER)
    )
    facet_result = decompose_and_align_argument_facets(
        briefs=argument_briefs,
        claims=claims,
        facts=facts,
        evidence_packets=packets,
        equations=equations,
        llm_config=(
            llm_config
            if (
                llm_config is not None
                and has_provider_api_key(llm_config)
                and facet_llm_enabled
            )
            else None
        ),
        llm_caller=auxiliary_llm_caller if facet_llm_enabled else None,
        intent_graph=intent_graph,
    )
    argument_briefs = bind_facets_to_argument_briefs(
        argument_briefs,
        facets=facet_result.facets,
        alignments=facet_result.alignments,
        policies=facet_result.policies,
    )
    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claims,
        completeness=completeness,
        equations=equations,
        configurations=configurations,
        method_name=str(intent_graph.method_goal or "Method"),
        story_spine=story_spine,
        policy=build_default_method_output_policy(),
        argument_briefs=argument_briefs,
        facts=facts,
        argument_facets=facet_result.facets,
        facet_alignments=facet_result.alignments,
        publication_field_candidates=facet_result.publication_field_candidates,
    )
    projection = build_authoring_projection(
        method_evidence=method_template,
        claim_map=ClaimEvidenceMap(),
        verification=ClaimVerificationReport(),
        atomic_claims_v3=claims,
        evidence_packets_v3=packets,
        equation_claims_v1=equations,
        intent_obligation_graph_v2=intent_graph,
        completeness=completeness,
    )
    method_evidence, claim_evidence_map = projected_writer_inputs(
        projection,
        template=method_template,
    )
    manifest_entries: list[dict[str, Any]] = []
    written: dict[str, str] = {}
    outputs: dict[str, Any] = {
        "method_argument_briefs_v1": argument_briefs,
        "method_argument_facets_v1": {
            "schema_version": "1.0",
            "facets": [
                item.model_dump(mode="json") for item in facet_result.facets
            ],
        },
        "facet_evidence_alignments_v1": {
            "schema_version": "1.0",
            "alignments": [
                item.model_dump(mode="json")
                for item in facet_result.alignments
            ],
        },
        "candidate_facet_policies_v1": {
            "schema_version": "1.0",
            "policies": [
                item.model_dump(mode="json") for item in facet_result.policies
            ],
        },
        # Keep the field-level surface that was used to build the plan.  If
        # this projection is omitted, the later Writer reloads only aggregate
        # facet alignments and recompiles fields without the original
        # ownership/readiness context, which changes the prose surface during
        # one replay.
        "publication_field_candidates_v1": {
            "schema_version": "1.0",
            "candidates": [
                item.model_dump(mode="json")
                for item in facet_result.publication_field_candidates
            ],
        },
        "typed_field_deferred_v1": {
            "schema_version": "1.0",
            "deferred": [
                item.model_dump(mode="json")
                for item in facet_result.typed_field_deferred
            ],
        },
        "method_argument_facet_alignment_trace_v1": {
            "schema_version": "1.0",
            "content_digest": facet_result.content_digest,
            "schema_failures": list(facet_result.schema_failures),
            "traces": list(facet_result.traces),
        },
        "method_section_plan_v2": plan,
        "authoring_projection_v1": projection,
        "method_evidence": method_evidence,
        "claim_evidence_map": claim_evidence_map,
    }
    for key, value in outputs.items():
        out_path = artifacts / f"{key}.json"
        if hasattr(value, "model_dump_json"):
            content = value.model_dump_json(indent=2)
        else:
            content = json.dumps(value, ensure_ascii=False, indent=2)
        out_path.write_text(content + "\n", encoding="utf-8")
        written[key] = str(out_path)
        manifest_entries.append(_manifest_entry(
            name=key,
            path=out_path,
            authority_class="derived-authoring",
            decision="rebuilt",
        ))
    return written, manifest_entries, ""


def _find_fresh_artifact(fresh: Path, name: str) -> Path | None:
    """Find one copied or rebuilt artifact without assuming its lane directory."""

    candidates = (
        fresh / "artifacts" / f"{name}.json",
        fresh / "artifacts" / "06_authoring" / f"{name}.json",
        fresh / "artifacts" / "07_validation" / f"{name}.json",
        fresh / "artifacts" / "research_product" / f"{name}.json",
    )
    return next((path for path in candidates if path.is_file()), None)


def _authoring_continuation_needed(fresh: Path) -> bool:
    """Whether a replay has an actionable writing-time authority gap.

    The Writer's initial success is deliberately not the deciding condition.
    This inspection only controls whether a repository-backed continuation is
    attempted; it does not authorize any evidence or mutate a status.
    """

    bundle_path = _find_fresh_artifact(
        fresh, "writing_research_callback_artifacts_v1"
    )
    if bundle_path is not None:
        try:
            payload = json.loads(bundle_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        if any(
            str(item.get("status") or "") in {"open", "partial"}
            for item in payload.get("requests") or ()
            if isinstance(item, dict)
        ):
            return True

    policy_path = _find_fresh_artifact(fresh, "candidate_facet_policies_v1")
    if policy_path is not None:
        try:
            payload = json.loads(policy_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        if any(
            str(item.get("alignment_status") or "") in {
                "partial", "mismatch", "unresolved"
            }
            or bool(item.get("schema_failures"))
            for item in payload.get("policies") or ()
            if isinstance(item, dict)
        ):
            return True

    section_path = _find_fresh_artifact(
        fresh, "formalization_section_results_v1"
    )
    if section_path is not None:
        try:
            payload = json.loads(section_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        if any(
            item.get("disposition") not in {None, ""}
            or str((item.get("outcome") or "")).lower() == "unresolved"
            for item in payload.get("sections") or ()
            if isinstance(item, dict)
        ):
            return True

    validation_path = next(
        (
            _find_fresh_artifact(fresh, name)
            for name in (
                "text_evidence_validation",
                "agentic_text_evidence_validation",
            )
            if _find_fresh_artifact(fresh, name) is not None
        ),
        None,
    )
    if validation_path is not None:
        try:
            payload = json.loads(validation_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        status = str(payload.get("status") or "").casefold()
        issue_counts = (
            "unsupported_claims",
            "unsupported_positive_claims",
            "unverified_claims",
            "critical_failures",
            "major_failures",
        )
        has_positive_issue_count = any(
            isinstance(payload.get(key), (int, float))
            and int(payload.get(key) or 0) > 0
            for key in issue_counts
        )
        issue_lists = (
            "issues",
            "failures",
            "quality_failures",
            "unresolved_issues",
            "evidence_gaps",
        )
        has_issue_list = any(
            bool(payload.get(key))
            for key in issue_lists
        )
        if (
            status in {"failed", "blocked", "error", "warnings", "incomplete"}
            or has_positive_issue_count
            or has_issue_list
        ):
            return True
    return False


def _build_replay_continuation_context(
    *,
    fresh: Path,
    artifacts: Path,
    repo: Path,
    llm_config: Any,
) -> tuple[Any, Any, str]:
    """Build a Research runtime and honest seed from frozen authority."""

    from code2paper.agentic.autonomous_method_agent import (
        build_product_research_runtime,
    )
    from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2
    from code2paper.agentic.research_models import ResearchAgendaV1
    from code2paper.agentic.writing_callback_fulfillment import (
        build_research_continuation_seed,
    )

    intent_path = artifacts / "intent_obligation_graph_v2.json"
    agenda_path = artifacts / "research_agenda_v1.json"
    if not intent_path.is_file() or not agenda_path.is_file():
        raise FileNotFoundError("frozen intent or research agenda is missing")
    intent_graph = IntentObligationGraphV2.model_validate_json(
        intent_path.read_text(encoding="utf-8")
    )
    agenda = ResearchAgendaV1.model_validate_json(
        agenda_path.read_text(encoding="utf-8")
    )
    runtime = build_product_research_runtime(
        repo_path=repo,
        author_intent_path=None,
        claims=None,
        run_id=agenda.run_id,
        llm_config=llm_config,
        artifact_root=fresh / "artifacts" / "research_tool_data",
        intent_graph_override=intent_graph,
        agenda_override=agenda,
    )
    runtime = runtime.model_copy(update={
        "intent_target_proposal_report": {
            "status": "reconstructed_from_frozen_authority",
            "origin": "reconstructed_from_frozen_authority",
            "past_decision_trace_available": False,
        },
    })
    artifact_paths = {
        path.stem: str(path)
        for path in artifacts.glob("*.json")
        if path.is_file()
    }
    artifact_paths.update({
        "writing_research_callback_artifacts_v1": str(
            fresh / "artifacts" / "06_authoring"
            / "writing_research_callback_artifacts_v1.json"
        ),
    })
    seed, seed_path = build_research_continuation_seed(
        runtime=runtime,
        artifact_paths=artifact_paths,
        out_root=fresh,
    )
    return runtime, seed, seed_path


def _run_deterministic_replay_preflight(
    *,
    artifact_paths: Mapping[str, str],
    effective_mode: str,
) -> dict[str, Any]:
    """Validate deterministic replay inputs before any authoring model call."""

    if effective_mode not in {"unified", "shadow_unified"}:
        return {
            "status": "not_applicable",
            "effective_mode": effective_mode,
            "model_calls": 0,
        }

    from code2paper.agentic.publication_method_writer import (
        _behavior_graph_summary,
        _load_authenticated_candidate_handoff,
        _load_repository_authoring_context,
    )

    context = _load_repository_authoring_context(artifact_paths)
    load_failures = tuple(
        str(item).strip()
        for item in (context.get("load_failures") or ())
        if str(item).strip()
    )
    handoff, handoff_failures = _load_authenticated_candidate_handoff(artifact_paths)
    failures = tuple(dict.fromkeys(
        (*load_failures, *(str(item).strip() for item in handoff_failures if str(item).strip()))
    ))
    if handoff is None:
        failures = tuple(dict.fromkeys((*failures, "candidate_handoff_missing_or_invalid")))
    return {
        "schema_version": "1.0",
        "status": "fail" if failures else "pass",
        "effective_mode": effective_mode,
        "model_calls": 0,
        "failure_codes": list(failures),
        "candidate_handoff": {
            "status": "eligible" if handoff is not None and handoff.eligible else "rejected",
            "content_digest": str(getattr(handoff, "content_digest", "") or "")
            if handoff is not None else "",
            "revalidation_failures": list(handoff_failures),
        },
        "behavior_graph": _behavior_graph_summary(context.get("behavior_graph")),
        "behavior_graph_rebuild": context.get("behavior_graph_rebuild") or {},
        "source_load_failures": list(load_failures),
    }


def _default_frozen_author_intent(frozen: Path) -> Path | None:
    candidate = frozen / "artifacts" / "intent_obligation_graph_v2.json"
    return candidate if candidate.is_file() else None


def _default_frozen_research_import(frozen: Path) -> Path | None:
    candidate = frozen / "artifacts" / "research_product" / "research_stage_checkpoint_v1.json"
    return candidate if candidate.is_file() else None


def _open_replay_execution_identity(
    *,
    frozen: Path,
    fresh: Path,
    arguments: Any,
    llm_config: Any,
) -> dict[str, Any]:
    """WP1 准入：回放入口与产品入口共用 ``open_authoring_execution``。

    返回写入 telemetry 的诊断；不可信输入一律 fail-closed（抛
    ``RunOpenRejected``），调用方据此零生成退出。
    """

    from code2paper.agentic.autonomous_method_agent import open_authoring_execution
    from code2paper.agentic.authoring_execution_identity import (
        RESEARCH_IMPORT_UNVERIFIABLE,
        RunOpenRejected,
        verify_research_import,
    )

    mode = str(getattr(arguments, "run_open_mode", "") or "").strip().casefold()
    if not mode:
        # 未显式要求身份（直接进程内调用/旧脚本用法）：如实记录"未请求"，
        # 不得让产物看起来像身份受控的 run。
        return {"status": "not_requested"}

    repo_value = str(getattr(arguments, "repo", "") or "").strip()
    if not repo_value:
        raise RunOpenRejected(
            _rejected_decision(mode, "execution_identity_target_repo_required")
        )
    repo_path = Path(repo_value).expanduser().resolve()
    if not repo_path.is_dir():
        raise RunOpenRejected(
            _rejected_decision(mode, "execution_identity_target_repo_missing")
        )

    intent_path = Path(str(getattr(arguments, "author_intent", "") or "")).expanduser()
    if not str(getattr(arguments, "author_intent", "") or "").strip():
        intent_path = _default_frozen_author_intent(frozen)
    claims_value = str(getattr(arguments, "claims", "") or "").strip()

    import_path = Path(str(getattr(arguments, "research_import", "") or "")).expanduser()
    if not str(getattr(arguments, "research_import", "") or "").strip():
        import_path = _default_frozen_research_import(frozen)

    # 回放永远从冻结研究证据出发（§14.2 L1/L2）：所有模式都要求可校验的导入，
    # 并把导入摘要绑进身份，否则两份不同冻结输入会得到同一个 execution_id。
    verifiable, import_digest, import_detail = verify_research_import(import_path)
    if not verifiable:
        raise RunOpenRejected(_rejected_decision(mode, RESEARCH_IMPORT_UNVERIFIABLE, import_detail))

    identity, _lease = open_authoring_execution(
        out_root=fresh,
        run_open_mode=mode,
        repo_path=repo_path,
        author_intent_path=intent_path,
        claims_path=(claims_value or None),
        llm_config=llm_config,
        research_stage_checkpoint=import_path,
        research_import_digest=import_digest,
    )
    return {
        "status": "opened",
        "mode": mode,
        "execution_id": identity.execution_id,
        "content_digest": identity.content_digest,
        "engine_commit_sha": identity.engine_commit_sha,
        "engine_source_digest": identity.engine_source_digest,
        "target_repo_snapshot_digest": identity.target_repo_snapshot_digest,
        "target_project_tree_hash": identity.target_project_tree_hash,
        "intent_content_digest": identity.intent_content_digest,
        "claims_digest": identity.claims_digest,
        "research_import_digest": identity.research_import_digest,
        "author_intent_path": str(intent_path) if intent_path else "",
        "research_import_path": str(import_path) if import_path else "",
        "identity_path": str(fresh / "artifacts" / "research_product" / "authoring_execution_identity_v2.json"),
    }


def _rejected_decision(mode: str, code: str, detail: str = "") -> Any:
    from code2paper.agentic.authoring_execution_identity import RunOpenDecision

    return RunOpenDecision(
        allowed=False,
        code=code,
        requested_mode=mode,
        effective_mode=mode,
        allowed_next_action="provide_target_repo_and_verified_research_import",
        detail=detail or "回放身份准入需要目标仓库与已校验的研究导入",
    )


def _replay(
    *,
    frozen: Path,
    fresh: Path,
    arguments: argparse.Namespace,
    telemetry: dict,
) -> int:
    telemetry["terminal_stage"] = "input"
    telemetry["terminal_reason"] = ""
    authoring_stage = str(
        getattr(arguments, "authoring_stage", "full") or "full"
    ).strip().casefold()
    if authoring_stage not in {"full", "prepare", "execute-prepared"}:
        telemetry["terminal_reason"] = "authoring_stage_invalid:" + authoring_stage
        _remember_first_failure(
            telemetry,
            stage="input",
            reason=telemetry["terminal_reason"],
            error_code="authoring_stage_invalid",
        )
        return 2
    telemetry["authoring_stage"] = authoring_stage
    legacy_stage_flags = (
        "resume",
        "rebuild_authoring",
        "reuse_derived_authoring",
        "reuse_authoring_callbacks",
    )
    if authoring_stage != "full" and any(
        bool(getattr(arguments, flag, False)) for flag in legacy_stage_flags
    ):
        telemetry["terminal_reason"] = (
            "authoring_stage_mutually_exclusive_with_legacy_flags"
        )
        _remember_first_failure(
            telemetry,
            stage="input",
            reason=telemetry["terminal_reason"],
            error_code="authoring_stage_mutually_exclusive",
        )
        return 2
    # A replay is one accounting boundary.  Reset the process-local collector
    # so direct test calls or a prior in-process run cannot contaminate its
    # token total.
    from code2paper.llm.generation_trace import reset_run_generation_traces

    reset_run_generation_traces()
    # Load the live profile into the environment (same as the probe).
    profile_path = _resolve_profile_path(arguments.profile, fresh=fresh)
    _apply_replay_profile(
        profile_path,
        force=bool(getattr(arguments, "force_profile", False)),
    )

    from code2paper.llm.providers import load_llm_config_from_env

    llm_config = load_llm_config_from_env()
    # 身份/准入已由 main() 在任何进程产物之前完成（见 _open_replay_execution_identity）；
    # 直接进程内调用 `_replay` 时 telemetry 里没有该键，如实视为"未请求"。
    telemetry.setdefault("execution_identity", {"status": "not_requested"})
    requested_mode = str(getattr(arguments, "authoring_context_mode", "") or "").strip().casefold()
    profile_mode = str(os.environ.get("CODE2PAPER_AUTHORING_CONTEXT_MODE", "") or "").strip().casefold()
    effective_mode = requested_mode or profile_mode or "legacy"
    mode_source = (
        "argument" if requested_mode
        else "profile" if profile_mode and profile_path.is_file()
        else "environment" if profile_mode
        else "default"
    )
    telemetry["authoring_context"] = {
        "requested_mode": requested_mode or effective_mode,
        "effective_mode": effective_mode,
        "mode_source": mode_source,
    }

    # Copy frozen research artifacts into the fresh root (never move/delete).
    artifacts = fresh / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    manifest_entries: list[dict[str, Any]] = []
    if authoring_stage == "execute-prepared":
        # The prepared root is the input contract.  Never recopy from the
        # frozen root or overwrite a settled receipt/response on resume.
        for name in (*RESEARCH_COPY_ARTIFACTS, *OPTIONAL_RESEARCH_ARTIFACTS,
                     *FORMALIZER_PHASE_COPY_ARTIFACTS):
            target = (
                artifacts / "06_authoring" / f"{name}.json"
                if name in FORMALIZER_PHASE_COPY_ARTIFACTS
                else artifacts / f"{name}.json"
            )
            if target.is_file():
                copied.append(name)
                manifest_entries.append(_manifest_entry(
                    name=name,
                    path=target,
                    authority_class=(
                        "formalizer-phase"
                        if name in FORMALIZER_PHASE_COPY_ARTIFACTS
                        else "research"
                    ),
                    decision="reused-prepared-root",
                ))
        missing = [
            name for name in RESEARCH_COPY_ARTIFACTS
            if not (artifacts / f"{name}.json").is_file()
        ]
        missing.extend(
            name for name in FORMALIZER_PHASE_COPY_ARTIFACTS
            if not (artifacts / "06_authoring" / f"{name}.json").is_file()
        )
        invocation_root = artifacts / "06_authoring" / "invocations"
        if not invocation_root.is_dir() or not any(
            path.is_file() for path in invocation_root.rglob("*")
        ):
            missing.append("formalizer_phase_invocations")
        else:
            manifest_entries.append({
                "artifact_name": "formalizer_phase_invocations",
                "path": str(invocation_root),
                "digest": _digest_text("\n".join(
                    f"{path.relative_to(invocation_root)}:{_digest_file(path)}"
                    for path in sorted(invocation_root.rglob("*"))
                    if path.is_file()
                )),
                "schema": "unified_invocation_ledger_v1",
                "authority_class": "formalizer-phase",
                "decision": "reused-prepared-root",
                "reason": "execute_prepared",
            })
        print(
            "[replay] reused prepared root artifacts: "
            + ", ".join(copied)
        )
    else:
        for name in RESEARCH_COPY_ARTIFACTS:
            source_candidates = [
                frozen / "artifacts" / "06_authoring" / f"{name}.json",
                frozen / "artifacts" / f"{name}.json",
            ]
            source = next((path for path in source_candidates if path.is_file()), None)
            if source is None:
                continue
            target = artifacts / f"{name}.json"
            shutil.copy2(source, target)
            copied.append(name)
            manifest_entries.append(_manifest_entry(
                name=name,
                path=target,
                authority_class="research",
                decision="copied",
            ))
        print(f"[replay] copied {len(copied)} research artifacts: {', '.join(copied)}")
        missing = [
            name for name in RESEARCH_COPY_ARTIFACTS
            if not (artifacts / f"{name}.json").is_file()
        ]
    if authoring_stage != "execute-prepared":
        for name in OPTIONAL_RESEARCH_ARTIFACTS:
            source_candidates = [
                frozen / "artifacts" / "06_authoring" / f"{name}.json",
                frozen / "artifacts" / f"{name}.json",
            ]
            source = next((path for path in source_candidates if path.is_file()), None)
            if source is not None:
                shutil.copy2(source, artifacts / f"{name}.json")
                copied.append(name)
                manifest_entries.append(_manifest_entry(
                    name=name,
                    path=artifacts / f"{name}.json",
                    authority_class="research",
                    decision="copied",
                ))
                print(f"[replay] copied optional research artifact: {name}")
        if authoring_stage == "prepare":
            phase_missing = _copy_frozen_formalizer_phase(
                frozen=frozen,
                fresh=fresh,
                artifacts=artifacts,
                copied=copied,
                manifest_entries=manifest_entries,
            )
            missing = [*missing, *phase_missing]

    if missing:
        telemetry["terminal_stage"] = "input"
        telemetry["terminal_reason"] = "missing_frozen_artifacts:" + ",".join(missing)
        _remember_first_failure(
            telemetry,
            stage="input",
            reason=telemetry["terminal_reason"],
            error_code="missing_frozen_artifacts",
        )
        print(f"[replay] FATAL missing frozen artifacts: {missing}")
        return 2

    # Unified/shadow replay must use the same source closure as product runs.
    # A frozen run from before source artifacts were persisted can still be
    # reconstructed, but only from an explicitly supplied repository whose
    # exact project tree hash matches the frozen authority.
    if (
        authoring_stage != "execute-prepared"
        and effective_mode in {"unified", "shadow_unified"}
        and str(
        getattr(arguments, "repo", "") or ""
        ).strip()
    ):
        replay_repo = Path(arguments.repo).expanduser().resolve()
        if not replay_repo.is_dir():
            telemetry["terminal_stage"] = "input"
            telemetry["terminal_reason"] = "unified_replay_repo_missing"
            _remember_first_failure(
                telemetry,
                stage="input",
                reason=telemetry["terminal_reason"],
                error_code="unified_replay_repo_missing",
            )
            print(f"[replay] FATAL --repo is not a directory: {replay_repo}")
            return 2
        try:
            rehydrated_names, rehydrated_entries, _rehydration_reason = (
                _rehydrate_repository_source_artifacts(
                    frozen=frozen,
                    fresh=fresh,
                    artifacts=artifacts,
                    repo=replay_repo,
                )
            )
        except Exception as exc:  # noqa: BLE001 - typed replay boundary
            reason = _safe_failure_text(exc)
            code = (
                "unified_project_tree_hash_mismatch"
                if "project_tree_hash_mismatch" in reason
                else "unified_replay_rehydration_failed"
            )
            telemetry["terminal_stage"] = "input"
            telemetry["terminal_reason"] = code + ":" + reason
            telemetry["terminal_error_code"] = code
            _remember_first_failure(
                telemetry,
                stage="input",
                reason=telemetry["terminal_reason"],
                error_code=code,
            )
            print(f"[replay] FATAL source rehydration failed: {reason}")
            return 2
        rehydrated_set = set(rehydrated_names)
        copied[:] = [name for name in copied if name not in rehydrated_set]
        manifest_entries[:] = [
            item for item in manifest_entries
            if str(item.get("artifact_name") or "") not in rehydrated_set
        ]
        copied.extend(rehydrated_names)
        manifest_entries.extend(rehydrated_entries)
        telemetry["repository_source_rehydration"] = {
            "status": "rehydrated",
            "repo": str(replay_repo),
            "artifact_names": list(rehydrated_names),
            "project_tree_hash": _read_json_mapping(
                artifacts / "repo_snapshot_v2.json"
            ).get("project_tree_hash", ""),
        }
        print(
            "[replay] rehydrated repository source artifacts: "
            + ", ".join(rehydrated_names)
        )

    execution_digest = _execution_manifest_digest(
        profile_path=profile_path,
        frozen=frozen,
        copied_artifact_names=tuple(copied),
        authoring_context_mode=effective_mode,
    )
    writer_execution_digest = execution_digest
    if authoring_stage == "execute-prepared":
        writer_execution_digest = _prepared_continuation_execution_digest(
            fresh=fresh,
            current_execution_digest=execution_digest,
            telemetry=telemetry,
        )
        if writer_execution_digest != execution_digest:
            continuation_info = telemetry.get("authoring_prepare_continuation") or {}
            continuation_codes = ",".join(
                str(value) for value in (continuation_info.get("failure_codes") or ())
                if str(value).strip()
            )
            print(
                "[replay] admitted one bounded prepared-root continuation"
                + (f" ({continuation_codes})" if continuation_codes else "")
            )
    if not profile_path.is_file():
        telemetry["terminal_stage"] = "input"
        telemetry["terminal_reason"] = "authoring_rebuild_profile_missing"
        _remember_first_failure(
            telemetry,
            stage="input",
            reason=telemetry["terminal_reason"],
            error_code="authoring_rebuild_profile_missing",
        )
        print("[replay] FATAL authoring rebuild manifest missing profile digest")
        return 2

    for derived_name in DERIVED_AUTHORING_ARTIFACTS:
        manifest_entries.append(_manifest_entry(
            name=derived_name,
            path=artifacts / f"{derived_name}.json",
            authority_class="derived-authoring",
            decision="refused",
            reason="not_copied_by_default",
        ))

    def _copied_artifact_path(name: str) -> Path:
        return (
            artifacts / "06_authoring" / f"{name}.json"
            if name in FORMALIZER_PHASE_COPY_ARTIFACTS
            else artifacts / f"{name}.json"
        )

    # Deterministic source/graph/Candidate checks must run before the optional
    # argument-brief/facet rebuild, whose planner/verifier calls are expensive.
    # The preflight has no caller and records an explicit zero-call boundary.
    preflight_artifact_paths = {
        name: str(_copied_artifact_path(name))
        for name in copied
    }
    historical_graph_path = artifacts / "behavior_graph_historical_v1.json"
    if historical_graph_path.is_file():
        preflight_artifact_paths["behavior_graph_historical_v1"] = str(
            historical_graph_path
        )
    preflight = _run_deterministic_replay_preflight(
        artifact_paths=preflight_artifact_paths,
        effective_mode=effective_mode,
    )
    telemetry["deterministic_preflight"] = preflight
    from code2paper.core.output_names import method_output

    preflight_path = method_output(fresh, "deterministic_preflight_v1")
    preflight_path.write_text(
        json.dumps(preflight, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    telemetry["deterministic_preflight_path"] = str(preflight_path)
    manifest_entries.append(_manifest_entry(
        name="deterministic_preflight_v1",
        path=preflight_path,
        authority_class="derived-source",
        decision=("passed" if preflight.get("status") == "pass" else "failed"),
        reason="model_calls:0",
    ))
    if preflight.get("status") == "fail":
        telemetry["terminal_stage"] = "input"
        telemetry["terminal_reason"] = (
            "deterministic_preflight_failed:"
            + ",".join(str(item) for item in preflight.get("failure_codes", ()))
        )
        _remember_first_failure(
            telemetry,
            stage="input",
            reason=telemetry["terminal_reason"],
            error_code="deterministic_preflight_failed",
        )
        print(
            "[replay] FATAL deterministic preflight failed: "
            + ",".join(str(item) for item in preflight.get("failure_codes", ()))
        )
        if getattr(arguments, "persist_authoring_rebuild_manifest", False):
            _write_authoring_rebuild_manifest(
                fresh=fresh,
                entries=manifest_entries,
                execution_digest=execution_digest,
                refused_reason=telemetry["terminal_reason"],
            )
        return 2

    if getattr(arguments, "deterministic_preflight_only", False):
        telemetry["preflight_only"] = True
        telemetry["terminal_stage"] = "input"
        telemetry["terminal_reason"] = "deterministic_preflight_only"
        if getattr(arguments, "persist_authoring_rebuild_manifest", False):
            _write_authoring_rebuild_manifest(
                fresh=fresh,
                entries=manifest_entries,
                execution_digest=execution_digest,
                refused_reason="deterministic_preflight_only",
            )
        print("[replay] deterministic preflight passed; stopping before model calls")
        return 0

    unified_tokenizer = None
    if effective_mode in {"unified", "shadow_unified"}:
        try:
            unified_tokenizer = _build_replay_unified_tokenizer(
                llm_config=llm_config,
                fresh=fresh,
            )
        except Exception as exc:  # noqa: BLE001 - live meter is an admission gate
            telemetry["terminal_stage"] = "budget"
            telemetry["terminal_reason"] = (
                "unified_tokenizer_admission_failed:" + _safe_failure_text(exc)
            )
            _remember_first_failure(
                telemetry,
                stage="budget",
                reason=telemetry["terminal_reason"],
                error_code="unified_tokenizer_admission_failed",
            )
            print(
                "[replay] FATAL exact unified tokenizer admission failed: "
                + _safe_failure_text(exc)
            )
            return 2
        telemetry["unified_tokenizer"] = {
            "status": "admitted",
            "identity": str(getattr(unified_tokenizer, "identity", "") or ""),
            "contract_path": str(
                fresh / "artifacts" / "06_authoring"
                / "unified_tokenizer_contract_v1.json"
            ),
        }

    auxiliary_envelope = None
    try:
        auxiliary_envelope = _build_replay_auxiliary_budget_envelope(
            llm_config=llm_config,
            run_digest=writer_execution_digest,
        )
    except Exception as exc:  # noqa: BLE001 - a malformed opt-in is a gate
        telemetry["terminal_stage"] = "input"
        telemetry["terminal_reason"] = (
            "auxiliary_budget_profile_invalid:" + _safe_failure_text(exc)
        )
        _remember_first_failure(
            telemetry,
            stage="input",
            reason=telemetry["terminal_reason"],
            error_code="auxiliary_budget_profile_invalid",
        )
        print(
            "[replay] FATAL auxiliary budget profile invalid: "
            + _safe_failure_text(exc)
        )
        return 2
    if auxiliary_envelope is not None:
        # The replay execution identity is known before the Writer archive is
        # assembled.  Bind all optional pre-page calls and the later proposal
        # meter to this same run identity.
        os.environ["CODE2PAPER_AUXILIARY_RUN_DIGEST"] = writer_execution_digest
    telemetry["auxiliary_budget"] = (
        {
            "status": "enabled",
            "envelope_digest": str(
                getattr(auxiliary_envelope, "content_digest", "") or ""
            ),
            "run_digest": str(
                getattr(auxiliary_envelope, "run_digest", "") or ""
            ),
            "roles": sorted(
                str(role)
                for role in (
                    getattr(auxiliary_envelope, "max_calls_by_role", {}) or {}
                )
                if str(role)
                not in {"formalizer", "writer", "realizer", "binder"}
            ),
        }
        if auxiliary_envelope is not None
        else {"status": "not_declared", "model_calls": 0}
    )

    # A frozen authoring replay may intentionally exercise the current
    # Formalizer/Writer/Binder against an already-built MethodUnit surface.
    # Keep that mode explicit, while still rebuilding the transaction trace
    # and structural exit below.  Callback bundles are excluded here because
    # their file-backed references require the dedicated rebase/integrity
    # path guarded by ``--reuse-authoring-callbacks``.
    if getattr(arguments, "reuse_derived_authoring", False):
        for derived_name in DERIVED_AUTHORING_ARTIFACTS:
            if derived_name in {
                # Callback references have a dedicated rebase path below.
                "writing_research_callback_artifacts_v1",
                # These are transaction results, not planning authority.  A
                # historical copy can describe a different plan revision and
                # would make a blocked replay look like a zero-coverage run.
                "publication_paragraph_transaction_assessments_v1",
                "authoring_structural_exit_v1",
            }:
                continue
            source_candidates = [
                # The final authoring lane is authoritative.  Historical
                # replay roots also contain pre-writer or stale diagnostics
                # with a different plan digest.
                frozen / "artifacts" / "06_authoring" / f"{derived_name}.json",
                frozen / "artifacts" / f"{derived_name}.json",
            ]
            source = next((path for path in source_candidates if path.is_file()), None)
            if source is None:
                continue
            target = artifacts / f"{derived_name}.json"
            shutil.copy2(source, target)
            copied.append(derived_name)
            manifest_entries.append(_manifest_entry(
                name=derived_name,
                path=target,
                authority_class="derived-authoring",
                decision="copied",
                reason="reuse_frozen_authoring",
            ))
        _persist_reused_method_unit_surface(fresh)

    if arguments.rebuild_authoring:
        telemetry["terminal_stage"] = "method_unit_reassembly"
        rebuilt_paths, rebuilt_entries, refused = _rebuild_derived_authoring(
            fresh=fresh,
            artifacts=artifacts,
            llm_config=llm_config,
            auxiliary_envelope=auxiliary_envelope,
        )
        if refused:
            telemetry["terminal_stage"] = "method_unit_reassembly"
            telemetry["terminal_reason"] = "authoring_rebuild_refused:" + str(refused)
            _remember_first_failure(
                telemetry,
                stage="method_unit_reassembly",
                reason=telemetry["terminal_reason"],
                error_code="method_unit_reassembly_refused",
            )
            print(f"[replay] FATAL authoring rebuild refused: {refused}")
            if arguments.persist_authoring_rebuild_manifest:
                _write_authoring_rebuild_manifest(
                    fresh=fresh,
                    entries=manifest_entries,
                    execution_digest=execution_digest,
                    refused_reason=refused,
                )
            return 2
        copied.extend(rebuilt_paths.keys())
        manifest_entries.extend(rebuilt_entries)
        for derived_name in DERIVED_AUTHORING_ARTIFACTS:
            if derived_name in rebuilt_paths:
                continue
            manifest_entries.append(_manifest_entry(
                name=derived_name,
                path=artifacts / f"{derived_name}.json",
                authority_class="derived-authoring",
                decision="refused",
                reason="rebuild_did_not_emit",
            ))

    research_checkpoint_path = (
        artifacts / "research_stage_checkpoint_v1.json"
        if (artifacts / "research_stage_checkpoint_v1.json").is_file()
        else None
    )

    # R3: callback bundle reuse is explicit only.
    reused_fulfilled_callback_ids: list[str] = []
    if arguments.reuse_authoring_callbacks:
        frozen_bundle_candidates = [
            frozen / "artifacts" / "06_authoring" / "writing_research_callback_artifacts_v1.json",
            frozen / "artifacts" / "writing_research_callback_artifacts_v1.json",
        ]
        frozen_bundle_path = next(
            (path for path in frozen_bundle_candidates if path.is_file()), None
        )
        if frozen_bundle_path is not None:
            from code2paper.agentic.publication_method_writer import (
                rebase_callback_bundle_artifacts,
            )

            rebase_report = rebase_callback_bundle_artifacts(
                bundle_path=frozen_bundle_path,
                frozen_root=frozen,
                fresh_root=fresh,
            )
            if rebase_report["failures"]:
                telemetry["terminal_stage"] = "callback"
                telemetry["terminal_reason"] = (
                    "callback_artifact_integrity:" + ";".join(
                        str(item) for item in rebase_report["failures"]
                    )
                )
                _remember_first_failure(
                    telemetry,
                    stage="callback",
                    reason=telemetry["terminal_reason"],
                    error_code="callback_artifact_integrity",
                )
                print(
                    "[replay] FATAL callback artifact integrity failures: "
                    + "; ".join(rebase_report["failures"])
                )
                return 2
            bundle_payload = rebase_report["bundle"]
            if bundle_payload is None:
                telemetry["terminal_stage"] = "callback"
                telemetry["terminal_reason"] = "callback_bundle_rebase_empty"
                _remember_first_failure(
                    telemetry,
                    stage="callback",
                    reason=telemetry["terminal_reason"],
                    error_code="callback_bundle_rebase_empty",
                )
                print("[replay] FATAL callback bundle rebase produced no bundle")
                return 2
            fresh_bundle_path = artifacts / "writing_research_callback_artifacts_v1.json"
            fresh_bundle_path.write_text(
                json.dumps(bundle_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            copied.append("writing_research_callback_artifacts_v1")
            manifest_entries.append(_manifest_entry(
                name="writing_research_callback_artifacts_v1",
                path=fresh_bundle_path,
                authority_class="derived-authoring",
                decision="copied",
                reason="reuse_authoring_callbacks",
            ))
            reused_fulfilled_callback_ids = rebase_report["reused_fulfilled_callback_ids"]
            print(
                "[replay] rebased callback bundle with "
                f"{len(rebase_report['copied_refs'])} file-backed artifact(s); "
                f"reused_fulfilled_callback_ids={reused_fulfilled_callback_ids}"
            )

    if arguments.persist_authoring_rebuild_manifest:
        _write_authoring_rebuild_manifest(
            fresh=fresh,
            entries=manifest_entries,
            execution_digest=execution_digest,
        )

    artifact_paths = {
        name: str(_copied_artifact_path(name))
        for name in copied
    }
    if historical_graph_path.is_file():
        artifact_paths["behavior_graph_historical_v1"] = str(
            historical_graph_path
        )

    from code2paper.agentic.publication_method_writer import (
        effective_writer_transaction_status,
        run_publication_method_writer,
    )

    telemetry["terminal_stage"] = "writer"
    result, paths = run_publication_method_writer(
        out_root=fresh,
        artifact_paths=artifact_paths,
        llm_config=llm_config,
        run_id=arguments.run_id,
        resume_section_ids=tuple(arguments.resume),
        llm_caller=None,
        editor_caller=None,
        rewrite_caller=None,
        formalization_caller=None,
        architect_proposal_caller=None,
        unified_tokenizer=unified_tokenizer,
        authoring_context_mode=requested_mode or None,
        authoring_context_mode_source=mode_source,
        formalizer_phase_checkpoint=(
            fresh
            if authoring_stage in {"prepare", "execute-prepared"}
            else None
        ),
        authoring_stage=authoring_stage,
        authoring_execution_manifest_digest=writer_execution_digest,
    )
    print(f"[replay] writer status: {result.status} blocked={result.blocked_reason}")
    print(f"[replay] paths: {json.dumps({k: v for k, v in sorted(paths.items()) if v}, indent=1)[:1200]}")
    print(f"[replay] reused_fulfilled_callback_ids: {reused_fulfilled_callback_ids}")
    print(f"[replay] writer_resumed_section_ids: {list(result.resumed_section_ids)}")
    telemetry["reused_fulfilled_callback_ids"] = reused_fulfilled_callback_ids
    telemetry["writer_resumed_section_ids"] = list(result.resumed_section_ids)
    telemetry["publication_status"] = result.status
    telemetry["writer_transaction_status"] = effective_writer_transaction_status(result)
    telemetry["candidate_completion_status"] = str(
        getattr(result, "candidate_completion_status", "incomplete") or "incomplete"
    )
    telemetry["candidate_complete"] = bool(
        getattr(result, "candidate_complete", False)
    )
    telemetry["verified_complete"] = bool(
        getattr(result, "verified_complete", False)
    )
    telemetry["writer_status"] = (
        "success"
        if telemetry["writer_transaction_status"] == "success"
        and telemetry["candidate_complete"]
        else "blocked"
        if telemetry["writer_transaction_status"] == "blocked"
        else "incomplete"
    )
    telemetry["writer_blocked_reason"] = result.blocked_reason
    if authoring_stage == "prepare":
        prepare_complete = (
            result.status == "incomplete"
            and result.blocked_reason == "authoring_prepare_complete"
        )
        telemetry["prepare_status"] = "complete" if prepare_complete else "failed"
        telemetry["terminal_stage"] = "prepare"
        telemetry["terminal_reason"] = "" if prepare_complete else str(
            result.blocked_reason or f"prepare_status:{result.status}"
        )
        telemetry["writer_status"] = "prepared" if prepare_complete else "blocked"
        if not prepare_complete:
            _remember_first_failure(
                telemetry,
                stage="prepare",
                reason=telemetry["terminal_reason"],
                error_code="authoring_prepare_failed",
            )
        else:
            print("[replay] authoring prepare complete; no generation calls made")
        return 0 if prepare_complete else 2
    telemetry["authoring_context"].update({
        "requested_mode": getattr(result, "requested_authoring_context_mode", effective_mode),
        "effective_mode": getattr(result, "effective_authoring_context_mode", effective_mode),
        "mode_source": getattr(result, "authoring_context_mode_source", mode_source),
        "run_contract_digest": getattr(result, "authoring_run_contract_digest", ""),
        "run_contract_path": paths.get("authoring_run_contract_v1", ""),
    })
    if telemetry["writer_status"] != "success":
        telemetry["terminal_reason"] = str(
            result.blocked_reason or f"writer_status:{result.status}"
        )
        research_block = str(result.blocked_reason or "").startswith(
            "research_dossier_"
        )
        _remember_first_failure(
            telemetry,
            stage="research" if research_block else "writer",
            reason=telemetry["terminal_reason"],
            error_code=(
                "research_boundary_not_ready"
                if research_block else "writer_boundary_failed"
            ),
        )
    telemetry["candidate_digest"] = _candidate_digest_for_root(fresh)
    trace_path = _record_method_content_trace(
        fresh=fresh,
        artifact_paths={**artifact_paths, **paths},
        telemetry=telemetry,
    )
    paths["method_content_trace_v1"] = trace_path
    _record_product_authoring_state(
        fresh=fresh,
        paths=paths,
        telemetry=telemetry,
    )

    structural_exit = _record_authoring_structural_exit(
        fresh=fresh,
        paths=paths,
        telemetry=telemetry,
    )
    if not bool(structural_exit.get("eligible")) and str(
        telemetry.get("writer_status") or result.status
    ) == "success":
        telemetry["terminal_stage"] = "structural_exit"
        telemetry["terminal_reason"] = "structural_exit_not_eligible:" + ";".join(
            str(item) for item in (structural_exit.get("reasons") or ())
        )
        _remember_first_failure(
            telemetry,
            stage="structural_exit",
            reason=telemetry["terminal_reason"],
            error_code="structural_exit_not_eligible",
        )

    callback_requested = (
        authoring_stage == "full"
        and
        arguments.repo
        and Path(arguments.repo).is_dir()
        and int(arguments.callback_rounds) > 0
    )
    writer_status_for_callback = str(
        telemetry.get("writer_status") or result.status or ""
    )
    callback_needed = bool(
        callback_requested and _authoring_continuation_needed(fresh)
    )
    callback_repair_authorized = bool(
        callback_needed
        and (
            writer_status_for_callback == "incomplete"
            or (
                writer_status_for_callback == "success"
                and bool(structural_exit.get("eligible"))
            )
        )
    )
    if callback_requested and not callback_repair_authorized and (
        not bool(structural_exit.get("eligible"))
        or writer_status_for_callback != "success"
    ):
        # A structurally complete Writer may enter the normal callback round
        # only through the structural receipt.  An incomplete Writer is a
        # different, bounded repair case: when it emitted an actionable local
        # request, let the owning Research route repair the affected
        # paragraph, while the final structural/acceptance gates remain
        # unchanged and fail closed.
        reason = "callback1_not_authorized:" + ";".join(
            str(item)
            for item in (
                (structural_exit.get("reasons") or ())
                if writer_status_for_callback == "success"
                else ("writer_status:" + (writer_status_for_callback or "missing"),)
            )
        )
        telemetry["callback_fulfillment"] = {
            "status": "not_authorized",
            "stopped_reason": "callback1_not_authorized",
            "reason": reason,
            "structural_exit_digest": str(
                telemetry.get("structural_exit", {}).get("content_digest") or ""
            ),
        }
        telemetry["writer_blocked_reason"] = reason
        telemetry["terminal_stage"] = "callback"
        telemetry["terminal_reason"] = reason
        _remember_first_failure(
            telemetry,
            stage="callback",
            reason=reason,
            error_code="callback1_not_authorized",
        )
    if (
        callback_repair_authorized
    ):
        from code2paper.agentic.writing_callback_fulfillment import (
            WritingCallbackFulfillmentBudgetV1,
            fulfill_and_resume_writing_callbacks,
        )

        checkpoint_path = research_checkpoint_path
        continuation_seed = None
        try:
            if checkpoint_path is not None:
                from code2paper.agentic.autonomous_method_agent import (
                    build_product_research_runtime,
                )
                from code2paper.agentic.intent_compiler_v2 import (
                    IntentObligationGraphV2,
                )
                from code2paper.agentic.research_models import ResearchAgendaV1

                checkpoint_payload = json.loads(
                    checkpoint_path.read_text(encoding="utf-8")
                )
                checkpoint_run_id = str(
                    checkpoint_payload.get("run_id") or arguments.run_id
                )
                runtime = build_product_research_runtime(
                    repo_path=Path(arguments.repo).expanduser().resolve(),
                    author_intent_path=None,
                    claims=None,
                    run_id=checkpoint_run_id,
                    llm_config=llm_config,
                    artifact_root=fresh / "artifacts" / "research_tool_data",
                    intent_graph_override=IntentObligationGraphV2.model_validate(
                        checkpoint_payload["intent_graph"]
                    ),
                    agenda_override=ResearchAgendaV1.model_validate(
                        checkpoint_payload["agenda"]
                    ),
                )
                seed_path = ""
            else:
                runtime, continuation_seed, seed_path = (
                    _build_replay_continuation_context(
                        fresh=fresh,
                        artifacts=artifacts,
                        repo=Path(arguments.repo).expanduser().resolve(),
                        llm_config=llm_config,
                    )
                )
                telemetry["research_continuation_seed"] = {
                    "path": seed_path,
                    **continuation_seed.model_dump(mode="json"),
                }
                if seed_path:
                    artifact_paths["research_continuation_seed_v1"] = seed_path
        except Exception as exc:  # noqa: BLE001 — checkpoint faults stay writer-only
            print(
                f"[replay] research continuation unavailable: "
                f"{type(exc).__name__}: {exc}"
            )
            runtime = None
        if runtime is not None:
            callback_transaction_snapshot = _capture_authoring_transaction_snapshot(fresh)
            incumbent_structural_exit = _read_json_mapping(
                fresh / "artifacts" / "06_authoring" / "authoring_structural_exit_v1.json"
            )
            callback_paths, callback_status, callback_reason, callback_result = (
                fulfill_and_resume_writing_callbacks(
                    runtime=runtime,
                    out_root=fresh,
                    artifact_paths=artifact_paths,
                    writer_paths=paths,
                    llm_config=llm_config,
                    budget=WritingCallbackFulfillmentBudgetV1(
                        max_callback_rounds=max(0, int(arguments.callback_rounds)),
                        max_tool_turns_per_request=max(
                            1, int(arguments.callback_tool_turns)
                        ),
                    ),
                    llm_caller=None,
                    research_stage_checkpoint=checkpoint_path,
                    research_continuation_seed=continuation_seed,
                    authoring_context_mode=getattr(
                        result, "effective_authoring_context_mode", effective_mode
                    ),
                )
            )
            print(
                f"[replay] callback continuation: fulfilled={callback_result.local_requests_fulfilled} "
                f"pending={callback_result.local_requests_seen - callback_result.local_requests_fulfilled} "
                f"resumed={list(callback_result.resumed_section_ids)} "
                f"stopped={callback_result.stopped_reason}"
            )
            callback_writer_payload = _load_artifact_payload(
                callback_paths.get("publication_writer_result_v1")
                or writer_paths.get("publication_writer_result_v1")
                or ""
            )
            telemetry["publication_status"] = str(
                callback_writer_payload.get("status") or telemetry.get(
                    "publication_status", ""
                )
            )
            telemetry["writer_transaction_status"] = callback_status
            telemetry["candidate_completion_status"] = str(
                callback_writer_payload.get("candidate_completion_status") or "incomplete"
            )
            telemetry["candidate_complete"] = bool(
                callback_writer_payload.get("candidate_complete")
            )
            telemetry["verified_complete"] = bool(
                callback_writer_payload.get("verified_complete")
            )
            telemetry["writer_status"] = (
                "success"
                if callback_status == "success" and telemetry["candidate_complete"]
                else "blocked" if callback_status == "blocked" else "incomplete"
            )
            telemetry["writer_blocked_reason"] = callback_reason
            telemetry["terminal_stage"] = "callback"
            telemetry["terminal_reason"] = str(
                callback_reason or callback_result.stopped_reason or ""
            )
            callback_stop_reason = str(callback_result.stopped_reason or "")
            callback_stop_is_normal = callback_stop_reason in {
                "completed",
                "no_open_requests",
                "no_open_local_requests",
                "no_progress",
                "no_information_gain",
                "writer_success",
                "review_ready_with_warnings",
                "callback_gated_off",
            }
            if (
                callback_status != "success"
                or callback_reason
                or not callback_stop_is_normal
            ):
                _remember_first_failure(
                    telemetry,
                    stage="callback",
                    reason=telemetry["terminal_reason"],
                    error_code="callback_continuation_failed",
                )
            telemetry["writer_resumed_section_ids"] = list(callback_result.resumed_section_ids)
            telemetry["callback_fulfillment"] = callback_result.model_dump(mode="json")
            telemetry["candidate_digest"] = _candidate_digest_for_root(fresh)
            paths.update(callback_paths)
            trace_path = _record_method_content_trace(
                fresh=fresh,
                artifact_paths={**artifact_paths, **paths},
                telemetry=telemetry,
            )
            paths["method_content_trace_v1"] = trace_path
            from code2paper.agentic.product_authoring_graph import (
                persist_product_authoring_state_from_writer,
            )
            _state, product_state_path = persist_product_authoring_state_from_writer(
                out_root=fresh,
                artifact_paths={**artifact_paths, **paths},
                run_id=arguments.run_id,
                terminal_status=(
                    "blocked"
                    if callback_status == "blocked"
                    else "completed"
                    if callback_status == "success"
                    else "review_ready_with_warnings"
                ),
                stop_reason=callback_reason or callback_result.stopped_reason,
            )
            paths["product_authoring_state_v1"] = product_state_path
            _record_product_authoring_state(
                fresh=fresh,
                paths=paths,
                telemetry=telemetry,
            )
            resumed_structural_exit = _record_authoring_structural_exit(
                fresh=fresh,
                paths=paths,
                telemetry=telemetry,
            )
            if incumbent_structural_exit:
                callback_commit, callback_commit_reason = _callback_transaction_decision(
                    incumbent_structural_exit,
                    resumed_structural_exit,
                )
                if not callback_commit:
                    # A Research callback may be valid in its own authority
                    # lane while the resumed Writer still loses paragraph
                    # coverage or formula witnesses.  Treat the callback and
                    # its publication view as one transaction: retain the
                    # research trace for diagnosis, but restore every direct
                    # publication/checkpoint artifact from the incumbent.
                    _restore_authoring_transaction_snapshot(
                        fresh,
                        callback_transaction_snapshot,
                    )
                    callback_reason = (
                        "callback_candidate_rolled_back:" + callback_commit_reason
                    )
                    callback_status = "incomplete"
                    callback_result = callback_result.model_copy(update={
                        "local_requests_fulfilled": 0,
                        "resumed_section_ids": (),
                        "stopped_reason": "quality_regression_incumbent_restored",
                    })
                    telemetry["writer_status"] = callback_status
                    telemetry["writer_transaction_status"] = callback_status
                    telemetry["writer_blocked_reason"] = callback_reason
                    telemetry["terminal_stage"] = "callback"
                    telemetry["terminal_reason"] = callback_reason
                    telemetry["writer_resumed_section_ids"] = []
                    telemetry["callback_fulfillment"] = callback_result.model_dump(mode="json")
                    telemetry["candidate_digest"] = _candidate_digest_for_root(fresh)
                    _remember_first_failure(
                        telemetry,
                        stage="callback",
                        reason=callback_reason,
                        error_code="callback_candidate_not_monotonic",
                    )
                    # Rebuild the shared state/receipt from the restored
                    # incumbent so downstream evaluators see one coherent
                    # transaction rather than the rejected resume.
                    _record_method_content_trace(
                        fresh=fresh,
                        artifact_paths={**artifact_paths, **paths},
                        telemetry=telemetry,
                    )
                    _state, product_state_path = persist_product_authoring_state_from_writer(
                        out_root=fresh,
                        artifact_paths={**artifact_paths, **paths},
                        run_id=arguments.run_id,
                        terminal_status="review_ready_with_warnings",
                        stop_reason=callback_reason,
                    )
                    paths["product_authoring_state_v1"] = product_state_path
                    _record_product_authoring_state(
                        fresh=fresh,
                        paths=paths,
                        telemetry=telemetry,
                    )
                    _record_authoring_structural_exit(
                        fresh=fresh,
                        paths=paths,
                        telemetry=telemetry,
                    )

    writer_status = str(telemetry.get("writer_status") or result.status)
    candidate_digest = str(telemetry.get("candidate_digest") or "")
    if writer_status == "success" and bool(telemetry.get("candidate_complete")) and bool(
        telemetry.get("structural_exit", {}).get("eligible")
    ):
        telemetry["terminal_stage"] = "complete"
        telemetry["terminal_reason"] = ""
    if writer_status != "success" or not bool(telemetry.get("candidate_complete")):
        # A retained incumbent/candidate is useful diagnostic evidence, but
        # it is not a successful replay.  Exit non-zero so evaluators cannot
        # mistake an incomplete or blocked writer for acceptance.
        return 2
    if not bool(telemetry.get("structural_exit", {}).get("eligible")):
        return 2
    return 0
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frozen_root", help="Frozen run root with research artifacts")
    parser.add_argument("fresh_root", help="Fresh output root for the replay")
    parser.add_argument("--resume", action="append", default=[],
                        help="Section ids to resume (e.g. MA-S2)")
    parser.add_argument("--repo", default="",
                        help="Repository path for Research-Graph callback continuation")
    parser.add_argument("--callback-rounds", type=int, default=2)
    parser.add_argument("--callback-tool-turns", type=int, default=6)
    parser.add_argument(
        "--profile",
        default=None,
        help="Path to an env profile (defaults to tests/live/profiles/qwen38_vllm_budgeted.example.env only if environment is not already configured)",
    )
    parser.add_argument(
        "--force-profile",
        action="store_true",
        help="Make the selected profile authoritative and override existing endpoint/model environment variables",
    )
    parser.add_argument("--run-id", default="replay")
    parser.add_argument(
        "--authoring-context-mode",
        choices=("legacy", "shadow_unified", "unified"),
        default=None,
        help="Authoring context lane; explicit CLI input wins over the profile/environment",
    )
    parser.add_argument(
        "--authoring-stage",
        choices=("full", "prepare", "execute-prepared"),
        default="full",
        help=(
            "Authoring execution stage: full delivery, zero-generation prepare, "
            "or execute a fresh prepared root"
        ),
    )
    parser.add_argument(
        "--rebuild-authoring",
        action="store_true",
        help="Rebuild derived authoring (concept cards, plan, projection) from research authority",
    )
    parser.add_argument(
        "--reuse-authoring-callbacks",
        action="store_true",
        help="Copy and rebase a frozen writing_research_callback_artifacts_v1 bundle",
    )
    parser.add_argument(
        "--reuse-derived-authoring",
        action="store_true",
        help="Reuse frozen MethodUnit/Writer authoring artifacts while rebuilding current downstream outputs",
    )
    parser.add_argument(
        "--persist-authoring-rebuild-manifest",
        action="store_true",
        help="Write authoring_rebuild_manifest_v1.json with copy/rebuild decisions",
    )
    parser.add_argument(
        "--deterministic-preflight-only",
        action="store_true",
        help=(
            "Stop after the zero-model source/graph/Candidate preflight and "
            "record its result"
        ),
    )
    parser.add_argument(
        "--run-open-mode",
        choices=("auto", "new", "resume", "fork_authoring"),
        default="auto",
        help=(
            "WP1 execution identity + directory admission before any authoring "
            "write (default: auto — new for an empty root, resume when the "
            "identity matches, otherwise rejected). fork_authoring requires a "
            "verified --research-import checkpoint."
        ),
    )
    parser.add_argument(
        "--research-import",
        default="",
        help=(
            "Verified research checkpoint for fork_authoring "
            "(default: <frozen>/artifacts/research_product/research_stage_checkpoint_v1.json)"
        ),
    )
    parser.add_argument(
        "--author-intent",
        default="",
        help=(
            "Author intent file bound into the execution identity "
            "(default: <frozen>/artifacts/intent_obligation_graph_v2.json)"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)

    if arguments.authoring_stage != "full" and any((
        bool(arguments.resume),
        bool(arguments.rebuild_authoring),
        bool(arguments.reuse_derived_authoring),
        bool(arguments.reuse_authoring_callbacks),
        bool(arguments.deterministic_preflight_only),
    )):
        parser.error(
            "--authoring-stage prepare/execute-prepared cannot be combined "
            "with --resume, --rebuild-authoring, --reuse-derived-authoring, "
            "--reuse-authoring-callbacks, or --deterministic-preflight-only"
        )

    frozen = Path(arguments.frozen_root).expanduser().resolve()
    fresh = Path(arguments.fresh_root).expanduser().resolve()
    if arguments.authoring_stage == "execute-prepared":
        if not fresh.is_dir():
            parser.error(
                "--authoring-stage execute-prepared requires an existing prepared fresh root"
            )
    elif arguments.authoring_stage == "prepare":
        if fresh.exists() and any(fresh.iterdir()):
            parser.error(
                "--authoring-stage prepare requires a fresh root that is empty"
            )
        fresh.mkdir(parents=True, exist_ok=True)
    else:
        fresh.mkdir(parents=True, exist_ok=True)
    initial_profile_path = _resolve_profile_path(arguments.profile, fresh=fresh)
    _apply_replay_profile(
        initial_profile_path,
        force=bool(arguments.force_profile),
    )

    from run_d5_consolidated_matrix import record_runtime_ledger

    telemetry: dict = {}
    runtime_start: dict | None = None
    runtime_end: dict | None = None
    exit_code = 0

    # WP1：身份 + 目录准入必须早于**任何**进程产物——包括运行账本与 token 汇总；
    # 否则一次被拒的准入会留下文件，把同一 fresh 根的下一次 `new` 也一起挡掉。
    from code2paper.agentic.authoring_execution_identity import RunOpenRejected
    from code2paper.llm.providers import load_llm_config_from_env

    try:
        telemetry["execution_identity"] = _open_replay_execution_identity(
            frozen=frozen,
            fresh=fresh,
            arguments=arguments,
            llm_config=load_llm_config_from_env(),
        )
    except RunOpenRejected as rejected:
        decision = rejected.decision
        telemetry["execution_identity"] = {
            "status": "rejected",
            "mode": str(getattr(arguments, "run_open_mode", "") or ""),
            "code": decision.code,
            "next_action": decision.allowed_next_action,
            "detail": decision.detail,
            "mismatched_fields": list(decision.mismatched_fields),
            "exhausted_invocations": list(decision.exhausted_invocations),
        }
        telemetry["terminal_stage"] = "input"
        telemetry["terminal_reason"] = f"execution_identity_rejected:{decision.code}"
        _remember_first_failure(
            telemetry,
            stage="input",
            reason=telemetry["terminal_reason"],
            error_code=decision.code,
        )
        # 拒绝证据写在 fresh 根之外：fresh 根保持可重试（零生成、零污染）。
        refusal = fresh.parent / f"{fresh.name}.execution_identity_rejected.json"
        refusal.parent.mkdir(parents=True, exist_ok=True)
        refusal.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "command": " ".join(sys.argv),
                    "frozen_root": str(frozen),
                    "fresh_root": str(fresh),
                    "execution_identity": telemetry["execution_identity"],
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(
            "[replay] execution identity rejected "
            f"code={decision.code} next={decision.allowed_next_action} "
            f"detail={decision.detail} record={refusal}"
        )
        return 2

    def _request_exit(signum: int, _frame: object) -> None:
        raise SystemExit(128 + int(signum))

    signal.signal(signal.SIGINT, _request_exit)
    signal.signal(signal.SIGTERM, _request_exit)
    signal.signal(signal.SIGHUP, _request_exit)
    try:
        runtime_start = record_runtime_ledger(fresh, "start")
        exit_code = _replay(
            frozen=frozen,
            fresh=fresh,
            arguments=arguments,
            telemetry=telemetry,
        )
    except SystemExit as exc:
        raw = exc.code
        exit_code = raw if isinstance(raw, int) else 143
        telemetry.setdefault("terminal_stage", "replay")
        telemetry["terminal_reason"] = telemetry.get(
            "terminal_reason", ""
        ) or f"process_exit:{exit_code}"
        print(f"[replay] interrupted SystemExit={exit_code}")
        raise
    except KeyboardInterrupt:
        exit_code = 130
        telemetry["terminal_stage"] = telemetry.get("terminal_stage") or "replay"
        telemetry["terminal_reason"] = telemetry.get(
            "terminal_reason", ""
        ) or "keyboard_interrupt"
        print("[replay] interrupted KeyboardInterrupt")
        raise
    except Exception as exc:  # noqa: BLE001 - replay boundary must record
        print(f"[replay] FATAL unhandled error: {exc!r}")
        message = str(exc)
        lowered = message.casefold()
        if "slot" in lowered or "methodunit" in lowered:
            stage = "method_unit_reassembly"
            code = "method_unit_slot_closure_failed"
        elif "research" in lowered or "dossier" in lowered:
            stage = "research"
            code = "research_boundary_failed"
        elif "formal" in lowered or "equation" in lowered:
            stage = "formalizer"
            code = "formalizer_boundary_failed"
        elif "writer" in lowered or "paragraph" in lowered:
            stage = "writer"
            code = "writer_boundary_failed"
        else:
            stage = "replay"
            code = "replay_unhandled_error"
        telemetry["terminal_stage"] = stage
        telemetry["terminal_reason"] = _safe_failure_text(message)
        telemetry["terminal_error_code"] = code
        telemetry["terminal_exception_type"] = type(exc).__name__
        _remember_first_failure(
            telemetry,
            stage=stage,
            reason=telemetry["terminal_reason"],
            error_code=code,
        )
        exit_code = 2
    finally:
        try:
            runtime_end = record_runtime_ledger(fresh, "end")
        except Exception as exc:  # noqa: BLE001 - diagnostics-only
            print(f"[replay] runtime end ledger failed: {exc!r}")
        try:
            telemetry["token_usage"] = _write_token_usage_summary(fresh)
        except Exception as exc:  # noqa: BLE001 - diagnostics-only
            print(f"[replay] token usage summary failed: {exc!r}")
        structural = telemetry.get("structural_exit") or {}
        writer_status = str(telemetry.get("writer_status") or "")
        preflight_only = bool(telemetry.get("preflight_only"))
        prepare_complete = (
            telemetry.get("authoring_stage") == "prepare"
            and telemetry.get("prepare_status") == "complete"
        )
        failure_needed = False if (preflight_only or prepare_complete) else bool(
            exit_code != 0
            or writer_status not in {"", "success"}
            or not bool(structural.get("eligible"))
        )
        if telemetry.get("first_failed_stage"):
            telemetry["terminal_stage"] = telemetry["first_failed_stage"]
            telemetry["terminal_reason"] = telemetry.get(
                "first_failed_reason", ""
            )
            telemetry["terminal_error_code"] = telemetry.get(
                "first_failed_error_code", "authoring_failure"
            )
        terminal_mode = str(
            (telemetry.get("authoring_context") or {}).get("effective_mode")
            or getattr(arguments, "authoring_context_mode", "")
            or os.environ.get("CODE2PAPER_AUTHORING_CONTEXT_MODE", "")
            or ""
        ).strip().casefold()
        if terminal_mode in {"unified", "shadow_unified"}:
            try:
                from code2paper.agentic.unified_invocation_ledger import (
                    write_run_terminal_event,
                )

                ledger_root = fresh / "artifacts" / "06_authoring" / "invocations"
                archive_payload = _read_json_mapping(
                    fresh / "artifacts" / "06_authoring" / "unified_context_archive_v2.json"
                )
                if not archive_payload:
                    archive_payload = _read_json_mapping(
                        fresh / "artifacts" / "unified_context_archive_v2.json"
                    )
                run_digest = str(
                    archive_payload.get("content_digest")
                    or telemetry.get("unified_run_digest")
                    or _digest_text(
                        json.dumps(
                            {
                                "run_id": str(arguments.run_id),
                                "frozen_root": str(frozen),
                                "fresh_root": str(fresh),
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                    )
                )
                completed: list[tuple[int, int, str]] = []
                if ledger_root.is_dir():
                    for directory in ledger_root.iterdir():
                        if not directory.is_dir():
                            continue
                        for receipt_path in directory.glob("attempt-*.completed.json"):
                            payload = _read_json_mapping(receipt_path)
                            invocation_id = str(payload.get("invocation_id") or "")
                            if not invocation_id:
                                continue
                            try:
                                attempt = int(payload.get("attempt", 0) or 0)
                            except (TypeError, ValueError):
                                attempt = 0
                            try:
                                mtime = receipt_path.stat().st_mtime_ns
                            except OSError:
                                mtime = 0
                            completed.append((mtime, attempt, invocation_id))
                last_completed = (
                    max(completed, key=lambda item: (item[0], item[1]))[2]
                    if completed else ""
                )
                terminal_path = write_run_terminal_event(
                    ledger_root,
                    run_digest=run_digest,
                    terminal_reason=str(telemetry.get("terminal_reason") or ""),
                    terminal_stage=str(telemetry.get("terminal_stage") or "replay"),
                    last_completed_invocation_id=last_completed,
                    extra={
                        "exit_code": int(exit_code),
                        "terminal_error_code": str(
                            telemetry.get("terminal_error_code") or ""
                        ),
                    },
                )
                telemetry["invocation_terminal_event"] = {
                    "path": str(terminal_path),
                    "run_digest": run_digest,
                    "last_completed_invocation_id": last_completed,
                }
            except Exception as exc:  # noqa: BLE001 - terminal diagnostics only
                print(f"[replay] invocation terminal event failed: {exc!r}")
        failure_path = _authoring_failure_path(fresh)
        if failure_needed and not failure_path.is_file():
            try:
                terminal_reason = str(
                    telemetry.get("terminal_reason")
                    or telemetry.get("writer_blocked_reason")
                    or f"process_exit:{exit_code}"
                )
                failure_scope = _failure_scope_from_artifacts(
                    fresh=fresh,
                    structural=structural,
                    terminal_reason=terminal_reason,
                )
                _write_authoring_failure(
                    fresh=fresh,
                    terminal_stage=str(telemetry.get("terminal_stage") or "replay"),
                    terminal_reason=terminal_reason,
                    error_code=str(
                        telemetry.get("terminal_error_code")
                        or "authoring_acceptance_not_reached"
                    ),
                    section_id=str(failure_scope.get("section_id") or ""),
                    paragraph_id=str(failure_scope.get("paragraph_id") or ""),
                    target_kind=str(failure_scope.get("target_kind") or ""),
                    target_id=str(failure_scope.get("target_id") or ""),
                    direct_reason=str(failure_scope.get("direct_reason") or ""),
                    cascade_reasons=tuple(failure_scope.get("cascade_reasons") or ()),
                    exc=None,
                )
            except Exception as exc:  # noqa: BLE001 - diagnostics-only
                print(f"[replay] authoring failure write failed: {exc!r}")
        try:
            _write_execution_record(
                frozen=frozen,
                fresh=fresh,
                arguments=arguments,
                exit_code=exit_code,
                runtime_start=runtime_start,
                runtime_end=runtime_end,
                telemetry=telemetry,
            )
        except Exception as exc:  # noqa: BLE001 - diagnostics-only
            print(f"[replay] execution record write failed: {exc!r}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
