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


_FORMULA_IDENTIFIER = (
    r"[A-Za-z_][A-Za-z0-9_]*"
    r"(?:\.[A-Za-z_][A-Za-z0-9_]*|\[[^\[\]]*\]|\([^)]*\))*"
)
_FORMULA_RISK = re.compile(
    r"\$[^$]+\$|\\(?:begin|end)\{equation\}|"
    r"(?<![A-Za-z0-9_])" + _FORMULA_IDENTIFIER
    + r"\s*==\s*[^,.;]+|"
    r"(?<![A-Za-z0-9_])" + _FORMULA_IDENTIFIER
    + r"\s+=\s+(?![\[\"'])[^,.;]+"
)


_RISK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("number", re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?%?")),
    # Distinguish mathematical formulas and comparisons from Python keyword
    # arguments and code patterns.  ``dim=1`` (no spaces) is a keyword argument;
    # ``x = ["..."]`` or ``x = "..."`` is a code pattern (list/string assignment).
    # ``x = 1`` (spaces around ``=``) and ``current_layer_num == 0`` (``==``)
    # are formulas.
    ("formula", _FORMULA_RISK),
    ("causal", re.compile(r"\b(?:causes?|ensures?|guarantees?|leads? to|results? in)\b", re.I)),
    ("performance", re.compile(r"\b(?:improves?|outperforms?|faster|better|state[- ]of[- ]the[- ]art)\b", re.I)),
    ("complexity", re.compile(r"\bO\s*\([^)]+\)")),
)

#: Writer-facing caveat markers.  A factual sentence that carries one of
#: these tokens is *explicitly caveated* author-intent/review material, so the
#: candidate may keep it while verified never does.  The candidate/verified
#: splitter uses these markers to distinguish ``author_intent_caveated`` from
#: an unsafe unmarked positive.
_CAVEAT_MARKERS = (
    "await",
    "awaiting",
    "pending",
    "unverified",
    "unsupported",
    "needs confirmation",
    "requires confirmation",
    "to be confirmed",
    "not yet verified",
    "not verified",
    "cannot be verified",
    "could not be verified",
    "review",
    "await confirmation",
    "repository evidence partially",
    "available repository evidence partially",
    "the current repository covers",
    "the available implementation covers",
    "our intended design",
    "the intended design",
    "we aim",
    "we intend",
    "we formulate",
    "we hypothesize",
    "we assume",
    "we propose to",
)

