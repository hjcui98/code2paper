"""Adapt grounded method drafts into PaperBanana figure briefs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable


GROUNDING_COMMENT_RE = re.compile(r"<!--\s*c2p:.*?-->", re.DOTALL)
TEX_GROUNDING_COMMENT_RE = re.compile(r"^\s*%\s*c2p:.*$", re.MULTILINE)
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
TEX_HEADING_RE = re.compile(
    r"\\(?:(?:sub)*section|(?:sub)?paragraph)(?:\[[^\]]*\])?\{([^{}]+)\}"
)
TEX_FORMAT_COMMAND_RE = re.compile(
    r"\\(?:textbf|textit|emph|texttt|mathrm|mathbf|mathit|mathsf|operatorname)\{([^{}]*)\}"
)
TEX_SECTION_COMMAND_RE = re.compile(r"\\(?:sub)*section(?:\[[^\]]*\])?\{([^{}]*)\}")
TEX_DROP_COMMAND_RE = re.compile(r"\\(?:label|ref|eqref|cite|citep|citet|autoref|cref|Cref)\{[^{}]*\}")
TEX_COMMAND_RE = re.compile(r"\\[a-zA-Z]+(?:\[[^\]]*\])?")
TEX_ESCAPES = {
    r"\_": "_",
    r"\%": "%",
    r"\&": "&",
    r"\#": "#",
    r"\$": "$",
    r"\{": "{",
    r"\}": "}",
    r"\textasciitilde{}": "~",
    r"\textbackslash{}": "\\",
}
UNKNOWN_VALUE = "unspecified"
DIAGRAM_SLOT_ORDER = [
    "backbone_and_depth",
    "branch_structure",
    "loss_logit_path",
]
_META_STAGE_HINTS = (
    "overview",
    "prelim",
    "introduction",
    "setup",
    "parse",
    "argument",
    "config",
    "entrypoint",
    "cli",
    "notes",
    "report",
    "ablation",
    "implementation details",
)
_INNOVATION_HINTS = (
    "propose",
    "proposed",
    "novel",
    "introduce",
    "key idea",
    "innovation",
    "predict",
    "replace",
    "cross-attention",
    "shared parameter",
    "stop-gradient",
    "mask",
    "center",
    "fusion",
    "alignment",
)


def read_method_draft(path: str | Path) -> str:
    """Read a method draft from Markdown or TeX."""

    return Path(path).read_text(encoding="utf-8")


def clean_method_draft(text: str) -> str:
    """Remove audit-only grounding comments while preserving paper content."""

    text = GROUNDING_COMMENT_RE.sub("", text)
    text = TEX_GROUNDING_COMMENT_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def clean_tex_to_plain_text(text: str) -> str:
    """Convert lightweight Method TeX into plain text for PaperBanana."""

    text = clean_method_draft(text)
    text = re.sub(r"(?<!\\)%.*$", "", text, flags=re.MULTILINE)
    text = TEX_DROP_COMMAND_RE.sub("", text)
    text = TEX_SECTION_COMMAND_RE.sub(lambda match: f"\n{match.group(1)}\n", text)
    text = re.sub(r"\\(?:begin|end)\{(?:itemize|enumerate|description)\}", "\n", text)
    text = re.sub(r"\\item(?:\[[^\]]*\])?", "- ", text)
    text = re.sub(r"\\(?:begin|end)\{[^{}]*\}", "\n", text)

    previous = None
    while previous != text:
        previous = text
        text = TEX_FORMAT_COMMAND_RE.sub(r"\1", text)

    text = re.sub(r"\\\((.*?)\\\)", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"\\\[(.*?)\\\]", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"\$\$(.*?)\$\$", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"\$(.*?)\$", r"\1", text, flags=re.DOTALL)
    text = _normalize_math_notation(text)

    for escaped, plain in TEX_ESCAPES.items():
        text = text.replace(escaped, plain)
    text = text.replace("~", " ")
    text = re.sub(r"---|--", "-", text)
    text = TEX_COMMAND_RE.sub("", text)
    text = re.sub(r"[{}]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def extract_section_titles(text: str) -> list[str]:
    """Extract draft section titles for figure metadata and fallback layout."""

    titles: list[str] = []
    for match in MARKDOWN_HEADING_RE.finditer(text):
        title = _normalize_title(_strip_inline_markup(match.group(2)))
        if title and title.lower() != "method":
            titles.append(title)
    for match in TEX_HEADING_RE.finditer(text):
        title = _normalize_title(_strip_inline_markup(match.group(1)))
        if title and title.lower() != "method" and title not in titles:
            titles.append(title)
    return titles


def build_diagram_intent_ir(
    draft_text: str,
    *,
    method_evidence_payload: dict[str, Any] | None = None,
    claim_map_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build diagram intent IR with slot completion from method and code evidence."""

    method_text = clean_method_draft(draft_text)
    evidence_payload = method_evidence_payload or {}
    claim_payload = claim_map_payload or {}
    section_titles = extract_section_titles(method_text)
    code_blob = _evidence_text_blob(evidence_payload)
    claim_blob = _claims_text_blob(claim_payload)
    equation_hints = _extract_equation_hints(method_text)
    has_equation = bool(equation_hints)

    slot_map = _detect_slots(
        method_text=method_text,
        code_blob=code_blob,
        claim_blob=claim_blob,
        has_equation=has_equation,
    )
    missing_slots = [
        slot_name
        for slot_name in DIAGRAM_SLOT_ORDER
        if slot_map.get(slot_name, {}).get("status") != "filled"
    ]

    required_nodes = _derive_required_nodes(evidence_payload, section_titles)
    required_edges = _derive_required_edges(required_nodes)
    expansion_actions = _diagram_intent_expander(slot_map=slot_map, method_text=method_text, code_blob=code_blob)
    code_summary = _build_code_summary(slot_map=slot_map, evidence_payload=evidence_payload)
    is_multimodal = _detect_multimodal_pipeline(method_text, evidence_payload)
    innovation_focus = _extract_innovation_focus(
        method_text=method_text,
        method_evidence_payload=evidence_payload,
        claim_map_payload=claim_payload,
    )

    return {
        "version": "diagram_intent_v1",
        "required_nodes": required_nodes,
        "required_edges": required_edges,
        "slots": slot_map,
        "missing_slots": missing_slots,
        "expansion_actions": expansion_actions,
        "code_summary": code_summary,
        "equation_hints": equation_hints,
        "is_multimodal": is_multimodal,
        "innovation_focus": innovation_focus,
        "method_text_excerpt": method_text[:2000],
    }


