"""Provider schema policy is frozen material, never a response repair."""
import copy

import pytest

from code2paper.integrations.dsh.protocol import ProtocolError
from code2paper.integrations.dsh.writer_contract import ArtifactRefV1, seal_projection
from .stage03_support import local_test_facade, unit_projection
from .test_composition_identity import composition


@pytest.mark.parametrize('mode,strict,accepted', [
    (None, False, True),
    (None, None, False),
    ('server-default', None, True),
    ('server-default', False, False),
    ('server-default', True, False),
    ('server-default', 'false', False),
    ('unknown', None, False),
])
def test_original_owner_binds_parameter_schema_policy(tmp_path, composition, mode, strict, accepted):
    options={'provider':'openai'}
    if mode is not None:options['nativeToolSchemaMode']=mode
    if mode == 'unknown':
        with pytest.raises(ProtocolError,match='provider_options_mismatch'):
            local_test_facade(tmp_path,composition,provider_options=options)
        return
    facade,_,_,frozen=local_test_facade(tmp_path,composition,provider_options=options)
    inp=facade.render_input(frozen,cap=4096);projection=unit_projection(facade,inp)
    eq=facade.store.read_json(projection.wire_equivalence_ref)
    wire=copy.deepcopy(facade.store.read_json(ArtifactRefV1.model_validate(eq['provider_wire_ref'])))
    function=wire['tools'][0]['function']
    if strict is None:function.pop('strict',None)
    else:function['strict']=strict
    ref=facade.store.put_json(wire)
    comparison=facade.store.read_json(ArtifactRefV1.model_validate(eq['comparison_ref']))
    comparison['provider_digest']=ref.bytes_digest
    eq['provider_wire_ref']=ref.model_dump(mode='json')
    eq['comparison_ref']=facade.store.put_json(comparison).model_dump(mode='json')
    measurement=facade.store.read_json(projection.measurement_ref)
    measurement.update(measured_wire_digest=ref.bytes_digest,
        measured_input_tokens=facade.request_meter(facade.store.read(ref)))
    values=projection.model_dump(mode='json')
    values['wire_equivalence_ref']=facade.store.put_json(eq).model_dump(mode='json')
    values['measurement_ref']=facade.store.put_json(measurement).model_dump(mode='json')
    if accepted:facade._verify_projection(inp,seal_projection(values))
    else:
        with pytest.raises(ProtocolError,match='provider_(wire|options)_mismatch'):
            facade._verify_projection(inp,seal_projection(values))


@pytest.mark.parametrize('value',[None,True,0,'false'])
def test_l01_refuses_parameter_schema_opt_out_profile(value):
    import importlib.util
    import json
    from pathlib import Path
    root=Path(__file__).resolve().parents[3]
    spec=importlib.util.spec_from_file_location('l01_schema_test',root/'integrations/dsh/dev/l01_worker.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    profile=json.loads((root/'tests/live/profiles/qwen38_dsh_l01.json').read_bytes())
    compat=profile['provider_config']['providers']['openai']['compat']
    if value is None:compat.pop('supportsStrictMode')
    else:compat['supportsStrictMode']=value
    with pytest.raises(ProtocolError,match='l01_parameter_schema_opt_out_forbidden'):
        module.reasoning_mode(profile)