#: Product lanes a final-text unit may be classified into (G1 contract).
#: ``repository_positive`` / ``repository_partial`` may enter the verified
#: document (partial only with preserved qualifiers); every other lane is
#: candidate-and-review material.
FINAL_TEXT_LANES: tuple[str, ...] = (
    "repository_positive",
    "repository_partial",
    "author_intent_caveated",
    "review_question",
    "mismatch_warning",
    "literature_pending",
    "formalization_pending",
    "expository_bridge",
    "unsafe_unsupported_positive",
)
_FACTUAL_HINT = re.compile(
    r"\b(?:use|uses|used|compute|computes|produce|produces|apply|applies|encode|decode|optimiz|train|"
    r"configure|construct|return|output|input|module|layer|loss|parameter|pipeline|stage|model|method|algorithm)\w*\b",
    re.I,
)
# This narrower pattern answers a different question from ``_FACTUAL_HINT``:
# whether one side of a coordination contains its own predicate and can be
# extracted as an independent atomic clause.  Nominal words such as
# ``output``, ``input``, ``model`` and ``method`` deliberately do not count.
# Otherwise ``returns node_features and output`` is split into a valid return
# claim plus a spurious bare ``output`` claim.
_INDEPENDENT_CLAUSE_VERB = re.compile(
    r"\b(?:uses?|comput(?:e|es|ed|ing)|produc(?:e|es|ed|ing)|"
    r"appl(?:y|ies|ied|ying)|encod(?:e|es|ed|ing)|decod(?:e|es|ed|ing)|"
    r"optimi[sz](?:e|es|ed|ing)|trains?|trained|training|"
    r"configur(?:e|es|ed|ing)|constructs?|constructed|constructing|"
    r"returns?|returned|returning|loads?|loaded|loading|reads?|read|reading|"
    r"writes?|wrote|written|writing|stores?|stored|storing|calls?|called|calling|"
    r"invokes?|invoked|invoking|normaliz(?:e|es|ed|ing)|"
    r"concatenat(?:e|es|ed|ing)|aggregat(?:e|es|ed|ing)|"
    r"propagat(?:e|es|ed|ing)|filters?|filtered|filtering|"
    r"sorts?|sorted|sorting|selects?|selected|selecting|"
    r"reshap(?:e|es|ed|ing)|projects?|projected|projecting|"
    r"attends?|attended|attending|samples?|sampled|sampling|"
    r"checks?|checked|checking|compares?|compared|comparing)\b",
    re.I,
)
# Exact nominal structural labels (``Implementation stage 1``, ``Stage 2``,
# ``Phase 3``).  Only a sentence that is *exactly* a heading-style label —
# an optional single nominal word followed by an ordinal token — may be
# non-factual.  A sentence with any additional content (a predicate, an
# object, a risk marker) is factual and must be reverse-validated.
_ORDINAL_LABEL = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9_-]*\s+)?"
    r"(?:stage|step|phase|layer|level|part|chapter|section)\s+\d+\s*$",
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
    "we describe our approach",
)
# Expository-bridge prefixes: organization / transition / definition
# scaffolding that carries no factual payload.  The bridge classifier is
# fail-closed: a bridge-marked sentence that matches a claim projection, a
# risk marker, or a code-fact inventory shape stays factual and is reverse-
# validated (and will fail if its content is unsupported).
_BRIDGE_PREFIXES = (
    "in this section",
    "in this method",
    "in short",
    "in summary",
    "in the following",
    "overall",
    "we now",
    "we first",
    "we then",
    "we describe",
    "we present",
    "we explain",
    "we turn",
    "the following",
    "the rest of",
    "the remainder",
    "as described",
    "as explained",
    "for clarity",
    "for brevity",
    "to summarize",
    "next",
    "finally",
    "below",
    "this section",
    "this method",
)


def extract_final_text_claims(text: str, projection: AuthoringInputProjection) -> FinalTextClaims:
    text_digest = _digest(text)
    visible_text = _without_html_comments(text)
    units: list[FinalTextUnit] = []
    atomic: list[FinalAtomicClaim] = []
    char_cursor = 0
    unit_number = 1
    claim_number = 1
    for line_number, raw_line in enumerate(visible_text.splitlines(keepends=True), start=1):
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
            expository_bridge = (
                not discourse
                and _is_expository_bridge(sentence, risks, projection)
            )
            unit_kind = (
                "expository_bridge"
                if expository_bridge
                else "discourse" if discourse else kind
            )
            # Fail closed for substantive sentences: arbitrary scientific verbs
            # cannot be exhaustively enumerated, so a sentence is factual unless
            # it is a heading, an explicit discourse prefix, a claim-free
            # expository bridge, or an exact nominal structural label.  A short
            # predicate such as ``Cache stores embeddings.`` must be extracted
            # and reverse-validated even though ``stores`` is not in any
            # allowlist; only the exact ordinal-label form (``Implementation
            # stage 1``) stays non-factual.  No configuration-assignment wording
            # is exempt: an unsupported non-numeric configuration sentence must
            # be extracted and rejected.
            factual = (
                kind != "heading"
                and not discourse
                and not expository_bridge
                and not bool(_ORDINAL_LABEL.match(sentence))
            )
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
                        candidate_author_attested_ids=[
                            item.fragment_id
                            for item in _author_attested_matches(fragment, projection)
                        ],
                        candidate_narrative_ids=[
                            item["point_id"]
                            for item in _candidate_narrative_matches(fragment, projection)
                        ],
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


