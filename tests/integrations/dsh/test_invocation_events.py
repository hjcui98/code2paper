"""DSH facts exercise the original run budget and recovery owners.

These initial journal tests are unit coverage; the worker RPC matrix is added
with invocation_adapter wiring and cannot be inferred from these tests.
"""
import json
from types import SimpleNamespace

import pytest

from code2paper.agentic.digest import digest_json
from code2paper.agentic.unified_context_models import DshInvocationEventV1
from code2paper.agentic.unified_invocation_ledger import (
    publish_dsh_invocation_event, read_dsh_invocation_events,
    read_run_budget_state, check_run_budget_before_send,
)
from code2paper.agentic.writer_attempt_ledger import reduce_invocation_recovery
from code2paper.integrations.dsh.artifacts import ArtifactStore, TaskScope
from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
from code2paper.integrations.dsh.protocol import parse_model
from code2paper.agentic.digest import canonical_json_bytes
from .test_composition_identity import composition
from .stage04_support import durable_material, start_worker, prepare_and_claim
from code2paper.integrations.dsh.invocation_adapter import _assembly_material

INVOCATION = "inv:dsh:writer:one"


def test_real_rpc_default_zero_usage_cannot_discharge_a_sent_reservation(rpc_worker):
    child,facade,_,_,request,_=rpc_worker
    reservation=child.call("request.reserve",request)["result"]
    params={key:request[key] for key in ("execution_id","task_id","task_epoch","contract_ref")}|{"reservation":reservation}
    for kind in ("dispatch-recorded","adapter-attempt"):
        assert "result" in child.call("request.dispatch",{**params,"event_id":"error:"+kind,"kind":kind})
    ledger=facade.store.root/"artifacts/06_authoring/invocations"
    before=read_run_budget_state(ledger)
    usage=facade.store.put_json({"schema_version":"DshAdapterUsageV1","request_digest":reservation["request_digest"],
        "input_tokens":0,"output_tokens":0,"source":"adapter-usage"})
    refused=child.call("request.settle",{**params,"event_id":"error:default-usage","kind":"usage",
        "evidence_ref":usage.model_dump(mode="json"),"usage_input_tokens":0,"usage_output_tokens":0})
    assert refused["error"]["message"]=="dsh_provider_usage_unobserved"
    assert read_run_budget_state(ledger)==before
    assert before["pending_call_count"]==1 and before["pending_input_tokens"]>0
    assert before["spent_input_tokens"]==0 and before["completed_call_count"]==0


def test_real_rpc_zero_input_with_observed_output_is_retained_as_usage(rpc_worker):
    child,facade,_,_,request,_=rpc_worker
    reservation=child.call("request.reserve",request)["result"]
    params={key:request[key] for key in ("execution_id","task_id","task_epoch","contract_ref")}|{"reservation":reservation}
    for kind in ("dispatch-recorded","adapter-attempt"):
        assert "result" in child.call("request.dispatch",{**params,"event_id":"cached:"+kind,"kind":kind})
    evidence=facade.store.put_json({"schema_version":"DshAdapterUsageV1","request_digest":reservation["request_digest"],
        "input_tokens":0,"output_tokens":3,"source":"adapter-usage"})
    observed=child.call("request.settle",{**params,"event_id":"cached:usage","kind":"usage",
        "evidence_ref":evidence.model_dump(mode="json"),"usage_input_tokens":0,"usage_output_tokens":3})
    assert "result" in observed
    ledger=facade.store.root/"artifacts/06_authoring/invocations"
    facts=read_dsh_invocation_events(ledger,reservation["request_id"])
    assert facts[-1].kind=="usage" and facts[-1].usage_input_tokens==0 and facts[-1].usage_output_tokens==3
    budget=read_run_budget_state(ledger)
    assert budget["pending_call_count"]==1 and budget["completed_call_count"]==0


