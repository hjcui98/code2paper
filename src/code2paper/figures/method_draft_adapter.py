"""Adapt grounded method drafts into PaperBanana figure briefs."""

from __future__ import annotations

import json
import re
from pathlib import Path


GROUNDING_COMMENT_RE = re.compile(r"<!--\s*c2p:.*?-->", re.DOTALL)
TEX_GROUNDING_COMMENT_RE = re.compile(r"^\s*%\s*c2p:.*$", re.MULTILINE)
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
TEX_SECTION_RE = re.compile(r"\\(?:sub)*section\{([^{}]+)\}")
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
        title = _strip_inline_markup(match.group(2))
        if title and title.lower() != "method":
            titles.append(title)
    for match in TEX_SECTION_RE.finditer(text):
        title = _strip_inline_markup(match.group(1))
        if title and title.lower() != "method" and title not in titles:
            titles.append(title)
    return titles


def build_paperbanana_figure_brief(
    draft_text: str,
    *,
    method_evidence_path: str | Path | None = None,
    claim_map_path: str | Path | None = None,
) -> str:
    """Build the text payload handed to PaperBanana."""

    clean_text = clean_method_draft(draft_text)
    section_titles = extract_section_titles(clean_text)
    evidence_summary = _compact_json_summary(method_evidence_path, claim_map_path)

    lines = [
        "Create a paper-ready method overview figure from the following method draft.",
        "",
        "Figure requirements:",
        "- Use the method draft as the primary source.",
        "- Show the paper-level method stages and the main mechanism flow.",
        "- Prefer a left-to-right or top-to-bottom pipeline with concise node labels.",
        "- Do not add claims that are not present in the draft.",
        "- Keep utility or experiment-support details out of the main visual flow.",
        "- Include only labels that can be traced to the draft text.",
        "",
    ]
    if section_titles:
        lines.extend(["Detected draft sections:", *[f"- {title}" for title in section_titles], ""])
    if evidence_summary:
        lines.extend(["Optional audit context:", evidence_summary, ""])
    lines.extend(["Method draft:", clean_text])
    return "\n".join(lines).strip() + "\n"


def build_figure_brief_from_files(
    draft_path: str | Path,
    *,
    method_evidence_path: str | Path | None = None,
    claim_map_path: str | Path | None = None,
) -> str:
    return build_paperbanana_figure_brief(
        read_method_draft(draft_path),
        method_evidence_path=method_evidence_path,
        claim_map_path=claim_map_path,
    )


def _compact_json_summary(
    method_evidence_path: str | Path | None,
    claim_map_path: str | Path | None,
) -> str:
    chunks: list[str] = []
    if method_evidence_path:
        payload = _load_json(method_evidence_path)
        stages = payload.get("stages", []) if isinstance(payload, dict) else []
        stage_names = [str(stage.get("name", "")).strip() for stage in stages if isinstance(stage, dict)]
        mechanisms = []
        for stage in stages:
            if isinstance(stage, dict):
                mechanisms.extend(stage.get("mechanisms", []) or [])
        chunks.append(
            "method_evidence="
            + json.dumps(
                {
                    "method_name": payload.get("method_name", "") if isinstance(payload, dict) else "",
                    "stage_names": [name for name in stage_names if name],
                    "mechanism_count": len(mechanisms),
                },
                ensure_ascii=False,
            )
        )
    if claim_map_path:
        payload = _load_json(claim_map_path)
        claims = payload.get("claims", []) if isinstance(payload, dict) else []
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


def _load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _strip_inline_markup(text: str) -> str:
    text = re.sub(r"[*_`]+", "", text)
    text = re.sub(r"\\[a-zA-Z]+\{([^{}]+)\}", r"\1", text)
    return text.strip()
