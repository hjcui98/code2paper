#!/usr/bin/env node
/**
 * B02 independent development toolchain driver.
 *
 * The frozen DSH runtime under `.dsh-dev/runtime` is read-only input: this driver
 * never installs into it. The TypeScript compiler and the Node type declarations
 * are locked by `integrations/dsh/package-lock.json` and installed into
 * `integrations/dsh/node_modules`; the DSH/Cordis API packages stay external
 * peers that Node resolves from the host installation at load time.
 *
 * Commands:
 *   install    npm ci from the locked manifest, then verify the toolchain identity
 *   verify     re-verify the installed toolchain against its recorded receipt
 *   typecheck  tsc --noEmit over src/**, tests/** and dev/toolchain/**
 *   build      emit lib/ (when src/** has inputs) and dev/toolchain/build/, then
 *              write lib/build-receipt.json
 *   stage      verify the build, then stage only the runtime package files
 *   test       verify staging, then run discovered source tests (no restaging)
 *   check      typecheck -> build -> stage -> test
 */

import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, lstatSync, readlinkSync, symlinkSync } from 'node:fs';
import { mkdir, readFile, readdir, rename, rm, unlink, writeFile } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { discoverCompatTests } from './compat-tests.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const packageDir = path.resolve(here, '..', '..');
const repoRoot = path.resolve(packageDir, '..', '..');
// The isolated development root. A candidate selects its own root through
// C2P_DSH_DEV_ROOT so its manifest, receipts, npm cache and frozen peers stay
// separate from the default environment; nothing is shared implicitly.
const devRoot = process.env.C2P_DSH_DEV_ROOT
  ? path.resolve(process.env.C2P_DSH_DEV_ROOT)
  : path.join(repoRoot, '.dsh-dev');
const manifestPath = path.join(devRoot, 'manifest.json');
const toolchainReceiptPath = path.join(devRoot, 'toolchain.json');
const lockPath = path.join(packageDir, 'package-lock.json');
const packageJsonPath = path.join(packageDir, 'package.json');
const libDir = path.join(packageDir, 'lib');
const buildReceiptPath = path.join(libDir, 'build-receipt.json');
const probeOutDir = path.join(here, 'build');
const tscPath = path.join(packageDir, 'node_modules', 'typescript', 'bin', 'tsc');
const RECEIPT_SCHEMA = 'c2p-dsh-development-toolchain/1';

function fail(message) {
  process.stderr.write(`toolchain: ${message}\n`);
  process.exit(1);
}

function run(label, command, args, options = {}) {
  process.stdout.write(`toolchain: ${label}: ${command} ${args.join(' ')}\n`);
  const result = spawnSync(command, args, { stdio: 'inherit', ...options });
  if (result.error) fail(`${label} could not start: ${result.error.message}`);
  if (result.status !== 0) fail(`${label} exited with status ${result.status}`);
}

async function readJson(file) {
  return JSON.parse(await readFile(file, 'utf8'));
}

async function sha256File(file) {
  return createHash('sha256').update(await readFile(file)).digest('hex');
}

async function listFiles(root, { skip = new Set() } = {}) {
  const found = [];
  async function walk(dir) {
    const entries = await readdir(dir, { withFileTypes: true });
    for (const entry of entries.sort((a, b) => (a.name < b.name ? -1 : 1))) {
      if (skip.has(entry.name)) continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) await walk(full);
      else if (entry.isFile()) found.push(path.relative(root, full).split(path.sep).join('/'));
    }
  }
  if (!existsSync(root)) return found;
  await walk(root);
  return found.sort();
}

async function digestFiles(root, relPaths) {
  const digests = {};
  for (const rel of relPaths) digests[rel] = await sha256File(path.join(root, rel));
  return digests;
}

function digestOf(value) {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex');
}

function npmInvocation() {
  if (process.env.npm_execpath) return { command: process.execPath, prefix: [process.env.npm_execpath] };
  return { command: 'npm', prefix: [] };
}

function npmEnvironment() {
  // Keep every npm write inside the isolated development root: the everyday npm
  // cache and the frozen runtime are not part of this toolchain.
  return {
    ...launcherEnvironment(),
    npm_config_cache: path.join(devRoot, 'cache', 'npm'),
    npm_config_userconfig: path.join(devRoot, 'config', 'npmrc'),
    npm_config_audit: 'false',
    npm_config_fund: 'false',
    npm_config_update_notifier: 'false',
    npm_config_global: 'false',
    npm_config_prefix: packageDir,
  };
}