def build_paperbanana_figure_brief(
    draft_text: str,
    *,
    method_evidence_path: str | Path | None = None,
    claim_map_path: str | Path | None = None,
    semantic_anchor: str = "",
    revision_note: str = "",
) -> str:
    """Build the text payload handed to PaperBanana from the method text.

    Keep this payload close to the paper prose. Earlier versions mixed in the
    internal figure-planning IR, which made the image model draw the planning
    artifact rather than the method. The evidence paths are accepted for API
    compatibility, but the visible prompt remains a cleaned method brief.
    """

    clean_text = clean_method_text_for_figure(draft_text)
    section_titles = extract_section_titles(clean_text)
    equation_hints = _extract_equation_hints(clean_text)

    lines = [
        "Create one paper-ready method overview figure from the cleaned Method text below.",
        "",
        "Use the Method text as the primary and sufficient source. Do not render any hidden planning JSON, audit report, code file tree, or quality-check artifact.",
        "",
        "Figure style:",
        "- Draw an academic architecture schematic, not a warning/error diagram and not a generic software pipeline.",
        "- Use one clean left-to-right mainline with compact side branches for losses or auxiliary prediction.",
        "- Use module regions, point/token/feature glyphs, arrows, masks, predictor/decoder blocks, and small loss callouts when the text supports them.",
        "- Do not place a large title on the canvas.",
        "- Do not use circled step numbers, large numeric labels, red crosses, alert icons, database/cloud icons, or generic dashboard panels.",
        "- Keep labels short and paper-like; prefer exact module names from the Method text.",
        "- Do not render detailed mathematical derivations, long equations, fractions, summations, integrals, derivatives, matrices, or multi-line formulas.",
        "- Use symbols and short labels when helpful; only render short structural formulas such as y = f(x), F = F_a + F_b, or s = alpha * s1 + beta * s2.",
        "- Replace concrete calculation formulas with named blocks or arrows; do not show how losses, scores, distances, attentions, or probabilities are computed.",
        "- Exclude implementation-only details, file paths, evidence ids, and validation language.",
        "",
        "Expected content extraction:",
        "- Identify the input representation, patch/token construction, masking or branching, encoder/predictor/core module, decoder/reconstruction path, losses, and final transferred representation if present.",
        "- Highlight the core methodological innovation more strongly than routine setup.",
        "- If a detail is absent from the Method text, omit it rather than inventing it.",
    ]

    if revision_note.strip():
        lines.extend(["", "Revision focus:", f"- {revision_note.strip()}"])
    if section_titles:
        lines.extend(["", "Detected draft sections:", *[f"- {title}" for title in section_titles]])
    if equation_hints:
        lines.extend(["", "Figure-safe equation hints:", *[f"- {hint}" for hint in equation_hints]])

    lines.extend(["", "Cleaned Method text:", clean_text])
    return "\n".join(lines).strip() + "\n"


