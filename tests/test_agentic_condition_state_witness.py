"""Copular switch wording must preserve the complete condition contract."""

import pytest

from code2paper.agentic.condition_structure import condition_statement_matches


@pytest.mark.parametrize("state", ["enabled", "active"])
def test_explicit_positive_switch_state(state: str) -> None:
    assert condition_statement_matches(
        "cfg.enable_fusion",
        f"When the fusion configuration flag is {state}, combine the inputs.",
    )


@pytest.mark.parametrize("witness", [
    "When the fusion configuration flag is not active, combine the inputs.",
    "When the fusion configuration flag is inactive, combine the inputs.",
    "When the fusion configuration flag is active or fallback holds, combine the inputs.",
    "When fallback holds or the fusion configuration flag is active, combine the inputs.",
    "The fusion configuration flag is active. Combine the inputs unconditionally.",
    "When another configuration flag is active, combine the inputs.",
    "When fusion is active.member, combine the inputs.",
])
def test_state_wording_does_not_drop_conditions(witness: str) -> None:
    assert not condition_statement_matches("cfg.enable_fusion", witness)


def test_active_operand_is_preserved() -> None:
    assert condition_statement_matches("active > threshold", "When active > threshold, continue.")
    assert not condition_statement_matches("active > threshold", "When threshold > active, continue.")