@pytest.mark.parametrize("reason",["error","aborted","length","unknown"])
def test_real_rpc_non_natural_finish_cannot_be_a_completed_observation(rpc_worker,reason):
    child,facade,_,_,request,_=rpc_worker
    reservation=child.call("request.reserve",request)["result"]
    params={key:request[key] for key in ("execution_id","task_id","task_epoch","contract_ref")}|{"reservation":reservation}
    for kind in ("dispatch-recorded","adapter-attempt"):
        assert "result" in child.call("request.dispatch",{**params,"event_id":"error:"+kind,"kind":kind})
    usage=facade.store.put_json({"schema_version":"DshAdapterUsageV1","request_digest":reservation["request_digest"],
        "input_tokens":40,"output_tokens":3,"source":"adapter-usage"})
    assert "result" in child.call("request.settle",{**params,"event_id":"error:actual-usage","kind":"usage",
        "evidence_ref":usage.model_dump(mode="json"),"usage_input_tokens":40,"usage_output_tokens":3})
    raw=facade.store.put(b"partial",media_type="text/plain")
    session=facade.store.put_json({"schema_version":"UNIT-partial-error-session"})
    evidence=facade.store.put_json({"schema_version":"DshFinishObservationV1","request_digest":reservation["request_digest"],
        "finish_reason":reason,"stream_complete":True,"raw_ref":raw.model_dump(mode="json"),
        "session_ref":session.model_dump(mode="json")})
    ledger=facade.store.root/"artifacts/06_authoring/invocations";before=read_run_budget_state(ledger)
    refused=child.call("request.settle",{**params,"event_id":"error:terminal","kind":"terminal",
        "evidence_ref":evidence.model_dump(mode="json")})
    assert refused["error"]["message"]=="dsh_finish_evidence_invalid"
    assert read_run_budget_state(ledger)==before and before["pending_call_count"]==1


def test_assembly_transport_normalization_is_frozen_and_preserves_all_content():
    expected={"messages":[{"id":"first","createdAt":1,"role":"user","content":[{"type":"text","text":"正文"}]}],"maxTokens":10}
    actual={"messages":[{"id":"second","createdAt":2,"role":"user","content":[{"type":"text","text":"正文"}]}],"maxTokens":10}
    assert _assembly_material(actual,[]) != _assembly_material(expected,[])
    whitelist=["messages.id","messages.createdAt"]
    assert _assembly_material(actual,whitelist) == _assembly_material(expected,whitelist)
    actual["messages"][0]["content"][0]["text"]="changed"
    assert _assembly_material(actual,whitelist) != _assembly_material(expected,whitelist)
    assert expected["messages"][0]["id"] == "first"


@pytest.fixture
def journal(tmp_path):
    root = tmp_path / "artifacts" / "06_authoring" / "invocations"
    store = ArtifactStore(tmp_path, TaskScope("execution:test", "task:writer", 0))
    evidence = store.put_json({"test_only_observation": True}).model_dump(mode="json")
    base = dict(invocation_id=INVOCATION, attempt=1, execution_id="execution:test", task_id="task:writer",
        task_epoch=0, claim_digest=digest_json("claim"), request_digest=digest_json("request"),
        contract_digest=digest_json("contract"), plan_digest=digest_json("plan"), consumer_role="writer")
    def append(kind, **updates):
        values = dict(base, event_id=f"event:{kind}", kind=kind,
            source="kernel" if kind in {"reserve", "settlement"} else "host-adapter")
        if kind == "reserve":
            values.update(reserved_input_tokens=100, reserved_output_tokens=20)
        if kind in {"usage", "terminal", "dispatch-confirmed", "proven-not-sent", "settlement"}:
            values["evidence_ref"] = evidence
        if kind in {"send-outcome-unknown", "cancel"}:
            values["reason"] = "test disconnected"
        values.update(updates)
        event = DshInvocationEventV1(**values)
        return publish_dsh_invocation_event(root, event)
    return tmp_path, root, append


def test_reserve_crash_retains_budget_and_is_unknown_in_original_reducer(journal):
    run, root, append = journal
    append("reserve")
    assert read_run_budget_state(root)["pending_input_tokens"] == 100
    assert read_run_budget_state(root)["call_count"] == 1
    state = reduce_invocation_recovery(run, INVOCATION)
    assert state.state == "send_outcome_unknown"
    assert state.unknown_reservation_attempts == (1,)
    assert "silently_retry" in state.forbidden_actions


