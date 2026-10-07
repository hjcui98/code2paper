/**
 * H03 — provenance: the three argument sources stay separate, and the rebuild
 * never invents what the log does not hold.
 *
 * These are the module's own functions over real inputs: the capture is the
 * module's real {@link TerminalArgumentCapture}, the events are shaped like the
 * persisted session log, and the rebuild is the same function the restarted
 * consumer calls. The real-loop path (scripted adapter → real tool → real
 * session → flush → restart) lives in `terminal.test.ts`; this file pins the
 * source-level invariants that path depends on.
 */

import assert from 'node:assert/strict';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';

import type * as TerminalApi from '../src/terminal-result.js';

const packageDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
// The launcher decides which development root is active (default or an isolated
// candidate) and exports it, so the guard compares against that same root.
const devRoot = process.env.C2P_DSH_DEV_ROOT
  ? path.resolve(process.env.C2P_DSH_DEV_ROOT)
  : path.resolve(packageDir, '../../.dsh-dev');
const stagedBundle = path.join(devRoot, 'home/profiles/node_modules/@code2paper/dsh-bundle');

type TerminalModule = {
  readonly TerminalArgumentCapture: typeof TerminalApi.TerminalArgumentCapture;
  readonly rebuildTerminal: typeof TerminalApi.rebuildTerminal;
  readonly digestText: typeof TerminalApi.digestText;
  readonly digestJson: typeof TerminalApi.digestJson;
  readonly canonicalJson: typeof TerminalApi.canonicalJson;
  readonly TERMINAL_SCHEMA_VERSION: typeof TerminalApi.TERMINAL_SCHEMA_VERSION;
  readonly TERMINAL_PARAMETERS: typeof TerminalApi.TERMINAL_PARAMETERS;
};

const module = await import(pathToFileURL(path.join(stagedBundle, 'lib/terminal-result.js')).href) as TerminalModule;

/** One raw text with whitespace, an escape and non-canonical key order. */
const RAW_A = '{ "result" :\n  { "kind":"draft", "draft": { "body":"line\\u0021", "title":"T" } } }';
/** The same value, written with different whitespace, escape spelling and key order. */
const RAW_B = '{"result":{"draft":{"title":"T","body":"line!"},"kind":"draft"}}';

/** Build one tool-call delta chunk. */
function delta(id: string, argumentsDelta: string): { type: 'tool-call-delta'; index: number; id: never; name: string; argumentsDelta: string } {
  return { type: 'tool-call-delta', index: 0, id: id as never, name: 'c2p_terminal', argumentsDelta };
}

/** The per-call completion fact: the block-end closing this call. */
function blockEnd(id: string, index = 0): unknown {
  return { type: 'block-end', index, block: { type: 'tool-call', id, name: 'c2p_terminal', arguments: '{}' } };
}

/** A normal stream finish. */
function finish(kind: 'stop' | 'tool-calls' | 'error' | 'aborted' = 'tool-calls'): unknown {
  return { type: 'finish', reason: { kind } };
}

/** Stream a fixed list of chunks, as the llm/stream waterfall would. */
async function* chunksOf(items: readonly unknown[]): AsyncIterable<never> {
  for (const item of items) yield item as never;
}

test('the capture keeps the raw text verbatim, per call and in arrival order', async () => {
  const capture = new module.TerminalArgumentCapture();
  const observed: string[] = [];
  const stream = capture.observe(chunksOf([
    { type: 'block-start', index: 0, blockType: 'tool-call' },
    delta('call-a', RAW_A.slice(0, 10)),
    delta('call-a', RAW_A.slice(10)),
    blockEnd('call-a'),
    finish(),
  ]) as AsyncIterable<never>);
  for await (const chunk of stream) observed.push((chunk as { type: string }).type);

  // The observer is passive: every chunk still reaches the loop.
  assert.deepEqual(observed, ['block-start', 'tool-call-delta', 'tool-call-delta', 'block-end', 'finish']);

  const raw = capture.raw('call-a');
  assert.equal(raw.state, 'captured');
  assert.ok(raw.state === 'captured');
  assert.equal(raw.text, RAW_A, 'the raw text must be the verbatim delta concatenation');
  assert.equal(raw.chunks, 2);
  assert.equal(raw.digest, module.digestText(RAW_A));
  assert.equal(raw.byteLength, Buffer.byteLength(RAW_A, 'utf8'));
  assert.equal(raw.source, 'llm-stream-tool-call-delta');
});

