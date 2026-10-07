/**
 * H01 composition inventory for the selected 0.2 candidate.
 *
 * The runtime tree may contain provider, title, retry, compaction, PTC, OTel
 * and schedule packages. The development profile whitelist and the offline
 * patch keep the real network rows disabled. This file records that inventory
 * and proves the launcher test process has no external network.
 */
import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { connect } from 'node:net';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const packageDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const devRoot = process.env.C2P_DSH_DEV_ROOT
  ? path.resolve(process.env.C2P_DSH_DEV_ROOT)
  : path.resolve(packageDir, '../../.dsh-dev');
const runtimePackages = path.join(devRoot, 'runtime/node_modules/@deepseek-ai');

test('the selected candidate matches its id and its profile whitelist is unchanged', () => {
  const candidateId = process.env.C2P_DSH_CANDIDATE ?? '0.2.0-rc.1';
  assert.equal(path.basename(devRoot), candidateId);
  const manifest = JSON.parse(readFileSync(path.join(devRoot, 'manifest.json'), 'utf8')) as {
    dsh_version: string;
    upstream_dsh_version?: string;
    runtime_tree_sha256: string;
    base_runtime_tree_sha256?: string;
    compositions: { web: string[]; compat: string[] };
  };
  assert.equal(manifest.dsh_version, candidateId);
  if (candidateId.includes('+')) {
    // A patched candidate validates the upstream version separately and
    // records the base and patched tree identities.
    assert.equal(manifest.upstream_dsh_version, candidateId.split('+', 1)[0]);
    assert.equal(manifest.base_runtime_tree_sha256, '43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c');
    assert.notEqual(manifest.runtime_tree_sha256, manifest.base_runtime_tree_sha256);
  } else {
    assert.equal(manifest.runtime_tree_sha256, '43490765da460c4300cd7ad8ec75dbc5d5e6dbda93b74e37466c6709c1ab359c');
  }
  assert.deepEqual(manifest.compositions.web, ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app']);
  assert.deepEqual(manifest.compositions.compat, [
    '@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app', '@code2paper/dsh-bundle',
  ]);
  const profile = JSON.parse(readFileSync(
    path.join(devRoot, 'home/profiles/code2paper-dev-compat/package.json'),
    'utf8',
  )) as { dsh: { profile: { bundles: string[] } } };
  assert.deepEqual(profile.dsh.profile.bundles, manifest.compositions.compat);
});

test('provider, title, retry, compaction, PTC, OTel and schedule are inventoried and network rows stay disabled', () => {
  const present = new Set(readdirSync(runtimePackages));
  const required = [
    'dsh-llm',
    'dsh-llm-deepseek',
    'dsh-llm-pi-ai',
    'dsh-llm-retry',
    'dsh-session-title',
    'dsh-session-title-llm',
    'dsh-compaction',
    'dsh-ptc-runtime',
    'dsh-otel',
    'dsh-session-telemetry-otel',
    'dsh-schedule',
    'dsh-experimental-schedule-bundle',
    'dsh-web-app',
  ];
  for (const name of required) assert.ok(present.has(name), `${name} is part of the 0.2 candidate tree`);
  assert.equal(present.has('dsh-desktop'), false, 'this candidate has no desktop package; the web app is the UI surface');
  const patch = readFileSync(path.join(packageDir, 'dev/offline.patch.yml'), 'utf8');
  for (const id of [
    'llm-deepseek', 'llm-pi-ai', 'llm-retry', 'session-title-llm', 'session-telemetry-otel',
    'web-search-deepseek', 'web-fetch-http',
  ]) {
    assert.match(patch, new RegExp(`id: ${id}\\n  disabled: true`));
  }
  const base = JSON.parse(readFileSync(path.join(runtimePackages, 'dsh-base/package.json'), 'utf8')) as {
    dependencies: Record<string, string>;
  };
  assert.equal(base.dependencies['@deepseek-ai/dsh-schedule'], undefined, 'schedule stays an optional tree package, not a base dependency');
  assert.ok(base.dependencies['@deepseek-ai/dsh-llm-retry'] !== undefined);
  assert.ok(existsSync(path.join(devRoot, 'home/profiles/code2paper-dev/package.json')));
});

test('the launcher network namespace cannot open an external connection', async () => {
  const error = await new Promise<Error | undefined>((resolve) => {
    const socket = connect({ host: '1.1.1.1', port: 443 });
    const timer = setTimeout(() => {
      socket.destroy();
      resolve(new Error('timed out'));
    }, 1500);
    socket.once('connect', () => {
      clearTimeout(timer);
      socket.destroy();
      resolve(undefined);
    });
    socket.once('error', (caught: Error) => {
      clearTimeout(timer);
      resolve(caught);
    });
  });
  assert.ok(error !== undefined, 'an external connection must fail inside the offline launcher');
});