def test_dispatch_record_is_not_http_proof_and_missing_usage_is_not_zero(journal):
    run, root, append = journal
    append("reserve")
    append("dispatch-recorded")
    assert reduce_invocation_recovery(run, INVOCATION).counters.provider_send_count == 0
    append("adapter-attempt")
    append("send-outcome-unknown")
    assert read_run_budget_state(root)["pending_input_tokens"] == 100
    assert read_run_budget_state(root)["provider_usage_missing_call_count"] == 1
    assert reduce_invocation_recovery(run, INVOCATION).counters.provider_send_count == 1
    with pytest.raises(ValueError, match="dsh_new_dispatch_after_stop_or_unknown|dsh_event_kind_duplicate"):
        append("adapter-attempt", event_id="second:attempt")


def test_usage_idempotence_and_local_settlement_preserve_fees_without_acceptance(journal):
    run, root, append = journal
    for kind in ("reserve", "dispatch-recorded", "adapter-attempt", "terminal"):
        append(kind)
    usage = append("usage", usage_input_tokens=70, usage_output_tokens=4)
    assert append("usage", usage_input_tokens=70, usage_output_tokens=4) == usage
    with pytest.raises(ValueError, match="dsh_event_id_conflict"):
        append("usage", usage_input_tokens=71, usage_output_tokens=4)
    assert read_run_budget_state(root)["pending_input_tokens"] == 100
    assert reduce_invocation_recovery(run, INVOCATION).state == "response_received_unsettled"
    append("settlement")
    state = read_run_budget_state(root)
    assert state["spent_input_tokens"] == 70
    assert state["pending_input_tokens"] == 0
    assert state["call_count"] == 1
    recovery = reduce_invocation_recovery(run, INVOCATION)
    assert recovery.state == "validation_pending"
    assert not recovery.accepted
    assert len(read_dsh_invocation_events(root, INVOCATION)) == 6


def test_positive_unsent_evidence_releases_reserve_and_conflicting_observation_refuses(journal):
    run, root, append = journal
    append("reserve")
    append("proven-not-sent")
    assert read_run_budget_state(root)["call_count"] == 0
    assert read_run_budget_state(root)["pending_input_tokens"] == 0
    assert reduce_invocation_recovery(run, INVOCATION).primary_cause == "dsh_proven_not_sent"
    with pytest.raises(ValueError, match="dsh_request_already_final"):
        append("dispatch-recorded")


def test_corrupt_event_is_fail_closed_for_budget_and_recovery(journal):
    run, root, append = journal
    path = append("reserve")
    payload = json.loads(path.read_text())
    payload["event"]["reserved_input_tokens"] = 0
    path.write_text(json.dumps(payload))
    assert read_run_budget_state(root)["status"] == "fail"
    assert reduce_invocation_recovery(run, INVOCATION).state == "ledger_corrupt"


def test_original_budget_checks_see_dsh_reservation_and_zero_call_budget(journal):
    _, root, append = journal
    append("reserve")
    envelope = SimpleNamespace(max_calls_by_role={"writer": 0}, max_total_input_tokens=100,
        max_input_tokens_by_role={"writer": 100})
    failures = check_run_budget_before_send(root, envelope, role="writer", request_input_tokens=100,
        current_reserved_input_tokens=100, current_attempt_recorded=True)
    assert any("calls:writer:1>0" in code for code in failures)
    envelope.max_calls_by_role["writer"] = 1
    assert not check_run_budget_before_send(root, envelope, role="writer", request_input_tokens=100,
        current_reserved_input_tokens=100, current_attempt_recorded=True)


def test_cross_epoch_event_and_settlement_without_usage_are_rejected(journal):
    _, _, append = journal
    append("reserve")
    with pytest.raises(ValueError, match="dsh_event_binding_conflict"):
        append("dispatch-recorded", task_epoch=1)
    with pytest.raises(ValueError, match="dsh_settlement_without_terminal_usage"):
        append("settlement")


