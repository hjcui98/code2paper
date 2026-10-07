"""V2 epoch admission derived exclusively from original invocation facts.

No spend, refund or token balance is stored here. Caller holds the original
run lease through admission and reserve publication. Unknown/unfinished facts
retain their original reservations across children and process restarts.
"""
from __future__ import annotations

import time

from code2paper.agentic.unified_invocation_ledger import (
    read_dsh_invocation_events, read_run_budget_state,
)
from .protocol import ProtocolError
from .writer_contract import WriterTaskContractV2


def epoch_requests(ledger_root, contract: WriterTaskContractV2):
    state = read_run_budget_state(ledger_root)
    if state['failure_codes']:
        raise ProtocolError('dsh_run_ledger_invalid')
    requests = []
    for directory in sorted(ledger_root.iterdir()) if ledger_root.is_dir() else ():
        if not directory.is_dir():
            continue
        files = sorted(directory.glob('attempt-0001.dsh-event-*.json'))
        if not files:
            continue
        from .protocol import strict_json_loads
        record = strict_json_loads(files[0].read_bytes())
        facts = read_dsh_invocation_events(ledger_root, record['invocation_id'])
        first = facts[0]
        if (first.execution_id, first.task_id, first.task_epoch) != (
                contract.execution_id, contract.task_id, contract.task_epoch):
            continue
        if not facts or facts[0].contract_digest != contract.task_digest:
            raise ProtocolError('dsh_epoch_contract_conflict')
        requests.append(facts)
    return tuple(requests)


def epoch_totals(ledger_root, contract: WriterTaskContractV2) -> dict:
    """Spent plus still committed liabilities; no usage is never zero cost."""
    calls = input_tokens = output_tokens = pending = 0
    for facts in epoch_requests(ledger_root, contract):
        kinds = {fact.kind for fact in facts}
        if 'proven-not-sent' in kinds:
            continue
        calls += 1
        usage = next((fact for fact in facts if fact.kind == 'usage'), None)
        if 'settlement' in kinds:
            input_tokens += usage.usage_input_tokens
            output_tokens += usage.usage_output_tokens
        else:
            pending += 1
            input_tokens += max(facts[0].reserved_input_tokens, usage.usage_input_tokens if usage else 0)
            output_tokens += max(facts[0].reserved_output_tokens, usage.usage_output_tokens if usage else 0)
    return {'model_requests': calls, 'input_tokens': input_tokens,
            'output_tokens': output_tokens, 'pending_requests': pending}


def assert_epoch_admission(ledger_root, contract: WriterTaskContractV2, *,
                           epoch_started_ms: int, input_tokens: int,
                           output_tokens: int, now_ms: int | None = None) -> dict:
    if not isinstance(contract, WriterTaskContractV2):
        raise ProtocolError('multistep_contract_required')
    if (type(input_tokens) is not int or type(output_tokens) is not int
            or input_tokens <= 0 or output_tokens <= 0):
        raise ProtocolError('dsh_epoch_request_amount_invalid')
    current = time.time_ns() // 1_000_000 if now_ms is None else now_ms
    if (type(epoch_started_ms) is not int or type(current) is not int
            or current < epoch_started_ms
            or current - epoch_started_ms >= contract.epoch_limits.max_wall_seconds * 1000):
        raise ProtocolError('dsh_epoch_deadline_exceeded')
    totals = epoch_totals(ledger_root, contract)
    limits = contract.epoch_limits
    if totals['pending_requests']:
        raise ProtocolError('dsh_epoch_has_unsettled_request')
    if totals['model_requests'] >= limits.max_model_requests:
        raise ProtocolError('dsh_epoch_request_budget_exceeded')
    if totals['input_tokens'] + input_tokens > limits.max_input_tokens:
        raise ProtocolError('dsh_epoch_input_budget_exceeded')
    if totals['output_tokens'] + output_tokens > limits.max_output_tokens:
        raise ProtocolError('dsh_epoch_output_budget_exceeded')
    return totals
