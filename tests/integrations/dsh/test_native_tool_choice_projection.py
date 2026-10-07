"""Selection policy is bound material, never response or dispatch authority."""
import copy
import pytest

from code2paper.integrations.dsh.protocol import ProtocolError
from code2paper.integrations.dsh.writer_contract import seal_projection
from .stage03_support import local_test_facade, unit_projection
from .test_composition_identity import composition

NAMED = {"type":"function","function":{"name":"c2p_terminal"}}


def test_runtime_candidate_uses_original_backend_even_without_optional_field():
    from integrations.dsh.dev.l01_launch import canonical_backend_root
    profile = {'candidate': '0.2.0-rc.1+loop-origin.1+tool-choice.2'}
    assert canonical_backend_root(profile).parent.name == '0.2.0-rc.1+loop-origin.1'
    profile['backend_admission_candidate'] = '0.2.0-rc.1+loop-origin.1'
    assert canonical_backend_root(profile).parent.name == '0.2.0-rc.1+loop-origin.1'


@pytest.mark.parametrize('alias', ['0.2.0-rc.1+loop-origin.1+tool-choice.2', '../other', None])
def test_backend_alias_refused(alias):
    from integrations.dsh.dev.l01_launch import canonical_backend_root
    with pytest.raises(RuntimeError, match='l01_backend_alias_forbidden'):
        canonical_backend_root({'backend_admission_candidate': alias})


@pytest.mark.parametrize('choice', [None, 'required', NAMED])
def test_original_owner_checks_selected_provider_wire(tmp_path, composition, choice):
    facade, _, _, frozen = local_test_facade(tmp_path, composition, native_tool_choice=choice)
    input = facade.render_input(frozen, cap=4096)
    facade._verify_projection(input, unit_projection(facade, input))


@pytest.mark.parametrize('choice,wire_choice', [
    (None, NAMED), (NAMED, None), (NAMED, 'required'),
    (NAMED, {"type":"function","function":{"name":"foreign_tool"}}),
    (NAMED, {"type":"function","function":{"name":"c2p_terminal","extra":True}}),
    ('required', NAMED),
])
def test_resealed_changed_selection_refused_before_dispatch(tmp_path, composition, choice, wire_choice):
    facade, _, _, frozen = local_test_facade(tmp_path, composition, native_tool_choice=choice)
    input = facade.render_input(frozen, cap=4096)
    projection = unit_projection(facade, input)
    from code2paper.integrations.dsh.artifacts import ArtifactRefV1
    equivalence = facade.store.read_json(projection.wire_equivalence_ref)
    wire_ref = ArtifactRefV1.model_validate(equivalence['provider_wire_ref'])
    wire = copy.deepcopy(facade.store.read_json(wire_ref))
    if wire_choice is None:
        wire.pop('tool_choice', None)
    else:
        wire['tool_choice'] = wire_choice
    new_wire = facade.store.put_json(wire)
    comparison = facade.store.read_json(ArtifactRefV1.model_validate(equivalence['comparison_ref']))
    comparison['provider_digest'] = new_wire.bytes_digest
    equivalence['provider_wire_ref'] = new_wire.model_dump(mode='json')
    equivalence['comparison_ref'] = facade.store.put_json(comparison).model_dump(mode='json')
    measurement = facade.store.read_json(projection.measurement_ref)
    measurement['measured_wire_digest'] = new_wire.bytes_digest
    measurement['measured_input_tokens'] = facade.request_meter(facade.store.read(new_wire))
    values = projection.model_dump(mode='json')
    values['wire_equivalence_ref'] = facade.store.put_json(equivalence).model_dump(mode='json')
    values['measurement_ref'] = facade.store.put_json(measurement).model_dump(mode='json')
    changed = seal_projection(values)
    with pytest.raises(ProtocolError, match='provider_options_mismatch'):
        facade._verify_projection(input, changed)


@pytest.mark.parametrize('damage',[None,'missing','enabled','numeric-false','effort','budget','reserve'])
def test_explicit_nonthinking_wire_is_bound_before_dispatch(tmp_path,composition,damage):
    from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
    composition.effective_config.update(writer_chat_template_kwargs={'enable_thinking':False},writer_thinking_tokens=0)
    facade,_,_,frozen=local_test_facade(tmp_path,composition,native_tool_choice=NAMED,
        provider_options={'provider':'openai','reasoningEffort':'off'})
    inp=facade.render_input(frozen,cap=4096);projection=unit_projection(facade,inp)
    if damage is None:
        facade._verify_projection(inp,projection)
        return
    eq=facade.store.read_json(projection.wire_equivalence_ref)
    wire=copy.deepcopy(facade.store.read_json(ArtifactRefV1.model_validate(eq['provider_wire_ref'])))
    if damage=='missing':wire.pop('chat_template_kwargs')
    elif damage=='enabled':wire['chat_template_kwargs']={'enable_thinking':True}
    elif damage=='numeric-false':wire['chat_template_kwargs']={'enable_thinking':0}
    elif damage=='effort':wire['reasoning_effort']='off'
    elif damage=='budget':wire['thinking_token_budget']=1024
    ref=facade.store.put_json(wire)
    comparison=facade.store.read_json(ArtifactRefV1.model_validate(eq['comparison_ref']))
    comparison['provider_digest']=ref.bytes_digest
    eq['provider_wire_ref']=ref.model_dump(mode='json');eq['comparison_ref']=facade.store.put_json(comparison).model_dump(mode='json')
    measurement=facade.store.read_json(projection.measurement_ref)
    measurement.update(measured_wire_digest=ref.bytes_digest,measured_input_tokens=facade.request_meter(facade.store.read(ref)))
    if damage=='reserve':measurement['thinking_tokens']=1024
    values=projection.model_dump(mode='json');values['wire_equivalence_ref']=facade.store.put_json(eq).model_dump(mode='json')
    values['measurement_ref']=facade.store.put_json(measurement).model_dump(mode='json')
    with pytest.raises(ProtocolError,match='measurement_binding_mismatch' if damage=='reserve' else 'provider_options_mismatch'):
        facade._verify_projection(inp,seal_projection(values))