@pytest.fixture
def rpc_worker(tmp_path,composition):
    facade,contract,frozen,projection,budget_ref,bootstrap=durable_material(tmp_path,composition)
    child=start_worker(bootstrap,facade)
    try:
        params,claim,contract_ref=prepare_and_claim(child,facade,contract,frozen,projection)
        wire_evidence=facade.store.read_json(projection.wire_equivalence_ref)
        actual_ref=wire_evidence["loop_request_ref"]
        request={**params,"contract_ref":contract_ref,"budget_ref":budget_ref.model_dump(mode="json"),
            "actual_request_ref":actual_ref,"event_id":"reserve:primary"}
        yield child,facade,contract,claim,request,bootstrap
    finally:
        if not child.process.stderr.closed:
            child.close()


def test_real_rpc_reserve_repeat_unknown_keeps_fee_and_new_request_refuses(rpc_worker):
    child,facade,contract,_,request,_=rpc_worker
    result=child.call("request.reserve",request)
    assert "result" in result,result
    reservation=result["result"]
    assert child.call("request.reserve",request)["result"] == reservation
    params={key:request[key] for key in ("execution_id","task_id","task_epoch","contract_ref")}
    dispatch=child.call("request.dispatch",{**params,"reservation":reservation,"event_id":"dispatch:one","kind":"dispatch-recorded"})
    assert "result" in dispatch,dispatch
    entered=child.call("request.dispatch",{**params,"reservation":reservation,"event_id":"adapter:one","kind":"adapter-attempt"})
    assert "result" in entered,entered
    # An event RPC retry cannot mint a second transport permit.
    again=child.call("request.dispatch",{**params,"reservation":reservation,"event_id":"adapter:one","kind":"adapter-attempt"})
    assert again["error"]["message"] == "dsh_adapter_permit_already_consumed"
    unknown=child.call("request.mark_unknown",{**params,"reservation":reservation,"event_id":"unknown:one",
        "kind":"send-outcome-unknown","reason":"connection-lost"})
    assert unknown["result"]["recovery"]["state"] == "send_outcome_unknown"
    ledger=facade.store.root / "artifacts" / "06_authoring" / "invocations"
    assert read_run_budget_state(ledger)["pending_input_tokens"] > 0
    retry=child.call("request.reserve",{**request,"event_id":"reserve:retry"})
    assert retry["error"]["message"] == "dsh_epoch_request_already_reserved"


def test_real_rpc_wrong_assembly_and_missing_dependency_refuse_before_reserve(rpc_worker):
    child,facade,_,_,request,_=rpc_worker
    bad=facade.store.put_json({"messages":[],"tools":[]})
    response=child.call("request.reserve",{**request,"actual_request_ref":bad.model_dump(mode="json")})
    assert response["error"]["message"] == "dsh_actual_assembly_mismatch"
    ref=ArtifactRefV1.model_validate_json(canonical_json_bytes(request["actual_request_ref"]))
    (facade.store.directory/ref.artifact_id.removeprefix("sha256:")).unlink()
    response=child.call("request.reserve",request)
    assert response["error"]["message"] == "artifact_unavailable"
    assert read_run_budget_state(facade.store.root / "artifacts" / "06_authoring" / "invocations")["call_count"] == 0


def test_real_rpc_cancelled_claim_and_wrong_epoch_do_not_reserve(rpc_worker):
    child,facade,_,claim,request,_=rpc_worker
    wrong=child.call("request.reserve",{**request,"task_epoch":1})
    assert wrong["error"]["message"] == "rpc_scope_mismatch"
    cancelled=child.call("task.cancel",{key:request[key] for key in ("execution_id","task_id","task_epoch")}|{"claim":claim})
    assert "result" in cancelled,cancelled
    refused=child.call("request.reserve",request)
    assert refused["error"]["message"] == "task_mutation_closed"


