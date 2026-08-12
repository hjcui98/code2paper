"""R5.1 robust intent compiler: author YAML -> typed obligations.

Implements design section 8.1 (``intent_compiler`` node) and the R5.1
execution plan.  The V1 compiler in ``intent_obligations.py`` produced
obligations whose coverage resolution relied on English token overlap and
project-specific claim ids (``C-RAP-*``).  The V2 compiler is generic and
multilingual: it maps author language (Chinese or English, paraphrased or
reordered) to a canonical set of ``TypedBehaviorTargetV1`` whose
``desired_predicates`` come from the project-agnostic
``BEHAVIOR_PREDICATES`` vocabulary.

Design invariants enforced here:

- the same semantic intent always produces the same set of
  ``desired_predicates`` regardless of wording, language or stage order
  (R5.2);
- training-scoped language and inference-scoped language produce targets
  with distinct ``conditions`` so the alignment layer can refuse to cover
  a training obligation with inference facts (R5.3);
- author stage names become ``organization_preference`` only, never a
  positive fact (R5.1);
- obligations whose typed targets cannot be derived from executable
  behavior (rationale, innovation, mismatch) are emitted as
  ``verify_only`` so they terminate as explicit gaps instead of entering
  the Method正文.

R5.4 hard constraint: this module's source MUST NOT contain project-specific
literals (``F-RAP-*``, ``C-RAP-*``, ``EBCAR``, ``DyG-Mamba``, ``LinearRAG``).
The concept registry only knows generic behavior categories.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from code2paper.agentic.author_intent_summary import AuthorIntentSummary
from code2paper.agentic.behavior_graph import (
    BEHAVIOR_PREDICATES,
    BEHAVIOR_RELATION_KINDS,
)
from code2paper.agentic.method_product_models import (
    AuthorStoryNodeV1,
    MethodEvidenceLane,
)
from code2paper.agentic.research_models import TypedBehaviorTargetV1


# ---------------------------------------------------------------------------
# Intent concept registry
# ---------------------------------------------------------------------------


class IntentConceptV1(BaseModel):
    """A semantic concept that maps author language to behavior predicates.

    ``terms_en`` and ``terms_cn`` are trigger phrases: when any of them
    appears in author text the concept is considered matched and its
    ``predicates`` / ``relations`` are added to the obligation's typed
    behavior target.  Terms are matched case-insensitively as substrings
    so they survive paraphrase, hyphenation and CJK tokenization
    differences.  ``scope`` records whether the concept indicates
    ``training``, ``inference`` or ``any`` execution scope; the
    alignment layer uses this to refuse cross-scope coverage.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    concept_id: str
    predicates: tuple[str, ...] = Field(default_factory=tuple)
    relations: tuple[str, ...] = Field(default_factory=tuple)
    terms_en: tuple[str, ...] = Field(default_factory=tuple)
    terms_cn: tuple[str, ...] = Field(default_factory=tuple)
    scope: str = "any"
    role_hint: str = ""

    @field_validator("predicates")
    @classmethod
    def _known_predicates(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        unknown = [p for p in value if p not in BEHAVIOR_PREDICATES]
        if unknown:
            raise ValueError(f"unknown behavior predicates: {unknown}")
        return value

    @field_validator("relations")
    @classmethod
    def _known_relations(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        unknown = [r for r in value if r not in BEHAVIOR_RELATION_KINDS]
        if unknown:
            raise ValueError(f"unknown behavior relations: {unknown}")
        return value

    @field_validator("scope")
    @classmethod
    def _known_scope(cls, value: str) -> str:
        if value not in {"any", "training", "inference"}:
            raise ValueError(f"unknown scope: {value}")
        return value


#: Canonical concept registry.  Order matters only for deterministic
#: ``search_terms`` emission; the predicate union is order-independent.
INTENT_CONCEPTS: tuple[IntentConceptV1, ...] = (
    IntentConceptV1(
        concept_id="feature_construction",
        predicates=("READ", "CONSTRUCT"),
        terms_en=(
            "feature", "descriptor", "attribute", "embedding",
            "construct", "build",
            "representation", "input",
        ),
        terms_cn=(
            "特征", "描述符", "属性", "嵌入", "构造", "构建", "表示", "输入",
        ),
        role_hint="feature",
    ),
    IntentConceptV1(
        concept_id="feature_transform",
        predicates=("TRANSFORM",),
        terms_en=("encode", "encodes", "encoding", "transform", "augment"),
        terms_cn=("编码", "变换", "增强"),
        role_hint="feature",
    ),
    IntentConceptV1(
        concept_id="feature_normalization",
        predicates=("NORMALIZE",),
        terms_en=("normalize", "normalizes", "normalized", "normalization"),
        terms_cn=("归一化", "标准化"),
        role_hint="feature",
    ),
    IntentConceptV1(
        concept_id="feature_combination",
        predicates=("CONCAT",),
        terms_en=("concat", "concatenate", "concatenation", "combine"),
        terms_cn=("拼接", "串联", "合并"),
        role_hint="feature",
    ),
    IntentConceptV1(
        concept_id="score_prediction",
        predicates=("COMPUTE", "CALL"),
        terms_en=(
            "predict", "predicts", "predicting", "prediction", "score",
            "scores", "scoring", "mlp", "mapping", "regress", "regression",
            "estimate", "importance", "weight", "predictor",
        ),
        terms_cn=(
            "预测", "打分", "评分", "得分", "分数", "回归", "估计",
            "重要性", "权重", "预测器",
        ),
        role_hint="predictor",
    ),
    IntentConceptV1(
        concept_id="ranking_selection",
        predicates=("SORT", "TOPK", "SELECT"),
        terms_en=(
            "rank", "ranks", "ranked", "ranking", "sort", "sorts", "sorting",
            "sorted", "top-k", "topk", "select", "selects", "selecting",
            "selected", "descending", "ascending",
        ),
        terms_cn=(
            "排序", "排名", "选择", "选取", "前k", "降序", "升序",
        ),
        role_hint="ranking",
    ),
    IntentConceptV1(
        concept_id="masking_filtering",
        predicates=("MASK", "FILTER"),
        terms_en=(
            "mask", "masks", "masking", "masked", "filter", "filters",
            "filtering", "filtered", "prune", "prunes", "pruning", "pruned",
            "remove", "removes", "removing", "removed", "drop", "drops",
            "keep", "keeps", "retain", "retained", "threshold",
        ),
        terms_cn=(
            "掩码", "遮罩", "过滤", "筛选", "剪枝", "修剪",
            "移除", "去除", "保留", "阈值",
        ),
        role_hint="filter",
    ),
    IntentConceptV1(
        concept_id="training_objective",
        predicates=("COMPUTE", "REDUCE", "AGGREGATE"),
        terms_en=(
            "train", "trains", "training", "trained",
            "learn", "learns", "learning", "learned",
            "loss", "losses", "objective", "objectives",
            "optimizer", "optimizers", "backward",
            "gradient", "gradients", "fit", "fits", "fitting",
            "cross-entropy", "infoNCE", "BCE",
            "contrastive", "training loss", "training losses",
            "training step", "training steps",
        ),
        terms_cn=(
            "训练", "学习", "损失", "目标", "优化器", "反向",
            "梯度", "交叉熵", "对比", "训练损失",
        ),
        scope="training",
        role_hint="training",
    ),
    IntentConceptV1(
        concept_id="inference_deploy",
        predicates=("CALL", "RETURN"),
        terms_en=(
            "infer", "inference", "deploy", "eval", "evaluate",
            "test", "forward", "rendering-free",
            "without rendering", "runtime",
        ),
        terms_cn=(
            "推理", "推断", "部署", "评估", "测试", "前向",
            "免渲染", "运行时",
        ),
        scope="inference",
        role_hint="inference",
    ),
    IntentConceptV1(
        concept_id="attention_mechanism",
        predicates=("ATTEND", "COMPUTE", "MASK"),
        terms_en=(
            "attention", "attend", "self-attention", "cross-attention",
            "scaled dot-product",
        ),
        terms_cn=(
            "注意力", "关注", "自注意力", "交叉注意力",
            "查询", "键", "值", "缩放点积",
        ),
        role_hint="attention",
    ),
    IntentConceptV1(
        concept_id="graph_construction",
        predicates=("CALL", "WRITE"),
        terms_en=(
            "graph construction", "graph index", "indexing", "adjacency",
            "adjacency matrix", "adjacency matrices", "create nodes",
            "build graph",
        ),
        terms_cn=(
            "图构建", "图索引", "建立索引", "邻接矩阵", "创建节点",
        ),
        role_hint="graph_builder",
    ),
    IntentConceptV1(
        concept_id="propagation_message_passing",
        predicates=("PROPAGATE", "AGGREGATE", "SAMPLE"),
        terms_en=(
            "propagate", "propagates", "propagating", "propagation",
            "message passing", "diffuse",
            "ppr", "pagerank", "personalized pagerank", "random walk",
            "bipartite",
        ),
        terms_cn=(
            "传播", "消息传递", "扩散", "随机游走",
            "二部图", "稀疏",
        ),
        role_hint="propagation",
    ),
    IntentConceptV1(
        concept_id="temporal_sequence",
        predicates=("SAMPLE", "STACK", "CONCAT", "ATTEND", "COMPUTE"),
        terms_en=(
            "temporal", "timespan", "timestamp", "elapsed time", "history",
            "elapsed", "timestamp", "mamba", "ssm", "state space",
            "readout", "gate", "gated",
        ),
        terms_cn=(
            "时序", "时间", "序列", "历史", "邻居",
            "时间戳", "门控", "读出",
        ),
        role_hint="temporal",
    ),
    IntentConceptV1(
        concept_id="generation_invocation",
        predicates=("CALL", "RETURN"),
        terms_en=(
            "generation", "invoke", "invokes", "execute", "executes",
            "emit", "emits",
        ),
        terms_cn=(
            "生成", "产生", "调用", "执行", "输出结果",
        ),
        role_hint="generation",
    ),
    IntentConceptV1(
        concept_id="verification_decision",
        predicates=("COMPARE", "BRANCH"),
        terms_en=(
            "verify", "verifies", "verification", "verifier",
            "compare", "compares", "comparison", "accept", "accepted",
            "reject", "rejected",
        ),
        terms_cn=(
            "验证", "校验", "比较", "接受", "拒绝",
        ),
        role_hint="verification",
    ),
    IntentConceptV1(
        concept_id="result_composition",
        predicates=("CONCAT", "RETURN"),
        terms_en=(
            "append", "appends", "concatenate", "concatenates",
            "compose", "composes", "assemble", "assembles",
        ),
        terms_cn=(
            "拼接", "追加", "组合结果", "组装",
        ),
        role_hint="composition",
    ),
    IntentConceptV1(
        concept_id="data_io",
        predicates=("READ", "WRITE", "LOAD", "SERIALIZE"),
        terms_en=(
            "load", "save", "read", "write", "file", "serialize",
            "checkpoint", "store", "persist",
        ),
        terms_cn=(
            "加载", "保存", "读取", "写入", "文件",
            "序列化", "输出", "存储",
        ),
        role_hint="io",
    ),
    IntentConceptV1(
        concept_id="control_branch",
        predicates=("BRANCH", "LOOP"),
        terms_en=(
            "branch", "fallback", "loop", "iterate", "condition",
            "default", "if ", "else", "switch", "case",
        ),
        terms_cn=(
            "分支", "条件", "回退", "循环", "迭代", "默认",
        ),
        role_hint="control",
    ),
    IntentConceptV1(
        concept_id="configuration",
        predicates=(),
        relations=("CONFIGURED_BY",),
        terms_en=(
            "config", "configure", "default", "parameter", "threshold",
            "hyperparameter", "setting",
        ),
        terms_cn=(
            "配置", "参数", "阈值", "超参", "默认值", "设置",
        ),
        role_hint="config",
    ),
    IntentConceptV1(
        concept_id="task_head_output",
        predicates=("PROJECT", "COMPUTE", "RETURN"),
        terms_en=(
            "classifier", "regressor", "head",
            "node classification", "link prediction", "output layer",
            "sigmoid", "logit",
        ),
        terms_cn=(
            "分类器", "回归器", "预测头", "链路预测",
            "节点分类", "输出层",
        ),
        role_hint="task_head",
    ),
)


# ---------------------------------------------------------------------------
# Obligation graph V2
# ---------------------------------------------------------------------------


ObligationKindV2 = str
ObligationPriorityV2 = str

#: Closed obligation kinds (same surface as V1 for compatibility).
OBLIGATION_KINDS_V2: tuple[str, ...] = (
    "method_mainline",
    "stage",
    "component",
    "organization",
    "rationale_check",
    "high_risk_claim",
    "mismatch_check",
)

#: Closed priority levels.
OBLIGATION_PRIORITIES_V2: tuple[str, ...] = (
    "must_cover", "should_cover", "preference", "verify_only",
)


class IntentObligationV2(BaseModel):
    """One author-requested method question with typed behavior targets.

    Unlike V1, every obligation carries zero or more
    ``TypedBehaviorTargetV1`` derived from the author text.  The targets
    are the only input the alignment layer uses to decide whether a fact
    set covers the obligation: the ``author_text`` is retained for
    diagnostics and search only, never for coverage authorization.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    obligation_id: str
    kind: ObligationKindV2
    priority: ObligationPriorityV2
    source_field: str
    source_index: int = 0
    author_text: str
    typed_behavior_targets: tuple[TypedBehaviorTargetV1, ...] = Field(default_factory=tuple)
    retrieval_queries: tuple[str, ...] = Field(default_factory=tuple)
    candidate_paths: tuple[str, ...] = Field(default_factory=tuple)
    status: str = "unresolved"

    @field_validator("kind")
    @classmethod
    def _known_kind(cls, value: str) -> str:
        if value not in OBLIGATION_KINDS_V2:
            raise ValueError(f"unknown obligation kind: {value}")
        return value

    @field_validator("priority")
    @classmethod
    def _known_priority(cls, value: str) -> str:
        if value not in OBLIGATION_PRIORITIES_V2:
            raise ValueError(f"unknown obligation priority: {value}")
        return value


class IntentObligationRelationV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_obligation_id: str
    target_obligation_id: str
    relation: str = "precedes"

    @field_validator("relation")
    @classmethod
    def _known_relation(cls, value: str) -> str:
        if value not in {"precedes", "supports", "checks"}:
            raise ValueError(f"unknown relation: {value}")
        return value


class IntentObligationGraphV2(BaseModel):
    """Content-addressed V2 intent graph.

    The digest covers obligation ids, kinds, priorities, source fields and
    the *normalized* typed behavior targets.  Every field that can change
    research selection or coverage (including role, semantic requirements,
    aliases and search terms) is part of the digest.  It deliberately
    excludes raw ``author_text``: two author YAMLs that compile to the same
    typed targets produce the same digest.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "2.0"
    mode: str = "intent-obligation-graph-v2"
    project_goal: str = ""
    method_goal: str = ""
    implementation_scope: str = ""
    obligations: list[IntentObligationV2] = Field(default_factory=list)
    relations: list[IntentObligationRelationV2] = Field(default_factory=list)
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "IntentObligationGraphV2":
        payload = {
            "schema_version": self.schema_version,
            "mode": self.mode,
            "project_goal": self.project_goal,
            "method_goal": self.method_goal,
            "implementation_scope": self.implementation_scope,
            "obligations": [
                {
                    "obligation_id": o.obligation_id,
                    "kind": o.kind,
                    "priority": o.priority,
                    "source_field": o.source_field,
                    "source_index": o.source_index,
                    "typed_targets": [
                        {
                            "target_id": t.target_id,
                            "role": t.role,
                            "desired_predicates": sorted(t.desired_predicates),
                            "predicate_groups": [
                                sorted(group) for group in t.predicate_groups
                            ],
                            "required_relations": sorted(t.required_relations),
                            "inputs": sorted(t.inputs),
                            "transformations": sorted(t.transformations),
                            "decisions": sorted(t.decisions),
                            "outputs": sorted(t.outputs),
                            "conditions": sorted(t.conditions),
                            "search_terms": sorted(t.search_terms),
                            "aliases": sorted(t.aliases),
                            "organization_preference": t.organization_preference,
                            "risk_level": t.risk_level,
                            "scope": _scope_of(t),
                        }
                        for t in o.typed_behavior_targets
                    ],
                }
                for o in self.obligations
            ],
            "relations": [r.model_dump(mode="json") for r in self.relations],
        }
        digest = _digest_payload(payload)
        object.__setattr__(self, "content_digest", digest)
        return self


# ---------------------------------------------------------------------------
# Concept matching
# ---------------------------------------------------------------------------


def _normalize_text(text: str) -> str:
    """Lowercase + collapse whitespace + strip hyphens for substring match.

    Hyphen stripping lets ``top-k`` match ``topk`` and ``cross-attention``
    match ``cross attention``.  CJK characters are preserved as-is because
    concept terms are matched as substrings against the raw text too.
    """

    lowered = (text or "").lower()
    # Normalize hyphens and dashes to spaces so hyphenation variants match.
    cleaned = re.sub(r"[\-\u2010\u2011\u2012\u2013\u2014\u2212]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def _match_concepts(text: str) -> list[IntentConceptV1]:
    """Return the list of concepts whose terms appear in ``text``.

    Matching is case-insensitive substring on the normalized text for both
    English and Chinese terms.  Substring matching is intentional: it
    survives CJK tokenization differences, hyphenation and paraphrase
    (``training loss`` matches ``loss``, ``训练`` matches ``训练损失``).
    """

    normalized = _normalize_text(text)
    if not normalized:
        return []
    matched: list[IntentConceptV1] = []
    for concept in INTENT_CONCEPTS:
        terms = tuple(concept.terms_en) + tuple(concept.terms_cn)
        if any(_term_present(term, normalized) for term in terms):
            matched.append(concept)
    return matched


def _term_present(term: str, normalized_text: str) -> bool:
    """Match a concept term against normalized text.

    English terms are matched on word boundaries when the term is purely
    alphabetic, so ``train`` does not match ``trainer``.  CJK and
    hyphenated terms are matched as substrings because word boundaries are
    not well-defined for CJK.
    """

    term_norm = _normalize_text(term)
    if not term_norm:
        return False
    if re.fullmatch(r"[a-z][a-z0-9 ]*", term_norm):
        # Word-boundary match for pure-Latin terms.
        return re.search(rf"\b{re.escape(term_norm)}\b", normalized_text) is not None
    return term_norm in normalized_text


def _scope_of(target: TypedBehaviorTargetV1) -> str:
    """Extract the execution scope recorded in a target's conditions."""

    for cond in target.conditions:
        if cond in {"training", "inference"}:
            return cond
    return "any"


# ---------------------------------------------------------------------------
# Typed behavior target builder
# ---------------------------------------------------------------------------


def _build_typed_targets(
    *,
    obligation_id: str,
    author_text: str,
    concepts: list[IntentConceptV1],
    organization_preference: str = "",
) -> list[TypedBehaviorTargetV1]:
    """Build one typed behavior target per matched semantic concept.

    Keeping concepts separate prevents a broad author sentence from turning
    into one permissive predicate union (for example, local TOPK plus an
    unrelated CONCAT falsely satisfying a PageRank stage).  Scope remains a
    condition on each target, and selected high-specificity author terms are
    retained as semantic anchors that must replay from one source fact.
    """

    if not concepts:
        return []
    targets: list[TypedBehaviorTargetV1] = []
    seen: set[tuple[Any, ...]] = set()
    for concept in concepts:
        scope = concept.scope or "any"
        conditions: tuple[str, ...] = (scope,) if scope in {"training", "inference"} else ()
        role = concept.role_hint or scope
        predicate_group = tuple(sorted(set(concept.predicates)))
        anchor = _concept_semantic_anchor(author_text, concept)
        code_symbol = _author_code_symbol(author_text)
        semantic_anchors = tuple(
            value for value in (anchor, code_symbol) if value
        )
        signature = (
            scope, role, predicate_group, tuple(sorted(concept.relations)),
            semantic_anchors,
        )
        if signature in seen:
            continue
        seen.add(signature)
        target_id = _stable_id(
            "target",
            obligation_id,
            concept.concept_id,
            scope,
            "+".join(predicate_group),
            "+".join(sorted(concept.relations)),
            "+".join(semantic_anchors),
        )
        targets.append(TypedBehaviorTargetV1(
            target_id=target_id,
            role=role,
            desired_predicates=predicate_group,
            predicate_groups=(predicate_group,) if predicate_group else (),
            required_relations=tuple(sorted(concept.relations)),
            transformations=semantic_anchors,
            conditions=conditions,
            search_terms=tuple(_search_terms_from(author_text, [concept])),
            aliases=((concept.role_hint,) if concept.role_hint else ()),
            outputs=tuple(_target_outputs(author_text, concept)),
            organization_preference=organization_preference,
            risk_level="high" if scope == "training" else "medium",
        ))
    return targets


def _author_code_symbol(author_text: str) -> str:
    """Extract an explicit ``path::Symbol`` author anchor, when present.

    Generated component markers use this notation to identify the intended
    implementation owner. Retaining the symbol as a semantic requirement
    prevents a missing owner from being silently replaced by an operation in
    an evaluator or an alternate model.
    """

    match = re.search(
        r"(?:^|\s)[^\s:]+::([A-Za-z_][A-Za-z0-9_.]*)\s*:",
        author_text,
    )
    return match.group(1) if match else ""


_SEMANTIC_ANCHOR_TERMS: dict[str, tuple[str, ...]] = {
    "training_objective": (
        "infonce", "info nce", "contrastive", "cross-entropy",
        "cross entropy", "bce",
    ),
    "score_prediction": (
        "scores", "score", "similarities", "similarity",
        "query–sentence similarities", "query-sentence similarities",
    ),
    "masking_filtering": (
        "pruning", "threshold", "filtering", "filter", "dynamic pruning",
    ),
    "attention_mechanism": (
        "scaled dot-product", "self-attention", "cross-attention", "attention",
    ),
    "graph_construction": (
        "adjacency matrices", "adjacency matrix", "adjacency",
        "graph construction", "graph index", "indexing",
    ),
    "propagation_message_passing": (
        "personalized pagerank", "pagerank", "ppr", "random walk",
        "message passing", "propagating", "propagation", "propagate",
    ),
    "temporal_sequence": (
        "state space", "mamba", "ssm", "timespan", "elapsed time",
        "timestamp", "temporal",
    ),
    "generation_invocation": (
        "generation", "generate", "answer", "infer", "qa",
    ),
}


def _concept_semantic_anchor(author_text: str, concept: IntentConceptV1) -> str:
    """Return one strong author term that executable evidence must witness."""

    normalized = _normalize_text(author_text)
    for term in _SEMANTIC_ANCHOR_TERMS.get(concept.concept_id, ()):
        if _term_present(term, normalized):
            return term
    return ""


def _quantitative_outputs(author_text: str) -> list[str]:
    """Retain explicit output dimensions as typed, code-verifiable detail."""

    outputs: list[str] = []
    for match in re.finditer(
        r"\b(\d+)\s*(?:[-‐-―]\s*)?(?:dimensional|dimension|dims?)\b",
        author_text,
        flags=re.IGNORECASE,
    ):
        value = f"dimension {match.group(1)}"
        if value not in outputs:
            outputs.append(value)
    return outputs


def _target_outputs(
    author_text: str,
    concept: IntentConceptV1,
) -> list[str]:
    """Derive explicit, code-checkable outputs for one semantic target."""

    outputs = _quantitative_outputs(author_text)
    if (
        concept.concept_id == "generation_invocation"
        and re.search(
            r"\b(?:query|queries|question|questions|retrieval[- ]augmented)\b",
            author_text,
            flags=re.IGNORECASE,
        )
        and "answer" not in outputs
    ):
        # A query-facing retrieval-augmented generation lifecycle is not
        # complete at the model invocation; executable evidence must also
        # expose the answer/result path consumed by the caller.
        outputs.append("answer")
    return outputs


def _search_terms_from(author_text: str, concepts: list[IntentConceptV1]) -> list[str]:
    """Derive a compact set of search terms for the research tools."""

    positioned: list[tuple[int, int, str]] = []
    lowered = author_text.lower()
    for concept in concepts:
        for term in concept.terms_en:
            term_lower = term.lower()
            latin_term = bool(re.fullmatch(r"[a-z][a-z0-9 ]*", term_lower))
            match = (
                re.search(rf"\b{re.escape(term_lower)}\b", lowered)
                if latin_term
                else None
            )
            position = (
                match.start()
                if match is not None
                else (-1 if latin_term else lowered.find(term_lower))
            )
            if position >= 0 and _term_present(term, lowered):
                positioned.append((position, -len(term), term))
        for term in concept.terms_cn:
            position = author_text.find(term)
            if position >= 0:
                positioned.append((position, -len(term), term))
    terms: list[str] = []
    for _position, _negative_length, term in sorted(positioned):
        if term not in terms:
            terms.append(term)
    return terms[:12]


def _aliases_from(concepts: list[IntentConceptV1]) -> list[str]:
    """Role aliases from matched concepts, used by behavior templates."""

    aliases: list[str] = []
    for concept in concepts:
        if concept.role_hint and concept.role_hint not in aliases:
            aliases.append(concept.role_hint)
    return aliases


# ---------------------------------------------------------------------------
# Obligation id helpers (stable, content-addressed)
# ---------------------------------------------------------------------------


def _obligation_id(kind: str, index: int, author_text: str) -> str:
    """Stable id derived from kind + index + normalized author text.

    The id is stable across paraphrase only when the normalized author
    text is the same.  For the cross-paraphrase equivalence test the
    caller compares typed targets (which are paraphrase-invariant), not
    obligation ids.
    """

    normalized = _normalize_text(author_text)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
    return f"O-{kind.upper().replace('_', '-')}-{index + 1:02d}-{digest}"


def _retrieval_queries(author_text: str, concepts: list[IntentConceptV1]) -> tuple[str, ...]:
    """Build retrieval queries from author text and matched concept terms."""

    queries: list[str] = []
    concept_terms: list[str] = []
    for concept in concepts:
        concept_terms.extend(concept.terms_en[:3])
    if concept_terms:
        queries.append(" ".join(sorted(set(concept_terms))[:10]))
    compact = " ".join(_normalize_text(author_text).split()[:14])
    if compact and compact not in queries:
        queries.append(compact)
    return tuple(queries)


def _paths_from_module_role(text: str) -> list[str]:
    prefix = text.split(":", 1)[0].strip()
    path = prefix.split("::", 1)[0].strip()
    return [path] if "/" in path or path.endswith((".py", ".js", ".ts", ".go", ".rs", ".java")) else []


# ---------------------------------------------------------------------------
# Core compiler
# ---------------------------------------------------------------------------


def compile_intent_obligation_graph_v2(
    summary: AuthorIntentSummary | None,
) -> IntentObligationGraphV2:
    """Compile an ``AuthorIntentSummary`` into a typed V2 obligation graph.

    The compiler is deterministic and multilingual.  It produces the same
    set of ``desired_predicates`` for the same semantic intent regardless
    of whether the author wrote in Chinese or English, paraphrased the
    text, or reordered the pipeline steps.

    Obligation structure mirrors V1 for compatibility:

    - ``method_mainline``  (must_cover)   from ``method_mainline`` / ``method_goal``
    - ``stage``            (must_cover)   from ``pipeline_steps``
    - ``component``        (should_cover) from ``module_roles``
    - ``organization``     (preference)   from ``story_order``
    - ``rationale_check``  (verify_only)  from ``design_intents``
    - ``high_risk_claim``  (verify_only)  from ``innovation_claims``
    - ``mismatch_check``   (verify_only)  from ``potential_mismatches``

    ``verify_only`` obligations still receive typed targets so the
    alignment layer can form an explicit gap when the requested behavior
    is absent from the executable code; they never become positive
    Method claims.
    """

    if summary is None:
        return IntentObligationGraphV2()

    obligations: list[IntentObligationV2] = []
    seen: set[tuple[str, str]] = set()

    def _add(
        *,
        kind: str,
        priority: str,
        source_field: str,
        source_index: int,
        text: str,
        paths: list[str] | None = None,
        organization_preference: str = "",
    ) -> None:
        clean = _clean(text)
        signature = (kind, _normalize_text(clean))
        if not clean or signature in seen:
            return
        seen.add(signature)
        concepts = _match_concepts(clean)
        targets = _build_typed_targets(
            obligation_id=_obligation_id(kind, source_index, clean),
            author_text=clean,
            concepts=concepts,
            organization_preference=organization_preference,
        )
        candidate_paths = _dedupe([*(paths or []), *summary.priority_files])[:24]
        obligations.append(IntentObligationV2(
            obligation_id=_obligation_id(kind, source_index, clean),
            kind=kind,
            priority=priority,
            source_field=source_field,
            source_index=source_index,
            author_text=clean,
            typed_behavior_targets=tuple(targets),
            retrieval_queries=_retrieval_queries(clean, concepts),
            candidate_paths=tuple(candidate_paths),
        ))

    _add(
        kind="method_mainline",
        priority="must_cover",
        source_field="method_mainline",
        source_index=0,
        text=summary.method_mainline or summary.method_goal,
    )
    for index, text in enumerate(summary.pipeline_steps):
        _add(
            kind="stage",
            priority="must_cover",
            source_field="pipeline_steps",
            source_index=index,
            text=text,
        )
    if summary.project_goal and _normalize_text(summary.project_goal) not in {
        _normalize_text(summary.method_mainline),
        _normalize_text(summary.method_goal),
    }:
        _add(
            kind="component",
            priority="should_cover",
            source_field="project_goal",
            source_index=0,
            text=summary.project_goal,
        )
    for index, text in enumerate(summary.module_roles):
        _add(
            kind="component",
            priority="should_cover",
            source_field="module_roles",
            source_index=index,
            text=text,
            paths=_paths_from_module_role(text),
        )
    for index, text in enumerate(summary.key_building_blocks):
        _add(
            kind="component",
            priority="should_cover",
            source_field="key_building_blocks",
            source_index=index,
            text=text,
        )
    for index, text in enumerate(summary.story_order):
        _add(
            kind="organization",
            priority="preference",
            source_field="story_order",
            source_index=index,
            text=text,
            organization_preference=text,
        )
    for index, text in enumerate(summary.design_intents):
        _add(
            kind="rationale_check",
            priority="verify_only",
            source_field="design_intents",
            source_index=index,
            text=text,
        )
    for index, text in enumerate(summary.innovation_claims):
        _add(
            kind="high_risk_claim",
            priority="verify_only",
            source_field="innovation_claims",
            source_index=index,
            text=text,
        )
    for index, text in enumerate(summary.potential_mismatches):
        _add(
            kind="mismatch_check",
            priority="verify_only",
            source_field="potential_mismatches",
            source_index=index,
            text=text,
        )

    relations = _build_relations(obligations)
    return IntentObligationGraphV2(
        project_goal=summary.project_goal,
        method_goal=summary.method_goal,
        implementation_scope=summary.implementation_scope,
        obligations=obligations,
        relations=relations,
    )


# ---------------------------------------------------------------------------
# Author story spine
# ---------------------------------------------------------------------------


def _story_role_for_kind(kind: str) -> str:
    """Map an obligation kind onto the story node role vocabulary.

    The mapping is project-agnostic and deterministic: ``method_mainline``
    and ``stage`` are algorithm steps, ``component`` is setup, design
    rationale is motivation, innovation claims are evaluation, and declared
    potential mismatches are limitation nodes.
    """

    return {
        "method_mainline": "algorithm_step",
        "stage": "algorithm_step",
        "component": "setup",
        "organization": "setup",
        "rationale_check": "motivation",
        "high_risk_claim": "evaluation",
        "mismatch_check": "limitation",
    }.get(kind, "algorithm_step")


def build_story_spine_from_intent_graph(
    intent_graph: IntentObligationGraphV2,
    *,
    claim_set: Any | None = None,
    evidence_lane: MethodEvidenceLane = "author_intent_unverified",
) -> list[AuthorStoryNodeV1]:
    """Compile the author story spine from the typed intent graph.

    The spine preserves the author's own order of presentation (obligation
    order and the ``organization`` obligations carry ``story_order`` text).
    It is the organization authority for the Architect; it never claims
    repository support.  ``evidence_lane`` defaults to
    ``author_intent_unverified``; the projection layer refines it later with
    actual claim/completeness evidence.  ``linked_claim_ids`` are filled from
    the optional claim set through exact ``covers_obligation_ids`` members.
    """

    if not intent_graph.obligations:
        return []
    claims_by_obligation: dict[str, list[str]] = {}
    if claim_set is not None:
        for claim in getattr(claim_set, "claims", ()):
            for obligation_id in getattr(claim, "covers_obligation_ids", ()) or ():
                claims_by_obligation.setdefault(str(obligation_id), []).append(
                    str(claim.claim_id)
                )
    nodes: list[AuthorStoryNodeV1] = []
    for index, obligation in enumerate(intent_graph.obligations, start=1):
        statement = _clean(obligation.author_text)
        if not statement:
            continue
        title = " ".join(statement.split())[:96] or f"Story point {index}"
        role = _story_role_for_kind(obligation.kind)
        nodes.append(AuthorStoryNodeV1(
            story_node_id=f"story:{obligation.obligation_id}",
            title=title,
            author_statement=statement,
            intended_role=role,  # type: ignore[arg-type]
            source_refs=(
                f"intent_graph_v2:{obligation.obligation_id}",
                f"author_field:{obligation.source_field}",
            ),
            linked_obligation_ids=(obligation.obligation_id,),
            linked_claim_ids=tuple(dict.fromkeys(
                claims_by_obligation.get(obligation.obligation_id, ())
            )),
            evidence_lane=evidence_lane,
            notes=(
                (
                    f"kind={obligation.kind}; priority={obligation.priority}"
                ),
            ),
        ))
    return nodes


def _build_relations(
    obligations: list[IntentObligationV2],
) -> list[IntentObligationRelationV2]:
    """Build precedence + support relations mirroring the V1 structure."""

    stage_ids = [o.obligation_id for o in obligations if o.kind == "stage"]
    organization_ids = [o.obligation_id for o in obligations if o.kind == "organization"]
    relations: list[IntentObligationRelationV2] = []
    for sequence in (stage_ids, organization_ids):
        for source, target in zip(sequence, sequence[1:]):
            relations.append(IntentObligationRelationV2(
                source_obligation_id=source,
                target_obligation_id=target,
                relation="precedes",
            ))
    mainline = next((o.obligation_id for o in obligations if o.kind == "method_mainline"), "")
    if mainline:
        for stage_id in stage_ids:
            relations.append(IntentObligationRelationV2(
                source_obligation_id=stage_id,
                target_obligation_id=mainline,
                relation="supports",
            ))
    return relations


# ---------------------------------------------------------------------------
# Comparison helpers (for tests and alignment)
# ---------------------------------------------------------------------------


def typed_targets_signature(
    obligations: list[IntentObligationV2],
) -> frozenset[tuple[str, frozenset[str], frozenset[str], frozenset[str]]]:
    """Return a paraphrase-invariant signature of an obligation set.

    The signature is the set of ``(kind, predicate_set, relation_set,
    condition_set)`` tuples extracted from every typed target.  Two
    author YAMLs that compile to the same signature are considered to
    express the same semantic intent, regardless of wording, language or
    stage order.  Used by the R5.4 paraphrase / multilingual tests.
    """

    signature: set[tuple[str, frozenset[str], frozenset[str], frozenset[str]]] = set()
    for obligation in obligations:
        if not obligation.typed_behavior_targets:
            signature.add((obligation.kind, frozenset(), frozenset(), frozenset()))
            continue
        for target in obligation.typed_behavior_targets:
            signature.add((
                obligation.kind,
                frozenset(target.desired_predicates),
                frozenset(target.required_relations),
                frozenset(target.conditions),
            ))
    return frozenset(signature)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clean(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = _clean(value)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


def _digest_payload(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _stable_id(prefix: str, *parts: str) -> str:
    material = "\u241F".join(str(part) for part in parts if part)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


__all__ = [
    "INTENT_CONCEPTS",
    "IntentConceptV1",
    "IntentObligationGraphV2",
    "IntentObligationRelationV2",
    "IntentObligationV2",
    "OBLIGATION_KINDS_V2",
    "OBLIGATION_PRIORITIES_V2",
    "build_story_spine_from_intent_graph",
    "compile_intent_obligation_graph_v2",
    "typed_targets_signature",
]
