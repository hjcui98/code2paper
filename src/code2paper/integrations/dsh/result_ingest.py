"""Trusted raw terminal provenance and one immutable local publication outcome."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any,Literal

from pydantic import model_validator

from code2paper.agentic.digest import canonical_json_bytes,digest_bytes,digest_json
from code2paper.agentic.authoring_artifact_publication import (
    build_publication_manifest,commit_publication_generation,load_active_publication_pointer,
    stage_publication_members,switch_publication_active,
)
from code2paper.agentic.authoring_artifact_index import load_index_for_reading,read_artifact_validated
from code2paper.agentic.final_text_authorship import GeneratedTextSpanV1,build_final_text_authorship_ledger
from .facade import WriterFacade
from .protocol import ProtocolError,WireModel,parse_model
from .writer_contract import ArtifactRefV1,Counter,Identifier,WriterTaskContractV1,WriterTaskResultV1


class ObservedLayerV1(WireModel):
    status: Literal["observed","not_observed"]
    ref: ArtifactRefV1 | None

    @model_validator(mode="after")
    def _observed(self):
        if (self.status == "observed") != (self.ref is not None): raise ValueError("source_observation_mismatch")
        return self


class OutputEnvelopeV1(WireModel):
    schema_version: Literal["OutputEnvelopeV1"]
    execution_id: Identifier
    task_id: Identifier
    task_epoch: Counter
    child_id: Identifier
    session_id: Identifier
    turn_id: Identifier | Counter
    step_id: Identifier | Counter
    tool_call_id: Identifier
    request_id: Identifier
    source: Literal["adapter_tool_arguments_delta"]
    arguments_complete: Literal[True]
    provider_http: ObservedLayerV1
    adapter_arguments: ObservedLayerV1
    normalized_arguments: ObservedLayerV1
    stop_reason: str | None
    usage: dict[str,Any] | None
    session_capture_ref: ArtifactRefV1 | None = None

    @model_validator(mode="before")
    @classmethod
    def _boolean_complete(cls,value):
        if isinstance(value,dict) and type(value.get("arguments_complete")) is not bool:
            raise ValueError("arguments_complete_type_invalid")
        return value


def _check_binding(facade:WriterFacade,envelope:OutputEnvelopeV1,*,replay:bool=False):
    facade.authorize(replay=replay)
    if facade.task_store is not None:
        if envelope.session_capture_ref is None:
            raise ProtocolError("durable_session_capture_required")
        capture=facade.store.read_json(envelope.session_capture_ref)
        if (not isinstance(capture,dict) or set(capture) != {"schema_version","session_id","format_version","events"}
                or capture["schema_version"] != "DshSessionCaptureV1" or capture["format_version"] != "SessionFileV4"
                or capture["session_id"] != facade.context.session_id or not isinstance(capture["events"],list)):
            raise ProtocolError("durable_session_capture_invalid")
        calls=[event["data"] for event in capture["events"] if isinstance(event,dict)
            and event.get("type") == "tool/call" and isinstance(event.get("data"),dict)
            and event["data"].get("name") == "c2p_terminal" and event["data"].get("callId") == envelope.tool_call_id]
        if len(calls) != 1:
            raise ProtocolError("durable_session_terminal_ambiguous")
        call=calls[0]
        if (type(call.get("turn")) is not int or type(call.get("step")) is not int
                or not 0 <= call["turn"] <= 2**53-1 or not 0 <= call["step"] <= 2**53-1
                or not isinstance(call.get("arguments"),str)
                or envelope.normalized_arguments.ref is None
                or facade.store.read(envelope.normalized_arguments.ref) != call["arguments"].encode("utf-8")):
            raise ProtocolError("durable_session_terminal_binding_invalid")
        results=[event["data"] for event in capture["events"] if isinstance(event,dict)
            and event.get("type") == "tool/result" and isinstance(event.get("data"),dict)
            and isinstance(event["data"].get("message"),dict)
            and event["data"]["message"].get("toolCallId") == call["callId"]]
        ends=[event["data"] for event in capture["events"] if isinstance(event,dict)
            and event.get("type") == "turn/end" and isinstance(event.get("data"),dict)
            and event["data"].get("turn") == call["turn"]]
        if len(results) != 1 or len(ends) != 1:
            raise ProtocolError("durable_session_terminal_not_completed")
        result=results[0];message=result["message"];end=ends[0]
        if (type(result.get("turn")) is not int or type(result.get("step")) is not int
                or (result["turn"],result["step"]) != (call["turn"],call["step"])
                or message.get("role") != "tool"
                or ("isError" in message and (type(message["isError"]) is not bool or message["isError"]))
                or type(end.get("turn")) is not int or end.get("reason") != {"kind":"completed"}):
            raise ProtocolError("durable_session_terminal_not_completed")
        facade.context=replace(facade.context,turn_id=call["turn"],step_id=call["step"],tool_call_id=call["callId"])
    context=facade.context
    for name in ("execution_id","task_id","task_epoch"):
        if getattr(envelope,name) != getattr(context.scope,name): raise ProtocolError("output_scope_mismatch")
    for name in ("child_id","session_id","turn_id","step_id","tool_call_id","request_id"):
        if getattr(envelope,name) != getattr(context,name): raise ProtocolError("output_provenance_mismatch")
    if envelope.adapter_arguments.status != "observed" or envelope.normalized_arguments.status != "observed":
        raise ProtocolError("raw_arguments_not_observed")


class WriterContentRejection(ProtocolError):
    """Original assessor refusal; complete observed response still costs fees."""


def record_output(facade:WriterFacade,contract:WriterTaskContractV1,envelope:OutputEnvelopeV1)->ArtifactRefV1:
    _check_binding(facade,envelope);facade.check_current()
    if (contract.execution_id,contract.task_id,contract.task_epoch) != (envelope.execution_id,envelope.task_id,envelope.task_epoch):
        raise ProtocolError("output_scope_mismatch")
    raw=facade.store.read(envelope.adapter_arguments.ref)
    parsed=parse_model(raw,WriterTaskResultV1)
    normalized=parse_model(facade.store.read(envelope.normalized_arguments.ref),WriterTaskResultV1)
    if parsed.model_dump(mode="json") != normalized.model_dump(mode="json"):
        raise ProtocolError("normalized_arguments_content_mismatch")
    if envelope.provider_http.ref is not None: facade.store.read(envelope.provider_http.ref)
    parsed_ref=facade.store.put_json(parsed)
    return facade.store.put_json({"schema_version":"RecordedWriterOutputV1","contract_digest":contract.task_digest,
        "envelope":envelope.model_dump(mode="json"),"parsed_ref":parsed_ref.model_dump(mode="json"),
        "raw_bytes_digest":digest_bytes(raw),"parsed_digest":digest_json(parsed)})


def ingest_key(contract:WriterTaskContractV1,output_ref:ArtifactRefV1)->str:
    return digest_json({"method":"task.ingest","execution_id":contract.execution_id,"task_id":contract.task_id,
        "task_epoch":contract.task_epoch,"contract_digest":contract.task_digest,"payload_digest":output_ref.bytes_digest,
        "validator_digest":contract.identity.validator_digest})


def _authorship(facade:WriterFacade,contract:WriterTaskContractV1,parsed:WriterTaskResultV1,text:str,raw_ref:ArtifactRefV1):
    # A full raw paragraph (split only at an authorized formula placeholder) is
    # the lexical source. Arbitrary words from metadata are never a prose pool.
    import re
    draft=parsed.result.draft
    section=facade.store.read_json(contract.private_input_ref)
    packages={str(p["package_id"]):p for p in section["prompt_payload"].get("formula_packages",[])}
    fragments=[]
    fields=[("/result/draft/section_markdown",draft.section_markdown),
            ("/result/draft/heading_text",draft.heading_text)]
    fields += [(f"/result/draft/paragraphs/{i}/paragraph_markdown",p.paragraph_markdown) for i,p in enumerate(draft.paragraphs)]
    for pointer,body in fields:
        if not body: continue
        # Prefixing a markdown heading is a representation operation only;
        # every heading word must already be present in its Writer field.
        if pointer.endswith("heading_text"):
            fragments.append(("## "+body.strip(),"writer",pointer,raw_ref.bytes_digest));continue
        parts=re.split(r"(\[\[FORMULA:[^\]]+\]\])",body)
        for part in parts:
            if part.startswith("[[FORMULA:"):
                package_id=part[len("[[FORMULA:"):-2]
                package=packages.get(package_id)
                if package is None: raise ProtocolError("authorship_formula_unknown")
                fragments.append((package["markdown_block"],"formalizer","/formula_packages/"+package_id,
                    contract.formalizer_receipt_ref.bytes_digest))
            elif part:
                fragments.append((part,"writer",pointer,raw_ref.bytes_digest))
    cursor=0;generated=[];mapping=[]
    while cursor < len(text):
        if text[cursor].isspace(): cursor+=1;continue
        matches=[]
        for source,owner,pointer,ref in fragments:
            # Whitespace-only representation changes do not add lexical tokens.
            source=source.strip()
            if source and text.startswith(source,cursor): matches.append((source,owner,pointer,ref))
        if not matches: raise ProtocolError("authorship_unowned_lexical_span")
        source,owner,pointer,ref=max(matches,key=lambda row:len(row[0]))
        generated.append(GeneratedTextSpanV1(span_id=f"source:{len(generated)}",text=source,owner=owner,
            response_ref=ref,section_id=contract.scope_id,generation_trace_id=facade.context.request_id))
        mapping.append(dict(json_pointer=pointer,owner=owner,final_start=cursor,final_end=cursor+len(source),source_ref=ref))
        cursor+=len(source)
    ledger=build_final_text_authorship_ledger(text,generated)
    if not ledger.hard_gate_passed: raise ProtocolError("authorship_gate_failed")
    return {"ledger":ledger.model_dump(mode="json"),"json_pointer_map":mapping}


@contextmanager
def _outcome_lock(root:Path):
    import fcntl
    root.mkdir(parents=True,exist_ok=True)
    with (root/".stage03-local-outcome.lock").open("a+b") as stream:
        fcntl.flock(stream.fileno(),fcntl.LOCK_EX)
        try: yield
        finally: fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


def ingest(facade:WriterFacade,contract:WriterTaskContractV1,output_ref:ArtifactRefV1,*,idempotency_key:str)->dict[str,Any]:
    # Authorization precedes both object reads and an already committed cache.
    facade.authorize(replay=True)
    if (contract.execution_id,contract.task_id,contract.task_epoch) != (
        facade.context.scope.execution_id,facade.context.scope.task_id,facade.context.scope.task_epoch): raise ProtocolError("task_scope_mismatch")
    output=facade.store.read_json(output_ref)
    envelope=parse_model(canonical_json_bytes(output["envelope"]),OutputEnvelopeV1)
    _check_binding(facade,envelope,replay=True)
    if output["contract_digest"] != contract.task_digest: raise ProtocolError("output_contract_mismatch")
    actual_key=ingest_key(contract,output_ref)
    if idempotency_key != actual_key: raise ProtocolError("idempotency_key_mismatch")
    raw=facade.store.read(envelope.adapter_arguments.ref)
    parsed=parse_model(raw,WriterTaskResultV1)
    if digest_json(parsed) != output["parsed_digest"] or digest_bytes(raw) != output["raw_bytes_digest"]:
        raise ProtocolError("recorded_output_digest_mismatch")
    normalized=parse_model(facade.store.read(envelope.normalized_arguments.ref),WriterTaskResultV1)
    recorded=facade.store.read_json(parse_model(canonical_json_bytes(output["parsed_ref"]),ArtifactRefV1))
    if digest_json(normalized) != digest_json(parsed) or digest_json(recorded) != digest_json(parsed):
        raise ProtocolError("recorded_output_digest_mismatch")
    # One task/epoch has its own K02 local publication root. This is not an R01
    # claim ledger nor the whole run's section_draft active publication.
    root=facade.store.root/"dsh-local-outcomes"/digest_json(facade.context.scope.__dict__).split(":")[1]
    with _outcome_lock(root):
        index,_=load_index_for_reading(root)
        pointer=load_active_publication_pointer(root)
        if pointer.active.get("section_draft:writer"):
            read=read_artifact_validated(index,"section_draft","writer",out_root=root)
            receipt=read.members["acceptance"]
            if receipt["idempotency_key"] != actual_key or receipt["result_digest"] != digest_json(parsed):
                raise ProtocolError("task_epoch_terminal_conflict")
            return receipt
        facade.authorize()
        facade.check_current();facade.verify_composition();facade.check_contract_current(contract)
        closure=facade.verify_contract_dependencies(contract)
        if parsed.result.outcome == "research_required":
            if any(request.section_id != contract.scope_id for request in parsed.result.requests):
                raise ProtocolError("research_request_scope_mismatch")
            status="waiting";text="";metrics={};authorship={"not_applicable":True}
            detail={"requests":[request.model_dump(mode="json") for request in parsed.result.requests]}
        elif parsed.result.outcome == "blocked":
            status="blocked";text="";metrics={};authorship={"not_applicable":True}
            detail={"reason":parsed.result.reason,"recovery_action":parsed.result.recovery_action}
        else:
            accepted,metrics,response=facade.assess(contract,canonical_json_bytes(parsed.result.draft).decode())
            if not accepted: raise WriterContentRejection(response.blocked_reason or "writer_content_rejected")
            text=response.text;authorship=_authorship(facade,contract,parsed,text,envelope.adapter_arguments.ref)
            status="pending_validation"
            detail={"validation_required":True,"text_digest":digest_bytes(text.encode()),
                "evidence_snapshot_digest":facade.context.snapshot_digest,"validator_digest":contract.identity.validator_digest}
        receipt=dict(schema_version="LocalWriterReceiptV1",domain_status=status,task_digest=contract.task_digest,
            execution_id=contract.execution_id,task_id=contract.task_id,task_epoch=contract.task_epoch,
            idempotency_key=actual_key,result_digest=digest_json(parsed),validator_digest=contract.identity.validator_digest,
            payload_digest=output_ref.bytes_digest,detail=detail,metrics=metrics,local_only=True)
        members={"prose":text.encode(),"acceptance":canonical_json_bytes(receipt),
            "authorship":canonical_json_bytes(authorship),"raw_result":raw,"provenance":canonical_json_bytes({**output,"dependency_closure":closure})}
        facade.verify_composition();facade.check_current();facade.check_contract_current(contract)
        for ref in closure["dependencies"].values():
            facade.store.read_json(parse_model(canonical_json_bytes(ref),ArtifactRefV1))
        staged=stage_publication_members(root,role="section_draft",phase="writer",members=members,
            schema_versions={key:"stage03-local/1" for key in members},
            media_types={"prose":"text/markdown","acceptance":"application/json","authorship":"application/json",
                         "raw_result":"application/json","provenance":"application/json"})
        manifest=build_publication_manifest(role="section_draft",phase="writer",generation=1,members=staged,
            read_set=tuple(ref["bytes_digest"] for ref in closure["dependencies"].values()),producer="dsh-controlled-writer-ingest",
            upstream_refs=(contract.task_digest,output_ref.bytes_digest,contract.identity.validator_digest))
        commit_publication_generation(root,manifest=manifest)
        switch_publication_active(root,manifest=manifest,expected_active_manifest_digest=None,expected_fence=int(pointer.fences.get("section_draft:writer",0)))
        index,_=load_index_for_reading(root)
        read=read_artifact_validated(index,"section_draft","writer",out_root=root)
        return read.members["acceptance"]
