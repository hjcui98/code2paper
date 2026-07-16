"""Minimal Markdown-to-LaTeX formatter for method drafts."""

from __future__ import annotations

import re


def format_method_draft_tex(markdown_text: str) -> str:
    """Convert the constrained method-draft Markdown subset to LaTeX."""

    lines: list[str] = []
    in_itemize = False
    in_math = False
    seen_section = False
    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if line.startswith(r"\[") and line.endswith(r"\]") and len(line) > 4:
            if in_itemize:
                lines.append(r"\end{itemize}")
                in_itemize = False
            math_body = line[2:-2].strip()
            lines.append(r"\[")
            lines.append(math_body)
            lines.append(r"\]")
            continue
        if line.startswith("$$") and line.endswith("$$") and len(line) > 4:
            if in_itemize:
                lines.append(r"\end{itemize}")
                in_itemize = False
            math_body = line[2:-2].strip()
            lines.append(r"\[")
            lines.append(math_body)
            lines.append(r"\]")
            continue
        if line in {"$$", r"\[", r"\]"}:
            if in_itemize:
                lines.append(r"\end{itemize}")
                in_itemize = False
            lines.append(r"\]" if in_math else r"\[")
            in_math = not in_math
            continue
        if in_math:
            lines.append(line)
            continue
        if not line:
            if in_itemize:
                lines.append(r"\end{itemize}")
                in_itemize = False
            lines.append("")
            continue
        if line.startswith("<!-- c2p:") and line.endswith("-->"):
            if in_itemize:
                lines.append(r"\end{itemize}")
                in_itemize = False
            lines.append("% " + line.removeprefix("<!-- ").removesuffix(" -->"))
            continue
        if line.startswith("# "):
            if in_itemize:
                lines.append(r"\end{itemize}")
                in_itemize = False
            lines.append(r"\section{" + _escape_inline(_normalize_heading_title(line[2:].strip())) + "}")
            seen_section = True
            continue
        if line.startswith("## "):
            if in_itemize:
                lines.append(r"\end{itemize}")
                in_itemize = False
            title = _normalize_heading_title(line[3:].strip())
            if not seen_section:
                lines.append(r"\section{" + _escape_inline(title) + "}")
                seen_section = True
            else:
                lines.append(r"\subsection{" + _escape_inline(title) + "}")
            continue
        if line.startswith("### "):
            if in_itemize:
                lines.append(r"\end{itemize}")
                in_itemize = False
            title = _normalize_heading_title(line[4:].strip())
            if not seen_section:
                lines.append(r"\section{" + _escape_inline(title) + "}")
                seen_section = True
            else:
                lines.append(r"\subsection{" + _escape_inline(title) + "}")
            continue
        if line.startswith("#### "):
            if in_itemize:
                lines.append(r"\end{itemize}")
                in_itemize = False
            lines.append(r"\paragraph{" + _escape_inline(_normalize_heading_title(line[5:].strip())) + "}")
            continue
        if line.startswith("- "):
            if not in_itemize:
                lines.append(r"\begin{itemize}")
                in_itemize = True
            lines.append(r"\item " + _format_inline(line[2:].strip()))
            continue
        if in_itemize:
            lines.append(r"\end{itemize}")
            in_itemize = False
        lines.append(_format_inline(line))
    if in_itemize:
        lines.append(r"\end{itemize}")
    return "\n".join(lines).rstrip() + "\n"


def _normalize_heading_title(text: str) -> str:
    """Let LaTeX own section numbering even if the LLM emits numbered headings."""

    title = str(text or "").strip()
    title = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s+", "", title)
    return title or str(text or "").strip()


def _format_inline(text: str) -> str:
    parts: list[str] = []
    pattern = re.compile(r"(\\\([^\n]+?\\\)|\$[^$\n]+\$|\*\*[^*]+\*\*|`[^`]+`)")
    cursor = 0
    for match in pattern.finditer(text):
        parts.append(_escape_inline(text[cursor : match.start()]))
        token = match.group(0)
        if (
            (token.startswith("$") and token.endswith("$"))
            or (token.startswith(r"\(") and token.endswith(r"\)"))
        ):
            parts.append(token)
        elif token.startswith("**"):
            parts.append(r"\textbf{" + _escape_inline(token[2:-2]) + "}")
        else:
            parts.append(r"\texttt{" + _escape_inline(token[1:-1]) + "}")
        cursor = match.end()
    parts.append(_escape_inline(text[cursor:]))
    return "".join(parts)


def _escape_inline(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)
