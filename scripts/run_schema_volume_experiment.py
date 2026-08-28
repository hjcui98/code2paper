#!/usr/bin/env python3
"""WP-B real-volume Writer schema A–E on 230920 MA-S1 prompt scale."""

from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path("/home/cuihengjia/agent/Code2Paper copy")
SRC = Path("/tmp/c2p-synth-linearrag-20260825-230920")
OUT = Path("/tmp/c2p-schema-volume-20260826")
PROFILE = ROOT / "tests/live/profiles/qwen38_vllm_budgeted.example.env"
sys.path.insert(0, str(ROOT / "src"))

from code2paper.agentic.autonomous_method_agent import _writer_artifact_paths
from code2paper.agentic.publication_method_writer import (
    _default_llm_caller,
    _section_body_truncated,
    run_publication_method_writer,
)
from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.providers import load_llm_config_from_env
from code2paper.llm.role_config import METHOD_WRITER, apply_role_config


def load_profile(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or not line.startswith("export "):
            continue
        body = line[len("export ") :]
        key, _, value = body.partition("=")
        os.environ[key.strip()] = value.strip().strip("'").strip('"')


def skip_rewrite(config, request: LLMRequest) -> LLMResponse:
    return LLMResponse(
        text="",
        response_hash="experiment_skip_rewrite",
        blocked_reason="experiment_skip_rewrite",
        finish_reason="blocked",
    )


def complete_sentences(markdown: str) -> bool:
    return bool(markdown.strip()) and not _section_body_truncated(markdown)


def extract_markdown(text: str, variant: str) -> str:
    raw = (text or "").strip()
    if variant == "A":
        return raw
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                payload = json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                return raw
        else:
            return raw
    if isinstance(payload, dict):
        return str(payload.get("section_markdown") or "")
    return raw


def schema_d(base: dict) -> dict:
    schema = copy.deepcopy(base)
    props = schema.get("properties") or {}
    if "section_markdown" in props:
        markdown = props.pop("section_markdown")
        props["section_markdown"] = markdown
        schema["properties"] = props
        required = [item for item in schema.get("required") or [] if item != "section_markdown"]
        required.append("section_markdown")
        schema["required"] = required
    return schema


def schema_e(base: dict) -> dict:
    schema = copy.deepcopy(base)
    drop = {
        "new_research_requests",
        "self_identified_risks",
        "unresolved_points",
        "used_argument_unit_ids",
        "used_claim_ids",
        "used_equation_ids",
        "used_configuration_ids",
        "completed_rhetorical_moves",
    }
    props = schema.get("properties") or {}
    for key in drop:
        props.pop(key, None)
    schema["properties"] = props
    if "required" in schema:
        schema["required"] = [item for item in schema["required"] if item not in drop]
    return schema


def schema_b() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {"section_markdown": {"type": "string"}},
        "required": ["section_markdown"],
    }


def prepare_mas1_copy() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SRC / "artifacts", OUT / "artifacts", dirs_exist_ok=True)
    plan_path = OUT / "artifacts" / "method_section_plan_v2.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    keep = [section for section in plan.get("sections") or [] if section.get("section_id") == "MA-S1"]
    if not keep:
        keep = list((plan.get("sections") or [])[:1])
    keep_units = {
        unit_id
        for section in keep
        for unit_id in section.get("argument_unit_ids") or []
    }
    plan["sections"] = keep
    if "argument_units" in plan:
        plan["argument_units"] = [
            unit for unit in plan["argument_units"]
            if unit.get("argument_unit_id") in keep_units
        ]
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    authoring = OUT / "artifacts" / "06_authoring"
    for name in (
        "publication_candidate_method.md",
        "publication_writer_result_v1.json",
        "publication_section_checkpoint_v1.json",
        "writing_research_callback_artifacts_v1.json",
        "writing_research_routes_v1.json",
        "method_draft_bundle_v1.json",
        "publication_candidate_checkpoint_v1.json",
        "product_authoring_state_v1.json",
    ):
        path = authoring / name
        if path.is_file():
            path.unlink()
    checkpoints = authoring / "immutable_section_checkpoints"
    if checkpoints.is_dir():
        shutil.rmtree(checkpoints)