test('raw, normalized and parsed digests are distinct for the same value', async () => {
  const capture = new module.TerminalArgumentCapture();
  for await (const _chunk of capture.observe(chunksOf([delta('call-b', RAW_A), blockEnd('call-b'), finish()]) as AsyncIterable<never>)) { /* drain */ }
  const raw = capture.raw('call-b');
  assert.ok(raw.state === 'captured');

  const parsed = { kind: 'draft', draft: { title: 'T', body: 'line!' } } as const;
  const normalized = JSON.stringify(parsed);

  // The same value written three ways: three different byte strings, three digests.
  assert.notEqual(raw.text, normalized, 'a re-serialization is not the raw text');
  assert.notEqual(raw.digest, module.digestText(normalized), 'JSON.stringify must not reproduce the raw digest');
  assert.notEqual(raw.digest, module.digestJson(parsed), 'the parsed digest is a different source');
  // The tool receives `result`, so the parsed domain value is the inner object.
  assert.equal(module.digestJson((JSON.parse(RAW_A) as { result: unknown }).result), module.digestJson(parsed),
    'the parsed VALUE is identical');
});

test('whitespace, escape spelling and key order change the raw digest but not the parsed value', () => {
  assert.notEqual(RAW_A, RAW_B, 'the fixture must differ textually');
  assert.deepEqual((JSON.parse(RAW_A) as { result: unknown }).result, (JSON.parse(RAW_B) as { result: unknown }).result,
    'the fixture must be the same value');
  assert.notEqual(module.digestText(RAW_A), module.digestText(RAW_B), 'raw digests must differ');
  assert.equal(
    module.digestJson((JSON.parse(RAW_A) as { result: unknown }).result),
    module.digestJson((JSON.parse(RAW_B) as { result: unknown }).result),
    'canonical digests must agree',
  );
  // Canonical JSON sorts keys but preserves array order.
  assert.equal(module.canonicalJson({ b: 1, a: 2 }), module.canonicalJson({ a: 2, b: 1 }));
  assert.notEqual(module.canonicalJson([1, 2]), module.canonicalJson([2, 1]));
});

test('an unobserved raw source stays explicitly missing', () => {
  const capture = new module.TerminalArgumentCapture();
  const raw = capture.raw('call-never-seen', { sessionId: 'h03-none' as never });
  assert.equal(raw.state, 'not_observed');
  assert.match(raw.reason, /no llm\/stream tool-call-delta was observed/);
  assert.equal('digest' in raw, false, 'a missing source must not carry a digest');
  assert.equal('text' in raw, false, 'a missing source must not carry text');
});

test('the rebuild returns what the log holds and refuses to reconstruct the rest', () => {
  const record = {
    schema: module.TERMINAL_SCHEMA_VERSION,
    terminalId: 'terminal-call-c',
    callId: 'call-c',
    turn: 1,
    step: 1,
    parsed: { kind: 'blocked', reason: 'no evidence' },
    parsedDigest: module.digestJson({ kind: 'blocked', reason: 'no evidence' }),
    rawArguments: { state: 'not_observed', source: 'llm-stream-tool-call-delta', reason: 'not captured' },
    normalizedArguments: {
      source: 'session-tool-call',
      text: '{"result":{"kind":"blocked","reason":"no evidence"}}',
      digest: module.digestText('{"result":{"kind":"blocked","reason":"no evidence"}}'),
    },
    prose: { source: 'assistant-message', text: '', blocks: 0, digest: module.digestText('') },
    schemaDigest: module.digestJson(module.TERMINAL_PARAMETERS),
    recordedAt: 0,
  };

  // A committed record is returned exactly as stored, missing raw included.
  const committed = module.rebuildTerminal([
    { type: 'tool/call', seq: 1, data: { turn: 1, step: 1, callId: 'call-c', name: 'c2p_terminal', arguments: record.normalizedArguments.text } },
    { type: 'tool/result', seq: 2, data: { turn: 1, step: 1, message: { content: [{ type: 'tool-result', toolCallId: 'call-c', isError: false }] } } },
    { type: 'c2p/terminal', seq: 3, data: record },
  ] as never, 3);
  assert.equal(committed.state, 'committed');
  assert.ok(committed.state === 'committed');
  assert.equal(committed.record.parsed.kind, 'blocked');
  assert.equal(committed.record.rawArguments.state, 'not_observed', 'missing raw must stay missing after a rebuild');

  // A logged terminal call with no committed record is unresolved, not rebuilt.
  const unresolved = module.rebuildTerminal([
    { type: 'tool/call', seq: 1, data: { turn: 1, step: 1, callId: 'call-d', name: 'c2p_terminal', arguments: '{}' } },
    { type: 'assistant/message', seq: 2, data: { turn: 1, content: [{ type: 'text', text: 'I finished.' }] } },
  ] as never, 3);
  assert.equal(unresolved.state, 'unresolved');
  assert.ok(unresolved.state === 'unresolved');
  assert.equal(unresolved.callId, 'call-d');
  assert.match(unresolved.reason, /without a committed/);

  // No terminal activity at all is absent — closing text never becomes a result.
  const absent = module.rebuildTerminal([
    { type: 'assistant/message', seq: 1, data: { turn: 1, content: [{ type: 'text', text: 'I finished.' }] } },
  ] as never, 3);
  assert.equal(absent.state, 'absent');
  assert.match(absent.reason, /no c2p_terminal call/);
});