def classify_final_text_unit_lanes(
    final_claims: FinalTextClaims,
    projection: AuthoringInputProjection,
) -> dict[str, str]:
    """Classify every final-text unit into a product lane (G1 contract).

    The classification is the candidate/verified decision input:
    ``repository_positive`` / ``repository_partial`` are the only lanes that
    may enter the repository-verified document (partial only with preserved
    qualifiers), every other lane stays in the candidate document and must be
    review-linked.  Classification rules are deterministic and fail closed:

    - non-factual units (headings, discourse, expository bridges) ->
      ``expository_bridge`` (structural scaffolding, safe for verified);
    - factual units with author-attested matches or explicit caveat markers ->
      ``author_intent_caveated``;
    - factual units whose atomic claims all match supported projection claims
      -> ``repository_positive``; any partial match -> ``repository_partial``;
    - factual units matching an author review question -> ``review_question``;
    - factual units with no match and no caveat marker ->
      ``unsafe_unsupported_positive`` (never enters verified, review-linked).
    """

    claim_by_unit: dict[str, list[FinalAtomicClaim]] = {}
    for claim in final_claims.atomic_claims:
        claim_by_unit.setdefault(claim.unit_id, []).append(claim)
    projection_by_id = {claim.claim_id: claim for claim in projection.projected_claims}
    author_fragment_ids = {
        fragment.fragment_id for fragment in projection.author_attested_fragments
    }
    candidate_lane_by_id = {
        str(item.get("point_id") or ""): str(item.get("lane") or "")
        for item in _candidate_narrative_points(projection)
        if str(item.get("point_id") or "")
    }
    review_question_token_sets = [
        _tokens(str(question.get("question") or question.get("text") or ""))
        for question in projection.review_questions
        if isinstance(question, dict)
        and str(question.get("question") or question.get("text") or "").strip()
    ]
    lanes: dict[str, str] = {}
    for unit in final_claims.units:
        if not unit.factual or unit.kind in {
            "heading", "discourse", "expository_bridge", "caption",
        }:
            lanes[unit.unit_id] = "expository_bridge"
            continue
        claims = claim_by_unit.get(unit.unit_id, [])
        if not claims:
            # A factual sentence with no extracted claim is an extraction
            # gap; it must never silently enter verified.
            lanes[unit.unit_id] = "unsafe_unsupported_positive"
            continue
        if any(
            claim.candidate_author_attested_ids
            for claim in claims
        ) or any(
            set(claim.candidate_author_attested_ids) & author_fragment_ids
            for claim in claims
        ):
            lanes[unit.unit_id] = "author_intent_caveated"
            continue
        narrative_lanes = {
            candidate_lane_by_id[point_id]
            for claim in claims
            for point_id in claim.candidate_narrative_ids
            if point_id in candidate_lane_by_id
        }
        if narrative_lanes:
            if "repository_mismatch" in narrative_lanes:
                lanes[unit.unit_id] = "mismatch_warning"
            elif "literature_pending" in narrative_lanes:
                lanes[unit.unit_id] = "literature_pending"
            elif "formalization_pending" in narrative_lanes:
                lanes[unit.unit_id] = "formalization_pending"
            else:
                lanes[unit.unit_id] = "author_intent_caveated"
            continue
        unit_tokens = _tokens(unit.text)
        review_framed = (
            "?" in unit.text
            or any(
                marker in unit.text.lower()
                for marker in (
                    "for review", "needs review", "author review",
                    "requires confirmation", "pending confirmation",
                    "to be confirmed", "should the method",
                )
            )
        )
        if review_framed and any(
            len(unit_tokens & question_tokens) / max(
                1, min(len(unit_tokens), len(question_tokens))
            ) >= 0.5
            for question_tokens in review_question_token_sets
        ):
            lanes[unit.unit_id] = "review_question"
            continue
        matched = [
            projection_by_id[claim_id]
            for claim in claims
            for claim_id in claim.candidate_projection_claim_ids
            if claim_id in projection_by_id
        ]
        if not matched:
            lowered = unit.text.lower()
            if any(marker in lowered for marker in _CAVEAT_MARKERS):
                lanes[unit.unit_id] = "author_intent_caveated"
            else:
                lanes[unit.unit_id] = "unsafe_unsupported_positive"
            continue
        if any(claim.support_status == "partial" for claim in matched):
            lanes[unit.unit_id] = "repository_partial"
        else:
            lanes[unit.unit_id] = "repository_positive"
    return lanes


