"""C03 real local publication owner and reader, with controlled provenance."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from code2paper.agentic.digest import canonical_json_bytes,digest_bytes,digest_json
from code2paper.agentic.authoring_artifact_index import load_index_for_reading,read_artifact_validated
from code2paper.integrations.dsh.protocol import ProtocolError,parse_model
from code2paper.integrations.dsh.result_ingest import OutputEnvelopeV1,ingest,ingest_key,record_output
from .stage03_support import local_test_facade,observed_output,terminal_raw
from .test_composition_identity import composition
from .test_writer_prepare_ingest import no_network_or_python_llm


@pytest.fixture
def domain(tmp_path,composition):return local_test_facade(tmp_path,composition)


def test_same_generation_prose_acceptance_authorship_and_lost_reply_retry(domain):
    facade,contract,material,_=domain
    envelope=observed_output(facade,terminal_raw(material))
    output=record_output(facade,contract,envelope)
    key=ingest_key(contract,output)
    receipt=ingest(facade,contract,output,idempotency_key=key)
    assert receipt["domain_status"] == "pending_validation" and receipt["local_only"]
    assert not {"candidate_complete","verified_complete","publication_ready"}.intersection(receipt)
    # A post-commit revision must not invalidate retrieval of the same receipt.
    facade.current_state=lambda:(2,9,digest_bytes(b"later-snapshot"))
    assert ingest(facade,contract,output,idempotency_key=key) == receipt
    root=facade.store.root/"dsh-local-outcomes"/digest_json(facade.context.scope.__dict__).split(":")[1]
    index,_=load_index_for_reading(root)
    read=read_artifact_validated(index,"section_draft","writer",out_root=root)
    assert set(read.members)=={"prose","acceptance","authorship","raw_result","provenance"}
    assert read.members["acceptance"] == receipt
    assert read.members["authorship"]["ledger"]["hard_gate_passed"]
    owners={span["owner"] for span in read.members["authorship"]["ledger"]["spans"]}
    assert owners=={"writer","formalizer"}
    assert read.members["prose"] and "[[FORMULA:" not in read.members["prose"]


@pytest.mark.parametrize("field",["execution_id","task_id","task_epoch","child_id","session_id","turn_id","step_id","tool_call_id","request_id"])
def test_host_binding_cannot_be_replaced(domain,field):
    facade,contract,material,_=domain
    with pytest.raises(ProtocolError,match="output_scope_mismatch|output_provenance_mismatch"):
        record_output(facade,contract,observed_output(facade,terminal_raw(material),**{field:1 if field=="task_epoch" else "wrong"}))


@pytest.mark.parametrize("raw",[b'{"schema_version":"WriterTaskResultV1","result":{"outcome":"accepted"}}',
    b'{"schema_version":"WriterTaskResultV1","result":{"outcome":"draft","draft":{},"caller":"host"}}',
    b'Closing prose is not tool arguments.',b'{"schema_version":"WriterTaskResultV1"'])
def test_selfreported_authority_closing_prose_and_incomplete_stream_reject(domain,raw):
    facade,contract,material,_=domain
    ref=facade.store.put(raw)
    values=observed_output(facade,terminal_raw(material)).model_dump(mode="json")
    values["adapter_arguments"]["ref"]=ref.model_dump(mode="json")
    envelope=parse_model(canonical_json_bytes(values),OutputEnvelopeV1)
    with pytest.raises(ProtocolError,match="schema_invalid|invalid_json"):
        record_output(facade,contract,envelope)


def test_content_changed_after_raw_observation_rejects(domain):
    facade,contract,material,_=domain
    raw=terminal_raw(material);env=observed_output(facade,raw)
    changed=json.loads(raw);changed["result"]["draft"]["paragraphs"][0]["paragraph_markdown"]+=" Host adds a sentence."
    values=env.model_dump(mode="json");values["normalized_arguments"]["ref"]=facade.store.put(canonical_json_bytes(changed)).model_dump(mode="json")
    with pytest.raises(ProtocolError,match="normalized_arguments_content_mismatch"):
        record_output(facade,contract,parse_model(canonical_json_bytes(values),OutputEnvelopeV1))


def test_different_result_with_new_valid_key_still_conflicts(domain):
    facade,contract,material,_=domain
    first=record_output(facade,contract,observed_output(facade,terminal_raw(material)))
    ingest(facade,contract,first,idempotency_key=ingest_key(contract,first))
    raw=canonical_json_bytes({"schema_version":"WriterTaskResultV1","result":{"outcome":"blocked","reason":"other","recovery_action":"retry new epoch"}})
    other=record_output(facade,contract,observed_output(facade,raw))
    with pytest.raises(ProtocolError,match="task_epoch_terminal_conflict"):
        ingest(facade,contract,other,idempotency_key=ingest_key(contract,other))
    with pytest.raises(ProtocolError,match="idempotency_key_mismatch"):
        ingest(facade,contract,other,idempotency_key=ingest_key(contract,first))


def test_unauthorized_caller_cannot_read_cached_receipt(domain):
    facade,contract,material,_=domain
    output=record_output(facade,contract,observed_output(facade,terminal_raw(material)))
    key=ingest_key(contract,output);ingest(facade,contract,output,idempotency_key=key)
    facade.context=replace(facade.context,role="model")
    with pytest.raises(ProtocolError,match="host_permission_denied"):
        ingest(facade,contract,output,idempotency_key=key)


def test_stale_fence_cannot_create_new_effect(domain):
    facade,contract,material,_=domain
    output=record_output(facade,contract,observed_output(facade,terminal_raw(material)))
    facade.current_state=lambda:(1,8,facade.context.snapshot_digest)
    with pytest.raises(ProtocolError,match="task_revision_or_fence_stale"):
        ingest(facade,contract,output,idempotency_key=ingest_key(contract,output))


def test_wrong_source_and_false_stream_complete_are_schema_rejected(domain):
    facade,contract,material,_=domain
    values=observed_output(facade,terminal_raw(material)).model_dump(mode="json")
    for changes in ({"source":"closing_prose"},{"arguments_complete":False},{"arguments_complete":1}):
        with pytest.raises(ProtocolError,match="schema_invalid"):
            parse_model(canonical_json_bytes({**values,**changes}),OutputEnvelopeV1)


def test_host_addition_after_assessment_has_no_lexical_owner(domain):
    facade,contract,material,_=domain
    from code2paper.integrations.dsh.result_ingest import _authorship
    from code2paper.integrations.dsh.writer_contract import WriterTaskResultV1
    raw=terminal_raw(material);parsed=parse_model(raw,WriterTaskResultV1)
    accepted,_,response=facade.assess(contract,canonical_json_bytes(parsed.result.draft).decode())
    assert accepted
    with pytest.raises(ProtocolError,match="authorship_unowned_lexical_span"):
        _authorship(facade,contract,parsed,response.text+"\nA novel Host sentence.",facade.store.put(raw))


def test_blocked_preserves_reason_and_action(domain):
    facade,contract,_,_=domain
    raw=canonical_json_bytes({"schema_version":"WriterTaskResultV1","result":{"outcome":"blocked","reason":"missing_material","recovery_action":"prepare a new frozen scope"}})
    output=record_output(facade,contract,observed_output(facade,raw))
    receipt=ingest(facade,contract,output,idempotency_key=ingest_key(contract,output))
    assert receipt["domain_status"]=="blocked" and receipt["detail"]=={"reason":"missing_material","recovery_action":"prepare a new frozen scope"}


def test_research_required_waits_without_running_research(domain):
    facade,contract,material,_=domain
    request=dict(request_id="rq:1",section_id=contract.scope_id,argument_unit_id="MA-L1_p1",
        missing_rhetorical_move="implementation_realization",exact_question="Which branch applies?",required_authority_lane="executable_hard")
    raw=canonical_json_bytes({"schema_version":"WriterTaskResultV1","result":{"outcome":"research_required","requests":[request]}})
    output=record_output(facade,contract,observed_output(facade,raw))
    receipt=ingest(facade,contract,output,idempotency_key=ingest_key(contract,output))
    assert receipt["domain_status"]=="waiting" and receipt["detail"]["requests"][0]["request_id"]=="rq:1"


def test_frozen_formula_must_be_actual_accepted_formalizer_package(domain):
    facade,_,material,_=domain
    formalizer=material['formalizer']
    changed=formalizer.accepted_packages[0].model_copy(update={'latex':'y = x'})
    forged=formalizer.model_copy(update={'accepted_packages':(changed,)})
    frozen=facade.store.read_json(domain[3])
    with pytest.raises(ProtocolError,match='formalizer_package_binding_mismatch'):
        facade.freeze_input(**{k:material[k] for k in ('section','page','narrative','manifest','plan')},
            formalizer=forged,identity=frozen['identity'],epoch_limits=frozen['epoch_limits'])


def test_absent_formalizer_receipt_cannot_authorize_formula(domain):
    facade,_,material,ref=domain
    frozen=facade.store.read_json(ref)
    with pytest.raises(ProtocolError,match='formalizer_receipt_missing'):
        facade.freeze_input(**{k:material[k] for k in ('section','page','narrative','manifest','plan')},
            formalizer=material['formalizer'].model_copy(update={'receipts':()}),
            identity=frozen['identity'],epoch_limits=frozen['epoch_limits'])


@pytest.mark.parametrize('field',['content_revision','snapshot_digest','fence'])
def test_old_contract_cannot_borrow_fresh_host_for_new_effect(domain,field):
    facade,contract,material,_=domain
    output=record_output(facade,contract,observed_output(facade,terminal_raw(material)))
    value=digest_bytes(b'new snapshot') if field=='snapshot_digest' else getattr(facade.context,field)+1
    facade.context=replace(facade.context,**{field:value})
    facade.current_state=lambda:(facade.context.content_revision,facade.context.fence,facade.context.snapshot_digest)
    with pytest.raises(ProtocolError,match='contract_revision_snapshot_or_fence_stale'):
        ingest(facade,contract,output,idempotency_key=ingest_key(contract,output))


@pytest.mark.parametrize('field',['validator_digest','composition_digest','renderer_digest','tokenizer_digest','engine_digest'])
def test_new_effect_rejects_contract_identity_disconnected_from_actual_composition(domain,field):
    facade,contract,material,_=domain
    from code2paper.integrations.dsh.writer_contract import seal_contract
    values=contract.model_dump(mode='json');values['identity'][field]=digest_bytes(b'wrong identity')
    contract=seal_contract(values)
    output=record_output(facade,contract,observed_output(facade,terminal_raw(material)))
    with pytest.raises(ProtocolError,match='contract_identity_mismatch'):
        ingest(facade,contract,output,idempotency_key=ingest_key(contract,output))


def test_committed_retry_with_fresh_host_still_returns_original_receipt(domain):
    facade,contract,material,_=domain
    output=record_output(facade,contract,observed_output(facade,terminal_raw(material)))
    key=ingest_key(contract,output);receipt=ingest(facade,contract,output,idempotency_key=key)
    facade.context=replace(facade.context,content_revision=2,fence=9,snapshot_digest=digest_bytes(b'new snapshot'))
    facade.current_state=lambda:(2,9,facade.context.snapshot_digest)
    assert ingest(facade,contract,output,idempotency_key=key)==receipt


@pytest.mark.parametrize('field,value,code',[
    ('scope_id','other','contract_page_scope_or_cap_mismatch'),
    ('post_clamp_max_output_tokens',2048,'contract_page_scope_or_cap_mismatch'),
    ('author_surface_digest',digest_bytes(b'wrong surface'),'contract_material_digest_mismatch'),
    ('model','other','contract_configuration_mismatch'),
    ('read_set',(),'contract_read_set_mismatch'),
])
def test_new_effect_cannot_relabel_scope_cap_material_model_or_read_set(domain,field,value,code):
    facade,contract,material,_=domain
    from code2paper.integrations.dsh.writer_contract import seal_contract
    values=contract.model_dump(mode='json');values[field]=value;contract=seal_contract(values)
    output=record_output(facade,contract,observed_output(facade,terminal_raw(material)))
    with pytest.raises(ProtocolError,match=code):
        ingest(facade,contract,output,idempotency_key=ingest_key(contract,output))

# GC-3: full closure must precede every NEW outcome; committed recovery stays first.
REQUIRED_WIRE_REFS=('projection','measurement','wire_equivalence','comparison','loop_request','provider_wire')


def closure_refs(facade,contract):
    from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
    projection=facade.store.read_json(contract.dsh_wire_contract_ref)
    equivalence=facade.store.read_json(ArtifactRefV1.model_validate(projection['wire_equivalence_ref']))
    return {'projection':contract.dsh_wire_contract_ref,
        **{name:ArtifactRefV1.model_validate(projection[name+'_ref']) for name in ('measurement','wire_equivalence')},
        **{name:ArtifactRefV1.model_validate(equivalence[name+'_ref']) for name in ('comparison','loop_request','provider_wire')}}


def raw_outcome(material,outcome):
    if outcome=='draft':return terminal_raw(material)
    if outcome=='blocked':return canonical_json_bytes({'schema_version':'WriterTaskResultV1','result':{
        'outcome':'blocked','reason':'missing material','recovery_action':'new task'}})
    return canonical_json_bytes({'schema_version':'WriterTaskResultV1','result':{'outcome':'research_required','requests':[{
        'request_id':'rq:1','section_id':material['section'].section_id,'argument_unit_id':'unit:1',
        'missing_rhetorical_move':'implementation_realization','exact_question':'Which branch applies?',
        'required_authority_lane':'executable_hard'}]}})


@pytest.mark.parametrize('outcome',['draft','research_required','blocked'])
@pytest.mark.parametrize('role',REQUIRED_WIRE_REFS)
@pytest.mark.parametrize('damage',['missing','corrupt'])
def test_new_outcome_rejects_any_missing_or_corrupt_wire_dependency(domain,outcome,role,damage):
    facade,contract,material,_=domain
    refs=closure_refs(facade,contract)
    output=record_output(facade,contract,observed_output(facade,raw_outcome(material,outcome)))
    path=facade.store.directory/refs[role].artifact_id.split(':')[1]
    if damage=='missing':path.unlink()
    else:path.write_bytes(b'damaged evidence')
    with pytest.raises(ProtocolError,match='artifact_unavailable' if damage=='missing' else 'artifact_bytes_mismatch'):
        ingest(facade,contract,output,idempotency_key=ingest_key(contract,output))
    root=facade.store.root/'dsh-local-outcomes'
    assert all(path.name=='.stage03-local-outcome.lock' for path in root.rglob('*') if path.is_file())


def mutate_wire_ref(facade,contract,role,mutate):
    """Reissue parent content-addresses, retaining the damaged leaf ref binding."""
    from code2paper.integrations.dsh.writer_contract import seal_projection,seal_contract
    projection=facade.store.read_json(contract.dsh_wire_contract_ref)
    if role=='projection':
        values=contract.model_dump(mode='json');values['dsh_wire_contract_ref']=mutate(values['dsh_wire_contract_ref'])
        return seal_contract(values)
    if role in ('measurement','wire_equivalence'):
        projection[role+'_ref']=mutate(projection[role+'_ref'])
    else:
        from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
        evidence=facade.store.read_json(ArtifactRefV1.model_validate(projection['wire_equivalence_ref']))
        evidence[role+'_ref']=mutate(evidence[role+'_ref'])
        projection['wire_equivalence_ref']=facade.store.put_json(evidence)
    values=contract.model_dump(mode='json');values['dsh_wire_contract_ref']=facade.store.put_json(seal_projection(projection))
    return seal_contract(values)


@pytest.mark.parametrize('role',REQUIRED_WIRE_REFS)
@pytest.mark.parametrize('damage,code',[
    ('length','artifact_bytes_mismatch'),('digest','artifact_unavailable'),('scope','artifact_scope_mismatch'),
    ('semantic','artifact_semantic_mismatch'),('version','schema_invalid')])
def test_new_outcome_rejects_dependency_metadata_and_versions(domain,role,damage,code):
    facade,contract,material,_=domain
    def mutate(ref):
        ref=dict(ref)
        if damage=='length':ref['byte_length']+=1
        elif damage=='digest':ref['bytes_digest']=ref['artifact_id']=digest_bytes(b'other')
        elif damage=='scope':ref['task_id']='other-task'
        elif damage=='semantic':ref['semantic_digest']=digest_bytes(b'wrong semantic')
        else:
            from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
            value=facade.store.read_json(ArtifactRefV1.model_validate(ref));value['schema_version']='unsupported/99'
            return facade.store.put_json(value).model_dump(mode='json')
        return ref
    # Captured raw wire/comparison have no version field: unsupported additions
    # fail their actual wire shape/binding, rather than inventing a provider schema.
    if damage=='version' and role in ('comparison','loop_request','provider_wire'):
        code='wire_comparison_mismatch'
    if role=='projection' and damage=='scope':
        with pytest.raises(ProtocolError,match='schema_invalid'):mutate_wire_ref(facade,contract,role,mutate)
        return
    changed=mutate_wire_ref(facade,contract,role,mutate)
    output=record_output(facade,changed,observed_output(facade,terminal_raw(material)))
    with pytest.raises(ProtocolError,match=code):
        ingest(facade,changed,output,idempotency_key=ingest_key(changed,output))


@pytest.mark.parametrize('role',REQUIRED_WIRE_REFS)
def test_cached_committed_retry_does_not_require_prepare_dependencies(domain,role):
    facade,contract,material,_=domain
    refs=closure_refs(facade,contract)
    output=record_output(facade,contract,observed_output(facade,terminal_raw(material)))
    key=ingest_key(contract,output);first=ingest(facade,contract,output,idempotency_key=key)
    (facade.store.directory/refs[role].artifact_id.split(':')[1]).unlink()
    facade.context=replace(facade.context,content_revision=2,fence=1)
    facade.current_state=lambda:(2,1,facade.context.snapshot_digest)
    assert ingest(facade,contract,output,idempotency_key=key)==first


def test_original_manifest_and_provenance_record_complete_dependency_closure(domain):
    facade,contract,material,_=domain
    output=record_output(facade,contract,observed_output(facade,terminal_raw(material)))
    ingest(facade,contract,output,idempotency_key=ingest_key(contract,output))
    root=facade.store.root/'dsh-local-outcomes'/digest_json(facade.context.scope.__dict__).split(':')[1]
    index,_=load_index_for_reading(root)
    read=read_artifact_validated(index,'section_draft','writer',out_root=root)
    closure=read.members['provenance']['dependency_closure']
    assert closure['schema_version']=='LocalWriterDependencyClosureV1'
    assert set(REQUIRED_WIRE_REFS).issubset(closure['dependencies'])
    assert len(closure['dependencies'])==14
    assert closure['task_digest']==contract.task_digest


@pytest.mark.parametrize('outcome',['draft','research_required','blocked'])
def test_other_valid_projection_cannot_supply_this_contract(domain,outcome):
    from .stage03_support import unit_projection
    from code2paper.integrations.dsh.writer_contract import WriterInputRefV1,seal_contract
    facade,contract,material,frozen=domain
    values=facade.render_input(frozen,cap=4096).model_dump(mode='json')
    values['post_clamp_max_output_tokens']=2048
    values['input_digest']=digest_json({key:value for key,value in values.items() if key!='input_digest'})
    other=unit_projection(facade,parse_model(canonical_json_bytes(values),WriterInputRefV1))
    values=contract.model_dump(mode='json');values['dsh_wire_contract_ref']=facade.store.put_json(other)
    changed=seal_contract(values)
    output=record_output(facade,changed,observed_output(facade,raw_outcome(material,outcome)))
    with pytest.raises(ProtocolError,match='projection_material_mismatch'):
        ingest(facade,changed,output,idempotency_key=ingest_key(changed,output))
