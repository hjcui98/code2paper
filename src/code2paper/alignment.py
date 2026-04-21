"""Rule-based Phase 2 code alignment.

This module maps raw evidence into a conservative CodeAlignmentIR. It is not a
semantic proof engine yet; it creates auditable first-pass alignment objects
that later stages can refine.
"""

from __future__ import annotations

import ast
import json
import shlex
from pathlib import Path

import yaml

from .schemas import (
    AlignedModuleRole,
    AuthorAlignment,
    AuthorClaimAssessment,
    AuthorMarkers,
    ClaimSupportLevel,
    CodeAlignmentIR,
    ConfigResolution,
    ConfigResolutionStep,
    Entrypoint,
    EvidenceItem,
    ExecutionStage,
    MethodStageAlignment,
    ModuleCategory,
    RawEvidencePack,
    SourceType,
    StageMapping,
    SupportStatus,
)


def align_code(
    raw_pack: RawEvidencePack,
    *,
    author_markers: AuthorMarkers | None = None,
) -> CodeAlignmentIR:
    """Generate a first-pass CodeAlignmentIR from a RawEvidencePack."""

    evidence = list(raw_pack.evidence_items)
    entrypoints = _detect_entrypoints(evidence, author_markers=author_markers)
    execution_stages = _extract_execution_stages(evidence)
    method_stages = _extract_method_stages(evidence)
    stage_mappings = _map_stages(execution_stages, method_stages)
    config_resolutions = _extract_config_resolutions(raw_pack)
    module_roles = _align_module_roles(evidence)
    author_alignment = _align_author(author_markers, evidence, method_stages) if author_markers else AuthorAlignment()

    return CodeAlignmentIR(
        project_id=raw_pack.project_id,
        author_mode=raw_pack.author_mode,
        author_confirmation_required=raw_pack.author_confirmation_required,
        entrypoints=entrypoints,
        execution_stages=execution_stages,
        method_stages=method_stages,
        stage_mappings=stage_mappings,
        config_resolutions=config_resolutions,
        module_roles=module_roles,
        role_conflicts=[],
        author_alignment=author_alignment,
    )


def align_from_files(
    raw_evidence_path: str | Path,
    *,
    author_markers_path: str | Path | None = None,
) -> CodeAlignmentIR:
    raw_payload = json.loads(Path(raw_evidence_path).read_text(encoding="utf-8"))
    raw_pack = RawEvidencePack.model_validate(raw_payload)
    author_markers = None
    if author_markers_path:
        author_payload = yaml.safe_load(Path(author_markers_path).read_text(encoding="utf-8"))
        author_markers = AuthorMarkers.model_validate(author_payload)
    return align_code(raw_pack, author_markers=author_markers)


def _detect_entrypoints(evidence: list[EvidenceItem], *, author_markers: AuthorMarkers | None = None) -> list[Entrypoint]:
    entrypoints: list[Entrypoint] = []
    source_by_path_symbol = {(item.path, item.symbol): item for item in evidence if item.source_type == SourceType.SOURCE}
    priority_files = set(author_markers.priority_files if author_markers else [])
    for item in evidence:
        if item.source_type != SourceType.BASH or "entrypoint" not in item.tags:
            continue
        script = _extract_python_script(item.content_summary)
        if script:
            ids = [item.evidence_id]
            source_item = source_by_path_symbol.get((script, "main"))
            if source_item:
                ids.append(source_item.evidence_id)
            entrypoints.append(
                Entrypoint(
                    path=script,
                    symbol="main",
                    called_by=[item.path],
                    confidence=0.95 if source_item else 0.82,
                    evidence_ids=ids,
                )
            )

    for item in evidence:
        if item.source_type == SourceType.SOURCE and item.symbol == "main" and _looks_like_entrypoint_file(item.path):
            if priority_files and item.path not in priority_files:
                continue
            if any(existing.path == item.path and existing.symbol == "main" for existing in entrypoints):
                continue
            entrypoints.append(
                Entrypoint(
                    path=item.path,
                    symbol="main",
                    called_by=[],
                    confidence=0.78,
                    evidence_ids=[item.evidence_id],
                )
            )
    return entrypoints