def test_real_rpc_cancel_is_original_journal_fact_and_epoch_limits_do_not_restart(rpc_worker):
    child,facade,_,claim,request,_=rpc_worker
    scoped={key:request[key] for key in ("execution_id","task_id","task_epoch")}
    before=child.call("task.limits",{**scoped,"claim":claim})["result"]
    assert before["epoch_started_ms"] == claim["epoch_started_ms"]
    assert before["epoch_limits"]["max_wall_seconds"] == 120
    reservation=child.call("request.reserve",request)["result"]
    result=child.call("task.cancel",{**scoped,"claim":claim})
    assert "result" in result,result
    assert child.call("task.cancel",{**scoped,"claim":claim})["result"] == result["result"]
    facts=read_dsh_invocation_events(facade.store.root / "artifacts" / "06_authoring" / "invocations",reservation["request_id"])
    assert [fact.kind for fact in facts] == ["reserve","cancel"]
    assert child.call("task.limits",{**scoped,"claim":claim})["result"] == before
    assert read_run_budget_state(facade.store.root / "artifacts" / "06_authoring" / "invocations")["pending_call_count"] == 1


def test_real_rpc_restart_cannot_turn_existing_reserve_into_dispatch(rpc_worker):
    child,facade,_,claim,request,bootstrap=rpc_worker
    reservation=child.call("request.reserve",request)["result"]
    child.close()
    restarted=start_worker(bootstrap,facade)
    try:
        resumed=restarted.call("task.resume",{key:request[key] for key in ("execution_id","task_id","task_epoch")}|{"claim":claim})
        assert "result" in resumed,resumed
        response=restarted.call("request.dispatch",{key:request[key] for key in ("execution_id","task_id","task_epoch","contract_ref")}
            |{"reservation":reservation,"event_id":"dispatch:after-crash","kind":"dispatch-recorded"})
        assert response["error"]["message"] == "dsh_recovery_cannot_redispatch"
    finally:
        restarted.close()


def test_real_rpc_lost_claim_can_rebind_only_original_local_facts(rpc_worker):
    child,facade,_,claim,request,bootstrap=rpc_worker
    reservation=child.call("request.reserve",request)["result"]
    child.close()
    restarted=start_worker(bootstrap,facade)
    scoped={key:request[key] for key in ("execution_id","task_id","task_epoch")}
    try:
        response=restarted.call("task.recover",{**scoped,"owner":"host:new-recovery"})
        assert "result" in response,response
        recovered=response["result"]
        assert recovered["claim_fence"] == claim["claim_fence"]+1
        assert recovered["epoch_started_ms"] == claim["epoch_started_ms"]
        rejected=restarted.call("request.reserve",request)
        assert rejected["error"]["message"] == "task_recovery_cannot_dispatch"
        rejected=restarted.call("request.dispatch",{**scoped,"contract_ref":request["contract_ref"],
            "reservation":reservation,"event_id":"recovered:dispatch","kind":"dispatch-recorded"})
        assert rejected["error"]["message"] == "dsh_recovery_cannot_redispatch"
        unknown=restarted.call("request.mark_unknown",{**scoped,"contract_ref":request["contract_ref"],
            "reservation":reservation,"event_id":"recovered:unknown","kind":"send-outcome-unknown","reason":"original-response-lost"})
        assert "result" in unknown,unknown
        assert unknown["result"]["recovery"]["state"] == "send_outcome_unknown"
        assert read_run_budget_state(facade.store.root / "artifacts" / "06_authoring" / "invocations")["pending_call_count"] == 1
    finally:
        restarted.close()


def test_real_rpc_ledger_write_failure_cannot_return_send_permission(rpc_worker):
    child,facade,_,_,request,_=rpc_worker
    ledger=facade.store.root / "artifacts" / "06_authoring" / "invocations"
    ledger.parent.mkdir(parents=True,exist_ok=True)
    ledger.write_bytes(b"filesystem blocker")
    response=child.call("request.reserve",request)
    assert response["error"]["message"] == "dsh_reserve_persistence_failed"