def clean_method_text_for_figure(text: str) -> str:
    """Clean a full Method draft into prose that is easier to draw."""

    text = clean_method_draft(text)
    if _looks_like_tex_document(text):
        text = clean_tex_to_plain_text(text)

    figure_equations = _select_figure_equations(text, max_equations=3)
    text = _remove_display_equations_for_figure(text)
    text = _normalize_inline_math_for_figure(text)

    # Remove prompt or repair-template residue if an authoring fallback leaked it
    # into the draft. The filter is generic and only targets meta-writing
    # instructions, not method content.
    residue_patterns = [
        r"\bdefines one paper-facing subsection of the method\.?",
        r"\bRepresent the paper-facing stage named\b[^.]*\.?",
        r"\bThis paragraph should\b[^.]*\.?",
        r"\bThis subsection must\b[^.]*\.?",
        r"\bThe paper-facing text should\b[^.]*\.?",
        r"\bWhen the implementation contains multiple helper branches,\s*[^.]*\.?",
        r"\bThe description also names\b[^.]*\.?",
        r"\bThis stage is described at the algorithmic level,\s*[^.]*\.?",
        r"\bThe section follows the author-provided method spine\b[^.]*\.?",
        r"\bkeeping every claim tied to\b[^.]*\.?",
        r"\bThis makes the generated Method section usable\b[^.]*\.?",
        r"\bThe associated modules implement infrastructure utility and model computation block\.?",
        r"\bMechanistically,\s*This stage performs the core representation transformation that drives the method behavior\.?",
        r"\bThe objective discussion is further constrained by the supported claims:\s*.*?(?=\n\n|$)",
        r"\bThe method contains a paper-facing stage named\b[^.]*\.?",
    ]
    for pattern in residue_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    text = re.sub(r"\bgoal is Describe\b", "goal is to describe", text)
    text = re.sub(
        r"PCP MAE Method Pipeline is described as a method pipeline whose goal is to describe PCP-MAE as",
        "PCP-MAE is",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"PCP-MAE is a point-cloud masked autoencoder designed to describe PCP-MAE as",
        "PCP-MAE is",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\b([A-Z][A-Za-z ]+):\s*keep\b[^.]*\.?", "", text)
    text = re.sub(r"\b([A-Z][A-Za-z ]+):\s*explain\b[^.]*\.?", "", text)
    text = re.sub(r"\.\.", ".", text)
    text = re.sub(r"\s+\.", ".", text)
    text = re.sub(r"(,\s*){2,}", ", ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if figure_equations:
        text = text.rstrip() + "\n\nFigure-safe formulas:\n" + "\n".join(f"- {equation}" for equation in figure_equations) + "\n"
    return text.strip() + "\n"


def _normalize_inline_math_for_figure(text: str) -> str:
    return re.sub(
        r"\$(?!\$)(.+?)(?<!\$)\$",
        lambda match: _inline_math_to_figure_text(match.group(1)),
        text,
        flags=re.DOTALL,
    )


def build_figure_brief_from_files(
    draft_path: str | Path,
    *,
    method_evidence_path: str | Path | None = None,
    claim_map_path: str | Path | None = None,
    semantic_anchor: str = "",
    revision_note: str = "",
) -> str:
    return build_paperbanana_figure_brief(
        read_method_draft(draft_path),
        method_evidence_path=method_evidence_path,
        claim_map_path=claim_map_path,
        semantic_anchor=semantic_anchor,
        revision_note=revision_note,
    )


def _compact_json_summary(
    method_evidence_payload: dict[str, Any],
    claim_map_payload: dict[str, Any],
) -> str:
    chunks: list[str] = []
    if method_evidence_payload:
        stages = method_evidence_payload.get("stages", [])
        stage_names = [str(stage.get("name", "")).strip() for stage in stages if isinstance(stage, dict)]
        mechanisms = []
        for stage in stages:
            if isinstance(stage, dict):
                mechanisms.extend(stage.get("mechanisms", []) or [])
        chunks.append(
            "method_evidence="
            + json.dumps(
                {
                    "method_name": method_evidence_payload.get("method_name", ""),
                    "stage_names": [name for name in stage_names if name],
                    "mechanism_count": len(mechanisms),
                },
                ensure_ascii=False,
            )
        )
    if claim_map_payload:
        claims = claim_map_payload.get("claims", [])
        supported = [
            claim
            for claim in claims
            if isinstance(claim, dict) and claim.get("support_status") in {"supported", "partial"}
        ]
        chunks.append(
            "claim_map="
            + json.dumps(
                {"claims": len(claims), "supported_or_partial": len(supported)},
                ensure_ascii=False,
            )
        )
    return "\n".join(chunks)


def _load_json_if_exists(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _strip_inline_markup(text: str) -> str:
    text = re.sub(r"[*_`]+", "", text)
    text = re.sub(r"\\[a-zA-Z]+\{([^{}]+)\}", r"\1", text)
    return text.strip()


def _normalize_title(text: str) -> str:
    text = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", text or "")
    return text.strip()


def _extract_equation_hints(text: str) -> list[str]:
    return _select_figure_equations(text, max_equations=3)


def _looks_like_tex_document(text: str) -> bool:
    return bool(
        re.search(r"\\(?:section|subsection|begin|end)\b", text)
        and not re.search(r"^\s*#{1,6}\s+", text, flags=re.MULTILINE)
    )


def _remove_display_equations_for_figure(text: str) -> str:
    text = re.sub(r"\$\$.*?\$\$", "", text, flags=re.DOTALL)
    text = re.sub(r"\\\[.*?\\\]", "", text, flags=re.DOTALL)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _select_figure_equations(text: str, *, max_equations: int = 3) -> list[str]:
    raw_equations = re.findall(r"\$\$(.+?)\$\$", text, flags=re.DOTALL)
    raw_equations += re.findall(r"\\\[(.+?)\\\]", text, flags=re.DOTALL)
    candidates: list[tuple[int, str]] = []
    for index, equation in enumerate(raw_equations):
        cleaned = _latex_equation_to_figure_text(equation)
        if not _is_figure_safe_equation(cleaned):
            continue
        candidates.append((_figure_equation_priority(cleaned, index), cleaned))
    candidates.sort(key=lambda item: item[0])
    result: list[str] = []
    seen: set[str] = set()
    for _priority, equation in candidates:
        key = equation.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(equation)
        if len(result) >= max_equations:
            break
    return result


def _inline_math_to_figure_text(equation: str) -> str:
    cleaned = _latex_equation_to_figure_text(equation)
    if _is_short_symbol_expression(cleaned) or _is_simple_structural_equation(cleaned):
        return cleaned
    lhs = _left_hand_symbol(cleaned)
    if lhs:
        return lhs
    return ""


def _latex_equation_to_figure_text(equation: str) -> str:
    text = " ".join(str(equation or "").split())
    replacements = {
        r"\operatorname": "",
        r"\mathrm": "",
        r"\mathbf": "",
        r"\mathcal": "",
        r"\text": "",
        r"\left": "",
        r"\right": "",
        r"\cdot": "*",
        r"\times": "x",
        r"\alpha": "alpha",
        r"\beta": "beta",
        r"\lambda": "lambda",
        r"\theta": "theta",
        r"\tau": "tau",
        r"\epsilon": "eps",
        r"\sum": "sum",
        r"\min": "min",
        r"\max": "max",
        r"\sqrt": "sqrt",
        r"\ln": "ln",
        r"\log": "log",
        r"\lVert": "||",
        r"\rVert": "||",
        r"\hat": "hat",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", text)
    text = re.sub(r"\\(?:sin|cos|softmax)\b", lambda m: m.group(0).lstrip("\\"), text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = re.sub(r"\{([^{}]+)\}", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_figure_safe_equation(equation: str) -> bool:
    return _is_simple_structural_equation(equation)


def _is_short_symbol_expression(text: str) -> bool:
    compact = " ".join(str(text or "").split())
    if not compact or len(compact) > 24:
        return False
    if any(token in compact.lower() for token in ("=", "+", "-", "*", "/", "sum", "int", "prod", "sqrt", "log", "exp")):
        return False
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_^\-]*(?:\s*,\s*[A-Za-z][A-Za-z0-9_^\-]*){0,3}", compact))


def _is_simple_structural_equation(text: str) -> bool:
    compact = " ".join(str(text or "").split())
    if not compact or len(compact) > 90:
        return False
    lowered = compact.lower()
    banned = (
        "frac",
        "sum",
        "prod",
        "int",
        "sqrt",
        "log",
        "ln",
        "exp",
        "arg",
        "grad",
        "partial",
        "softmax",
        "ssim",
        "norm",
        "min",
        "max",
        "trace",
        "det",
        "cov",
        "sigma^{-1}",
        "^{-1}",
        "^t",
        "||",
        "\\",
        "[",
        "]",
    )
    if any(token in lowered for token in banned):
        return False
    if re.search(r"\^\s*[23-9]", compact):
        return False
    if re.search(r"[<>≤≥]", compact):
        return False
    if compact.count("=") != 1:
        return False
    lhs, rhs = [part.strip() for part in compact.split("=", 1)]
    name = r"[A-Za-z][A-Za-z0-9_^\-]*"
    simple_call = rf"{name}\({name}(?:\s*,\s*{name}){{0,3}}\)"
    simple_term = rf"(?:{simple_call}|{name})"
    if not re.fullmatch(name, lhs):
        return False
    if len(re.findall(r"[A-Za-z][A-Za-z0-9_^\-]*", rhs)) > 8:
        return False
    if not re.search(r"[+\-*/()]|^[A-Za-z][A-Za-z0-9_^\-]*$", rhs):
        return False
    expression = rf"{simple_term}(?:\s*[+\-*/]\s*{simple_term}){{0,4}}"
    return bool(re.fullmatch(expression, rhs))


def _left_hand_symbol(text: str) -> str:
    compact = " ".join(str(text or "").split())
    if "=" not in compact:
        return ""
    lhs = compact.split("=", 1)[0].strip()
    if len(lhs) > 24:
        return ""
    return lhs if re.fullmatch(r"[A-Za-z][A-Za-z0-9_^\-]*", lhs) else ""


def _figure_equation_priority(equation: str, index: int) -> int:
    lowered = equation.lower()
    priority = 50 + index
    if any(term in lowered for term in ("loss", "l_", "ssim")):
        priority = min(priority, 10 + index)
    if any(term in lowered for term in ("score", "mask", "sum")):
        priority = min(priority, 20 + index)
    if any(term in lowered for term in ("softmax", "fusion")):
        priority = min(priority, 30 + index)
    return priority


def _derive_required_nodes(evidence_payload: dict[str, Any], section_titles: list[str]) -> list[str]:
    stage_names: list[str] = []
    stages = evidence_payload.get("stages", []) if isinstance(evidence_payload, dict) else []
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        name = str(stage.get("name", "")).strip()
        if name:
            stage_names.append(name)
    if not stage_names:
        stage_names = list(section_titles)

    normalized = [_normalize_title(name) for name in stage_names if _normalize_title(name)]
    deduped: list[str] = []
    seen: set[str] = set()
    for item in normalized:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    process_nodes = [node for node in deduped if not _is_meta_stage_label(node)]
    if len(process_nodes) >= 3:
        deduped = process_nodes
    elif len(process_nodes) >= 2 and len(deduped) > 2:
        deduped = process_nodes
    return deduped[:7]


def _derive_required_edges(nodes: list[str]) -> list[str]:
    if len(nodes) < 2:
        return []
    edges: list[str] = []
    for idx in range(len(nodes) - 1):
        edges.append(f"{nodes[idx]} -> {nodes[idx + 1]}")
    return edges


def _detect_multimodal_pipeline(text: str, evidence_payload: dict[str, Any]) -> bool:
    lowered = text.lower()
    if _has_explicit_multimodal_sentence(lowered):
        return True

    stages = evidence_payload.get("stages", []) if isinstance(evidence_payload, dict) else []
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        bag = " ".join(
            [
                str(stage.get("name", "")),
                str(stage.get("purpose", "")),
                " ".join(str(x) for x in stage.get("inputs", []) if isinstance(x, str)),
                " ".join(str(x) for x in stage.get("outputs", []) if isinstance(x, str)),
            ]
        ).lower()
        if _has_explicit_multimodal_sentence(bag):
            return True
    return False


def _infer_semantic_anchor(text: str) -> str:
    normalized = text.replace("\u201c", '"').replace("\u201d", '"')
    quoted = re.findall(r'"([^"]+)"', normalized)
    for item in quoted:
        candidate = item.strip()
        if 1 <= len(candidate) <= 24 and re.search(r"[a-zA-Z]", candidate):
            return candidate
    return ""


def _is_meta_stage_label(label: str) -> bool:
    lowered = _normalize_title(label).lower()
    if not lowered:
        return True
    if lowered in {"method", "method overview", "method overview and preliminaries"}:
        return True
    return any(hint in lowered for hint in _META_STAGE_HINTS)


def _normalize_math_notation(text: str) -> str:
    text = re.sub(r"\\hat\{([^{}]+)\}", r"\1_hat", text)
    text = re.sub(r"\\mathcal\{([^{}]+)\}", r"\1", text)
    text = re.sub(r"\\text\{([^{}]+)\}", r"\1", text)
    text = re.sub(r"_\{([^{}]+)\}", r"_\1", text)
    text = re.sub(r"\^\{([^{}]+)\}", r"^\1", text)
    replacements = {
        r"\alpha": "alpha",
        r"\beta": "beta",
        r"\theta": "theta",
        r"\lambda": "lambda",
        r"\phi": "phi",
        r"\nabla": "grad",
        r"\cdot": ".",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def _detect_slots(
    *,
    method_text: str,
    code_blob: str,
    claim_blob: str,
    has_equation: bool,
) -> dict[str, dict[str, Any]]:
    slot_map: dict[str, dict[str, Any]] = {}
    combined = "\n".join([method_text, code_blob, claim_blob])

    backbone, layers, backbone_source = _infer_backbone_and_depth(method_text, code_blob)
    slot_map["backbone_and_depth"] = {
        "status": "filled" if backbone != UNKNOWN_VALUE or layers != UNKNOWN_VALUE else "unknown",
        "source": backbone_source,
        "value": {"backbone": backbone, "total_layers": layers},
    }

    branch_value, branch_source = _infer_branch_structure(combined)
    slot_map["branch_structure"] = {
        "status": "filled" if branch_value.get("structure") != UNKNOWN_VALUE else "unknown",
        "source": branch_source,
        "value": branch_value,
    }

    loss_path, loss_source = _infer_loss_logit_path(combined)
    slot_map["loss_logit_path"] = {
        "status": "filled" if loss_path != UNKNOWN_VALUE else "unknown",
        "source": loss_source,
        "value": loss_path,
    }

    slot_map["equation_binding"] = {
        "status": "filled" if has_equation else "unknown",
        "source": "method_text" if has_equation else "unknown",
        "value": "equations_detected" if has_equation else UNKNOWN_VALUE,
    }
    return slot_map


def _infer_backbone_and_depth(method_text: str, code_blob: str) -> tuple[str, str | int, str]:
    candidates = [("method_text", method_text), ("code_evidence", code_blob)]
    backbone_patterns = [
        r"\bclip\b",
        r"\bvit\b",
        r"\btransformer\b",
        r"\bresnet\b",
        r"\bbert\b",
        r"\bllama\b",
        r"\bgpt\b",
    ]
    for source, text in candidates:
        lowered = text.lower()
        backbone = UNKNOWN_VALUE
        for pattern in backbone_patterns:
            match = re.search(pattern, lowered)
            if match:
                backbone = match.group(0).upper() if match.group(0) in {"vit", "gpt"} else match.group(0)
                break
        depth_match = re.search(r"\b(\d{1,3})\s*(?:layers?|blocks?)\b", lowered)
        layers: str | int = int(depth_match.group(1)) if depth_match else UNKNOWN_VALUE
        if backbone != UNKNOWN_VALUE or layers != UNKNOWN_VALUE:
            return backbone, layers, source
    return UNKNOWN_VALUE, UNKNOWN_VALUE, "unknown"


def _infer_branch_structure(text: str) -> tuple[dict[str, Any], str]:
    for sentence in re.split(r"[;\n\.]+", text):
        lowered = sentence.strip().lower()
        if not lowered:
            continue
        if any(term in lowered for term in ("pretrain", "finetune", "test mode", "entrypoint", "dispatch")):
            continue
        if any(term in lowered for term in ("dual-branch", "dual branch", "two-branch", "two branch")):
            return {"structure": "dual_branch", "branches": ["branch_a", "branch_b"], "fusion": "merge_or_scoring_node"}, "method_or_code"
        if _has_explicit_multimodal_sentence(lowered) and any(term in lowered for term in ("branch", "fusion", "align")):
            return {"structure": "dual_branch", "branches": ["image_branch", "text_branch"], "fusion": "shared_alignment_or_fusion"}, "method_or_code"
        if "branch" in lowered and any(term in lowered for term in ("fusion", "logit", "auxiliary", "consistency", "parallel", "stream")):
            return {"structure": "multi_branch", "branches": ["branch_1", "branch_2"], "fusion": UNKNOWN_VALUE}, "method_or_code"
    return {"structure": UNKNOWN_VALUE, "branches": [UNKNOWN_VALUE], "fusion": UNKNOWN_VALUE}, "unknown"


def _has_explicit_multimodal_sentence(text: str) -> bool:
    has_text_side = "text" in text or "language" in text
    has_image_side = "image" in text or "vision" in text or "visual" in text
    if not (has_text_side and has_image_side):
        return False
    return any(term in text for term in ("branch", "fusion", "align", "cross-modal", "multimodal", "dual"))


def _figure_naming_hints(text: str, evidence_payload: dict[str, Any]) -> list[str]:
    hints: list[str] = []
    lowered = text.lower()
    for phrase in (
        "visible",
        "masked",
        "positional embedding",
        "self-attention",
        "cross-attention",
        "center prediction",
        "reconstruction",
        "chamfer",
        "loss",
        "encoder",
        "decoder",
    ):
        if phrase in lowered:
            hints.append(phrase)

    acronyms = re.findall(r"\b[A-Z]{2,}(?:[-_][A-Z0-9]{2,})*\b", text)
    for acronym in acronyms[:20]:
        cleaned = acronym.strip()
        if cleaned and cleaned not in hints:
            hints.append(cleaned)

    method_name = str(evidence_payload.get("method_name", "")).strip() if isinstance(evidence_payload, dict) else ""
    if method_name:
        hints.insert(0, method_name)
    return _dedupe_text(hints)


def _extract_innovation_focus(
    *,
    method_text: str,
    method_evidence_payload: dict[str, Any],
    claim_map_payload: dict[str, Any],
) -> list[str]:
    candidates: list[str] = []
    claims = claim_map_payload.get("claims", []) if isinstance(claim_map_payload, dict) else []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        if str(claim.get("support_status", "")).strip().lower() not in {"supported", "partial"}:
            continue
        claim_text = str(claim.get("claim_text", "")).strip()
        if claim_text:
            candidates.append(claim_text)

    for mechanism in method_evidence_payload.get("frozen_mechanisms", []) if isinstance(method_evidence_payload, dict) else []:
        if not isinstance(mechanism, dict):
            continue
        description = str(mechanism.get("mechanism_description", "")).strip()
        if description:
            candidates.append(description)

    for stage in method_evidence_payload.get("stages", []) if isinstance(method_evidence_payload, dict) else []:
        if not isinstance(stage, dict):
            continue
        for mechanism in stage.get("mechanisms", []) or []:
            if not isinstance(mechanism, dict):
                continue
            description = str(mechanism.get("description", "") or mechanism.get("mechanism_description", "")).strip()
            if description:
                candidates.append(description)

    for sentence in re.split(r"(?<=[\.\n])\s+", method_text):
        compact = " ".join(sentence.strip().split())
        if compact and any(hint in compact.lower() for hint in _INNOVATION_HINTS):
            candidates.append(compact)

    scored: list[tuple[int, str]] = []
    for text in _dedupe_text(candidates):
        lowered = text.lower()
        score = sum(1 for hint in _INNOVATION_HINTS if hint in lowered)
        if score <= 0:
            continue
        scored.append((score, _trim_sentence(text, limit=160)))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in scored[:4]]


def _trim_sentence(text: str, *, limit: int) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _infer_loss_logit_path(text: str) -> tuple[str, str]:
    sentence = _first_sentence_with_keywords(text, ["loss", "objective", "logit", "regulariz"])
    if sentence:
        return sentence[:180], "method_or_code"
    return UNKNOWN_VALUE, "unknown"


def _build_code_summary(slot_map: dict[str, dict[str, Any]], evidence_payload: dict[str, Any]) -> dict[str, Any]:
    architecture_value = slot_map.get("backbone_and_depth", {}).get("value", {})
    branch_value = slot_map.get("branch_structure", {}).get("value", {})
    loss_path = slot_map.get("loss_logit_path", {}).get("value", UNKNOWN_VALUE)

    architecture = {
        "backbone": architecture_value.get("backbone", UNKNOWN_VALUE),
        "total_layers": architecture_value.get("total_layers", UNKNOWN_VALUE),
        "stage_count": len(evidence_payload.get("stages", [])) if isinstance(evidence_payload.get("stages", []), list) else UNKNOWN_VALUE,
    }
    branches = {
        "structure": branch_value.get("structure", UNKNOWN_VALUE),
        "paths": branch_value.get("branches", [UNKNOWN_VALUE]),
        "fusion": branch_value.get("fusion", UNKNOWN_VALUE),
    }
    objectives = {"loss_or_logit_path": loss_path}

    return {
        "architecture": architecture,
        "branches": branches,
        "objectives": objectives,
    }


def _diagram_intent_expander(
    *,
    slot_map: dict[str, dict[str, Any]],
    method_text: str,
    code_blob: str,
) -> list[str]:
    bag = f"{method_text}\n{code_blob}".lower()
    actions: list[str] = []

    if slot_map.get("branch_structure", {}).get("status") == "filled":
        actions.append(
            "Dual/multi branch -> draw parallel scoring paths with a compact fusion node and one loss node."
        )
    if slot_map.get("loss_logit_path", {}).get("status") == "filled":
        actions.append("Loss/logit path -> attach objective callout to the exact branch/module where logits are produced.")

    if "equation" in bag or "loss" in bag or "objective" in bag:
        actions.append("Equation mention -> bind each equation callout to its owning module instead of floating global formula text.")

    if not actions:
        actions.append("No strong mechanism cues detected -> keep architecture concise and label unresolved details as unspecified.")
    return _dedupe_text(actions)


def _detail_hints(text: str, evidence_payload: dict[str, Any], *, slot_map: dict[str, dict[str, Any]] | None = None) -> list[str]:
    """Suggest detail-level visual constraints without forcing exact wiring."""

    hints: list[str] = []
    lower_text = text.lower()
    evidence_blob = _evidence_text_blob(evidence_payload).lower()
    bag = f"{lower_text}\n{evidence_blob}"
    slots = slot_map or {}

    branch_structure = str(slots.get("branch_structure", {}).get("value", {}).get("structure", ""))
    if branch_structure in {"dual_branch", "multi_branch"} or any(term in bag for term in ("dual-branch", "dual branch", "two-branch", "branch-wise", "cross-branch")):
        hints.append(
            "Use a compact branch cue with branch-specific labels and one merge/scoring node to avoid duplicated full pipelines."
        )

    if any(term in bag for term in ("equation", "formula", "loss", "objective")):
        hints.append("Attach one compact formula callout near the mechanism it governs, with symbols explained inline.")

    return _dedupe_text(hints)


def _render_slot_status_lines(slot_map: dict[str, dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for slot_name in DIAGRAM_SLOT_ORDER:
        slot = slot_map.get(slot_name, {})
        status = str(slot.get("status", "unknown"))
        source = str(slot.get("source", "unknown"))
        value = slot.get("value", UNKNOWN_VALUE)
        compact = _compact_value(value)
        lines.append(f"- {slot_name}: status={status}; source={source}; value={compact}")
    return lines


def _render_code_summary_yaml(code_summary: dict[str, Any]) -> str:
    if not code_summary:
        return "architecture:\n  backbone: unspecified\n  total_layers: unspecified"
    return _to_yaml_like(code_summary)


def _to_yaml_like(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(_to_yaml_like(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_scalar_text(item)}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{prefix}- {UNKNOWN_VALUE}"
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(_to_yaml_like(item, indent + 2))
            else:
                lines.append(f"{prefix}- {_scalar_text(item)}")
        return "\n".join(lines)
    return f"{prefix}{_scalar_text(value)}"


def _scalar_text(value: Any) -> str:
    text = str(value).strip()
    return text if text else UNKNOWN_VALUE


def _compact_value(value: Any) -> str:
    if isinstance(value, dict):
        items = [f"{key}={_compact_value(item)}" for key, item in value.items()]
        return "{" + ", ".join(items[:6]) + (" ..." if len(items) > 6 else "") + "}"
    if isinstance(value, list):
        parts = [_compact_value(item) for item in value[:4]]
        return "[" + ", ".join(parts) + (" ..." if len(value) > 4 else "") + "]"
    return _scalar_text(value)


def _claims_text_blob(claim_payload: dict[str, Any]) -> str:
    claims = claim_payload.get("claims", []) if isinstance(claim_payload, dict) else []
    texts: list[str] = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        claim_text = str(claim.get("claim_text", "")).strip()
        if claim_text:
            texts.append(claim_text)
    return "\n".join(_dedupe_text(texts[:200]))


def _evidence_text_blob(evidence_payload: dict[str, Any]) -> str:
    """Flatten evidence payload into lightweight searchable text."""

    if not isinstance(evidence_payload, dict) or not evidence_payload:
        return ""

    texts: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, str):
            value = node.strip()
            if value and len(value) <= 400:
                texts.append(value)
            return
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(key, str):
                    key_text = key.strip()
                    if key_text and len(key_text) <= 80:
                        texts.append(key_text)
                visit(value)
            return
        if isinstance(node, list):
            for item in node[:250]:
                visit(item)

    visit(evidence_payload)
    deduped = _dedupe_text(texts)
    return "\n".join(deduped[:400])


def _first_sentence_with_keywords(text: str, keywords: list[str]) -> str:
    for chunk in re.split(r"(?<=[\.\n])\s+", text):
        lowered = chunk.lower()
        if any(keyword in lowered for keyword in keywords):
            compact = re.sub(r"\s+", " ", chunk.strip())
            if compact:
                return compact
    return ""


def _collect_scope_sentences(text: str, keywords: list[str]) -> list[str]:
    scopes: list[str] = []
    for chunk in re.split(r"(?<=[\.\n])\s+", text):
        compact = re.sub(r"\s+", " ", chunk.strip())
        if not compact:
            continue
        lowered = compact.lower()
        if any(keyword in lowered for keyword in keywords):
            scopes.append(compact[:140])
    return _dedupe_text(scopes)


def _dedupe_text(values: Iterable[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = (value or "").strip()
        if not item:
            continue
        key = re.sub(r"\s+", " ", item).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