test('a reused call id in a later stream does not merge two sources', async () => {
  const capture = new module.TerminalArgumentCapture();
  const first = '{ "result": { "kind": "draft", "draft": { "title": "T", "body": "B" } } }';
  const second = '{ "result": { "kind": "blocked", "reason": "R" } }';
  for await (const _chunk of capture.observe(chunksOf([delta('reused', first), blockEnd('reused'), finish()]) as AsyncIterable<never>)) { /* drain */ }
  for await (const _chunk of capture.observe(chunksOf([delta('reused', second), blockEnd('reused'), finish()]) as AsyncIterable<never>)) { /* drain */ }

  // Two streams carry the same id: the capture refuses to guess and names both.
  const ambiguous = capture.raw('reused');
  assert.equal(ambiguous.state, 'ambiguous');
  assert.ok(ambiguous.state === 'ambiguous');
  assert.deepEqual(ambiguous.candidates.map((candidate) => candidate.streamIndex), [1, 2]);

  // Naming a stream attributes the source exactly; the second stream is separate.
  const raw = capture.raw('reused', { streamIndex: 2 });
  assert.equal(raw.state, 'captured');
  assert.ok(raw.state === 'captured');
  assert.equal(raw.text, second, 'a later stream must not be appended to the earlier one');
  assert.equal(raw.chunks, 1);
  assert.equal(raw.streamIndex, 2, 'the source names which stream it came from');
  assert.notEqual(raw.text.length, first.length + second.length, 'the two streams must not be concatenated');
  const earlier = capture.raw('reused', { streamIndex: 1 });
  assert.ok(earlier.state === 'captured');
  assert.equal(earlier.text, first, 'the earlier stream keeps its own source');
});

test('a stream that fails or is abandoned yields an explicitly incomplete source', async () => {
  const capture = new module.TerminalArgumentCapture();
  const partial = '{ "result": { "kind": "dra';
  const failing = (async function* broken(): AsyncIterable<never> {
    yield delta('failed', partial) as never;
    throw new Error('adapter stream failed midway');
  })();
  await assert.rejects(async () => {
    for await (const _chunk of capture.observe(failing)) { /* drain */ }
  }, /adapter stream failed midway/);

  const failed = capture.raw('failed');
  assert.equal(failed.state, 'incomplete', 'a failed stream is never a complete source');
  assert.ok(failed.state === 'incomplete');
  assert.equal(failed.text, partial, 'the partial text is kept, not discarded');
  assert.equal(failed.digest, module.digestText(partial));
  assert.match(failed.reason, /failed/);

  // A consumer that stops early (break) leaves the same explicit state.
  const abandoned = capture.observe(chunksOf([delta('abandoned', partial), delta('abandoned', 'ft" } } }')]) as AsyncIterable<never>);
  for await (const _chunk of abandoned) break;
  const stopped = capture.raw('abandoned');
  assert.equal(stopped.state, 'incomplete');
  assert.ok(stopped.state === 'incomplete');
  assert.match(stopped.reason, /abandoned/);

  // Only a normally completed stream is reported as captured.
  for await (const _chunk of capture.observe(chunksOf([delta('whole', partial + 'ft" } } }'), blockEnd('whole'), finish()]) as AsyncIterable<never>)) { /* drain */ }
  assert.equal(capture.raw('whole').state, 'captured');
});