def test_real_rpc_completed_prior_spend_exhausts_current_reserve(rpc_worker):
    child,facade,_,claim,request,_=rpc_worker
    ledger=facade.store.root / "artifacts" / "06_authoring" / "invocations"
    plan=facade.store.read_json(ArtifactRefV1.model_validate_json(canonical_json_bytes(request["contract_ref"])))
    budget=facade.store.read_json(ArtifactRefV1.model_validate_json(canonical_json_bytes(request["budget_ref"])))
    evidence=facade.store.put_json({"scope":"unit prior completed cost fixture"}).model_dump(mode="json")
    base=dict(invocation_id="inv:prior:cost",attempt=1,execution_id=request["execution_id"],task_id=request["task_id"],
        task_epoch=0,claim_digest=digest_json(claim),request_digest=digest_json("prior-request"),
        contract_digest=plan["task_digest"],plan_digest=digest_json("prior-plan"),consumer_role="writer")
    # The prior provider response is an explicitly controlled accounting
    # fixture. The current reservation is evaluated by the real worker.
    for kind in ("reserve","dispatch-recorded","adapter-attempt","usage","terminal","settlement"):
        values=dict(base,event_id="prior:"+kind,kind=kind,source="kernel" if kind in {"reserve","settlement"} else "host-adapter")
        if kind == "reserve": values.update(reserved_input_tokens=budget["max_total_input_tokens"],reserved_output_tokens=1)
        if kind == "usage": values.update(usage_input_tokens=budget["max_total_input_tokens"],usage_output_tokens=1)
        if kind in {"usage","terminal","settlement"}: values["evidence_ref"]=evidence
        publish_dsh_invocation_event(ledger,DshInvocationEventV1(**values))
    response=child.call("request.reserve",request)
    assert "unified_invocation_budget_exceeded" in response["error"]["message"]
    assert read_run_budget_state(ledger)["call_count"] == 1


def test_real_rpc_usage_duplicate_and_format_failure_settle_cost_without_acceptance(rpc_worker):
    child,facade,_,_,request,_=rpc_worker
    response=child.call("request.reserve",request)
    assert "result" in response,response
    reservation=response["result"]
    params={key:request[key] for key in ("execution_id","task_id","task_epoch","contract_ref")}|{"reservation":reservation}
    for kind in ("dispatch-recorded","adapter-attempt"):
        result=child.call("request.dispatch",{**params,"event_id":"format-failure:"+kind,"kind":kind})
        assert "result" in result,result
    usage_ref=facade.store.put_json({"schema_version":"DshAdapterUsageV1","request_digest":reservation["request_digest"],
        "input_tokens":40,"output_tokens":3,"source":"adapter-usage"})
    usage={**params,"event_id":"usage:format-failure","kind":"usage","evidence_ref":usage_ref.model_dump(mode="json"),
        "usage_input_tokens":40,"usage_output_tokens":3}
    result=child.call("request.settle",usage)
    assert "result" in result,result
    assert child.call("request.settle",usage)["result"] == result["result"]
    bad=child.call("request.settle",{**usage,"usage_input_tokens":41})
    assert bad["error"]["message"] == "dsh_usage_evidence_mismatch"
    raw=facade.store.put(b"not a valid Writer terminal")
    session=facade.store.put(b"unit actual-observation fixture; not a V01 Session")
    finish=facade.store.put_json({"schema_version":"DshFinishObservationV1","request_digest":reservation["request_digest"],
        "finish_reason":"stop","stream_complete":True,"raw_ref":raw.model_dump(mode="json"),"session_ref":session.model_dump(mode="json")})
    for kind in ("terminal","settlement"):
        result=child.call("request.settle",{**params,"event_id":"format-failure:"+kind,"kind":kind,"evidence_ref":finish.model_dump(mode="json")})
        assert "result" in result,result
    state=read_run_budget_state(facade.store.root / "artifacts" / "06_authoring" / "invocations")
    assert state["spent_input_tokens"] == 40
    assert state["pending_input_tokens"] == 0
    assert not result["result"]["recovery"]["accepted"]
    assert facade.task_store.read()["receipt"] is None


