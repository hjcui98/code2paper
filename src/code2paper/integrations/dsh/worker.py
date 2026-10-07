"""Private stdio JSON-RPC worker. Bootstrap is supplied by the trusted Host.

No Python LLM caller, model wait, arbitrary import/eval, or client-selected path
is available. Durable claims/reservations and production Host pump are R work.
"""
from __future__ import annotations

import argparse
import base64
import re
import signal
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any,Literal

from code2paper.agentic.authoring_execution_identity import CompositionSpecV1, scoped_run_lease
from code2paper.agentic.digest import canonical_json_bytes,digest_json,digest_bytes
from code2paper.agentic.unified_invocation_ledger import read_dsh_invocation_events
from code2paper.agentic.writer_attempt_ledger import reduce_invocation_recovery
from .artifacts import ArtifactStore,TaskScope
from .facade import ControlledHostContext,WriterFacade
from .task_store import TaskStore, SerialBackendAdmission
from .epoch_tools import ToolCandidateV2, EpochTools
from .invocation_adapter import InvocationAdapter
from .protocol import MAX_FRAME_BYTES,MAX_READ_CHUNK,ProtocolError,WireModel,parse_model,strict_json_loads
from .result_ingest import OutputEnvelopeV1,ingest,record_output,ingest_key,WriterContentRejection
from .writer_contract import ArtifactRefV1,Counter,Digest,Identifier,Positive,WriterWireProjectionV1,parse_writer_contract


class RpcRequest(WireModel):
    jsonrpc:Literal["2.0"]
    id:Counter | Identifier
    method:Identifier
    params:dict[str,Any]


class Handshake(WireModel):
    protocol_version:Literal["c2p-dsh/1"]
    schema_digest:Digest
    validator_digest:Digest
    max_frame_bytes:Literal[1048576]


class ScopedParams(WireModel):
    execution_id:Identifier
    task_id:Identifier
    task_epoch:Counter


class ReadGrantParams(ScopedParams):
    grant_id:Digest
    offset:Counter
    length:Positive


class PutParams(ScopedParams):
    raw_base64:str
    media_type:Literal["application/json","text/plain","application/octet-stream"]


class PrepareParams(ScopedParams):
    frozen_ref:ArtifactRefV1
    projection_ref:ArtifactRefV1
    cap:Positive


class ContractParams(ScopedParams):
    contract_ref:ArtifactRefV1


class ToolCandidateParams(ContractParams):
    candidate:ToolCandidateV2


class ReleaseParams(ScopedParams):
    quiescence_ref:ArtifactRefV1


class ProviderQuiescenceV1(ScopedParams):
    schema_version:Literal['DshProviderQuiescenceV1','DshRejectedTextProviderQuiescenceV1','DshRejectedUnknownToolProviderQuiescenceV1']
    request_id:Identifier
    request_digest:Digest
    session_id:Identifier
    source:Literal['gated-adapter-natural-exhaustion/1','gated-adapter-natural-text-exhaustion/1','gated-adapter-natural-unknown-tool-exhaustion/1']
    finish_reason:Literal['tool-calls','stop']
    raw_ref:ArtifactRefV1
    session_ref:ArtifactRefV1


class OutputParams(ContractParams):
    envelope:OutputEnvelopeV1


class RawCaptureV1(ScopedParams):
    schema_version:Literal["DshRawCaptureV1"]
    child_id:Identifier
    session_id:Identifier
    request_id:Identifier
    tool_call_id:Identifier
    stream_index:Positive
    source:Literal["adapter_tool_arguments_delta"]
    arguments_completion:Literal["block-ended"]
    arguments_ref:ArtifactRefV1


class RawCaptureParams(ScopedParams):
    capture:RawCaptureV1


class OutputKeyParams(ScopedParams):
    contract_ref:ArtifactRefV1
    output_ref:ArtifactRefV1


class IngestParams(OutputKeyParams):
    idempotency_key:Digest


class ClaimV1(WireModel):
    task_key:Digest
    owner:Identifier
    claim_fence:Positive
    capability:Identifier
    epoch_started_ms:Counter


class ClaimParams(ScopedParams):
    owner:Identifier


class ResumeParams(ScopedParams):
    claim:ClaimV1


class BindParams(ResumeParams):
    child_id:Identifier
    session_id:Identifier


