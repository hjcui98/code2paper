"""Autonomous Writer-callback fulfillment and section-resume loop.

The Writer emits ``WritingResearchRequestV1`` entries when a required move
lacks evidence.  The router already knows which lane owns each request; this
module adds the *production loop* that the product runner was missing:

- reads the persisted callback bundle after the first Writer run;
- executes open local-owned routes (repository / configuration /
  formalization) with a bounded, progress-driven research loop;
- writes digest-pinned, file-backed callback artifacts the resumed Writer
  can actually read (``artifact_preview``);
- fulfills the bundle and resumes only the affected sections;
- repeats until no local progress remains or the budget is exhausted;
- external author/literature/empirical requests stay in their explicit
  queues and never block local resume.

Nothing here fabricates completion: a request that finds no frozen repository
evidence stays pending, and the candidate prose remains caveated/reviewable.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.evidence_compiler_v3 import (
    CodeFactSetV1,
    load_code_facts_v1,
)
from code2paper.agentic.method_argument_models import (
    ConfigurationClaimSetV1,
    MethodSectionPlanV2,
    WritingResearchCallbackArtifactV1,
    WritingResearchCallbackBundleV1,
    WritingResearchRequestV1,
)
from code2paper.agentic.research_models import ResearchToolCallV1
from code2paper.agentic.research_tools import ResearchToolContext, execute_research_tool
from code2paper.agentic.writer_research_router import (
    execute_open_requests_for_routes,
)
from code2paper.agentic.publication_method_writer import (
    fulfill_writing_research_callbacks,
    run_publication_method_writer,
)


#: Lanes the local harness may fulfill.  Requests on any other lane are
#: external queues (author/literature/empirical) and stay pending here.
_LOCAL_OWNED_LANES: frozenset[str] = frozenset({
    "executable_hard",
    "configuration_resolved",
    "formal_derivation",
})

_SEED_STOPWORDS: frozenset[str] = frozenset({
    "the", "for", "and", "are", "was", "with", "what", "which", "find",
    "this", "that", "from", "into", "have", "has", "does", "is", "of",
    "it", "its", "on", "in", "to", "a", "an", "be", "by", "or", "how",
})


class WritingCallbackFulfillmentBudgetV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_callback_rounds: int = 3
    max_tool_turns_per_request: int = 8
    max_requests_per_round: int = 8
    max_artifacts_per_request: int = 3


class WritingCallbackFulfillmentResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rounds_attempted: int = 0
    local_requests_seen: int = 0
    local_requests_fulfilled: int = 0
    external_requests_seen: int = 0
    resumed_section_ids: tuple[str, ...] = Field(default_factory=tuple)
    stopped_reason: str = ""
    trace_path: str = ""


def _load_bundle(path: str | Path) -> WritingResearchCallbackBundleV1 | None:
    candidate = Path(path)
    if not str(path).strip() or not candidate.is_file():
        return None
    try:
        return WritingResearchCallbackBundleV1.model_validate_json(
            candidate.read_text(encoding="utf-8")
        )
    except (OSError, TypeError, ValueError):
        return None


def fulfill_and_resume_writing_callbacks(
    *,
    runtime: Any,
    out_root: Path,
    artifact_paths: dict[str, str],
    writer_paths: dict[str, str],
    llm_config: Any,
    budget: WritingCallbackFulfillmentBudgetV1 | None = None,
    llm_caller: Callable[..., Any] | None = None,
) -> tuple[dict[str, str], str, str, WritingCallbackFulfillmentResultV1]:
    """Run the bounded callback fulfillment/resume loop after a Writer run.

    Returns ``(writer_paths, writer_status, writer_blocked_reason, result)``.
    The loop stops when no open local-owned requests remain, a round produces
    no new validated artifacts, the Writer succeeds with no new local-owned
    open request, or the round budget is exhausted.
    """

    budget = budget or WritingCallbackFulfillmentBudgetV1()
    bundle_path = str(
        writer_paths.get("writing_research_callback_artifacts_v1")
        or artifact_paths.get("writing_research_callback_artifacts_v1")
        or ""
    )
    bundle = _load_bundle(bundle_path)
    if bundle is None:
        return (
            writer_paths,
            "incomplete",
            "",
            WritingCallbackFulfillmentResultV1(stopped_reason="no_callback_bundle"),
        )

    facts = _load_facts(artifact_paths)
    plan = _load_plan(artifact_paths)
    configurations = _load_configurations(artifact_paths)
    formalization = _load_formalization(artifact_paths)
    callback_root = Path(bundle_path).expanduser().resolve().parent

    result = WritingCallbackFulfillmentResultV1()
    trace_rows: list[dict[str, Any]] = []
    local_seen: set[str] = set()
    local_fulfilled: set[str] = set()
    external_seen: set[str] = set()
    resumed: set[str] = set()
    writer_status = "incomplete"
    writer_blocked_reason = ""
    provider = _BudgetedRepositoryCallbackProvider(
        runtime=runtime,
        facts=facts,
        plan=plan,
        callback_root=callback_root,
        budget=budget,
    )

    for round_index in range(1, budget.max_callback_rounds + 1):
        result = result.model_copy(update={"rounds_attempted": round_index})
        open_requests = [item for item in bundle.requests if item.status == "open"]
        if not open_requests:
            result = result.model_copy(update={"stopped_reason": "no_open_requests"})
            break
        local_requests = [
            item for item in open_requests
            if item.required_authority_lane in _LOCAL_OWNED_LANES
        ]
        external_requests = [
            item for item in open_requests
            if item.required_authority_lane not in _LOCAL_OWNED_LANES
        ]
        local_seen.update(item.request_id for item in local_requests)
        external_seen.update(item.request_id for item in external_requests)
        selected = local_requests[: budget.max_requests_per_round]
        if not selected:
            result = result.model_copy(update={"stopped_reason": "no_open_local_requests"})
            break

        artifacts = execute_open_requests_for_routes(
            selected,
            configuration_claims=configurations,
            formalization=formalization,
            repository_provider=provider,
        )
        if not artifacts:
            result = result.model_copy(update={"stopped_reason": "no_progress"})
            break
        if sum(len(items) for items in artifacts.values()) == 0:
            result = result.model_copy(update={"stopped_reason": "no_progress"})
            break

        try:
            bundle = fulfill_writing_research_callbacks(bundle_path, artifacts)
        except (OSError, TypeError, ValueError) as exc:
            result = result.model_copy(update={
                "stopped_reason": f"fulfillment_failed:{type(exc).__name__}",
            })
            break
        local_fulfilled.update(
            request_id for request_id in artifacts
        )
        resumed.update(bundle.resume_section_ids)
        trace_rows.append({
            "round": round_index,
            "fulfilled_request_ids": sorted(artifacts),
            "resume_section_ids": list(bundle.resume_section_ids),
        })

        merged_paths = {
            **artifact_paths,
            **writer_paths,
        }
        writer_result, writer_paths = run_publication_method_writer(
            out_root=out_root,
            artifact_paths=merged_paths,
            llm_config=llm_config,
            llm_caller=llm_caller,
            resume_section_ids=bundle.resume_section_ids,
            research_callback_artifacts=artifacts,
        )
        writer_status = getattr(writer_result, "status", "blocked")
        writer_blocked_reason = getattr(writer_result, "blocked_reason", "")
        bundle = _load_bundle(
            writer_paths.get("writing_research_callback_artifacts_v1", "")
            or bundle_path
        ) or bundle
        if writer_status == "success":
            remaining_local = [
                item for item in bundle.requests
                if item.status == "open"
                and item.required_authority_lane in _LOCAL_OWNED_LANES
            ]
            if not remaining_local:
                result = result.model_copy(update={"stopped_reason": "writer_success"})
                break

    else:
        result = result.model_copy(update={"stopped_reason": "budget_exhausted"})

    trace_path = ""
    if trace_rows:
        trace_path = str(
            Path(out_root) / "artifacts" / "research_tool_data"
            / "writing_callback_fulfillment_trace_v1.json"
        )
        _atomic_write_text(
            trace_path,
            json.dumps({"schema_version": "1.0", "rounds": trace_rows}, ensure_ascii=False, indent=2) + "\n",
        )
    result = result.model_copy(update={
        "local_requests_seen": len(local_seen),
        "local_requests_fulfilled": len(local_fulfilled),
        "external_requests_seen": len(external_seen),
        "resumed_section_ids": tuple(sorted(resumed)),
        "stopped_reason": result.stopped_reason or "completed",
        "trace_path": trace_path,
    })
    return writer_paths, writer_status, writer_blocked_reason, result


def _load_facts(artifact_paths: dict[str, str]) -> CodeFactSetV1 | None:
    value = artifact_paths.get("code_facts_v1", "")
    if not value or not Path(value).is_file():
        return None
    try:
        return load_code_facts_v1(value)
    except (OSError, TypeError, ValueError):
        return None


def _load_plan(artifact_paths: dict[str, str]) -> MethodSectionPlanV2 | None:
    value = artifact_paths.get("method_section_plan_v2", "")
    if not value or not Path(value).is_file():
        return None
    try:
        return MethodSectionPlanV2.model_validate_json(Path(value).read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return None


def _load_configurations(artifact_paths: dict[str, str]) -> ConfigurationClaimSetV1 | None:
    value = artifact_paths.get("configuration_claims_v1", "")
    if not value or not Path(value).is_file():
        return None
    try:
        return ConfigurationClaimSetV1.model_validate_json(Path(value).read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return None


def _load_formalization(artifact_paths: dict[str, str]) -> Any | None:
    value = artifact_paths.get("formalization_result_v1", "")
    if not value or not Path(value).is_file():
        return None
    try:
        from code2paper.agentic.formalization_agent import FormalizationResultV1

        return FormalizationResultV1.model_validate_json(
            Path(value).read_text(encoding="utf-8")
        )
    except (OSError, TypeError, ValueError):
        return None


def _atomic_write_text(path: str | Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(target)


class _BudgetedRepositoryCallbackProvider:
    """Local repository research for one callback request, under budget.

    Seeds the search from the request's exact question, candidate symbols and
    known facts; executes bounded tool turns through the frozen research tool
    context; de-duplicates by ``(tool_name, arguments, path_scope)``; and
    produces a file-backed, digest-pinned artifact only when frozen facts
    match the observed spans.  No matching evidence leaves the request
    pending.
    """

    def __init__(
        self,
        *,
        runtime: Any,
        facts: CodeFactSetV1 | None,
        plan: MethodSectionPlanV2 | None,
        callback_root: Path,
        budget: WritingCallbackFulfillmentBudgetV1,
    ) -> None:
        self.runtime = runtime
        self.facts = facts
        self.plan = plan
        self.callback_root = callback_root
        self.budget = budget
        self._ctx: ResearchToolContext | None = None
        self._seen_calls: set[tuple[str, str, tuple[str, ...]]] = set()

    def _tool_context(self) -> ResearchToolContext:
        if self._ctx is None:
            self._ctx = self.runtime.tool_context()
        return self._ctx

    def __call__(self, request: WritingResearchRequestV1) -> dict[str, Any] | None:
        self._seen_calls.clear()
        if self.facts is None:
            return None
        terms = self._seed_terms(request)
        obligation_id = self._obligation_id_for(request)
        repo_snapshot_id = self.runtime.repo_snapshot.snapshot_id
        observed_spans: set[str] = set()
        observed_refs: set[str] = set()
        consecutive_no_new = 0
        for turn in range(self.budget.max_tool_turns_per_request):
            tool_call = self._next_tool_call(
                terms=terms,
                observed_spans=observed_spans,
                observed_refs=observed_refs,
                obligation_id=obligation_id,
                repo_snapshot_id=repo_snapshot_id,
                turn=turn,
            )
            if tool_call is None:
                break
            observation = execute_research_tool(self._tool_context(), tool_call)
            if observation.status == "invalid_request":
                break
            new_spans = set(observation.exact_span_ids) - observed_spans
            new_refs = set(observation.result_refs) - observed_refs
            observed_spans.update(new_spans)
            observed_refs.update(new_refs)
            if not new_spans and not new_refs:
                if turn >= len(terms):
                    consecutive_no_new += 1
            else:
                consecutive_no_new = 0
            matched = self._matched_facts(observed_spans, observed_refs)
            if matched:
                return self._write_artifact(request, matched, observed_spans, observed_refs, obligation_id)
            if consecutive_no_new >= 2:
                break
        return None

    def _seed_terms(self, request: WritingResearchRequestV1) -> list[str]:
        # Symbol/term candidates come first and are the authoritative seed;
        # question tokens are only auxiliary search seeds and stay capped so
        # they never starve the read phases of the tool budget.
        terms: list[str] = []
        seen_lower: set[str] = set()

        def add(term: str) -> None:
            clean = str(term or "").strip().strip("`'\"()[]")
            if not clean or len(clean) < 2:
                return
            lowered = clean.lower()
            if lowered in _SEED_STOPWORDS or lowered in seen_lower:
                return
            seen_lower.add(lowered)
            terms.append(clean)

        for value in (
            *request.candidate_symbols_or_terms,
            *request.current_known_facts,
        ):
            for part in re.split(r"[\s,;:]+", str(value or "")):
                add(part)
        question = str(request.exact_question or "")
        for match in re.finditer(r"[A-Za-z_][A-Za-z0-9_.]{2,}", question):
            add(match.group(0))
        return terms[:10]

    def _obligation_id_for(self, request: WritingResearchRequestV1) -> str:
        if self.plan is not None:
            for unit in self.plan.argument_units:
                if unit.argument_unit_id == request.argument_unit_id:
                    if unit.source_obligation_ids:
                        return unit.source_obligation_ids[0]
                    break
        return f"callback:{request.request_id}"

    def _next_tool_call(
        self,
        *,
        terms: list[str],
        observed_spans: set[str],
        observed_refs: set[str],
        obligation_id: str,
        repo_snapshot_id: str,
        turn: int,
    ) -> ResearchToolCallV1 | None:
        ctx = self._tool_context()

        def make_call(
            tool_name: str,
            arguments: dict[str, Any],
            *,
            path_scope: tuple[str, ...] = (),
        ) -> ResearchToolCallV1 | None:
            signature = (
                tool_name,
                json.dumps(arguments, sort_keys=True),
                path_scope,
            )
            if signature in self._seen_calls:
                return None
            self._seen_calls.add(signature)
            return ResearchToolCallV1(
                tool_call_id=f"callback-tool-{tool_name}-{len(self._seen_calls)}",
                tool_name=tool_name,
                obligation_id=obligation_id,
                goal=f"Callback research for writer request on obligation {obligation_id}",
                repo_snapshot_id=repo_snapshot_id,
                path_scope=path_scope,
                arguments=arguments,
            )

        # Phase A: search symbols.  Capped so question-derived seeds can never
        # starve the read phases below.
        search_count = min(len(terms), 4)
        if turn < search_count:
            return make_call("search_symbols", {"query": terms[turn], "kind_filter": ()})

        # Phase B: read the source files whose names match the seeded terms
        # (a term like ``train`` must reach ``train.py`` even when the symbol
        # index only matched config refs).
        file_read_start = search_count
        file_read_count = min(4, len(terms))
        if file_read_start <= turn < file_read_start + file_read_count:
            term = terms[turn - file_read_start]
            files = [
                item.path
                for item in ctx.repo_snapshot.included_files
                if item.kind == "file"
                and item.path.endswith((".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs"))
                and _path_matches_term(item.path, term)
            ]
            for path in files[:3]:
                call = make_call(
                    "read_code_span",
                    {"path": path, "start_line": 1, "end_line": 0},
                    path_scope=(path,),
                )
                if call is not None:
                    return call

        # Phase C: ref-driven reads — the search refs carry exact
        # ``path:line`` anchors, so read those windows directly (the fastest
        # path to real spans), then read_symbol for symbol refs.
        refs = sorted(observed_refs)
        ref_start = file_read_start + file_read_count
        ref_index = turn - ref_start
        if refs and ref_index < len(refs) * 2:
            reference = refs[ref_index % len(refs)]
            path, line = _parse_path_line_reference(reference)
            if path and line and ref_index < len(refs):
                call = make_call(
                    "read_code_span",
                    {
                        "path": path,
                        "start_line": max(1, line - 3),
                        "end_line": line + 3,
                    },
                    path_scope=(path,),
                )
                if call is not None:
                    return call
            symbol_path, symbol = _parse_symbol_reference(reference, ctx)
            if symbol_path and symbol:
                call = make_call(
                    "read_symbol",
                    {"path": symbol_path, "symbol": symbol},
                )
                if call is not None:
                    return call
        if refs and ref_index >= len(refs) * 2 and ref_index < len(refs) * 3:
            _path, symbol = _parse_symbol_reference(refs[ref_index % len(refs)], ctx)
            if symbol:
                return make_call("find_references", {"symbol": symbol, "import_only": False})
        return None

    def _matched_facts(
        self,
        observed_spans: set[str],
        observed_refs: set[str],
    ) -> list[Any]:
        matched: list[Any] = []
        for fact in self.facts.facts:
            if any(
                _span_ids_overlap(str(item), observed_spans)
                for item in (getattr(fact, "direct_span_ids", ()) or ())
            ):
                matched.append(fact)
                continue
            if any(
                str(ref) in observed_refs
                for ref in (
                    f"fact:{fact.fact_id}",
                    f"span:{fact.fact_id}",
                )
            ):
                matched.append(fact)
        return matched[: self.budget.max_artifacts_per_request]

    def _write_artifact(
        self,
        request: WritingResearchRequestV1,
        matched_facts: list[Any],
        observed_spans: set[str],
        observed_refs: set[str],
        obligation_id: str,
    ) -> dict[str, Any]:
        fact_refs = tuple(fact.fact_id for fact in matched_facts)
        span_ids = tuple(dict.fromkeys(
            span_id for fact in matched_facts for span_id in fact.direct_span_ids
        ))
        relation_ids = tuple(dict.fromkeys(
            relation_id for fact in matched_facts for relation_id in fact.relation_evidence_ids
        ))
        summary = _fact_summary_for_writer(matched_facts)
        payload = {
            "schema_version": "1.0",
            "request_id": request.request_id,
            "section_id": request.section_id,
            "argument_unit_id": request.argument_unit_id,
            "authority_lane": "executable_hard",
            "summary_for_writer": summary,
            "matched_fact_ids": list(fact_refs),
            "matched_span_ids": list(span_ids),
            "matched_relation_ids": list(relation_ids),
            "tool_observation_refs": sorted(observed_refs)[:12],
            "remaining_limits": [
                f"The repository evidence covers only the matched facts; the "
                "remaining parts of this request stay unresolved for review.",
            ],
            "source_snapshot_id": self.runtime.repo_snapshot.snapshot_id,
            "project_tree_hash": self.runtime.repo_snapshot.project_tree_hash,
            "obligation_id": obligation_id,
        }
        artifact_id = "writing-callback:" + request.request_id + ":" + _short_digest(payload)
        artifact_dir = (
            self.callback_root.parent
            / "research_tool_data" / "writing_callbacks" / request.request_id
        )
        artifact_path = artifact_dir / f"{artifact_id}.json"
        _atomic_write_text(artifact_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        digest = "sha256:" + hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        reference = os_path_relative(artifact_path, self.callback_root)
        return {
            "artifact_id": artifact_id,
            "request_id": request.request_id,
            "section_id": request.section_id,
            "argument_unit_id": request.argument_unit_id,
            "authority_lane": "executable_hard",
            "artifact_ref": reference,
            "artifact_digest": digest,
            "validated": True,
        }


def _fact_summary_for_writer(facts: list[Any]) -> str:
    sentences: list[str] = []
    for fact in facts:
        subject = str(getattr(fact, "subject", "") or "").replace("_", " ").strip()
        predicate = str(getattr(fact, "predicate", "") or "").replace("_", " ").strip()
        obj = getattr(fact, "object", None)
        if isinstance(obj, list):
            obj = ", ".join(str(item) for item in obj[:3])
        sentences.append(
            f"Repository evidence shows that {subject} {predicate} {obj or '(an operand)'}."
        )
    return " ".join(sentences) or "Repository evidence matched the requested scope."


def _span_ids_overlap(span_id: str, observed_spans: set[str]) -> bool:
    """True when ``span_id`` overlaps any observed span on the same file.

    Reads return whole-file or wide ranges while facts pin exact operation
    ranges; exact-id equality would miss every genuine hit.  Parse
    ``span:<path>:<start>:<end>`` and compare numeric ranges per path.
    """

    def parsed(value: str) -> tuple[str, int, int] | None:
        parts = str(value or "").split(":")
        if len(parts) != 4 or parts[0] != "span":
            return None
        try:
            return parts[1], int(parts[2]), int(parts[3])
        except ValueError:
            return None

    target = parsed(span_id)
    if target is None:
        return span_id in observed_spans
    path, start, end = target
    for observed in observed_spans:
        other = parsed(observed)
        if other is None:
            continue
        if other[0] != path:
            continue
        if other[1] <= end and start <= other[2]:
            return True
    return False


def _path_matches_term(path: str, term: str) -> bool:
    normalized = str(term or "").strip().strip("`'\"()[]")
    if not normalized:
        return False
    stem = Path(path).name
    return (
        normalized in path
        or normalized.lower() in stem.lower()
        or normalized.split(".")[0].lower() in stem.lower()
    )


def _parse_path_line_reference(reference: str) -> tuple[str, int]:
    """Parse ``symbol:<path>:<symbol>:<line>`` refs into (path, line)."""

    raw = str(reference or "").strip()
    if not raw.startswith("symbol:"):
        return "", 0
    parts = raw[len("symbol:"):].split(":")
    if len(parts) >= 3 and parts[-1].isdigit():
        return ":".join(parts[:-2]), int(parts[-1])
    return "", 0


def _parse_symbol_reference(
    reference: str,
    ctx: ResearchToolContext,
) -> tuple[str, str]:
    raw = str(reference or "").strip()
    if raw.startswith("symbol:"):
        raw = raw[len("symbol:"):]
    if raw.startswith("span:"):
        return "", ""
    if "::" in raw:
        path, _, symbol = raw.partition("::")
        return path, symbol.split(".")[0]
    if raw.startswith("module:"):
        return "", ""
    path, _, symbol = raw.rpartition(".")
    if path and symbol and not symbol.startswith("_"):
        return path, symbol
    return "", raw


def os_path_relative(path: Path, base: Path) -> str:
    return os.path.relpath(str(path.resolve()), str(base.resolve()))


def _short_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:12]


__all__ = [
    "WritingCallbackFulfillmentBudgetV1",
    "WritingCallbackFulfillmentResultV1",
    "fulfill_and_resume_writing_callbacks",
]
