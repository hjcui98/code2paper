/** C01: consume Python-produced schema/goldens as bytes, then return actual TS bytes to Python. */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { before, test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
import type * as WireApi from '../src/wire.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const packageRoot = path.join(root, 'integrations/dsh');
const devRoot = process.env.C2P_DSH_DEV_ROOT ?? path.join(root, '.dsh-dev');
const staged = path.join(devRoot, 'home/profiles/node_modules/@code2paper/dsh-bundle/lib/wire.js');
const python = path.join(devRoot, 'pyworker/bin/python');
const fixtures = path.join(packageRoot, 'wire-v1');
interface Golden { name: string; model: string; raw: string; expected: string; wire_digest: string; semantic_digest?: string }
const cases = JSON.parse(readFileSync(path.join(fixtures, 'goldens.json'), 'utf8')) as Golden[];
let wire: typeof WireApi;
before(async () => { wire = await import(pathToFileURL(staged).href) as typeof WireApi; });

for (const golden of cases) test(`Python wire golden: ${golden.name}`, () => {
  const raw = Buffer.from(golden.raw, 'utf8');
  assert.equal(`sha256:${createHash('sha256').update(raw).digest('hex')}`, golden.wire_digest);
  const schema = wire.decodeWire(readFileSync(path.join(fixtures, `${golden.model}.schema.json`)));
  assert.ok(wire.isObject(schema));
  if (golden.expected !== 'ok') {
    assert.throws(() => wire.parseWire(raw, schema), (error: unknown) => error instanceof wire.WireError && error.code === golden.expected);
    return;
  }
  const parsed = wire.parseWire(raw, schema);
  assert.ok(Object.isFrozen(parsed));
  // The subprocess receives newly serialized TS bytes; Python recomputes the
  // semantic digest and rechecks its private model, including digest/scope relations.
  const result = spawnSync(python, ['-c', [
    'import sys',
    'from code2paper.integrations.dsh import writer_contract as c',
    'from code2paper.integrations.dsh.protocol import parse_model,strict_json_loads',
    'from code2paper.agentic.digest import digest_json',
    'raw=sys.stdin.buffer.read()',
    'parse_model(raw,getattr(c,sys.argv[1]))',
    'print(digest_json(strict_json_loads(raw)))',
  ].join('\n'), golden.model], { input: JSON.stringify(parsed), cwd: root, encoding: 'utf8', timeout: 15000 });
  assert.equal(result.error, undefined);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout.trim(), golden.semantic_digest);
});

test('escaped duplicate keys, nested duplicates, non-finite numbers and malformed UTF-8 reject before schema', () => {
  for (const raw of ['{"a":0,"\\u0061":1}', '{"nested":{"x":0,"x":1}}']) {
    assert.throws(() => wire.decodeWire(raw), { code: 'duplicate_json_key' });
  }
  for (const raw of ['NaN', 'Infinity', '-Infinity', '1e999']) assert.throws(() => wire.decodeWire(raw), { code: 'non_finite_number' });
  for (const raw of ['9007199254740992', '-9007199254740992']) assert.throws(() => wire.decodeWire(raw), { code: 'integer_out_of_range' });
  for (const raw of ['"\\ud800"', '"\\udc00"']) assert.throws(() => wire.decodeWire(raw), { code: 'invalid_unicode' });
  assert.throws(() => wire.decodeWire(Uint8Array.from([0x22, 0xc0, 0xaf, 0x22])), { code: 'invalid_json' });
  assert.throws(() => wire.decodeWire(' '.repeat(wire.MAX_WIRE_BYTES + 1)), { code: 'frame_too_large' });
  assert.deepEqual(wire.decodeWire('{"__proto__":{"admin":true}}'), JSON.parse('{"__proto__":{"admin":true}}'));
  assert.equal(({} as Record<string, unknown>)['admin'], undefined);
});

