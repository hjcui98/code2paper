#!/usr/bin/env python3
"""Prepare, run, and resume one unified V2 publication Writer page."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

_ROOT = Path(__file__).resolve().parents[1]
for _path in (_ROOT / "src", _ROOT / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

TARGET_PAGE_ID = "page:02a75f6a1ef46816946276263439296fa93593e0f32c30694b497c72e96d484f"
TARGET_SECTION_ID = "MA-REV-mech_sym-f6cf5bdfe2ae16f0"
HISTORICAL_PRIMARY_CHAT_TOKENS = 49_678
MAX_REQUEST_INPUT_TOKENS = 60_000
MAX_DIAGNOSTIC_INPUT_TOKENS = 120_000
MAX_ATTEMPTS = 2
WRITER_OUTPUT_TOKENS = 8_192
WRITER_THINKING_RESERVE_TOKENS = 1_024
SAFETY_MARGIN_TOKENS = 1_024


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    raise TypeError(type(value).__name__)


def _write_json(path: Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, default=_json_default) + "\n"
    temp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


def _read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _digest_json(value: Any) -> str:
    from code2paper.agentic.mechanism_context_models import canonical_json_bytes, sha256_digest
    return sha256_digest(canonical_json_bytes(value))


def _digest_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _profile_path(value: str | None) -> Path:
    return Path(value or (_ROOT / "tests/live/profiles/qwen38_vllm_budgeted.example.env")).expanduser().resolve()


def _load_config(profile: Path) -> Any:
    from run_authoring_replay import _apply_replay_profile
    from code2paper.llm.providers import load_llm_config_from_env
    if not profile.is_file():
        raise ValueError(f"profile_missing:{profile}")
    _apply_replay_profile(profile, force=True)
    config = load_llm_config_from_env()
    base = os.environ.get("CODE2PAPER_OPENAI_BASE_URL", "").strip().rstrip("/")
    parts = urlsplit(base)
    if str(getattr(config.provider, "value", config.provider)) != "openai":
        raise ValueError("single_page_provider_must_be_openai")
    if parts.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("single_page_endpoint_must_be_loopback")
    if int(parts.port or 0) != 8006:
        raise ValueError(f"single_page_endpoint_must_use_8006:{parts.port or 0}")
    if not base.endswith("/v1"):
        raise ValueError(f"single_page_base_url_must_end_v1:{base}")
    if config.model != "qwen38-27b-nvfp4":
        raise ValueError(f"single_page_model_mismatch:{config.model}")
    return config


def _base_url() -> str:
    return os.environ.get("CODE2PAPER_OPENAI_BASE_URL", "").strip().rstrip("/")


def _runtime_url(suffix: str) -> str:
    base = _base_url()
    root = base[:-3] if base.endswith("/v1") else base
    return root + "/" + suffix.lstrip("/")


def _get(url: str, timeout: int = 20) -> tuple[int, Any, str]:
    request = Request(url, headers={"User-Agent": "code2paper-single-page/1"}, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            status = int(response.status)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        return 0, {"error": f"{type(exc).__name__}:{str(exc)[:160]}"}, ""
    try:
        return status, json.loads(raw), raw
    except json.JSONDecodeError:
        return status, {"raw": raw[:500]}, raw


def _context_tokens() -> int:
    value = int(os.environ.get("CODE2PAPER_MODEL_CONTEXT_TOKENS", "0") or 0)
    if value > 0:
        return value
    capability = os.environ.get("CODE2PAPER_LLM_CAPABILITY_PROFILE", "")
    if capability:
        try:
            value = int(_read_json(Path(capability)).get("max_model_len", 0) or 0)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            value = 0
    if value <= 0:
        raise ValueError("model_context_tokens_missing")
    return value


def _preflight(config: Any) -> dict[str, Any]:
    health_status, health, health_raw = _get(_runtime_url("health"))
    model_status, models, model_raw = _get(_base_url() + "/models")
    metric_status, _, metric_raw = _get(_runtime_url("metrics"))
    model_ids = tuple(
        str(item.get("id") or "")
        for item in (models.get("data") if isinstance(models, Mapping) else ()) or ()
        if isinstance(item, Mapping) and str(item.get("id") or "").strip()
    )
    context = _context_tokens()
    identity = {
        "provider": str(getattr(config.provider, "value", config.provider)),
        "configured_model": config.model,
        "served_model_ids": list(model_ids),
        "base_url": _base_url(),
        "context_tokens": context,
    }
    result = {
        "health": {"status": health_status, "body": health, "raw_prefix": health_raw[:200]},
        "models": {"status": model_status, "body": models, "raw_prefix": model_raw[:500]},
        "metrics": {"status": metric_status, "body_prefix": metric_raw[:1000]},
        "identity": identity,
        "identity_digest": _digest_json(identity),
        "model_match": config.model in set(model_ids),
        "context_tokens": context,
    }
    if health_status != 200:
        raise ValueError(f"runtime_health_failed:{health_status}")
    if model_status != 200 or not result["model_match"]:
        raise ValueError(f"runtime_model_identity_failed:{model_ids}")
    if context < 131072:
        raise ValueError(f"runtime_context_too_small:{context}")
    return result


def _authoring_root(frozen_root: Path) -> Path:
    value = Path(frozen_root).expanduser().resolve() / "artifacts" / "06_authoring"
    if not value.is_dir():
        raise ValueError(f"frozen_authoring_root_missing:{value}")
    return value


def _frozen_inputs(frozen_root: Path) -> dict[str, Any]:
    from code2paper.agentic.unified_context_models import (
        ConsumerInvocationPlanV1,
        ConsumerWorksetManifestV2,
        ConsumerWorksetV2,
        UnifiedContextArchiveV2,
    )
    root = _authoring_root(frozen_root)
    manifest = ConsumerWorksetManifestV2.model_validate_json(
        (root / "consumer_workset_manifest_v2.writer.2.json").read_text(encoding="utf-8")
    )
    parent_plan = ConsumerInvocationPlanV1.model_validate_json(
        (root / "consumer_invocation_plan_v1.2.json").read_text(encoding="utf-8")
    )
    archive = UnifiedContextArchiveV2.model_validate_json(
        (root / "unified_context_archive_v2.json").read_text(encoding="utf-8")
    )
    narrative = _read_json(root / "narrative_plan_v3.revision.2.json")
    section = next(
        (item for item in narrative.get("sections", ()) if item.get("section_id") == TARGET_SECTION_ID),
        None,
    )
    if not isinstance(section, Mapping):
        raise ValueError(f"target_section_missing:{TARGET_SECTION_ID}")
    page = manifest.page_by_id(TARGET_PAGE_ID)
    if page is None:
        raise ValueError(f"target_page_missing:{TARGET_PAGE_ID}")
    page_payload = getattr(page, "technical_payload", {}) or {}
    page_paragraph_ids = {
        str(value)
        for value in (page_payload.get("paragraph_ids") or ())
        if str(value).strip()
    }
    section_data = dict(section)
    section_data["paragraphs"] = [
        item for item in (section.get("paragraphs") or ())
        if isinstance(item, Mapping)
        and str(item.get("paragraph_id") or "") in page_paragraph_ids
    ]
    if not section_data["paragraphs"]:
        raise ValueError(f"target_page_paragraphs_missing:{TARGET_PAGE_ID}")
    source_workset = next(
        (item for item in manifest.worksets if item.workset_id == f"workset:section:{TARGET_SECTION_ID}"),
        None,
    )
    if source_workset is None:
        raise ValueError(f"target_workset_missing:{TARGET_SECTION_ID}")
    workset_data = source_workset.model_dump(mode="json")
    workset_data.update({
        "required_page_ids": [TARGET_PAGE_ID],
        "required_atom_ids": list(page.atom_ids),
        "content_digest": "",
    })
    single_workset = ConsumerWorksetV2.model_validate(workset_data)
    manifest_data = manifest.model_dump(mode="json")
    manifest_data.update({
        "pages": [page.model_dump(mode="json")],
        "worksets": [single_workset.model_dump(mode="json")],
        "content_digest": "",
    })
    single_manifest = ConsumerWorksetManifestV2.model_validate(manifest_data)
    package_file = root / "mechanism_formula_packages_v2.json"
    package_data = _read_json(package_file) if package_file.is_file() else {}
    obligation_file = root / "mechanism_formula_obligations_v1.json"
    obligation_data = _read_json(obligation_file) if obligation_file.is_file() else {}
    obligations: list[Mapping[str, Any]] = []
    if isinstance(obligation_data.get("by_mechanism"), Mapping):
        for values in obligation_data["by_mechanism"].values():
            obligations.extend(item for item in (values or ()) if isinstance(item, Mapping))
    return {
        "root": root,
        "manifest": single_manifest,
        "full_manifest_digest": manifest.content_digest,
        "parent_plan": parent_plan,
        "archive": archive,
        "section": section_data,
        "target_page": page,
        "packages": tuple(item for item in (package_data.get("packages") or ()) if isinstance(item, Mapping)),
        "obligations": tuple(obligations),
    }


@dataclass(frozen=True)
class _SectionProxy:
    payload: Mapping[str, Any]

    @property
    def section_id(self) -> str:
        return str(self.payload.get("section_id") or "")

    @property
    def heading(self) -> str:
        return str(self.payload.get("heading") or "")

    @property
    def mechanism_ids(self) -> tuple[str, ...]:
        return tuple(str(item) for item in (self.payload.get("mechanism_ids") or ()))

    def model_dump(self, *, mode: str = "json") -> dict[str, Any]:
        return json.loads(json.dumps(dict(self.payload), ensure_ascii=False))


@dataclass(frozen=True)
class _NarrativeProxy:
    sections: tuple[_SectionProxy, ...]

def _envelope(*, run_digest: str, profile_digest: str, model_identity_digest: str, meter: Any, context_tokens: int) -> Any:
    from code2paper.agentic.unified_context_models import RoleRequestBudgetV1, RunInvocationBudgetEnvelopeV1
    budget = RoleRequestBudgetV1(
        role="writer",
        prompt_token_reserve=2048,
        output_token_reserve=WRITER_OUTPUT_TOKENS,
        thinking_token_reserve=WRITER_THINKING_RESERVE_TOKENS,
        scaffolding_token_reserve=0,
    )
    return RunInvocationBudgetEnvelopeV1(
        envelope_id=f"single-page-writer-v1:{run_digest}",
        run_digest=run_digest,
        profile_digest=profile_digest,
        model_identity_digest=model_identity_digest,
        token_meter=meter,
        request_budget_by_role={"writer": budget},
        max_request_input_tokens_by_role={"writer": MAX_REQUEST_INPUT_TOKENS},
        safety_margin_tokens=SAFETY_MARGIN_TOKENS,
        model_context_tokens=context_tokens,
        max_calls_by_role={"writer": MAX_ATTEMPTS},
        max_input_tokens_by_role={"writer": MAX_DIAGNOSTIC_INPUT_TOKENS},
        retry_reserve_input_tokens_by_role={"writer": MAX_REQUEST_INPUT_TOKENS},
        max_total_input_tokens=MAX_DIAGNOSTIC_INPUT_TOKENS,
        max_formula_repair_calls=0,
        max_page_input_tokens=MAX_REQUEST_INPUT_TOKENS,
        max_obligations_per_page=8,
    )


def _plan(inputs: Mapping[str, Any], envelope: Any, identity_digest: str, request_digest: str) -> Any:
    from code2paper.agentic.unified_context_models import ConsumerInvocationPlanV1, ConsumerInvocationV1
    page = inputs["target_page"]
    workset = inputs["manifest"].worksets[0]
    invocation = ConsumerInvocationV1(
        invocation_id=f"inv:writer:{TARGET_SECTION_ID}:{TARGET_PAGE_ID}",
        role="writer",
        phase="writer",
        workset_id=workset.workset_id,
        task_ids=tuple(workset.task_ids),
        mechanism_id=workset.mechanism_id,
        section_id=TARGET_SECTION_ID,
        page_id=TARGET_PAGE_ID,
        expected_technical_bytes_digest=page.technical_bytes_digest,
        expected_request_envelope_digest=request_digest,
        max_input_tokens=MAX_REQUEST_INPUT_TOKENS,
        max_output_tokens=WRITER_OUTPUT_TOKENS,
        max_attempts=MAX_ATTEMPTS,
    )
    return ConsumerInvocationPlanV1(
        plan_revision=3,
        parent_plan_digest=inputs["parent_plan"].content_digest,
        phase="writer",
        archive_digest=inputs["manifest"].archive_digest,
        workset_manifest_digest=inputs["manifest"].content_digest,
        envelope_digest=envelope.content_digest,
        profile_digest=envelope.profile_digest,
        model_identity_digest=identity_digest,
        invocations=(invocation,),
        formalizer_repair_call_limit=0,
        planned_calls_by_role={"writer": 1},
        planned_input_tokens_by_role={"writer": MAX_REQUEST_INPUT_TOKENS},
        reserved_calls_by_role={"writer": 1},
        reserved_input_tokens_by_role={"writer": MAX_DIAGNOSTIC_INPUT_TOKENS},
        reservation_contract="atomic_debit_v1",
    )


def _writer_input(inputs: Mapping[str, Any], plan: Any) -> Any:
    from code2paper.agentic.publication_method_writer import _writer_section_inputs_v2
    values = _writer_section_inputs_v2(
        narrative_plan=_NarrativeProxy((_SectionProxy(inputs["section"]),)),
        formula_packages=tuple(inputs["packages"]),
        formula_obligations=tuple(inputs["obligations"]),
        consumer_workset_manifest=inputs["manifest"],
        consumer_invocation_plan=plan,
        system_prompt="",
    )
    if len(values) != 1 or values[0].section_id != TARGET_SECTION_ID:
        raise ValueError("single_page_writer_input_not_unique")
    return values[0]


def _request(section: Any) -> Any:
    from code2paper.agentic.unified_context_compiler import consumer_response_json_schema
    from code2paper.llm.response_schemas import PUBLICATION_METHOD_SECTION_SCHEMA
    from code2paper.llm.section_writer import build_publication_writer_request
    return build_publication_writer_request(
        section,
        system_prompt=section.system_prompt,
        schema_name=PUBLICATION_METHOD_SECTION_SCHEMA,
        response_json_schema=consumer_response_json_schema("writer"),
    )


def _request_digest(request: Any, page: Any, task_ids: tuple[str, ...]) -> str:
    from code2paper.agentic.mechanism_context_models import canonical_json_bytes, sha256_digest
    from code2paper.agentic.unified_context_compiler import consumer_response_json_schema
    from code2paper.agentic.unified_context_models import compute_request_envelope_digest
    schema_digest = sha256_digest(canonical_json_bytes({
        "role": "writer",
        "schema_version": "unified-consumer-response-v2",
        "shape": consumer_response_json_schema("writer"),
    }))
    prompt_digest = sha256_digest(str(request.prompt).encode("utf-8"))
    return compute_request_envelope_digest(
        prompt_template_id=str(request.prompt_template_id),
        consumer_role="writer",
        task_ids=task_ids,
        page_id=page.page_id,
        technical_bytes_digest=page.technical_bytes_digest,
        system_prompt_digest=prompt_digest,
        rendered_prompt_digest=prompt_digest,
        canonical_input_payload_digest=sha256_digest(canonical_json_bytes(request.input_payload)),
        response_schema_digest=schema_digest,
    )


def _measure(request: Any, envelope: Any, tokenizer: Any, plan: Any) -> Any:
    from code2paper.agentic.unified_context_compiler import account_unified_request_tokens
    return account_unified_request_tokens(
        consumer_role="writer",
        rendered_prompt=request.prompt,
        input_payload=request.input_payload,
        response_schema=request.response_json_schema or {},
        request_budget=envelope.request_budget_by_role["writer"],
        max_input_tokens=MAX_REQUEST_INPUT_TOKENS,
        model_context_tokens=envelope.model_context_tokens,
        safety_margin_tokens=envelope.safety_margin_tokens,
        meter=envelope.token_meter,
        tokenizer=tokenizer,
        invocation_id=plan.invocations[0].invocation_id,
        page_id=TARGET_PAGE_ID,
        scaffolding_reserve_tokens=0,
    )


def _prepare(args: argparse.Namespace) -> Path:
    output = Path(args.output).expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"prepare_output_must_be_fresh:{output}")
    output.mkdir(parents=True, exist_ok=True)
    config = _load_config(_profile_path(args.profile))
    runtime = _preflight(config)
    from code2paper.agentic.unified_context_models import model_chat_template_tokenizer_meter
    from code2paper.llm.tokenizer import VllmOpenAIChatTokenizer
    identity = f"vllm-openai-chat-template-v1:{config.model}|{_base_url()}|{runtime['identity_digest']}"
    tokenizer = VllmOpenAIChatTokenizer(base_url=_base_url(), model=config.model, identity=identity)
    inputs = _frozen_inputs(Path(args.frozen_root).expanduser().resolve())
    run_digest = _digest_json({
        "source_root": str(Path(args.frozen_root).expanduser().resolve()),
        "page_id": TARGET_PAGE_ID,
        "section_id": TARGET_SECTION_ID,
        "parent_plan_digest": inputs["parent_plan"].content_digest,
    })
    profile_contract = {
        "profile": str(_profile_path(args.profile)),
        "max_total_input_tokens": MAX_DIAGNOSTIC_INPUT_TOKENS,
        "max_request_input_tokens": MAX_REQUEST_INPUT_TOKENS,
        "max_attempts": MAX_ATTEMPTS,
        "output_tokens": WRITER_OUTPUT_TOKENS,
        "thinking_reserve_tokens": WRITER_THINKING_RESERVE_TOKENS,
        "safety_margin_tokens": SAFETY_MARGIN_TOKENS,
        "tokenizer_identity": tokenizer.identity,
    }
    profile_digest = _digest_json(profile_contract)
    identity_digest = _digest_json({
        "runtime_identity_digest": runtime["identity_digest"],
        "tokenizer_identity": tokenizer.identity,
    })
    envelope = _envelope(
        run_digest=run_digest,
        profile_digest=profile_digest,
        model_identity_digest=identity_digest,
        meter=model_chat_template_tokenizer_meter(tokenizer.identity),
        context_tokens=runtime["context_tokens"],
    )
    provisional = _plan(inputs, envelope, identity_digest, "sha256:pending")
    section = _writer_input(inputs, provisional)
    request = _request(section)
    measured = _measure(request, envelope, tokenizer, provisional)
    if not measured.fits or measured.input_tokens > MAX_REQUEST_INPUT_TOKENS:
        raise ValueError(f"prepare_input_budget_failed:{measured.input_tokens}:{measured.overflow_tokens}")
    request_digest = _request_digest(request, inputs["target_page"], tuple(provisional.invocations[0].task_ids))
    plan = _plan(inputs, envelope, identity_digest, request_digest)
    section = _writer_input(inputs, plan)
    final_request = _request(section)
    if final_request.input_hash != request.input_hash:
        raise ValueError("request_changed_after_plan_freeze")
    state = {
        "schema_version": "unified-single-page-writer-v1",
        "prepared_at_unix": time.time(),
        "frozen_root": str(Path(args.frozen_root).expanduser().resolve()),
        "target_page_id": TARGET_PAGE_ID,
        "target_section_id": TARGET_SECTION_ID,
        "historical_primary_chat_tokens": HISTORICAL_PRIMARY_CHAT_TOKENS,
        "runtime_preflight": runtime,
        "profile_contract": profile_contract,
        "profile_digest": profile_digest,
        "model_identity_digest": identity_digest,
        "tokenizer_identity": tokenizer.identity,
        "run_digest": run_digest,
        "archive_digest": inputs["archive"].content_digest,
        "parent_writer_plan_digest": inputs["parent_plan"].content_digest,
        "full_writer_manifest_digest": inputs["full_manifest_digest"],
        "manifest": inputs["manifest"].model_dump(mode="json"),
        "envelope": envelope.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "writer_section": {
            "section_id": section.section_id,
            "heading": section.heading,
            "system_prompt": section.system_prompt,
            "prompt_payload": section.prompt_payload,
            "argument_graph": section.argument_graph,
        },
        "request_contract": {
            "prompt_template_id": final_request.prompt_template_id,
            "input_hash": final_request.input_hash,
            "request_envelope_digest": request_digest,
            "technical_bytes_digest": inputs["target_page"].technical_bytes_digest,
            "accounting": measured.model_dump(mode="json"),
        },
        "generation_calls": 0,
        "provider_sends": 0,
    }
    _write_json(output / "single_page_state.json", state)
    _write_json(output / "runtime_preflight.json", runtime)
    _write_json(output / "prepare_result.json", {
        "status": "pass",
        "generation_calls": 0,
        "provider_sends": 0,
        "input_tokens": measured.input_tokens,
        "historical_primary_chat_tokens": HISTORICAL_PRIMARY_CHAT_TOKENS,
        "max_request_input_tokens": MAX_REQUEST_INPUT_TOKENS,
        "diagnostic_input_limit": MAX_DIAGNOSTIC_INPUT_TOKENS,
        "tokenizer_identity": tokenizer.identity,
        "model_identity_digest": identity_digest,
        "plan_digest": plan.content_digest,
        "envelope_digest": envelope.content_digest,
        "request_envelope_digest": request_digest,
    })
    return output


def _load_state(output: Path) -> tuple[dict[str, Any], Any, Any, Any, Any]:
    from code2paper.agentic.unified_context_models import (
        ConsumerInvocationPlanV1,
        ConsumerWorksetManifestV2,
        RunInvocationBudgetEnvelopeV1,
        UnifiedContextArchiveV2,
    )
    state = _read_json(output / "single_page_state.json")
    if state.get("schema_version") != "unified-single-page-writer-v1":
        raise ValueError("single_page_state_schema_mismatch")
    manifest = ConsumerWorksetManifestV2.model_validate(state["manifest"])
    envelope = RunInvocationBudgetEnvelopeV1.model_validate(state["envelope"])
    plan = ConsumerInvocationPlanV1.model_validate(state["plan"])
    archive = UnifiedContextArchiveV2.model_validate_json(
        (_authoring_root(Path(state["frozen_root"])) / "unified_context_archive_v2.json").read_text(encoding="utf-8")
    )
    return state, manifest, envelope, plan, archive


def _section(state: Mapping[str, Any]) -> Any:
    from code2paper.llm.section_writer import WriterSectionInput
    raw = state["writer_section"]
    return WriterSectionInput(
        section_id=str(raw["section_id"]),
        heading=str(raw["heading"]),
        prompt_payload=dict(raw["prompt_payload"]),
        system_prompt=str(raw["system_prompt"]),
        publication_mode=True,
        argument_graph=dict(raw.get("argument_graph") or {}),
    )


def _verify_identity(state: Mapping[str, Any], runtime: Mapping[str, Any], tokenizer: Any) -> None:
    actual = _digest_json({
        "runtime_identity_digest": runtime["identity_digest"],
        "tokenizer_identity": tokenizer.identity,
    })
    if actual != str(state["model_identity_digest"]):
        raise ValueError("single_page_model_identity_changed")
    if tokenizer.identity != str(state["tokenizer_identity"]):
        raise ValueError("single_page_tokenizer_identity_changed")

def _writer_summary(writer: Any) -> dict[str, Any]:
    aggregate = getattr(writer, "aggregate", None)
    return {
        "output_count": len(getattr(writer, "outputs", ()) or ()),
        "incomplete_sections": list(getattr(aggregate, "incomplete_sections", ()) or ()) if aggregate else [],
        "writer_repair_rounds": int(getattr(aggregate, "writer_repair_rounds", 0) or 0) if aggregate else 0,
        "writer_repair_commits": int(getattr(aggregate, "writer_repair_commits", 0) or 0) if aggregate else 0,
        "writer_repair_no_progress_stops": int(getattr(aggregate, "writer_repair_no_progress_stops", 0) or 0) if aggregate else 0,
        "outputs": [
            item.model_dump(mode="json")
            for item in (getattr(writer, "outputs", ()) or ())
            if hasattr(item, "model_dump")
        ],
    }


def _resume_decision_payload(decision: Any) -> dict[str, Any]:
    """Serialize both the ledger dataclass and future Pydantic decisions."""

    if hasattr(decision, "model_dump"):
        return decision.model_dump(mode="json")
    if hasattr(decision, "__dataclass_fields__"):
        return asdict(decision)
    if hasattr(decision, "__dict__"):
        return dict(vars(decision))
    raise TypeError(type(decision).__name__)


def _submission(output: Path, state: Mapping[str, Any], plan: Any) -> dict[str, Any] | None:
    from code2paper.agentic.unified_invocation_ledger import (
        build_resume_plan, read_all_completed_receipts, read_writer_content_acceptance,
    )
    ledger = _ledger(output)
    accepted = []
    for receipt in read_all_completed_receipts(ledger, strict=True):
        if receipt.invocation_id != plan.invocations[0].invocation_id:
            continue
        sidecar = read_writer_content_acceptance(ledger, receipt)
        if sidecar and sidecar.get("accepted") and sidecar.get("resume_eligible"):
            accepted.append((receipt, sidecar))
    if not accepted:
        return None
    receipt, sidecar = sorted(accepted, key=lambda item: (item[0].attempt, item[0].content_digest))[-1]
    decision = build_resume_plan(
        ledger,
        plan,
        archive_digest=state["archive_digest"],
        workset_manifest_digest=plan.workset_manifest_digest,
        model_identity_digest=plan.model_identity_digest,
    ).decisions[plan.invocations[0].invocation_id]
    if decision.decision != "reuse":
        return None
    return {
        "submission_status": "committed",
        "page_id": TARGET_PAGE_ID,
        "section_id": TARGET_SECTION_ID,
        "invocation_id": receipt.invocation_id,
        "receipt_digest": receipt.content_digest,
        "content_acceptance_digest": _digest_json(sidecar),
        "attempt": receipt.attempt,
        "content_repair_attempt": bool(receipt.content_repair_attempt),
        "resume_decision": _resume_decision_payload(decision),
        "plan_digest": plan.content_digest,
        "model_identity_digest": plan.model_identity_digest,
    }


def _live(args: argparse.Namespace) -> int:
    output = Path(args.output).expanduser().resolve()
    state, manifest, envelope, plan, archive = _load_state(output)
    config = _load_config(_profile_path(args.profile))
    runtime = _preflight(config)
    from code2paper.llm.tokenizer import VllmOpenAIChatTokenizer
    tokenizer = VllmOpenAIChatTokenizer(
        base_url=_base_url(), model=config.model, identity=state["tokenizer_identity"]
    )
    _verify_identity(state, runtime, tokenizer)
    section = _section(state)
    request = _request(section)
    invocation = plan.invocations[0]
    page = manifest.page_by_id(TARGET_PAGE_ID)
    if request.input_hash != state["request_contract"]["input_hash"]:
        raise ValueError("live_request_hash_changed")
    if _request_digest(request, page, tuple(invocation.task_ids)) != invocation.expected_request_envelope_digest:
        raise ValueError("live_request_envelope_changed")
    # A process may crash after the provider calls and acceptance sidecar have
    # been durably published but before ``live_result.json`` is assembled.
    # Recover that committed submission without sending a duplicate primary or
    # repair request.
    existing_submission = _submission(output, state, plan)
    if existing_submission is not None:
        recovered = {
            "status": "pass",
            "page_id": TARGET_PAGE_ID,
            "section_id": TARGET_SECTION_ID,
            "generation_calls": 0,
            "provider_sends": 0,
            "writer": {
                "output_count": 1,
                "incomplete_sections": [],
                "recovered_existing_submission": True,
            },
            "submission": existing_submission,
            "runtime_preflight": runtime,
            "plan_digest": plan.content_digest,
            "envelope_digest": envelope.content_digest,
            "model_identity_digest": plan.model_identity_digest,
            "archive_digest": archive.content_digest,
            "recovered_without_provider_send": True,
        }
        _write_json(output / "single_page_submission.json", existing_submission)
        _write_json(output / "live_result.json", recovered)
        return 0
    config = config.model_copy(update={
        "retry_max_attempts": 1,
        "cache": False,
        "max_output_tokens": WRITER_OUTPUT_TOKENS,
    })
    from code2paper.agentic.unified_invocation_ledger import register_invocation_plan
    register_invocation_plan(_ledger(output), plan)
    caller = _LiveCaller(output, state, manifest, envelope, plan, tokenizer)
    sink = _AcceptanceSink(output)
    from code2paper.llm.section_writer import (
        assess_publication_content_progress,
        write_publication_method_by_sections,
    )
    writer = write_publication_method_by_sections(
        config,
        [section],
        llm_caller=caller,
        content_transaction_assessor=assess_publication_content_progress,
        response_attempt_sink=sink,
        page_acceptance_sink=sink,
    )
    submission = _submission(output, state, plan)
    result = {
        "status": "pass" if submission else "fail",
        "page_id": TARGET_PAGE_ID,
        "section_id": TARGET_SECTION_ID,
        "generation_calls": caller.generation_calls,
        "provider_sends": caller.provider_sends,
        "writer": _writer_summary(writer),
        "submission": submission,
        "runtime_preflight": runtime,
        "plan_digest": plan.content_digest,
        "envelope_digest": envelope.content_digest,
        "model_identity_digest": plan.model_identity_digest,
        "archive_digest": archive.content_digest,
    }
    _write_json(output / "runtime_preflight.json", runtime)
    _write_json(output / "live_result.json", result)
    if submission:
        _write_json(output / "single_page_submission.json", submission)
    return 0 if submission else 2


class _ResumeCaller:
    def __init__(self, text: str, response_hash: str) -> None:
        self.text = text
        self.response_hash = response_hash
        self.provider_sends = 0

    def __call__(self, config: Any, request: Any) -> Any:
        from code2paper.export.run_manifest import hash_text
        from code2paper.llm.client import LLMResponse
        if isinstance(request.input_payload, Mapping) and request.input_payload.get("writer_section_repair"):
            return LLMResponse(
                text="", response_hash=hash_text(""),
                blocked_reason="resume_repair_forbidden",
            )
        return LLMResponse(
            text=self.text,
            response_hash=self.response_hash or hash_text(self.text),
            cached=True,
            response_mode="durable_ledger_reuse",
            finish_reason="resume_reuse",
        )


def _resume(args: argparse.Namespace) -> int:
    output = Path(args.output).expanduser().resolve()
    state, manifest, envelope, plan, archive = _load_state(output)
    config = _load_config(_profile_path(args.profile))
    runtime = _preflight(config)
    from code2paper.llm.tokenizer import VllmOpenAIChatTokenizer
    tokenizer = VllmOpenAIChatTokenizer(
        base_url=_base_url(), model=config.model, identity=state["tokenizer_identity"]
    )
    _verify_identity(state, runtime, tokenizer)
    from code2paper.agentic.unified_invocation_ledger import (
        build_resume_plan, rebuild_aggregate_fragments,
        read_all_completed_receipts, read_writer_content_acceptance,
    )
    ledger = _ledger(output)
    invocation_id = plan.invocations[0].invocation_id
    decision = build_resume_plan(
        ledger,
        plan,
        archive_digest=state["archive_digest"],
        workset_manifest_digest=plan.workset_manifest_digest,
        model_identity_digest=plan.model_identity_digest,
    ).decisions.get(invocation_id)
    if decision is None or decision.decision != "reuse":
        _write_json(output / "resume_decision.json", {
            "decision": _resume_decision_payload(decision) if decision else None,
            "new_provider_sends": 0,
        })
        _write_json(output / "resume_result.json", {
            "status": "fail",
            "reason": "resume_decision_not_reuse",
            "new_provider_sends": 0,
        })
        return 2
    fragment = next(
        (
            item for item in rebuild_aggregate_fragments(ledger, plan, role="writer")
            if item.get("receipt_digest") == decision.reuse_receipt_digest
        ),
        None,
    )
    if not isinstance(fragment, Mapping):
        raise ValueError("resume_fragment_missing")
    receipt = next(
        (
            item for item in read_all_completed_receipts(ledger, strict=True)
            if item.content_digest == decision.reuse_receipt_digest
        ),
        None,
    )
    if receipt is None:
        raise ValueError("resume_receipt_missing")
    sidecar = read_writer_content_acceptance(ledger, receipt)
    fragment_payload = fragment.get("fragment") or {}
    text = str((sidecar or {}).get("response_text") or fragment_payload.get("response_text") or "")
    if not text.strip() or not sidecar or not sidecar.get("accepted"):
        raise ValueError("resume_content_acceptance_missing")
    section = _section(state)
    caller = _ResumeCaller(text, str(fragment_payload.get("response_hash") or ""))
    sink = _AcceptanceSink(output, resume=True)
    from code2paper.llm.section_writer import (
        assess_publication_content_progress,
        write_publication_method_by_sections,
    )
    writer = write_publication_method_by_sections(
        config.model_copy(update={"cache": False, "retry_max_attempts": 1}),
        [section],
        llm_caller=caller,
        content_transaction_assessor=assess_publication_content_progress,
        response_attempt_sink=sink,
        page_acceptance_sink=sink,
    )
    summary = _writer_summary(writer)
    passed = (
        summary["output_count"] == 1
        and not summary["incomplete_sections"]
        and caller.provider_sends == 0
    )
    decision_payload = {
        "decision": _resume_decision_payload(decision),
        "reused_receipt_digest": receipt.content_digest,
        "new_provider_sends": caller.provider_sends,
    }
    result = {
        "status": "pass" if passed else "fail",
        "page_id": TARGET_PAGE_ID,
        "section_id": TARGET_SECTION_ID,
        "new_provider_sends": caller.provider_sends,
        "new_receipt_count": 0,
        "resume_decision": decision_payload,
        "writer": summary,
        "runtime_preflight": runtime,
        "archive_digest": archive.content_digest,
        "model_identity_digest": plan.model_identity_digest,
    }
    _write_json(output / "resume_decision.json", decision_payload)
    _write_json(output / "resume_result.json", result)
    return 0 if passed else 2


def _record(output: Path, status: str, exit_code: int, started: float, error: str = "") -> None:
    _write_json(output / "execution_record.json", {
        "schema_version": "single-page-execution-record-v1",
        "command": " ".join(sys.argv),
        "status": status,
        "exit_code": exit_code,
        "started_at_unix": started,
        "finished_at_unix": time.time(),
        "error": error,
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "live", "resume"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--output", required=True)
        sub.add_argument("--profile", default=str(_ROOT / "tests/live/profiles/qwen38_vllm_budgeted.example.env"))
        if name == "prepare":
            sub.add_argument("--frozen-root", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output).expanduser().resolve()
    started = time.time()
    try:
        if args.command == "prepare":
            _prepare(args)
            code = 0
        elif args.command == "live":
            code = _live(args)
        else:
            code = _resume(args)
        _record(output, "pass" if code == 0 else "fail", code, started)
        return code
    except Exception as exc:
        output.mkdir(parents=True, exist_ok=True)
        _record(output, "error", 2, started, f"{type(exc).__name__}:{str(exc)[:500]}")
        print(f"single-page {args.command} failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


def _ledger(output: Path) -> Path:
    return output / "artifacts" / "06_authoring" / "invocations"


class _LiveCaller:
    def __init__(self, output: Path, state: Mapping[str, Any], manifest: Any, envelope: Any, plan: Any, tokenizer: Any) -> None:
        self.output, self.state, self.manifest = output, state, manifest
        self.envelope, self.plan, self.tokenizer = envelope, plan, tokenizer
        self.ledger = _ledger(output)
        self.provider_sends = 0
        self.generation_calls = 0

    def __call__(self, config: Any, request: Any) -> Any:
        from code2paper.agentic.mechanism_context_models import canonical_json_bytes, sha256_digest
        from code2paper.agentic.unified_context_compiler import account_unified_request_tokens
        from code2paper.agentic.unified_context_models import ActualRequestReceiptV2, InvocationAttemptStartedV1
        from code2paper.agentic.unified_invocation_ledger import (
            check_run_budget_before_send, last_started_attempt,
            publish_attempt_completed, publish_attempt_started,
            publish_output_fragment, publish_provider_request,
            publish_provider_response, register_invocation_plan,
        )
        from code2paper.export.run_manifest import hash_text
        from code2paper.llm.client import LLMClient, LLMResponse

        invocation = self.plan.invocations[0]
        page = self.manifest.page_by_id(invocation.page_id)
        if page is None:
            return LLMResponse(text="", response_hash=hash_text(""), blocked_reason="target_page_missing")
        payload = request.input_payload if isinstance(request.input_payload, Mapping) else {}
        is_repair = isinstance(payload.get("writer_section_repair"), Mapping)
        failures: list[str] = []
        actual_envelope = _request_digest(request, page, tuple(invocation.task_ids))
        if not is_repair and actual_envelope != invocation.expected_request_envelope_digest:
            failures.append("primary_request_envelope_mismatch")
        if request.prompt_template_id != "unified_writer_page_v2":
            failures.append("request_template_mismatch")
        raw_pages = payload.get("shared_contexts") or ()
        raw_page = raw_pages[0] if len(raw_pages) == 1 else None
        actual_bytes = (
            raw_page if isinstance(raw_page, bytes)
            else raw_page.encode("utf-8") if isinstance(raw_page, str)
            else canonical_json_bytes(dict(raw_page)) if isinstance(raw_page, Mapping)
            else b""
        )
        actual_page_digest = sha256_digest(actual_bytes) if actual_bytes else ""
        if actual_bytes != canonical_json_bytes(dict(page.technical_payload)):
            failures.append("technical_bytes_mismatch")
        if payload.get("section_id") != TARGET_SECTION_ID:
            failures.append("section_id_mismatch")
        try:
            accounting = account_unified_request_tokens(
                consumer_role="writer",
                rendered_prompt=request.prompt,
                input_payload=request.input_payload,
                response_schema=request.response_json_schema or {},
                request_budget=self.envelope.request_budget_by_role["writer"],
                max_input_tokens=MAX_REQUEST_INPUT_TOKENS,
                model_context_tokens=self.envelope.model_context_tokens,
                safety_margin_tokens=self.envelope.safety_margin_tokens,
                meter=self.envelope.token_meter,
                tokenizer=self.tokenizer,
                invocation_id=invocation.invocation_id,
                page_id=page.page_id,
                scaffolding_reserve_tokens=0,
            )
            if not accounting.fits:
                failures.append(f"budget_overflow:{accounting.input_tokens}")
            if accounting.input_tokens > MAX_REQUEST_INPUT_TOKENS:
                failures.append(f"input_over_60000:{accounting.input_tokens}")
        except Exception as exc:
            accounting = None
            failures.append(f"meter_failed:{type(exc).__name__}")
        attempt = last_started_attempt(self.ledger, invocation.invocation_id) + 1
        if attempt > invocation.max_attempts:
            failures.append(f"attempt_limit:{attempt}>{invocation.max_attempts}")
        register_invocation_plan(self.ledger, self.plan)
        started = time.time()
        publish_attempt_started(
            self.ledger,
            InvocationAttemptStartedV1(
                invocation_id=invocation.invocation_id,
                attempt=attempt,
                plan_digest=self.plan.content_digest,
                page_id=page.page_id,
                expected_technical_bytes_digest=page.technical_bytes_digest,
                expected_request_envelope_digest=actual_envelope,
                model_identity_digest=self.envelope.model_identity_digest,
                started_at_unix=started,
                content_repair_attempt=is_repair,
            ),
        )
        if not failures:
            failures.extend(check_run_budget_before_send(
                self.ledger, self.envelope, role="writer",
                invocation_id=invocation.invocation_id,
                is_content_repair=is_repair,
                request_input_tokens=int(accounting.input_tokens),
                current_reserved_input_tokens=invocation.max_input_tokens,
                current_attempt_recorded=True,
            ))
        sent = False
        if failures:
            response = LLMResponse(
                text="", response_hash=hash_text(""),
                blocked_reason="request_rejected:" + ";".join(dict.fromkeys(failures)),
            )
        else:
            publish_provider_request(self.ledger, invocation.invocation_id, attempt, request, config)
            sent = True
            self.provider_sends += 1
            self.generation_calls += 1
            try:
                response = LLMClient(config).complete(request)
            except Exception as exc:
                response = LLMResponse(
                    text="", response_hash=hash_text(""),
                    blocked_reason=f"provider_error:{type(exc).__name__}",
                )
        response_text = str(response.text or "")
        fragment_digest = publish_output_fragment(
            self.ledger,
            invocation_id=invocation.invocation_id,
            attempt=attempt,
            fragment={
                "consumer_role": "writer",
                "phase": "writer",
                "section_id": TARGET_SECTION_ID,
                "page_id": page.page_id,
                "response_text": response_text,
                "response_hash": str(response.response_hash or ""),
                "blocked_reason": str(response.blocked_reason or ""),
            },
        )
        provider_diag = (
            publish_provider_response(self.ledger, invocation.invocation_id, attempt, response)
            if sent else ""
        )
        receipt = ActualRequestReceiptV2(
            invocation_id=invocation.invocation_id,
            attempt=attempt,
            consumer_role="writer",
            phase="writer",
            workset_id=invocation.workset_id,
            task_ids=tuple(invocation.task_ids),
            mechanism_id=invocation.mechanism_id,
            section_id=invocation.section_id,
            page_id=page.page_id,
            actual_technical_bytes_digest=actual_page_digest,
            actual_request_envelope_digest=actual_envelope,
            response_digest=_digest_text(response_text),
            fragment_digests=(fragment_digest,),
            model_identity_digest=self.envelope.model_identity_digest,
            provider_usage=getattr(response, "token_usage", None),
            provider_diagnostics_digest=provider_diag,
            reserved_input_tokens=invocation.max_input_tokens,
            token_accounting=accounting,
            started_at_unix=started,
            finished_at_unix=time.time(),
            delivery_status="accepted" if not failures else "rejected",
            delivery_rejection_code=failures[0] if failures else "",
            sent_to_caller=sent,
            task_status="partial" if response_text.strip() else "failed",
            succeeded_task_ids=(),
            failed_task_ids=tuple(invocation.task_ids),
            task_failures=tuple({"code": str(item)} for item in failures)
            + (({"code": str(response.blocked_reason)},) if response.blocked_reason else ()),
            is_repair=False,
            content_repair_attempt=is_repair,
            upstream_archive_digest=self.state["archive_digest"],
            upstream_workset_manifest_digest=self.manifest.content_digest,
            upstream_plan_digest=self.plan.content_digest,
        )
        publish_attempt_completed(self.ledger, receipt)
        _write_json(self.output / "last_live_receipt.json", receipt.model_dump(mode="json"))
        return response


class _AcceptanceSink:
    def __init__(self, output: Path, resume: bool = False) -> None:
        self.ledger = _ledger(output)
        self.resume = resume

    def __call__(self, section: Any, response: Any) -> None:
        if self.resume:
            return
        from code2paper.agentic.unified_invocation_ledger import (
            publish_writer_content_acceptance,
            read_all_completed_receipts,
            read_writer_content_acceptance,
        )
        invocation_id = str(section.prompt_payload.get("writer_invocation_id") or "")
        receipts = [
            item for item in read_all_completed_receipts(self.ledger, strict=True)
            if item.invocation_id == invocation_id
        ]
        receipts.sort(key=lambda item: (item.attempt, item.content_digest))
        receipt = next(
            (item for item in receipts if read_writer_content_acceptance(self.ledger, item) is None),
            None,
        )
        if receipt is None:
            return
        from code2paper.llm.section_writer import assess_publication_content_acceptance
        accepted, metrics = assess_publication_content_acceptance(section, response)
        metadata = getattr(response, "metadata", None)
        response_text = (
            metadata.model_dump_json()
            if hasattr(metadata, "model_dump_json")
            else str(getattr(response, "text", "") or "")
        )
        publish_writer_content_acceptance(
            self.ledger,
            receipt,
            accepted=accepted,
            response_text=response_text,
            failures=metrics["failures"],
        )


if __name__ == "__main__":
    raise SystemExit(main())