test('the rebuild validates a stored record instead of trusting it', () => {
  const parsed = { kind: 'draft', draft: { title: 'T', body: 'B' } } as const;
  const normalizedText = '{"result":{"kind":"draft","draft":{"title":"T","body":"B"}}}';
  const good = {
    schema: module.TERMINAL_SCHEMA_VERSION,
    terminalId: 'terminal-call-ok',
    callId: 'call-ok',
    turn: 1,
    step: 1,
    parsed,
    parsedDigest: module.digestJson(parsed),
    rawArguments: { state: 'not_observed', source: 'llm-stream-tool-call-delta', reason: 'not captured' },
    normalizedArguments: { source: 'session-tool-call', text: normalizedText, digest: module.digestText(normalizedText) },
    prose: { source: 'assistant-message', text: '', blocks: 0, digest: module.digestText('') },
    schemaDigest: module.digestJson(module.TERMINAL_PARAMETERS),
    recordedAt: 0,
  };
  const call = { type: 'tool/call', seq: 1, data: { turn: 1, step: 1, callId: 'call-ok', name: 'c2p_terminal', arguments: normalizedText } };
  const result = { type: 'tool/result', seq: 2, data: { turn: 1, step: 1, message: { content: [{ type: 'tool-result', toolCallId: 'call-ok' }] } } };
  const record = (patch: Record<string, unknown>) => ({ type: 'c2p/terminal', seq: 3, data: { ...good, ...patch } });
  const rebuild = (events: readonly unknown[]) => module.rebuildTerminal(events as never, 3);

  // Control: a consistent record with its successful call is accepted.
  assert.equal(rebuild([call, result, record({})]).state, 'committed');

  // A foreign schema version is refused by name.
  const wrongVersion = rebuild([call, result, record({ schema: 'c2p-terminal/0' })]);
  assert.equal(wrongVersion.state, 'unresolved');
  assert.ok(wrongVersion.state === 'unresolved');
  assert.equal(wrongVersion.reasonCode, 'schema-version-mismatch');

  // A missing required field is refused, not defaulted.
  const missing = rebuild([call, result, record({ parsedDigest: undefined })]);
  assert.ok(missing.state === 'unresolved');
  assert.equal(missing.reasonCode, 'record-missing-field');

  // A digest that contradicts its value is refused.
  const contradicting = rebuild([call, result, record({ parsedDigest: module.digestJson({ kind: 'blocked', reason: 'x' }) })]);
  assert.ok(contradicting.state === 'unresolved');
  assert.equal(contradicting.reasonCode, 'digest-mismatch');

  // Two structurally valid but disagreeing records are a conflict, never last-one-wins.
  const other = { kind: 'blocked', reason: 'y' } as const;
  const conflict = rebuild([call, result, record({}), record({ terminalId: 'terminal-other', parsed: other, parsedDigest: module.digestJson(other) })]);
  assert.ok(conflict.state === 'unresolved');
  assert.equal(conflict.reasonCode, 'conflicting-records');
  assert.match(conflict.reason, /2 disagreeing/);

  // A record with no matching terminal call in this log is refused.
  const orphan = rebuild([result, record({})]);
  assert.ok(orphan.state === 'unresolved');
  assert.equal(orphan.reasonCode, 'no-matching-tool-call');

  // A matching call without its successful result is refused.
  const unsuccessful = rebuild([call, record({})]);
  assert.ok(unsuccessful.state === 'unresolved');
  assert.equal(unsuccessful.reasonCode, 'no-successful-tool-result');
});

test('attribution follows the trusted session, and an unattributable id is ambiguous', async () => {
  const capture = new module.TerminalArgumentCapture();
  const a = '{ "result": { "kind": "draft", "draft": { "title": "A", "body": "a" } } }';
  const b = '{ "result": { "kind": "blocked", "reason": "B" } }';
  const sessionA = 'h03-session-a' as never;
  const sessionB = 'h03-session-b' as never;

  // Interleaved streams of two live sessions that reuse the same call id.
  for await (const _chunk of capture.observe(chunksOf([delta('shared', a), blockEnd('shared'), finish()]) as AsyncIterable<never>, { sessionId: sessionA })) { /* drain */ }
  for await (const _chunk of capture.observe(chunksOf([delta('shared', b), blockEnd('shared'), finish()]) as AsyncIterable<never>, { sessionId: sessionB })) { /* drain */ }
  // A third stream for session A, with no completion fact yet.
  for await (const _chunk of capture.observe(chunksOf([delta('other', a)]) as AsyncIterable<never>, { sessionId: sessionA })) { /* drain */ }

  // Delayed read: each session reads back its own source, never the other's.
  const fromA = capture.raw('shared', { sessionId: sessionA });
  const fromB = capture.raw('shared', { sessionId: sessionB });
  assert.ok(fromA.state === 'captured' && fromB.state === 'captured');
  assert.equal(fromA.text, a, 'session A must get its own raw text');
  assert.equal(fromB.text, b, 'session B must get its own raw text');
  assert.equal(fromA.streamIndex, 1);
  assert.equal(fromB.streamIndex, 2);
  assert.equal(fromA.sessionId, sessionA);
  assert.equal(fromB.sessionId, sessionB);

  // Without the session link the id is ambiguous, not "the most recent one".
  const unlinked = capture.raw('shared');
  assert.equal(unlinked.state, 'ambiguous');
  assert.ok(unlinked.state === 'ambiguous');
  assert.equal(unlinked.candidates.length, 2);

  // A session that never carried the call gets an explicit miss.
  const missing = capture.raw('shared', { sessionId: 'h03-session-c' as never });
  assert.equal(missing.state, 'not_observed');
});