def _extract_execution_stages(evidence: list[EvidenceItem]) -> list[ExecutionStage]:
    stages: list[ExecutionStage] = []

    launch_ids = [item.evidence_id for item in evidence if item.source_type == SourceType.BASH and "entrypoint" in item.tags]
    if launch_ids:
        stages.append(
            ExecutionStage(
                stage_id="X1",
                name="training_launch",
                description="Launch training through shell commands and runtime overrides.",
                related_evidence_ids=launch_ids,
            )
        )

    setup_ids = [
        item.evidence_id
        for item in evidence
        if item.source_type == SourceType.SOURCE and item.path == "train.py" and item.symbol == "main"
    ]
    if setup_ids:
        stages.append(
            ExecutionStage(
                stage_id=f"X{len(stages) + 1}",
                name="training_setup",
                description="Parse options, prepare data, construct the model, build the optimizer, and start training.",
                related_evidence_ids=setup_ids,
            )
        )

    update_ids = [
        item.evidence_id
        for item in evidence
        if item.source_type == SourceType.SOURCE
        and (item.symbol in {"train_epoch", "cal_performance", "cal_loss", "ScheduledOptim"} or "optimization" in item.tags)
    ]
    if update_ids:
        stages.append(
            ExecutionStage(
                stage_id=f"X{len(stages) + 1}",
                name="epoch_update",
                description="Run forward, loss computation, backpropagation, and scheduled parameter updates.",
                related_evidence_ids=_dedupe(update_ids),
            )
        )

    preprocess_ids = [
        item.evidence_id
        for item in evidence
        if item.source_type == SourceType.SOURCE and (item.path == "preprocess.py" or "preprocess" in item.tags)
    ]
    if preprocess_ids:
        stages.append(
            ExecutionStage(
                stage_id=f"X{len(stages) + 1}",
                name="preprocess_data",
                description="Prepare raw text data into serialized model-ready training data.",
                related_evidence_ids=_dedupe(preprocess_ids),
            )
        )

    return stages


def _extract_method_stages(evidence: list[EvidenceItem]) -> list[MethodStageAlignment]:
    stages: list[MethodStageAlignment] = []

    input_ids = [
        item.evidence_id
        for item in evidence
        if item.source_type == SourceType.SOURCE and (item.path == "preprocess.py" or "data" in item.tags or "preprocess" in item.tags)
    ]
    if input_ids:
        stages.append(
            MethodStageAlignment(
                stage_id="M1",
                name="input_preparation",
                purpose="Prepare tokenized and serialized data for training.",
                related_evidence_ids=_dedupe(input_ids),
            )
        )

    model_ids = [
        item.evidence_id
        for item in evidence
        if item.source_type == SourceType.SOURCE
        and (
            item.path.startswith("transformer/")
            or "attention" in item.tags
            or "model" in item.tags
            or item.symbol in {"EncoderLayer", "DecoderLayer", "MultiHeadAttention", "PositionwiseFeedForward"}
        )
    ]
    if model_ids:
        stages.append(
            MethodStageAlignment(
                stage_id=f"M{len(stages) + 1}",
                name="transformer_computation",
                purpose="Compute sequence representations through Transformer layers and sublayers.",
                related_evidence_ids=_dedupe(model_ids),
            )
        )

    optim_ids = [
        item.evidence_id
        for item in evidence
        if item.source_type == SourceType.SOURCE
        and (item.symbol in {"train_epoch", "cal_loss", "cal_performance", "ScheduledOptim"} or "optimization" in item.tags)
    ]
    bash_train_ids = [
        item.evidence_id
        for item in evidence
        if item.source_type == SourceType.BASH and ("train" in item.tags or "shell_override" in item.tags)
    ]
    if optim_ids or bash_train_ids:
        stages.append(
            MethodStageAlignment(
                stage_id=f"M{len(stages) + 1}",
                name="scheduled_optimization",
                purpose="Optimize model parameters with loss computation, optional label smoothing, and learning-rate scheduling.",
                related_evidence_ids=_dedupe(bash_train_ids + optim_ids),
            )
        )

    return stages


