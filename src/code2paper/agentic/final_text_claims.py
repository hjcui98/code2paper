from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from code2paper.agentic.trust_contracts import (
    AuthoringInputProjection,
    FinalAtomicClaim,
    FinalTextClaims,
    FinalTextUnit,
)


_RISK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("number", re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?%?")),
    ("formula", re.compile(r"\$[^$]+\$|\\(?:begin|end)\{equation\}|[A-Za-z]\s*=\s*[^,.;]+")),
    ("causal", re.compile(r"\b(?:causes?|ensures?|guarantees?|leads? to|results? in)\b", re.I)),
    ("performance", re.compile(r"\b(?:improves?|outperforms?|faster|better|state[- ]of[- ]the[- ]art)\b", re.I)),
    ("complexity", re.compile(r"\bO\s*\([^)]+\)")),
)
_FACTUAL_HINT = re.compile(
    r"\b(?:use|uses|used|compute|computes|produce|produces|apply|applies|encode|decode|optimiz|train|"
    r"configure|construct|return|output|input|module|layer|loss|parameter|pipeline|stage|model|method|algorithm)\w*\b",
    re.I,
)
_DISCOURSE_PREFIXES = (
    "in this section",
    "next",
    "finally",
    "for clarity",
    "in summary",
    "overall",
    "we now describe",
)


def extract_final_text_claims(text: str, projection: AuthoringInputProjection) -> FinalTextClaims:
    text_digest = _digest(text)
    units: list[FinalTextUnit] = []
    atomic: list[FinalAtomicClaim] = []
    char_cursor = 0
    unit_number = 1
    claim_number = 1
    for line_number, raw_line in enumerate(text.splitlines(keepends=True), start=1):
        line = raw_line.rstrip("\r\n")
        line_start = char_cursor
        char_cursor += len(raw_line)
        stripped = line.strip()
        if not stripped:
            continue
        kind = _line_kind(stripped)
        clean = _strip_markup(stripped, kind)
        for sentence, local_start, local_end in _sentence_spans(clean):
            risks = _risk_markers(sentence)
            discourse = _is_discourse(sentence, risks)
            unit_kind = "discourse" if discourse else kind
            factual = kind != "heading" and not discourse and (bool(risks) or bool(_FACTUAL_HINT.search(sentence)))
            unit_id = f"FTU{unit_number}"
            unit_number += 1
            absolute_start = line_start + max(line.find(clean), 0) + local_start
            absolute_end = line_start + max(line.find(clean), 0) + local_end
            unit = FinalTextUnit(
                unit_id=unit_id,
                kind=unit_kind,
                text=sentence,
                line_start=line_number,
                line_end=line_number,
                char_start=absolute_start,
                char_end=absolute_end,
                factual=factual,
                high_risk_markers=risks,
                span_digest=_digest(sentence),
            )
            units.append(unit)
            if not factual:
                continue
            for fragment, offset_start, offset_end in _atomic_fragments(sentence):
                matches = _projection_matches(fragment, projection)
                atomic.append(
                    FinalAtomicClaim(
                        atomic_claim_id=f"FAC{claim_number}",
                        unit_id=unit_id,
                        text=fragment,
                        normalized_text=_normalize(fragment),
                        line_start=line_number,
                        line_end=line_number,
                        char_start=absolute_start + offset_start,
                        char_end=absolute_start + offset_end,
                        candidate_projection_claim_ids=[item.claim_id for item in matches],
                        candidate_direct_evidence_ids=_dedupe(
                            [evidence_id for item in matches for evidence_id in item.direct_evidence_ids]
                        ),
                        high_risk_markers=_risk_markers(fragment),
                        claim_digest=_digest(fragment),
                    )
                )
                claim_number += 1
    failures = _completeness_failures(units, atomic)
    return FinalTextClaims(
        input_text_digest=text_digest,
        units=units,
        atomic_claims=atomic,
        deterministic_completeness_passed=not failures,
        completeness_failures=failures,
    )