def test_real_rpc_session_bound_receipt_replays_in_new_worker_without_second_fee(rpc_worker):
    """UNIT Session capture, actual worker/ledger/publication, no V01 claim."""
    child,facade,_,claim,request,bootstrap=rpc_worker
    reservation=child.call("request.reserve",request)["result"]
    params={key:request[key] for key in ("execution_id","task_id","task_epoch","contract_ref")}
    for kind in ("dispatch-recorded","adapter-attempt"):
        response=child.call("request.dispatch",{**params,"reservation":reservation,"event_id":"receipt:"+kind,"kind":kind})
        assert "result" in response,response
    usage_ref=facade.store.put_json({"schema_version":"DshAdapterUsageV1","request_digest":reservation["request_digest"],
        "input_tokens":40,"output_tokens":3,"source":"adapter-usage"})
    response=child.call("request.settle",{**params,"reservation":reservation,"event_id":"usage:receipt","kind":"usage",
        "evidence_ref":usage_ref.model_dump(mode="json"),"usage_input_tokens":40,"usage_output_tokens":3})
    assert "result" in response,response
    raw=json.dumps({"schema_version":"WriterTaskResultV1","result":{"outcome":"blocked","reason":"controlled unit refusal",
        "recovery_action":"new scoped task"}})
    raw_ref=facade.store.put(raw.encode()).model_dump(mode="json")
    capture={**{key:request[key] for key in ("execution_id","task_id","task_epoch")},"schema_version":"DshRawCaptureV1",
        "child_id":facade.context.child_id,"session_id":facade.context.session_id,"request_id":reservation["request_id"],
        "tool_call_id":"call:actual","stream_index":1,"source":"adapter_tool_arguments_delta",
        "arguments_completion":"block-ended","arguments_ref":raw_ref}
    captured=child.call("task.capture_raw",{key:request[key] for key in ("execution_id","task_id","task_epoch")}|{"capture":capture})
    assert "result" in captured,captured
    session=facade.store.put_json({"schema_version":"DshSessionCaptureV1","session_id":facade.context.session_id,
        "format_version":"SessionFileV4","events":[{"type":"tool/call","data":{"turn":0,"step":1,"callId":"call:actual",
        "name":"c2p_terminal","arguments":raw}},{"type":"tool/result","data":{"turn":0,"step":1,
        "message":{"role":"tool","toolCallId":"call:actual","isError":False}}},
        {"type":"turn/end","data":{"turn":0,"reason":{"kind":"completed"}}}]})
    envelope=dict(schema_version="OutputEnvelopeV1",**facade.context.scope.__dict__,child_id=facade.context.child_id,
        session_id=facade.context.session_id,turn_id=0,step_id=1,tool_call_id="call:actual",request_id=reservation["request_id"],
        source="adapter_tool_arguments_delta",arguments_complete=True,provider_http={"status":"not_observed","ref":None},
        adapter_arguments={"status":"observed","ref":raw_ref},normalized_arguments={"status":"observed","ref":raw_ref},
        stop_reason="completed",usage=None,session_capture_ref=session.model_dump(mode="json"))
    incomplete=facade.store.read_json(session)
    incomplete["events"]=incomplete["events"][:1]
    incomplete_ref=facade.store.put_json(incomplete)
    refused=child.call("task.record_output",{**params,"envelope":{**envelope,"session_capture_ref":incomplete_ref.model_dump(mode="json")}})
    assert refused["error"]["message"] == "durable_session_terminal_not_completed"
    bad=child.call("task.record_output",{**params,"envelope":{**envelope,"turn_id":2}})
    assert bad["error"]["message"] == "output_provenance_mismatch"
    response=child.call("task.record_output",{**params,"envelope":envelope})
    assert "result" in response,response
    output=response["result"]
    status=child.call("request.status",params)["result"]
    assert status["recorded_output_ref"] == output
    assert status["reservation"] == reservation
    key=child.call("task.ingest_key",{**params,"output_ref":output})["result"]["idempotency_key"]
    ingest_params={**params,"output_ref":output,"idempotency_key":key}
    response=child.call("task.ingest",ingest_params)
    assert "result" in response,response
    receipt=response["result"]
    assert receipt["domain_status"] == "blocked"
    child.close()
    restarted=start_worker(bootstrap,facade)
    try:
        resumed=restarted.call("task.recover",{key:request[key] for key in ("execution_id","task_id","task_epoch")}|{"owner":"host:receipt-recovery"})
        assert "result" in resumed,resumed
        replay=restarted.call("task.ingest",ingest_params)
        assert replay.get("result") == receipt,replay
        state=read_run_budget_state(facade.store.root / "artifacts" / "06_authoring" / "invocations")
        assert state["spent_input_tokens"] == 40
        assert state["call_count"] == 1
    finally:
        restarted.close()