const defaultDevRoot = path.join(repoRoot, '.dsh-dev');
const candidateParent = path.join(defaultDevRoot, 'candidates');

/**
 * The selected candidate, or null for the historical default root.
 *
 * `C2P_DSH_DEV_ROOT` and `C2P_DSH_CANDIDATE` must name the same candidate.
 * A root under `candidates/` with no version, or a version whose root is
 * somewhere else, is a mismatch and is refused before any Python child runs.
 */
function selectedCandidate() {
  const named = process.env.C2P_DSH_CANDIDATE;
  const underCandidates = devRoot === candidateParent || devRoot.startsWith(`${candidateParent}${path.sep}`);
  if (!underCandidates && (named === undefined || named === '')) return null;
  if (!underCandidates) {
    fail(`C2P_DSH_CANDIDATE=${named} but C2P_DSH_DEV_ROOT=${devRoot} is not that candidate`);
  }
  const version = path.basename(devRoot);
  if (named === undefined || named === '') {
    fail(`C2P_DSH_DEV_ROOT selects candidate ${version} but C2P_DSH_CANDIDATE is unset`);
  }
  if (named !== version || path.resolve(devRoot) !== path.resolve(candidateParent, named)) {
    fail(`candidate mismatch: C2P_DSH_CANDIDATE=${named} but the development root is ${devRoot}`);
  }
  return named;
}

function launcherEnvironment() {
  const allowed = ['HOME', 'USER', 'LOGNAME', 'LANG', 'LC_ALL', 'TERM', 'TZ'];
  const candidate = selectedCandidate();
  return {
    ...Object.fromEntries(allowed.filter((key) => process.env[key] !== undefined).map((key) => [key, process.env[key]])),
    PATH: `${path.dirname(process.execPath)}:/usr/bin:/bin`,
    PYTHONNOUSERSITE: '1',
    PYTHONDONTWRITEBYTECODE: '1',
    C2P_DSH_DEV_ROOT: devRoot,
    ...(candidate === null ? {} : { C2P_DSH_CANDIDATE: candidate }),
  };
}

function pythonCandidateArgs() {
  const candidate = selectedCandidate();
  return candidate === null ? [] : ['--candidate', candidate];
}

async function requireFrozenManifest() {
  if (!existsSync(manifestPath)) return null;
  return readJson(manifestPath);
}

/**
 * The DSH/Cordis API packages are external peers. During development the
 * package's own `node_modules/@deepseek-ai` is a symlink into the frozen
 * runtime, exactly as the DSH profile links its own `node_modules` — never a
 * vendored copy and never a second Cordis generation.
 */
const peerLinkPath = path.join(packageDir, 'node_modules', '@deepseek-ai');
const frozenPeerRoot = path.join(devRoot, 'runtime', 'node_modules', '@deepseek-ai');

async function linkPeers() {
  if (!existsSync(frozenPeerRoot)) {
    fail(`frozen runtime peers are missing at ${frozenPeerRoot}; run: python scripts/dsh_dev.py setup`);
  }
  if (existsSync(peerLinkPath) || lstatSafe(peerLinkPath)) {
    const stats = lstatSync(peerLinkPath);
    if (!stats.isSymbolicLink()) {
      fail('DSH/Cordis were vendored into integrations/dsh/node_modules; peers must stay external');
    }
    await unlink(peerLinkPath);
  }
  await mkdir(path.dirname(peerLinkPath), { recursive: true });
  symlinkSync(frozenPeerRoot, peerLinkPath, 'dir');
}

function lstatSafe(target) {
  try {
    return lstatSync(target);
  } catch {
    return null;
  }
}

function peerLinkTarget() {
  if (!lstatSafe(peerLinkPath)) return null;
  if (!lstatSync(peerLinkPath).isSymbolicLink()) return 'vendored-directory';
  return readlinkSync(peerLinkPath);
}

async function installedPackageVersion(name) {
  const file = path.join(packageDir, 'node_modules', ...name.split('/'), 'package.json');
  if (!existsSync(file)) return null;
  return (await readJson(file)).version;
}