test('completeness is the call\'s own completion fact, not iterator completion', async () => {
  const capture = new module.TerminalArgumentCapture();
  const text = '{ "result": { "kind": "blocked", "reason": "R" } }';

  // (a) completion fact + normal finish -> captured
  for await (const _chunk of capture.observe(chunksOf([delta('ok', text), blockEnd('ok'), finish('tool-calls')]) as AsyncIterable<never>)) { /* drain */ }
  assert.equal(capture.raw('ok').state, 'captured');

  // (b) this call closed, then the stream failed for a LATER call: its own fact stands
  const laterFailure = (async function* twoCalls(): AsyncIterable<never> {
    yield delta('first', text) as never;
    yield blockEnd('first') as never;
    yield delta('second', '{ "result": { "kind": "dra') as never;
    throw new Error('adapter failed on the second call');
  })();
  await assert.rejects(async () => {
    for await (const _chunk of capture.observe(laterFailure)) { /* drain */ }
  }, /adapter failed on the second call/);
  assert.equal(capture.raw('first').state, 'captured', 'a completed call is not retracted by another call\'s failure');
  const second = capture.raw('second');
  assert.ok(second.state === 'incomplete');
  assert.match(second.reason, /failed/);

  // (c) normal finish but NO completion fact for this call -> truncated, not captured
  for await (const _chunk of capture.observe(chunksOf([delta('truncated', text), finish('stop')]) as AsyncIterable<never>)) { /* drain */ }
  const truncated = capture.raw('truncated');
  assert.equal(truncated.state, 'incomplete');
  assert.ok(truncated.state === 'incomplete');
  assert.match(truncated.reason, /block-end completion fact/);

  // (d) normalized abort finish without a completion fact -> incomplete with the reason
  for await (const _chunk of capture.observe(chunksOf([delta('aborted', text), finish('aborted')]) as AsyncIterable<never>)) { /* drain */ }
  const aborted = capture.raw('aborted');
  assert.ok(aborted.state === 'incomplete');
  assert.match(aborted.reason, /finished with aborted/);

  // (e) normalized error finish without a completion fact -> incomplete
  for await (const _chunk of capture.observe(chunksOf([delta('errored', text), finish('error')]) as AsyncIterable<never>)) { /* drain */ }
  assert.equal(capture.raw('errored').state, 'incomplete');

  // (f) consumer abandons the stream before the completion fact -> incomplete
  const abandoned = capture.observe(chunksOf([delta('abandoned', text), blockEnd('abandoned'), finish()]) as AsyncIterable<never>);
  for await (const _chunk of abandoned) break;
  const stopped = capture.raw('abandoned');
  assert.equal(stopped.state, 'incomplete');
  assert.ok(stopped.state === 'incomplete');
  assert.match(stopped.reason, /abandoned/);
});