def _author_attested_matches(text: str, projection: AuthoringInputProjection):
    """Find only close matches to the separately-authorized author lane."""

    text_tokens = _tokens(text)
    normalized_text = _normalize(text)
    exact = [
        fragment
        for fragment in projection.author_attested_fragments
        if _normalize(fragment.supported_fragment) == normalized_text
    ]
    if exact:
        return exact
    scored = []
    for fragment in projection.author_attested_fragments:
        fragment_tokens = _tokens(fragment.supported_fragment)
        # Permit a small discourse wrapper (for example, "The goal is to
        # demonstrate ...") but reject an author fragment that grows new
        # factual tokens beyond the callback-bound wording.
        discourse_tokens = {"goal", "aim", "objective", "demonstrate", "method"}
        text_core = text_tokens - discourse_tokens
        fragment_core = fragment_tokens - discourse_tokens
        if not text_core.issubset(fragment_core):
            continue
        overlap = len(text_tokens.intersection(fragment_tokens)) / max(
            1, min(len(text_tokens), len(fragment_tokens))
        )
        if overlap >= 0.7:
            scored.append((overlap, fragment))
    if not scored:
        return []
    best_score = max(score for score, _fragment in scored)
    return [fragment for score, fragment in scored if score >= best_score - 0.06]


def _candidate_narrative_points(
    projection: AuthoringInputProjection,
) -> list[dict[str, object]]:
    """Return all typed candidate-only narrative points.

    These fields already carry the authority lane produced by the projection.
    Combining them here gives the final-text extractor one closed candidate
    surface without promoting any point into ``projected_claims``.
    """

    return [
        item
        for values in (
            projection.author_intent_unverified_points,
            projection.repository_mismatches,
            projection.external_pending_points,
            projection.formalization_needed_points,
        )
        for item in values
        if isinstance(item, dict)
        and str(item.get("point_id") or "").strip()
        and str(item.get("statement") or "").strip()
    ]


def _candidate_narrative_matches(
    text: str,
    projection: AuthoringInputProjection,
) -> list[dict[str, object]]:
    """Match visibly caveated prose to candidate-only author material.

    A lexical match alone is intentionally insufficient: positive prose such
    as ``the predictor uses three layers`` must still fail when it has no
    repository claim.  The sentence must also expose its epistemic status via
    an author-stance, partial-support, mismatch, or pending marker.
    """

    lowered = text.lower()
    if not any(marker in lowered for marker in _CAVEAT_MARKERS):
        return []
    text_tokens = _tokens(text)
    scored: list[tuple[float, dict[str, object]]] = []
    for point in _candidate_narrative_points(projection):
        statement = str(point.get("statement") or "")
        point_tokens = _tokens(statement)
        overlap = len(text_tokens & point_tokens) / max(
            1, min(len(text_tokens), len(point_tokens))
        )
        if overlap >= 0.45 or _normalize(statement) in _normalize(text):
            scored.append((overlap, point))
    if not scored:
        return []
    best = max(score for score, _point in scored)
    return [point for score, point in scored if score >= max(0.45, best - 0.06)]


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
    start = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char not in ".!?":
            index += 1
            continue
        # ``!=`` is a code comparison operator, not a sentence boundary.
        # Splitting ``sum(x) != 1.`` into ``sum(x) !`` and ``= 1.`` produces
        # an orphaned numeric fragment that fails reverse validation.
        if char == "!" and index + 1 < len(text) and text[index + 1] == "=":
            index += 1
            continue
        # Dots inside code identifiers (torch.no_grad), module paths, and
        # decimals are not sentence boundaries. Splitting there can detach a
        # required scope/condition qualifier from the factual clause.
        if (
            char == "."
            and index > 0
            and index + 1 < len(text)
            and (text[index - 1].isalnum() or text[index - 1] == "_")
            and (text[index + 1].isalnum() or text[index + 1] == "_")
        ):
            index += 1
            continue
        end = index + 1
        while end < len(text) and text[end] in ".!?":
            end += 1
        raw = text[start:end]
        sentence = raw.strip()
        if sentence:
            local_start = start + len(raw) - len(raw.lstrip())
            spans.append((sentence, local_start, local_start + len(sentence)))
        start = end
        index = end
    raw = text[start:]
    sentence = raw.strip()
    if sentence:
        local_start = start + len(raw) - len(raw.lstrip())
        spans.append((sentence, local_start, local_start + len(sentence)))
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
    # A clause-like fragment must contain a factual verb (compute, return,
    # call, etc.).  Risk markers alone (a bare number or formula token) do
    # not make an independent clause — ``1 when self.cfg.use_dedicated_attention.``
    # is an operand detached by ``and`` from ``computes the formula for X and 1``,
    # not a standalone factual claim.  Dotted code paths (e.g.
    # ``self.cfg.use_dedicated_attention``) are removed before the check so
    # attribute names containing factual verbs (``use``, ``configure``) are
    # not mistaken for clause verbs.
    cleaned = re.sub(r"`[^`]+`", "", text)
    cleaned = re.sub(r"\b\w+(?:\.\w+)+\b", "", cleaned)
    return bool(_INDEPENDENT_CLAUSE_VERB.search(cleaned))


