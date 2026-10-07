/** V02 actual executable refusal checks; positive qualification is a bound Host suite. */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, mkdtempSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { before, test } from 'node:test';
import { fileURLToPath } from 'node:url';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const devRoot = process.env.C2P_DSH_DEV_ROOT!;
const python = path.join(devRoot, 'pyworker/bin/python');
const executable = path.join(devRoot, 'home/profiles/node_modules/@code2paper/dsh-bundle/lib/cli.js');
const candidate = process.env.C2P_DSH_CANDIDATE ?? path.basename(devRoot);
let root: string;
let bootstrap: string;
let partialReceipt: string;
let legacyReceipt: string;
let invalidReceipt: string;

function inventory(directory: string): Record<string, string> {
  const result: Record<string, string> = {};
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      for (const [nested, digest] of Object.entries(inventory(file))) result[path.join(entry.name, nested)] = digest;
    } else {
      assert.ok(entry.isFile(), 'admission must not create links or special files');
      result[entry.name] = createHash('sha256').update(readFileSync(file)).digest('hex');
    }
  }
  return result;
}

before(() => {
  assert.ok(path.isAbsolute(devRoot));
  assert.ok(statSync(executable).isFile(), 'the actual staged CLI must exist');
  root = mkdtempSync(path.join(process.env.C2P_DSH_RUN_ROOT!, 'stage04-cli-negative-'));
  mkdirSync(path.join(root, 'receipts'));
  bootstrap = path.join(root, 'invalid-bootstrap.json');
  partialReceipt = path.join(root, 'receipts/partial.json');
  legacyReceipt = path.join(root, 'receipts/legacy.json');
  invalidReceipt = path.join(root, 'receipts/invalid.json');
  writeFileSync(bootstrap, '{}');
  writeFileSync(invalidReceipt, '{malformed');
  // Original models produce negative fixtures only: no claimed passing tests,
  // current identities, machine reports or complete DSH coverage are invented.
  const produced = spawnSync(python, ['-c', [
    'import json',
    'from code2paper.agentic.live_admission_preflight import OfflineSuiteReceiptV1',
    'legacy=OfflineSuiteReceiptV1()',
    "partial=OfflineSuiteReceiptV1(schema_version='2.0',coverage_failure_code='offline_suite_reports_missing')",
    "print(json.dumps({'legacy':legacy.model_dump(mode='json'),'partial':partial.model_dump(mode='json')}))",
  ].join('\n')], { cwd: repo, env: { ...process.env, PYTHONPATH: path.join(repo, 'src'), PYTHONDONTWRITEBYTECODE: '1' },
    encoding: 'utf8', timeout: 30_000, maxBuffer: 64 << 10 });
  assert.equal(produced.error, undefined);
  assert.equal(produced.status, 0, 'original receipt model fixture creation must succeed');
  const values = JSON.parse(produced.stdout) as { legacy: unknown; partial: unknown };
  writeFileSync(legacyReceipt, JSON.stringify(values.legacy));
  writeFileSync(partialReceipt, JSON.stringify(values.partial));
});

function options(overrides: Readonly<Record<string, string>> = {}): string[] {
  const values = { '--candidate': candidate, '--offline-receipt': partialReceipt, '--python': python,
    '--engine-root': repo, '--bootstrap': bootstrap, ...overrides };
  return ['admit', '--experimental-dsh', ...Object.entries(values).flatMap(([key, value]) => [key, value])];
}

function refuses(argv: readonly string[], reason: string): void {
  const before = inventory(root);
  const result = spawnSync(process.execPath, [executable, ...argv], {
    cwd: repo, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
    encoding: 'utf8', timeout: 35_000, maxBuffer: 64 << 10,
  });
  assert.equal(result.error, undefined, 'the actual executable must finish normally');
  assert.equal(result.signal, null);
  assert.equal(result.status, 2);
  assert.equal(result.stderr, '', 'the CLI must not leak traceback or operator configuration');
  assert.deepEqual(JSON.parse(result.stdout), { schema_version: 'DshHostAdmissionV1', admitted: false, reason });
  assert.deepEqual(inventory(root), before, 'refusal must not create a task, journal, claim or worker output');
}

