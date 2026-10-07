/**
 * B02: the Python launcher refuses a candidate flag, env and root that disagree.
 * The matching selection reports the 0.2 root and does not touch the default runtime.
 */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const packageDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repoRoot = path.resolve(packageDir, '../..');
const CANDIDATE_ID = process.env.C2P_DSH_CANDIDATE ?? '0.2.0-rc.1';
const candidateRoot = path.join(repoRoot, '.dsh-dev/candidates', CANDIDATE_ID);
const launcher = path.join(repoRoot, 'scripts/dsh_dev.py');

function run(args: string[], env: Record<string, string | undefined>): { status: number | null; stdout: string; stderr: string } {
  const result = spawnSync(process.env.PYTHON ?? 'python', [launcher, ...args], {
    cwd: repoRoot,
    encoding: 'utf8',
    env: {
      HOME: process.env.HOME,
      PATH: process.env.PATH,
      ...env,
    },
  });
  return { status: result.status, stdout: result.stdout, stderr: result.stderr };
}

const UPSTREAM_VERSION = CANDIDATE_ID.split('+', 1)[0];

test('a matching selection reports its candidate root and separates id from upstream', () => {
  const result = run(['--candidate', CANDIDATE_ID, 'candidate'], {
    C2P_DSH_CANDIDATE: CANDIDATE_ID,
    C2P_DSH_DEV_ROOT: candidateRoot,
  });
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout) as {
    candidate: string; runtime: string; installed_version: string; candidate_id: string; upstream_version: string;
  };
  assert.equal(report.candidate, CANDIDATE_ID);
  assert.equal(report.candidate_id, CANDIDATE_ID);
  assert.equal(report.upstream_version, UPSTREAM_VERSION);
  assert.equal(report.installed_version, UPSTREAM_VERSION);
  assert.ok(report.runtime.endsWith(`/.dsh-dev/candidates/${CANDIDATE_ID}/runtime`));
});

test('a candidate flag that disagrees with the env or the root is refused', () => {
  const envMismatch = run(['--candidate', CANDIDATE_ID, 'candidate'], {
    C2P_DSH_CANDIDATE: '0.1.5-rc.3',
    C2P_DSH_DEV_ROOT: candidateRoot,
  });
  assert.notEqual(envMismatch.status, 0);
  assert.match(envMismatch.stderr, /candidate mismatch/);

  const rootMismatch = run(['--candidate', CANDIDATE_ID, 'candidate'], {
    C2P_DSH_CANDIDATE: CANDIDATE_ID,
    C2P_DSH_DEV_ROOT: path.join(repoRoot, '.dsh-dev'),
  });
  assert.notEqual(rootMismatch.status, 0);
  assert.match(rootMismatch.stderr, /candidate mismatch/);

  const unnamed = run(['candidate'], {
    C2P_DSH_DEV_ROOT: candidateRoot,
  });
  assert.notEqual(unnamed.status, 0);
  assert.match(unnamed.stderr, /no candidate is selected/);
});