def _is_discourse(text: str, risks: list[str]) -> bool:
    if risks or _FACTUAL_HINT.search(text):
        return False
    # Discourse exemption is whole-unit and fail-closed.  A discourse bridge
    # (``Next, ...``, ``In this section, ...``) may exempt the sentence only
    # when the complete unit is demonstrably discourse-only: repeatedly strip
    # recognized discourse prefixes; if substantive content remains, the
    # sentence is factual and must be reverse-validated.  A prefix alone can
    # never authorize factual suffix content such as ``Next, cache stores
    # embeddings.``.
    remainder = text.lower().strip()
    while True:
        for prefix in _DISCOURSE_PREFIXES:
            if remainder.startswith(prefix):
                remainder = remainder[len(prefix):].lstrip(" \t,;:.!?")
                break
        else:
            return remainder == ""


# Expository-bridge closed construction grammar.  A bridge remainder must
# match exactly one organizational construction ``[we] VERB (the|this) NOUN``
# (or a bare ``below``/``next`` token) after its marker.  Modal verbs
# (``can``/``will``/``may``/``could``/``should``/``must``) and any other
# substantive token are NOT part of any construction, so a capability or
# purpose assertion composed entirely of otherwise ordinary organization
# words (``This method can address the objective.``) stays factual and is
# reverse-validated.
_ORG_BRIDGE_VERBS = (
    "describe|describes|present|presents|explain|explains|summarize|summarizes|"
    "outline|outlines|discuss|discusses|cover|covers|detail|details|define|defines|"
    "introduce|introduces|conclude|concludes|begin|begins|turn|turns|follow|follows|"
    "close|closes|show|shows|review|reviews|recap|recaps|focus|focuses|highlight|"
    "highlights|address|addresses|walk|walks"
)
_ORG_BRIDGE_NOUNS = (
    "section|method|approach|step|stage|remainder|overview|goal|purpose|objective|"
    "plan|structure|flow|content|rest|scope|parts|layout|angle|perspective|terms|"
    "point|points|manner|way|example|examples|description|introduction|conclusion|"
    "summary|details|notation|below|next|finally|part|chapter|subsection|paragraph|"
    "reader|readers|writing|draft|material|material"
)
_BRIDGE_CONSTRUCTION = re.compile(
    r"^\s*(?:we\s+)?(?:"
    + _ORG_BRIDGE_VERBS
    + r")(?:\s+(?:the|this|its|our))?\s+(?:"
    + _ORG_BRIDGE_NOUNS
    + r")(?:\s+below)?\s*[.!]?\s*$",
    flags=re.IGNORECASE,
)
_BRIDGE_MODALS = re.compile(r"\b(?:can|will|may|could|would|should|must|shall|can't|won't)\b", re.I)


