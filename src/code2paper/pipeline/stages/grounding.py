"""Phase 4 grounding artifacts for authoring and auditability."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from code2paper.export.run_manifest import hash_file
from code2paper.core.output_names import method_output
from code2paper.core.schemas import ClaimEvidenceMap, LLMConfig, LLMProvider, MethodEvidence
from code2paper.llm.client import LLMClient, LLMRequest


LLM_JSON_RETRY_ATTEMPTS = 3
JSON_OBJECT_SCHEMA: dict[str, Any] = {"type": "object"}


def write_phase4_artifacts(
    *,
    method_root: Path,
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap,
    llm_config: LLMConfig | None = None,
) -> dict[str, Path]:
    method_root.mkdir(parents=True, exist_ok=True)
    code_context = _adjacent_code_context(method_root)
    paths = {
        "grounding_context": method_output(method_root, "grounding_context"),
        "equation_candidates": method_output(method_root, "equation_candidates"),
        "equations_tex": method_output(method_root, "equations_tex"),
        "symbols_tex": method_output(method_root, "symbols_tex"),
        "phase4_manifest": method_output(method_root, "phase4_manifest"),
    }
    llm_call_logs: list[str] = []
    equation_candidates = _equation_candidate_records(
        method_evidence,
        claim_map=claim_map,
        code_context=code_context,
    )
    llm_equations, llm_symbols, llm_report, llm_call_logs = _llm_grounded_equation_records(
        method_evidence=method_evidence,
        claim_map=claim_map,
        code_context=code_context,
        existing=equation_candidates,
        llm_config=llm_config,
    )
    equation_candidates = _merge_equation_records(equation_candidates, llm_equations)
    paths["grounding_context"].write_text(
        _grounding_context(method_evidence, claim_map, equation_candidates=equation_candidates),
        encoding="utf-8",
    )
    _write_json(
        paths["equation_candidates"],
        {
            "equations": equation_candidates,
            "symbols": llm_symbols,
            "llm_grounding_report": llm_report,
        },
    )
    paths["equations_tex"].write_text(_equations_tex(equation_candidates), encoding="utf-8")
    paths["symbols_tex"].write_text(
        _symbols_tex(method_evidence, code_context=code_context, grounded_symbols=llm_symbols),
        encoding="utf-8",
    )
    manifest = {
        "project_id": method_evidence.project_id,
        "mode": "equation-and-symbol-grounding",
        "equation_candidates": len(equation_candidates),
        "llm_grounded_equations": len(llm_equations),
        "llm_available": bool(llm_config and llm_config.provider != LLMProvider.NONE),
        "llm_blocked_reason": str(llm_report.get("blocked_reason") or ""),
        "llm_call_logs": llm_call_logs,
        "tensor_roles": len(method_evidence.tensor_roles),
        "architecture_parameters": len(method_evidence.architecture_parameters),
        "outputs": {
            name: {"path": str(path), "hash": hash_file(path)}
            for name, path in paths.items()
            if name != "phase4_manifest"
        },
    }
    _write_json(paths["phase4_manifest"], manifest)
    return paths


def _grounding_context(
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap,
    *,
    equation_candidates: list[dict[str, Any]] | None = None,
) -> str:
    lines = [
        f"# Grounding Context for {method_evidence.method_name}",
        "",
        "## Method Goal",
        method_evidence.method_goal,
        "",
        "## Evidence-backed Stages",
    ]
    for stage in method_evidence.stages:
        lines.append(f"- {stage.stage_id} {stage.name}: {stage.purpose}")
        if stage.inputs:
            lines.append(f"  Inputs: {', '.join(stage.inputs[:6])}")
        if stage.outputs:
            lines.append(f"  Outputs: {', '.join(stage.outputs[:6])}")
    supported_claims = [claim for claim in claim_map.claims if claim.support_status.value != "unsupported"]
    lines.extend(["", "## Supported Claims"])
    if supported_claims:
        for claim in supported_claims[:20]:
            evidence = ", ".join(claim.evidence_ids[:8]) or "none"
            lines.append(f"- {claim.claim_id}: {claim.claim_text} [evidence: {evidence}]")
    else:
        lines.append("- No strongly supported claims were frozen; keep wording conservative.")
    lines.extend(["", "## Equation Candidates"])
    if equation_candidates:
        for equation in equation_candidates[:12]:
            evidence = ", ".join(equation.get("evidence_ids", [])[:8]) or "none"
            placement = str(equation.get("placement_hint") or "").strip()
            placement_text = f" [place near: {placement}]" if placement else ""
            lines.append(
                f"- {equation.get('equation_id')} {equation.get('name')}: "
                f"{equation.get('latex')} [evidence: {evidence}]{placement_text}"
            )
    else:
        lines.append("- No explicit equation candidates were extracted from code.")
        lines.append("- Do not invent display equations; describe mechanisms in prose unless evidence-backed formulas can be synthesized.")
    lines.extend(
        [
            "",
            "## Grounding Policy",
            "- Equations and symbols are supportive scaffolds; they must not introduce unsupported claims.",
            "- Prefer notation consistency across stages over aggressive formula invention.",
            "- If explicit code-level equations are missing, use stage-structured notation templates only when supported evidence IDs are available.",
            "- Place equations inside the subsection whose operation they define; avoid collecting them in a detached prelude or appendix-like block.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _equations_tex(equation_candidates: list[dict[str, Any]]) -> str:
    blocks = ["% Equation bundle for method authoring"]
    normalized_latex: set[str] = set()
    ordered_equations: list[dict[str, Any]] = []

    for equation in equation_candidates:
        latex = str(equation.get("latex") or "").strip()
        if not _valid_equation_latex(latex):
            continue
        key = _normalize_equation_key(latex)
        if key not in normalized_latex:
            normalized_latex.add(key)
            ordered_equations.append(equation)

    ordered_equations = sorted(ordered_equations, key=lambda item: _equation_authoring_priority(str(item.get("latex") or "")))
    for equation in ordered_equations:
        latex = str(equation.get("latex") or "").strip()
        if not _valid_equation_latex(latex):
            continue
        blocks.append(
            "% "
            + " | ".join(
                part
                for part in [
                    str(equation.get("equation_id") or "EQ"),
                    str(equation.get("name") or "Method equation"),
                    f"role={equation.get('role') or 'method relation'}",
                    f"source={equation.get('source') or 'method_evidence'}",
                    f"place={equation.get('placement_hint') or 'relevant method subsection'}",
                    "evidence=" + ",".join(equation.get("evidence_ids") or []),
                ]
                if part
            )
        )
        blocks.append("\\begin{equation}")
        blocks.append(latex)
        blocks.append("\\end{equation}")
        blocks.append("")

    if len(normalized_latex) == 0:
        blocks.append("% No evidence-backed equations were extracted; no generic fallback equations emitted.")
    return "\n".join(blocks).rstrip() + "\n"


def _valid_equation_latex(latex: str) -> bool:
    text = str(latex or "").strip()
    if not text or text.startswith("%"):
        return False
    return bool(re.search(r"[A-Za-z0-9]", text))


def _equation_candidate_records(
    method_evidence: MethodEvidence,
    *,
    claim_map: ClaimEvidenceMap,
    code_context: str = "",
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for equation in _dedupe_equation_candidates(method_evidence):
        latex = str(equation.latex or "").strip()
        if not _valid_equation_latex(latex):
            continue
        key = _normalize_equation_key(latex)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "equation_id": str(equation.equation_id or f"EQ{len(records) + 1}"),
                "name": str(equation.name or _equation_extractive_name(latex)),
                "role": _equation_extractive_name(latex),
                "latex": latex,
                "source": str(equation.source or "method_evidence"),
                "evidence_ids": list(equation.evidence_ids or []),
                "confidence": str(equation.confidence or "medium"),
                "placement_hint": _equation_placement_hint(latex, fallback=str(equation.name or "")),
            }
        )
    return records


def _llm_grounded_equation_records(
    method_evidence: MethodEvidence,
    *,
    claim_map: ClaimEvidenceMap,
    code_context: str,
    existing: list[dict[str, Any]],
    llm_config: LLMConfig | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[str]]:
    if llm_config is None or llm_config.provider == LLMProvider.NONE:
        return [], [], {"mode": "skipped", "blocked_reason": "llm_provider_not_configured"}, []
    payload = _formula_grounding_payload(
        method_evidence=method_evidence,
        claim_map=claim_map,
        code_context=code_context,
        existing=existing,
    )
    request = LLMRequest(
        prompt_template_id="stage5_formula_grounding_v1",
        prompt=_formula_grounding_prompt(),
        input_payload=payload,
        schema_name="formula_grounding",
        response_json_schema=JSON_OBJECT_SCHEMA,
    )
    response, parsed, call_logs = _complete_json_request_with_retries(llm_config=llm_config, request=request)
    if response.blocked_reason:
        return [], [], {"mode": "blocked", "blocked_reason": response.blocked_reason}, call_logs
    if not isinstance(parsed, dict):
        return [], [], {"mode": "parse_failed", "blocked_reason": "formula_grounding_response_not_json"}, call_logs
    valid_evidence_ids = _all_evidence_ids(method_evidence, claim_map)
    existing_keys = {_normalize_equation_key(str(item.get("latex") or "")) for item in existing}
    equations: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for item in parsed.get("equations", []) if isinstance(parsed.get("equations"), list) else []:
        record, reason = _normalize_llm_equation_record(
            item,
            index=len(equations) + 1,
            valid_evidence_ids=valid_evidence_ids,
        )
        if record is None:
            rejected.append({"reason": reason, "item": _safe_preview(item)})
            continue
        key = _normalize_equation_key(str(record.get("latex") or ""))
        if key in existing_keys:
            continue
        existing_keys.add(key)
        equations.append(record)
    symbols = _normalize_llm_symbols(parsed.get("symbols", []), valid_evidence_ids=valid_evidence_ids)
    report = {
        "mode": "llm-grounded",
        "blocked_reason": "",
        "raw_equation_count": len(parsed.get("equations", []) if isinstance(parsed.get("equations"), list) else []),
        "accepted_equation_count": len(equations),
        "accepted_symbol_count": len(symbols),
        "rejected": rejected[:20],
    }
    return equations[:16], symbols[:80], report, call_logs


def _complete_json_request_with_retries(
    *,
    llm_config: LLMConfig,
    request: LLMRequest,
) -> tuple[Any, Any, list[str]]:
    call_logs: list[str] = []
    response = None
    parsed = None
    from code2paper.llm.role_config import AUTHORING_PLANNER, apply_role_config

    no_cache_config = apply_role_config(llm_config, AUTHORING_PLANNER).model_copy(update={"cache": False})

    for attempt in range(1, LLM_JSON_RETRY_ATTEMPTS + 1):
        response = LLMClient(no_cache_config).complete(request)
        if response.response_hash:
            call_logs.append(response.response_hash)

        if response.blocked_reason:
            if attempt < LLM_JSON_RETRY_ATTEMPTS and _should_retry_grounding_blocked_reason(response.blocked_reason):
                continue
            return response, None, call_logs

        parsed = _parse_json_object(response.text)
        if isinstance(parsed, dict):
            return response, parsed, call_logs

        if attempt >= LLM_JSON_RETRY_ATTEMPTS:
            return response, parsed, call_logs

    return response, parsed, call_logs


def _should_retry_grounding_blocked_reason(reason: str) -> bool:
    text = str(reason or "").lower()
    return "provider_response_empty_content" in text


def _formula_grounding_prompt() -> str:
    return "\n".join(
        [
            "You are grounding Method-section equations from implementation evidence.",
            "Return only JSON with this exact shape:",
            "{\"equations\": [{\"name\": str, \"role\": str, \"latex\": str, \"placement_hint\": str, \"evidence_ids\": [str], \"symbols\": {str: str}, \"confidence\": \"high|medium|low\", \"rationale\": str}], \"symbols\": [{\"symbol\": str, \"meaning\": str, \"evidence_ids\": [str]}]}",
            "",
            "Hard rules:",
            "- Produce formulas only when they are supported by concrete evidence_ids from the input.",
            "- Do not invent generic fallback equations, placeholder pipelines, or formulas unrelated to the code evidence.",
            "- Prefer method-specific transformations, selection rules, scoring functions, objectives, losses, projections, updates, normalization, masking, aggregation, and optimization relations.",
            "- It is allowed to write detailed equations when evidence supports the actual computation. Do not simplify every relation into a loss sum.",
            "- Use publication-ready notation, but keep it traceable to code snippets, facts, claims, or author marks.",
            "- Do not include equations for boilerplate, CLI, logging, checkpointing, evaluation-only metrics, or unsupported author wishes.",
            "- If no evidence-supported equations exist, return empty arrays.",
            "- Each equation must include non-empty evidence_ids and a placement_hint naming the subsection/mechanism where it belongs.",
        ]
    )


def _formula_grounding_payload(
    *,
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap,
    code_context: str,
    existing: list[dict[str, Any]],
) -> dict[str, Any]:
    supported_claims = [
        claim.model_dump(mode="json")
        for claim in claim_map.claims
        if claim.support_status.value != "unsupported" and claim.evidence_ids
    ][:80]
    return {
        "method_name": method_evidence.method_name,
        "method_goal": method_evidence.method_goal,
        "stages": [stage.model_dump(mode="json") for stage in method_evidence.stages[:16]],
        "frozen_mechanisms": [item.model_dump(mode="json") for item in method_evidence.frozen_mechanisms[:80]],
        "stage_packets": list(getattr(method_evidence, "stage_packets", []) or [])[:16],
        "existing_equation_candidates": existing[:24],
        "tensor_roles": [item.model_dump(mode="json") for item in method_evidence.tensor_roles[:80]],
        "architecture_parameters": [item.model_dump(mode="json") for item in method_evidence.architecture_parameters[:80]],
        "supported_claims": supported_claims,
        "code_context": code_context[:80_000],
    }


def _normalize_llm_equation_record(
    item: Any,
    *,
    index: int,
    valid_evidence_ids: set[str],
) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(item, dict):
        return None, "not_object"
    latex = str(item.get("latex") or "").strip()
    if not _valid_equation_latex(latex):
        return None, "invalid_or_empty_latex"
    evidence_ids = _dedupe([str(eid) for eid in item.get("evidence_ids", []) if str(eid) in valid_evidence_ids])
    if not evidence_ids:
        return None, "missing_valid_evidence_ids"
    confidence = str(item.get("confidence") or "medium").lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"
    return (
        {
            "equation_id": f"LLMEQ{index}",
            "name": str(item.get("name") or _equation_extractive_name(latex)).strip()[:120],
            "role": str(item.get("role") or _equation_extractive_name(latex)).strip()[:160],
            "latex": latex,
            "source": "llm_grounded",
            "evidence_ids": evidence_ids[:12],
            "confidence": confidence,
            "placement_hint": str(item.get("placement_hint") or "").strip()[:160],
            "symbols": item.get("symbols") if isinstance(item.get("symbols"), dict) else {},
            "rationale": str(item.get("rationale") or "").strip()[:500],
        },
        "",
    )


def _normalize_llm_symbols(value: Any, *, valid_evidence_ids: set[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    symbols: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").strip()
        meaning = str(item.get("meaning") or "").strip()
        if not symbol or not meaning or symbol in seen:
            continue
        evidence_ids = _dedupe([str(eid) for eid in item.get("evidence_ids", []) if str(eid) in valid_evidence_ids])
        if not evidence_ids:
            continue
        seen.add(symbol)
        symbols.append({"symbol": symbol[:80], "meaning": meaning[:240], "evidence_ids": evidence_ids[:8]})
    return symbols


def _merge_equation_records(base: list[dict[str, Any]], extra: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*base, *extra]:
        latex = str(item.get("latex") or "").strip()
        key = _normalize_equation_key(latex)
        if not key or key in seen:
            continue
        if not item.get("evidence_ids"):
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _stage_evidence_ids(stage: Any) -> list[str]:
    ids: list[str] = []
    for mechanism in getattr(stage, "mechanisms", []) or []:
        ids.extend(getattr(mechanism, "evidence_ids", []) or [])
    return _dedupe(ids)


def _stage_mechanism_ids(stage: Any) -> list[str]:
    return [str(getattr(mechanism, "mechanism_id", "") or "") for mechanism in getattr(stage, "mechanisms", []) or []]


def _flatten_packet_evidence_ids(packet: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    if not packet:
        return ids
    ids.extend(str(item) for item in packet.get("evidence_ids", []) or [])
    for value in packet.values():
        if isinstance(value, dict):
            ids.extend(_flatten_packet_evidence_ids(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    ids.extend(_flatten_packet_evidence_ids(item))
    return _dedupe(ids)


def _equation_placement_hint(latex: str, *, fallback: str = "") -> str:
    family = _equation_family_for_grounding(latex)
    hints = {
        "photometric_loss": "objective or reconstruction-loss subsection",
        "total_objective": "objective or training subsection",
        "stage_transform": "core transformation subsection",
        "score_accumulation": "score computation subsection",
        "selection_rule": "selection, densification, or pruning subsection",
        "distance_culling": "distance/culling/rasterization subsection",
    }
    return fallback or hints.get(family, "relevant method subsection")


def _equation_extractive_name(latex: str) -> str:
    family = _equation_family_for_grounding(latex)
    names = {
        "photometric_loss": "Photometric reconstruction loss",
        "total_objective": "Total objective",
        "stage_transform": "Stage transformation",
    }
    return names.get(family, "Method equation")


def _equation_family_for_grounding(latex: str) -> str:
    lowered = _normalize_equation_key(latex).lower()
    if "\\operatorname{ssim}" in lowered or "\\mathcal{l}_{\\mathrm{rec}" in lowered:
        return "photometric_loss"
    if "\\mathcal{l}=" in lowered:
        return "total_objective"
    if "z_{0}=x" in lowered:
        return "stage_transform"
    if "s_i=" in lowered and "\\sum" in lowered:
        return "score_accumulation"
    if "\\mathcal{d}=" in lowered or "\\mathcal{p}=" in lowered or "\\mathcal{a}=" in lowered:
        return "selection_rule"
    if "sigma_i^{-1}" in lowered or "d_{ij}" in lowered:
        return "distance_culling"
    return "other"


def _dedupe_equation_candidates(method_evidence: MethodEvidence) -> list[Any]:
    deduped: list[Any] = []
    seen: set[str] = set()
    for equation in method_evidence.equation_candidates:
        key = _normalize_equation_key(str(equation.latex or ""))
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(equation)
    return deduped


def _normalize_equation_key(latex: str) -> str:
    return re.sub(r"\s+", "", str(latex or ""))


def _adjacent_code_context(method_root: Path) -> str:
    chunks: list[str] = []
    for key in ("snippets", "facts", "analysis", "evidence", "claims"):
        path = method_output(method_root, key)
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        chunks.extend(_flatten_strings(payload)[:250])
    return " ".join(chunks)[:120_000]


def _equation_authoring_priority(latex: str) -> tuple[int, str]:
    lowered = str(latex or "").lower()
    priority_terms = (
        ("s_{\\mathrm{out}", 0),
        ("operatorname{ce}", 0),
        ("\\mathcal{l}_{\\mathrm{task}", 0),
        ("\\mathcal{l}_{\\mathrm{reg}", 0),
        ("\\bar{f}_{", 1),
        ("u^{(\\ell)}v^{(\\ell)}", 2),
        ("operatorname{group}", 3),
        ("operatorname{normalize}", 4),
        ("operatorname{embed}", 5),
        ("operatorname{enc}", 5),
        ("operatorname{pred}", 6),
        ("operatorname{proj}", 7),
        ("operatorname{sg}", 8),
        ("operatorname{dec}", 9),
        ("\\mathcal{l}_{\\mathrm{rec}", 12),
        ("\\min", 13),
        ("loss", 14),
        ("\\mathcal{l}", 14),
        ("operatorname{attn}", 20),
        ("softmax", 21),
        ("\\mathrm{ffn}", 22),
        ("\\mathrm{pe}", 23),
    )
    for term, priority in priority_terms:
        if term in lowered:
            return (priority, lowered)
    return (15, lowered)


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_flatten_strings(item))
        return out
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_flatten_strings(item))
        return out
    if value is None:
        return []
    return [str(value)]


def _all_evidence_ids(method_evidence: MethodEvidence, claim_map: ClaimEvidenceMap) -> set[str]:
    ids: set[str] = set()
    for item in _flatten_strings(method_evidence.model_dump(mode="json")):
        for match in re.findall(r"\bE[A-Za-z0-9_.:-]+\b", item):
            ids.add(match)
    for claim in claim_map.claims:
        ids.update(str(eid) for eid in claim.evidence_ids if str(eid).startswith("E"))
    return ids


def _parse_json_object(text: str) -> Any:
    raw = str(text or "").strip()
    raw = re.sub(r"^\s*```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```\s*$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _safe_preview(value: Any) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        text = str(value)
    return text[:500]


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _symbols_tex(
    method_evidence: MethodEvidence,
    *,
    code_context: str = "",
    grounded_symbols: list[dict[str, Any]] | None = None,
) -> str:
    lines = [
        "% Symbol guidance for authoring (prefer inline explanations near equations).",
        "\\paragraph{Notation Guidance}",
        "Use symbol explanations directly after each equation (e.g., 'where ...').",
        "Avoid standalone symbol tables in the main method narrative.",
        "",
        "\\begin{itemize}",
    ]
    stage_count = max(1, len(method_evidence.stages))
    default_items = [
        "$x$: model input.",
        "$z_i$: latent representation after stage $i$ ($i=1,\\ldots," + str(stage_count) + "$).",
        "$F_i(\\cdot)$: transformation in stage $i$.",
        "$\\theta_i$: parameters of stage-$i$ module(s).",
        "$\\hat{y}$: final prediction.",
    ]
    if _has_training_signal(method_evidence):
        default_items.extend(
            [
                "$\\mathcal{L}$: total training objective.",
                "$\\mathcal{L}_k$: objective component $k$.",
                "$\\lambda_k$: weighting coefficient for $\\mathcal{L}_k$.",
            ]
        )
    for item in grounded_symbols or []:
        symbol = _escape_tex(str(item.get("symbol") or ""))
        meaning = _escape_tex(str(item.get("meaning") or ""))
        if symbol and meaning:
            lines.append("\\item " + symbol + ": " + meaning + ".")
    for item in default_items:
        lines.append("\\item " + item)

    for tensor in method_evidence.tensor_roles[:10]:
        lines.append(
            "\\item "
            + _escape_tex(tensor.name)
            + ": "
            + _escape_tex(tensor.role)
            + " (anchor: "
            + _escape_tex(f"{tensor.path}:{tensor.symbol}")
            + ")."
        )
    for param in method_evidence.architecture_parameters[:8]:
        lines.append(
            "\\item "
            + _escape_tex(param.name)
            + ": "
            + _escape_tex(str(param.value))
            + " (anchor: "
            + _escape_tex(f"{param.path}:{param.symbol}")
            + ")."
        )
    lines.extend(["\\end{itemize}", ""])
    return "\n".join(lines).rstrip() + "\n"


def _has_training_signal(method_evidence: MethodEvidence) -> bool:
    text_chunks: list[str] = [method_evidence.method_goal]
    text_chunks.extend(stage.name for stage in method_evidence.stages)
    text_chunks.extend(stage.purpose for stage in method_evidence.stages)
    text_chunks.extend(contract.claim_intent for contract in method_evidence.claim_contracts)
    text_chunks.extend(mechanism.mechanism_description for mechanism in method_evidence.frozen_mechanisms)
    combined = " ".join(chunk for chunk in text_chunks if chunk).lower()
    keywords = {
        "train",
        "training",
        "optimiz",
        "loss",
        "objective",
        "backprop",
        "gradient",
        "epoch",
        "scheduler",
    }
    return any(keyword in combined for keyword in keywords)


def _escape_tex(value: str) -> str:
    text = str(value)
    replacements = {
        "\\": "\\textbackslash{}",
        "&": "\\&",
        "%": "\\%",
        "$": "\\$",
        "#": "\\#",
        "_": "\\_",
        "{": "\\{",
        "}": "\\}",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
