"""Private DSH facts bridge into the original budget and recovery owners.

No transport or model call runs here. A reserve returns only after the frozen
materials, actual assembly, claim, epoch and current whole-run budget pass.
"""
from __future__ import annotations

import time
from typing import Any

from code2paper.agentic.authoring_execution_identity import scoped_run_lease
from code2paper.agentic.digest import canonical_json_bytes, digest_json
from code2paper.agentic.unified_context_models import (
    ConsumerInvocationPlanV1, DshInvocationEventV1, RunInvocationBudgetEnvelopeV1,
)
from code2paper.agentic.unified_invocation_ledger import (
    check_run_budget_before_send, publish_dsh_invocation_event, read_dsh_invocation_events,
    read_run_budget_state, register_invocation_plan,
)
from code2paper.agentic.writer_attempt_ledger import reduce_invocation_recovery
from .facade import WriterFacade
from .protocol import ProtocolError, parse_model
from .writer_contract import ArtifactRefV1, WriterWireProjectionV1, WriterMeasurementV1, parse_writer_contract


def _assembly_material(value, whitelist):
    """Remove only the frozen, enumerated non-material transport fields."""
    if not isinstance(value,dict):
        raise ProtocolError("dsh_actual_assembly_mismatch")
    result=dict(value)
    for field in ("signal","sessionId"):
        if "request."+field in whitelist:
            result.pop(field,None)
    messages=result.get("messages")
    if isinstance(messages,list):
        result["messages"]=[{key:item for key,item in message.items()
            if not (key in {"id","createdAt"} and "messages."+key in whitelist)}
            if isinstance(message,dict) else message for message in messages]
    return result


