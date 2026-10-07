"""Offline real-Host material builder. Caller supplies actual measured paths.

This builds original compiler inputs only, not claims, reserves or receipts.
The actual DSH Host subsequently owns those private worker operations.
"""
from dataclasses import asdict
import sys
from pathlib import Path

from code2paper.agentic.authoring_execution_identity import CompositionSpecV1
from code2paper.agentic.digest import canonical_json_bytes, digest_json
from code2paper.integrations.dsh.artifacts import TaskScope
from code2paper.integrations.dsh.protocol import strict_json_loads, MAX_FRAME_BYTES
from code2paper.integrations.dsh.worker import rpc_schema_digest
from code2paper.integrations.dsh.writer_contract import WriterTaskResultV1
from tests.integrations.dsh.stage04_support import durable_material


def main():
    values=strict_json_loads(sys.stdin.buffer.read())
    root=Path(values["root"])
    spec=CompositionSpecV1(files={name:Path(value) for name,value in values["files"].items()},
        trees={name:Path(value) for name,value in values["trees"].items()},
        effective_config={"model":"deepseek-v4-flash","options":{"provider":"deepseek","temperature":0.2,
            "reasoningEffort":"off","maxTokens":4096},"worker_version":"dsh-private-worker/1",
            "renderer_version":"native-text/1","tokenizer_version":"conservative_utf8_bytes_div_4",
            "meter_version":"conservative_utf8_bytes_div_4","backend_resource_key":"fake-http:"+values["endpoint"]})
    if 'native_tool_choice' in values:
        spec.effective_config['options']['nativeToolChoice'] = values['native_tool_choice']
    fixture_mode=values.get("fixture_mode","qualification")
    if fixture_mode not in {"qualification","normal"}:
        raise ValueError("stage04_fixture_mode_invalid")
    scope=TaskScope("execution:stage04-normal-host" if fixture_mode == "normal" else "execution:stage04-real-host","task:writer",0)
    material={}
    multistep=values.get('multistep') is True
    overrides={'max_writer_calls':0} if values.get('zero_writer_budget') is True else {}
    if values.get('compaction') is True:
        overrides.update(extra_roles='compaction',max_compaction_calls=1,output_token_reserve_compaction=256,
            max_request_input_tokens_compaction=32768,scaffolding_token_reserve_compaction=512)
    facade,_,frozen,input,budget,bootstrap=durable_material(root,spec,prepare_contract=False,scope=scope,wall_seconds=300,
        material_sink=material,page_kind=values.get('page_kind','technical'),
        profile_overrides=overrides,
        workflow_version='writer-multistep/2' if multistep else 'writer-single-request/1',
        epoch_limits=dict(max_model_requests=3,max_input_tokens=131072,max_output_tokens=8192,max_tool_calls=6,
            max_tool_return_bytes=8192,max_wall_seconds=300,max_terminal_candidates=1) if multistep else None)
    research=WriterTaskResultV1.model_validate_json(canonical_json_bytes({"schema_version":"WriterTaskResultV1","result":{
        "outcome":"research_required","requests":[{"request_id":"request:offline-gap",
            "section_id":material["section"].section_id,"argument_unit_id":"unit:offline-gap",
            "missing_rhetorical_move":"mechanism_overview","exact_question":"Which repository span establishes the scalar operation?",
            "required_authority_lane":"executable_hard"}]}}))
    result={"bootstrap":str(bootstrap),"scope":asdict(scope),"frozen_ref":frozen.model_dump(mode="json"),
        "input":input.model_dump(mode="json"),"budget_ref":budget.model_dump(mode="json"),
        "composition_digest":facade.composition["composition_digest"],
        "tokenizer_digest":facade.composition["files"]["tokenizer"]["digest"],
        "writer_raw":material["writer_raw"],"fixture_model":material["model"],"fixture_profile":material["profile"],
        "research_required_raw":research.model_dump_json(),
        "initialize":{"protocol_version":"c2p-dsh/1","schema_digest":rpc_schema_digest(),
            "validator_digest":facade.composition["validator_digest"],"max_frame_bytes":MAX_FRAME_BYTES}}
    # The whole immutable composition remains in the bootstrap; no credentials.
    result["descriptor_digest"]=digest_json(result)
    print(canonical_json_bytes(result).decode())


if __name__ == "__main__":
    main()