test('the rebuild refuses damaged structure by name and never throws', () => {
  const normalized = '{"result":{"kind":"draft","draft":{"title":"T","body":"B"}}}';
  const parsed = { kind: 'draft', draft: { title: 'T', body: 'B' } } as const;
  const base = {
    schema: module.TERMINAL_SCHEMA_VERSION,
    terminalId: 'terminal-1',
    callId: 'call-1',
    turn: 1,
    step: 1,
    parsed,
    parsedDigest: module.digestJson(parsed),
    rawArguments: { state: 'not_observed', source: 'llm-stream-tool-call-delta', reason: 'not captured' },
    normalizedArguments: { source: 'session-tool-call', text: normalized, digest: module.digestText(normalized) },
    prose: { source: 'assistant-message', text: '', blocks: 0, digest: module.digestText('') },
    schemaDigest: module.digestJson(module.TERMINAL_PARAMETERS),
    recordedAt: 0,
  };
  const call = { type: 'tool/call', seq: 1, data: { turn: 1, step: 1, callId: 'call-1', name: 'c2p_terminal', arguments: normalized } };
  const result = { type: 'tool/result', seq: 2, data: { turn: 1, step: 1, message: { content: [{ type: 'tool-result', toolCallId: 'call-1', isError: false }] } } };
  const withRecord = (value: unknown) => module.rebuildTerminal([call, result, { type: 'c2p/terminal', seq: 3, data: value }] as never, 3);
  const expectCode = (value: unknown, code: string): void => {
    const outcome = withRecord(value);
    assert.equal(outcome.state, 'unresolved', `expected a refusal, got ${outcome.state}`);
    assert.ok(outcome.state === 'unresolved');
    assert.equal(outcome.reasonCode, code);
  };

  // Control: the intact record is accepted.
  assert.equal(withRecord(base).state, 'committed');

  expectCode(null, 'record-malformed');
  expectCode('not a record', 'record-malformed');
  expectCode({ ...base, terminalId: undefined }, 'record-missing-field');
  expectCode({ ...base, terminalId: '' }, 'record-missing-field');
  expectCode({ ...base, turn: -1 }, 'record-missing-field');
  expectCode({ ...base, normalizedArguments: null }, 'record-missing-field');
  expectCode({ ...base, prose: null }, 'record-missing-field');
  expectCode({ ...base, rawArguments: null }, 'raw-source-invalid');
  expectCode({ ...base, rawArguments: { state: 'bogus' } }, 'raw-source-invalid');
  expectCode({ ...base, rawArguments: { state: 'captured', callId: 'call-1', streamIndex: 1, text: 'x', digest: 'wrong', chunks: 1, byteLength: 1 } }, 'digest-mismatch');
  expectCode({ ...base, parsed: { kind: 'nope' } }, 'parsed-invalid');
  expectCode({ ...base, parsed: { kind: 'draft', draft: { title: 'T' } } }, 'parsed-invalid');
  // A self-consistent but non-union value is still refused.
  const other = { kind: 'draft', draft: { title: 'X', body: 'Y' } } as const;
  expectCode({ ...base, parsed: other, parsedDigest: module.digestJson(other) }, 'parsed-mismatch');
  expectCode({ ...base, schemaDigest: 'z' }, 'schema-digest-mismatch');
  expectCode({ ...base, schema: 'c2p-terminal/0' }, 'schema-version-mismatch');
});

test('the rebuild validates every record and treats disagreement as a conflict', () => {
  const normalized = '{"result":{"kind":"draft","draft":{"title":"T","body":"B"}}}';
  const parsed = { kind: 'draft', draft: { title: 'T', body: 'B' } } as const;
  const base = {
    schema: module.TERMINAL_SCHEMA_VERSION,
    terminalId: 'terminal-2',
    callId: 'call-2',
    turn: 2,
    step: 3,
    parsed,
    parsedDigest: module.digestJson(parsed),
    rawArguments: { state: 'not_observed', source: 'llm-stream-tool-call-delta', reason: 'not captured' },
    normalizedArguments: { source: 'session-tool-call', text: normalized, digest: module.digestText(normalized) },
    prose: { source: 'assistant-message', text: '', blocks: 0, digest: module.digestText('') },
    schemaDigest: module.digestJson(module.TERMINAL_PARAMETERS),
    recordedAt: 0,
  };
  const call = { type: 'tool/call', seq: 1, data: { turn: 2, step: 3, callId: 'call-2', name: 'c2p_terminal', arguments: normalized } };
  const result = { type: 'tool/result', seq: 2, data: { turn: 2, step: 3, message: { content: [{ type: 'tool-result', toolCallId: 'call-2', isError: false }] } } };
  const withRecords = (...values: unknown[]) => module.rebuildTerminal([
    call, result, ...values.map((value, index) => ({ type: 'c2p/terminal', seq: 3 + index, data: value })),
  ] as never, 3);
  const expectConflict = (...values: unknown[]): void => {
    const outcome = withRecords(...values);
    assert.equal(outcome.state, 'unresolved');
    assert.ok(outcome.state === 'unresolved');
    assert.equal(outcome.reasonCode, 'conflicting-records');
  };

  // An identical repeat is idempotent.
  assert.equal(withRecords(base, { ...base }).state, 'committed');
  // Every other field that disagrees is a conflict, not first-one-wins.
  expectConflict(base, { ...base, prose: { source: 'assistant-message', text: 'other', blocks: 1, digest: module.digestText('other') } });
  // A damaged second record is rejected by its own validation before any duplicate
  // comparison; a structurally valid but different one is the conflict.
  expectConflict(base, { ...base, callId: 'call-2b' });
  expectConflict(base, { ...base, turn: 9 });
  expectConflict(base, { ...base, step: 9 });
  expectConflict(base, { ...base, normalizedArguments: { ...base.normalizedArguments, text: '{"result":{}}', digest: module.digestText('{"result":{}}') } });
  expectConflict(base, { ...base, rawArguments: { state: 'incomplete', callId: 'call-2', streamIndex: 1, text: 'x', digest: module.digestText('x'), chunks: 1, byteLength: 1, reason: 'truncated' } });
  // A damaged SECOND record is reported with its own code, not hidden by the first.
  const damagedSecond = withRecords(base, { ...base, parsed: null });
  assert.ok(damagedSecond.state === 'unresolved');
  assert.equal(damagedSecond.reasonCode, 'parsed-invalid');
});