test('executable requires explicit opt-in before bootstrap or receipt processing', () => {
  refuses(options().filter(value => value !== '--experimental-dsh'), 'experimental_dsh_opt_in_required');
});

test('executable rejects unsupported parallel execution before admission', () => {
  refuses([...options(), '--parallel-agents', 'true'], 'parallel_execution_unsupported');
});

for (const flag of ['TRUE', '1', '', 'null']) test(`executable rejects malformed parallel flag ${JSON.stringify(flag)}`, () => {
  refuses([...options(), '--parallel-agents', flag], 'execution_parallel_flag_invalid');
});

for (const invalid of ['../other', '.', '..', '']) test(`executable rejects candidate ${JSON.stringify(invalid)}`, () => {
  refuses(options({ '--candidate': invalid }), 'host_admission_candidate_invalid');
});

for (const key of ['--offline-receipt', '--python', '--engine-root', '--bootstrap']) {
  test(`executable requires an absolute operator path for ${key}`, () => {
    refuses(options({ [key]: 'relative-path' }), 'host_admission_absolute_path_required');
  });
}

test('executable rejects unknown options and missing option values', () => {
  refuses([...options(), '--unknown', 'value'], 'host_cli_option_invalid');
  refuses([...options(), '--bootstrap'], 'host_cli_option_invalid');
});

test('executable rejects duplicate valued and opt-in switches', () => {
  refuses([...options(), '--candidate', candidate], 'host_cli_option_invalid');
  refuses([...options(), '--experimental-dsh'], 'host_cli_duplicate_option');
});

test('executable rejects an unsupported command', () => {
  refuses(['publish', ...options().slice(1)], 'host_cli_command_invalid');
});

test('offline run requires a frozen operator launch before booting a Host', () => {
  refuses(['run',...options().slice(1)],'host_cli_launch_file_required');
});


test('qualification requires explicit opt-in and a frozen absolute launch', () => {
  const qualified=['qualify',...options().slice(1)];
  refuses(qualified.filter(value=>value !== '--experimental-dsh'),'experimental_dsh_opt_in_required');
  refuses(qualified,'host_cli_launch_file_required');
  refuses([...qualified,'--launch-file','relative-launch'],'host_admission_absolute_path_required');
});

test('qualification rejects parallel execution before any owner or Host entry', () => {
  refuses(['qualify',...options().slice(1),'--parallel-agents','true','--launch-file',bootstrap],
    'parallel_execution_unsupported');
});

test('normal commands cannot select core qualification through a switch', () => {
  for (const command of ['admit','run']) {
    refuses([command,...options().slice(1),'--qualification-core'],'host_cli_option_invalid');
  }
});

test('original owner rejects a missing receipt before bootstrap inspection', () => {
  refuses(options({ '--offline-receipt': path.join(root, 'receipts/missing.json') }), 'host_admission_unavailable_or_invalid');
});

test('original owner rejects malformed receipt JSON before bootstrap inspection', () => {
  refuses(options({ '--offline-receipt': invalidReceipt }), 'invalid_json');
});

test('original owner refuses legacy coverage as DSH admission', () => {
  refuses(options({ '--offline-receipt': legacyReceipt }), 'host_admission_full_dsh_receipt_required');
});

test('original owner refuses a partial machine receipt as DSH admission', () => {
  refuses(options(), 'host_admission_full_dsh_receipt_required');
});

// The executable's admit command is read-only and has no Context/adapter. These
// tests exercise refusal ordering plus absence of task output; they do not claim
// full passing A01 coverage, positive Host execution or real-model compatibility.