def _map_stages(
    execution_stages: list[ExecutionStage],
    method_stages: list[MethodStageAlignment],
) -> list[StageMapping]:
    method_by_name = {stage.name: stage for stage in method_stages}
    mappings: list[StageMapping] = []
    for execution in execution_stages:
        target_name = None
        if execution.name == "preprocess_data":
            target_name = "input_preparation"
        elif execution.name == "training_setup":
            target_name = "transformer_computation"
        elif execution.name == "epoch_update":
            target_name = "scheduled_optimization"
        elif execution.name == "training_launch":
            target_name = "scheduled_optimization"
        if target_name and target_name in method_by_name:
            mappings.append(
                StageMapping(
                    execution_stage_id=execution.stage_id,
                    method_stage_id=method_by_name[target_name].stage_id,
                    confidence=0.88 if execution.name != "training_launch" else 0.78,
                )
            )
    return mappings


def _align_module_roles(evidence: list[EvidenceItem]) -> list[AlignedModuleRole]:
    roles: list[AlignedModuleRole] = []
    for item in evidence:
        if item.source_type != SourceType.SOURCE or not item.symbol:
            continue
        category = _module_category(item)
        role = _module_role(item)
        roles.append(
            AlignedModuleRole(
                path=item.path,
                symbol=item.symbol,
                role=role,
                category=category,
                confidence=_role_confidence(category),
                evidence_ids=[item.evidence_id],
            )
        )
    return roles


