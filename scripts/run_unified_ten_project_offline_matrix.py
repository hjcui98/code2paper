#!/usr/bin/env python3
"""Run the unified-context reconstruction and admission matrix offline.

This entry point is deliberately a compiler/admission harness only.  It loads
frozen repository/research artifacts, rebuilds the V2 archive, worksets and
phase plans, and writes a per-project plus aggregate report.  It has no LLM
caller, provider client, network operation, or live-run fallback.

Projects are supplied as ``<project-id>=<artifact-root>``.  The root may be a
frozen/replay root or an ``artifacts`` directory; the loader accepts the
tracked historical layouts so the matrix can compare projects without
copying or mutating their inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from code2paper.agentic.behavior_graph import SymbolIndexV2  # noqa: E402
from code2paper.agentic.equation_claims import (  # noqa: E402
    load_equation_claims,
)
from code2paper.agentic.evidence_compiler_v3 import (  # noqa: E402
    load_atomic_claims_v3_or_v2,
    load_code_facts_v1,
)
from code2paper.agentic.formalization_agent import (  # noqa: E402
    MechanismFormulaObligationV1,
    compile_mechanism_formula_obligations,
    load_mechanism_formula_obligations_v1_payload,
)
from code2paper.agentic.mechanism_context_compiler import (  # noqa: E402
    build_current_behavior_graph,
    compile_mechanism_contexts,
    validate_mechanism_context_completeness,
    validate_mechanism_context_structural_gates,
)
from code2paper.agentic.mechanism_context_models import (  # noqa: E402
    MechanismContextSetV1,
    canonical_json_bytes,
    load_mechanism_context_set_v1_payload,
    sha256_digest,
)
from code2paper.agentic.method_architect import build_narrative_plan_v3  # noqa: E402
from code2paper.agentic.method_argument_models import MethodSectionPlanV2  # noqa: E402
from code2paper.agentic.method_product_models import AuthorStoryNodeV1  # noqa: E402
from code2paper.agentic.repo_snapshot import (  # noqa: E402
    RepoSnapshot,
    read_verified_snapshot_sources,
    repo_snapshot_identity_digest,
)
from code2paper.agentic.research_models import (  # noqa: E402
    ImplementationScopeV1,
    ResearchAgendaV1,
)
from code2paper.agentic.repository_authoring_artifacts import (  # noqa: E402
    REPOSITORY_AUTHORING_BUILDER_VERSION,
    rebuild_repository_authoring_artifacts,
    repository_authoring_identity_payload,
)
from code2paper.agentic.source_inventory import (  # noqa: E402
    RepositorySourceManifestV1,
    normalize_source_path,
    source_manifest_snapshot_failures,
)
from code2paper.agentic.unified_context_compiler import (  # noqa: E402
    read_unified_extra_roles,
    BUDGET_FIELD_BY_ENV,
    UnifiedCompilerError,
    bind_formula_obligation_page_owners,
    build_consumer_invocation_plan_v1,
    build_consumer_workset_manifest_v2,
    build_run_invocation_budget_envelope_v1,
    build_unified_context_archive_v2,
    evaluate_unified_live_admission_v1,
    extend_writer_worksets_from_narrative_plan,
    fit_narrative_plan_to_page_budget,
    read_unified_budget_profile,
)
from code2paper.agentic.unified_context_models import (  # noqa: E402
    UNIFIED_INVOCATION_BUDGET_MISSING,
)


_SOURCE_NAMES = (
    ("repo_snapshot_v2", ("repo_snapshot_v2", "repo_snapshot")),
    ("symbol_index_v2", ("symbol_index_v2", "symbol_index")),
    (
        "implementation_scope_v1",
        ("implementation_scope_v1", "implementation_scope"),
    ),
    (
        "repository_source_manifest_v1",
        ("repository_source_manifest_v1", "repository_source_manifest"),
    ),
    (
        "repository_authoring_artifacts_v1",
        ("repository_authoring_artifacts_v1",),
    ),
)

_RESEARCH_NAMES = {
    "context_set": ("mechanism_context_set_v1",),
    "formula_obligations": ("mechanism_formula_obligations_v1",),
    "narrative_plan": ("narrative_plan_v3",),
    "section_plan": ("method_section_plan_v2",),
    "intent_graph": ("intent_obligation_graph_v2",),
    "research_agenda": ("research_agenda_v1",),
    "equations": ("equation_claims_v1",),
    "claims": ("atomic_claims_v3", "atomic_claims_v3_v3"),
    "facts": ("code_facts_v1", "code_facts_v1_v3"),
}

_CONTEXT_REBUILD_NAMES = {
    "argument_briefs": ("method_argument_briefs_v1",),
    "facets": ("method_argument_facets_v1",),
    "facet_alignments": ("facet_evidence_alignments_v1",),
    "field_candidates": ("publication_field_candidates_v1",),
    "story_spine": (
        "author_story_spine_v1",
        "story_spine",
        "method_story_nodes_v1",
    ),
    "configurations": ("configuration_claims_v1",),
    "evidence_packets": ("evidence_packets_v3",),
    "behavior_graph": ("behavior_graph_v1",),
}

def _digest_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _digest_file(path: Path) -> str:
    return _digest_bytes(path.read_bytes())


def _artifact_path(root: Path, names: tuple[str, ...]) -> Path | None:
    candidates: list[Path] = []
    for name in names:
        filename = name if name.endswith(".json") else f"{name}.json"
        candidates.extend((
            root / filename,
            root / "artifacts" / "06_authoring" / filename,
            root / "artifacts" / filename,
            root / "artifacts" / "research_product" / filename,
            root / "06_authoring" / filename,
        ))
    return next((path for path in candidates if path.is_file()), None)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_mapping(path: Path) -> Mapping[str, Any]:
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def _resolve_capability_profile_path(profile_path: Path, raw_value: str) -> Path:
    """Resolve the non-secret capability-profile reference in an env file."""

    value = str(raw_value or "").strip().strip("'").strip('"')
    marker = "${_CODE2PAPER_PROFILE_DIR}"
    if marker in value:
        value = value.replace(marker, str(profile_path.parent))
    elif value.startswith("$_CODE2PAPER_PROFILE_DIR"):
        value = value.replace("$_CODE2PAPER_PROFILE_DIR", str(profile_path.parent), 1)
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        profile_relative = profile_path.parent / candidate
        if profile_relative.is_file():
            candidate = profile_relative
        else:
            candidate = Path.cwd() / candidate
    return candidate


def _profile_values(path: Path | None) -> tuple[dict[str, str], str, str, int]:
    """Read only non-secret profile metadata and numeric budget settings."""

    if path is None or not path.is_file():
        return {}, "", "", 0
    raw_bytes = path.read_bytes()
    values: dict[str, str] = {}
    if path.suffix.casefold() == ".json":
        payload = _read_mapping(path)
        for key, value in payload.items():
            if isinstance(value, (str, int, float)):
                values[str(key)] = str(value)
    else:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            line = line.removeprefix("export ").strip()
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            # Shell expansion is intentionally not evaluated.  The capability
            # profile is a tracked, non-secret path and is the one safe
            # exception needed to read qwen36's profile-relative reference.
            if key and value and ("$" not in value or key == "CODE2PAPER_LLM_CAPABILITY_PROFILE"):
                values[key] = value
    model = (
        values.get("CODE2PAPER_LLM_MODEL")
        or values.get("CODE2PAPER_DEFAULT_LLM_MODEL")
        or values.get("model")
        or ""
    )
    context_tokens = 0
    for key in (
        "CODE2PAPER_MODEL_CONTEXT_TOKENS",
        "CODE2PAPER_LLM_CONTEXT_TOKENS",
        "max_model_len",
    ):
        try:
            context_tokens = int(values.get(key, "0") or 0)
        except (TypeError, ValueError):
            context_tokens = 0
        if context_tokens > 0:
            break
    capability_path = values.get("CODE2PAPER_LLM_CAPABILITY_PROFILE", "")
    if context_tokens <= 0 and capability_path:
        candidate = _resolve_capability_profile_path(path, capability_path)
        if candidate.is_file():
            try:
                capability = _read_mapping(candidate)
                context_tokens = int(capability.get("max_model_len", 0) or 0)
                model = model or str(capability.get("model", "") or "")
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                context_tokens = 0
    return values, _digest_bytes(raw_bytes), model, context_tokens


def _parse_budget(values: Mapping[str, str]) -> tuple[dict[str, int], tuple[str, ...]]:
    """Read the same declared contract the product compiler reads.

    The matrix keeps no second profile map: an undeclared field fails here and
    in production with the identical failure code.
    """

    budget = read_unified_budget_profile(values)
    budget.update(read_unified_extra_roles(values))
    failures = [
        f"{UNIFIED_INVOCATION_BUDGET_MISSING}:{env_name}"
        for env_name, field_name in BUDGET_FIELD_BY_ENV.items()
        if field_name not in budget
    ]
    return budget, tuple(dict.fromkeys(failures))


def _failure_code(exc: BaseException) -> str:
    code = str(getattr(exc, "failure_code", "") or "").strip()
    if code:
        return code
    text = str(exc).strip().split(":", 1)[0]
    return text or exc.__class__.__name__


def _failure_detail(stage: str, exc: BaseException) -> dict[str, str]:
    """Retain the typed code and full diagnostic at the failing boundary."""

    return {
        "stage": stage,
        "code": _failure_code(exc),
        "message": str(exc).strip() or exc.__class__.__name__,
    }


def _context_rebuild_inputs(root: Path) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Load the same frozen inputs used by the production context compiler.

    The previous matrix loaded ``mechanism_context_set_v1`` directly.  That
    validates a historical compiler output and cannot verify owner-first
    merging, active-path reconstruction, or current source authority.  The
    offline gate now treats the V1 set only as a tree-hash migration anchor
    and deterministically recompiles from the frozen research products.
    """

    inputs: dict[str, Any] = {}
    diagnostics: list[str] = []
    collection_keys = {
        "facets": ("facets",),
        "facet_alignments": ("alignments",),
        "field_candidates": ("candidates",),
        "story_spine": ("author_story_spine", "story_spine", "nodes"),
    }
    for logical_name, names in _CONTEXT_REBUILD_NAMES.items():
        path = _artifact_path(root, names)
        if path is None:
            diagnostics.append(f"unified_context_rebuild_input_missing:{logical_name}")
            continue
        try:
            payload = _read_json(path)
            keys = collection_keys.get(logical_name, ())
            if keys and isinstance(payload, Mapping):
                value = next(
                    (payload.get(key) for key in keys if payload.get(key) is not None),
                    (),
                )
                inputs[logical_name] = tuple(value or ())
            elif keys and isinstance(payload, list):
                inputs[logical_name] = tuple(payload)
            else:
                inputs[logical_name] = payload
        except Exception as exc:
            diagnostics.append(
                f"unified_context_rebuild_input_invalid:{logical_name}:{_failure_code(exc)}"
            )
    return inputs, tuple(dict.fromkeys(diagnostics))


