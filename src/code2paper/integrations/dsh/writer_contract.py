"""Private Writer contract, derived TaskView and model-only terminal union.

Authority digests use the existing Python canonical serializer. Wire-byte
identity is recorded independently. Accounting observations are deliberately
outside the content contract; no prepare snapshot grants send permission.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from code2paper.agentic.digest import digest_json
from code2paper.llm.response_schemas import PublicationMethodSectionOutputV1
from code2paper.agentic.method_argument_models import WritingResearchRequestV1
from .protocol import MAX_SAFE_INTEGER, WireModel, parse_model, ProtocolError

Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
# Frozen Pydantic/Rust regex Unicode White_Space accepted domain. No host \s.
IDENTIFIER_CHARACTER_RULE = "unicode-white-space-nonblank/1"
IDENTIFIER_WHITESPACE_RANGES = ((0x0009, 0x000D), (0x0020, 0x0020), (0x0085, 0x0085),
    (0x00A0, 0x00A0), (0x1680, 0x1680), (0x2000, 0x200A), (0x2028, 0x2029),
    (0x202F, 0x202F), (0x205F, 0x205F), (0x3000, 0x3000))
IDENTIFIER_PATTERN = r"[^\u0009-\u000d\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]"
Identifier = Annotated[str, Field(min_length=1, max_length=256, pattern=IDENTIFIER_PATTERN,
    json_schema_extra={"x-c2p-character-rule": IDENTIFIER_CHARACTER_RULE})]
Counter = Annotated[int, Field(ge=0, le=MAX_SAFE_INTEGER)]
Positive = Annotated[int, Field(ge=1, le=MAX_SAFE_INTEGER)]


class ArtifactRefV1(WireModel):
    schema_version: Literal["ArtifactRefV1"]
    artifact_id: Digest
    execution_id: Identifier
    task_id: Identifier
    task_epoch: Counter
    media_type: Literal["application/json", "text/plain", "application/octet-stream"]
    byte_length: Counter
    bytes_digest: Digest
    semantic_digest: Digest | None

    @model_validator(mode="after")
    def _identity(self):
        if self.artifact_id != self.bytes_digest:
            raise ValueError("artifact_digest_mismatch")
        return self


class WriterIdentityV1(WireModel):
    engine_digest: Digest
    target_digest: Digest
    intent_digest: Digest
    claims_digest: Digest
    profile_digest: Digest
    model_digest: Digest
    validator_digest: Digest
    composition_digest: Digest
    renderer_digest: Digest
    tokenizer_digest: Digest


class WriterEpochLimitsV1(WireModel):
    max_model_requests: Literal[1]
    max_input_tokens: Positive
    max_output_tokens: Positive
    max_tool_calls: Counter
    max_wall_seconds: Positive

    @model_validator(mode="before")
    @classmethod
    def _request_integer(cls,value):
        if isinstance(value,dict) and type(value.get("max_model_requests")) is not int:
            raise ValueError("model_request_limit_type_invalid")
        return value


class WriterEpochLimitsV2(WireModel):
    """Explicit multi-request epoch; V1's Literal[1] remains unchanged."""
    max_model_requests: Positive
    max_input_tokens: Positive
    max_output_tokens: Positive
    max_tool_calls: Counter
    max_tool_return_bytes: Positive
    max_wall_seconds: Positive
    max_terminal_candidates: Literal[1] = 1

    @model_validator(mode="before")
    @classmethod
    def _strict_terminal_limit(cls,value):
        if isinstance(value,dict) and "max_terminal_candidates" in value and type(value["max_terminal_candidates"]) is not int:
            raise ValueError("terminal_candidate_limit_type_invalid")
        return value


