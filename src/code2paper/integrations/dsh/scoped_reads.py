"""Explicit Kernel-issued read grants over immutable artifacts.

This table contains capabilities and delivered-byte counters, never money or
model usage. Issuance is a private owner operation; no model RPC can issue or
promote a grant. Navigation remains navigation even when its text quotes code.
"""
from __future__ import annotations

from typing import Callable

from code2paper.agentic.digest import canonical_json_bytes, digest_json
from .artifacts import ArtifactStore
from .protocol import MAX_READ_CHUNK, ProtocolError, strict_json_loads
from .task_store import TaskStore
from .writer_contract import ArtifactRefV1


class ScopedReads:
    def __init__(self, tasks: TaskStore, artifacts: ArtifactStore,
                 current_state: Callable[[], tuple[int, int, str]]):
        if tasks.scope != artifacts.scope or tasks.root != artifacts.root:
            raise ProtocolError('read_owner_scope_mismatch')
        self.tasks, self.artifacts, self.current_state = tasks, artifacts, current_state
        with tasks._transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS scoped_read_epochs (
                task_key TEXT PRIMARY KEY, limits BLOB NOT NULL,
                calls INTEGER NOT NULL DEFAULT 0, delivered_bytes INTEGER NOT NULL DEFAULT 0,
                closed INTEGER NOT NULL DEFAULT 0)''')
            db.execute('''CREATE TABLE IF NOT EXISTS scoped_read_grants (
                task_key TEXT NOT NULL, grant_id TEXT NOT NULL, payload BLOB NOT NULL,
                PRIMARY KEY (task_key, grant_id))''')

    def _owner(self, db, claim, session_id):
        row = self.tasks._row(db)
        self.tasks._authorize(row, claim)
        view = self.tasks._view(row)
        prepared = view['prepared']
        if view['grant_mode'] != 'execute':
            raise ProtocolError('read_execute_claim_required')
        if self.current_state() != (prepared['content_revision'], prepared['content_fence'], prepared['snapshot_digest']):
            raise ProtocolError('task_revision_or_fence_stale')
        if not view['binding'] or view['binding']['session_id'] != session_id:
            raise ProtocolError('read_session_binding_invalid')
        return prepared

    def configure(self, claim, *, session_id: str, max_calls: int, max_bytes: int, read_set: list[dict]):
        """Private Kernel operation, immutable for the entire task epoch."""
        if (type(max_calls) is not int or not 1 <= max_calls <= 10000
                or type(max_bytes) is not int or not 64 <= max_bytes <= (16 << 20)):
            raise ProtocolError('read_limits_invalid')
        if not isinstance(read_set,list) or not read_set or len(read_set) > 256:
            raise ProtocolError('read_set_invalid')
        for member in read_set:
            if (not isinstance(member,dict) or set(member) != {'ref','kind','start','end'}
                    or member['kind'] not in {'navigation','exact_excerpt'}):
                raise ProtocolError('read_set_invalid')
            ref = ArtifactRefV1.model_validate(member['ref'])
            raw = self.artifacts.read(ref)
            if (type(member['start']) is not int or type(member['end']) is not int
                    or not 0 <= member['start'] < member['end'] <= len(raw)):
                raise ProtocolError('read_span_invalid')
            try:
                raw[member['start']:member['end']].decode('utf-8',errors='strict')
            except UnicodeError as error:
                raise ProtocolError('read_span_not_utf8') from error
        limits = canonical_json_bytes({'max_calls': max_calls, 'max_bytes': max_bytes, 'read_set': read_set})
        with self.tasks._transaction() as db:
            self._owner(db, claim, session_id)
            db.execute('INSERT OR IGNORE INTO scoped_read_epochs(task_key,limits) VALUES (?,?)', (self.tasks.key, limits))
            if db.execute('SELECT limits FROM scoped_read_epochs WHERE task_key=?', (self.tasks.key,)).fetchone()[0] != limits:
                raise ProtocolError('read_limits_conflict')

    def issue(self, claim, *, session_id: str, ref: ArtifactRefV1,
              kind: str, start: int, end: int) -> str:
        """Original owner explicitly selects one read-set member and exact span.

        `exact_excerpt` denotes the issued immutable bytes only. It is not a
        claim license, evidence promotion or permission to read sibling refs.
        Summary artifacts must be issued as navigation by their original owner.
        """
        if kind not in {'navigation', 'exact_excerpt'}:
            raise ProtocolError('read_kind_invalid')
        raw = self.artifacts.read(ref)
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(raw):
            raise ProtocolError('read_span_invalid')
        try:
            raw[start:end].decode('utf-8', errors='strict')
        except UnicodeError as error:
            raise ProtocolError('read_span_not_utf8') from error
        with self.tasks._transaction() as db:
            prepared = self._owner(db, claim, session_id)
            epoch = db.execute('SELECT limits FROM scoped_read_epochs WHERE task_key=?', (self.tasks.key,)).fetchone()
            if epoch is None:
                raise ProtocolError('read_limits_unavailable')
            member = {'ref':ref.model_dump(mode='json'),'kind':kind,'start':start,'end':end}
            if member not in strict_json_loads(epoch['limits'])['read_set']:
                raise ProtocolError('read_outside_issued_set')
            payload = {'schema_version': 'DshScopedReadGrantV1', 'scope': self.tasks.scope.__dict__,
                       'snapshot_digest': prepared['snapshot_digest'], 'content_revision': prepared['content_revision'],
                       'content_fence': prepared['content_fence'], 'ref': ref.model_dump(mode='json'),
                       'kind': kind, 'start': start, 'end': end}
            grant_id = digest_json(payload)
            db.execute('INSERT OR IGNORE INTO scoped_read_grants VALUES (?,?,?)',
                       (self.tasks.key, grant_id, canonical_json_bytes(payload)))
            return grant_id

    def read(self, claim, *, session_id: str, grant_id: str, offset: int, length: int) -> dict:
        """Return exactly the text charged to the epoch, including its labels.

        Denied model reads also consume a call and their rendered error bytes.
        Exhaustion closes further delivery and must stop the calling loop; no
        uncharged tool result is supplied by this operation on exhaustion.
        """
        exhausted = False
        with self.tasks._transaction() as db:
            self._owner(db, claim, session_id)
            epoch = db.execute('SELECT * FROM scoped_read_epochs WHERE task_key=?', (self.tasks.key,)).fetchone()
            if epoch is None:
                raise ProtocolError('read_limits_unavailable')
            limits = strict_json_loads(epoch['limits'])
            if epoch['closed'] or epoch['calls'] >= limits['max_calls']:
                raise ProtocolError('read_epoch_exhausted')
            row = db.execute('SELECT payload FROM scoped_read_grants WHERE task_key=? AND grant_id=?',
                             (self.tasks.key, grant_id)).fetchone()
            code = None
            if row is None:
                code = 'read_grant_unavailable'
            elif (type(offset) is not int or type(length) is not int or offset < 0
                  or not 1 <= length <= MAX_READ_CHUNK):
                code = 'read_range_invalid'
            else:
                grant = strict_json_loads(row['payload'])
                if digest_json(grant) != grant_id:
                    raise ProtocolError('read_grant_integrity_invalid')
                if offset + length > grant['end'] - grant['start']:
                    code = 'read_range_outside_grant'
                else:
                    ref = ArtifactRefV1.model_validate(grant['ref'])
                    try:
                        content = self.artifacts.read(ref)[grant['start'] + offset:grant['start'] + offset + length].decode('utf-8', errors='strict')
                    except UnicodeError:
                        code = 'read_range_not_utf8'
            if code:
                result = {'error': code}
            else:
                result = {'schema_version': 'DshScopedReadResultV1', 'grant_id': grant_id,
                          'kind': grant['kind'], 'snapshot_digest': grant['snapshot_digest'],
                          'content_revision': grant['content_revision'], 'source_digest': ref.bytes_digest,
                          'start': grant['start'] + offset, 'end': grant['start'] + offset + length,
                          'text': content}
            # This exact canonical string, not a private artifact envelope, is
            # the sole public tool-result text. UTF-8 and JSON escaping count.
            model_text = canonical_json_bytes(result).decode('utf-8')
            count = len(model_text.encode('utf-8'))
            exhausted = epoch['delivered_bytes'] + count > limits['max_bytes']
            db.execute('UPDATE scoped_read_epochs SET calls=calls+1, delivered_bytes=delivered_bytes+?,closed=? WHERE task_key=?',
                       (0 if exhausted else count, int(exhausted), self.tasks.key))
        if exhausted:
            raise ProtocolError('read_epoch_exhausted')
        return {'model_text': model_text, 'delivered_bytes': count}

    def status(self, claim, *, session_id: str):
        with self.tasks._transaction() as db:
            self._owner(db, claim, session_id)
            row = db.execute('SELECT * FROM scoped_read_epochs WHERE task_key=?', (self.tasks.key,)).fetchone()
            if row is None:
                raise ProtocolError('read_limits_unavailable')
            limits = strict_json_loads(row['limits'])
            return {'max_calls':limits['max_calls'],'max_bytes':limits['max_bytes'], 'calls': row['calls'],
                    'delivered_bytes': row['delivered_bytes'], 'closed': bool(row['closed'])}