def _align_author(
    author_markers: AuthorMarkers,
    evidence: list[EvidenceItem],
    method_stages: list[MethodStageAlignment],
) -> AuthorAlignment:
    evidence_paths = {item.path for item in evidence}
    evidence_by_id = {item.evidence_id: item for item in evidence}
    evidence_symbols = {item.symbol for item in evidence if item.symbol}
    evidence_by_path = {}
    evidence_by_symbol = {}
    for item in evidence:
        evidence_by_path.setdefault(item.path, []).append(item)
        if item.symbol:
            evidence_by_symbol.setdefault(item.symbol, []).append(item)
    method_stage_names = {stage.name.replace("_", " ").lower() for stage in method_stages}
    matched_steps: list[str] = []
    mismatched_steps: list[str] = []
    expected_flow = author_markers.paper_story_order or [step.name for step in author_markers.pipeline_steps]
    related_files_by_step = {step.name: step.related_files for step in author_markers.pipeline_steps}
    stage_paths_by_id = {
        stage.stage_id: {
            evidence_by_id[eid].path
            for eid in stage.related_evidence_ids
            if eid in evidence_by_id
        }
        for stage in method_stages
    }
    preferred_method_stage_ids: list[str] = []
    for step_name in expected_flow:
        related_match = any(path in evidence_paths for path in related_files_by_step.get(step_name, []))
        name_match = step_name.lower() in method_stage_names
        if related_match or name_match:
            matched_steps.append(step_name)
        else:
            mismatched_steps.append(step_name)
        stage_id = _match_story_step_to_method_stage_id(
            step_name=step_name,
            related_files=related_files_by_step.get(step_name, []),
            method_stages=method_stages,
            stage_paths_by_id=stage_paths_by_id,
        )
        if stage_id and stage_id not in preferred_method_stage_ids:
            preferred_method_stage_ids.append(stage_id)

    unsupported_claims: list[str] = []
    claim_assessments: list[AuthorClaimAssessment] = []
    claim_specs = [
        {
            "claim": claim.claim,
            "supporting_files": claim.supporting_files,
            "supporting_functions": claim.supporting_functions,
            "caveats": claim.caveats,
        }
        for claim in author_markers.innovation_claims
    ] + [
        {
            "claim": intent.intent,
            "supporting_files": intent.supporting_files,
            "supporting_functions": intent.supporting_functions,
            "caveats": intent.caveats + ([intent.rationale] if intent.rationale else []),
        }
        for intent in author_markers.design_intents
    ]
    for claim in claim_specs:
        file_matches = [
            item
            for path in claim["supporting_files"]
            for item in evidence_by_path.get(path, [])
            if item.source_type == SourceType.SOURCE
        ]
        symbol_matches = [
            item
            for symbol in claim["supporting_functions"]
            for item in evidence_by_symbol.get(symbol, [])
            if item.source_type == SourceType.SOURCE
            and (not claim["supporting_files"] or item.path in claim["supporting_files"])
        ]
        if symbol_matches:
            support_status = SupportStatus.SUPPORTED
            support_level = ClaimSupportLevel.SYMBOL
            matched_items = symbol_matches
        elif file_matches:
            support_status = SupportStatus.PARTIAL
            support_level = ClaimSupportLevel.FILE
            matched_items = file_matches
        else:
            support_status = SupportStatus.UNSUPPORTED
            support_level = ClaimSupportLevel.NONE
            matched_items = []
            unsupported_claims.append(claim["claim"])
        claim_assessments.append(
            AuthorClaimAssessment(
                claim_text=claim["claim"],
                support_status=support_status,
                support_level=support_level,
                supporting_files=[path for path in claim["supporting_files"] if path in evidence_paths],
                supporting_functions=[symbol for symbol in claim["supporting_functions"] if symbol in evidence_symbols],
                evidence_ids=_dedupe([item.evidence_id for item in matched_items]),
                caveats=claim["caveats"],
            )
        )
    return AuthorAlignment(
        matched_steps=matched_steps,
        mismatched_steps=mismatched_steps,
        unsupported_claims=unsupported_claims,
        author_story_order=expected_flow,
        preferred_method_stage_ids=preferred_method_stage_ids,
        latex_expression_preference=author_markers.latex_expression_preference,
        claim_assessments=claim_assessments,
    )


def _match_story_step_to_method_stage_id(
    *,
    step_name: str,
    related_files: list[str],
    method_stages: list[MethodStageAlignment],
    stage_paths_by_id: dict[str, set[str]],
) -> str:
    normalized_step = _normalize_text(step_name)
    if not normalized_step:
        return ""
    # prefer explicit file overlap when author provided related files
    if related_files:
        related = set(related_files)
        for stage in method_stages:
            if stage_paths_by_id.get(stage.stage_id, set()).intersection(related):
                return stage.stage_id
    for stage in method_stages:
        stage_name = _normalize_text(stage.name.replace("_", " "))
        stage_purpose = _normalize_text(stage.purpose)
        if normalized_step == stage_name or normalized_step in stage_name or stage_name in normalized_step:
            return stage.stage_id
        if normalized_step in stage_purpose:
            return stage.stage_id
    keyword_map = (
        ("input_preparation", ("preprocess", "token", "data")),
        ("transformer_computation", ("transformer", "attention", "encoder", "decoder", "representation")),
        ("scheduled_optimization", ("optim", "schedule", "loss", "update", "train")),
    )
    for stage in method_stages:
        for expected_name, keywords in keyword_map:
            if stage.name != expected_name:
                continue
            if any(keyword in normalized_step for keyword in keywords):
                return stage.stage_id
    return ""


def _normalize_text(value: str) -> str:
    lowered = value.lower().replace("_", " ").replace("-", " ")
    return " ".join(lowered.split())


