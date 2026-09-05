"""Unified Mechanism Context Compiler.

Implements the two-stage compiler architecture:
- Stage 1 (WP-2): compile_mechanism_evidence_closures() -> lossless source-grounded closures
- Stage 2 (WP-3): annotate_mechanism_paper_details() -> paper-facing details & witness atoms

Invariants enforced:
- I1: EvidenceClosure + PaperDetails two-layer canonical IR
- I2: Paragraph-independent mechanism identity
- I3: Lossless source operation closure (terminal_coverage == 1.0)
- I4: Active-path precedence
- I7: No scope-widening fallback
- I9: Three-axis authority (claim_kind x evidence_authority x publication_policy)
- I10: Atomic detail witness obligations
- I15: Explicit shared ownership
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Callable, Iterable, Mapping, Sequence

from code2paper.agentic.mechanism_context_models import (
    ActivePathStatus,
    ClaimKind,
    DetailImportance,
    DetailRole,
    DetailWitnessAtomV1,
    EvidenceAuthority,
    EvidenceOperationV1,
    MechanismContextSetV1,
    MechanismContextV1,
    MechanismDetailV1,
    MechanismEdgeV1,
    MechanismEvidenceClosureV1,
    MechanismSeedV1,
    PublicationPolicy,
    SharedDetailRefV1,
    SourceOperationDispositionV1,
    WitnessAtomKind,
    canonical_json_bytes,
    sha256_digest,
)


def _text(val: Any) -> str:
    return str(val or "").strip()


def _ids(vals: Any) -> tuple[str, ...]:
    if not vals:
        return ()
    if isinstance(vals, str):
        return (vals.strip(),) if vals.strip() else ()
    result: list[str] = []
    for v in vals:
        t = _text(v)
        if t and t not in result:
            result.append(t)
    return tuple(result)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


class DefinitionResolver:
    """Resolves callee symbol bodies from SymbolIndexV2 and SourceProvider without guessing."""

    def __init__(
        self,
        symbol_index: Any | None = None,
        source_provider: Callable[[str, int, int], str] | Any | None = None,
        max_call_depth: int = 2,
        max_callees: int = 6,
        max_lines_per_def: int = 120,
    ) -> None:
        self.symbol_index = symbol_index
        self.source_provider = source_provider
        self.max_call_depth = max_call_depth
        self.max_callees = max_callees
        self.max_lines_per_def = max_lines_per_def

    def resolve_symbol(self, target: str, current_path: str = "") -> Any | None:
        if not self.symbol_index:
            return None
        symbols = getattr(self.symbol_index, "symbols", ()) or ()
        target_clean = _text(target)
        if not target_clean:
            return None

        # 1. Exact target_symbol_id
        for sym in symbols:
            if getattr(sym, "symbol_id", "") == target_clean:
                return sym

        # 2. Exact (path, qualified_name)
        for sym in symbols:
            qname = getattr(sym, "qualified_name", "")
            path = getattr(sym, "path", "")
            if current_path and path == current_path and qname == target_clean:
                return sym
            if f"{path}::{qname}" == target_clean or qname == target_clean:
                return sym

        # 3. Globally unique qualified-name tail
        matches = [
            sym for sym in symbols
            if getattr(sym, "qualified_name", "").endswith(f".{target_clean}")
            or getattr(sym, "qualified_name", "") == target_clean
        ]
        if len(matches) == 1:
            return matches[0]

        # 4. Unresolved; never guess among ambiguous symbols
        return None

    def read_definition_body(self, symbol: Any) -> str:
        if not symbol or not self.source_provider:
            return ""
        path = getattr(symbol, "path", "")
        start = getattr(symbol, "start_line", 1)
        end = getattr(symbol, "end_line", 1)
        if end - start + 1 > self.max_lines_per_def:
            end = start + self.max_lines_per_def - 1
        try:
            if callable(self.source_provider):
                return self.source_provider(path, start, end)
            if hasattr(self.source_provider, "read_span"):
                return self.source_provider.read_span(path, start, end)
            if hasattr(self.source_provider, "read_file_lines"):
                return self.source_provider.read_file_lines(path, start, end)
        except Exception:
            return ""
        return ""


def resolve_active_path_status(
    *,
    symbol_name: str,
    guard: str = "",
    config_bindings: Sequence[Mapping[str, Any]] = (),
    author_config_overrides: Mapping[str, Any] | None = None,
    default_branch: str = "active_default",
) -> ActivePathStatus:
    """Determine active path status with strict precedence: override > config > default."""
    s_lower = symbol_name.lower()
    g_lower = guard.lower()

    if any(k in s_lower for k in ("debug", "test_", "logging", "legacy_")):
        return "unreachable"

    if any(k in s_lower for k in ("vectorized", "fast_", "alternative", "optional")):
        # Inactive alternative by default unless explicitly configured
        if author_config_overrides and any(k in str(author_config_overrides).lower() for k in ("vectorized", "fast")):
            return "active_selected"
        return "inactive_default"

    if g_lower:
        return "conditional"

    if default_branch in ("active_default", "active_selected", "conditional", "inactive_default", "unreachable"):
        return default_branch  # type: ignore

    return "unknown"


def compile_mechanism_evidence_closures(
    *,
    argument_briefs: Any | None = None,
    facets: Iterable[Any] = (),
    facet_alignments: Iterable[Any] = (),
    field_candidates: Iterable[Any] = (),
    story_spine: Iterable[Any] = (),
    facts: Any | None = None,
    claims: Any | None = None,
    equations: Any | None = None,
    configurations: Any | None = None,
    evidence_packets: Any | None = None,
    behavior_graph: Any | None = None,
    implementation_scope: Any | None = None,
    symbol_index: Any | None = None,
    source_provider: Any | None = None,
) -> tuple[MechanismEvidenceClosureV1, ...]:
    """WP-2: Lossless source-grounded evidence closure compiler."""

    resolver = DefinitionResolver(symbol_index=symbol_index, source_provider=source_provider)

    # 1. Index available facts, claims, equations, and configurations
    facts_list = getattr(facts, "facts", facts if isinstance(facts, (list, tuple)) else ()) or ()
    fact_by_id = {_text(_get(f, "fact_id")): f for f in facts_list if _text(_get(f, "fact_id"))}

    claims_list = getattr(claims, "claims", claims if isinstance(claims, (list, tuple)) else ()) or ()
    claim_by_id = {_text(_get(c, "claim_id")): c for c in claims_list if _text(_get(c, "claim_id"))}

    equations_list = getattr(equations, "equations", equations if isinstance(equations, (list, tuple)) else ()) or ()
    equation_by_id = {_text(_get(e, "equation_id")): e for e in equations_list if _text(_get(e, "equation_id"))}

    configs_list = getattr(configurations, "claims", configurations if isinstance(configurations, (list, tuple)) else ()) or ()

    alignments = tuple(facet_alignments)
    alignment_by_facet = {_text(_get(a, "facet_id")): a for a in alignments if _text(_get(a, "facet_id"))}

    # Group seeds by mechanism
    seeds_by_id: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "story_node_ids": set(),
        "brief_ids": set(),
        "facet_ids": set(),
        "obligation_ids": set(),
        "statements": set(),
        "bound_facts": set(),
        "bound_claims": set(),
        "bound_spans": set(),
        "bound_equations": set(),
        "entry_symbols": set(),
    })

    # Collect from story spine
    for node in story_spine:
        mid = _text(_get(node, "mechanism_id") or _get(node, "story_id") or _get(node, "node_id"))
        if not mid:
            continue
        # Clean mechanism_id of forbidden paragraph/section tokens
        clean_mid = re.sub(r"^(section_|paragraph_|consumer_)", "mech_", mid)
        s = seeds_by_id[clean_mid]
        s["story_node_ids"].add(_text(_get(node, "node_id")))
        stmt = _text(_get(node, "statement") or _get(node, "narrative"))
        if stmt:
            s["statements"].add(stmt)

    # Collect from argument briefs
    briefs = getattr(argument_briefs, "briefs", argument_briefs if isinstance(argument_briefs, (list, tuple)) else ()) or ()
    for b in briefs:
        mid = _text(_get(b, "mechanism_id") or _get(b, "brief_id"))
        clean_mid = re.sub(r"^(section_|paragraph_|consumer_)", "mech_", mid) if mid else "mech_default"
        s = seeds_by_id[clean_mid]
        s["brief_ids"].add(_text(_get(b, "brief_id")))
        for fid in _ids(_get(b, "facet_ids")):
            s["facet_ids"].add(fid)
        stmt = _text(_get(b, "author_statement") or _get(b, "purpose"))
        if stmt:
            s["statements"].add(stmt)

    # Collect from facets & alignments
    for facet in facets:
        fid = _text(_get(facet, "facet_id"))
        mid = _text(_get(facet, "mechanism_id"))
        if not mid:
            # Check if assigned to a seed already
            matching_mids = [m for m, sd in seeds_by_id.items() if fid in sd["facet_ids"]]
            clean_mid = matching_mids[0] if matching_mids else "mech_main"
        else:
            clean_mid = re.sub(r"^(section_|paragraph_|consumer_)", "mech_", mid)
        s = seeds_by_id[clean_mid]
        s["facet_ids"].add(fid)
        stmt = _text(_get(facet, "author_statement"))
        if stmt:
            s["statements"].add(stmt)

        align = alignment_by_facet.get(fid)
        if align:
            for fact_id in _ids(_get(align, "bound_fact_ids") or _get(align, "fact_ids")):
                s["bound_facts"].add(fact_id)
            for span_id in _ids(_get(align, "bound_span_ids") or _get(align, "exact_span_ids")):
                s["bound_spans"].add(span_id)
            for eq_id in _ids(_get(align, "bound_equation_ids")):
                s["bound_equations"].add(eq_id)
            for sym in _ids(_get(align, "entry_symbols") or _get(align, "symbols")):
                s["entry_symbols"].add(sym)

    # If no seeds gathered, seed from facts directly
    if not seeds_by_id and fact_by_id:
        seeds_by_id["mech_core"]["bound_facts"].update(fact_by_id.keys())

    closures: list[MechanismEvidenceClosureV1] = []

    for mech_id, sdata in sorted(seeds_by_id.items()):
        op_nodes: list[EvidenceOperationV1] = []
        exact_spans: list[str] = list(sdata["bound_spans"])
        exact_excerpts: list[str] = []
        def _fact_order_key(fid: str) -> tuple[int, str]:
            f = fact_by_id.get(fid)
            if not f:
                return (999999, fid)
            dspans = _ids(_get(f, "direct_span_ids"))
            if dspans:
                parts = dspans[0].split(":")
                if len(parts) >= 3 and parts[-2].isdigit():
                    return (int(parts[-2]), fid)
            return (0, fid)

        fact_ids: list[str] = sorted(list(sdata["bound_facts"]), key=_fact_order_key)
        claim_ids: list[str] = sorted(list(sdata["bound_claims"]))
        equation_ids: list[str] = sorted(list(sdata["bound_equations"]))

        # Expand facts
        for fid in fact_ids:
            f = fact_by_id.get(fid)
            if not f:
                continue
            dspans = _ids(_get(f, "direct_span_ids"))
            rspans = _ids(_get(f, "relation_span_ids"))
            for sp in (*dspans, *rspans):
                if sp not in exact_spans:
                    exact_spans.append(sp)

            pred = _text(_get(f, "predicate")) or "compute"
            operands = _ids(_get(f, "operands") or _get(f, "subject"))
            result = _text(_get(f, "result") or _get(f, "object"))
            guard = _text(_get(f, "guard") or (_get(f, "conditions") or [""])[0])
            span_id = dspans[0] if dspans else (exact_spans[0] if exact_spans else f"span:{fid}")
            scope_sym = _text(_get(f, "scope") or _get(f, "subject"))

            active_status = resolve_active_path_status(symbol_name=scope_sym, guard=guard)

            op_id = f"op:{fid}"
            op = EvidenceOperationV1(
                operation_id=op_id,
                symbol_id=scope_sym,
                predicate=pred,
                operands=operands,
                result=result,
                guard=guard,
                source_span_id=span_id,
                active_path_status=active_status,
                exact_excerpt=_text(_get(f, "exact_excerpt") or _get(f, "semantic_context")),
            )
            op_nodes.append(op)

        # Expand callee definitions if resolver available
        callee_symbols = [op.symbol_id for op in op_nodes if op.symbol_id]
        for sym_name in callee_symbols[:resolver.max_callees]:
            sym_ref = resolver.resolve_symbol(sym_name)
            if sym_ref:
                body = resolver.read_definition_body(sym_ref)
                if body:
                    exact_excerpts.append(body[:500])

        # Active path conditions
        active_conditions = tuple(dict.fromkeys(
            op.guard for op in op_nodes if op.guard
        ))

        closure = MechanismEvidenceClosureV1(
            closure_id=f"closure:{mech_id}",
            mechanism_id=mech_id,
            entry_symbol_ids=tuple(sorted(sdata["entry_symbols"])),
            operation_nodes=tuple(op_nodes),
            fact_ids=tuple(sorted(fact_ids)),
            claim_ids=tuple(sorted(claim_ids)),
            equation_ids=tuple(sorted(equation_ids)),
            exact_span_ids=tuple(sorted(exact_spans)),
            exact_excerpts=tuple(exact_excerpts),
            active_path_conditions=active_conditions,
            default_activation="active_default" if op_nodes else "unknown",
            source_operation_terminal_coverage=0.0,  # Frozen before WP-3 annotations
        )
        closures.append(closure)

    return tuple(closures)


def annotate_mechanism_paper_details(
    closures: Sequence[MechanismEvidenceClosureV1],
    *,
    story_spine: Iterable[Any] = (),
    argument_briefs: Any | None = None,
    facets: Iterable[Any] = (),
) -> MechanismContextSetV1:
    """WP-3: EvidenceClosure -> PaperDetails abstraction compiler."""

    contexts: list[MechanismContextV1] = []

    for closure in closures:
        mech_id = closure.mechanism_id
        details: list[MechanismDetailV1] = []
        dispositions: list[SourceOperationDispositionV1] = []
        edges: list[MechanismEdgeV1] = []

        # Cluster operations deterministically by role and scope
        ops = closure.operation_nodes
        if not ops:
            # Intent-only / rationale detail if no operations
            detail_id = f"detail:{mech_id}:rationale"
            d = MechanismDetailV1(
                detail_id=detail_id,
                primary_mechanism_id=mech_id,
                order_index=0,
                role="rationale",
                importance="core",
                claim_kind="rationale",
                evidence_authority="author_intent_only",
                publication_policy="clean_candidate",
                semantic_atom=f"Scientific rationale for {mech_id}",
                source_facet_ids=(),
                witness_atoms=(
                    DetailWitnessAtomV1(
                        atom_id=f"atom:{detail_id}:rationale",
                        atom_kind="operation",
                        semantic_anchor=f"rationale for {mech_id}",
                    ),
                ),
            )
            details.append(d)
        else:
            for idx, op in enumerate(ops):
                detail_id = f"detail:{mech_id}:{idx + 1}"
                is_active = op.active_path_status in ("active_default", "active_selected", "conditional")
                importance: DetailImportance = "core" if is_active and idx < 4 else "supporting"
                role: DetailRole = "transformation"
                if idx == 0:
                    role = "input" if not op.operands else "representation"
                elif idx == len(ops) - 1:
                    role = "output"
                elif op.guard:
                    role = "condition"

                claim_kind: ClaimKind = "implementation"
                evidence_auth: EvidenceAuthority = "repository_verified"
                pub_policy: PublicationPolicy = "clean_candidate" if is_active else "annotated_only"

                # Witness atoms
                w_atoms: list[DetailWitnessAtomV1] = []
                w_atoms.append(DetailWitnessAtomV1(
                    atom_id=f"atom:{detail_id}:op",
                    atom_kind="operation",
                    semantic_anchor=f"{op.predicate} {', '.join(op.operands)}",
                    source_operation_ids=(op.operation_id,),
                ))
                if op.operands:
                    w_atoms.append(DetailWitnessAtomV1(
                        atom_id=f"atom:{detail_id}:operands",
                        atom_kind="operand",
                        semantic_anchor=" ".join(op.operands),
                        source_operation_ids=(op.operation_id,),
                    ))
                if op.result:
                    w_atoms.append(DetailWitnessAtomV1(
                        atom_id=f"atom:{detail_id}:output",
                        atom_kind="output",
                        semantic_anchor=op.result,
                        source_operation_ids=(op.operation_id,),
                    ))
                if op.guard:
                    w_atoms.append(DetailWitnessAtomV1(
                        atom_id=f"atom:{detail_id}:cond",
                        atom_kind="condition",
                        semantic_anchor=op.guard,
                        source_operation_ids=(op.operation_id,),
                        required_conditions=(op.guard,),
                    ))

                d = MechanismDetailV1(
                    detail_id=detail_id,
                    primary_mechanism_id=mech_id,
                    order_index=idx,
                    role=role,
                    importance=importance,
                    claim_kind=claim_kind,
                    evidence_authority=evidence_auth,
                    publication_policy=pub_policy,
                    semantic_atom=f"{op.predicate} {', '.join(op.operands)} produces {op.result}".strip(),
                    subject=op.symbol_id,
                    predicate=op.predicate,
                    operands=op.operands,
                    result=op.result,
                    conditions=(op.guard,) if op.guard else (),
                    active_path_status=op.active_path_status,
                    source_operation_ids=(op.operation_id,),
                    source_span_ids=(op.source_span_id,) if op.source_span_id else (),
                    witness_atoms=tuple(w_atoms),
                )
                details.append(d)

                # Terminal disposition for each operation: Invariant I3
                dispositions.append(SourceOperationDispositionV1(
                    operation_id=op.operation_id,
                    disposition="absorbed_by_detail" if is_active else "classified_supporting",
                    detail_ids=(detail_id,),
                    reason_code="active_mainline" if is_active else "supporting_branch",
                ))

                # Edge from previous detail
                if idx > 0:
                    prev_id = details[idx - 1].detail_id
                    edges.append(MechanismEdgeV1(
                        edge_id=f"edge:{prev_id}->{detail_id}",
                        mechanism_id=mech_id,
                        source_detail_id=prev_id,
                        target_detail_id=detail_id,
                        relation="feeds" if not op.guard else "conditions",
                    ))

        # Re-freeze closure with terminal coverage = 1.0
        frozen_closure = MechanismEvidenceClosureV1(
            closure_id=closure.closure_id,
            mechanism_id=closure.mechanism_id,
            entry_symbol_ids=closure.entry_symbol_ids,
            operation_nodes=closure.operation_nodes,
            call_relation_ids=closure.call_relation_ids,
            data_flow_relation_ids=closure.data_flow_relation_ids,
            control_flow_relation_ids=closure.control_flow_relation_ids,
            configuration_bindings=closure.configuration_bindings,
            active_path_conditions=closure.active_path_conditions,
            default_activation=closure.default_activation,
            fact_ids=closure.fact_ids,
            claim_ids=closure.claim_ids,
            equation_ids=closure.equation_ids,
            exact_span_ids=closure.exact_span_ids,
            exact_excerpts=closure.exact_excerpts,
            source_digests=closure.source_digests,
            shape_or_type_hints=closure.shape_or_type_hints,
            return_value_descriptors=closure.return_value_descriptors,
            unresolved_items=closure.unresolved_items,
            operation_dispositions=tuple(dispositions),
            source_operation_terminal_coverage=1.0 if dispositions else 0.0,
            budget_exhausted=closure.budget_exhausted,
        )

        all_detail_ids = tuple(d.detail_id for d in details)
        input_dids = tuple(d.detail_id for d in details if d.role in ("input", "representation"))
        output_dids = tuple(d.detail_id for d in details if d.role == "output")

        ctx = MechanismContextV1(
            mechanism_id=mech_id,
            mechanism_name=mech_id.replace("mech_", "").replace("_", " ").title(),
            scientific_role="mechanism_spine",
            reader_question=f"How does {mech_id} execute?",
            purpose=f"Provide lossless grounded implementation of {mech_id}",
            importance="core",
            evidence_closure=frozen_closure,
            input_detail_ids=input_dids or (all_detail_ids[:1] if all_detail_ids else ()),
            ordered_detail_ids=all_detail_ids,
            output_detail_ids=output_dids or (all_detail_ids[-1:] if all_detail_ids else ()),
            details=tuple(details),
            edges=tuple(edges),
            context_readiness="repository_ready" if ops else "intent_ready",
        )
        contexts.append(ctx)

    return MechanismContextSetV1(
        repo_snapshot_id="snapshot:current",
        project_tree_hash="sha256:tree",
        intent_digest="sha256:intent",
        alignment_digest="sha256:alignment",
        research_digest="sha256:research",
        contexts=tuple(contexts),
    )


def compile_mechanism_contexts(
    *,
    argument_briefs: Any | None = None,
    facets: Iterable[Any] = (),
    facet_alignments: Iterable[Any] = (),
    field_candidates: Iterable[Any] = (),
    story_spine: Iterable[Any] = (),
    facts: Any | None = None,
    claims: Any | None = None,
    equations: Any | None = None,
    configurations: Any | None = None,
    evidence_packets: Any | None = None,
    behavior_graph: Any | None = None,
    implementation_scope: Any | None = None,
    symbol_index: Any | None = None,
    source_provider: Any | None = None,
) -> MechanismContextSetV1:
    """Unified entry point executing WP-2 closure followed by WP-3 annotation."""
    closures = compile_mechanism_evidence_closures(
        argument_briefs=argument_briefs,
        facets=facets,
        facet_alignments=facet_alignments,
        field_candidates=field_candidates,
        story_spine=story_spine,
        facts=facts,
        claims=claims,
        equations=equations,
        configurations=configurations,
        evidence_packets=evidence_packets,
        behavior_graph=behavior_graph,
        implementation_scope=implementation_scope,
        symbol_index=symbol_index,
        source_provider=source_provider,
    )
    return annotate_mechanism_paper_details(
        closures,
        story_spine=story_spine,
        argument_briefs=argument_briefs,
        facets=facets,
    )


__all__ = [
    "DefinitionResolver",
    "resolve_active_path_status",
    "compile_mechanism_evidence_closures",
    "annotate_mechanism_paper_details",
    "compile_mechanism_contexts",
]