class ReservationV1(WireModel):
    schema_version:Literal["DshReservationV1"]
    request_id:Identifier
    reservation_id:Digest
    request_digest:Digest
    contract_digest:Digest
    claim_digest:Digest


class ReserveParams(ScopedParams):
    contract_ref:ArtifactRefV1
    budget_ref:ArtifactRefV1
    actual_request_ref:ArtifactRefV1
    event_id:Identifier


class MeasureStepParams(ContractParams):
    actual_request_ref:ArtifactRefV1
    provider_wire_ref:ArtifactRefV1
    sequence:Positive


class CompactionPromptParams(ContractParams):
    input_ref:ArtifactRefV1


class BindAuxiliaryParams(ContractParams):
    budget_ref:ArtifactRefV1
    parent_session_ref:ArtifactRefV1
    input_ref:ArtifactRefV1
    child_id:Identifier
    session_id:Identifier
    output_tokens:Positive


class MeasureAuxiliaryParams(MeasureStepParams):
    binding_ref:ArtifactRefV1


class ReserveStepParams(ContractParams):
    budget_ref:ArtifactRefV1
    step_ref:ArtifactRefV1
    event_id:Identifier


class EventParams(ScopedParams):
    contract_ref:ArtifactRefV1
    reservation:ReservationV1
    event_id:Identifier
    kind:Literal["dispatch-recorded","adapter-attempt","dispatch-confirmed","proven-not-sent",
                 "send-outcome-unknown","usage","terminal","cancel","settlement"]
    evidence_ref:ArtifactRefV1 | None = None
    reason:str = ""
    usage_input_tokens:Counter | None = None
    usage_output_tokens:Counter | None = None


METHOD_MODELS={"context.compaction_prompt":CompactionPromptParams,"task.bind_auxiliary":BindAuxiliaryParams,"request.measure_auxiliary":MeasureAuxiliaryParams,"request.measure_step":MeasureStepParams,"request.reserve_step":ReserveStepParams,"context.read_grants":ContractParams,"task.record_tool_candidate":ToolCandidateParams,"context.materials":ContractParams,"task.read_grant":ReadGrantParams,"artifact.record":PutParams,"task.prepare":PrepareParams,"task.record_output":OutputParams,
               "backend.release":ReleaseParams,"backend.observe_quiescence":ReleaseParams,
               "task.capture_raw":RawCaptureParams,
               "task.ingest_key":OutputKeyParams,
               "task.ingest":IngestParams,"worker.status":ScopedParams,
               "worker.shutdown":ScopedParams,"task.claim":ClaimParams,
               "task.recover":ClaimParams,
               "task.resume":ResumeParams,"task.bind":BindParams,
               "task.cancel":ResumeParams,"task.read":ScopedParams,
               "task.limits":ResumeParams,
               "request.reserve":ReserveParams,"request.dispatch":EventParams,
               "request.status":ContractParams,
               "request.settle":EventParams,"request.mark_unknown":EventParams}
DURABLE_METHODS={"context.compaction_prompt","task.bind_auxiliary","request.measure_auxiliary","request.measure_step","request.reserve_step","context.read_grants","task.record_tool_candidate","context.materials","task.read_grant","task.claim","task.recover","task.resume","task.bind","task.cancel","task.read","task.limits","task.ingest_key","task.capture_raw",
                 "backend.release","backend.observe_quiescence",
                 "request.reserve","request.dispatch","request.settle","request.mark_unknown","request.status"}


def rpc_schema_digest()->str:
    return digest_json({"request":RpcRequest.model_json_schema(),"handshake":Handshake.model_json_schema(),
                       "methods":{key:model.model_json_schema() for key,model in METHOD_MODELS.items()}})