def main() -> None:
    load_profile(PROFILE)
    os.environ["CODE2PAPER_LLM_CACHE"] = "0"
    os.environ["CODE2PAPER_SECTION_REVISION_BUDGET"] = "0"
    os.environ["CODE2PAPER_MAX_CALLBACK_ROUNDS"] = "0"
    prepare_mas1_copy()
    dump_dir = OUT / "captured"
    dump_dir.mkdir(parents=True, exist_ok=True)
    captured: dict[str, object] = {}

    def capturing_caller(config, request: LLMRequest) -> LLMResponse:
        if request.prompt_template_id == "phase5_method_writer_section_v1" and "request" not in captured:
            captured["request"] = request
            (dump_dir / "prompt.txt").write_text(request.prompt or "", encoding="utf-8")
            (dump_dir / "input_payload.json").write_text(
                json.dumps(request.input_payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (dump_dir / "schema.json").write_text(
                json.dumps(request.response_json_schema or {}, indent=2) + "\n",
                encoding="utf-8",
            )
            meta = {
                "prompt_chars": len(request.prompt or ""),
                "payload_chars": len(json.dumps(request.input_payload, ensure_ascii=False)),
                "schema_chars": len(json.dumps(request.response_json_schema or {})),
                "thinking_token_budget": getattr(config, "thinking_token_budget", None),
                "max_output_tokens": getattr(config, "max_output_tokens", None),
                "schema_name": request.schema_name,
            }
            (dump_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
            return LLMResponse(
                text="",
                response_hash="capture_only",
                blocked_reason="schema_volume_capture",
                finish_reason="blocked",
            )
        return _default_llm_caller(config, request)

    artifact_paths = _writer_artifact_paths(OUT)
    briefs = OUT / "artifacts" / "method_argument_briefs_v1.json"
    if briefs.is_file():
        artifact_paths["method_argument_briefs_v1"] = str(briefs)
    for drop in (
        "writing_research_callback_artifacts_v1",
        "publication_section_checkpoint_v1",
        "method_propositions_v1",
        "method_proposition_bindings_v1",
    ):
        artifact_paths.pop(drop, None)
    llm_config = load_llm_config_from_env()
    run_publication_method_writer(
        out_root=OUT,
        artifact_paths=artifact_paths,
        llm_config=llm_config,
        llm_caller=capturing_caller,
        rewrite_caller=skip_rewrite,
        editor_caller=skip_rewrite,
        rebuild_architect_plan=False,
    )
    request = captured.get("request")
    if not isinstance(request, LLMRequest):
        raise SystemExit("failed to capture MA-S1 writer request")
    writer_config = apply_role_config(llm_config, METHOD_WRITER, extended_writer_budget=False)
    client = LLMClient(writer_config)
    base_schema = request.response_json_schema or {}
    variants = {
        "A": None,
        "B": schema_b(),
        "C": base_schema,
        "D": schema_d(base_schema),
        "E": schema_e(base_schema),
    }
    rows = []
    for name, schema in variants.items():
        prompt = request.prompt
        if name == "A":
            prompt = (request.prompt or "") + "\nWrite the section as Markdown only, starting with the supplied H2."
        variant_request = LLMRequest(
            prompt_template_id=f"schema_volume_{name}",
            prompt=prompt,
            input_payload=request.input_payload,
            schema_name="" if name == "A" else request.schema_name,
            response_json_schema=schema,
        )
        started = time.time()
        response = client.complete(variant_request)
        elapsed = time.time() - started
        markdown = extract_markdown(response.text or "", name)
        usage = response.token_usage or {}
        row = {
            "variant": name,
            "elapsed_s": round(elapsed, 2),
            "finish_reason": response.finish_reason,
            "blocked_reason": response.blocked_reason,
            "text_chars": len(response.text or ""),
            "markdown_chars": len(markdown),
            "complete_sentence": complete_sentences(markdown),
            "truncated": _section_body_truncated(markdown),
            "thinking_token_budget": writer_config.thinking_token_budget,
            "token_usage": usage,
            "prompt_chars": len(request.prompt or ""),
            "payload_chars": len(json.dumps(request.input_payload, ensure_ascii=False)),
            "schema_chars": len(json.dumps(schema or {})),
            "markdown_tail": markdown[-180:],
        }
        rows.append(row)
        (OUT / f"variant_{name}_response.txt").write_text(response.text or "", encoding="utf-8")
        (OUT / f"variant_{name}_markdown.md").write_text(markdown, encoding="utf-8")
        print(json.dumps({k: v for k, v in row.items() if k != "markdown_tail"}, ensure_ascii=False), flush=True)
    (OUT / "schema_volume_report.json").write_text(
        json.dumps({"rows": rows}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