async function toolchainState({ writeReceipt, root = devRoot, prepared = false }) {
  const manifest = await readJson(path.join(root, "manifest.json"));
  const expectedPeer = path.join(root, "runtime/node_modules/@deepseek-ai");
  const receiptPath = path.join(root, "toolchain.json");
  const declared = await readJson(packageJsonPath);
  if (!existsSync(tscPath)) {
    fail('TypeScript is not installed; run `npm run toolchain:install` in integrations/dsh first');
  }
  const typescript = await installedPackageVersion('typescript');
  const typesNode = await installedPackageVersion('@types/node');
  if (typescript !== declared.devDependencies.typescript) {
    fail(`installed typescript ${typescript} does not match the locked ${declared.devDependencies.typescript}`);
  }
  if (typesNode !== declared.devDependencies['@types/node']) {
    fail(`installed @types/node ${typesNode} does not match the locked ${declared.devDependencies['@types/node']}`);
  }
  const peerLink = prepared ? expectedPeer : peerLinkTarget();
  if (peerLink !== expectedPeer) {
    fail(
      `the DSH/Cordis peer link is ${peerLink ?? 'absent'}; expected a symlink to ${frozenPeerRoot} ` +
        '(run `npm run toolchain:install`)',
    );
  }
  if (manifest && process.version !== manifest.node_version) {
    fail(`Node ${process.version} differs from the frozen runtime Node ${manifest.node_version}`);
  }
  const files = await listFiles(path.join(packageDir, 'node_modules'));
  const digests = await digestFiles(path.join(packageDir, 'node_modules'), files);
  const state = {
    schema_version: RECEIPT_SCHEMA,
    package: declared.name,
    node_version: process.version,
    typescript_version: typescript,
    types_node_version: typesNode,
    lock_sha256: await sha256File(lockPath),
    peer_link_target: peerLink,
    peer_packages_vendored: false,
    frozen_runtime: manifest
      ? {
          dsh_version: manifest.dsh_version,
          runtime_tree_sha256: manifest.runtime_tree_sha256,
          package_lock_sha256: manifest.package_lock_sha256,
          node_version: manifest.node_version,
        }
      : null,
    node_modules_file_count: files.length,
    node_modules_tree_sha256: digestOf(digests),
  };
  if (prepared) return state;
  if (writeReceipt) {
    await mkdir(devRoot, { recursive: true });
    await writeFile(toolchainReceiptPath, `${JSON.stringify(state, null, 2)}\n`);
  } else {
    if (!existsSync(receiptPath)) fail('no toolchain receipt; run `npm run toolchain:install`');
    const recorded = await readJson(receiptPath);
    for (const key of ["schema_version", "package", "node_version", "typescript_version", "types_node_version", "peer_link_target"]) {
      if (recorded[key] !== state[key]) fail(`installed toolchain identity drifted: ${key}`);
    }
    if (JSON.stringify(recorded.frozen_runtime) !== JSON.stringify(state.frozen_runtime)) fail("installed runtime binding drifted");
    if (recorded.node_modules_tree_sha256 !== state.node_modules_tree_sha256) {
      fail('installed toolchain bytes drifted from the recorded receipt; re-run toolchain:install');
    }
    if (recorded.lock_sha256 !== state.lock_sha256) {
      fail('package-lock.json changed since the toolchain was installed; re-run toolchain:install');
    }
  }
  return state;
}

async function install() {
  if (!existsSync(lockPath)) fail('package-lock.json is required for a locked install');
  const npm = npmInvocation();
  run('install', npm.command, [...npm.prefix, 'ci', '--legacy-peer-deps', '--no-audit', '--no-fund', '--ignore-scripts'], {
    cwd: packageDir,
    env: npmEnvironment(),
  });
  // `npm ci` replaces node_modules, so the external peer link is recreated here
  // and re-verified on every later toolchain command.
  await linkPeers();
  const state = await toolchainState({ writeReceipt: true });
  process.stdout.write(
    `toolchain: installed typescript ${state.typescript_version} / @types/node ${state.types_node_version} ` +
      `for Node ${state.node_version}\n`,
  );
}

