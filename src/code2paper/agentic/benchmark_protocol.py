from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.benchmark_v2 import BenchmarkDatasetV2
from code2paper.agentic.benchmark_v2 import BenchmarkObservationV2
from code2paper.agentic.repo_snapshot import build_repo_snapshot


class ProtocolModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BenchmarkRunSpecV2(ProtocolModel):
    case_id: str
    variant: Literal["fixed_legacy", "agentic_deterministic", "agentic_gemma4_mtp"]
    intent_id: str = ""
    repeat_index: int = 1
    repo_root: str
    author_markers_path: str
    out_root: str
    run_id: str
    repo_snapshot_id: str
    repo_tree_hash: str
    model_id: str = ""
    llm_base_url: str = ""
    capability_profile_path: str = ""
    capability_profile_digest: str = ""
    prompt_version: str = "agentic-graph-v3"
    renderer: str = "structured-svg"
    temperature: float = 0.0
    budgets: dict[str, int] = Field(default_factory=dict)
    environment: dict[str, str] = Field(default_factory=dict)
    command: list[str]


class BenchmarkProtocolV2(ProtocolModel):
    schema_version: str = "2.0"
    producer_version: str = "code2paper-agentic-p4"
    gold_digest: str
    code_root: str
    workspace_commit: str
    clean_tracked_commit_required: bool = True
    scoped_dirty_exceptions: list[str] = Field(default_factory=list)
    specs: list[BenchmarkRunSpecV2]

    @model_validator(mode="after")
    def _validate_matrix(self) -> "BenchmarkProtocolV2":
        keys = [(s.case_id, s.variant, s.intent_id, s.repeat_index) for s in self.specs]
        if len(keys) != len(set(keys)):
            raise ValueError("benchmark protocol contains duplicate run identities")
        grouped: dict[tuple[str, str], list[BenchmarkRunSpecV2]] = {}
        for spec in self.specs:
            grouped.setdefault((spec.case_id, spec.intent_id), []).append(spec)
            if spec.variant == "agentic_gemma4_mtp" and spec.environment.get("CODE2PAPER_LLM_CACHE") != "0":
                raise ValueError("Gemma benchmark runs must disable the LLM cache")
            if spec.variant in {"fixed_legacy", "agentic_gemma4_mtp"}:
                if not spec.llm_base_url:
                    raise ValueError("model-backed benchmark runs require a frozen LLM base URL")
                parsed_url = urlsplit(spec.llm_base_url)
                if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
                    raise ValueError("model-backed benchmark LLM base URL must be an absolute HTTP(S) URL")
                if parsed_url.username or parsed_url.password or parsed_url.query or parsed_url.fragment:
                    raise ValueError("model-backed benchmark LLM base URL must not contain credentials, query, or fragment")
                if spec.environment.get("CODE2PAPER_OPENAI_BASE_URL") != spec.llm_base_url:
                    raise ValueError("model-backed benchmark environment must load the frozen LLM base URL")
                if not spec.capability_profile_path or not spec.capability_profile_digest:
                    raise ValueError("model-backed benchmark runs require a frozen capability profile")
                if spec.environment.get("CODE2PAPER_LLM_CAPABILITY_PROFILE") != spec.capability_profile_path:
                    raise ValueError("model-backed benchmark environment must load the frozen capability profile")
        for key, items in grouped.items():
            variants = {item.variant for item in items}
            if variants != {"fixed_legacy", "agentic_deterministic", "agentic_gemma4_mtp"}:
                raise ValueError(f"incomplete benchmark variants for {key}")
            repeats = {item.repeat_index for item in items if item.variant == "agentic_gemma4_mtp"}
            if repeats != {1, 2, 3}:
                raise ValueError(f"Gemma repeat matrix must be exactly 1,2,3 for {key}")
            snapshots = {item.repo_snapshot_id for item in items}
            if len(snapshots) != 1:
                raise ValueError(f"variant snapshot mismatch for {key}")
        return self