test('strict integer spelling survives nested arrays, refs and unions while number fields accept decimals and exponents', () => {
  const integer: WireApi.JsonObject = { type: 'integer' };
  for (const raw of ['1.0', '1e0', '-0.0']) assert.throws(() => wire.parseWire(raw, integer), { code: 'schema_invalid' });
  assert.equal(wire.parseWire('1', integer), 1);
  const schema: WireApi.JsonObject = { type: 'object', $defs: { counter: integer }, properties: {
    'a/b~c': { type: 'array', items: { anyOf: [{ $ref: '#/$defs/counter' }, { type: 'null' }] } },
    sampling: { type: 'number' },
  }, additionalProperties: false };
  for (const raw of ['{"a/b~c":[1.0],"sampling":1e0}', '{"a/b~c":[1e0],"sampling":1.0}']) {
    assert.throws(() => wire.parseWire(raw, schema), { code: 'schema_invalid' });
    assert.throws(() => wire.validateWireSchema(wire.decodeWire(raw), schema), { code: 'schema_invalid' });
  }
  assert.deepEqual(wire.parseWire('{"a/b~c":[1,null],"sampling":1.0}', schema), { 'a/b~c': [1, null], sampling: 1 });
  assert.deepEqual(wire.parseWire('{"a/b~c":[1],"sampling":2e-1}', schema), { 'a/b~c': [1], sampling: 0.2 });
});

test('full exported schema keeps unknown version, nullable-required, union and extra restrictions', () => {
  const schema = wire.decodeWire(readFileSync(path.join(fixtures, 'ArtifactRefV1.schema.json')));
  assert.ok(wire.isObject(schema));
  const contract = JSON.parse(cases.find(item => item.model === 'WriterTaskContractV1' && item.expected === 'ok')!.raw) as { read_set: WireApi.JsonObject[] };
  const ref = contract.read_set[0]!;
  wire.parseWire(JSON.stringify(ref), schema);
  for (const changes of [{ schema_version: 'ArtifactRefV2' }, { path: '/etc/passwd' }, { task_epoch: -1 }, { byte_length: 1.5 }]) {
    assert.throws(() => wire.parseWire(JSON.stringify({ ...ref, ...changes }), schema), { code: 'schema_invalid' });
  }
  const { semantic_digest: _removed, ...absent } = ref;
  assert.throws(() => wire.parseWire(JSON.stringify(absent), schema), { code: 'schema_invalid' });
});

test('unsupported schema constraints reject explicitly instead of being ignored', () => {
  assert.throws(() => wire.validateWireSchema('x', { type: 'string', format: 'secret-format' }), { code: 'schema_unsupported' });
  assert.throws(() => wire.validateWireSchema({}, { '$ref': 'https://example.invalid/schema' }), { code: 'schema_unsupported' });
});

test('versioned Unicode rule exactly matches Python export and rejects unsupported pattern contracts', () => {
  assert.deepEqual(wire.IDENTIFIER_CHARACTER_RULE, JSON.parse(readFileSync(path.join(fixtures, 'character-rules.json'), 'utf8')));
  const rule = wire.IDENTIFIER_CHARACTER_RULE;
  const schema = { type: 'string', minLength: 1, maxLength: 256, pattern: rule.pattern, 'x-c2p-character-rule': rule.rule };
  for (const value of ['\ufeff', '\u001c', '\u001d', '\u001e', '\u001f', '正文', '\u0085正文', '🚀'.repeat(256)]) {
    assert.equal(wire.parseWire(JSON.stringify(value), schema), value);
  }
  for (const range of rule.whitespace_ranges) {
    const first = range[0]!; const last = range[1]!;
    for (let cp = first; cp <= last; cp++) assert.throws(() => wire.parseWire(JSON.stringify(String.fromCodePoint(cp)), schema), { code: 'schema_invalid' });
  }
  assert.throws(() => wire.parseWire(JSON.stringify('🚀'.repeat(257)), schema), { code: 'schema_invalid' });
  for (const bad of [
    { ...schema, 'x-c2p-character-rule': 'unicode-white-space-nonblank/2' },
    { ...schema, pattern: '\\S' },
    { type: 'string', pattern: rule.pattern },
    { type: 'string', pattern: '\\S' },
    { type: 'string', pattern: '.*' },
  ]) assert.throws(() => wire.parseWire('"body"', bad), { code: 'schema_unsupported' });
});