def _extract_config_resolutions(raw_pack: RawEvidencePack) -> list[ConfigResolution]:
    project_root = Path(raw_pack.project_root)
    defaults, alias_to_key, default_evidence_id = _extract_argparse_defaults(raw_pack, project_root / "train.py")
    resolutions: dict[str, ConfigResolution] = {}
    for item in raw_pack.evidence_items:
        if item.source_type != SourceType.BASH or not item.shell_command_segment:
            continue
        for key, value in _extract_env_overrides(item.shell_command_segment).items():
            resolutions[f"env.{key}"] = ConfigResolution(
                resolved_key=f"env.{key}",
                final_value=value,
                resolution_chain=[
                    ConfigResolutionStep(
                        source=f"{item.path} {key}",
                        value=value,
                        evidence_id=item.evidence_id,
                        kind="env_override",
                    )
                ],
            )
        for alias, value in _extract_shell_overrides(item.shell_command_segment).items():
            key = alias_to_key.get(alias.strip("-"))
            if key is None:
                continue
            final_value = _coerce_value(value, defaults.get(key))
            chain: list[ConfigResolutionStep] = []
            if key in defaults:
                chain.append(
                    ConfigResolutionStep(
                        source="train.py argparse default",
                        value=defaults[key],
                        evidence_id=default_evidence_id,
                        kind="argparse_default",
                    )
                )
            chain.append(
                ConfigResolutionStep(
                    source=f"{item.path} {alias}",
                    value=final_value,
                    evidence_id=item.evidence_id,
                    kind="shell_override",
                )
            )
            resolutions[key] = ConfigResolution(
                resolved_key=key,
                final_value=final_value,
                resolution_chain=chain,
            )
    return list(resolutions.values())


def _extract_env_overrides(command: str) -> dict[str, object]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    overrides: dict[str, object] = {}
    for token in tokens:
        if token in {"python", "python3"} or token.endswith(".py"):
            break
        if "=" not in token or token.startswith("-"):
            continue
        key, value = token.split("=", 1)
        if key:
            overrides[key] = value
    return overrides