class WriterTaskContractV1(WireModel):
    schema_version: Literal["WriterTaskContractV1"]
    protocol_version: Literal["c2p-dsh/1"]
    workflow_version: Literal["writer-single-request/1"]
    accounting_version: Literal["c2p-dsh-task-loop-v1"]
    storage_version: Literal["publication-generation/1"]
    parser_version: Literal["publication-writer/1"]
    execution_id: Identifier
    workflow_id: Identifier
    node_id: Identifier
    task_id: Identifier
    scope_id: Identifier
    task_epoch: Counter
    expected_state_revision: Counter
    writer_request_ref: ArtifactRefV1
    private_input_ref: ArtifactRefV1
    formalizer_receipt_ref: ArtifactRefV1
    narrative_ref: ArtifactRefV1
    manifest_ref: ArtifactRefV1
    plan_ref: ArtifactRefV1
    resolved_snapshot_ref: ArtifactRefV1
    read_set: tuple[ArtifactRefV1, ...]
    author_surface_digest: Digest
    binding_contract_digest: Digest
    technical_bytes_digest: Digest
    identity: WriterIdentityV1
    dsh_wire_contract_ref: ArtifactRefV1
    renderer_version: Identifier
    model: Identifier
    effective_options: dict[str, Any]
    terminal_schema_digest: Digest
    post_clamp_max_output_tokens: Positive
    epoch_limits: WriterEpochLimitsV1
    task_digest: Digest

    @model_validator(mode="after")
    def _bindings(self):
        values = self.model_dump(mode="json", exclude={"task_digest"})
        if digest_json(values) != self.task_digest:
            raise ValueError("task_digest_mismatch")
        for ref in (self.writer_request_ref, self.private_input_ref, self.formalizer_receipt_ref,
                    self.narrative_ref, self.manifest_ref, self.plan_ref, self.resolved_snapshot_ref,
                    self.dsh_wire_contract_ref, *self.read_set):
            if (ref.execution_id, ref.task_id, ref.task_epoch) != (self.execution_id, self.task_id, self.task_epoch):
                raise ValueError("artifact_scope_mismatch")
        if self.post_clamp_max_output_tokens > self.epoch_limits.max_output_tokens:
            raise ValueError("output_cap_exceeds_epoch")
        return self


class WriterTaskContractV2(WriterTaskContractV1):
    """Same frozen content owners and quality parser, explicit V2 execution."""
    schema_version: Literal["WriterTaskContractV2"]
    workflow_version: Literal["writer-multistep/2"]
    accounting_version: Literal["c2p-dsh-task-loop-v2"]
    epoch_limits: WriterEpochLimitsV2


def parse_writer_contract(raw: bytes) -> WriterTaskContractV1 | WriterTaskContractV2:
    from .protocol import strict_json_loads
    value=strict_json_loads(raw)
    schema=value.get("schema_version") if isinstance(value,dict) else None
    if schema == "WriterTaskContractV1":
        return parse_model(raw,WriterTaskContractV1)
    if schema == "WriterTaskContractV2":
        return parse_model(raw,WriterTaskContractV2)
    raise ProtocolError("writer_contract_version_unsupported")


class WriterDraftV1(WireModel):
    outcome: Literal["draft"]
    draft: PublicationMethodSectionOutputV1


class WriterResearchRequiredV1(WireModel):
    outcome: Literal["research_required"]
    requests: Annotated[tuple[WritingResearchRequestV1, ...], Field(min_length=1)]


class WriterBlockedV1(WireModel):
    outcome: Literal["blocked"]
    reason: Identifier
    recovery_action: Annotated[str, Field(min_length=1, max_length=4096)]


class WriterTaskResultV1(WireModel):
    schema_version: Literal["WriterTaskResultV1"]
    result: Annotated[WriterDraftV1 | WriterResearchRequiredV1 | WriterBlockedV1, Field(discriminator="outcome")]


class WriterWireProjectionV1(WireModel):
    schema_version: Literal["WriterWireProjectionV1"]
    protocol_version: Literal["c2p-dsh/1"]
    renderer_version: Identifier
    renderer_digest: Digest
    composition_digest: Digest
    input_digest: Digest
    task_view_digest: Digest
    terminal_schema_digest: Digest
    model: Identifier
    effective_options: dict[str, Any]
    post_clamp_max_output_tokens: Positive
    system_text: str
    user_text: str
    tools: tuple[dict[str, Any], ...]
    measurement_ref: ArtifactRefV1
    wire_equivalence_ref: ArtifactRefV1
    projection_digest: Digest

    @model_validator(mode="after")
    def _digest(self):
        if self.projection_digest != digest_json(self.model_dump(mode="json", exclude={"projection_digest"})):
            raise ValueError("projection_digest_mismatch")
        return self


def seal_contract(values: dict[str, Any]) -> WriterTaskContractV1 | WriterTaskContractV2:
    from code2paper.agentic.digest import canonical_json_bytes
    payload = {key: value for key, value in values.items() if key != "task_digest"}
    payload["task_digest"] = digest_json(payload)
    return parse_writer_contract(canonical_json_bytes(payload))


def derive_task_view(request: dict[str, Any]) -> dict[str, Any]:
    # Exactly the real request builder's visible input; no second author/evidence compiler.
    from copy import deepcopy
    return deepcopy(request["input_payload"])


def terminal_schema() -> dict[str, Any]:
    return WriterTaskResultV1.model_json_schema()


