/**
 * B02 acceptance evidence: module resolution at the *final staging install
 * location* and non-pollution of the frozen runtime.
 *
 * The bundle is installed the way the profile loads it:
 *   <DSH_HOME>/profiles/node_modules/@code2paper/dsh-bundle
 * and its DSH/Cordis peers must resolve from the host installation that owns that
 * profile — never from this repository and never from a vendored copy.
 *
 * Run after `python scripts/dsh_dev.py stage`:
 *   npm --prefix integrations/dsh run test:compat
 */

import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, lstatSync, readFileSync, readdirSync, realpathSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { Service } from '@deepseek-ai/cordis';

const here = path.dirname(fileURLToPath(import.meta.url));
const packageDir = path.resolve(here, '..', '..');
const repoRoot = path.resolve(packageDir, '..', '..');
const devRoot = process.env.C2P_DSH_DEV_ROOT
  ? path.resolve(process.env.C2P_DSH_DEV_ROOT)
  : path.join(repoRoot, '.dsh-dev');
const runtimeModules = path.join(devRoot, 'runtime', 'node_modules');
const stagingDir = path.join(devRoot, 'home', 'profiles', 'node_modules', '@code2paper', 'dsh-bundle');
const stagingReceiptPath = path.join(devRoot, 'staging.json');
const buildReceiptPath = path.join(packageDir, 'lib', 'build-receipt.json');
const manifest = JSON.parse(readFileSync(path.join(devRoot, 'manifest.json'), 'utf8')) as {
  dsh_version: string;
  upstream_dsh_version?: string;
  source_installation?: string;
};
// A patched candidate keeps the upstream package bytes (and therefore the
// upstream package version) while the manifest's dsh_version is the candidate
// id; the upstream version is the byte-level authority for the frozen tree.
const runtimeVersion = manifest.upstream_dsh_version ?? manifest.dsh_version;

const bundlePackage = JSON.parse(readFileSync(path.join(packageDir, 'package.json'), 'utf8')) as {
  name: string;
  peerDependencies: Record<string, string>;
};

function sha256File(file: string): string {
  return createHash('sha256').update(readFileSync(file)).digest('hex');
}

function requireStaging(): { staged: string; runtimeReal: string } {
  assert.ok(
    existsSync(stagingReceiptPath) && existsSync(path.join(stagingDir, 'package.json')),
    `staged bundle missing at ${stagingDir}; run: python scripts/dsh_dev.py stage`,
  );
  return { staged: stagingDir, runtimeReal: realpathSync(runtimeModules) };
}

test('the bundle is staged at the profile install location with its build receipt', () => {
  const { staged } = requireStaging();
  const stagedPackage = JSON.parse(readFileSync(path.join(staged, 'package.json'), 'utf8')) as { name: string };
  assert.equal(stagedPackage.name, bundlePackage.name);
  const stagingReceipt = JSON.parse(readFileSync(stagingReceiptPath, 'utf8')) as {
    build_receipt_sha256: string;
    bundle: string;
  };
  assert.equal(stagingReceipt.bundle, bundlePackage.name);
  assert.ok(existsSync(buildReceiptPath), 'lib/build-receipt.json missing; run: npm --prefix integrations/dsh run build');
  assert.equal(
    stagingReceipt.build_receipt_sha256,
    sha256File(buildReceiptPath),
    'the bundle was rebuilt after staging; re-run: python scripts/dsh_dev.py stage',
  );
});

test('every declared peer resolves from the staged bundle into the frozen runtime', () => {
  const { staged, runtimeReal } = requireStaging();
  const peers = Object.keys(bundlePackage.peerDependencies);
  assert.ok(peers.length > 0, 'the bundle must declare its DSH/Cordis peers');
  const requireFromStagedBundle = createRequire(path.join(staged, 'package.json'));
  for (const peer of peers) {
    const resolved = realpathSync(requireFromStagedBundle.resolve(peer));
    assert.ok(
      resolved.startsWith(`${runtimeReal}${path.sep}`),
      `${peer} resolved to ${resolved}, outside the frozen runtime ${runtimeReal}`,
    );
  }
});

test('the staged package imports the shared cordis instance without shipping dev files', async () => {
  const { staged, runtimeReal } = requireStaging();
  for (const directory of ['dev', 'tests', 'node_modules', 'src']) {
    assert.ok(!existsSync(path.join(staged, directory)), `${directory} must not be shipped in the runtime bundle`);
  }
  const requireFromStagedBundle = createRequire(path.join(staged, 'package.json'));
  const resolved = realpathSync(requireFromStagedBundle.resolve('@deepseek-ai/cordis'));
  assert.ok(resolved.startsWith(`${runtimeReal}${path.sep}`), `cordis resolved to ${resolved}`);
  const imported = (await import(pathToFileURL(resolved).href)) as { Service: typeof Service };
  assert.equal(typeof imported.Service, 'function');
  assert.equal(imported.Service, Service, 'development and staged imports must share one Cordis instance');
});

test('development dependencies did not modify the frozen runtime', () => {
  const runtimePackage = JSON.parse(
    readFileSync(path.join(runtimeModules, '@deepseek-ai', 'dsh', 'package.json'), 'utf8'),
  ) as { version: string };
  assert.equal(runtimePackage.version, runtimeVersion);
  assert.ok(
    !existsSync(path.join(runtimeModules, 'typescript')),
    'the TypeScript compiler must not be installed into the frozen runtime',
  );
  // A snapshot runtime is compared with the everyday installation it was copied
  // from. An npm candidate has no such installation; its own manifest identity
  // is the byte authority, checked by the launcher.
  const typesRoot = path.join(runtimeModules, '@types');
  if (existsSync(typesRoot) && manifest.source_installation !== undefined) {
    for (const entry of readdirSync(typesRoot)) {
      const runtimeFile = path.join(typesRoot, entry, 'package.json');
      const originalFile = path.join(manifest.source_installation, 'node_modules', '@types', entry, 'package.json');
      assert.ok(existsSync(originalFile), `@types/${entry} is not part of the everyday installation`);
      assert.equal(
        sha256File(runtimeFile),
        sha256File(originalFile),
        `@types/${entry} was modified in the frozen runtime`,
      );
    }
  }
  // Peers are external: the package links them from the frozen runtime instead
  // of vendoring a second Cordis/DSH generation.
  const peerPath = path.join(packageDir, 'node_modules', '@deepseek-ai');
  assert.ok(lstatSync(peerPath).isSymbolicLink(), 'DSH/Cordis peers must stay external');
  assert.equal(realpathSync(peerPath), realpathSync(path.join(runtimeModules, '@deepseek-ai')));
});