async function activate() {
  const candidate = selectedCandidate();
  const oldPeer = peerLinkTarget();
  if (!oldPeer || oldPeer === 'vendored-directory') fail('activation requires an existing external peer link');
  const activeRoot = path.resolve(path.dirname(peerLinkPath), oldPeer, '../../..');
  if (activeRoot !== defaultDevRoot && path.dirname(activeRoot) !== candidateParent) fail('existing peer root is outside the development candidates');
  // Verify the installed bytes against the active receipt before inspecting or
  // writing the target. Only install may establish a new installation baseline.
  await toolchainState({ writeReceipt: false, root: activeRoot });
  for (const root of new Set([activeRoot, devRoot])) {
    const id = root === defaultDevRoot ? null : path.basename(root);
    const result = spawnSync('python', [path.join(repoRoot, 'scripts/dsh_dev.py'),
      ...(id ? ['--candidate', id] : []), 'activation-inputs'], {
      cwd: repoRoot, encoding: 'utf8', env: {
        ...launcherEnvironment(), C2P_DSH_DEV_ROOT: root,
        ...(id ? { C2P_DSH_CANDIDATE: id } : { C2P_DSH_CANDIDATE: '' }),
      },
    });
    if (result.error || result.status !== 0) fail(`activation input rejected: ${result.stderr || result.error}`);
  }
  const state = await toolchainState({ writeReceipt: false, prepared: true });
  // An existing target receipt is also a required trust binding, never a new
  // baseline inferred from whatever happens to be installed during activation.
  const targetReceipt = await readJson(toolchainReceiptPath);
  for (const key of Object.keys(state)) {
    if (JSON.stringify(targetReceipt[key]) !== JSON.stringify(state[key])) fail(`target toolchain binding drifted: ${key}`);
  }
  const linkTemp = `${peerLinkPath}.activate-${process.pid}`;
  const receiptTemp = `${toolchainReceiptPath}.activate-${process.pid}`;
  const oldReceipt = await readFile(toolchainReceiptPath);
  let switched = false;
  try {
    symlinkSync(frozenPeerRoot, linkTemp, 'dir');
    await writeFile(receiptTemp, `${JSON.stringify(state, null, 2)}\n`, { flag: 'wx' });
    await rename(linkTemp, peerLinkPath);
    switched = true;
    await rename(receiptTemp, toolchainReceiptPath);
  } catch (error) {
    if (switched) {
      symlinkSync(oldPeer, linkTemp, 'dir');
      await rename(linkTemp, peerLinkPath);
    }
    // The receipt rename is the last operation; failed preparation/commit
    // leaves the original receipt bytes intact.
    if (!oldReceipt.equals(await readFile(toolchainReceiptPath))) throw new Error('activation rollback receipt mismatch');
    throw error;
  } finally {
    await rm(linkTemp, { force: true });
    await rm(receiptTemp, { force: true });
  }
  process.stdout.write(`toolchain: activated candidate=${candidate ?? 'default'} peer=${state.peer_link_target}\n`);
}

async function verify() {
  const state = await toolchainState({ writeReceipt: false });
  process.stdout.write(`${JSON.stringify(state, null, 2)}\n`);
}

async function typecheck() {
  await toolchainState({ writeReceipt: false });
  run('typecheck', process.execPath, [tscPath, '--project', path.join(packageDir, 'tsconfig.json')], {
    cwd: packageDir,
  });
}

