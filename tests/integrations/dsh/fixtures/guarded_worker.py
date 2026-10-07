"""Test-only refusal sentinel around the unchanged production worker entry."""
import json
import os
from pathlib import Path
import socket
import sys

from code2paper.llm.client import LLMClient
from code2paper.integrations.dsh.worker import main as worker_main
from code2paper.integrations.dsh.host_admission import main as admission_main


def run():
    record=Path(sys.argv[1])
    args=sys.argv[2:]
    entries={"code2paper.integrations.dsh.worker":worker_main,
        "code2paper.integrations.dsh.host_admission":admission_main}
    if len(args)<2 or args[0] != '-m' or args[1] not in entries:
        raise RuntimeError("sentinel_expected_original_owner_entry")
    facts={"schema_version":"PythonLlmRefusalSentinelV1","state":"installed",
        "probe_refused":False,"model_calls":0,"network_calls":0}

    def flush():
        with record.open("w") as stream:
            json.dump(facts,stream);stream.flush();os.fsync(stream.fileno())

    def model_blocked(*args,**kwargs):
        facts["model_calls"]+=1;flush()
        raise AssertionError("hidden_python_llm_refused")

    def network_blocked(*args,**kwargs):
        facts["network_calls"]+=1;flush()
        raise AssertionError("hidden_python_network_refused")

    LLMClient.complete=model_blocked
    socket.socket.connect=network_blocked
    socket.socket.connect_ex=network_blocked
    # Prove refusal is installed, independently of the measured worker run.
    try:
        LLMClient.complete(None,None)
    except AssertionError as error:
        if str(error) != "hidden_python_llm_refused": raise
        facts["probe_refused"]=True
    else:
        raise AssertionError("sentinel_probe_did_not_refuse")
    facts["model_calls"]=0;flush()
    sys.argv=[sys.argv[0],*args[2:]]
    try:
        sys.exit(entries[args[1]]())
    finally:
        facts["state"]="closed";flush()


if __name__ == "__main__":
    run()