class InvocationAdapter:
    def __init__(self, facade: WriterFacade):
        if facade.task_store is None or facade.context.claim_mode != "dsh-durable-claim/1":
            raise ProtocolError("durable_claim_required")
        self.facade = facade
        self.root = facade.store.root / "artifacts" / "06_authoring" / "invocations"

    def _contract(self, ref: ArtifactRefV1):
        return parse_writer_contract(canonical_json_bytes(self.facade.store.read_json(ref)))

    def _bound_plan(self, contract, *, recorded_request_id=None):
        if contract.schema_version=='WriterTaskContractV2' and recorded_request_id is not None:
            from .step_admission import LoopPlanV2
            facts=read_dsh_invocation_events(self.root,recorded_request_id)
            if (not facts or facts[0].contract_digest!=contract.task_digest
                    or (facts[0].execution_id,facts[0].task_id,facts[0].task_epoch)!=(contract.execution_id,contract.task_id,contract.task_epoch)):
                raise ProtocolError('dsh_reservation_binding_mismatch')
            evidence=self.facade.store.read_json(parse_model(canonical_json_bytes(facts[0].evidence_ref),ArtifactRefV1))
            if evidence.get('schema_version')!='DshReserveEvidenceV2':raise ProtocolError('dsh_step_evidence_required')
            plan=parse_model(canonical_json_bytes(self.facade.store.read_json(parse_model(canonical_json_bytes(evidence['loop_plan_ref']),ArtifactRefV1))),LoopPlanV2)
            rows=[row for row in plan.invocations if row.invocation_id==recorded_request_id and row.role==facts[0].consumer_role and row.role in {'writer','compaction'} and not row.is_repair]
            if len(rows)!=1 or plan.contract_digest!=contract.task_digest or plan.content_digest!=facts[0].plan_digest:
                raise ProtocolError('dsh_invocation_plan_scope_invalid')
            return plan,rows[0]
        plan = ConsumerInvocationPlanV1.model_validate_json(canonical_json_bytes(self.facade.store.read_json(contract.plan_ref)))
        if recorded_request_id is None:
            section = self.facade.store.read_json(contract.private_input_ref)
            rows = [row for row in plan.invocations if not row.is_repair and row.role == "writer"
                    and row.page_id == section["prompt_payload"]["unified_v2_page_id"]]
        else:
            # Local replay/settlement uses the original durable request binding.
            # New sends still validate the complete section/read-set below.
            rows = [row for row in plan.invocations if not row.is_repair and row.role == "writer"
                    and row.invocation_id == recorded_request_id]
        if len(rows) != 1:
            raise ProtocolError("dsh_invocation_plan_scope_invalid")
        return plan, rows[0]

    def _deadline(self, contract):
        view = self.facade.task_store.authorize(self.facade.claim)
        now_ms = time.time_ns() // 1_000_000
        elapsed = now_ms - view["epoch_started_ms"]
        if elapsed < 0 or elapsed >= contract.epoch_limits.max_wall_seconds * 1000:
            raise ProtocolError("dsh_epoch_deadline_exceeded")

    def reserve(self, *, contract_ref: ArtifactRefV1, budget_ref: ArtifactRefV1,
                actual_request_ref: ArtifactRefV1, event_id: str) -> dict[str, Any]:
        facade = self.facade
        with scoped_run_lease(facade.store.root, execution_id=facade.context.scope.execution_id, blocking=True):
            facade.authorize()
            facade.task_store.authorize(facade.claim,require_execute=True)
            facade.verify_composition()
            contract = self._contract(contract_ref)
            if contract.schema_version!='WriterTaskContractV1':raise ProtocolError('dsh_measured_step_required')
            facade.check_contract_current(contract)
            view = facade.task_store.read()
            if view["prepared"]["contract_ref"] != contract_ref.model_dump(mode="json"):
                raise ProtocolError("dsh_task_contract_ref_mismatch")
            self._deadline(contract)
            closure = facade.verify_contract_dependencies(contract)
            actual = facade.store.read_json(actual_request_ref)
            expected = facade.store.read_json(parse_model(canonical_json_bytes(closure["dependencies"]["loop_request"]),ArtifactRefV1))
            projection = parse_model(canonical_json_bytes(facade.store.read_json(contract.dsh_wire_contract_ref)),WriterWireProjectionV1)
            equivalence=facade.store.read_json(projection.wire_equivalence_ref)
            whitelist=equivalence["transport_whitelist"]
            if digest_json(_assembly_material(actual,whitelist)) != digest_json(_assembly_material(expected,whitelist)):
                raise ProtocolError("dsh_actual_assembly_mismatch")
            plan, invocation = self._bound_plan(contract)
            envelope = RunInvocationBudgetEnvelopeV1.model_validate_json(canonical_json_bytes(facade.store.read_json(budget_ref)))
            if (envelope.content_digest != plan.envelope_digest or envelope.profile_digest != plan.profile_digest
                    or envelope.model_identity_digest != plan.model_identity_digest
                    or envelope.profile_digest != contract.identity.profile_digest
                    or envelope.model_identity_digest != contract.identity.model_digest):
                raise ProtocolError("dsh_budget_envelope_binding_mismatch")
            measured = parse_model(canonical_json_bytes(facade.store.read_json(projection.measurement_ref)),WriterMeasurementV1)
            # Exact tokens were remeasured in the dependency closure above.
            request_digest = digest_json(actual)
            reserve_evidence = facade.store.put_json({"schema_version":"DshReserveEvidenceV1",
                "budget_ref":budget_ref.model_dump(mode="json"),"actual_request_ref":actual_request_ref.model_dump(mode="json")})
            values = dict(event_id=event_id, kind="reserve", invocation_id=invocation.invocation_id, attempt=1,
                execution_id=contract.execution_id, task_id=contract.task_id, task_epoch=contract.task_epoch,
                claim_digest=digest_json(facade.claim), request_digest=request_digest,
                contract_digest=contract.task_digest, plan_digest=plan.content_digest,
                consumer_role="writer", source="kernel", reserved_input_tokens=measured.measured_input_tokens,
                reserved_output_tokens=contract.post_clamp_max_output_tokens,evidence_ref=reserve_evidence.model_dump(mode="json"))
            event = DshInvocationEventV1(**values)
            facts = read_dsh_invocation_events(self.root, invocation.invocation_id)
            if facts:
                if facts[0] == event and len(facts) == 1:
                    # The same private RPC response can be recovered. It does
                    # not create a new request, epoch, or transport fact.
                    return self._reservation(facts[0])
                raise ProtocolError("dsh_epoch_request_already_reserved")
            state = read_run_budget_state(self.root)
            if state["failure_codes"]:
                raise ProtocolError("dsh_run_ledger_invalid")
            if state["pending_call_count"]:
                raise ProtocolError("dsh_run_has_unsettled_request")
            try:
                register_invocation_plan(self.root, plan)
            except OSError as error:
                raise ProtocolError("dsh_reserve_persistence_failed") from error
            failures = check_run_budget_before_send(self.root, envelope, role="writer",
                request_input_tokens=event.reserved_input_tokens, current_attempt_recorded=False,
                invocation_id=invocation.invocation_id)
            if failures:
                raise ProtocolError(failures[0])
            try:
                publish_dsh_invocation_event(self.root, event)
            except OSError as error:
                raise ProtocolError("dsh_reserve_persistence_failed") from error
            # Caller receives no permission if write/readback failed.
            if read_dsh_invocation_events(self.root, invocation.invocation_id) != (event,):
                raise ProtocolError("dsh_reserve_readback_failed")
            return self._reservation(event)

    @staticmethod
    def _reservation(event):
        return {"schema_version":"DshReservationV1", "request_id":event.invocation_id,
            "reservation_id":event.content_digest, "request_digest":event.request_digest,
            "contract_digest":event.contract_digest, "claim_digest":event.claim_digest}

    def reservation(self, contract_ref: ArtifactRefV1, *, allow_missing: bool = False):
        contract=self._contract(contract_ref)
        source=self.facade.task_store.read()['captured_source']
        request_id=source['request_id'] if source else None
        if contract.schema_version=='WriterTaskContractV2' and request_id is None:
            from .epoch_accounting import epoch_requests
            from .auxiliary_admission import parse_step
            requests=epoch_requests(self.root,contract);steps=[]
            for facts in requests:
                evidence=self.facade.store.read_json(parse_model(canonical_json_bytes(facts[0].evidence_ref),ArtifactRefV1))
                if evidence.get('schema_version')!='DshReserveEvidenceV2':raise ProtocolError('dsh_step_evidence_required')
                step=parse_step(self.facade.store.read_json(parse_model(canonical_json_bytes(evidence['step_ref']),ArtifactRefV1)))
                steps.append((step.sequence,facts[0].invocation_id))
            if steps:
                if sorted(row[0] for row in steps)!=list(range(1,len(steps)+1)):raise ProtocolError('dsh_step_sequence_mismatch')
                request_id=max(steps)[1]
        _,invocation=self._bound_plan(contract,recorded_request_id=request_id)
        facts=read_dsh_invocation_events(self.root,invocation.invocation_id)
        if not facts:
            if allow_missing: return None
            raise ProtocolError("dsh_reservation_required")
        if (not self.facade.task_store.accepts_recorded_claim(self.facade.claim,facts[0].claim_digest)
                or facts[0].contract_digest != contract.task_digest
                or (facts[0].execution_id,facts[0].task_id,facts[0].task_epoch) !=
                   (contract.execution_id,contract.task_id,contract.task_epoch)):
            raise ProtocolError("dsh_reservation_claim_or_contract_mismatch")
        return self._reservation(facts[0])

    def record(self, *, contract_ref: ArtifactRefV1, reservation: dict[str, Any],
               event_id: str, kind: str, evidence_ref: ArtifactRefV1 | None = None,
               reason: str = "", usage_input_tokens: int | None = None,
               usage_output_tokens: int | None = None, domain_receipt: bool = False,
               domain_rejection: bool = False) -> dict[str, Any]:
        facade = self.facade
        with scoped_run_lease(facade.store.root, execution_id=facade.context.scope.execution_id, blocking=True):
            # Local late observations can settle a cancelled epoch. Dispatch
            # below still requires the live, uncancelled claim and deadline.
            facade.authorize(replay=kind not in {"dispatch-recorded", "adapter-attempt"})
            contract = self._contract(contract_ref)
            _, invocation = self._bound_plan(contract,recorded_request_id=reservation.get('request_id'))
            facts = read_dsh_invocation_events(self.root, invocation.invocation_id)
            if not facts or reservation != self._reservation(facts[0]):
                raise ProtocolError("dsh_reservation_binding_mismatch")
            if (not facade.task_store.accepts_recorded_claim(facade.claim,facts[0].claim_digest)
                    or facts[0].contract_digest != contract.task_digest
                    or (facts[0].execution_id,facts[0].task_id,facts[0].task_epoch) !=
                       (contract.execution_id,contract.task_id,contract.task_epoch)):
                raise ProtocolError("dsh_reservation_claim_or_contract_mismatch")
            if kind in {"dispatch-recorded", "adapter-attempt"}:
                if facade.recovery_only:
                    raise ProtocolError("dsh_recovery_cannot_redispatch")
                if kind == "adapter-attempt" and any(fact.kind == "adapter-attempt" for fact in facts):
                    raise ProtocolError("dsh_adapter_permit_already_consumed")
                facade.authorize()
                facade.task_store.authorize(facade.claim,require_execute=True)
                facade.verify_composition()
                facade.verify_contract_dependencies(contract)
                self._deadline(contract)
                evidence=facade.store.read_json(parse_model(canonical_json_bytes(facts[0].evidence_ref),ArtifactRefV1))
                budget_ref=parse_model(canonical_json_bytes(evidence["budget_ref"]),ArtifactRefV1)
                envelope=RunInvocationBudgetEnvelopeV1.model_validate_json(canonical_json_bytes(facade.store.read_json(budget_ref)))
                if envelope.content_digest != self._bound_plan(contract)[0].envelope_digest:
                    raise ProtocolError("dsh_budget_envelope_binding_mismatch")
                failures=check_run_budget_before_send(self.root,envelope,role=facts[0].consumer_role,
                    request_input_tokens=facts[0].reserved_input_tokens,
                    current_reserved_input_tokens=facts[0].reserved_input_tokens,
                    current_attempt_recorded=True,invocation_id=invocation.invocation_id)
                if failures: raise ProtocolError(failures[0])
            if evidence_ref is not None:
                evidence=facade.store.read_json(evidence_ref)
                finish_observed=False
                if (contract.schema_version=='WriterTaskContractV2' and evidence.get('schema_version') in {
                        'DshRejectedTextFinishObservationV1','DshRejectedUnknownToolFinishObservationV1'}):
                    raise ProtocolError('dsh_step_completion_required')
                if evidence.get("schema_version") in {"DshRejectedTextFinishObservationV1","DshRejectedUnknownToolFinishObservationV1"}:
                    view=facade.task_store.read()
                    observation=view.get('provider_quiescence')
                    if observation is None:
                        raise ProtocolError('dsh_text_finish_owner_observation_required')
                    finish=facade.store.read_json(parse_model(canonical_json_bytes(observation['quiescence_ref']),ArtifactRefV1))
                    if evidence['schema_version']=='DshRejectedTextFinishObservationV1':
                        from .text_rejection_completion import verify_text_rejection
                        verify_text_rejection(facade.store,view,finish,facts,require_settlement=False)
                    else:
                        from .unknown_tool_completion import verify_unknown_tool_rejection
                        verify_unknown_tool_rejection(facade.store,view,finish,facts,require_settlement=False)
                    if evidence != {'schema_version':evidence['schema_version'],
                            'request_digest':facts[0].request_digest,'finish_reason':finish['finish_reason'],'stream_complete':True,
                            'raw_ref':finish['raw_ref'],'session_ref':finish['session_ref']}:
                        raise ProtocolError('dsh_text_finish_evidence_invalid')
                    finish_observed=True
                if evidence.get("schema_version") == "DshStepFinishObservationV2":
                    from .step_completion import verify_step_completion
                    verify_step_completion(facade,contract,evidence,facts)
                    finish_observed=True
                if evidence.get("schema_version") == "DshFinishObservationV1":
                    if contract.schema_version=='WriterTaskContractV2':
                        raise ProtocolError('dsh_step_completion_required')
                    if (set(evidence) != {"schema_version","request_digest","finish_reason","stream_complete","raw_ref","session_ref"}
                            or evidence["request_digest"] != facts[0].request_digest
                            or not isinstance(evidence["finish_reason"], str)
                            or evidence["finish_reason"] not in {"stop", "tool-calls", "tool_calls"}
                            or evidence["stream_complete"] is not True):
                        raise ProtocolError("dsh_finish_evidence_invalid")
                    for name in ("raw_ref","session_ref"):
                        facade.store.read(parse_model(canonical_json_bytes(evidence[name]),ArtifactRefV1))
                    finish_observed=True
                if kind == "usage" and evidence != {"schema_version":"DshAdapterUsageV1",
                    "request_digest":facts[0].request_digest,"input_tokens":usage_input_tokens,
                    "output_tokens":usage_output_tokens,"source":"adapter-usage"}:
                    raise ProtocolError("dsh_usage_evidence_mismatch")
                if kind == "usage" and usage_input_tokens == 0 and usage_output_tokens == 0:
                    raise ProtocolError("dsh_provider_usage_unobserved")
                if kind == "terminal" and not finish_observed and (evidence.get("schema_version") != "RecordedWriterOutputV1"
                        or evidence.get("contract_digest") != contract.task_digest):
                    raise ProtocolError("dsh_terminal_evidence_mismatch")
                rejection_observed=False
                if kind == 'settlement' and domain_rejection:
                    terminal=next((fact for fact in facts if fact.kind == 'terminal'),None)
                    if (set(evidence) != {'schema_version','contract_digest','output_ref','reason','source'}
                            or evidence['schema_version'] != 'DshRejectedOutputObservationV1'
                            or evidence['contract_digest'] != contract.task_digest or evidence['source'] != 'kernel-ingest-rejection'
                            or not isinstance(evidence['reason'],str) or not evidence['reason']
                            or terminal is None or evidence['output_ref'] != terminal.evidence_ref):
                        raise ProtocolError('dsh_rejection_evidence_invalid')
                    recorded=facade.store.read_json(parse_model(canonical_json_bytes(evidence['output_ref']),ArtifactRefV1))
                    if recorded.get('schema_version') != 'RecordedWriterOutputV1' or recorded.get('contract_digest') != contract.task_digest:
                        raise ProtocolError('dsh_rejection_terminal_mismatch')
                    rejection_observed=True
                if kind == "settlement" and not finish_observed and not rejection_observed and (not domain_receipt
                        or evidence.get("schema_version") != "LocalWriterReceiptV1"
                        or evidence.get("task_digest") != contract.task_digest):
                    raise ProtocolError("dsh_settlement_evidence_mismatch")
                if kind == "settlement" and finish_observed:
                    terminal=next((fact for fact in facts if fact.kind == "terminal"),None)
                    if terminal is None or terminal.evidence_ref != evidence_ref.model_dump(mode="json"):
                        raise ProtocolError("dsh_settlement_terminal_mismatch")
                if kind == "proven-not-sent" and evidence != {"schema_version":"DshUnsentProofV1",
                        "request_digest":facts[0].request_digest,"adapter_never_entered":True,
                        "provider_scope_quiescent":True}:
                    raise ProtocolError("dsh_unsent_evidence_invalid")
                if kind == "dispatch-confirmed" and (evidence.get("schema_version") != "DshTransportDispatchV1"
                        or evidence.get("request_digest") != facts[0].request_digest
                        or evidence.get("source") != "provider-http-observation"
                        or type(evidence.get("http_status")) is not int
                        or not 100 <= evidence["http_status"] <= 599):
                    raise ProtocolError("dsh_transport_evidence_invalid")
            values = facts[0].model_dump(mode="json",exclude={"content_digest"})
            values.update(event_id=event_id, kind=kind, source="kernel" if kind == "settlement" else "host-adapter",
                reserved_input_tokens=0, reserved_output_tokens=0, usage_input_tokens=usage_input_tokens,
                usage_output_tokens=usage_output_tokens, evidence_ref=evidence_ref.model_dump(mode="json") if evidence_ref else None,
                reason=reason)
            event = DshInvocationEventV1.model_validate_json(canonical_json_bytes(values))
            try:
                path = publish_dsh_invocation_event(self.root,event)
            except ValueError as error:
                raise ProtocolError(str(error)) from error
            return {"event_digest":event.content_digest, "event_file":path.name,
                "recovery":reduce_invocation_recovery(facade.store.root,invocation.invocation_id).as_diagnostics()}
