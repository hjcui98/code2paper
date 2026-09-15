"""Structural condition matching for Writer/Binder witness authorization.

R5 originally authorized a paragraph witness by comparing *word sets* and a few
derived features of a declared condition.  That is not a logic: grouping,
signs, repeated negation, comparator operand order and scope widening were all
invisible to it.  Five counterexamples (``(alpha or beta) and gamma``,
``value > -5``, ``not not alpha``, ``alpha < beta``, ``alpha`` widened to
``alpha or beta``) were accepted as equivalent.

This module replaces the word-set authorization with an explicit, bounded
grammar:

* the declared condition is parsed into a structural tree (AND/OR with
  commutative children, NOT with multiplicity, ordered comparisons, operands
  as canonical word parts);
* the paragraph witness is split into condition-sized spans that are parsed
  with the same grammar, and a span matches only when its canonical tree is
  *identical* to the declared tree;
* reader-facing phrasings (``is at least``, ``does not hold``, ``is enabled``)
  are rewritten to structure by a fixed phrase table, not by lexical
  intersection;
* any syntax the grammar cannot consume stays unproven, so the witness returns
  to the owning Agent instead of being authorized by a word overlap.

The lexical helpers that remain (stem matching, generic verbs) are used only to
compare *operand wording* inside an already-matching structure.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Literal, Sequence


# ---------------------------------------------------------------------------
# Token vocabulary
# ---------------------------------------------------------------------------

NEGATION_TOKENS = frozenset({
    "not", "no", "never", "without", "unless", "disabled", "false", "off",
    "absent", "missing", "skip", "skips", "skipped", "cannot", "none",
})
UNCONDITIONAL_TOKENS = frozenset({
    "always", "unconditionally", "regardless", "anyway", "invariably",
})
CONNECTIVES = frozenset({
    "when", "whenever", "if", "provided", "assuming", "under", "with",
    "only", "given", "should", "case",
})
NOISE_TOKENS = frozenset({
    "self", "cfg", "config", "configuration", "true", "is", "the", "a", "an",
})
AND_TOKENS = frozenset({"and", "&&", "&", "also"})
OR_TOKENS = frozenset({"or", "||", "|"})
GENERIC_VERBS = frozenset({
    "use", "uses", "used", "using", "enable", "enables", "enabled",
    "enablement", "apply", "applies", "applied", "set", "sets", "setting",
    "add", "adds", "added", "include", "includes", "included",
    "activate", "activates", "activated", "turn", "turns", "turned",
    "switch", "switches", "switched", "on", "off", "hold", "holds", "held",
})
#: Auxiliaries, copulas, prepositions and quantifier filler.  They carry no
#: condition structure; dropping them lets a reader-facing sentence reduce to
#: the same tree as its declarative form.
DROP_TOKENS = frozenset({
    "are", "was", "were", "be", "been", "being", "do", "does", "did",
    "has", "have", "had", "will", "would", "can", "could", "may", "might",
    "must", "of", "to", "for", "in", "at", "by", "from", "than", "that",
    "then", "which", "its", "it", "this", "these", "those", "condition", "flag",
    "conditions", "whenever",
})
#: Reader-facing state words that assert the positive form of a switch.
STATE_TOKENS = frozenset({
    "active", "present", "available", "exists", "exist", "enabled",
})

#: Multi-token comparator phrasings, matched longest first.
COMPARATOR_PHRASES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("greater", "or", "equal"), ">="),
    (("less", "or", "equal"), "<="),
    (("not", "less", "than"), ">="),
    (("no", "less", "than"), ">="),
    (("not", "more", "than"), "<="),
    (("no", "more", "than"), "<="),
    (("at", "least"), ">="),
    (("at", "most"), "<="),
    (("greater", "than"), ">"),
    (("more", "than"), ">"),
    (("exceeds",), ">"),
    (("above",), ">"),
    (("less", "than"), "<"),
    (("fewer", "than"), "<"),
    (("below",), "<"),
    (("equal", "to"), "="),
    (("equals",), "="),
    (("equal",), "="),
    (("not", "equal"), "!="),
    (("different", "from"), "!="),
    (("other", "than"), "!="),
)
#: Multi-token negation phrasings.
NEGATION_PHRASES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("does", "not"), "not"),
    (("do", "not"), "not"),
    (("did", "not"), "not"),
    (("is", "not"), "not"),
    (("are", "not"), "not"),
    (("was", "not"), "not"),
    (("were", "not"), "not"),
    (("has", "not"), "not"),
    (("have", "not"), "not"),
    (("had", "not"), "not"),
    (("can", "not"), "not"),
    (("cannot",), "not"),
    (("will", "not"), "not"),
    (("would", "not"), "not"),
)
_SYMBOL_COMPARATORS: dict[str, str] = {
    ">=": ">=", "<=": "<=", "==": "=", "!=": "!=", ">": ">", "<": "<",
    "=": "=",
}

_NUMBER_RE = re.compile(r"[+-]?\d+(?:\.\d+)?")
_WORD_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SPLIT_RE = re.compile(r"[^A-Za-z0-9]+")
_MULTI_CHAR_OPERATORS = ("&&", "||", ">=", "<=", "==", "!=", "**", "//")
#: Arithmetic / set operators that stay part of the condition structure.  They
#: are never dropped: ``x * y`` and ``x / y`` are different guards.
_ARITHMETIC_OPERATORS = frozenset({"*", "/", "+", "-", "%", "**", "//"})
#: Comparison operators, including the assignment-like ``=``.
_COMPARISON_OPERATORS = frozenset({">=", "<=", "==", "!=", ">", "<", "="})
_SENTENCE_SEPARATORS = frozenset({",", ";", ":"})

Unit = tuple[str, str]

UnitKind = Literal[
    "WORD", "NUM", "VERB", "DROP", "JOIN", "NEG", "WRAP", "UNCOND", "OP",
    "LP", "RP", "LBRACK", "RBRACK", "DOT", "SEP", "SYNTAX",
]


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().strip(".,;:")


def _match_phrase(
    tokens: Sequence[tuple[str, str]],
    index: int,
    table: Sequence[tuple[tuple[str, ...], str]],
) -> tuple[str, int] | None:
    """Match one multi-token phrase at ``index`` (longest table entry first)."""

    values = [
        str(value).casefold() for _kind, value in tokens[index:index + 4]
    ]
    for phrase, replacement in table:
        if len(phrase) > len(values):
            continue
        if tuple(values[: len(phrase)]) == phrase:
            return replacement, len(phrase)
    return None


def _lex_condition(text: str) -> list[tuple[str, str]]:
    """Tokenize a condition without silently dropping syntax.

    Every non-space character is consumed as a word, a number, an operator, a
    bracket, a separator or an explicit ``SYNTAX`` token.  A ``SYNTAX`` token
    fails the parse, so an expression the grammar does not understand stays
    unproven instead of being reduced to the parts the lexer happened to know.
    """

    # A hyphen between ordinary multi-letter words is reader punctuation
    # (``dedicated-attention``), not subtraction.  Keep short symbolic forms
    # such as ``x-y`` structural so arithmetic counterexamples remain rejected.
    text = re.sub(r"(?<=[A-Za-z]{2})-(?=[A-Za-z]{2})", " ", str(text or ""))
    tokens: list[tuple[str, str]] = []
    index = 0
    length = len(text)
    while index < length:
        character = text[index]
        if character.isspace():
            index += 1
            continue
        if character == "." and index + 1 < length and text[index + 1] == ".":
            tokens.append(("SYNTAX", ".."))
            index += 2
            continue
        match = _WORD_TOKEN_RE.match(text, index)
        if match is not None:
            tokens.append(("WORD", match.group(0).casefold()))
            index = match.end()
            continue
        # A sign only starts a number when it is not an operator between two
        # operands (``x - 1`` is subtraction, ``> -1`` is a negative literal).
        previous = tokens[-1][0] if tokens else ""
        signed_number_allowed = previous not in {"WORD", "NUM", "RBRACK", "RP"}
        if character.isdigit() or (
            character in "+-" and signed_number_allowed
        ):
            number = _NUMBER_RE.match(text, index)
            if number is not None:
                tokens.append(("NUMBER", number.group(0)))
                index = number.end()
                continue
        operator = next(
            (
                candidate
                for candidate in _MULTI_CHAR_OPERATORS
                if text.startswith(candidate, index)
            ),
            "",
        )
        if operator:
            tokens.append(("SYMBOL", operator))
            index += len(operator)
            continue
        if character == "!" and not text.startswith("!=", index):
            tokens.append(("BANG", "!"))
            index += 1
            continue
        if character in "<>=!*/+-%":
            tokens.append(("SYMBOL", character))
            index += 1
            continue
        if character == "(":
            tokens.append(("LPAREN", character))
            index += 1
            continue
        if character == ")":
            tokens.append(("RPAREN", character))
            index += 1
            continue
        if character == "[":
            tokens.append(("LBRACK", character))
            index += 1
            continue
        if character == "]":
            tokens.append(("RBRACK", character))
            index += 1
            continue
        if character in _SENTENCE_SEPARATORS or character == ".":
            tokens.append(("PERIOD" if character == "." else "SEP", character))
            index += 1
            continue
        # Unknown punctuation (quotes, question marks, ...) keeps the span from
        # being read as a proven condition.
        tokens.append(("SYNTAX", character))
        index += 1
    return tokens


def condition_units(text: str) -> tuple[Unit, ...]:
    """Rewrite raw text into canonical structural units."""

    normalized = normalize_text(str(text or "")).casefold()
    # An explicit copular state asserts the same positive switch as
    # "is enabled". Do not drop bare "active": it can be an operand or an
    # identifier. Negation, operators, and all other operands remain intact.
    normalized = re.sub(
        r"\bis\s+active(?=\s*(?:[,;!?]|\.(?:\s|$)|$))",
        "is enabled", normalized,
    )
    raw = _lex_condition(normalized)
    units: list[Unit] = []
    index = 0
    while index < len(raw):
        phrase = _match_phrase(raw, index, COMPARATOR_PHRASES)
        if phrase is not None:
            units.append(("OP", phrase[0]))
            index += phrase[1]
            continue
        phrase = _match_phrase(raw, index, NEGATION_PHRASES)
        if phrase is not None:
            units.append(("NEG", phrase[0]))
            index += phrase[1]
            continue
        kind, value = raw[index]
        index += 1
        if kind == "NUMBER":
            units.append(("NUM", value))
            continue
        if kind == "BANG":
            units.append(("NEG", "!"))
            continue
        if kind == "WORD":
            if value in UNCONDITIONAL_TOKENS:
                units.append(("UNCOND", value))
            elif value in AND_TOKENS:
                units.append(("JOIN", "and"))
            elif value in OR_TOKENS:
                units.append(("JOIN", "or"))
            elif value in NEGATION_TOKENS:
                units.append(("NEG", value))
            elif value in CONNECTIVES:
                units.append(("WRAP", value))
            elif value in GENERIC_VERBS:
                units.append(("VERB", value))
            elif value in DROP_TOKENS or value in NOISE_TOKENS:
                units.append(("DROP", value))
            else:
                units.append(("WORD", value))
            continue
        if kind == "SYMBOL":
            if value in _COMPARISON_OPERATORS or value in _ARITHMETIC_OPERATORS:
                units.append(("OP", "=" if value == "==" else value))
            elif value in AND_TOKENS:
                units.append(("JOIN", "and"))
            elif value in OR_TOKENS:
                units.append(("JOIN", "or"))
            continue
        if kind == "LPAREN":
            units.append(("LP", value))
            continue
        if kind == "RPAREN":
            units.append(("RP", value))
            continue
        if kind == "LBRACK":
            units.append(("LBRACK", value))
            continue
        if kind == "RBRACK":
            units.append(("RBRACK", value))
            continue
        if kind == "SEP":
            units.append(("SEP", value))
            continue
        if kind == "PERIOD":
            # A period between operand characters is attribute access; a
            # sentence period separates spans.  Adjacency decides, so
            # ``x.shape[0]`` stays one operand while ``holds. Then`` splits.
            units.append(("DOT", value))
            continue
        units.append(("SYNTAX", value))
    return tuple(_fix_postfix_negation(_resolve_dots(units)))


def _resolve_dots(units: list[Unit]) -> list[Unit]:
    """Turn attribute dots into operand punctuation and sentence dots into SEP.

    ``x.shape[0]`` keeps its attribute chain; a period that ends a word run
    becomes a span separator.  The rule is purely local (neighbouring units),
    so it cannot depend on project vocabulary.
    """

    resolved: list[Unit] = []
    for position, unit in enumerate(units):
        if unit[0] != "DOT":
            resolved.append(unit)
            continue
        before = units[position - 1][0] if position else ""
        after = units[position + 1][0] if position + 1 < len(units) else ""
        if before in {"WORD", "NUM", "RBRACK", "RP"} and after in {
            "WORD", "NUM", "LBRACK"
        }:
            resolved.append(("OPERAND_PUNCT", "."))
        else:
            resolved.append(("SEP", unit[1]))
    return resolved


def _fix_postfix_negation(units: list[Unit]) -> list[Unit]:
    """Turn ``alpha does not hold`` (already rewritten to ``alpha not``) into
    ``not alpha`` so the prefix grammar can parse English word order."""

    result = list(units)
    changed = True
    while changed:
        changed = False
        for index, (kind, value) in enumerate(result):
            if kind != "NEG" or index == 0:
                continue
            previous_kind = result[index - 1][0]
            if previous_kind not in {"WORD", "NUM"}:
                continue
            start = index - 1
            while start > 0 and result[start - 1][0] in {"WORD", "NUM"}:
                start -= 1
            operand = result[start:index]
            result = [
                *result[:start],
                (kind, value),
                *operand,
                *result[index + 1:],
            ]
            changed = True
            break
    return result


def condition_spans(text: str) -> tuple[tuple[Unit, ...], ...]:
    """Split a witness sentence into candidate condition spans."""

    units = list(condition_units(text))
    spans: list[list[Unit]] = []
    current: list[Unit] = []
    for unit in units:
        if unit[0] == "SEP":
            if current:
                spans.append(current)
            current = []
            continue
        current.append(unit)
    if current:
        spans.append(current)
    # A condition may follow its main clause ("the mask is built when X").
    # Every suffix that starts after a conditional connective is a candidate.
    extras: list[list[Unit]] = []
    for span in spans:
        for index, unit in enumerate(span):
            if unit[0] == "WRAP":
                suffix = span[index + 1:]
                if suffix:
                    extras.append(suffix)
    return tuple(tuple(span) for span in (*spans, *extras) if span)


# ---------------------------------------------------------------------------
# Operand parts
# ---------------------------------------------------------------------------


def _drop_words() -> frozenset[str]:
    return frozenset(
        NOISE_TOKENS
        | GENERIC_VERBS
        | CONNECTIVES
        | NEGATION_TOKENS
        | UNCONDITIONAL_TOKENS
        | AND_TOKENS
        | OR_TOKENS
        | DROP_TOKENS
    )


def operand_parts(values: Iterable[str]) -> tuple[str, ...]:
    parts: list[str] = []
    drop = _drop_words()
    for value in values:
        text = str(value)
        # A numeric literal keeps its sign: ``-5`` and ``5`` are different
        # conditions, so the sign must never be normalized away.
        if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
            parts.append("#" + text)
            continue
        for chunk in _SPLIT_RE.split(text):
            if not chunk:
                continue
            if chunk.isdigit():
                parts.append("#" + chunk)
                continue
            word = chunk.casefold()
            if word in drop:
                continue
            parts.append(word)
    return tuple(dict.fromkeys(parts))


def _token_matches(declared_token: str, witness_tokens: set[str]) -> bool:
    """Locate one declared operand part in a witness operand.

    Candidate location only: the structural comparison has already fixed the
    tree, the operator, the operand order and the operand count.
    """

    if declared_token in witness_tokens:
        return True
    for suffix in ("s", "es", "d", "ed", "ing"):
        if declared_token + suffix in witness_tokens:
            return True
    if len(declared_token) >= 6:
        prefix = declared_token[:5]
        return any(
            len(token) >= 5 and token[:5] == prefix for token in witness_tokens
        )
    return False


def _operand_covers(
    declared: tuple[str, ...], witness: tuple[str, ...]
) -> bool:
    if not declared or not witness:
        return False
    witness_set = set(witness)
    return all(_token_matches(token, witness_set) for token in declared)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class _ParseError(Exception):
    pass


class _Parser:
    """Recursive-descent parser for the controlled condition grammar.

    The grammar keeps the full expression: boolean grouping, negation
    multiplicity, comparison operators with ordered operands, arithmetic
    operators and attribute/index operands.  Every token must be consumed, so
    syntax the grammar does not model (including an explicit ``SYNTAX`` token)
    fails the parse instead of being dropped.
    """

    def __init__(self, units: Sequence[Unit]) -> None:
        # Filler words carry no structure; they are removed before parsing so
        # reader-facing phrasing ("x is at least 5") reduces to its expression.
        self.units = [unit for unit in units if unit[0] != "DROP"]
        self.index = 0

    def peek(self) -> Unit | None:
        return self.units[self.index] if self.index < len(self.units) else None

    def take(self) -> Unit:
        unit = self.peek()
        if unit is None:
            raise _ParseError("unexpected end of condition")
        self.index += 1
        return unit

    def parse(self) -> Node:
        while self.peek() is not None and self.peek()[0] in {
            "WRAP", "UNCOND", "SEP",
        }:
            self.index += 1
        node = self.parse_or()
        while self.peek() is not None and self.peek()[0] in {"SEP", "WRAP"}:
            self.index += 1
        if self.peek() is not None:
            raise _ParseError(f"unconsumed syntax: {self.peek()}")
        return node

    def parse_or(self) -> Node:
        children = [self.parse_and()]
        while self.peek() is not None and self.peek() == ("JOIN", "or"):
            self.index += 1
            children.append(self.parse_and())
        return _combine("or", children)

    def parse_and(self) -> Node:
        children = [self.parse_unary()]
        while self.peek() is not None and self.peek() == ("JOIN", "and"):
            self.index += 1
            children.append(self.parse_unary())
        return _combine("and", children)

    def parse_unary(self) -> Node:
        if self.peek() is not None and self.peek()[0] == "NEG":
            self.index += 1
            return ("not", self.parse_unary())
        return self.parse_primary()

    def parse_primary(self) -> Node:
        unit = self.peek()
        if unit is None:
            raise _ParseError("empty condition")
        if unit[0] == "LP":
            self.index += 1
            node = self.parse_or()
            closing = self.peek()
            if closing is None or closing[0] != "RP":
                raise _ParseError("unbalanced parentheses")
            self.index += 1
            return node
        if unit[0] in {
            "RP", "JOIN", "LBRACK", "RBRACK", "SYNTAX", "OPERAND_PUNCT",
        }:
            raise _ParseError(f"unexpected token {unit}")
        return self.parse_comparison()

    def parse_comparison(self) -> Node:
        left = self.parse_arithmetic()
        unit = self.peek()
        if unit is not None and unit[0] == "OP" and unit[1] in _COMPARISON_OPERATORS:
            self.index += 1
            right = self.parse_arithmetic()
            return ("cmp", unit[1], left, right)
        return left

    def parse_arithmetic(self) -> Node:
        left = self.parse_term()
        while True:
            unit = self.peek()
            if unit is None or unit[0] != "OP" or unit[1] not in {"+", "-"}:
                break
            self.index += 1
            right = self.parse_term()
            left = ("arith", unit[1], left, right)
        return left

    def parse_term(self) -> Node:
        left = self.parse_factor()
        while True:
            unit = self.peek()
            if unit is None or unit[0] != "OP" or unit[1] not in {
                "*", "/", "%", "**", "//",
            }:
                break
            self.index += 1
            right = self.parse_factor()
            left = ("arith", unit[1], left, right)
        return left

    def parse_factor(self) -> Node:
        unit = self.peek()
        if unit is not None and unit[0] == "OP" and unit[1] in {"+", "-"}:
            self.index += 1
            operand = self.parse_factor()
            if unit[1] == "-":
                return ("neg", operand)
            return operand
        return self.parse_operand()

    def parse_operand(self) -> Node:
        values: list[str] = []
        verbs = False
        while True:
            unit = self.peek()
            if unit is None:
                break
            if unit[0] in {"WORD", "NUM"}:
                values.append(unit[1])
                self.index += 1
                continue
            if unit[0] == "VERB":
                verbs = True
                self.index += 1
                continue
            if unit[0] in {"OPERAND_PUNCT", "LBRACK", "RBRACK"}:
                # Attribute/index punctuation belongs to the operand: dropping
                # it would equate ``x.shape[0]`` with ``x``.
                values.append(unit[1])
                self.index += 1
                continue
            break
        if not values:
            raise _ParseError("operand without content")
        parts = operand_parts(values)
        if not parts:
            raise _ParseError("operand without content")
        # A compound declaration (``use_dedicated_attention``) names a
        # predicate verb inside the identifier; it still has to be stated with
        # a verb by the witness.
        if not verbs and any(
            chunk.casefold() in GENERIC_VERBS
            for value in values
            for chunk in _SPLIT_RE.split(str(value))
            if chunk
        ):
            verbs = True
        return ("atom", parts, verbs)


def _combine(kind: str, children: list[Node]) -> Node:
    flattened: list[Node] = []
    for child in children:
        if child[0] == kind:
            flattened.extend(child[1])
        else:
            flattened.append(child)
    if len(flattened) == 1:
        return flattened[0]
    # AND/OR are commutative: compare structure, not surface order.
    return (kind, tuple(sorted(flattened, key=_canonical)))


def canonical(node: Node) -> str:
    kind = node[0]
    if kind == "atom":
        return f"atom({'+'.join(node[1])})"
    if kind == "cmp":
        return f"cmp({node[1]},{canonical(node[2])},{canonical(node[3])})"
    if kind == "arith":
        return f"arith({node[1]},{canonical(node[2])},{canonical(node[3])})"
    if kind == "neg":
        return f"neg({canonical(node[1])})"
    if kind == "not":
        return f"not({canonical(node[1])})"
    return f"{kind}({','.join(canonical(child) for child in node[1])})"


_canonical = canonical


def parse_condition(text: str) -> Node | None:
    """Parse one condition expression; ``None`` means unknown syntax."""

    units = condition_units(text)
    if not units:
        return None
    try:
        return _Parser(units).parse()
    except _ParseError:
        return None


def parse_units(units: Sequence[Unit]) -> Node | None:
    try:
        return _Parser(units).parse()
    except _ParseError:
        return None


# ---------------------------------------------------------------------------
# Node comparison
# ---------------------------------------------------------------------------


def _verbs_present(units: Sequence[Unit]) -> bool:
    return any(unit[0] == "VERB" for unit in units)


def _node_has_verb(node: Node) -> bool:
    kind = node[0]
    if kind == "atom":
        return bool(node[2])
    if kind in {"arith", "cmp"}:
        return _node_has_verb(node[2]) or _node_has_verb(node[3])
    if kind in {"not", "neg"}:
        return _node_has_verb(node[1])
    return any(_node_has_verb(child) for child in node[1])


def _subspan(span: Sequence[Unit], container: Sequence[Unit]) -> bool:
    """Return whether ``span`` is a contiguous part of ``container``.

    Candidate spans are generated as suffixes of larger spans, so a condition
    that matched inside a span also matches the enclosing span.  Such a
    duplicate must not be read as a second, appended condition.
    """

    if not span or len(span) > len(container):
        return False
    wanted = tuple(span)
    for start in range(len(container) - len(span) + 1):
        if tuple(container[start:start + len(span)]) == wanted:
            return True
    return False


def _nodes_equivalent(
    declared: Node,
    witness: Node,
    *,
    declared_verbs: bool,
    witness_verbs: bool,
) -> bool:
    if declared[0] != witness[0]:
        return False
    kind = declared[0]
    if kind == "atom":
        if declared[2] and not witness_verbs:
            # A declaration that names a predicate verb must be stated with a
            # verb; a bare noun phrase does not authorize it.
            return False
        return _operand_covers(declared[1], witness[1])
    if kind in {"cmp", "arith"}:
        # The operator and the operand structure are part of the condition:
        # ``x * y > 5`` never authorizes ``x / y > 5``.
        if declared[1] != witness[1]:
            return False
        return _nodes_equivalent(
            declared[2], witness[2],
            declared_verbs=declared_verbs, witness_verbs=witness_verbs,
        ) and _nodes_equivalent(
            declared[3], witness[3],
            declared_verbs=declared_verbs, witness_verbs=witness_verbs,
        )
    if kind == "neg":
        return _nodes_equivalent(
            declared[1],
            witness[1],
            declared_verbs=declared_verbs,
            witness_verbs=witness_verbs,
        )
    if kind == "not":
        return _nodes_equivalent(
            declared[1],
            witness[1],
            declared_verbs=declared_verbs,
            witness_verbs=witness_verbs,
        )
    declared_children = declared[1]
    witness_children = witness[1]
    if len(declared_children) != len(witness_children):
        return False
    # Children are already sorted canonically on both sides; match by identity.
    for left, right in zip(declared_children, witness_children):
        if canonical(left) != canonical(right):
            # Same shape but different operand wording is still a candidate for
            # containment-based operand comparison.
            if not _nodes_equivalent(
                left,
                right,
                declared_verbs=declared_verbs,
                witness_verbs=witness_verbs,
            ):
                return False
    return True


# ---------------------------------------------------------------------------
# Public matcher
# ---------------------------------------------------------------------------


def _flagged_span(units: Sequence[Unit], declared_parts: set[str]) -> bool:
    """Return whether an unmatched span could still change the condition.

    A structural token anywhere in the unmatched part (not only at its start)
    is enough: ``When beta or when alpha, ...`` carries an extra OR branch
    around the matched suffix, and the suffix alone must not authorize the
    narrower declaration.
    """

    for unit in units or ():
        if unit[0] in {"JOIN", "NEG", "OP", "UNCOND", "SYNTAX"}:
            return True
        if unit[0] in {"WORD", "NUM"}:
            parts = operand_parts((unit[1],))
            if parts and any(
                _token_matches(part, set(parts)) for part in declared_parts
            ):
                return True
    return False


def _unmatched_remainder(
    span: Sequence[Unit], matched: Sequence[Unit]
) -> tuple[Unit, ...] | None:
    """Return the tokens of ``span`` outside the contained ``matched`` run."""

    wanted = tuple(matched)
    if not wanted or len(wanted) > len(span):
        return None
    for start in range(len(span) - len(wanted) + 1):
        if tuple(span[start:start + len(wanted)]) == wanted:
            return tuple(span[:start]) + tuple(span[start + len(wanted):])
    return None


def condition_statement_matches(declared: str, witness: str) -> bool:
    """Return whether a paragraph sentence provably states one condition.

    Authorization is structural: the witness must contain a condition span
    whose parsed tree is identical to the declared condition's tree, including
    grouping, negation multiplicity, comparison operators with ordered
    operands, numeric literals with sign, and the operand set.  Anything the
    grammar cannot consume stays unproven.
    """

    declared_norm = normalize_text(declared)
    witness_norm = normalize_text(witness)
    if not declared_norm or not witness_norm:
        return False
    declared_units = condition_units(declared_norm)
    declared_tree = parse_units(declared_units)
    if declared_tree is None:
        return False
    declared_unconditional = any(
        unit[0] == "UNCOND" for unit in declared_units
    )
    witness_units = condition_units(witness_norm)
    if not declared_unconditional:
        if not any(unit[0] == "WRAP" for unit in witness_units):
            # The witness must state the condition conditionally.
            return False
        if any(unit[0] == "UNCOND" for unit in witness_units):
            return False
    declared_verbs = _verbs_present(declared_units) or _node_has_verb(
        declared_tree
    )
    declared_canonical = canonical(declared_tree)
    declared_parts: set[str] = set()

    def collect(node: Node) -> None:
        kind = node[0]
        if kind == "atom":
            declared_parts.update(node[1])
        elif kind in {"cmp", "arith"}:
            collect(node[2])
            collect(node[3])
        elif kind in {"not", "neg"}:
            collect(node[1])
        else:
            for child in node[1]:
                collect(child)

    collect(declared_tree)
    spans = condition_spans(witness_norm)
    matched_index: int | None = None
    matched_span: tuple[Unit, ...] = ()
    for index, span in enumerate(spans):
        witness_tree = parse_units(span)
        if witness_tree is None:
            continue
        witness_verbs = _verbs_present(span) or _node_has_verb(witness_tree)
        if not _nodes_equivalent(
            declared_tree,
            witness_tree,
            declared_verbs=declared_verbs,
            witness_verbs=witness_verbs,
        ):
            continue
        if declared_verbs and not witness_verbs:
            continue
        matched_index = index
        matched_span = tuple(span)
        break
    if matched_index is None:
        return False
    for index, span in enumerate(spans):
        if index == matched_index:
            continue
        if _subspan(span, matched_span):
            # A suffix of the matched condition is the same condition seen
            # through a smaller candidate span.
            continue
        if _subspan(matched_span, span):
            # A larger span that contains the match is only the same condition
            # when nothing structural surrounds it; an extra ``or``/``when``
            # branch outside the matched run changes the guard.
            remainder = _unmatched_remainder(span, matched_span)
            if remainder is None or not _flagged_span(remainder, declared_parts):
                continue
            return False
        if _flagged_span(span, declared_parts):
            return False
    return True


__all__ = [
    "AND_TOKENS",
    "COMPARATOR_PHRASES",
    "CONNECTIVES",
    "DROP_TOKENS",
    "GENERIC_VERBS",
    "NEGATION_PHRASES",
    "NEGATION_TOKENS",
    "NOISE_TOKENS",
    "OR_TOKENS",
    "STATE_TOKENS",
    "UNCONDITIONAL_TOKENS",
    "canonical",
    "condition_spans",
    "condition_statement_matches",
    "condition_units",
    "normalize_text",
    "operand_parts",
    "parse_condition",
    "parse_units",
]