async function build() {
  await toolchainState({ writeReceipt: false });
  const srcRoot = path.join(packageDir, 'src');
  const srcInputs = (await listFiles(srcRoot)).filter((rel) => rel.endsWith('.ts'));
  await rm(libDir, { recursive: true, force: true });
  await rm(probeOutDir, { recursive: true, force: true });
  await mkdir(libDir, { recursive: true });

  if (srcInputs.length > 0) {
    run('build:src', process.execPath, [tscPath, '--project', path.join(here, 'tsconfig.build.json')], {
      cwd: packageDir,
    });
  } else {
    process.stdout.write('toolchain: build:src skipped: src/**/*.ts is absent (bundle entry not implemented yet)\n');
  }
  run('build:probe', process.execPath, [tscPath, '--project', path.join(here, 'tsconfig.probe.json')], {
    cwd: packageDir,
  });

  const declared = await readJson(packageJsonPath);
  const manifest = await requireFrozenManifest();
  const outputs = {
    ...Object.fromEntries(
      Object.entries(
        await digestFiles(libDir, (await listFiles(libDir)).filter((rel) => rel !== 'build-receipt.json')),
      ).map(([rel, digest]) => [`lib/${rel}`, digest]),
    ),
    ...Object.fromEntries(
      Object.entries(await digestFiles(probeOutDir, await listFiles(probeOutDir))).map(([rel, digest]) => [
        `dev/toolchain/build/${rel}`,
        digest,
      ]),
    ),
  };
  const receipt = {
    schema_version: RECEIPT_SCHEMA,
    package: declared.name,
    src_present: srcInputs.length > 0,
    src_inputs: await digestFiles(packageDir, srcInputs.map((rel) => `src/${rel}`)),
    asset_inputs: await digestFiles(packageDir, [
      ...(existsSync(path.join(packageDir, 'cordis.patch.yml')) ? ['cordis.patch.yml'] : []),
      ...(await listFiles(path.join(packageDir, 'presets'))).map((rel) => `presets/${rel}`),
    ]),
    config_inputs: {
      'package.json': await sha256File(packageJsonPath),
      'tsconfig.json': await sha256File(path.join(packageDir, 'tsconfig.json')),
      'dev/toolchain/tsconfig.build.json': await sha256File(path.join(here, 'tsconfig.build.json')),
      'dev/toolchain/tsconfig.probe.json': await sha256File(path.join(here, 'tsconfig.probe.json')),
      'dev/toolchain/peer-probe.ts': await sha256File(path.join(here, 'peer-probe.ts')),
      'dev/toolchain/toolchain.mjs': await sha256File(path.join(here, 'toolchain.mjs')),
    },
    outputs,
    outputs_digest: digestOf(outputs),
    entry_present: existsSync(path.join(libDir, 'index.js')),
    patch_present: existsSync(path.join(packageDir, 'cordis.patch.yml')),
    node_version: process.version,
    typescript_version: await installedPackageVersion('typescript'),
    frozen_runtime: manifest
      ? {
          dsh_version: manifest.dsh_version,
          runtime_tree_sha256: manifest.runtime_tree_sha256,
          package_lock_sha256: manifest.package_lock_sha256,
        }
      : null,
  };
  await writeFile(buildReceiptPath, `${JSON.stringify(receipt, null, 2)}\n`);
  process.stdout.write(
    `toolchain: build complete; src_present=${receipt.src_present} entry_present=${receipt.entry_present} ` +
      `outputs=${Object.keys(outputs).length} outputs_digest=${receipt.outputs_digest}\n`,
  );
}

function stage({ checkOnly = false } = {}) {
  const candidate = selectedCandidate();
  process.stdout.write(
    `toolchain: ${checkOnly ? 'stage:verify' : 'stage'} candidate=${candidate ?? 'default'} root=${devRoot}\n`,
  );
  run(checkOnly ? 'stage:verify' : 'stage', 'python', [
    path.join(repoRoot, 'scripts', 'dsh_dev.py'),
    ...pythonCandidateArgs(),
    'stage',
    ...(checkOnly ? ['--check'] : []),
  ], { cwd: repoRoot, env: launcherEnvironment() });
}

async function test() {
  await toolchainState({ writeReceipt: false });
  stage({ checkOnly: true });
  const files = await discoverCompatTests(packageDir);
  if (files.length === 0) fail('no compatibility test files were discovered');
  const candidate = selectedCandidate();
  process.stdout.write(`toolchain: test candidate=${candidate ?? 'default'} root=${devRoot} files=${String(files.length)}\n`);
  // The launcher creates and narrowly binds this fresh directory. Actual Host
  // subprocess tests must retain their artifacts outside its private /tmp.
  const outputRoot=path.join(os.tmpdir(),`c2p-dsh-compat-${randomUUID()}`);
  process.stdout.write(`toolchain: test output=${outputRoot}\n`);
  run('test:compat', 'python', [
    path.join(repoRoot, 'scripts', 'dsh_dev.py'),
    ...pythonCandidateArgs(),
    'test', '--output-root', outputRoot, '--report-path', path.join(outputRoot,'node-events.jsonl'), '--', ...files,
  ], {
    cwd: repoRoot, env: launcherEnvironment(),
  });
}

async function check() {
  await typecheck();
  await build();
  stage();
  await test();
}

const command = process.argv[2];
const commands = { install, verify, typecheck, build, stage, test, check, activate };
if (!(command in commands)) {
  fail(`expected one of ${Object.keys(commands).join(', ')}`);
}
await commands[command]();