def _is_expository_bridge(text: str, risks: list[str], projection) -> bool:
    """Claim-free organization lane (fail-closed).

    A sentence is an expository bridge only when it starts with a recognized
    bridge marker AND its remainder matches the closed organizational
    construction grammar exactly (``[we] VERB (the|this) NOUN``).  Any other
    remainder — a modal capability or purpose assertion, a claim's canonical
    tokens, a factual predicate, a number, a formula, or a code-fact inventory
    shape — keeps the sentence factual, where it is reverse-validated and
    fails if unsupported.
    """

    if risks or _BRIDGE_MODALS.search(text):
        return False
    remainder = text.lower().strip()
    for prefix in _BRIDGE_PREFIXES:
        if remainder.startswith(prefix):
            remainder = remainder[len(prefix):].lstrip(" \t,;:.!?")
            break
    else:
        return False
    if not remainder:
        return True
    if remainder.strip(" .!") in {"below", "next", "finally", "in short", "in summary"}:
        return True
    if _code_fact_inventory(remainder) or _code_fact_inventory(text):
        return False
    if _projection_matches(text, projection):
        return False
    return bool(_BRIDGE_CONSTRUCTION.match(remainder))


_AUDIT_PREDICATE = re.compile(
    r"^\s*(?:the\s+)?"
    r"(?:`?[A-Za-z_][\w.:]*[_.:][\w.:]*`?|`?sym:[\w.:]+`?)"
    r"(?:\s+(?:operation|method|function|entrypoint|component|procedure|stage|step|phase))?"
    r"(?:\s+(?:loads weights|loads the weights|computes formula|computes the formula|"
    r"computes|returns|concatenates|normalizes|branches on|sorts by|selects top k|"
    r"calls|propagates|attends|reduces|writes|stores|reads|constructs|invokes|runs|applies|"
    r"loads|stores|reads))"
    r"\b",
    flags=re.IGNORECASE,
)


def _normalize_audit_candidate(text: str) -> str:
    """Strip markdown backticks and leading connective wrappers.

    The inventory subject is a code symbol (dotted / underscored / ``sym:``
    path); the wrapper stripping only removes leading flow connectives
    (``the method first``, ``it then``, ``and finally it``) so a wrapped
    record still exposes its symbol before the predicate shape is tested.
    """

    candidate = re.sub(r"`", "", text)
    candidate = re.sub(
        r"^\s*(?:and\s+)?(?:the\s+)?(?:method|system|pipeline)\s+"
        r"(?:first|then|finally|subsequently|afterwards)\s+",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(
        r"^\s*(?:and\s+)?(?:finally|then|first|subsequently|afterwards)\s+(?:it\s+)?",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(
        r"^\s*(?:and\s+)?(?:it\s+)?(?:first|then|finally|subsequently|afterwards)\s+",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    return candidate.strip()


def _code_fact_inventory(text: str) -> bool:
    """Detect the generic behavior-predicate serialization shape."""

    return bool(_AUDIT_PREDICATE.match(_normalize_audit_candidate(text)))


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
    if not scored:
        return []
    # Keep only the best lexical neighborhood.  Returning every claim above a
    # fixed threshold makes a broad sentence about ``features_dc`` inherit
    # qualifiers from an unrelated conditional ``get_features_dc`` claim.  A
    # narrow score band still permits one sentence to restate two equally
    # supported claims, while preventing low-scoring collateral matches from
    # contributing evidence or required qualifiers.
    ranked = sorted(scored, key=lambda pair: pair[0], reverse=True)
    best_score = ranked[0][0]
    score_floor = max(0.45, best_score - 0.06)
    return [claim for score, claim in ranked if score >= score_floor]


def _completeness_failures(units: list[FinalTextUnit], claims: list[FinalAtomicClaim]) -> list[str]:
    claim_units = {claim.unit_id for claim in claims}
    return [
        f"high_risk_unit_not_extracted:{unit.unit_id}"
        for unit in units
        if unit.high_risk_markers and unit.factual and unit.unit_id not in claim_units
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


def _without_html_comments(text: str) -> str:
    """Hide non-rendered Markdown comments while preserving every source offset."""

    return re.sub(
        r"<!--.*?-->",
        lambda match: "".join("\n" if char == "\n" else " " for char in match.group(0)),
        text,
        flags=re.DOTALL,
    )