def _extract_argparse_defaults(raw_pack: RawEvidencePack, train_path: Path) -> tuple[dict[str, object], dict[str, str], str | None]:
    defaults: dict[str, object] = {}
    alias_to_key: dict[str, str] = {}
    default_evidence_id = next(
        (
            item.evidence_id
            for item in raw_pack.evidence_items
            if item.source_type == SourceType.SOURCE and item.path == "train.py" and item.symbol == "main"
        ),
        None,
    )
    if not train_path.exists():
        return defaults, alias_to_key, default_evidence_id
    try:
        tree = ast.parse(train_path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return defaults, alias_to_key, default_evidence_id
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "add_argument":
            continue
        aliases = [arg.value for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
        if not aliases:
            continue
        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        key = _argparse_key(aliases, kwargs)
        default = _argparse_default(kwargs)
        defaults[key] = default
        for alias in aliases:
            alias_to_key[alias.lstrip("-").replace("-", "_")] = key
    return defaults, alias_to_key, default_evidence_id


def _argparse_key(aliases: list[str], kwargs: dict[str, ast.AST]) -> str:
    dest = kwargs.get("dest")
    if isinstance(dest, ast.Constant) and isinstance(dest.value, str):
        return dest.value.replace("-", "_")
    long_aliases = [alias for alias in aliases if alias.startswith("--")]
    chosen = long_aliases[-1] if long_aliases else aliases[-1]
    return chosen.lstrip("-").replace("-", "_")


def _argparse_default(kwargs: dict[str, ast.AST]) -> object:
    action = kwargs.get("action")
    if isinstance(action, ast.Constant) and action.value == "store_true":
        return False
    default = kwargs.get("default")
    if default is None:
        return None
    try:
        return ast.literal_eval(default)
    except Exception:
        return None


def _extract_shell_overrides(command: str) -> dict[str, object]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    overrides: dict[str, object] = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("-") and not token.startswith("--="):
            if "=" in token:
                alias, value = token.split("=", 1)
                overrides[alias] = value
            elif index + 1 < len(tokens) and not tokens[index + 1].startswith("-"):
                overrides[token] = tokens[index + 1]
                index += 1
            else:
                overrides[token] = True
        index += 1
    return overrides


def _coerce_value(value: object, default: object) -> object:
    if isinstance(value, bool):
        return value
    if default is None:
        return value
    if isinstance(default, bool):
        if isinstance(value, str):
            return value.lower() not in {"0", "false", "no", "off"}
        return bool(value)
    if isinstance(default, int) and isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return value
    if isinstance(default, float) and isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return value
    return value


def _module_category(item: EvidenceItem) -> ModuleCategory:
    lowered = f"{item.path}::{item.symbol or ''}".lower()
    tags = {tag.lower() for tag in item.tags}
    core_score = 0
    support_score = 0
    infra_score = 0

    if any(token in lowered for token in ("forward", "attention", "encoder", "decoder", "loss", "gradient", "backprop")):
        core_score += 3
    if any(token in tags for token in ("model", "attention", "optimization")):
        core_score += 2
    if any(token in lowered for token in ("train", "eval", "preprocess", "dataloader", "dataset", "entrypoint")):
        support_score += 2
    if any(token in tags for token in ("train", "preprocess", "data")):
        support_score += 2
    if any(token in lowered for token in ("util", "helper", "logger", "metric", "io", "config", "setup", "download")):
        infra_score += 2
    if any(token in lowered for token in ("file_exist", "exists", "mkdir", "path", "load", "save", "read", "write", "seed")):
        infra_score += 5
        support_score = max(0, support_score - 1)
    if "call_chain" in tags:
        support_score += 1
    if "method_flow" in tags:
        core_score += 1
    if item.symbol and "." in item.symbol:
        core_score += 1

    if core_score >= max(support_score, infra_score):
        return ModuleCategory.METHOD_CORE
    if support_score >= infra_score:
        return ModuleCategory.EXPERIMENT_SUPPORT
    return ModuleCategory.INFRA_UTILITY


def _module_role(item: EvidenceItem) -> str:
    lowered = f"{item.path}::{item.symbol or ''}".lower()
    tags = {tag.lower() for tag in item.tags}
    if "call_chain" in tags:
        return "call-chain flow relation"
    if any(token in lowered for token in ("forward", "attention", "encoder", "decoder")):
        return "model computation block"
    if any(token in lowered for token in ("loss", "gradient", "optim", "schedule", "update", "train_epoch")):
        return "optimization and objective logic"
    if any(token in lowered for token in ("preprocess", "dataset", "dataloader", "token")):
        return "data preparation and loading"
    if any(token in lowered for token in ("main", "entry", "launch", "runner", "pipeline")):
        return "entrypoint orchestration"
    if any(token in lowered for token in ("eval", "metric", "inference", "predict")):
        return "evaluation or inference utility"
    if any(token in lowered for token in ("config", "argparse", "cli")):
        return "configuration and runtime wiring"
    return "infrastructure utility"


def _role_confidence(category: ModuleCategory) -> float:
    if category == ModuleCategory.METHOD_CORE:
        return 0.9
    if category == ModuleCategory.EXPERIMENT_SUPPORT:
        return 0.78
    return 0.65


def _extract_python_script(summary: str) -> str | None:
    words = summary.replace(":", " ").split()
    for index, word in enumerate(words):
        if word == "python" and index + 1 < len(words):
            candidate = words[index + 1]
            if candidate.endswith(".py"):
                return candidate
    for word in words:
        if word.endswith(".py"):
            return word
    return None


def _looks_like_entrypoint_file(path: str) -> bool:
    return Path(path).name in {"train.py", "preprocess.py", "translate.py", "main.py", "run.py"}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
