"""Test-only true stdio worker with deterministic Host/owner lifecycle faults.

The normal worker/bootstrap/serve path is retained. Hooks supply the otherwise
external current-state transition and owner recompiler; no production switches.
"""
import json
import os
from pathlib import Path

from code2paper.integrations.dsh.facade import WriterFacade
from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
from code2paper.integrations.dsh.worker import main

original=WriterFacade.prepare

def prepare(self,frozen_ref,*,cap,project,**kwargs):
    fault=json.loads(Path(os.environ['C2P_TEST_LIFECYCLE_FAULT']).read_text())
    if fault['mode']=='state_change':
        def projected(input):
            value=project(input)
            self.current_state=lambda:(self.context.content_revision+1,self.context.fence,self.context.snapshot_digest)
            return value
        return original(self,frozen_ref,cap=cap,project=projected,**kwargs)
    assert fault['mode']=='stale_recompile'
    return original(self,frozen_ref,cap=cap,project=project,
        recompile=lambda *_:ArtifactRefV1.model_validate(fault['frozen_ref']),**kwargs)

WriterFacade.prepare=prepare
if __name__=='__main__':main()