def write_final_text_claims(path: str | Path, claims: FinalTextClaims) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(claims.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_final_text_claims(path: str | Path) -> FinalTextClaims:
    return FinalTextClaims.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def text_digest(text: str) -> str:
    return _digest(text)


def _line_kind(text: str) -> str:
    if text.startswith("#"):
        return "heading"
    if re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)", text):
        return "list_item"
    if text.lower().startswith(("figure ", "table ", "caption:")):
        return "caption"
    if text.startswith(("$$", "\\begin{equation}")):
        return "formula"
    return "sentence"


def _strip_markup(text: str, kind: str) -> str:
    if kind == "heading":
        return text.lstrip("# ").strip()
    if kind == "list_item":
        return re.sub(r"^(?:[-*+]\s+|\d+[.)]\s+)", "", text).strip()
    return text


def _sentence_spans(text: str) -> list[tuple[str, int, int]]:
    spans: list[tuple[str, int, int]] = []
    for match in re.finditer(r"[^.!?]+(?:[.!?]+|$)", text):
        sentence = match.group(0).strip()
        if sentence:
            start = match.start() + len(match.group(0)) - len(match.group(0).lstrip())
            spans.append((sentence, start, start + len(sentence)))
    return spans or [(text, 0, len(text))]


def _atomic_fragments(sentence: str) -> list[tuple[str, int, int]]:
    separators = re.compile(r"\s*;\s*|\s+(?:and|but|while|whereas)\s+", re.I)
    parts: list[tuple[str, int, int]] = []
    cursor = 0
    for match in separators.finditer(sentence):
        left = sentence[cursor : match.start()].strip(" ,")
        right = sentence[match.end() :].strip(" ,")
        if not (_clause_like(left) and _clause_like(right)):
            continue
        candidate = sentence[cursor : match.start()].strip(" ,")
        if candidate:
            start = sentence.find(candidate, cursor, match.start() + 1)
            parts.append((candidate, start, start + len(candidate)))
        cursor = match.end()
    candidate = sentence[cursor:].strip(" ,")
    if candidate:
        start = sentence.find(candidate, cursor)
        parts.append((candidate, start, start + len(candidate)))
    return parts or [(sentence, 0, len(sentence))]


def _clause_like(text: str) -> bool:
    return bool(_FACTUAL_HINT.search(text) or _risk_markers(text))


def _is_discourse(text: str, risks: list[str]) -> bool:
    lowered = text.lower().strip()
    if risks or _FACTUAL_HINT.search(text):
        return False
    return lowered.startswith(_DISCOURSE_PREFIXES) or len(_tokens(text)) <= 5


def _risk_markers(text: str) -> list[str]:
    return [name for name, pattern in _RISK_PATTERNS if pattern.search(text)]


def _projection_matches(text: str, projection: AuthoringInputProjection):
    text_tokens = _tokens(text)
    normalized_text = _normalize(text)
    exact = [
        claim
        for claim in projection.projected_claims
        if _normalize(claim.supported_fragment) == normalized_text
        or _normalize(claim.supported_fragment) in normalized_text
    ]
    if exact:
        return exact
    scored = []
    for claim in projection.projected_claims:
        claim_tokens = _tokens(claim.supported_fragment)
        overlap = len(text_tokens.intersection(claim_tokens)) / max(1, min(len(text_tokens), len(claim_tokens)))
        if overlap >= 0.45 or _normalize(claim.supported_fragment) in _normalize(text):
            scored.append((overlap, claim))
    return [item for _score, item in sorted(scored, key=lambda pair: pair[0], reverse=True)]


def _completeness_failures(units: list[FinalTextUnit], claims: list[FinalAtomicClaim]) -> list[str]:
    claim_units = {claim.unit_id for claim in claims}
    return [
        f"high_risk_unit_not_extracted:{unit.unit_id}"
        for unit in units
        if unit.high_risk_markers and unit.unit_id not in claim_units
    ]


def _tokens(text: str) -> set[str]:
    stop = {"the", "a", "an", "of", "to", "and", "or", "is", "are", "we", "our", "this", "that", "with", "for"}
    return {token for token in re.findall(r"[a-z0-9_]+", text.lower()) if len(token) > 1 and token not in stop}


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9_%]+", text.lower()))


def _digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