test('the rebuild attributes the record to a real successful call', () => {
  const normalized = '{"result":{"kind":"draft","draft":{"title":"T","body":"B"}}}';
  const parsed = { kind: 'draft', draft: { title: 'T', body: 'B' } } as const;
  const record = {
    schema: module.TERMINAL_SCHEMA_VERSION,
    terminalId: 'terminal-3',
    callId: 'call-3',
    turn: 1,
    step: 2,
    parsed,
    parsedDigest: module.digestJson(parsed),
    rawArguments: { state: 'not_observed', source: 'llm-stream-tool-call-delta', reason: 'not captured' },
    normalizedArguments: { source: 'session-tool-call', text: normalized, digest: module.digestText(normalized) },
    prose: { source: 'assistant-message', text: '', blocks: 0, digest: module.digestText('') },
    schemaDigest: module.digestJson(module.TERMINAL_PARAMETERS),
    recordedAt: 0,
  };
  const call = (data: Record<string, unknown>) => ({ type: 'tool/call', seq: 1, data: { turn: 1, step: 2, callId: 'call-3', name: 'c2p_terminal', arguments: normalized, ...data } });
  const result = (block: Record<string, unknown>) => ({ type: 'tool/result', seq: 2, data: { turn: 1, step: 2, message: { content: [{ type: 'tool-result', toolCallId: 'call-3', ...block }] } } });
  const stored = { type: 'c2p/terminal', seq: 3, data: record };
  const outcome = (events: readonly unknown[]) => module.rebuildTerminal(events as never, 3);
  const expectCode = (events: readonly unknown[], code: string): void => {
    const built = outcome(events);
    assert.ok(built.state === 'unresolved', `expected a refusal, got ${built.state}`);
    assert.equal(built.reasonCode, code);
  };

  // Control.
  assert.equal(outcome([call({}), result({ isError: false }), stored]).state, 'committed');
  // The failure fact is the tool-result block's isError, not the optional `error` identity.
  expectCode([call({}), result({ isError: true }), stored], 'no-successful-tool-result');
  // A call in another turn/step cannot authorize this record.
  expectCode([call({ turn: 4 }), result({ isError: false }), stored], 'no-matching-tool-call');
  // Normalized text must equal the call's own logged arguments.
  expectCode([call({ arguments: '{"result":{"kind":"blocked","reason":"x"}}' }), result({ isError: false }), stored], 'arguments-mismatch');
  // Two calls sharing id and turn/step cannot be attributed.
  expectCode([call({}), call({}), result({ isError: false }), stored], 'ambiguous-call');
  // No terminal call at all.
  expectCode([result({ isError: false }), stored], 'no-matching-tool-call');
});