def build_benchmark_protocol_v2(
    dataset: BenchmarkDatasetV2,
    *,
    workspace_root: str | Path,
    code_root: str | Path | None = None,
    out_root: str | Path,
    author_markers: dict[tuple[str, str], str | Path],
    workspace_commit: str,
    model_id: str,
    llm_base_url: str,
    capability_profile_digest: str,
    capability_profile_path: str | Path,
    budgets: dict[str, int] | None = None,
) -> BenchmarkProtocolV2:
    root = Path(workspace_root).resolve()
    clean_code_root = Path(code_root or workspace_root).resolve()
    destination = Path(out_root).resolve()
    profile_path = Path(capability_profile_path).resolve()
    if not profile_path.is_file():
        raise ValueError(f"capability profile not found:{profile_path}")
    actual_profile_digest = "sha256:" + hashlib.sha256(profile_path.read_bytes()).hexdigest()
    if capability_profile_digest != actual_profile_digest:
        raise ValueError("capability profile digest does not match the frozen profile file")
    normalized_base_url = llm_base_url.strip().rstrip("/")
    parsed_url = urlsplit(normalized_base_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
        raise ValueError("LLM base URL must be an absolute HTTP(S) URL")
    if parsed_url.username or parsed_url.password or parsed_url.query or parsed_url.fragment:
        raise ValueError("LLM base URL must not contain credentials, query, or fragment")
    effective_budgets = budgets or {
        "retrieval": 1, "evidence_revision": 1, "authoring_revision": 1,
        # The largest frozen case currently extracts seven factual claims. One
        # authoring revision can require a second independent validation pass,
        # so three calls made the formal Gemma matrix fail by construction.
        "figure_revision": 1, "semantic_verifier_calls": 16,
    }
    specs: list[BenchmarkRunSpecV2] = []
    for case in dataset.cases:
        repo = (root / case.repo_root).resolve()
        snapshot = build_repo_snapshot(repo)
        intents = [item.intent_id for item in case.intents] or [""]
        for intent_id in intents:
            marker_key = (case.case_id, intent_id)
            if marker_key not in author_markers:
                raise ValueError(f"missing author markers for {case.case_id}:{intent_id or 'default'}")
            author = Path(author_markers[marker_key]).resolve()
            for variant, repeats in (("fixed_legacy", (1,)), ("agentic_deterministic", (1,)), ("agentic_gemma4_mtp", (1, 2, 3))):
                for repeat in repeats:
                    slug = "-".join(filter(None, (case.case_id, intent_id, variant, f"r{repeat}")))
                    output = destination / slug
                    run_id = f"p4-{slug}"
                    command = _command(
                        variant=variant, repo=repo, author=author, output=output, run_id=run_id,
                        model_id=model_id, budgets=effective_budgets,
                    )
                    specs.append(BenchmarkRunSpecV2(
                        case_id=case.case_id,
                        variant=variant,
                        intent_id=intent_id,
                        repeat_index=repeat,
                        repo_root=str(repo),
                        author_markers_path=str(author),
                        out_root=str(output),
                        run_id=run_id,
                        repo_snapshot_id=snapshot.snapshot_id,
                        repo_tree_hash=snapshot.project_tree_hash,
                        model_id=model_id if variant in {"fixed_legacy", "agentic_gemma4_mtp"} else "",
                        llm_base_url=normalized_base_url if variant in {"fixed_legacy", "agentic_gemma4_mtp"} else "",
                        capability_profile_path=str(profile_path) if variant in {"fixed_legacy", "agentic_gemma4_mtp"} else "",
                        capability_profile_digest=capability_profile_digest if variant in {"fixed_legacy", "agentic_gemma4_mtp"} else "",
                        budgets=effective_budgets,
                        environment={
                            "CODE2PAPER_LLM_CACHE": "0",
                            "PYTHONPATH": str(clean_code_root / "src"),
                            **(
                                {
                                    "CODE2PAPER_LLM_CAPABILITY_PROFILE": str(profile_path),
                                    "CODE2PAPER_OPENAI_BASE_URL": normalized_base_url,
                                }
                                if variant in {"fixed_legacy", "agentic_gemma4_mtp"}
                                else {}
                            ),
                        },
                        command=command,
                    ))
    gold_payload = dataset.model_dump_json(exclude_none=False)
    return BenchmarkProtocolV2(
        gold_digest="sha256:" + hashlib.sha256(gold_payload.encode("utf-8")).hexdigest(),
        code_root=str(clean_code_root),
        workspace_commit=workspace_commit,
        specs=specs,
    )


def write_benchmark_protocol_v2(path: str | Path, protocol: BenchmarkProtocolV2) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(protocol.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return output


def load_benchmark_protocol_v2(path: str | Path) -> BenchmarkProtocolV2:
    return BenchmarkProtocolV2.model_validate_json(Path(path).read_text(encoding="utf-8"))


def benchmark_spec_digest(spec: BenchmarkRunSpecV2) -> str:
    payload = json_canonical(spec.model_dump(mode="json"))
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def validate_protocol_observations_v2(
    protocol: BenchmarkProtocolV2,
    observations: list[BenchmarkObservationV2],
) -> list[str]:
    failures: list[str] = []
    expected = {(s.case_id, s.variant, s.intent_id, s.repeat_index): s for s in protocol.specs}
    actual = {(o.case_id, o.variant, o.intent_id, o.repeat_index): o for o in observations}
    if len(expected) != len(protocol.specs):
        failures.append("protocol_contains_duplicate_run_identity")
    if len(actual) != len(observations):
        failures.append("observations_contain_duplicate_run_identity")
    if set(actual) != set(expected):
        failures.append("protocol_observation_matrix_mismatch")
    for key in sorted(set(expected) & set(actual)):
        spec = expected[key]
        observation = actual[key]
        if observation.provenance.get("protocol_spec_digest") != benchmark_spec_digest(spec):
            failures.append(f"protocol_spec_digest_mismatch:{':'.join(map(str, key))}")
        if observation.provenance.get("repo_snapshot_id") != spec.repo_snapshot_id:
            failures.append(f"protocol_repo_snapshot_mismatch:{':'.join(map(str, key))}")
        if spec.variant in {"fixed_legacy", "agentic_gemma4_mtp"}:
            if observation.provenance.get("model_id") != spec.model_id:
                failures.append(f"protocol_model_id_mismatch:{':'.join(map(str, key))}")
            if observation.provenance.get("capability_profile_digest") != spec.capability_profile_digest:
                failures.append(f"protocol_capability_profile_mismatch:{':'.join(map(str, key))}")
    return failures


def json_canonical(value: object) -> bytes:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _command(*, variant: str, repo: Path, author: Path, output: Path, run_id: str, model_id: str, budgets: dict[str, int]) -> list[str]:
    base = [
        "python", "-m", "code2paper.run_cli", str(repo), "--author", str(author),
        "--out-root", str(output), "--run-id", run_id,
    ]
    if variant == "fixed_legacy":
        return [
            *base, "--mode", "legacy", "--llm-provider", "openai", "--llm-model", model_id,
            "--figure-backend", "fallback", "--allow-fidelity-fail",
        ]
    provider = "none" if variant == "agentic_deterministic" else "openai"
    command = [
        *base, "--mode", "agentic", "--llm-provider", provider,
        "--max-retrieval-rounds", str(budgets["retrieval"]),
        "--max-evidence-revision-rounds", str(budgets["evidence_revision"]),
        "--max-authoring-revision-rounds", str(budgets["authoring_revision"]),
        "--max-figure-revision-rounds", str(budgets["figure_revision"]),
        "--max-semantic-verifier-calls", str(budgets["semantic_verifier_calls"]),
    ]
    if variant == "agentic_gemma4_mtp":
        command.extend(["--llm-model", model_id])
    return command
