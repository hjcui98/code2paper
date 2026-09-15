"""Repository-verified definition values for branch-gating configuration keys.

The first real Candidate blocker was a configuration value the frozen research
input never resolved: ``if self.cfg.use_dedicated_attention:`` gates the
ablation branch, the value is declared in ``conf/config.yaml``, but no fact
carried it -- so the access claim stayed ``unresolved`` and every operation on
the branch kept an unknown active path.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from code2paper.agentic.configuration_claims import compile_configuration_claims
from code2paper.agentic.configuration_definitions import (
    append_configuration_definition_facts,
)
from code2paper.agentic.generic_fact_compiler import (
    CodeFactSetV1,
    CodeFactV1,
    _digest,
)
from code2paper.agentic.repo_snapshot import RepoSnapshot, SnapshotFile


ACCESS_EXPRESSION = "self.cfg.use_dedicated_attention"


def _digest_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _snapshot(tmp_path: Path, files: dict[str, str]) -> RepoSnapshot:
    included: list[SnapshotFile] = []
    for path, text in files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        included.append(SnapshotFile(path=path, content_digest=_digest_text(text)))
    return RepoSnapshot(
        snapshot_id="repo:snapshot",
        project_root=str(tmp_path),
        project_tree_hash="sha256:" + "a" * 64,
        included_files=included,
    )


def _access_fact(*, predicate: str = "loads_weights") -> CodeFactV1:
    identity = _digest({"access": ACCESS_EXPRESSION, "predicate": predicate})
    return CodeFactV1(
        fact_id="fact-O-1-node:0000000000000001",
        subject="EBCarRerankerHybridAttention.forward",
        predicate=predicate,
        object=[ACCESS_EXPRESSION],
        scope="sym:f6cf5bdfe2ae16f0",
        direct_span_ids=[
            "span:src/model/ebcar_dedicated_attention_model.py:145:145"
        ],
        exact_source_digest=_digest(["span:src/model/ebcar_dedicated_attention_model.py:145:145"]),
        canonical_identity=identity,
        semantic_context=[
            "sym:f6cf5bdfe2ae16f0", "LOAD", ACCESS_EXPRESSION, "config_access", "attr_read",
        ],
        validation_status="supported",
    )


def _fact_set(*facts: CodeFactV1) -> CodeFactSetV1:
    return CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:" + "a" * 64,
        evidence_packet_digest="sha256:" + "b" * 64,
        facts=facts,
        content_digest="",
    )


def test_declared_configuration_value_becomes_a_resolved_default_claim(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot(tmp_path, {
        "src/model/ebcar_dedicated_attention_model.py": (
            "if self.cfg.use_dedicated_attention:\n"
            "    dedicated_attention_mask = torch.zeros(1)\n"
        ),
        "conf/config.yaml": (
            "model:\n"
            "  dropout: 0.1\n"
            "add_positional_encoding: True\n"
            "use_dedicated_attention: True\n"
        ),
    })
    fact_set = _fact_set(_access_fact())

    # Before: the access has no definition evidence.
    unresolved = compile_configuration_claims(fact_set)
    assert [(c.key, c.state, c.value) for c in unresolved.claims] == [
        (ACCESS_EXPRESSION, "unresolved", None)
    ]

    enriched = append_configuration_definition_facts(
        fact_set, repo_snapshot=snapshot
    )
    assert len(enriched.facts) == 2
    definition = enriched.facts[-1]
    assert definition.subject == ACCESS_EXPRESSION
    assert definition.predicate == "configured_by"
    # The fact object is the string contract; the claim restores the type.
    assert definition.object == "true"
    assert "definition_default" in definition.semantic_context
    assert definition.direct_span_ids == ["span:conf/config.yaml:4:4"]
    # The fact set keeps a valid content digest after the append.
    assert enriched.content_digest.startswith("sha256:")

    # After: the claim resolves with the declared value and the span that
    # carries it, which is what branch resolution consumes.
    resolved = compile_configuration_claims(enriched)
    assert [(c.key, c.state, c.value) for c in resolved.claims] == [
        (ACCESS_EXPRESSION, "default", True)
    ]
    assert resolved.claims[0].definition_span_ids == ("span:conf/config.yaml:4:4",)


def test_definition_fact_requires_owning_packet_span_when_constrained(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot(tmp_path, {
        "conf/config.yaml": "use_dedicated_attention: True\n",
    })
    fact_set = _fact_set(_access_fact())

    omitted = append_configuration_definition_facts(
        fact_set,
        repo_snapshot=snapshot,
        allowed_definition_span_ids=("span:other.yaml:1:1",),
    )
    assert omitted.facts == fact_set.facts

    included = append_configuration_definition_facts(
        fact_set,
        repo_snapshot=snapshot,
        allowed_definition_span_ids=("span:conf/config.yaml:1:1",),
    )
    assert len(included.facts) == 2
    assert included.facts[-1].direct_span_ids == ["span:conf/config.yaml:1:1"]


def test_ambiguous_or_non_scalar_definitions_stay_unresolved(
    tmp_path: Path,
) -> None:
    # Two files declare the same leaf with different values: no guessing.
    conflicting = _snapshot(tmp_path / "conflict", {
        "conf/config.yaml": "use_dedicated_attention: True\n",
        "conf/retrieval_model/e5.yaml": "use_dedicated_attention: False\n",
    })
    fact_set = _fact_set(_access_fact())
    assert append_configuration_definition_facts(
        fact_set, repo_snapshot=conflicting
    ).facts == fact_set.facts

    # A structured (non-scalar) value is not a definition default.
    structured = _snapshot(tmp_path / "structured", {
        "conf/config.yaml": "use_dedicated_attention:\n  nested: 1\n",
    })
    assert append_configuration_definition_facts(
        fact_set, repo_snapshot=structured
    ).facts == fact_set.facts

    # No declaration at all stays unresolved.
    absent = _snapshot(tmp_path / "absent", {
        "conf/config.yaml": "something_else: 1\n",
    })
    assert append_configuration_definition_facts(
        fact_set, repo_snapshot=absent
    ).facts == fact_set.facts


def test_digest_drift_and_non_configuration_partitions_are_not_evidence(
    tmp_path: Path,
) -> None:
    # A dataset-partition file may not define a value even if it declares the
    # leaf; the classifier decides, not the file name alone.
    snapshot = _snapshot(tmp_path / "partition", {
        "conf/config.yaml": "seed: 1\n",
        "data/real/ConTEB/config.yaml": "use_dedicated_attention: True\n",
    })
    fact_set = _fact_set(_access_fact())
    assert append_configuration_definition_facts(
        fact_set, repo_snapshot=snapshot
    ).facts == fact_set.facts

    # Digest drift invalidates the declaration: the bytes are not the frozen
    # bytes the snapshot recorded.
    drifted = _snapshot(tmp_path / "drift", {
        "conf/config.yaml": "use_dedicated_attention: True\n",
    })
    (tmp_path / "drift" / "conf" / "config.yaml").write_text(
        "use_dedicated_attention: False\n", encoding="utf-8"
    )
    assert append_configuration_definition_facts(
        fact_set, repo_snapshot=drifted
    ).facts == fact_set.facts


def test_an_already_resolved_access_is_not_redefined(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, {
        "conf/config.yaml": "use_dedicated_attention: True\n",
    })
    resolved_fact = _access_fact().model_copy(update={
        "semantic_context": [
            "sym:f6cf5bdfe2ae16f0", "LOAD", ACCESS_EXPRESSION, "config_access",
            "definition_default",
        ],
    })
    fact_set = _fact_set(resolved_fact)
    assert append_configuration_definition_facts(
        fact_set, repo_snapshot=snapshot
    ).facts == fact_set.facts


def test_only_the_bare_access_is_superseded_not_other_lanes() -> None:
    """Definition evidence retires the access record, nothing else."""

    from code2paper.agentic.configuration_claims import (
        ConfigurationClaimV1,
        _supersede_unresolved_accesses,
    )

    access = ConfigurationClaimV1(
        configuration_id="config:access",
        key=ACCESS_EXPRESSION,
        value=None,
        state="unresolved",
        unresolved_reason="config_access_unresolved:no_definition_or_entrypoint_value_evidence",
        source_authority="executable_hard",
    )
    default = ConfigurationClaimV1(
        configuration_id="config:default",
        key=ACCESS_EXPRESSION,
        value=True,
        state="default",
        definition_span_ids=("span:conf/config.yaml:4:4",),
        source_authority="executable_hard",
    )
    unreachable = ConfigurationClaimV1(
        configuration_id="config:unreachable",
        key="other.key",
        value="x",
        state="unreachable",
        active=False,
        unresolved_reason="fact_rejected:unreachable_from_entrypoint",
        source_authority="executable_hard",
    )
    merged = _supersede_unresolved_accesses([access, default, unreachable])
    assert [claim.configuration_id for claim in merged] == [
        "config:default", "config:unreachable",
    ]
    # Without definition evidence the access record stays.
    assert _supersede_unresolved_accesses([access, unreachable]) == [
        access, unreachable,
    ]