class WriterInputRefV1(WireModel):
    """Host-private render input, populated from a kernel-issued request ref."""
    schema_version: Literal["WriterInputRefV1"]
    request_ref: ArtifactRefV1
    writer_request: dict[str, Any]
    task_view_json: str
    terminal_schema: dict[str, Any]
    native_terminal_schema: dict[str, Any]
    native_schema_enforcement: tuple[dict[str, Any], ...]
    terminal_instruction: str
    model: Identifier
    effective_options: dict[str, Any]
    post_clamp_max_output_tokens: Positive
    composition_digest: Digest
    renderer_version: Identifier
    renderer_digest: Digest
    input_digest: Digest

    @model_validator(mode="after")
    def _bindings(self):
        from code2paper.agentic.digest import canonical_json_bytes
        if self.task_view_json != canonical_json_bytes(derive_task_view(self.writer_request)).decode("utf-8"):
            raise ValueError("task_view_mismatch")
        if self.request_ref.bytes_digest != digest_json(self.writer_request):
            raise ValueError("request_ref_digest_mismatch")
        if self.input_digest != digest_json(self.model_dump(mode="json",exclude={"input_digest"})):
            raise ValueError("input_digest_mismatch")
        return self


def native_terminal_schema(writer_request: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Registration shape plus explicit full-schema enforcement obligations.

    Original length constraints remain full-schema guard obligations. The
    raw native tool interface additionally carries task-derived minItems;
    the project terminal guard enforces them before concluding the turn.
    This shape alone never authorizes acceptance.
    """
    full = terminal_schema()
    obligations: list[dict[str, Any]] = []
    allowed = {"type","oneOf","properties","required","additionalProperties","items","enum","const","description","title","default","examples"}
    def visit(node: dict[str, Any], pointer: str) -> dict[str, Any]:
        if "$ref" in node:
            reference = node["$ref"]
            if not reference.startswith("#/$defs/"):
                raise ValueError("terminal_schema_reference_unsupported")
            return visit(full["$defs"][reference.split("/")[-1]],pointer)
        result = {}
        for key,value in node.items():
            if key == "$defs": continue
            if key == "anyOf":
                # Only disjoint nullable scalar unions are converted. Overlapping
                # anyOf would not have the semantics of exact-one oneOf.
                nullable = len(value) == 2 and sum(branch.get("type") == "null" for branch in value) == 1
                enum_sets = [set(branch.get("enum", [branch["const"]] if "const" in branch else [])) for branch in value]
                disjoint_enums = all(enum_sets) and all(not a.intersection(b) for i,a in enumerate(enum_sets) for b in enum_sets[i+1:])
                if not (nullable or disjoint_enums):
                    raise ValueError("terminal_union_unsupported")
                result["oneOf"]=[visit(branch,f"{pointer}/oneOf/{index}") for index,branch in enumerate(value)]
            elif key == "properties": result[key]={name:visit(schema,f"{pointer}/properties/{name}") for name,schema in value.items()}
            elif key == "items": result[key]=visit(value,f"{pointer}/items")
            elif key == "oneOf": result[key]=[visit(schema,f"{pointer}/oneOf/{index}") for index,schema in enumerate(value)]
            elif key in allowed: result[key]=value
            else: obligations.append({"pointer":pointer,"keyword":key,"value":value,"enforced_by":"full-schema-terminal-guard-and-python"})
        branches=result.get("oneOf")
        if branches and all(branch.get("type") == "object" for branch in branches):
            # Native DSH rejects type together with oneOf. Guide object
            # encoding through a supported annotation, preserving every
            # branch and the original full-schema guard.
            result["description"]=("Pass this value as a JSON object, never as a string "
                "containing JSON. Follow exactly one of the declared branches.")
        properties = result.get("properties", {})
        if {"section_id", "paragraphs"}.issubset(properties):
            result["required"] = list(dict.fromkeys([*result.get("required", []), "paragraphs"]))
            properties["paragraphs"].pop("default", None)
            properties["paragraphs"]["description"] = (
                "Emit the task's structured paragraphs with their original paragraph identifiers, "
                "paragraph_markdown and explicit witnesses. Do not replace them with section text alone."
            )
        if {"paragraph_id", "paragraph_markdown", "witnesses"}.issubset(properties):
            # The publication parser's legacy default is useful when reading
            # old output, but is not an instruction to omit evidence bindings
            # from a new Writer candidate. Make that existing field explicit
            # in the native emission contract; domain acceptance still belongs
            # to the original required-target and semantic assessors.
            result["required"] = list(dict.fromkeys([*result.get("required", []), "witnesses"]))
            witnesses = properties["witnesses"]
            witnesses.pop("default", None)
            witnesses["description"] = (
                "Explicitly provide a source-bound witness for every required Writer-owned target "
                "in this paragraph's frozen witness_contract.targets. Binder-owned atom witnesses "
                "and internal sidecar bindings are supplied separately; do not invent them. "
                "Use an empty array only when this paragraph has no required Writer-owned targets. Each exact_text "
                "must quote one unique contiguous clause you wrote that preserves the supplied target "
                "semantics. A target identifier alone does not supply evidence."
            )
        return result
    native = visit(full, "")
    if writer_request is not None:
        from copy import deepcopy
        payload = derive_task_view(writer_request)
        rows = (payload.get("narrative_plan") or {}).get("paragraphs") or []
        if payload.get("paragraph_transaction_required") and rows:
            ids = [row.get("paragraph_id") for row in rows]
            if any(not isinstance(value, str) or not value.strip() for value in ids) or len(set(ids)) != len(ids):
                raise ValueError("native_paragraph_scope_invalid")
            for branch in native["properties"]["result"]["oneOf"]:
                if "draft" not in branch.get("properties", {}):
                    continue
                paragraphs = branch["properties"]["draft"]["properties"]["paragraphs"]
                paragraphs["minItems"] = len(rows)
                base = paragraphs["items"]
                scoped = []
                for row in rows:
                    item = deepcopy(base)
                    item["properties"]["paragraph_id"]["const"] = row["paragraph_id"]
                    # This is only the Writer's visible, required detail set.
                    # Binder-owned atom contracts and private exact anchors
                    # never become model-facing schema material.
                    targets = (row.get("witness_contract") or {}).get("targets") or []
                    detail_ids = tuple(dict.fromkeys([
                        *row.get("required_detail_ids", []),
                        *(target["target_id"] for target in targets
                        if target.get("target_kind") == "detail"
                        and target.get("render_policy") == "required"),
                    ]))
                    if detail_ids:
                        witnesses = item["properties"]["witnesses"]
                        witnesses["minItems"] = len(detail_ids)
                        witnesses["description"] += (
                            " Required detail target identifiers for this paragraph: "
                            + ", ".join(detail_ids) + ". Supply each with its own complete exact clause."
                        )
                    scoped.append(item)
                paragraphs["items"] = scoped[0] if len(scoped) == 1 else {"oneOf": scoped}
    return native, obligations


def seal_projection(values: dict[str, Any]) -> WriterWireProjectionV1:
    from code2paper.agentic.digest import canonical_json_bytes
    payload={key:value for key,value in values.items() if key != "projection_digest"}
    payload["projection_digest"]=digest_json(payload)
    return parse_model(canonical_json_bytes(payload),WriterWireProjectionV1)


def _main() -> None:
    """Local byte/seal utility for C00 tests; it grants no domain receipt."""
    import sys
    from code2paper.agentic.digest import canonical_json_bytes
    from .protocol import strict_json_loads, MAX_FRAME_BYTES
    raw=sys.stdin.buffer.read(MAX_FRAME_BYTES+1)
    if len(sys.argv) != 2 or sys.argv[1] != "seal-projection":
        raise SystemExit("unsupported_operation")
    print(canonical_json_bytes(seal_projection(strict_json_loads(raw))).decode("utf-8"))


if __name__ == "__main__":
    _main()


class WriterMeasurementV1(WireModel):
    schema_version: Literal["WriterMeasurementV1"]
    input_digest: Digest
    renderer_digest: Digest
    tokenizer_digest: Digest
    meter_version: Identifier
    measured_input_tokens: Positive
    context_tokens: Positive
    safety_margin_tokens: Counter
    thinking_tokens: Counter
    post_clamp_max_output_tokens: Positive
    measured_wire_digest: Digest


class WriterWireEquivalenceV1(WireModel):
    schema_version: Literal["WriterWireEquivalenceV1"]
    input_digest: Digest
    renderer_digest: Digest
    composition_digest: Digest
    projection_material_digest: Digest
    loop_request_ref: ArtifactRefV1
    provider_wire_ref: ArtifactRefV1
    comparison_ref: ArtifactRefV1
    transport_whitelist: tuple[Literal["request_id", "tool_call_id", "http.authorization", "http.user-agent", "http.host", "http.connection", "http.content-length", "request.signal", "request.sessionId", "messages.id", "messages.createdAt"], ...]
