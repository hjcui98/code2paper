"""Host-private preparation over frozen owner inputs and observed renderer wire.

No model or network operation belongs here. A projection without prior C00
loop/provider evidence is unavailable. This is not a task claim/budget service.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from code2paper.agentic.authoring_execution_identity import CompositionSpecV1,validate_execution_composition
from code2paper.agentic.digest import canonical_json_bytes,digest_bytes,digest_json
from code2paper.agentic.page_contract_recheck import author_surface_digest,binding_contract_digest
from code2paper.agentic.unified_context_models import ConsumerTechnicalPageV2
from code2paper.llm.client import LLMRequest,LLMResponse
from code2paper.llm.section_writer import (
    WriterSectionInput,assess_publication_content_acceptance,build_publication_writer_request,
    parse_publication_writer_response,
)
from .artifacts import ArtifactStore,TaskScope
from .protocol import ProtocolError,parse_model
from .task_store import TaskStore, SerialBackendAdmission
from .writer_contract import (
    ArtifactRefV1,WriterInputRefV1,WriterTaskContractV1,WriterTaskContractV2,WriterWireProjectionV1,
    WriterMeasurementV1,WriterWireEquivalenceV1,derive_task_view,native_terminal_schema,
    seal_contract,terminal_schema,WriterIdentityV1,WriterEpochLimitsV1,WriterEpochLimitsV2,
)

TERMINAL_INSTRUCTION = (
    "The only outer output is one c2p_terminal tool call with an object containing exactly "
    'schema_version="WriterTaskResultV1" and result. '
    'For draft the structure is {"schema_version":"WriterTaskResultV1",'
    '"result":{"outcome":"draft","draft":<original section object>}}. '
    "Earlier instructions to return a section object apply only to result.draft, not to the outer object. "
    "Do not return a string or an unwrapped section. Use the supplied schema for every branch. "
    "Invoke the registered c2p_terminal function through the native tool-call channel. "
    "The function name must be exactly c2p_terminal. Quotes, whitespace, markup and parameter "
    "tags are not part of its name. Put schema_version and result in the arguments object, "
    "never in the function name. Follow the backend-provided tool serialization format. "
    "Do not write its JSON arguments, a Markdown code fence, or a simulated function call in assistant text. "
    "An ordinary text response is rejected even when it contains a valid-looking JSON object. "
    "Consume each required frozen formula package by its exact [[FORMULA:<package_id>]] placeholder "
    "in paragraph_markdown. Retain its original package id in used_formula_package_ids. "
    "Formula metadata or a copied package id cannot replace a placeholder. Do not write an inline "
    "equation in place of a package, change its expression, or remove a formula obligation. "
    "Explain each operation in words and mention its individual symbols; do not join symbols "
    "with an operator in inline math. The supplied placeholder owns the mathematical expression. "
    "Earlier instructions that the separate Binder supplies witnesses apply only to Binder-owned "
    "atom witnesses and internal sidecar bindings. They do not remove the Writer's detail-witness duty. "
    "For every required Writer-owned detail in each paragraph's frozen witness_contract.targets, "
    "include a detail witness in that paragraph's witnesses array. This duty applies even when "
    "rendered_detail_ids is empty or omitted. Do not invent Binder-owned atom witnesses. "
    "Its exact_text must be one unique substring of your paragraph and preserve the supplied source "
    "operation, operands, result, conditions and polarity. Select a full clause or sentence "
    "that states the complete relationship, including its result; an operand-only fragment is insufficient. "
    "Preserve the supplied source-bound semantic description together with the operation. "
    "State the source operand/operator relationship "
    "explicitly in prose; a detail id or formula placeholder alone does not prove prose coverage. "
    "Python attaches Binder-owned atom witnesses without changing your prose. "
    "Otherwise return typed research_required requests or blocked with reason and recovery_action. "
    "Tool completion does not mean accepted. Closing prose cannot replace terminal arguments."
)


@dataclass(frozen=True)
class ControlledHostContext:
    """Injected by private Host bootstrap, never parsed from a model terminal.

    This stage deliberately does not pretend to own an R01 durable claim.
    """
    scope: TaskScope
    snapshot_digest: str
    content_revision: int
    fence: int
    caller: str
    child_id: str
    session_id: str
    turn_id: str | int
    step_id: str | int
    tool_call_id: str
    request_id: str
    claim_mode: str = "stage03-controlled-context"
    role: str = "host"


class WriterFacade:
    def __init__(self, *, store: ArtifactStore, context: ControlledHostContext,
                 composition_spec: CompositionSpecV1, composition: dict[str,Any], engine_root: Path,
                 current_state: Callable[[],tuple[int,int,str]] | None = None,
                 request_meter: Callable[[bytes],int] | None = None,
                 task_store: TaskStore | None = None,
                 backend_admission: SerialBackendAdmission | None = None):
        self.store=store;self.context=context;self.spec=composition_spec;self.composition=composition;self.engine_root=engine_root
        self.request_meter=request_meter
        self.task_store=task_store
        self.backend_admission=backend_admission
        self.claim: dict[str,Any] | None = None
        self.recovery_only=False
        def default_state():
            original = (context.content_revision, context.fence, context.snapshot_digest)
            return task_store.current_content_state(original) if task_store is not None else original
        self.current_state=current_state or default_state

    def authorize(self, *, preparation: bool = False, replay: bool = False):
        if self.context.role != "host" or self.context.scope != self.store.scope:
            raise ProtocolError("host_permission_denied")
        if self.context.claim_mode == "stage03-controlled-context":
            if self.task_store is not None:
                raise ProtocolError("controlled_context_cannot_claim")
            return
        if (self.context.claim_mode != "dsh-durable-claim/1" or self.task_store is None
                or self.task_store.scope != self.store.scope or self.task_store.root != self.store.root
                or self.backend_admission is None):
            raise ProtocolError("host_permission_denied")
        if preparation:
            return
        if self.claim is None:
            raise ProtocolError("durable_claim_required")
        view=self.task_store.authorize(self.claim,allow_terminal=replay)
        self.backend_admission.authorize_observed_owner(execution_id=self.store.scope.execution_id,
            run_root=self.store.root,local_replay=replay or self.recovery_only)
        if view["binding"] != {"child_id":self.context.child_id,"session_id":self.context.session_id}:
            raise ProtocolError("durable_child_binding_required")

    def read_grant(self, *, grant_id: str, offset: int, length: int) -> dict[str,Any]:
        """Model-visible bytes only through a privately issued durable grant."""
        self.authorize()
        self.check_current()
        self.verify_composition()
        from .scoped_reads import ScopedReads
        if self.task_store is None or self.claim is None:
            raise ProtocolError("durable_claim_required")
        return ScopedReads(self.task_store,self.store,self.current_state).read(
            self.claim,session_id=self.context.session_id,
            grant_id=grant_id,offset=offset,length=length)

    def public_read_grants(self, contract: WriterTaskContractV2) -> list[dict[str,Any]]:
        """Issue bounded navigation over the original *public* Writer TaskView.

        No private section, frozen archive, golden answer or whole read-set is
        exposed. Exact evidence remains in the original full TaskView; a
        navigation read does not promote it or invent a new source license.
        """
        self.authorize();self.verify_composition();self.check_contract_current(contract)
        if not isinstance(contract,WriterTaskContractV2):
            raise ProtocolError('multistep_contract_required')
        prepared=self.task_store.read()['prepared']
        if self.store.read_json(parse_model(canonical_json_bytes(prepared['contract_ref']),ArtifactRefV1)) != contract.model_dump(mode='json'):
            raise ProtocolError('dsh_task_contract_ref_mismatch')
        limits=contract.epoch_limits
        if not limits.max_tool_calls:return []
        public=self.store.read_json(contract.writer_request_ref)['input_payload']
        ref=self.store.put_json(public)
        from .scoped_reads import ScopedReads
        reads=ScopedReads(self.task_store,self.store,self.current_state)
        member={'ref':ref.model_dump(mode='json'),'kind':'navigation','start':0,'end':ref.byte_length}
        reads.configure(self.claim,session_id=self.context.session_id,
                        max_calls=limits.max_tool_calls,max_bytes=limits.max_tool_return_bytes,
                        read_set=[member])
        grant=reads.issue(self.claim,session_id=self.context.session_id,ref=ref,
                         kind='navigation',start=0,end=ref.byte_length)
        return [{'grant_id':grant,'kind':'navigation','byte_length':ref.byte_length}]

    def check_current(self):
        if self.current_state() != (self.context.content_revision,self.context.fence,self.context.snapshot_digest):
            raise ProtocolError("task_revision_or_fence_stale")

    def verify_composition(self):
        try: return validate_execution_composition(self.spec,self.composition,engine_root=self.engine_root)
        except ValueError as error: raise ProtocolError(str(error).split(":")[0]) from error

    def freeze_input(self, *, section: WriterSectionInput, page: ConsumerTechnicalPageV2,
                     narrative: Any, manifest: Any, plan: Any, formalizer: Any,
                     identity: dict[str,Any], epoch_limits: dict[str,Any],
                     workflow_version: str = "writer-single-request/1") -> ArtifactRefV1:
        """Store complete frozen inputs after original owner validation/rebuild."""
        self.authorize(preparation=True);self.check_current();self.verify_composition()
        if workflow_version not in {"writer-single-request/1","writer-multistep/2"}:
            raise ProtocolError("writer_workflow_version_unsupported")
        limits_model=WriterEpochLimitsV1 if workflow_version == "writer-single-request/1" else WriterEpochLimitsV2
        epoch_limits=parse_model(canonical_json_bytes(epoch_limits),limits_model).model_dump(mode="json")
        page=ConsumerTechnicalPageV2.model_validate_json(page.model_dump_json())
        if section.prompt_payload.get("shared_contexts") != [dict(page.technical_payload)]:
            raise ProtocolError("page_material_mismatch")
        if section.prompt_payload.get("unified_v2_page_id") != page.page_id:
            raise ProtocolError("page_scope_mismatch")
        pages={p.page_id:p for p in manifest.pages}
        if page.page_id not in pages or pages[page.page_id] != page:
            raise ProtocolError("page_manifest_mismatch")
        if formalizer.task_failures or formalizer.assertion_failures:
            raise ProtocolError("formalizer_not_complete")
        from code2paper.agentic.unified_context_models import ActualRequestReceiptV2
        for receipt_value in formalizer.receipts:
            receipt=ActualRequestReceiptV2.model_validate_json(canonical_json_bytes(receipt_value))
            if receipt.upstream_plan_digest != formalizer.plan_digest:
                raise ProtocolError("formalizer_receipt_plan_mismatch")
        packages=tuple(section.prompt_payload.get("formula_packages") or ())
        if packages and (not formalizer.accepted_packages or not formalizer.receipts):
            raise ProtocolError("formalizer_receipt_missing")
        from code2paper.agentic.formalization_agent import adapt_mechanism_formula_package_to_legacy
        accepted_packages={package.package_id:package for package in formalizer.accepted_packages}
        for package in packages:
            accepted=accepted_packages.get(package.get("package_id"))
            if accepted is None:
                raise ProtocolError("formalizer_package_not_accepted")
            adapted=adapt_mechanism_formula_package_to_legacy(accepted,section_id=section.section_id,
                consumer_paragraph_id=package.get("consumer_paragraph_id",""))
            if digest_json(adapted) != digest_json(package):
                raise ProtocolError("formalizer_package_binding_mismatch")
        succeeded={target for row in formalizer.receipts if row.get("delivery_status") == "accepted"
            and row.get("task_status") == "complete" for target in row.get("succeeded_task_ids",())}
        used_obligations={str(value) for package in packages for value in package.get("satisfied_obligation_ids",())}
        if not used_obligations.issubset(succeeded):
            raise ProtocolError("formalizer_obligations_not_complete")
        # Rebuild this exact private page through the original compiler adapter.
        from code2paper.agentic.publication_method_writer import _writer_section_inputs_v2
        rebuilt=_writer_section_inputs_v2(narrative_plan=narrative,formula_packages=packages,
            formula_obligations=tuple(section.prompt_payload.get("formula_obligations") or ()),
            consumer_workset_manifest=manifest,consumer_invocation_plan=plan)
        matches=[s for s in rebuilt if s.section_id == section.section_id and s.prompt_payload.get("unified_v2_page_id") == page.page_id]
        if len(matches) != 1 or asdict(matches[0]) != asdict(section):
            raise ProtocolError("private_input_rebuild_mismatch")
        request=build_publication_writer_request(section,system_prompt=section.system_prompt,
            schema_name="publication_method_section_v1",response_json_schema=__import__(
                "code2paper.agentic.unified_context_compiler",fromlist=["consumer_response_json_schema"]
            ).consumer_response_json_schema("writer",section_id=section.section_id))
        objects={"request":asdict(request),"section":asdict(section),"page":page.model_dump(mode="json"),
                 "narrative":narrative.model_dump(mode="json"),"manifest":manifest.model_dump(mode="json"),
                 "plan":plan.model_dump(mode="json"),"formalizer":formalizer.model_dump(mode="json")}
        refs={name:self.store.put_json(value).model_dump(mode="json") for name,value in objects.items()}
        return self.store.put_json({"schema_version":"FrozenWriterInputV1" if workflow_version == "writer-single-request/1" else "FrozenWriterInputV2","refs":refs,
            "identity":identity,"epoch_limits":epoch_limits,"expected_state_revision":self.context.content_revision,
            "snapshot_digest":self.context.snapshot_digest,"fence":self.context.fence})

    def check_frozen_current(self, frozen_ref: ArtifactRefV1) -> dict[str, Any]:
        """Reconsume the immutable owner snapshot against this Host's current binding."""
        self.authorize(preparation=True);self.check_current()
        frozen=self.store.read_json(frozen_ref)
        required={"schema_version","refs","identity","epoch_limits","expected_state_revision","snapshot_digest","fence"}
        if (not isinstance(frozen,dict) or set(frozen) != required
                or frozen["schema_version"] not in {"FrozenWriterInputV1","FrozenWriterInputV2"}):
            raise ProtocolError("frozen_input_schema_invalid")
        if (type(frozen["expected_state_revision"]) is not int or type(frozen["fence"]) is not int
                or (frozen["expected_state_revision"],frozen["fence"],frozen["snapshot_digest"]) !=
                   (self.context.content_revision,self.context.fence,self.context.snapshot_digest)):
            raise ProtocolError("frozen_revision_snapshot_or_fence_stale")
        identity=parse_model(canonical_json_bytes(frozen["identity"]),WriterIdentityV1).model_dump(mode="json")
        parse_model(canonical_json_bytes(frozen["epoch_limits"]),WriterEpochLimitsV1 if frozen["schema_version"] == "FrozenWriterInputV1" else WriterEpochLimitsV2)
        current={"engine_digest":self.composition["engine_digest"],"validator_digest":self.composition["validator_digest"],
            "composition_digest":self.composition["composition_digest"],
            "renderer_digest":self.composition["files"]["renderer"]["digest"],
            "tokenizer_digest":self.composition["files"]["tokenizer"]["digest"]}
        if any(identity[key] != value for key,value in current.items()):
            raise ProtocolError("contract_identity_mismatch")
        if not isinstance(frozen["refs"],dict) or set(frozen["refs"]) != {"request","section","page","narrative","manifest","plan","formalizer"}:
            raise ProtocolError("frozen_input_references_invalid")
        objects={name:self.store.read_json(parse_model(canonical_json_bytes(ref),ArtifactRefV1))
            for name,ref in frozen["refs"].items()}
        section=objects["section"];page=objects["page"]
        if (page["page_id"] != section["prompt_payload"]["unified_v2_page_id"]
                or section["prompt_payload"].get("shared_contexts") != [page["technical_payload"]]
                or sum(row == page for row in objects["manifest"]["pages"]) != 1):
            raise ProtocolError("frozen_page_material_mismatch")
        request=build_publication_writer_request(WriterSectionInput(**section),system_prompt=section["system_prompt"],
            schema_name="publication_method_section_v1",response_json_schema=__import__(
                "code2paper.agentic.unified_context_compiler",fromlist=["consumer_response_json_schema"]
            ).consumer_response_json_schema("writer",section_id=section["section_id"]))
        if digest_json(asdict(request)) != digest_json(objects["request"]):
            raise ProtocolError("frozen_request_binding_mismatch")
        self.check_current()
        return frozen

    def check_contract_current(self, contract: WriterTaskContractV1):
        """Bind a new effect to the prepared read-set, not just a fresh Host."""
        frozen=self.store.read_json(contract.resolved_snapshot_ref)
        expected_frozen="FrozenWriterInputV2" if contract.schema_version == "WriterTaskContractV2" else "FrozenWriterInputV1"
        if (frozen.get("schema_version") != expected_frozen
                or frozen.get("epoch_limits") != contract.epoch_limits.model_dump(mode="json")):
            raise ProtocolError("contract_execution_version_or_limits_mismatch")
        if (contract.expected_state_revision != self.context.content_revision
                or frozen["expected_state_revision"] != contract.expected_state_revision
                or frozen["snapshot_digest"] != self.context.snapshot_digest
                or frozen.get("fence") != self.context.fence):
            raise ProtocolError("contract_revision_snapshot_or_fence_stale")
        self.check_frozen_current(contract.resolved_snapshot_ref)
        identity=contract.identity.model_dump(mode="json")
        current={"engine_digest":self.composition["engine_digest"],
            "validator_digest":self.composition["validator_digest"],
            "composition_digest":self.composition["composition_digest"],
            "renderer_digest":self.composition["files"]["renderer"]["digest"],
            "tokenizer_digest":self.composition["files"]["tokenizer"]["digest"]}
        if identity != frozen["identity"] or any(identity[key] != value for key,value in current.items()):
            raise ProtocolError("contract_identity_mismatch")
        references={"request":"writer_request_ref","section":"private_input_ref",
            "formalizer":"formalizer_receipt_ref","narrative":"narrative_ref",
            "manifest":"manifest_ref","plan":"plan_ref"}
        if any(getattr(contract,field).model_dump(mode="json") != frozen["refs"][name]
               for name,field in references.items()):
            raise ProtocolError("contract_read_set_mismatch")
        if sorted(digest_json(ref) for ref in contract.read_set) != sorted(digest_json(ref) for ref in frozen["refs"].values()):
            raise ProtocolError("contract_read_set_mismatch")
        request=self.store.read_json(contract.writer_request_ref)
        page=self.store.read_json(parse_model(canonical_json_bytes(frozen["refs"]["page"]),ArtifactRefV1))
        section=self.store.read_json(contract.private_input_ref)
        plan=self.store.read_json(contract.plan_ref)
        invocations=[row for row in plan["invocations"] if not row.get("is_repair")
            and row.get("page_id") == page["page_id"]]
        if (contract.scope_id != section["section_id"]
                or page["page_id"] != section["prompt_payload"]["unified_v2_page_id"]
                or len(invocations) != 1 or invocations[0]["max_output_tokens"] != contract.post_clamp_max_output_tokens):
            raise ProtocolError("contract_page_scope_or_cap_mismatch")
        if (contract.author_surface_digest != author_surface_digest(request["input_payload"])
                or contract.binding_contract_digest != binding_contract_digest(request["input_payload"])
                or contract.technical_bytes_digest != page["technical_bytes_digest"]):
            raise ProtocolError("contract_material_digest_mismatch")
        config=self.composition["effective_config"]
        if (contract.model != config["model"] or contract.effective_options != config["options"]
                or contract.renderer_version != config["renderer_version"]
                or contract.terminal_schema_digest != digest_json(terminal_schema())
                or contract.epoch_limits.model_dump(mode="json") != frozen["epoch_limits"]
                or ("maxTokens" in config["options"] and config["options"]["maxTokens"] != contract.post_clamp_max_output_tokens)
                or contract.post_clamp_max_output_tokens > contract.epoch_limits.max_output_tokens):
            raise ProtocolError("contract_configuration_mismatch")

    def render_input(self, frozen_ref: ArtifactRefV1, *, cap: int) -> WriterInputRefV1:
        self.authorize(preparation=True);self.check_current();self.verify_composition()
        frozen=self.check_frozen_current(frozen_ref)
        request_ref=parse_model(canonical_json_bytes(frozen["refs"]["request"]),ArtifactRefV1)
        request=self.store.read_json(request_ref)
        native,enforcement=native_terminal_schema(request)
        config=self.composition["effective_config"]
        if config["options"].get("maxTokens") != cap:
            raise ProtocolError("cap_composition_reprepare_required")
        plan=self.store.read_json(parse_model(canonical_json_bytes(frozen["refs"]["plan"]),ArtifactRefV1))
        section=self.store.read_json(parse_model(canonical_json_bytes(frozen["refs"]["section"]),ArtifactRefV1))
        invocations=[row for row in plan["invocations"] if not row.get("is_repair")
            and row.get("page_id") == section["prompt_payload"]["unified_v2_page_id"]]
        if len(invocations) != 1 or invocations[0]["max_output_tokens"] != cap:
            raise ProtocolError("cap_plan_recompile_required")
        options=dict(config["options"])
        values=dict(schema_version="WriterInputRefV1",request_ref=request_ref.model_dump(mode="json"),
            writer_request=request,task_view_json=canonical_json_bytes(derive_task_view(request)).decode(),
            terminal_schema=terminal_schema(),native_terminal_schema=native,native_schema_enforcement=enforcement,
            terminal_instruction=TERMINAL_INSTRUCTION,model=config["model"],effective_options=options,
            post_clamp_max_output_tokens=cap,composition_digest=self.composition["composition_digest"],
            renderer_version=config["renderer_version"],renderer_digest=self.composition["files"]["renderer"]["digest"])
        values["input_digest"]=digest_json(values)
        result=parse_model(canonical_json_bytes(values),WriterInputRefV1)
        self.check_frozen_current(frozen_ref)
        return result

    def _verify_projection(self, input: WriterInputRefV1, projection: WriterWireProjectionV1):
        expected={"input_digest":input.input_digest,"renderer_digest":input.renderer_digest,
            "composition_digest":input.composition_digest,"model":input.model,"effective_options":input.effective_options,
            "post_clamp_max_output_tokens":input.post_clamp_max_output_tokens,
            "system_text":input.writer_request["prompt"]+"\n\n"+input.terminal_instruction,
            "user_text":input.task_view_json,"tools":[{"name":"c2p_terminal",
                "description":"Return the single WriterTaskResultV1 terminal candidate. No domain acceptance is granted.",
                "parameters":input.native_terminal_schema}]}
        if projection.renderer_version != input.renderer_version: raise ProtocolError("projection_material_mismatch")
        actual=projection.model_dump(mode="json")
        for key,value in expected.items():
            if actual[key] != value: raise ProtocolError("projection_material_mismatch")
        if projection.task_view_digest != digest_json(input.writer_request["input_payload"]) or projection.terminal_schema_digest != digest_json(input.terminal_schema):
            raise ProtocolError("projection_digest_binding_mismatch")
        evidence=parse_model(canonical_json_bytes(self.store.read_json(projection.wire_equivalence_ref)),WriterWireEquivalenceV1)
        if (evidence.input_digest,evidence.renderer_digest,evidence.composition_digest,evidence.projection_material_digest) != (
            input.input_digest,input.renderer_digest,input.composition_digest,digest_json(expected)):
            raise ProtocolError("wire_evidence_binding_mismatch")
        # Validate leaf bytes/semantic/scope before interpreting cross-bindings.
        comparison=self.store.read_json(evidence.comparison_ref)
        loop=self.store.read_json(evidence.loop_request_ref)
        provider=self.store.read_json(evidence.provider_wire_ref)
        if not isinstance(comparison,dict) or set(comparison) != {"binding","loop_digest","provider_digest"}:
            raise ProtocolError("wire_comparison_mismatch")
        if comparison.get("binding") != expected or comparison.get("loop_digest") != evidence.loop_request_ref.bytes_digest or comparison.get("provider_digest") != evidence.provider_wire_ref.bytes_digest:
            raise ProtocolError("wire_comparison_mismatch")
        if not isinstance(loop,dict) or "schema_version" in loop: raise ProtocolError("loop_wire_mismatch")
        if not isinstance(provider,dict) or "schema_version" in provider: raise ProtocolError("provider_wire_mismatch")
        messages=loop.get("messages",[])
        if len(messages) != 2 or [m.get("role") for m in messages] != ["system","user"]:
            raise ProtocolError("loop_wire_mismatch")
        for message,text in zip(messages,(projection.system_text,projection.user_text)):
            if message.get("content") != [{"type":"text","text":text}]: raise ProtocolError("loop_wire_mismatch")
        if loop.get("tools") != expected["tools"] or loop.get("model") != input.model or loop.get("maxTokens") != input.post_clamp_max_output_tokens:
            raise ProtocolError("loop_wire_mismatch")
        wire_messages=provider.get("messages",[])
        if len(wire_messages) != 2 or [m.get("role") for m in wire_messages] != ["system","user"]:
            raise ProtocolError("provider_wire_mismatch")
        for message,text in zip(wire_messages,(projection.system_text,projection.user_text)):
            if message.get("content") not in (text,[{"type":"text","text":text}]): raise ProtocolError("provider_wire_mismatch")
        schema_mode=input.effective_options.get("nativeToolSchemaMode")
        if schema_mode is not None and (schema_mode != "server-default" or input.effective_options.get("provider") != "openai"):
            raise ProtocolError("provider_options_mismatch")
        # Some structural-tag backends interpret explicit strict:false as an
        # opt-out from parameter constraints. Bind omission as its own policy;
        # retain the SDK default for every existing contract.
        expected_tools=[{"type":"function","function":{
            **tool,**({} if schema_mode == "server-default" else {"strict":False})
        }} for tool in expected["tools"]]
        if provider.get("tools") != expected_tools or provider.get("model") != input.model:
            raise ProtocolError("provider_wire_mismatch")
        if provider.get("max_tokens",provider.get("max_completion_tokens")) != input.post_clamp_max_output_tokens:
            raise ProtocolError("provider_cap_mismatch")
        if "temperature" in input.effective_options and provider.get("temperature") != input.effective_options["temperature"]:
            raise ProtocolError("provider_options_mismatch")
        # Profile-owned native selection affects dispatch material, not source
        # authority. Refuse unbound additions, omissions and changed names.
        choice = input.effective_options.get("nativeToolChoice")
        if choice is not None:
            if choice != "required" and choice != {"type":"function","function":{"name":"c2p_terminal"}}:
                raise ProtocolError("provider_options_mismatch")
            if provider.get("tool_choice") != choice:
                raise ProtocolError("provider_options_mismatch")
        elif "tool_choice" in provider:
            raise ProtocolError("provider_options_mismatch")
        thinking=input.effective_options.get("reasoningEffort")
        if input.effective_options.get("provider") == "deepseek" and thinking == "off":
            if provider.get("thinking") != {"type":"disabled"} or "reasoning_effort" in provider:
                raise ProtocolError("provider_options_mismatch")
        elif input.effective_options.get("provider") == "openai" and thinking == "off":
            template=self.composition["effective_config"].get("writer_chat_template_kwargs")
            actual=provider.get("chat_template_kwargs")
            if (template!={"enable_thinking":False} or type(template.get("enable_thinking")) is not bool
                    or actual!=template or type(actual.get("enable_thinking")) is not bool
                    or "reasoning_effort" in provider or "thinking_token_budget" in provider):
                raise ProtocolError("provider_options_mismatch")
        elif thinking is not None and provider.get("reasoning_effort") != thinking:
            raise ProtocolError("provider_options_mismatch")
        measurement=parse_model(canonical_json_bytes(self.store.read_json(projection.measurement_ref)),WriterMeasurementV1)
        writer_reserve=self.composition["effective_config"].get("writer_thinking_tokens")
        if input.effective_options.get("provider") == "openai" and thinking == "off":
            if type(writer_reserve) is not int or writer_reserve!=0 or measurement.thinking_tokens!=writer_reserve:
                raise ProtocolError("measurement_binding_mismatch")
        if (measurement.input_digest,measurement.renderer_digest,measurement.tokenizer_digest,measurement.measured_wire_digest) != (
            input.input_digest,input.renderer_digest,self.composition["files"]["tokenizer"]["digest"],evidence.provider_wire_ref.bytes_digest):
            raise ProtocolError("measurement_binding_mismatch")
        if self.request_meter is None: raise ProtocolError("request_meter_unavailable")
        measured=self.request_meter(self.store.read(evidence.provider_wire_ref))
        if type(measured) is not int or measured <= 0 or measured != measurement.measured_input_tokens:
            raise ProtocolError("measurement_tokens_mismatch")
        if measurement.meter_version != self.composition["effective_config"]["meter_version"]:
            raise ProtocolError("measurement_meter_mismatch")
        return measurement

    def prepare(self, frozen_ref: ArtifactRefV1, *, cap: int,
                project: Callable[[WriterInputRefV1],WriterWireProjectionV1], max_recompiles: int = 1,
                recompile: Callable[[ArtifactRefV1,int],ArtifactRefV1] | None = None) -> WriterTaskContractV1:
        self.authorize(preparation=True);self.check_current();self.verify_composition()
        frozen=self.check_frozen_current(frozen_ref)
        for attempt in range(max_recompiles+1):
            input=self.render_input(frozen_ref,cap=cap)
            projection=project(input)
            # Never accept an unsealed mutable in-memory projection.
            projection=parse_model(canonical_json_bytes(projection),WriterWireProjectionV1)
            measurement=self._verify_projection(input,projection)
            if measurement.measured_input_tokens > frozen["epoch_limits"]["max_input_tokens"]:
                raise ProtocolError("writer_epoch_input_budget_exceeded")
            allowed=measurement.context_tokens-measurement.measured_input_tokens-measurement.safety_margin_tokens-measurement.thinking_tokens
            if allowed < cap:
                if allowed <= 0 or attempt == max_recompiles: raise ProtocolError("writer_context_budget_exceeded")
                # New cap must produce a fresh complete render/evidence binding.
                if recompile is None: raise ProtocolError("cap_plan_recompile_required")
                frozen_ref=recompile(frozen_ref,allowed)
                frozen=self.check_frozen_current(frozen_ref)
                cap=allowed;continue
            if measurement.post_clamp_max_output_tokens != cap: raise ProtocolError("measurement_cap_mismatch")
            break
        refs={name:parse_model(canonical_json_bytes(value),ArtifactRefV1) for name,value in frozen["refs"].items()}
        request=self.store.read_json(refs["request"]);section=self.store.read_json(refs["section"]);page=self.store.read_json(refs["page"])
        identity=frozen["identity"]
        if identity["engine_digest"] != self.composition["engine_digest"] or identity["validator_digest"] != self.composition["validator_digest"] or identity["composition_digest"] != self.composition["composition_digest"] or identity["renderer_digest"] != input.renderer_digest:
            raise ProtocolError("contract_identity_mismatch")
        v2=frozen["schema_version"] == "FrozenWriterInputV2"
        values=dict(schema_version="WriterTaskContractV2" if v2 else "WriterTaskContractV1",protocol_version="c2p-dsh/1",workflow_version="writer-multistep/2" if v2 else "writer-single-request/1",
            accounting_version="c2p-dsh-task-loop-v2" if v2 else "c2p-dsh-task-loop-v1",storage_version="publication-generation/1",parser_version="publication-writer/1",
            execution_id=self.store.scope.execution_id,workflow_id="method-authoring",node_id="writer",task_id=self.store.scope.task_id,
            scope_id=section["section_id"],task_epoch=self.store.scope.task_epoch,expected_state_revision=frozen["expected_state_revision"],
            writer_request_ref=refs["request"],private_input_ref=refs["section"],formalizer_receipt_ref=refs["formalizer"],
            narrative_ref=refs["narrative"],manifest_ref=refs["manifest"],plan_ref=refs["plan"],resolved_snapshot_ref=frozen_ref,
            read_set=list(refs.values()),author_surface_digest=author_surface_digest(request["input_payload"]),
            binding_contract_digest=binding_contract_digest(request["input_payload"]),technical_bytes_digest=page["technical_bytes_digest"],
            identity=identity,dsh_wire_contract_ref=self.store.put_json(projection),renderer_version=input.renderer_version,
            model=input.model,effective_options=input.effective_options,terminal_schema_digest=digest_json(input.terminal_schema),
            post_clamp_max_output_tokens=cap,epoch_limits=frozen["epoch_limits"])
        self.check_frozen_current(frozen_ref)
        contract=seal_contract(values)
        self.verify_composition();self.check_contract_current(contract);self.check_current()
        return contract

    def verify_contract_dependencies(self, contract: WriterTaskContractV1) -> dict[str, Any]:
        """Local-only revalidation for a NEW effect; committed recovery bypasses it."""
        self.check_contract_current(contract)
        input=self.render_input(contract.resolved_snapshot_ref,cap=contract.post_clamp_max_output_tokens)
        projection=parse_model(canonical_json_bytes(self.store.read_json(contract.dsh_wire_contract_ref)),WriterWireProjectionV1)
        measurement=self._verify_projection(input,projection)
        if measurement.measured_input_tokens > contract.epoch_limits.max_input_tokens:
            raise ProtocolError("writer_epoch_input_budget_exceeded")
        allowed=measurement.context_tokens-measurement.measured_input_tokens-measurement.safety_margin_tokens-measurement.thinking_tokens
        if allowed < contract.post_clamp_max_output_tokens:
            raise ProtocolError("writer_context_budget_exceeded")
        if measurement.post_clamp_max_output_tokens != contract.post_clamp_max_output_tokens:
            raise ProtocolError("measurement_cap_mismatch")
        evidence=parse_model(canonical_json_bytes(self.store.read_json(projection.wire_equivalence_ref)),WriterWireEquivalenceV1)
        dependencies={"frozen_input":contract.resolved_snapshot_ref,"projection":contract.dsh_wire_contract_ref,
            "measurement":projection.measurement_ref,"wire_equivalence":projection.wire_equivalence_ref,
            "comparison":evidence.comparison_ref,"loop_request":evidence.loop_request_ref,"provider_wire":evidence.provider_wire_ref}
        frozen=self.check_frozen_current(contract.resolved_snapshot_ref)
        dependencies.update({"domain_"+name:parse_model(canonical_json_bytes(ref),ArtifactRefV1) for name,ref in frozen["refs"].items()})
        # Every JSON reference's semantic digest is mandatory, including raw wire.
        for ref in dependencies.values(): self.store.read_json(ref)
        self.verify_composition();self.check_current()
        return {"schema_version":"LocalWriterDependencyClosureV1","task_digest":contract.task_digest,
            "input_digest":input.input_digest,"projection_digest":projection.projection_digest,
            "dependencies":{name:ref.model_dump(mode="json") for name,ref in dependencies.items()}}

    def assess(self, contract: WriterTaskContractV1, raw_draft: str):
        self.authorize()
        section=WriterSectionInput(**self.store.read_json(contract.private_input_ref))
        request=LLMRequest(**self.store.read_json(contract.writer_request_ref))
        response=parse_publication_writer_response(LLMResponse(text=raw_draft,response_hash=digest_bytes(raw_draft.encode())),
            request=request,private_section=section)
        accepted,metrics=assess_publication_content_acceptance(section,response)
        return bool(accepted and not response.blocked_reason),metrics,response