def _authoring_scope_hints(
    root: Path,
    research: Mapping[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Collect intent text and only fresh explicit owner hints.

    The legacy ``mechanism_context_set_v1`` is deliberately excluded from
    the owner-hint lane: its entry/detail IDs are exactly the values the
    current source compiler is meant to replace.  Narrative prose remains a
    useful semantic hint, while explicit symbol fields in the frozen
    brief/facet/story inputs retain their higher authority.
    """

    inputs, _diagnostics = _context_rebuild_inputs(root)
    texts: list[str] = []
    owner_ids: list[str] = []
    owner_fields = (
        "entry_symbol_ids", "target_entry_symbol_ids", "entry_symbol_id",
        "target_entry_symbol_id", "owner_symbol_ids", "owner_symbol_id",
        "implementation_owner_symbol_ids", "implementation_owner_symbol_id",
    )
    text_fields = (
        "mechanism_name", "scientific_role", "purpose", "reader_question",
        "author_statement", "statement", "narrative", "description",
        "semantic_atom", "exact_source_quote", "formula_expectation",
        "field_name", "search_terms", "transformations", "outputs",
        "inputs", "goal", "question", "canonical_text",
    )

    def visit(value: Any, *, allow_owner_fields: bool = True) -> None:
        if isinstance(value, Mapping):
            if allow_owner_fields:
                for field_name in owner_fields:
                    raw = value.get(field_name, ())
                    if isinstance(raw, str):
                        raw = (raw,)
                    if raw is not None:
                        try:
                            owner_ids.extend(
                                str(item).strip() for item in raw if str(item).strip()
                            )
                        except TypeError:
                            item = str(raw).strip()
                            if item:
                                owner_ids.append(item)
            for field_name in text_fields:
                raw = value.get(field_name)
                if raw is None:
                    continue
                if isinstance(raw, (list, tuple, set)):
                    texts.extend(str(item).strip() for item in raw if str(item).strip())
                elif not isinstance(raw, Mapping):
                    item = str(raw).strip()
                    if item:
                        texts.append(item)
            for key, item in value.items():
                if key not in set(text_fields) and key not in set(owner_fields):
                    visit(item, allow_owner_fields=allow_owner_fields)
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                visit(item, allow_owner_fields=allow_owner_fields)

    # Use current/research-side narrative inputs, not old technical context
    # IDs.  The context set may still contribute prose as a semantic hint.
    visit(inputs, allow_owner_fields=True)
    for context in getattr(research.get("context_set"), "contexts", ()) or ():
        for field_name in text_fields:
            raw = getattr(context, field_name, None)
            if raw is None:
                continue
            if isinstance(raw, (list, tuple, set)):
                texts.extend(str(item).strip() for item in raw if str(item).strip())
            else:
                item = str(raw).strip()
                if item:
                    texts.append(item)
    for key in ("intent_graph", "claims"):
        visit(research.get(key), allow_owner_fields=False)
    return tuple(dict.fromkeys(texts)), tuple(dict.fromkeys(owner_ids))


def _verified_source_provider(source: Mapping[str, Any]) -> Any:
    """Return the digest-verified source reader for a rehydrated snapshot."""

    snapshot = source.get("repo_snapshot")
    if snapshot is None:
        return None
    project_root = str(getattr(snapshot, "project_root", "") or "")
    if not project_root:
        return snapshot
    return read_verified_snapshot_sources(
        project_root=project_root,
        source_manifest=source.get("source_manifest"),
        repo_snapshot=snapshot,
    )


def _rebuild_current_context_set(
    root: Path,
    *,
    research: Mapping[str, Any],
    source: Mapping[str, Any],
) -> tuple[MechanismContextSetV1, tuple[str, ...], dict[str, Any]]:
    inputs, diagnostics = _context_rebuild_inputs(root)
    # The compiler can operate without every optional projection, but it
    # cannot establish an executable owner from narrative alone.  Preserve
    # missing-input diagnostics for the report while letting the compiler
    # expose the exact owner/source gate that follows.
    context_set = compile_mechanism_contexts(
        argument_briefs=inputs.get("argument_briefs"),
        facets=inputs.get("facets", ()),
        facet_alignments=inputs.get("facet_alignments", ()),
        field_candidates=inputs.get("field_candidates", ()),
        story_spine=inputs.get("story_spine", ()),
        facts=research.get("facts"),
        claims=research.get("claims"),
        equations=research.get("equations"),
        configurations=inputs.get("configurations"),
        evidence_packets=inputs.get("evidence_packets"),
        # The graph is rebuilt by the shared current-source preparation path;
        # a persisted historical graph is never passed into the compiler.
        behavior_graph=source.get("behavior_graph"),
        implementation_scope=source.get("implementation_scope"),
        symbol_index=source.get("symbol_index"),
        # R6: pass the same revision-frozen, digest-verified reader production
        # uses.  A raw snapshot model carries its capture timestamp, which must
        # not enter the closure/archive identity.
        source_provider=_verified_source_provider(source),
        source_manifest=source.get("source_manifest"),
    )
    if not context_set.contexts:
        raise ValueError("unified_context_rebuild_empty:no executable mechanism owner")
    return context_set, diagnostics, inputs


def _load_research_inputs(root: Path) -> tuple[dict[str, Any], list[str]]:
    loaded: dict[str, Any] = {}
    failures: list[str] = []
    compatibility: list[dict[str, str]] = []

    context_path = _artifact_path(root, _RESEARCH_NAMES["context_set"])
    if context_path is not None:
        try:
            context_payload = _read_mapping(context_path)
            context_set, migrated = load_mechanism_context_set_v1_payload(
                context_payload
            )
            loaded["context_set"] = context_set
            if migrated:
                compatibility.append({
                    "artifact": "mechanism_context_set_v1",
                    "action": "recomputed_current_derived_digests_after_legacy_v1_root_verification",
                })
        except Exception:
            # The historical context is only a tree-hash/migration anchor.
            # The current offline chain never consumes its mechanism/detail
            # IDs, so a stale or malformed copy is non-blocking when the
            # source snapshot can be rebuilt from the repository.
            compatibility.append({
                "artifact": "mechanism_context_set_v1",
                "action": "ignored_invalid_legacy_context_for_current_rebuild",
            })

    formula_path = _artifact_path(root, _RESEARCH_NAMES["formula_obligations"])
    if formula_path is not None:
        try:
            payload = _read_mapping(formula_path)
            formula_obligations, migrated = load_mechanism_formula_obligations_v1_payload(
                payload
            )
            loaded["formula_obligations"] = formula_obligations
            if migrated:
                compatibility.append({
                    "artifact": "mechanism_formula_obligations_v1",
                    "action": "recomputed_current_derived_digests_after_legacy_v1_row_verification",
                })
        except Exception:
            compatibility.append({
                "artifact": "mechanism_formula_obligations_v1",
                "action": "ignored_invalid_legacy_obligations_for_current_rebuild",
            })

    narrative_path = _artifact_path(root, _RESEARCH_NAMES["narrative_plan"])
    if narrative_path is not None:
        try:
            loaded["narrative_plan"] = _read_json(narrative_path)
        except Exception:
            compatibility.append({
                "artifact": "narrative_plan_v3",
                "action": "ignored_invalid_legacy_narrative_for_current_rebuild",
            })

    section_plan_path = _artifact_path(root, _RESEARCH_NAMES["section_plan"])
    if section_plan_path is not None:
        try:
            loaded["section_plan"] = MethodSectionPlanV2.model_validate_json(
                section_plan_path.read_text(encoding="utf-8")
            )
        except Exception:
            compatibility.append({
                "artifact": "method_section_plan_v2",
                "action": "ignored_invalid_legacy_section_plan_for_current_rebuild",
            })

    intent_path = _artifact_path(root, _RESEARCH_NAMES["intent_graph"])
    if intent_path is not None:
        try:
            from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2

            loaded["intent_graph"] = IntentObligationGraphV2.model_validate_json(
                intent_path.read_text(encoding="utf-8")
            )
        except Exception:
            failures.append("unified_intent_graph_invalid")
    else:
        failures.append("unified_intent_graph_missing")

    agenda_path = _artifact_path(root, _RESEARCH_NAMES["research_agenda"])
    if agenda_path is not None:
        try:
            loaded["research_agenda"] = ResearchAgendaV1.model_validate_json(
                agenda_path.read_text(encoding="utf-8")
            )
        except Exception:
            failures.append("unified_research_agenda_invalid")
    else:
        failures.append("unified_research_agenda_missing")

    optional_loaders = {
        "equations": lambda path: load_equation_claims(path),
        "claims": lambda path: load_atomic_claims_v3_or_v2(path),
        "facts": lambda path: load_code_facts_v1(path),
    }
    for key, loader in optional_loaders.items():
        path = _artifact_path(root, _RESEARCH_NAMES[key])
        if path is None:
            continue
        try:
            loaded[key] = loader(path)
        except Exception:
            failures.append(f"unified_{key}_invalid")
    if compatibility:
        loaded["compatibility"] = tuple(compatibility)
    return loaded, list(dict.fromkeys(failures))


def _source_inputs(root: Path) -> tuple[dict[str, Any], list[str]]:
    loaded: dict[str, Any] = {}
    failures: list[str] = []
    paths: dict[str, Path] = {}
    for logical_name, names in _SOURCE_NAMES:
        path = _artifact_path(root, names)
        if path is None:
            failures.append(f"unified_{logical_name}_missing")
        else:
            paths[logical_name] = path
    try:
        if "repo_snapshot_v2" in paths:
            loaded["repo_snapshot"] = RepoSnapshot.model_validate_json(
                paths["repo_snapshot_v2"].read_text(encoding="utf-8")
            )
        if "symbol_index_v2" in paths:
            loaded["symbol_index"] = SymbolIndexV2.model_validate_json(
                paths["symbol_index_v2"].read_text(encoding="utf-8")
            )
        if "implementation_scope_v1" in paths:
            loaded["implementation_scope"] = ImplementationScopeV1.model_validate_json(
                paths["implementation_scope_v1"].read_text(encoding="utf-8")
            )
        if "repository_source_manifest_v1" in paths:
            loaded["source_manifest"] = RepositorySourceManifestV1.model_validate_json(
                paths["repository_source_manifest_v1"].read_text(encoding="utf-8")
            )
    except Exception as exc:
        failures.append(f"unified_source_artifact_invalid:{_failure_code(exc)}")

    snapshot = loaded.get("repo_snapshot")
    symbol_index = loaded.get("symbol_index")
    scope = loaded.get("implementation_scope")
    manifest = loaded.get("source_manifest")
    if snapshot is not None and manifest is not None:
        failures.extend(source_manifest_snapshot_failures(manifest, snapshot))
        failures.extend(
            f"unified_source_manifest_anomaly:{item}"
            for item in (getattr(manifest, "anomaly_codes", ()) or ())
        )
    if snapshot is not None and symbol_index is not None:
        if symbol_index.repo_snapshot_id != snapshot.snapshot_id:
            failures.append("unified_symbol_index_snapshot_mismatch")
        if symbol_index.project_tree_hash != snapshot.project_tree_hash:
            failures.append("unified_symbol_index_tree_hash_mismatch")
        snapshot_paths = {
            normalize_source_path(str(item.path))
            for item in snapshot.included_files
        }
        for symbol in symbol_index.symbols:
            if normalize_source_path(symbol.path) not in snapshot_paths:
                failures.append(f"unified_symbol_source_path_missing:{symbol.path}")
    if symbol_index is not None and scope is not None:
        indexed = {str(item.symbol_id) for item in symbol_index.symbols}
        scoped = set()
        for field_name in (
            "target_entry_symbol_ids", "target_core_symbol_ids",
            "target_dependency_symbol_ids", "comparand_symbol_ids",
            "evaluation_symbol_ids", "configuration_symbol_ids",
            "unknown_symbol_ids",
        ):
            scoped.update(str(item) for item in getattr(scope, field_name, ()) or ())
        failures.extend(
            f"unified_implementation_scope_symbol_missing:{item}"
            for item in sorted(scoped - indexed)
        )

    identity_path = paths.get("repository_authoring_artifacts_v1")
    if identity_path is not None:
        try:
            identity = _read_mapping(identity_path)
            if all(item is not None for item in (snapshot, symbol_index, scope, manifest)):
                expected = repository_authoring_identity_payload(
                    snapshot=snapshot,
                    symbol_index=symbol_index,
                    implementation_scope=scope,
                    source_manifest=manifest,
                    builder_version=REPOSITORY_AUTHORING_BUILDER_VERSION,
                )
                if dict(identity) != expected:
                    failures.append("unified_repository_authoring_identity_mismatch")
        except Exception:
            failures.append("unified_repository_authoring_identity_invalid")
    return loaded, list(dict.fromkeys(failures))


def _trusted_frozen_project_tree_hash(root: Path) -> tuple[str, str]:
    """Read a frozen tree hash from typed source/replay authority only.

    Historical roots can predate persisted V2 source artifacts.  The replay
    contract still records the same hash in a continuation seed or its
    execution record, which is sufficient to authenticate an explicitly
    supplied repository for an offline rebuild.  Do not search arbitrary JSON
    because diagnostics may contain stale or unrelated project hashes.
    """

    values: list[tuple[str, str]] = []

    def _record(name: str, payload: Mapping[str, Any]) -> None:
        value = str(payload.get("project_tree_hash") or "").strip()
        # ``tree:unknown`` and other diagnostic placeholders are not an
        # authentication value.  A frozen hash must be the exact digest form
        # emitted by ``build_repo_snapshot``.
        if re.fullmatch(r"sha256:[0-9a-f]{64}", value):
            values.append((name, value))

    for name, names in (
        ("repo_snapshot_v2", ("repo_snapshot_v2", "repo_snapshot")),
        (
            "repository_source_manifest_v1",
            ("repository_source_manifest_v1", "repository_source_manifest"),
        ),
        (
            "repository_authoring_artifacts_v1",
            ("repository_authoring_artifacts_v1",),
        ),
        ("research_continuation_seed_v1", ("research_continuation_seed_v1",)),
        ("authoring_run_contract_v1", ("authoring_run_contract_v1",)),
        # V1 authoring outputs are accepted only as a migration anchor.  The
        # supplied repository is still rebuilt through the shared source
        # builder and must match this exact hash before it can be used.
        ("mechanism_context_set_v1", ("mechanism_context_set_v1",)),
        ("formalization_result_v1", ("formalization_result_v1",)),
    ):
        path = _artifact_path(root, names)
        if path is None:
            continue
        payload = _read_json(path)
        if not isinstance(payload, Mapping):
            continue
        _record(name, payload)

    execution_path = root / "execution_record.json"
    if execution_path.is_file():
        payload = _read_mapping(execution_path)
        seed = payload.get("research_continuation_seed")
        if isinstance(seed, Mapping):
            _record("execution_record.research_continuation_seed", seed)

    if not values:
        raise ValueError("unified_project_tree_hash_missing")
    hashes = {value for _name, value in values}
    if len(hashes) != 1:
        detail = ",".join(f"{name}={value}" for name, value in values)
        raise ValueError(
            "unified_project_tree_hash_mismatch:frozen_artifacts_disagree:" + detail
        )
    return values[0][1], values[0][0]


def _rehydrate_source_inputs(
    root: Path,
    repo_path: Path,
    *,
    author_texts: tuple[str, ...] = (),
    entry_symbol_ids: tuple[str, ...] = (),
) -> tuple[dict[str, Any], str]:
    """Rebuild missing source artifacts in memory after an exact hash check."""

    expected_tree_hash, hash_source = _trusted_frozen_project_tree_hash(root)
    rebuilt = rebuild_repository_authoring_artifacts(
        repo_path,
        expected_project_tree_hash=expected_tree_hash,
        author_texts=author_texts,
        entry_symbol_ids=entry_symbol_ids,
    )
    # Construct and compare the same cross-artifact identity that a replay
    # would persist.  This keeps the offline path on the product builder and
    # avoids accepting four independently fabricated model payloads.
    identity = repository_authoring_identity_payload(
        snapshot=rebuilt.snapshot,
        symbol_index=rebuilt.symbol_index,
        implementation_scope=rebuilt.implementation_scope,
        source_manifest=rebuilt.source_manifest,
        builder_version=REPOSITORY_AUTHORING_BUILDER_VERSION,
    )
    if identity.get("project_tree_hash") != expected_tree_hash:
        raise ValueError("unified_project_tree_hash_mismatch:rehydrated_identity")
    source_failures = list(source_manifest_snapshot_failures(
        rebuilt.source_manifest,
        rebuilt.snapshot,
    ))
    source_failures.extend(
        f"unified_source_manifest_anomaly:{item}"
        for item in (getattr(rebuilt.source_manifest, "anomaly_codes", ()) or ())
    )
    if source_failures:
        raise ValueError(";".join(dict.fromkeys(source_failures)))

    entry_roots = tuple(
        str(item).strip()
        for item in (getattr(rebuilt.implementation_scope, "target_entry_symbol_ids", ()) or ())
        if str(item).strip()
    )
    current_graph = build_current_behavior_graph(
        symbol_index=rebuilt.symbol_index,
        source_provider=rebuilt.files,
        entry_symbol_ids=entry_roots,
    )
    historical_graph_path = _artifact_path(root, ("behavior_graph_v1",))
    historical_summary: dict[str, Any] = {"present": False}
    historical_node_count = 0
    historical_relation_count = 0
    if historical_graph_path is not None:
        try:
            payload = _read_json(historical_graph_path)
            if isinstance(payload, Mapping):
                payload = payload.get("behavior_graph") or payload.get("graph") or payload
            nodes = tuple(payload.get("nodes", ()) or ()) if isinstance(payload, Mapping) else ()
            relations = tuple(payload.get("relations", ()) or ()) if isinstance(payload, Mapping) else ()
            historical_node_count = len(nodes)
            historical_relation_count = len(relations)
            historical_summary = {
                "present": True,
                "content_digest": str(payload.get("content_digest", "") or "")
                if isinstance(payload, Mapping) else "",
                "node_count": historical_node_count,
                "relation_count": historical_relation_count,
                "unresolved_relation_count": len(
                    tuple(payload.get("unresolved_relations", ()) or ())
                ) if isinstance(payload, Mapping) else 0,
            }
        except Exception as exc:
            historical_summary = {
                "present": True,
                "load_failure": f"{exc.__class__.__name__}:{str(exc)[:160]}",
            }
    if historical_graph_path is not None and current_graph is None:
        raise ValueError("unified_behavior_graph_rebuild_missing")
    current_summary = {
        "present": current_graph is not None,
        "repo_snapshot_id": str(getattr(current_graph, "repo_snapshot_id", "") or "")
        if current_graph is not None else "",
        "project_tree_hash": str(getattr(current_graph, "project_tree_hash", "") or "")
        if current_graph is not None else "",
        "content_digest": str(getattr(current_graph, "content_digest", "") or "")
        if current_graph is not None else "",
        "node_count": len(getattr(current_graph, "nodes", ()) or ())
        if current_graph is not None else 0,
        "relation_count": len(getattr(current_graph, "relations", ()) or ())
        if current_graph is not None else 0,
        "unresolved_relation_count": len(getattr(current_graph, "unresolved_relations", ()) or ())
        if current_graph is not None else 0,
    }
    graph_rebuild = {
        "schema_version": "1.0",
        "source": "current_verified_repository_source",
        "entry_symbol_ids": list(entry_roots),
        "repo_snapshot_id": rebuilt.snapshot.snapshot_id,
        "project_tree_hash": rebuilt.snapshot.project_tree_hash,
        "historical_graph": historical_summary,
        "current_graph": current_summary,
        "node_count_delta": current_summary["node_count"] - historical_node_count,
        "relation_count_delta": current_summary["relation_count"] - historical_relation_count,
    }
    graph_rebuild["content_digest"] = sha256_digest(
        canonical_json_bytes(graph_rebuild)
    )
    return (
        {
            "repo_snapshot": rebuilt.snapshot,
            "symbol_index": rebuilt.symbol_index,
            "implementation_scope": rebuilt.implementation_scope,
            "source_manifest": rebuilt.source_manifest,
            "behavior_graph": current_graph,
            "behavior_graph_rebuild": graph_rebuild,
        },
        f"rehydrated_from_repo:{hash_source}:{expected_tree_hash}",
    )


def _research_gate_failures(inputs: Mapping[str, Any]) -> tuple[str, ...]:
    """Strict Research gate, computed by the product's own function.

    R2: the harness no longer keeps a second, independently drifting copy of
    the strict gate.  Product and offline therefore agree on every failure
    code for the same frozen inputs; the only remaining difference is the
    explicitly selected lane (strict vs Candidate).
    """

    from code2paper.agentic.publication_method_writer import (
        _unified_research_gate_failures,
    )

    return _unified_research_gate_failures(
        intent_graph=inputs.get("intent_graph"),
        research_agenda=inputs.get("research_agenda"),
        contexts=inputs.get("context_set"),
    )


def _research_artifact_paths(root: Path) -> dict[str, str]:
    """Resolve the frozen paths Candidate revalidation consumes."""

    names = {
        "candidate_handoff_v1": ("candidate_handoff_v1",),
        "candidate_retry_ledger_v1": ("candidate_retry_ledger_v1",),
        "observation_promotion_ledger_v1": ("observation_promotion_ledger_v1",),
        "research_agenda_v1": ("research_agenda_v1",),
        "atomic_claims_v3": ("atomic_claims_v3", "atomic_claims_v3_v3"),
        "code_facts_v1": ("code_facts_v1", "code_facts_v1_v3"),
        "evidence_packets_v3": ("evidence_packets_v3",),
    }
    paths: dict[str, str] = {}
    for key, candidates in names.items():
        path = _artifact_path(root, candidates)
        if path is not None:
            paths[key] = str(path)
    return paths


def _research_mode_failures(
    inputs: Mapping[str, Any],
    *,
    artifact_paths: Mapping[str, str],
) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, Any]]:
    """Return ``(strict, candidate, diagnostics)`` for one frozen project.

    The Candidate projection reuses the product's authenticated-handoff
    loader and Candidate-lane filter, so a partial handoff can never be
    silently promoted to a strict pass, and a harness that does not recognise
    the handoff cannot invent a terminal gap the product would not see.
    """

    from code2paper.agentic.publication_method_writer import (
        _candidate_lane_research_failures,
        _load_authenticated_candidate_handoff,
    )

    strict = _research_gate_failures(inputs)
    artifact_map = {str(key): str(value) for key, value in artifact_paths.items()}
    handoff, handoff_failures = _load_authenticated_candidate_handoff(artifact_map)
    candidate = _candidate_lane_research_failures(
        strict,
        candidate_handoff=handoff,
    )
    if handoff is not None and handoff.eligible:
        handoff_status = "eligible"
    elif handoff is not None:
        handoff_status = "ineligible"
    elif artifact_map.get("candidate_handoff_v1"):
        handoff_status = "rejected"
    else:
        handoff_status = "missing"
    diagnostics = {
        "gate_mode": "strict",
        "strict_failure_codes": list(strict),
        "candidate_failure_codes": list(candidate),
        "candidate_gate_pass": not candidate,
        "candidate_handoff_status": handoff_status,
        "candidate_handoff_digest": str(getattr(handoff, "content_digest", "") or ""),
        "candidate_handoff_revalidation_failures": list(handoff_failures),
    }
    return strict, candidate, diagnostics


def _derive_formula_obligations(
    contexts: MechanismContextSetV1,
    loaded: Mapping[str, Any],
) -> dict[str, tuple[MechanismFormulaObligationV1, ...]]:
    existing = loaded.get("formula_obligations")
    if isinstance(existing, Mapping):
        result: dict[str, tuple[MechanismFormulaObligationV1, ...]] = {}
        for context in contexts.contexts:
            mechanism_id = str(context.mechanism_id)
            result[mechanism_id] = tuple(
                item for item in (existing.get(mechanism_id, ()) or ())
                if isinstance(item, MechanismFormulaObligationV1)
            )
        return result
    equations = loaded.get("equations")
    claims = loaded.get("claims")
    return {
        str(context.mechanism_id): compile_mechanism_formula_obligations(
            context,
            equations=equations,
            claims=claims,
            author_formula_expectations=tuple(
                str(item).strip()
                for item in (context.notation_hints or ())
                if str(item).strip()
            ),
        )
        for context in contexts.contexts
    }


def _phase_row(
    plan: Any | None,
    admission: Any | None,
    error: str = "",
    candidate_admission: Any | None = None,
) -> dict[str, Any]:
    if plan is None:
        return {
            "status": "fail",
            "planned_calls": {},
            "planned_input_tokens": {},
            "max_attempts": 0,
            "admission_failure_codes": [error] if error else [],
            "candidate_status": "fail",
            "candidate_admission_failure_codes": [error] if error else [],
        }
    return {
        "status": "pass" if admission is not None and admission.status == "pass" else "fail",
        "candidate_status": (
            "pass"
            if candidate_admission is not None
            and candidate_admission.status == "pass"
            else "fail"
        ),
        "candidate_admission_failure_codes": list(
            getattr(candidate_admission, "failure_codes", ()) or ()
        ),
        "planned_calls": dict(plan.planned_calls_by_role),
        "planned_input_tokens": dict(plan.planned_input_tokens_by_role),
        "reserved_calls": dict(plan.reserved_calls_by_role),
        "reserved_input_tokens": dict(plan.reserved_input_tokens_by_role),
        "max_attempts": max((item.max_attempts for item in plan.invocations), default=0),
        "invocation_count": len(plan.invocations),
        "admission_failure_codes": list(getattr(admission, "failure_codes", ()) or ()),
    }


def _deterministic_formula_packages(
    *,
    contexts: Any,
    formula_obligations: Mapping[str, tuple[MechanismFormulaObligationV1, ...]],
    research: Mapping[str, Any],
) -> tuple[Any, ...]:
    """Build offline formula packages so the narrative plan owns real math.

    The live lane consumes Formalizer LLM packages.  Offline there is no
    caller, so the conservative deterministic source-equation route is used
    with the operation-shaped fallback explicitly disabled; a project without
    authorized source equations simply gets no packages instead of invented
    mathematics.
    """

    from code2paper.agentic.formalization_agent import (
        build_deterministic_mechanism_formula_packages,
    )

    packages: list[Any] = []
    for context in getattr(contexts, "contexts", ()) or ():
        packages.extend(
            build_deterministic_mechanism_formula_packages(
                context=context,
                obligations=tuple(
                    formula_obligations.get(str(context.mechanism_id), ()) or ()
                ),
                equations=research.get("equations"),
                allow_deterministic_operation_fallback=False,
            )
        )
    return tuple(packages)


def project_unified_offline(
    project_id: str,
    root: Path,
    *,
    repo_path: Path | None,
    profile_path: Path | None,
    model_context_override: int | None,
    max_attempts: int,
) -> dict[str, Any]:
    failures: list[str] = []
    failure_details: list[dict[str, str]] = []
    research, research_failures = _load_research_inputs(root)
    failures.extend(research_failures)
    source, source_failures = _source_inputs(root)
    failures.extend(source_failures)
    source_rehydration = ""
    # ``--repo`` is an explicit request to bind the run to the current
    # repository snapshot.  Always rebuild the four source-bound artifacts;
    # the files in the replay root are migration evidence only and may carry
    # a stale implementation owner or graph.
    if repo_path is not None:
        try:
            author_texts, entry_symbol_ids = _authoring_scope_hints(root, research)
            source, source_rehydration = _rehydrate_source_inputs(
                root,
                repo_path,
                author_texts=author_texts,
                entry_symbol_ids=entry_symbol_ids,
            )
            prior_source_failures = set(source_failures)
            failures = [item for item in failures if item not in prior_source_failures]
            source_failures = []
        except Exception as exc:
            failure = _failure_code(exc)
            failures.append(failure)
            source_failures.append(failure)
            failure_details.append(_failure_detail("source_rehydration", exc))
    else:
        # The offline gate must prove the source closure is rebuilt from the
        # current repository.  Without ``--repo`` the frozen replay artifacts
        # are the only source and no external tree hash anchors them.
        failures.append("unified_source_rehydration_missing")
        source_failures.append("unified_source_rehydration_missing")

    profile_values, profile_digest, model_name, profile_context_tokens = _profile_values(profile_path)
    profile_budget, budget_failures = _parse_budget(profile_values)
    failures.extend(budget_failures)
    model_context_tokens = int(model_context_override or profile_context_tokens or 0)
    if model_context_tokens <= 0:
        failures.append(f"{UNIFIED_INVOCATION_BUDGET_MISSING}:model_context_tokens")
    model_identity_digest = (
        sha256_digest(model_name.encode("utf-8")) if model_name else ""
    )
    if not model_identity_digest:
        failures.append("unified_model_identity_missing")

    snapshot = source.get("repo_snapshot")
    manifest = source.get("source_manifest")
    contexts = None
    context_origin = "current_compiler_rebuild"
    context_rebuild_diagnostics: tuple[str, ...] = ()
    current_context_inputs: dict[str, Any] = {}
    # Strict vs Candidate gate verdicts are always reported, even when the
    # mechanism reconstruction never started.
    strict_research_failures, candidate_research_failures, research_gate_modes = (
        _research_mode_failures(
            research,
            artifact_paths=_research_artifact_paths(root),
        )
    )
    research_gate_modes.setdefault("candidate_gate_pass", not candidate_research_failures)
    if snapshot is not None and manifest is not None:
        try:
            (
                contexts,
                context_rebuild_diagnostics,
                current_context_inputs,
            ) = _rebuild_current_context_set(root, research=research, source=source)
            research["context_set"] = contexts
            # A missing/invalid rebuild input means the matrix would be
            # validating a partially reconstructed context; fail the project.
            failures.extend(context_rebuild_diagnostics)
        except Exception as exc:
            failures.append(_failure_code(exc))
            failure_details.append(_failure_detail("mechanism_context_rebuild", exc))
    else:
        context_origin = "unavailable"
    archive = None
    workset_manifest = None
    envelope = None
    phase_plans: dict[str, Any] = {}
    phase_admissions: dict[str, Any] = {}
    # R2/round-4 guidance: the same real admission is evaluated in the
    # Candidate lane with identical inputs, so a phase blocked only by
    # strict-lane research codes reports its Candidate verdict too.
    phase_admissions_candidate: dict[str, Any] = {}
    phase_manifests: dict[str, Any] = {}
    if contexts is None or snapshot is None or manifest is None:
        failures.append("unified_context_compilation_inputs_missing")
    else:
        if contexts.repo_snapshot_id != snapshot.snapshot_id:
            failures.append("unified_context_snapshot_id_mismatch")
        if contexts.project_tree_hash != snapshot.project_tree_hash:
            failures.append("unified_context_tree_hash_mismatch")
        try:
            archive = build_unified_context_archive_v2(
                contexts,
                source_manifest_digest=manifest.content_digest,
                source_manifest=manifest,
                # The snapshot identity helper excludes capture-time fields;
                # dumping the model inline leaked ``created_at`` here.
                repo_snapshot_digest=repo_snapshot_identity_digest(snapshot),
                equations=research.get("equations"),
                claims=research.get("claims"),
                facts=research.get("facts"),
                intent_graph=research.get("intent_graph"),
            )
        except Exception as exc:
            failures.append(_failure_code(exc))
            failure_details.append(_failure_detail("archive_compile", exc))

    formula_obligations: dict[str, tuple[MechanismFormulaObligationV1, ...]] = {}
    if contexts is not None:
        try:
            # Frozen formula obligations name the historical context/detail
            # owners.  Once the context is rebuilt they must be recompiled
            # from the same equations and claims, not silently rebound by
            # matching an old mechanism ID.
            current_formula_inputs = dict(research)
            current_formula_inputs.pop("formula_obligations", None)
            formula_obligations = _derive_formula_obligations(
                contexts,
                current_formula_inputs,
            )
        except Exception as exc:
            failures.append(f"unified_formula_obligation_compile_failed:{_failure_code(exc)}")
            failure_details.append(_failure_detail("formula_obligation_compile", exc))

    completeness: dict[str, list[str]] = {}
    mechanism_diagnostics: dict[str, Any] = {}
    if contexts is not None:
        completeness = {
            str(context.mechanism_id): list(
                validate_mechanism_context_completeness(
                    context,
                    source_manifest=manifest,
                )
            )
            for context in contexts.contexts
        }
        mechanism_diagnostics = validate_mechanism_context_structural_gates(
            contexts,
            merge_proofs=(archive.merge_proofs if archive is not None else ()),
        )
        failures.extend(
            f"{mechanism_id}:{item}"
            for mechanism_id, items in completeness.items()
            for item in items
        )
        strict_research_failures, candidate_research_failures, research_gate_modes = (
            _research_mode_failures(
                research,
                artifact_paths=_research_artifact_paths(root),
            )
        )
        research_failures = list(strict_research_failures)
        failures.extend(research_failures)

    phase_rows: dict[str, dict[str, Any]] = {}
    deterministic_formula_packages: tuple[Any, ...] = ()
    # Each stage records its own failure code so a matrix row says which part
    # of the chain failed instead of a single opaque invocation_plan_compile.
    stage = "budget_envelope_compile"
    if archive is not None and model_context_tokens > 0 and model_identity_digest:
        try:
            envelope = build_run_invocation_budget_envelope_v1(
                profile_budget=profile_budget,
                model_capabilities={"context_tokens": model_context_tokens},
                run_digest=archive.content_digest,
                profile_digest=profile_digest,
                model_identity_digest=model_identity_digest,
            )
            stage = "workset_compile"
            workset_manifest = build_consumer_workset_manifest_v2(
                archive,
                formula_obligations_by_mechanism=formula_obligations,
                max_page_input_tokens=envelope.max_page_input_tokens,
                max_obligations_per_page=envelope.max_obligations_per_page,
            )
            stage = "formula_page_owner_binding"
            formula_obligations = bind_formula_obligation_page_owners(
                formula_obligations,
                workset_manifest,
            )
            phase_manifests["formalizer"] = workset_manifest
            stage = "formalizer_plan_compile"
            phase_plans["formalizer"] = build_consumer_invocation_plan_v1(
                workset_manifest,
                envelope,
                phase="formalizer",
                profile_digest=envelope.profile_digest,
                model_identity_digest=envelope.model_identity_digest,
                model_context_tokens=model_context_tokens,
                max_attempts=max_attempts,
            )
            stage = "formalizer_admission"
            phase_admissions["formalizer"] = evaluate_unified_live_admission_v1(
                phase="formalizer",
                plan=phase_plans["formalizer"],
                envelope=envelope,
                archive=archive,
                manifest=workset_manifest,
                run_digest=archive.content_digest,
                model_context_tokens=model_context_tokens,
                closed_set_failures=tuple(
                    f"{mid}:{item}"
                    for mid, items in completeness.items()
                    for item in items
                ),
                research_failures=_research_gate_failures(research),
                mechanism_diagnostics=mechanism_diagnostics,
                source_failures=source_failures,
            )
            phase_admissions_candidate["formalizer"] = evaluate_unified_live_admission_v1(
                phase="formalizer",
                plan=phase_plans["formalizer"],
                envelope=envelope,
                archive=archive,
                manifest=workset_manifest,
                run_digest=archive.content_digest,
                model_context_tokens=model_context_tokens,
                closed_set_failures=tuple(
                    f"{mid}:{item}"
                    for mid, items in completeness.items()
                    for item in items
                ),
                research_failures=candidate_research_failures,
                mechanism_diagnostics=mechanism_diagnostics,
                source_failures=source_failures,
            )
            stage = "narrative_plan_compile"
            story_spine = tuple(
                AuthorStoryNodeV1.model_validate(item)
                for item in current_context_inputs.get("story_spine", ())
            )
            deterministic_formula_packages = _deterministic_formula_packages(
                contexts=contexts,
                formula_obligations=formula_obligations,
                research=research,
            )
            narrative_plan, _narrative_trace = build_narrative_plan_v3(
                contexts=contexts,
                story_spine=story_spine,
                formula_packages=deterministic_formula_packages,
                prior_plan=research.get("section_plan"),
                proposal_caller=None,
                llm_config=None,
            )
            stage = "writer_workset_extend"
            narrative_plan, paragraph_revision_failures, revision_diag = (
                fit_narrative_plan_to_page_budget(
                    narrative_plan,
                    archive=archive,
                    max_page_input_tokens=envelope.max_page_input_tokens,
                )
            )
            if paragraph_revision_failures:
                raise ValueError(
                    "narrative_plan_page_budget_unresolved:"
                    + ";".join(paragraph_revision_failures)
                )
            writer_manifest = extend_writer_worksets_from_narrative_plan(
                workset_manifest,
                narrative_plan,
                max_page_input_tokens=envelope.max_page_input_tokens,
                archive=archive,
            )
            phase_manifests["writer"] = writer_manifest
            phase_manifests["realizer"] = writer_manifest
            stage = "writer_plan_compile"
            phase_plans["writer"] = build_consumer_invocation_plan_v1(
                writer_manifest,
                envelope,
                phase="writer",
                parent_plan=phase_plans["formalizer"],
                plan_revision=2,
                profile_digest=envelope.profile_digest,
                model_identity_digest=envelope.model_identity_digest,
                model_context_tokens=model_context_tokens,
                max_attempts=max_attempts,
            )
            stage = "writer_admission"
            phase_admissions["writer"] = evaluate_unified_live_admission_v1(
                phase="writer",
                plan=phase_plans["writer"],
                envelope=envelope,
                archive=archive,
                manifest=writer_manifest,
                run_digest=archive.content_digest,
                model_context_tokens=model_context_tokens,
                closed_set_failures=tuple(
                    f"{mid}:{item}"
                    for mid, items in completeness.items()
                    for item in items
                ),
                research_failures=_research_gate_failures(research),
                mechanism_diagnostics=mechanism_diagnostics,
                source_failures=source_failures,
            )
            phase_admissions_candidate["writer"] = evaluate_unified_live_admission_v1(
                phase="writer",
                plan=phase_plans["writer"],
                envelope=envelope,
                archive=archive,
                manifest=writer_manifest,
                run_digest=archive.content_digest,
                model_context_tokens=model_context_tokens,
                closed_set_failures=tuple(
                    f"{mid}:{item}"
                    for mid, items in completeness.items()
                    for item in items
                ),
                research_failures=candidate_research_failures,
                mechanism_diagnostics=mechanism_diagnostics,
                source_failures=source_failures,
            )
            stage = "realizer_plan_compile"
            phase_plans["realizer"] = build_consumer_invocation_plan_v1(
                writer_manifest,
                envelope,
                phase="realizer",
                parent_plan=phase_plans["writer"],
                plan_revision=3,
                profile_digest=envelope.profile_digest,
                model_identity_digest=envelope.model_identity_digest,
                model_context_tokens=model_context_tokens,
                max_attempts=max_attempts,
            )
            stage = "realizer_admission"
            phase_admissions["realizer"] = evaluate_unified_live_admission_v1(
                phase="realizer",
                plan=phase_plans["realizer"],
                envelope=envelope,
                archive=archive,
                manifest=writer_manifest,
                run_digest=archive.content_digest,
                model_context_tokens=model_context_tokens,
                closed_set_failures=tuple(
                    f"{mid}:{item}"
                    for mid, items in completeness.items()
                    for item in items
                ),
                research_failures=_research_gate_failures(research),
                mechanism_diagnostics=mechanism_diagnostics,
                source_failures=source_failures,
            )
            phase_admissions_candidate["realizer"] = evaluate_unified_live_admission_v1(
                phase="realizer",
                plan=phase_plans["realizer"],
                envelope=envelope,
                archive=archive,
                manifest=writer_manifest,
                run_digest=archive.content_digest,
                model_context_tokens=model_context_tokens,
                closed_set_failures=tuple(
                    f"{mid}:{item}"
                    for mid, items in completeness.items()
                    for item in items
                ),
                research_failures=candidate_research_failures,
                mechanism_diagnostics=mechanism_diagnostics,
                source_failures=source_failures,
            )
        except Exception as exc:
            failures.append(f"unified_{stage}_failed:{_failure_code(exc)}")
            failure_details.append(_failure_detail(stage, exc))

    for phase in ("formalizer", "writer", "realizer"):
        phase_rows[phase] = _phase_row(
            phase_plans.get(phase),
            phase_admissions.get(phase),
            error="unified_phase_not_compiled",
            candidate_admission=phase_admissions_candidate.get(phase),
        )
        failures.extend(phase_rows[phase].get("admission_failure_codes", ()))

    report_manifest = phase_manifests.get("realizer") or phase_manifests.get("writer") or workset_manifest
    unique_page_count = len(report_manifest.unique_page_ids) if report_manifest is not None else 0
    unique_tokens = report_manifest.total_token_estimate if report_manifest is not None else 0
    sent_tokens = sum(
        sum(
            phase_manifest.page_by_id(item.page_id).token_estimate
            for item in plan.invocations
            if phase_manifest.page_by_id(item.page_id) is not None
        )
        for phase, plan in phase_plans.items()
        for phase_manifest in (phase_manifests.get(phase),)
        if phase_manifest is not None
    )
    phase_statuses = [phase_rows[phase]["status"] for phase in ("formalizer", "writer", "realizer")]
    status = "pass" if not failures and all(value == "pass" for value in phase_statuses) else "fail"
    return {
        "project": project_id,
        "input_root": str(root),
        "status": status,
        "failure_codes": list(dict.fromkeys(str(item) for item in failures if str(item))),
        "failure_details": failure_details,
        "source": {
            "status": "pass" if not source_failures else "fail",
            "rehydration": source_rehydration,
            "snapshot_id": str(getattr(snapshot, "snapshot_id", "") or ""),
            "project_tree_hash": str(getattr(snapshot, "project_tree_hash", "") or ""),
            "manifest_digest": str(getattr(manifest, "content_digest", "") or ""),
            "behavior_graph_rebuild": source.get("behavior_graph_rebuild", {}),
        },
        "research": {
            "status": "pass" if not research_failures else "fail",
            "context_origin": context_origin,
            "context_rebuild_diagnostics": list(context_rebuild_diagnostics),
            "compatibility": list(research.get("compatibility", ()) or ()),
            "mechanism_count": len(getattr(contexts, "contexts", ()) or ()) if contexts is not None else 0,
            "seed_count": int(mechanism_diagnostics.get("mechanism_count", 0)) if mechanism_diagnostics else 0,
            "ownerless_count": int(mechanism_diagnostics.get("core_ownerless_count", 0)) if mechanism_diagnostics else 0,
            "owner_conflict_count": int(mechanism_diagnostics.get("core_owner_conflict_count", 0)) if mechanism_diagnostics else 0,
            "completeness_failures": completeness,
            "mechanism_diagnostics": mechanism_diagnostics,
            "deterministic_formula_packages": len(deterministic_formula_packages),
            # R2: strict and Candidate gate verdicts are reported side by side.
            # The row status above stays strict; the Candidate projection is an
            # explicit mode, never a silent relaxation.
            **research_gate_modes,
        },
        "archive": {
            "status": "pass" if archive is not None else "fail",
            "digest": str(getattr(archive, "content_digest", "") or ""),
            "atom_count": len(archive.all_atoms()) if archive is not None else 0,
            "serialized_bytes": len(canonical_json_bytes(archive.model_dump(mode="json"))) if archive is not None else 0,
        },
        "worksets": {
            "status": "pass" if workset_manifest is not None else "fail",
            "page_count": len(report_manifest.pages) if report_manifest is not None else 0,
            "unique_page_count": unique_page_count,
            "workset_count": len(report_manifest.worksets) if report_manifest is not None else 0,
            "unique_tokens": unique_tokens,
            "sent_tokens": sent_tokens,
            "send_duplication_ratio": sent_tokens / max(1, unique_tokens),
        },
        "budget": {
            "profile_digest": profile_digest,
            "model_identity_digest": model_identity_digest,
            "model_context_tokens": model_context_tokens,
            "envelope_digest": str(getattr(envelope, "content_digest", "") or ""),
            "max_calls_by_role": dict(getattr(envelope, "max_calls_by_role", {}) or {}),
            "max_total_input_tokens": int(getattr(envelope, "max_total_input_tokens", 0) or 0),
        },
        "phases": phase_rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "projects",
        nargs="+",
        metavar="PROJECT=ROOT",
        help="one or more frozen/replay artifact roots",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        metavar="PROJECT=PATH",
        help=(
            "optional repository for a project with missing source artifacts; "
            "the frozen tree hash is checked before rebuilding"
        ),
    )
    parser.add_argument("--model-context-tokens", type=int, default=None)
    parser.add_argument("--max-attempts", type=int, default=2)
    args = parser.parse_args(argv)
    if args.max_attempts <= 0:
        parser.error("--max-attempts must be positive")

    repo_by_project: dict[str, Path] = {}
    for spec in args.repo:
        project_id, separator, raw_repo = spec.partition("=")
        if not separator or not project_id.strip() or not raw_repo.strip():
            parser.error(f"repository must use PROJECT=PATH syntax: {spec!r}")
        if project_id in repo_by_project:
            parser.error(f"duplicate repository mapping for project: {project_id!r}")
        repo_by_project[project_id] = Path(raw_repo).expanduser().resolve()

    reports: dict[str, Any] = {}
    for spec in args.projects:
        project_id, separator, raw_root = spec.partition("=")
        if not separator or not project_id.strip() or not raw_root.strip():
            parser.error(f"project must use PROJECT=ROOT syntax: {spec!r}")
        if project_id in reports:
            parser.error(f"duplicate project id: {project_id!r}")
        reports[project_id] = project_unified_offline(
            project_id,
            Path(raw_root).expanduser().resolve(),
            repo_path=repo_by_project.get(project_id),
            profile_path=(args.profile.expanduser().resolve() if args.profile else None),
            model_context_override=args.model_context_tokens,
            max_attempts=args.max_attempts,
        )

    passed = sum(1 for report in reports.values() if report["status"] == "pass")
    summary = {
        "schema_version": "unified_ten_project_offline_matrix_v1",
        "model_calls_allowed": False,
        "project_count": len(reports),
        "passed_projects": passed,
        "failed_projects": len(reports) - passed,
        "all_pass": bool(reports) and passed == len(reports),
        "projects": reports,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
