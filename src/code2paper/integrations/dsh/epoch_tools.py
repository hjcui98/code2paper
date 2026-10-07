"""Durable V2 tool/candidate admission, before any content/schema guard.

Only the trusted gated-stream observer supplies these raw-source facts. This
stores lifecycle metadata on the original TaskStore, not a fee balance.
"""
from __future__ import annotations

import time
from typing import Literal

from code2paper.agentic.digest import canonical_json_bytes, digest_json
from code2paper.agentic.unified_invocation_ledger import read_dsh_invocation_events
from .protocol import ProtocolError, WireModel, parse_model
from .writer_contract import ArtifactRefV1, Identifier, Positive, Counter, WriterTaskContractV2


class ToolCandidateV2(WireModel):
    schema_version: Literal['DshToolCandidateV2']
    execution_id: Identifier
    task_id: Identifier
    task_epoch: Counter
    child_id: Identifier
    session_id: Identifier
    request_id: Identifier
    tool_call_id: Identifier
    stream_index: Positive
    name: Identifier
    arguments_ref: ArtifactRefV1
    source: Literal['gated-adapter-tool-arguments-delta/2']


class EpochTools:
    def __init__(self,tasks,artifacts,current_state):
        if tasks.scope != artifacts.scope or tasks.root != artifacts.root:
            raise ProtocolError('tool_owner_scope_mismatch')
        self.tasks,self.artifacts,self.current_state=tasks,artifacts,current_state

    @staticmethod
    def _key(source):
        return digest_json({key:getattr(source,key) for key in
            ('execution_id','task_id','task_epoch','request_id','tool_call_id')})

    def _owner(self,db,claim,contract,*,read_only=False):
        row=self.tasks._row(db)
        self.tasks._authorize(row,claim,allow_terminal=read_only)
        if not read_only and row['grant_mode'] != 'execute':raise ProtocolError('tool_execute_claim_required')
        if not isinstance(contract,WriterTaskContractV2):raise ProtocolError('multistep_contract_required')
        view=self.tasks._view(row);prepared=view['prepared']
        if not read_only:
            now=time.time_ns()//1_000_000
            if now < view['epoch_started_ms'] or now-view['epoch_started_ms'] >= contract.epoch_limits.max_wall_seconds*1000:
                raise ProtocolError('dsh_epoch_deadline_exceeded')
        if (self.current_state() != (prepared['content_revision'],prepared['content_fence'],prepared['snapshot_digest'])
                or (contract.execution_id,contract.task_id,contract.task_epoch) !=
                   (self.tasks.scope.execution_id,self.tasks.scope.task_id,self.tasks.scope.task_epoch)):
            raise ProtocolError('task_revision_or_fence_stale')
        ref=parse_model(canonical_json_bytes(prepared['contract_ref']),ArtifactRefV1)
        if self.artifacts.read_json(ref) != contract.model_dump(mode='json'):
            raise ProtocolError('tool_contract_binding_invalid')
        return view

    def _rows(self,db,contract):
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='epoch_tool_candidates'").fetchone() is None:
            return []
        result=[]
        for row in db.execute('SELECT candidate_key,payload FROM epoch_tool_candidates WHERE task_key=?',(self.tasks.key,)):
            record_ref=parse_model(row['payload'],ArtifactRefV1)
            value=self.artifacts.read_json(record_ref)
            if (not isinstance(value,dict) or set(value) != {'source','contract_digest','admitted','rejection'}
                    or value['contract_digest'] != contract.task_digest or type(value['admitted']) is not bool
                    or value['rejection'] not in {'','dsh_epoch_tool_budget_exceeded','dsh_epoch_terminal_already_consumed'}
                    or value['admitted'] != (value['rejection']=='')):
                raise ProtocolError('tool_candidate_record_invalid')
            source=parse_model(canonical_json_bytes(value['source']),ToolCandidateV2)
            if (row['candidate_key'] != self._key(source)
                    or (source.execution_id,source.task_id,source.task_epoch) !=
                       (contract.execution_id,contract.task_id,contract.task_epoch)):
                raise ProtocolError('tool_candidate_record_invalid')
            if source.arguments_ref.media_type != 'application/octet-stream':
                raise ProtocolError('tool_candidate_record_invalid')
            self.artifacts.read(source.arguments_ref)
            result.append(value)
        return result

    def record(self,claim,contract:WriterTaskContractV2,source:ToolCandidateV2):
        rejection=''
        with self.tasks._transaction() as db:
            view=self._owner(db,claim,contract)
            if view['binding'] != {'child_id':source.child_id,'session_id':source.session_id}:
                raise ProtocolError('tool_session_binding_invalid')
            if (source.execution_id,source.task_id,source.task_epoch) != (
                    contract.execution_id,contract.task_id,contract.task_epoch):
                raise ProtocolError('tool_candidate_scope_invalid')
            if source.arguments_ref.media_type != 'application/octet-stream':
                raise ProtocolError('tool_candidate_raw_media_invalid')
            self.artifacts.read(source.arguments_ref)
            root=self.tasks.root/'artifacts/06_authoring/invocations'
            facts=read_dsh_invocation_events(root,source.request_id)
            if (not facts or facts[0].contract_digest != contract.task_digest
                    or facts[0].claim_digest != digest_json(claim)
                    or (facts[0].execution_id,facts[0].task_id,facts[0].task_epoch) !=
                       (contract.execution_id,contract.task_id,contract.task_epoch)
                    or 'adapter-attempt' not in {fact.kind for fact in facts}
                    or any(fact.kind in {'settlement','proven-not-sent'} for fact in facts)):
                raise ProtocolError('tool_candidate_request_binding_invalid')
            rows=self._rows(db,contract);key=self._key(source)
            existing=next((row for row in rows if self._key(parse_model(canonical_json_bytes(row['source']),ToolCandidateV2))==key),None)
            if existing is not None:
                if existing['source'] != source.model_dump(mode='json'):
                    raise ProtocolError('tool_candidate_source_conflict')
                rejection=existing['rejection']
            else:
                if any(not row['admitted'] for row in rows) or sum(row['admitted'] for row in rows) >= contract.epoch_limits.max_tool_calls:
                    rejection='dsh_epoch_tool_budget_exceeded'
                if source.name=='c2p_terminal' and any(row['admitted'] and row['source']['name']=='c2p_terminal' for row in rows):
                    rejection='dsh_epoch_terminal_already_consumed'
                db.execute('''CREATE TABLE IF NOT EXISTS epoch_tool_candidates (
                    task_key TEXT NOT NULL,candidate_key TEXT NOT NULL,payload BLOB NOT NULL,
                    PRIMARY KEY(task_key,candidate_key))''')
                value={'source':source.model_dump(mode='json'),'contract_digest':contract.task_digest,
                       'admitted':not rejection,'rejection':rejection}
                db.execute('INSERT INTO epoch_tool_candidates VALUES (?,?,?)',
                           (self.tasks.key,key,canonical_json_bytes(self.artifacts.put_json(value))))
        # Persist the rejected source and closed epoch before returning denial.
        if rejection:raise ProtocolError(rejection)
        return {'candidate_key':key,'admitted':True}

    def status(self,claim,contract):
        with self.tasks._transaction() as db:
            view=self._owner(db,claim,contract,read_only=True);rows=self._rows(db,contract)
            return {'observed':len(rows),'admitted':sum(row['admitted'] for row in rows),
                    'terminal_consumed':any(row['admitted'] and row['source']['name']=='c2p_terminal' for row in rows),
                    'closed':view['state'] in {'cancelled','terminal'} or any(not row['admitted'] for row in rows)}