class Worker:
    def __init__(self,facade:WriterFacade):
        self.facade=facade;self.ready=False;self.shutdown=False;self.sequence=0

    def call(self,request:RpcRequest)->Any:
        if self.facade.task_store is not None:
            with scoped_run_lease(self.facade.store.root,
                    execution_id=self.facade.context.scope.execution_id,blocking=True):
                return self._call(request)
        return self._call(request)

    def _call(self,request:RpcRequest)->Any:
        self.facade.authorize(preparation=True)
        if request.method == "initialize":
            params=parse_model(canonical_json_bytes(request.params),Handshake)
            if params.schema_digest != rpc_schema_digest(): raise ProtocolError("rpc_schema_mismatch")
            if params.validator_digest != self.facade.composition["validator_digest"]: raise ProtocolError("validator_mismatch")
            self.facade.verify_composition();self.ready=True
            return {"protocol_version":"c2p-dsh/1","schema_digest":rpc_schema_digest(),
                "validator_digest":params.validator_digest,"methods":[key for key in METHOD_MODELS
                    if self.facade.task_store is not None or key not in DURABLE_METHODS],
                "unavailable_methods":[] if self.facade.task_store is not None else sorted(DURABLE_METHODS),
                "max_frame_bytes":MAX_FRAME_BYTES,"max_read_chunk":MAX_READ_CHUNK,"scope_mode":self.facade.context.claim_mode}
        if not self.ready: raise ProtocolError("handshake_required")
        model=METHOD_MODELS.get(request.method)
        if model is None: raise ProtocolError("method_unavailable")
        if request.method in DURABLE_METHODS and self.facade.task_store is None:
            raise ProtocolError("method_unavailable")
        params=parse_model(canonical_json_bytes(request.params),model)
        scope=self.facade.context.scope
        if (params.execution_id,params.task_id,params.task_epoch) != (scope.execution_id,scope.task_id,scope.task_epoch):
            raise ProtocolError("rpc_scope_mismatch")
        self.sequence+=1
        if request.method == "task.read_grant":
            return self.facade.read_grant(grant_id=params.grant_id,offset=params.offset,length=params.length)
        if request.method == 'backend.observe_quiescence':
            if self.facade.recovery_only:raise ProtocolError('provider_observation_execute_claim_required')
            self.facade.authorize()
            self.facade.verify_composition()
            view=self.facade.task_store.authorize(self.facade.claim,require_execute=True)
            observed=self.facade.store.read_json(params.quiescence_ref)
            if observed.get('schema_version')=='DshEpochProviderQuiescenceV2':
                from .epoch_completion import verify_epoch_quiescence
                contract_ref=parse_model(canonical_json_bytes(view['prepared']['contract_ref']),ArtifactRefV1)
                contract=parse_writer_contract(canonical_json_bytes(self.facade.store.read_json(contract_ref)))
                verify_epoch_quiescence(self.facade,contract,observed,require_settlement=False)
                return self.facade.task_store.record_provider_quiescence(self.facade.claim,params.quiescence_ref)
            value=parse_model(canonical_json_bytes(observed),ProviderQuiescenceV1)
            if ((value.execution_id,value.task_id,value.task_epoch) != (scope.execution_id,scope.task_id,scope.task_epoch)
                    or value.session_id != self.facade.context.session_id):
                raise ProtocolError('provider_observation_binding_invalid')
            contract_ref=parse_model(canonical_json_bytes(view['prepared']['contract_ref']),ArtifactRefV1)
            adapter=InvocationAdapter(self.facade);reservation=adapter.reservation(contract_ref)
            facts=read_dsh_invocation_events(adapter.root,reservation['request_id'])
            if (value.request_id != reservation['request_id'] or value.request_digest != reservation['request_digest']
                    or any(f.kind in {'terminal','settlement','cancel','send-outcome-unknown'} for f in facts)
                    or any(len([f for f in facts if f.kind==kind]) != 1 for kind in ('adapter-attempt','usage'))):
                raise ProtocolError('provider_observation_binding_invalid')
            SerialBackendAdmission._verify_native_quiescence(self.facade.store,view,value.model_dump(mode='json'),
                facts,require_settlement=False)
            return self.facade.task_store.record_provider_quiescence(self.facade.claim,params.quiescence_ref)
        if request.method == "backend.release":
            self.facade.authorize(replay=True)
            self.facade.task_store.authorize(self.facade.claim,allow_terminal=True)
            return self.facade.backend_admission.release_observed_finish(
                run_root=self.facade.store.root,scope=scope,quiescence_ref=params.quiescence_ref)
        if request.method == "task.capture_raw":
            self.facade.authorize()
            self.facade.verify_composition()
            capture=params.capture
            if (capture.execution_id,capture.task_id,capture.task_epoch) != (scope.execution_id,scope.task_id,scope.task_epoch):
                raise ProtocolError("raw_capture_scope_mismatch")
            if any(getattr(capture,key) != getattr(self.facade.context,key) for key in ("child_id","session_id","request_id")):
                raise ProtocolError("raw_capture_binding_mismatch")
            self.facade.store.read(capture.arguments_ref)
            if capture.arguments_ref.media_type != "application/octet-stream": raise ProtocolError("raw_capture_media_mismatch")
            view=self.facade.task_store.read()
            ref=parse_model(canonical_json_bytes(view["prepared"]["contract_ref"]),ArtifactRefV1)
            reservation=InvocationAdapter(self.facade).reservation(ref)
            if capture.request_id != reservation["request_id"]: raise ProtocolError("raw_capture_request_mismatch")
            return self.facade.task_store.capture_source(self.facade.claim,capture.model_dump(mode="json"))
        if request.method in {"task.claim","task.recover","task.resume","task.bind","task.cancel","task.read","task.limits"}:
            store=self.facade.task_store
            if store is None: raise ProtocolError("durable_task_store_unavailable")
            if request.method == "task.read": return store.read()
            if request.method == "task.claim":
                self.facade.verify_composition()
                if store.read()['state'] != 'outbox':raise ProtocolError('task_claim_held')
                self.facade.backend_admission.acquire(execution_id=scope.execution_id,run_root=self.facade.store.root)
                self.facade.claim=store.claim(params.owner)
                return self.facade.claim
            if request.method == "task.recover":
                self.facade.verify_composition()
                # Local settlement has no provider permit. In particular it
                # must not reacquire a retired owner or block a subsequent run.
                self.facade.claim=store.recover_for_settlement(params.owner)
                self.facade.recovery_only=True
                view=store.authorize(self.facade.claim,allow_terminal=True)
                if view["binding"]:
                    self.facade.context=replace(self.facade.context,**view["binding"])
                    ref=parse_model(canonical_json_bytes(view["prepared"]["contract_ref"]),ArtifactRefV1)
                    reservation=InvocationAdapter(self.facade).reservation(ref,allow_missing=True)
                    if reservation: self.facade.context=replace(self.facade.context,request_id=reservation["request_id"])
                return self.facade.claim
            claim=params.claim.model_dump(mode="json")
            if request.method == "task.limits":
                view=store.authorize(claim,allow_terminal=True)
                ref=parse_model(canonical_json_bytes(view["prepared"]["contract_ref"]),ArtifactRefV1)
                contract=parse_writer_contract(canonical_json_bytes(self.facade.store.read_json(ref)))
                return {"epoch_started_ms":view["epoch_started_ms"],"epoch_limits":contract.epoch_limits.model_dump(mode="json")}
            if request.method == "task.resume":
                self.facade.verify_composition()
                view=store.authorize(claim,allow_terminal=True)
                self.facade.claim=claim
                self.facade.recovery_only=True
                if view["binding"]:
                    self.facade.context=replace(self.facade.context,**view["binding"])
                ref=parse_model(canonical_json_bytes(view["prepared"]["contract_ref"]),ArtifactRefV1)
                reservation=InvocationAdapter(self.facade).reservation(ref,allow_missing=True)
                if reservation:
                    self.facade.context=replace(self.facade.context,request_id=reservation["request_id"])
                return view
            if request.method == "task.bind":
                self.facade.verify_composition()
                view=store.bind(claim,child_id=params.child_id,session_id=params.session_id)
                self.facade.claim=claim
                self.facade.context=replace(self.facade.context,child_id=params.child_id,session_id=params.session_id)
                return view
            view=store.cancel(claim)
            self.facade.claim=claim
            if view["binding"]:
                self.facade.context=replace(self.facade.context,**view["binding"])
                ref=parse_model(canonical_json_bytes(view["prepared"]["contract_ref"]),ArtifactRefV1)
                adapter=InvocationAdapter(self.facade)
                reservation=adapter.reservation(ref,allow_missing=True)
                if reservation:
                    facts=read_dsh_invocation_events(adapter.root,reservation["request_id"])
                    if not any(fact.kind in {"settlement","proven-not-sent"} for fact in facts):
                        adapter.record(contract_ref=ref,reservation=reservation,kind="cancel",
                            event_id="cancel:task-lifecycle",reason="task-cancelled")
            return view
        if request.method == 'context.compaction_prompt':
            from .step_admission import StepAdmission
            from .auxiliary_admission import COMPACTION_INSTRUCTION, COMPACTION_SYSTEM
            contract,_=StepAdmission(self.facade).owner(params.contract_ref)
            from .writer_contract import WriterWireEquivalenceV1
            projection=parse_model(canonical_json_bytes(self.facade.store.read_json(contract.dsh_wire_contract_ref)),WriterWireProjectionV1)
            equivalent=parse_model(canonical_json_bytes(self.facade.store.read_json(projection.wire_equivalence_ref)),WriterWireEquivalenceV1)
            seed=self.facade.store.read_json(equivalent.loop_request_ref)
            return {'system_text':COMPACTION_SYSTEM,'options':{k:seed[k] for k in ('provider','model','temperature','reasoningEffort') if k in seed},
                'prompt_text':COMPACTION_INSTRUCTION+'\n'+canonical_json_bytes(self.facade.store.read_json(params.input_ref)).decode()}
        if request.method == 'task.bind_auxiliary':
            from .auxiliary_admission import AuxiliaryAdmission
            values=params.model_dump(exclude={'execution_id','task_id','task_epoch'})
            ref,binding=AuxiliaryAdmission(self.facade).issue(**{k:getattr(params,k) for k in values})
            return {'binding_ref':ref.model_dump(mode='json'),'binding':binding.model_dump(mode='json')}
        if request.method == 'request.measure_auxiliary':
            from .step_admission import StepAdmission
            ref=StepAdmission(self.facade).measure_auxiliary(contract_ref=params.contract_ref,binding_ref=params.binding_ref,
                actual_request_ref=params.actual_request_ref,provider_wire_ref=params.provider_wire_ref,sequence=params.sequence)
            return {'step_ref':ref.model_dump(mode='json')}
        if request.method == 'request.measure_step':
            from .step_admission import StepAdmission
            ref=StepAdmission(self.facade).measure(contract_ref=params.contract_ref,
                actual_request_ref=params.actual_request_ref,provider_wire_ref=params.provider_wire_ref,sequence=params.sequence)
            return {'step_ref':ref.model_dump(mode='json')}
        if request.method == 'request.reserve_step':
            from .step_admission import StepAdmission
            reservation=StepAdmission(self.facade).reserve(contract_ref=params.contract_ref,budget_ref=params.budget_ref,
                step_ref=params.step_ref,event_id=params.event_id)
            self.facade.context=replace(self.facade.context,request_id=reservation['request_id'])
            return reservation
        if request.method.startswith("request."):
            adapter=InvocationAdapter(self.facade)
            if request.method == "request.status":
                self.facade.authorize(replay=True)
                view=self.facade.task_store.read()
                if view["prepared"]["contract_ref"] != params.contract_ref.model_dump(mode="json"):
                    raise ProtocolError("dsh_task_contract_ref_mismatch")
                reservation=adapter.reservation(params.contract_ref,allow_missing=True)
                if reservation is None: return {"reservation":None,"recorded_output_ref":None,"recovery":None}
                facts=read_dsh_invocation_events(adapter.root,reservation["request_id"])
                terminal=next((fact for fact in facts if fact.kind == "terminal"),None)
                output=None
                if terminal:
                    ref=parse_model(canonical_json_bytes(terminal.evidence_ref),ArtifactRefV1)
                    if self.facade.store.read_json(ref).get("schema_version") == "RecordedWriterOutputV1":
                        output=ref.model_dump(mode="json")
                completed=[]
                contract=adapter._contract(params.contract_ref)
                if contract.schema_version=='WriterTaskContractV2':
                    from .epoch_accounting import epoch_requests
                    ordered=[]
                    for rows in epoch_requests(adapter.root,contract):
                        reserve=self.facade.store.read_json(parse_model(canonical_json_bytes(rows[0].evidence_ref),ArtifactRefV1))
                        step=self.facade.store.read_json(parse_model(canonical_json_bytes(reserve['step_ref']),ArtifactRefV1))
                        terminal=next((row for row in rows if row.kind=='terminal'),None)
                        if terminal and self.facade.store.read_json(parse_model(canonical_json_bytes(terminal.evidence_ref),ArtifactRefV1)).get('schema_version')=='DshStepFinishObservationV2':
                            ordered.append((step['sequence'],terminal.evidence_ref))
                    completed=[ref for _,ref in sorted(ordered)]
                return {"completed_step_refs":completed,"reservation":reservation,"recorded_output_ref":output,
                    "recovery":reduce_invocation_recovery(self.facade.store.root,reservation["request_id"]).as_diagnostics()}
            if request.method == "request.reserve":
                reservation=adapter.reserve(contract_ref=params.contract_ref,budget_ref=params.budget_ref,
                    actual_request_ref=params.actual_request_ref,event_id=params.event_id)
                self.facade.context=replace(self.facade.context,request_id=reservation["request_id"])
                return reservation
            allowed={"request.dispatch":{"dispatch-recorded","adapter-attempt","dispatch-confirmed","proven-not-sent"},
                "request.settle":{"usage","cancel","terminal","settlement"},
                "request.mark_unknown":{"send-outcome-unknown"}}
            if params.kind not in allowed[request.method]: raise ProtocolError("request_event_method_mismatch")
            return adapter.record(contract_ref=params.contract_ref,reservation=params.reservation.model_dump(mode="json"),
                event_id=params.event_id,kind=params.kind,evidence_ref=params.evidence_ref,reason=params.reason,
                usage_input_tokens=params.usage_input_tokens,usage_output_tokens=params.usage_output_tokens)
        if request.method == "worker.status":
            return {"state":"idle","operation_sequence":self.sequence,"model_calls":0,"inflight_mutations":0}
        if request.method == "worker.shutdown":
            self.shutdown=True
            return {"worker_shutdown_requested":True,"inflight_mutations":0,"provider_scope_quiescence":"not_proven_by_worker"}
        if request.method == "artifact.record":
            try: raw=base64.b64decode(params.raw_base64,validate=True)
            except ValueError as error: raise ProtocolError("invalid_base64") from error
            if params.media_type == "application/json":
                self.facade.store.put_json(strict_json_loads(raw))
                return self.facade.store.put(raw,media_type="application/json",semantic_digest=digest_json(strict_json_loads(raw)))
            return self.facade.store.put(raw,media_type=params.media_type)
        if request.method == "task.prepare":
            projection=parse_model(canonical_json_bytes(self.facade.store.read_json(params.projection_ref)),WriterWireProjectionV1)
            def project(input):
                if input.input_digest != projection.input_digest:
                    raise ProtocolError("reprojection_required")
                return projection
            contract=self.facade.prepare(params.frozen_ref,cap=params.cap,project=project)
            ref=self.facade.store.put_json(contract)
            if self.facade.task_store is not None:
                self.facade.task_store.prepare(workflow_id=contract.workflow_id,node_id=contract.node_id,
                    scope_id=contract.scope_id,contract_ref=ref.model_dump(mode="json"),
                    content_revision=self.facade.context.content_revision,content_fence=self.facade.context.fence,
                    snapshot_digest=self.facade.context.snapshot_digest)
            return ref
        contract=parse_writer_contract(canonical_json_bytes(self.facade.store.read_json(params.contract_ref)))
        if request.method == "task.record_tool_candidate":
            self.facade.authorize()
            self.facade.verify_composition()
            self.facade.check_contract_current(contract)
            return EpochTools(self.facade.task_store,self.facade.store,self.facade.current_state).record(
                self.facade.claim,contract,params.candidate)
        if request.method == "context.read_grants":
            contract=parse_writer_contract(canonical_json_bytes(self.facade.store.read_json(params.contract_ref)))
            return {"grants":self.facade.public_read_grants(contract)}
        if request.method == "context.materials":
            self.facade.authorize()
            self.facade.verify_composition()
            self.facade.check_contract_current(contract)
            view=self.facade.task_store.authorize(self.facade.claim,require_execute=True)
            if view['prepared']['contract_ref'] != params.contract_ref.model_dump(mode='json'):
                raise ProtocolError('dsh_task_contract_ref_mismatch')
            if contract.schema_version != 'WriterTaskContractV2':
                raise ProtocolError('multistep_contract_required')
            request=self.facade.store.read_json(contract.writer_request_ref)
            from .writer_contract import derive_task_view
            text=canonical_json_bytes(derive_task_view(request)).decode('utf-8')
            return {'scope':{'executionId':scope.execution_id,'taskId':scope.task_id,
                'epoch':scope.task_epoch,'sessionId':self.facade.context.session_id,
                'revision':contract.expected_state_revision,'snapshotDigest':self.facade.context.snapshot_digest},
                'required':[{'id':'task-view:'+contract.writer_request_ref.bytes_digest,
                    'kind':'writer_task_view','text':text,'bytesDigest':digest_bytes(text.encode('utf-8'))}],
                'origin_ref':contract.writer_request_ref.model_dump(mode='json')}
        if request.method == "task.ingest_key":
            self.facade.authorize(replay=True)
            output=self.facade.store.read_json(params.output_ref)
            if output.get("schema_version") != "RecordedWriterOutputV1" or output.get("contract_digest") != contract.task_digest:
                raise ProtocolError("output_contract_mismatch")
            return {"idempotency_key":ingest_key(contract,params.output_ref)}
        if request.method == "task.record_output":
            if self.facade.task_store is not None:
                adapter=InvocationAdapter(self.facade)
                reservation=adapter.reservation(params.contract_ref)
                source=self.facade.task_store.read()["captured_source"]
                if (source is None or params.envelope.adapter_arguments.ref is None
                        or source["arguments_ref"] != params.envelope.adapter_arguments.ref.model_dump(mode="json")
                        or any(source[key] != getattr(params.envelope,key) for key in ("request_id","child_id","session_id","tool_call_id"))):
                    raise ProtocolError("dsh_durable_raw_source_required")
            output_ref=record_output(self.facade,contract,params.envelope)
            if self.facade.task_store is not None:
                adapter.record(contract_ref=params.contract_ref,reservation=reservation,kind="terminal",
                    event_id="terminal:"+output_ref.bytes_digest.removeprefix("sha256:"),evidence_ref=output_ref)
            return output_ref
        if self.facade.task_store is not None:
            adapter=InvocationAdapter(self.facade)
            reservation=adapter.reservation(params.contract_ref)
            facts=read_dsh_invocation_events(adapter.root,reservation["request_id"])
            terminal=next((fact for fact in facts if fact.kind == "terminal"),None)
            if terminal is None or terminal.evidence_ref != params.output_ref.model_dump(mode="json"):
                raise ProtocolError("dsh_recorded_terminal_required")
        try:
            receipt=ingest(self.facade,contract,params.output_ref,idempotency_key=params.idempotency_key)
        except WriterContentRejection as error:
            if self.facade.task_store is not None and any(fact.kind == 'usage' for fact in facts):
                evidence=self.facade.store.put_json({'schema_version':'DshRejectedOutputObservationV1',
                    'contract_digest':contract.task_digest,'output_ref':params.output_ref.model_dump(mode='json'),
                    'reason':error.code,'source':'kernel-ingest-rejection'})
                adapter.record(contract_ref=params.contract_ref,reservation=reservation,kind='settlement',
                    event_id='rejected-settlement:'+params.output_ref.bytes_digest.removeprefix('sha256:'),
                    evidence_ref=evidence,domain_rejection=True)
            raise
        if self.facade.task_store is not None:
            self.facade.task_store.commit(self.facade.claim,receipt)
            if any(fact.kind == "usage" for fact in facts):
                adapter.record(contract_ref=params.contract_ref,reservation=reservation,kind="settlement",
                    event_id="settlement:"+receipt["idempotency_key"].removeprefix("sha256:"),evidence_ref=self.facade.store.put_json(receipt),domain_receipt=True)
            else:
                adapter.record(contract_ref=params.contract_ref,reservation=reservation,kind="send-outcome-unknown",
                    event_id="usage-missing:"+receipt["idempotency_key"].removeprefix("sha256:"),reason="usage-missing")
        return receipt


