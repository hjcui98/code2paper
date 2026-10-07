"""Exact empty nonthinking placeholder; never ignore generated reasoning."""
from copy import deepcopy
import pytest
from code2paper.integrations.dsh.protocol import ProtocolError
from code2paper.integrations.dsh.step_admission import verify_message_wire


def test_bound_empty_sdk_placeholder_retains_exact_message_bytes():
    messages=[{'role':'assistant','content':[{'type':'text','text':'Unchanged 原文.'}]}]
    wire=[{'role':'assistant','content':'Unchanged 原文.','reasoning_content':''}]
    with pytest.raises(ProtocolError):verify_message_wire(messages,wire)
    verify_message_wire(messages,wire,allow_empty_reasoning=True)
    for changed in ('hidden generated text',None,False,[]):
        damaged=deepcopy(wire);damaged[0]['reasoning_content']=changed
        with pytest.raises(ProtocolError):verify_message_wire(messages,damaged,allow_empty_reasoning=True)


def test_placeholder_cannot_change_role_or_text_or_hide_reasoning_blocks():
    user=[{'role':'user','content':[{'type':'text','text':'Exact.'}]}]
    with pytest.raises(ProtocolError):
        verify_message_wire(user,[{'role':'user','content':'Exact.','reasoning_content':''}],allow_empty_reasoning=True)
    assistant=[{'role':'assistant','content':[{'type':'text','text':'Exact.'}]}]
    with pytest.raises(ProtocolError):
        verify_message_wire(assistant,[{'role':'assistant','content':'Changed.','reasoning_content':''}],allow_empty_reasoning=True)
    assistant[0]['content'].append({'type':'reasoning','text':'Unmeasured.'})
    with pytest.raises(ProtocolError):
        verify_message_wire(assistant,[{'role':'assistant','content':'Exact.','reasoning_content':''}],allow_empty_reasoning=True)