test('ASCII digest matching rejects trailing line terminators and non-ASCII lookalikes', () => {
  const schema = { type: 'string', pattern: '^sha256:[0-9a-f]{64}$' };
  const digest = `sha256:${'a'.repeat(64)}`;
  assert.equal(wire.parseWire(JSON.stringify(digest), schema), digest);
  for (const value of [digest + '\n', digest + '\r', digest + '\u2028', digest.replace('a', 'Ａ'), digest.toUpperCase()]) {
    assert.throws(() => wire.parseWire(JSON.stringify(value), schema), { code: 'schema_invalid' });
  }
});

test('native Writer emission rejects omitted paragraphs and witnesses before legacy defaults', () => {
  const native = wire.decodeWire(readFileSync(path.join(fixtures, 'native-terminal.schema.json')));
  const full = wire.decodeWire(readFileSync(path.join(fixtures, 'WriterTaskResultV1.schema.json')));
  assert.ok(wire.isObject(native)); assert.ok(wire.isObject(full));
  const paragraph = { paragraph_id: 'p1', paragraph_markdown: 'A source-bound clause.' };
  const value = { schema_version: 'WriterTaskResultV1', result: { outcome: 'draft',
    draft: { section_id: 'section', paragraphs: [paragraph] } } };
  // Frozen historical publication data remains readable by its original schema.
  wire.parseWire(JSON.stringify(value), full);
  assert.throws(() => wire.parseWire(JSON.stringify(value), native), { code: 'schema_invalid' });
  const sectionOnly = { schema_version: 'WriterTaskResultV1', result: { outcome: 'draft',
    draft: { section_id: 'section', section_markdown: 'A source-bound clause.' } } };
  wire.parseWire(JSON.stringify(sectionOnly), full);
  assert.throws(() => wire.parseWire(JSON.stringify(sectionOnly), native), { code: 'schema_invalid' });
  const complete = { ...value, result: { ...value.result, draft: { ...value.result.draft,
    paragraphs: [{ ...paragraph, witnesses: [{ witness_kind: 'detail', target_id: 'detail',
      exact_text: paragraph.paragraph_markdown }] }] } } };
  wire.parseWire(JSON.stringify(complete), native);
  wire.parseWire(JSON.stringify(complete), full);
  // Structural presence is not target coverage; empty arrays remain for the
  // original paragraph-dependent content assessor to accept or reject.
  const empty = { ...value, result: { ...value.result, draft: { ...value.result.draft,
    paragraphs: [{ ...paragraph, witnesses: [] }] } } };
  wire.parseWire(JSON.stringify(empty), native);
});

test('native emission retains blocked/research branches and the full witness guard', () => {
  const native = wire.decodeWire(readFileSync(path.join(fixtures, 'native-terminal.schema.json')));
  const full = wire.decodeWire(readFileSync(path.join(fixtures, 'WriterTaskResultV1.schema.json')));
  assert.ok(wire.isObject(native)); assert.ok(wire.isObject(full));
  for (const name of ['blocked_unicode', 'research_required']) {
    const value = cases.find(item => item.name === name)!;
    wire.parseWire(value.raw, native); wire.parseWire(value.raw, full);
  }
  const invalid = { schema_version: 'WriterTaskResultV1', result: { outcome: 'draft', draft: {
    section_id: 'section', paragraphs: [{ paragraph_id: 'p1', paragraph_markdown: 'A clause.',
      witnesses: [{ witness_kind: 'detail', target_id: 'detail', exact_text: '' }] }] } } };
  assert.throws(() => wire.parseWire(JSON.stringify(invalid), full), { code: 'schema_invalid' });
});