def iter_frames(stream):
    """Bounded chunks and frame accumulation; oversized frames are drained."""
    frame=bytearray();oversized=False
    while True:
        chunk=stream.read1(MAX_READ_CHUNK)
        if not chunk:
            if frame or oversized: yield ProtocolError("incomplete_frame")
            return
        parts=chunk.split(b"\n")
        for index,part in enumerate(parts):
            if not oversized:
                if len(frame)+len(part) > MAX_FRAME_BYTES:
                    oversized=True;frame.clear()
                else: frame.extend(part)
            if index < len(parts)-1:
                yield ProtocolError("frame_too_large") if oversized else bytes(frame)
                frame.clear();oversized=False


def _timeout(_signal,_frame): raise ProtocolError("operation_timeout")


def serve(worker:Worker):
    signal.signal(signal.SIGALRM,_timeout)
    for raw in iter_frames(sys.stdin.buffer):
        request_id=None
        try:
            if isinstance(raw,ProtocolError): raise raw
            request=parse_model(raw,RpcRequest);request_id=request.id
            signal.alarm(30)
            result=worker.call(request)
            response={"jsonrpc":"2.0","id":request_id,"result":result}
        except ProtocolError as error:
            response={"jsonrpc":"2.0","id":request_id,"error":{"code":-32000,"message":error.code}}
        except Exception as error:
            # No traceback or input data reaches stdout or logs (capabilities
            # and terminal source may be sensitive).
            print(f"worker_internal_error:{type(error).__name__}",file=sys.stderr)
            response={"jsonrpc":"2.0","id":request_id,"error":{"code":-32603,"message":"worker_internal_error"}}
        finally: signal.alarm(0)
        output=canonical_json_bytes(response)
        if len(output)>MAX_FRAME_BYTES:
            output=canonical_json_bytes({"jsonrpc":"2.0","id":request_id,"error":{"code":-32000,"message":"response_too_large"}})
        sys.stdout.buffer.write(output+b"\n");sys.stdout.buffer.flush()
        if worker.shutdown: return


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--bootstrap",type=Path,required=True)
    args=parser.parse_args()
    # The operator's bootstrap path is not an RPC or model field.
    config=strict_json_loads(args.bootstrap.read_bytes(),max_bytes=32 << 20)
    required={"artifact_root","engine_root","scope","context","composition_spec","composition","meter"}
    if set(config) not in (required,required|{'host_launch_binding'}): raise ProtocolError("bootstrap_schema_invalid")
    if 'host_launch_binding' in config:
        binding=config['host_launch_binding']
        if (not isinstance(binding,dict) or set(binding) != {'schema_version','path','bytes_digest','byte_length'}
                or binding['schema_version'] != 'DshHostLaunchBindingV1'
                or not isinstance(binding['path'],str) or not Path(binding['path']).is_absolute()
                or type(binding['byte_length']) is not int or not 0 < binding['byte_length'] <= MAX_FRAME_BYTES
                or not isinstance(binding['bytes_digest'],str)
                or re.fullmatch(r'sha256:[0-9a-f]{64}',binding['bytes_digest']) is None):
            raise ProtocolError('bootstrap_host_launch_binding_invalid')
        with Path(binding['path']).open('rb') as stream:
            launch_raw=stream.read(MAX_FRAME_BYTES+1)
        if len(launch_raw) != binding['byte_length'] or digest_bytes(launch_raw) != binding['bytes_digest']:
            raise ProtocolError('bootstrap_host_launch_changed')
    scope=TaskScope(**config["scope"]);context=ControlledHostContext(scope=scope,**config["context"])
    spec=config["composition_spec"]
    composition_spec=CompositionSpecV1(files={key:Path(value) for key,value in spec["files"].items()},
        trees={key:Path(value) for key,value in spec["trees"].items()},effective_config=spec["effective_config"],
        upstream_source_sha=spec.get("upstream_source_sha"))
    # Explicit conservative meter from the original owner. It measures actual
    # provider-wire bytes and is recorded as an upper-bound observation, never
    # presented as provider tokenizer usage. Model-tokenizer bootstraps require
    # a separately implemented local adapter; no vLLM/network fallback.
    from code2paper.agentic.unified_context_compiler import measure_unified_tokens
    from code2paper.agentic.unified_context_models import UnifiedTokenMeterV1
    if config["meter"].get("kind") == "controlled-utf8-byte-id/1":
        from .local_meter import bind_controlled_meter
        request_meter=bind_controlled_meter(composition_spec.effective_config)
    else:
        meter=UnifiedTokenMeterV1.model_validate(config["meter"])
        if meter.method != "conservative_utf8_bytes_div_4": raise ProtocolError("local_tokenizer_unavailable")
        request_meter=lambda wire:measure_unified_tokens(wire.decode("utf-8"),meter=meter)
    durable=context.claim_mode == "dsh-durable-claim/1"
    backend=None
    if durable:
        effective=composition_spec.effective_config
        if not all(isinstance(effective.get(key),str) and effective[key] for key in ("backend_state_root","backend_resource_key")):
            raise ProtocolError("backend_admission_config_required")
        backend=SerialBackendAdmission(Path(effective["backend_state_root"]),effective["backend_resource_key"])
    facade=WriterFacade(store=ArtifactStore(Path(config["artifact_root"]),scope),context=context,
        composition_spec=composition_spec,composition=config["composition"],engine_root=Path(config["engine_root"]),
        request_meter=request_meter,task_store=TaskStore(Path(config["artifact_root"]),scope)
            if durable else None,backend_admission=backend)
    serve(Worker(facade))


if __name__ == "__main__": main()