test('V4 independent tool messages correspond by call, turn, step and isError', () => {
  const normalized = '{"result":{"kind":"blocked","reason":"R"}}';
  const parsed = { kind: 'blocked', reason: 'R' } as const;
  const record = {
    schema: module.TERMINAL_SCHEMA_VERSION,
    terminalId: 'terminal-v4',
    callId: 'call-v4',
    turn: 2,
    step: 1,
    parsed,
    parsedDigest: module.digestJson(parsed),
    rawArguments: { state: 'not_observed', source: 'llm-stream-tool-call-delta', reason: 'not captured' },
    normalizedArguments: { source: 'session-tool-call', text: normalized, digest: module.digestText(normalized) },
    prose: { source: 'assistant-message', text: '', blocks: 0, digest: module.digestText('') },
    schemaDigest: module.digestJson(module.TERMINAL_PARAMETERS),
    recordedAt: 0,
  };
  const call = { type: 'tool/call', seq: 1, data: { turn: 2, step: 1, callId: 'call-v4', name: 'c2p_terminal', arguments: normalized } };
  const toolMessage = (patch: Record<string, unknown>) => ({
    type: 'tool/result',
    seq: 2,
    data: {
      turn: 2,
      step: 1,
      message: { role: 'tool', toolCallId: 'call-v4', content: [{ type: 'text', text: 'ok' }], ...patch },
    },
  });
  const stored = { type: 'c2p/terminal', seq: 3, data: record };
  const rebuild = (events: readonly unknown[], version: number) => module.rebuildTerminal(events as never, version);

  assert.equal(rebuild([call, toolMessage({}), stored], 4).state, 'committed');
  const errored = rebuild([call, toolMessage({ isError: true }), stored], 4);
  assert.ok(errored.state === 'unresolved');
  assert.equal(errored.reasonCode, 'no-successful-tool-result');

  const notStarted = rebuild([call, {
    type: 'tool/result', seq: 2,
    data: {
      turn: 2, step: 1,
      message: { role: 'tool', toolCallId: 'call-v4', isError: true, content: [{ type: 'text', text: 'interrupted' }] },
      error: { name: 'ToolRecovery', code: 'TOOL_NOT_STARTED' },
    },
  }, stored], 4);
  assert.ok(notStarted.state === 'unresolved');
  assert.equal(notStarted.reasonCode, 'no-successful-tool-result');

  const unknown = rebuild([call, {
    type: 'tool/result', seq: 2,
    data: {
      turn: 2, step: 1,
      message: { role: 'tool', toolCallId: 'call-v4', isError: true, content: [{ type: 'text', text: 'unknown' }] },
      error: { name: 'ToolRecovery', code: 'TOOL_OUTCOME_UNKNOWN' },
    },
  }, stored], 4);
  assert.ok(unknown.state === 'unresolved');
  assert.equal(unknown.reasonCode, 'no-successful-tool-result');

  // A V3 block is not a V4 success, and a V4 message is not a V3 success.
  const v3Shape = rebuild([call, {
    type: 'tool/result', seq: 2,
    data: { turn: 2, step: 1, message: { content: [{ type: 'tool-result', toolCallId: 'call-v4', isError: false }] } },
  }, stored], 4);
  assert.ok(v3Shape.state === 'unresolved');
  assert.equal(v3Shape.reasonCode, 'tool-result-malformed');
  const v4AsV3 = rebuild([call, toolMessage({}), stored], 3);
  assert.ok(v4AsV3.state === 'unresolved');
  assert.equal(v4AsV3.reasonCode, 'tool-result-malformed');
  const unsupported = rebuild([call, toolMessage({}), stored], 9);
  assert.ok(unsupported.state === 'unresolved');
  assert.equal(unsupported.reasonCode, 'format-unsupported');

  const nullCall = rebuild([
    { type: 'tool/call', seq: 1, data: null },
    toolMessage({}), stored,
  ], 4);
  assert.ok(nullCall.state === 'unresolved');
  assert.equal(nullCall.reasonCode, 'tool-call-malformed');

  const nullEvent = rebuild([null, call, toolMessage({}), stored], 4);
  assert.ok(nullEvent.state === 'unresolved');
  assert.equal(nullEvent.reasonCode, 'event-malformed');

  for (const isError of ['true', 1]) {
    const badFlag = rebuild([call, toolMessage({ isError }), stored], 4);
    assert.ok(badFlag.state === 'unresolved', `isError ${JSON.stringify(isError)} must not commit`);
    assert.equal(badFlag.reasonCode, 'tool-result-malformed');
  }
  const nullContent = rebuild([call, toolMessage({ content: null }), stored], 4);
  assert.ok(nullContent.state === 'unresolved');
  assert.equal(nullContent.reasonCode, 'tool-result-malformed');
  const badError = rebuild([call, {
    type: 'tool/result', seq: 2,
    data: {
      turn: 2, step: 1,
      message: { role: 'tool', toolCallId: 'call-v4', content: [{ type: 'text', text: 'ok' }] },
      error: { name: 'ToolRecovery', code: { broken: true } },
    },
  }, stored], 4);
  assert.ok(badError.state === 'unresolved');
  assert.equal(badError.reasonCode, 'tool-result-malformed');
});
