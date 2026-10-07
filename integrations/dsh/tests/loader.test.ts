/**
 * H01: real frozen Loader/roster/Agent/ToolRuntime, without model turns.
 *
 * Deployment inputs are read-only: the real profile manifest and patch layers,
 * staged bundle and preset root are consumed unchanged. The profile root's exact
 * bytes are copied into this run's private config so Loader persistence cannot
 * overwrite the shared profile. Bare module names resolve through private links
 * to the existing staged bundle and frozen peers; no dependency is copied.
 *
 * Negative/drift presets and packages belong to a separate real host whose only
 * extra overlay points the roster at this run's private fixture root. Neither
 * normal cleanup nor recovery deletes a shared namespace or staging directory.
 */

import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import {
  existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readdirSync,
  readlinkSync, rmSync, symlinkSync, writeFileSync,
} from 'node:fs';
import { connect } from 'node:net';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { boot, loadOverlayPatches, loadProfileDirectory } from '@deepseek-ai/dsh-app-boot';
import { provideCmdline } from '@deepseek-ai/dsh-cmdline';
import { livePresetMounts, standingMountFor } from '@deepseek-ai/dsh-agent-preset-registry';
import { brandString } from '@deepseek-ai/dsh-brand';
import { scopeOf } from '@deepseek-ai/dsh-scope';
import type { AgentHandle } from '@deepseek-ai/dsh-agent';
import type { Context } from '@deepseek-ai/cordis';
import type { ToolCallId } from '@deepseek-ai/dsh-llm';
import type { SessionId } from '@deepseek-ai/dsh-session';

const packageDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
// The launcher decides which development root is active (default or an
// isolated candidate) and exports it; the guard below then compares the
// running environment against that same root instead of a hardcoded one.
const devRoot = process.env.C2P_DSH_DEV_ROOT
  ? path.resolve(process.env.C2P_DSH_DEV_ROOT)
  : path.resolve(packageDir, '../../.dsh-dev');
const home = path.join(devRoot, 'home');
const runRoot = process.env.C2P_DSH_RUN_ROOT ?? path.join(devRoot, 'run');
const runtimeRoot = path.join(devRoot, 'runtime');
const installAnchor = path.join(runtimeRoot, 'node_modules/@deepseek-ai/dsh/package.json');
const profileDir = path.join(home, 'profiles/code2paper-dev-compat');
const bundleName = '@code2paper/dsh-bundle';
const presetId = 'code2paper';
const probeTool = 'c2p_bridge_probe';
const stagedBundle = path.join(home, 'profiles/node_modules', bundleName);
const stagedPresets = path.join(stagedBundle, 'presets');
const stagingReceipt = path.join(devRoot, 'staging.json');
const policyFile = path.join(packageDir, 'dev/offline.patch.yml');
const runId = `${String(process.pid)}-${Date.now().toString(36)}`;
/** Marker that arms {@link injectPostBootFailure} for one boot; absent in normal runs. */
const faultMarker = path.join(runRoot, 'h01-fault-after-boot.flag');

interface RootModule {
  readonly name: string;
  readonly inject: readonly string[];
  readonly Config: unknown;
  mountCode2PaperPreset(caller: Context, agentCtx: Context, id?: string): Promise<unknown>;
  applyChildComposition(caller: Context, agentCtx: Context, parentCtx: Context): string | undefined;
}

interface BridgeApi {
  readonly presetId: string;
  readonly presetRoot: string;
  readonly runRoot: string;
  readonly hostGeneration: number;
  composedPreset(agentCtx: Context): string;
  read(id: string): { readonly notes: readonly string[] };
}

interface LoaderEntryLike {
  readonly options: { readonly name?: string };
  readonly fiber?: {
    readonly inject?: Record<string, unknown>;
    readonly runtime?: { readonly name?: string; readonly Config?: unknown };
  };
}

interface Host {
  readonly ctx: Context;
  readonly bridge: BridgeApi;
  readonly createdAgents: Set<string>;
  readonly createdSessions: Set<string>;
  readonly modelCalls: { count: number };
}

let privateRoot: string | undefined;
let fixturePresets: string;
let rootModule: RootModule;
let deployment: Host;
let fixture: Host;
let protectedBefore: ReturnType<typeof protectedInputs> | undefined;
let callSequence = 0;
const hosts: Host[] = [];
const handles = new Map<AgentHandle, Host>();
/** Verbatim refusal reason of every rejected preset, for the run's evidence. */
const refusals: string[] = [];

function sessionId(label: string): SessionId {
  return brandString<SessionId>(`h01-${label}-${runId}`);
}

/** Fingerprint bytes, directories and link targets, without traversing links. */
function treeSnapshot(root: string, includeWriteMetadata = false): Record<string, string> {
  const entries: Record<string, string> = {};
  if (includeWriteMetadata) {
    const stat = lstatSync(root, { bigint: true });
    entries['.'] = `directory|inode:${String(stat.ino)}|mtime_ns:${String(stat.mtimeNs)}`;
  }
  function walk(dir: string): void {
    for (const name of readdirSync(dir).sort()) {
      const file = path.join(dir, name);
      const relative = path.relative(root, file);
      const stat = lstatSync(file, { bigint: true });
      if (stat.isSymbolicLink()) entries[relative] = `link:${readlinkSync(file)}`;
      else if (stat.isDirectory()) {
        entries[relative] = 'directory';
        walk(file);
      } else entries[relative] = createHash('sha256').update(readFileSync(file)).digest('hex');
      if (includeWriteMetadata) {
        entries[relative] += `|inode:${String(stat.ino)}|mtime_ns:${String(stat.mtimeNs)}`;
      }
    }
  }
  walk(root);
  return entries;
}

/** Top-level view of the shared profile module fallback: names and link targets. */
function moduleFallbackSnapshot(): Record<string, string> {
  const root = path.join(home, 'profiles/node_modules');
  const entries: Record<string, string> = {};
  for (const name of readdirSync(root).sort()) {
    const file = path.join(root, name);
    const stat = lstatSync(file);
    if (stat.isSymbolicLink()) entries[name] = `link:${readlinkSync(file)}`;
    else if (stat.isDirectory()) entries[name] = 'directory';
    else entries[name] = `file:${createHash('sha256').update(readFileSync(file)).digest('hex')}`;
  }
  return entries;
}

function protectedInputs() {
  return {
    profile: treeSnapshot(profileDir, true),
    profileModules: moduleFallbackSnapshot(),
    staging: treeSnapshot(stagedBundle),
    receipt: readFileSync(stagingReceipt, 'utf8'),
  };
}

function loaderEntry(host: Host, packageName: string): LoaderEntryLike | undefined {
  const loader = host.ctx.get('loader') as unknown as { entries(): Iterable<LoaderEntryLike> };
  return [...loader.entries()].find((entry) => entry.options.name === packageName);
}

function toolNames(host: Host, agentCtx: Context): string[] {
  return host.ctx.tools.schemas(scopeOf(agentCtx)).map((schema) => schema.name);
}

async function createRootAgent(host: Host, label: string, preset: string = presetId): Promise<AgentHandle> {
  const handle = await host.ctx.agents.create({
    sessionId: sessionId(label),
    meta: { cwd: path.join(privateRoot!, 'workspace'), agentPreset: 'untrusted-metadata-is-not-composition' },
    setup: async (agentCtx) => {
      await rootModule.mountCode2PaperPreset(host.ctx, agentCtx, preset);
      assert.ok(host.ctx.tools.get(probeTool, scopeOf(agentCtx)), 'tool must exist before setup returns');
    },
  });
  handles.set(handle, host);
  return handle;
}

async function executeProbe(host: Host, handle: AgentHandle, note = '') {
  const result = await host.ctx.tools.execute({
    callId: brandString<ToolCallId>(`h01-call-${runId}-${String(++callSequence)}`),
    name: probeTool,
    arguments: { note },
    agent: handle.agent,
    signal: new AbortController().signal,
  });
  assert.equal(result.isError, false, JSON.stringify(result));
  assert.ok(!result.isError);
  assert.ok(result.content.some((block) => block.type === 'text' && block.text.includes('Code2Paper bridge:')));
  return result.value;
}

async function disposeHandle(handle: AgentHandle, host: Host): Promise<void> {
  await handle.dispose();
  handles.delete(handle);
  assert.equal(host.ctx.agents.get(handle.agent.id), undefined, 'disposed agent must leave the live registry');
  assert.equal(host.ctx.sessions.get(handle.agent.session.id), undefined, 'disposed session must leave the live store');
}

function writeFixture(name: string, source: string): void {
  const dir = path.join(privateRoot!, 'node_modules/@h01-fixtures', name);
  mkdirSync(dir, { recursive: true });
  writeFileSync(path.join(dir, 'package.json'), `${JSON.stringify({
    name: `@h01-fixtures/${name}`, version: '0.0.0', type: 'module', exports: { '.': './index.mjs' },
  })}\n`);
  writeFileSync(path.join(dir, 'index.mjs'), source);
}

/**
 * Render a fixture preset the 0.2 way.
 *
 * 0.1.5 scanned `presets/<id>/agent.cordis.yml` through the registry's `roots`
 * config. 0.2 has no scan model: a preset exists only once declared, so the
 * fixture declares one `@deepseek-ai/dsh-agent-preset` row whose `plugins` are
 * the rows under test. `pluginRows` stays a plain YAML entry list, so the
 * negative fixtures keep generating exactly the rows they mean to test.
 */
/**
 * Declare a fixture preset the 0.2 way.
 *
 * 0.1.5 discovered presets lazily by scanning `presets/<id>/agent.cordis.yml`
 * through the registry's `roots` config, so a fixture file written after boot
 * was still found at mount time. 0.2 has no scan model: a preset exists only
 * once it is declared, so fixtures register straight through the registry's
 * public API. Rows are plain plugin objects here, exactly what the declaration
 * carries in `config.plugins`.
 */
const presetDisposers = new Map<string, () => Promise<void>>();

async function writePreset(id: string, plugins: readonly unknown[]): Promise<void> {
  // 0.2 refuses a duplicate declaration, and 0.1.5's scan model silently picked
  // up an edited file. Re-declaring therefore means releasing the previous
  // registration first, which is also what makes the edit a real new generation.
  const previous = presetDisposers.get(id);
  if (previous !== undefined) await previous();
  presetDisposers.set(id, await fixture.ctx.agentPresets.register({ id, name: id, plugins: plugins as never }));
}

function toolsRows(): readonly unknown[] {
  return [{ id: 'code2paper-tools', name: `${bundleName}/tools` }];
}

/** Real setup failure must not publish an id or leave a failed mount/service. */
async function assertMountFailure(preset: string, expected: RegExp): Promise<void> {
  const host = fixture;
  const id = sessionId(`negative-${preset}`);
  const agentsBefore = host.ctx.agents.list().map((agent) => agent.id);
  const sessionsBefore = host.ctx.sessions.list().map((session) => session.id);
  const mountsBefore = livePresetMounts(host.ctx.fiber).map((mount) => mount.fiber);
  const bridgeFiber = loaderEntry(host, bundleName)?.fiber;
  const generation = host.bridge.hostGeneration;
  let observed = '';
  await assert.rejects(host.ctx.agents.create({
    sessionId: id,
    meta: { cwd: path.join(privateRoot!, 'workspace') },
    setup: async (agentCtx) => { await rootModule.mountCode2PaperPreset(host.ctx, agentCtx, preset); },
  }).then((handle) => {
    handles.set(handle, host); // retain cleanup ownership even if an expected failure wrongly succeeds
    return handle;
  }), (error: Error) => {
    observed = error.message;
    return expected.test(observed);
  });
  refusals.push(`${preset}: ${observed.split('\n')[0]!}`);
  assert.equal(host.ctx.agents.get(id), undefined);
  assert.equal(host.ctx.sessions.get(id), undefined);
  assert.equal(host.createdAgents.has(id), false, 'failed setup must not announce an agent');
  assert.equal(host.createdSessions.has(id), false, 'failed setup must not announce a session');
  assert.deepEqual(host.ctx.agents.list().map((agent) => agent.id), agentsBefore);
  assert.deepEqual(host.ctx.sessions.list().map((session) => session.id), sessionsBefore);
  assert.deepEqual(livePresetMounts(host.ctx.fiber).map((mount) => mount.fiber), mountsBefore);
  assert.equal(host.ctx.get('h01LeakedService'), undefined);
  // Cordis returns caller-traced service proxies: compare composition identity,
  // not two proxy objects. Durable failed-session audit records are not leaks.
  assert.equal(loaderEntry(host, bundleName)?.fiber, bridgeFiber);
  assert.equal((host.ctx.get('code2paperBridge') as unknown as BridgeApi).hostGeneration, generation);
}

async function bootHost(label: string, overlay?: string): Promise<Host> {
  // Unlike loadProfile(), this API only reads an already initialized directory;
  // it neither initializes/normalizes the shared profile nor heals module links.
  const profile = loadProfileDirectory('h01-loader-test', profileDir, installAnchor);
  assert.deepEqual(profile.layers.map((layer) => layer.packageName), [
    '@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app', bundleName,
  ]);
  const configDir = path.join(privateRoot!, label);
  mkdirSync(configDir, { recursive: true });
  const config = path.join(configDir, 'cordis.yml');
  const rootBytes = readFileSync(path.join(profileDir, 'cordis.yml'));
  writeFileSync(config, rootBytes);
  assert.deepEqual(readFileSync(config), rootBytes);
  const patches = [
    ...profile.layers.flatMap((layer) => layer.patches), ...profile.patches,
    ...loadOverlayPatches('h01-loader-test', policyFile),
    ...(overlay === undefined ? [] : loadOverlayPatches('h01-loader-test', overlay)),
  ];
  const createdAgents = new Set<string>();
  const createdSessions = new Set<string>();
  const modelCalls = { count: 0 };
  const ctx = await boot('h01-loader-test', config, patches, (hostCtx) => {
    provideCmdline(hostCtx, { args: ['--host', '127.0.0.1', '--port', '0', '--no-open'], exit: () => {} });
    hostCtx.on('agent/created', ({ agent }) => { createdAgents.add(agent.id);
      return undefined; });
    hostCtx.on('session/created', (session) => { createdSessions.add(session.id); });
    hostCtx.on('llm/stream', () => {
      modelCalls.count += 1;
      throw new Error('H01 must not issue a model request');
    });
  });
  // Cleanup responsibility is established the moment the tree exists: `after()`
  // must release this context — its services and its bound port — even when a
  // later read or assertion in this function fails. Registering the host only
  // after the checks below would leak a successfully booted host on such a
  // failure and could keep the test process alive.
  const host = {
    ctx,
    bridge: ctx.get('code2paperBridge') as unknown as BridgeApi,
    createdAgents,
    createdSessions,
    modelCalls,
  };
  hosts.push(host);
  assert.ok(host.bridge, 'real bundle must publish its host service');
  injectPostBootFailure(label, ctx);
  // The boot itself must consume the shared profile read-only: no init, no heal,
  // no profile write. Checked here as well as at teardown so a write is attributed
  // to the boot rather than to a later phase.
  assert.deepEqual(protectedInputs().profile, protectedBefore?.profile, 'booting must not write into the shared profile');
  assert.deepEqual(
    protectedInputs().profileModules,
    protectedBefore?.profileModules,
    'booting must not touch the shared profile module fallback',
  );
  return host;
}

/**
 * One-shot fault injection for the cleanup path above. A marker file in the run
 * root makes the next boot fail exactly where a real post-boot read/assertion
 * would, after the host is registered but before the protection checks. The
 * teardown then has to prove the failure still released the context and its port.
 *
 * Inert unless the marker exists, and the marker is consumed on first use:
 *
 *   printf '{}' > .dsh-dev/run/h01-fault-after-boot.flag
 *   npm --prefix integrations/dsh run test:compat   # expected: non-zero exit
 */
function injectPostBootFailure(label: string, hostCtx: Context): void {
  if (!existsSync(faultMarker)) return;
  const port = (hostCtx.get('webServer') as { port?: number } | undefined)?.port;
  writeFileSync(path.join(privateRoot!, 'fault-port.txt'), `${String(port)}\n`);
  rmSync(faultMarker, { force: true });
  assert.fail(`injected post-boot failure for ${label} (cleanup-path verification)`);
}

/** Teardown proof for {@link injectPostBootFailure}: the bound port is gone. */
async function assertInjectedPortReleased(errors: unknown[]): Promise<void> {
  const portFile = path.join(privateRoot!, 'fault-port.txt');
  if (!existsSync(portFile)) return;
  try {
    const port = Number(readFileSync(portFile, 'utf8').trim());
    rmSync(portFile, { force: true });
    const released = await new Promise<boolean>((resolve) => {
      const socket = connect(port, '127.0.0.1');
      socket.once('connect', () => { socket.destroy(); resolve(false); });
      socket.once('error', () => { socket.destroy(); resolve(true); });
    });
    process.stdout.write(`H01 fault injection: port ${String(port)} released after teardown: ${String(released)}\n`);
    assert.ok(released, 'a post-boot failure must still release the bound port');
  } catch (error) {
    errors.push(error);
  }
}

before(async () => {
  assert.equal(process.env.DSH_HOME, home, 'use the isolated launcher');
  assert.ok(existsSync(installAnchor));
  assert.ok(existsSync(path.join(stagedBundle, 'lib/index.js')), 'build and stage first');
  protectedBefore = protectedInputs();
  privateRoot = mkdtempSync(path.join(runRoot, 'h01-loader-'));
  mkdirSync(path.join(privateRoot, 'workspace'));
  const modules = path.join(privateRoot, 'node_modules');
  mkdirSync(path.join(modules, '@code2paper'), { recursive: true });
  symlinkSync(path.join(runtimeRoot, 'node_modules/@deepseek-ai'), path.join(modules, '@deepseek-ai'), 'dir');
  symlinkSync(stagedBundle, path.join(modules, '@code2paper/dsh-bundle'), 'dir');
  rootModule = await import(pathToFileURL(path.join(stagedBundle, 'lib/index.js')).href) as RootModule;
  deployment = await bootHost('positive');

  fixturePresets = path.join(privateRoot, 'fixture-presets');
  mkdirSync(fixturePresets, { recursive: true });
  const overlay = path.join(privateRoot, 'fixture.patch.yml');
  writeFileSync(overlay, [
    '- id: agent-preset-registry',
    '  config:',
    `    default: ${presetId}`,
    '- id: code2paper-bridge',
    '  config:',
    `    presetId: ${presetId}`,
    `    presetRoot: ${fixturePresets}`,
    `    runRoot: ${privateRoot}`,
    '',
  ].join('\n'));
  // `presetId` itself comes from the bundle's own declaration patch, which the
  // fixture host loads like any other profile; only the extra fixture presets
  // below are registered here.
  fixture = await bootHost('negative', overlay);
});

after(async () => {
  const errors: unknown[] = [];
  for (const [handle, host] of [...handles].reverse()) {
    try { await disposeHandle(handle, host); } catch (error) { errors.push(error); }
  }
  for (const host of [...hosts].reverse()) {
    try {
      await host.ctx.fiber.dispose();
      assert.deepEqual(livePresetMounts(host.ctx.fiber), [], 'root disposal must release its standing mounts');
      assert.equal(host.ctx.get('code2paperBridge'), undefined, 'root disposal must unpublish the bridge');
      assert.equal(host.modelCalls.count, 0);
    } catch (error) { errors.push(error); }
  }
  try {
    if (protectedBefore !== undefined) assert.deepEqual(protectedInputs(), protectedBefore,
      'profile, staged files/link targets and staging receipt must remain byte-identical');
  } catch (error) { errors.push(error); }
  // Runs before the private root is removed, so an injected post-boot failure
  // still proves its port was released by the disposal above.
  if (privateRoot !== undefined) await assertInjectedPortReleased(errors);
  try {
    if (privateRoot !== undefined) rmSync(privateRoot, { recursive: true, force: true });
  } catch (error) { errors.push(error); }
  if (errors.length > 0) throw new AggregateError(errors, 'H01 teardown/preservation failed');
});

test('real deployment patch and roster load from unchanged profile/staging inputs', async () => {
  const { ctx, bridge } = deployment;
  assert.equal(bridge.presetId, presetId);
  assert.equal(bridge.presetRoot, stagedPresets);
  assert.equal(bridge.runRoot, runRoot);
  // 0.2 replaced the scanned roster (roots/trust/path) with declarative
  // registration: the registry exposes roster metadata only, so the roster is
  // asserted through its real surface instead of the removed scan fields.
  const presets = await ctx.agentPresets.list();
  // The web-app bundle declares its own shipped preset alongside ours, so the
  // roster is asserted by membership on the real surface, not by exclusivity.
  assert.deepEqual(presets.filter((preset) => preset.id === presetId).map((preset) => preset.broken), [undefined]);
  assert.equal((await ctx.agentPresets.resolve()).id, presetId);
  assert.equal(ctx.tools.get(probeTool, undefined), undefined);
});

test('named exports preserve name/inject/Config on the actual Loader rows', async () => {
  const tools = await import(pathToFileURL(path.join(stagedBundle, 'lib/task-tools.js')).href) as {
    readonly name: string; readonly inject: readonly string[]; readonly PROBE_TOOL: string; readonly apply: unknown;
  };
  assert.ok(!('default' in rootModule));
  assert.ok(!('default' in tools));
  assert.equal(rootModule.name, 'code2paper-bridge');
  assert.deepEqual(rootModule.inject, ['agentPresets']);
  assert.ok(rootModule.Config);
  assert.equal(tools.name, 'code2paper-tools');
  assert.deepEqual(tools.inject, ['tools', 'code2paperBridge']);
  assert.equal(tools.PROBE_TOOL, probeTool);
  assert.equal(typeof tools.apply, 'function');
  const rootRow = loaderEntry(deployment, bundleName)?.fiber;
  assert.ok(rootRow?.runtime);
  assert.equal(rootRow?.runtime?.name, 'code2paper-bridge');
  assert.deepEqual(Object.keys(rootRow.inject ?? {}), ['agentPresets']);
  assert.ok(rootRow.runtime.Config);
});

test('root setup awaits composition and the public ToolRuntime executes/renders its scoped tool', async () => {
  const parent = await createRootAgent(deployment, 'parent');
  const mount = standingMountFor(parent.agent.ctx);
  assert.equal(mount?.presetId, presetId);
  const presetRow = [...mount!.tree.entries()].find((entry) => entry.options.name === `${bundleName}/tools`);
  assert.equal(presetRow?.fiber?.runtime?.name, 'code2paper-tools');
  assert.deepEqual(Object.keys(presetRow?.fiber?.inject ?? {}).sort(), ['code2paperBridge', 'tools']);
  assert.deepEqual(await executeProbe(deployment, parent, 'first'), {
    sessionId: parent.agent.session.id, presetId, hostGeneration: deployment.bridge.hostGeneration,
    noteCount: 1, notes: ['first'],
  });
});

test('sibling ledgers stay separate and the public ToolRuntime rejects a non-joined agent', async () => {
  const sibling = await createRootAgent(deployment, 'sibling');
  const plain = await deployment.ctx.agents.create({
    sessionId: sessionId('plain'), meta: { cwd: path.join(privateRoot!, 'workspace') }, setup: () => {},
  });
  handles.set(plain, deployment);
  assert.ok(toolNames(deployment, sibling.agent.ctx).includes(probeTool));
  assert.equal(deployment.ctx.tools.get(probeTool, scopeOf(plain.agent.ctx)), undefined);
  const rejected = await deployment.ctx.tools.execute({
    callId: brandString<ToolCallId>(`h01-plain-${runId}`), name: probeTool, arguments: { note: 'must not append' },
    agent: plain.agent, signal: new AbortController().signal,
  });
  assert.ok(rejected.isError);
  assert.equal(rejected.error.info?.code, 'UNKNOWN_TOOL');
  assert.throws(() => deployment.bridge.composedPreset(plain.agent.ctx), /requires an agent joined to a preset/);
  assert.deepEqual(await executeProbe(deployment, sibling, 'sibling-only'), {
    sessionId: sibling.agent.session.id, presetId, hostGeneration: deployment.bridge.hostGeneration,
    noteCount: 1, notes: ['sibling-only'],
  });
  assert.deepEqual(deployment.bridge.read(sessionId('plain')).notes, []);
  assert.deepEqual(deployment.bridge.read(sessionId('parent')).notes, ['first']);
});

test('override and child report their actual preset and retain the parent standing generation after an edit', async () => {
  const override = 'h01-drift';
  await writePreset(override, toolsRows());
  const parent = await createRootAgent(fixture, 'drift-parent', override);
  const composed = standingMountFor(parent.agent.ctx);
  assert.ok(composed);
  assert.deepEqual(await executeProbe(fixture, parent, 'override-parent'), {
    sessionId: parent.agent.session.id, presetId: override, hostGeneration: fixture.bridge.hostGeneration,
    noteCount: 1, notes: ['override-parent'],
  });
  await writePreset(override, toolsRows());
  const child = await fixture.ctx.agents.create({
    sessionId: sessionId('drift-child'), parentAgent: parent.agent,
    meta: { cwd: path.join(privateRoot!, 'workspace'), agentPreset: 'forged-metadata' },
    setup: (childCtx) => {
      assert.equal(rootModule.applyChildComposition(fixture.ctx, childCtx, parent.agent.ctx), override);
    },
  });
  handles.set(child, fixture);
  assert.equal(standingMountFor(child.agent.ctx)?.key, composed.key);
  assert.equal(standingMountFor(child.agent.ctx)?.fiber, composed.fiber);
  const next = await createRootAgent(fixture, 'drift-next', override);
  assert.notEqual(standingMountFor(next.agent.ctx)?.key, composed.key);
  assert.equal(standingMountFor(parent.agent.ctx)?.key, composed.key);
  assert.equal(standingMountFor(child.agent.ctx)?.key, composed.key);
  assert.deepEqual(await executeProbe(fixture, child, 'child-only'), {
    sessionId: child.agent.session.id, presetId: override, hostGeneration: fixture.bridge.hostGeneration,
    noteCount: 1, notes: ['child-only'],
  });
  assert.deepEqual(fixture.bridge.read(parent.agent.session.id).notes, ['override-parent']);
});

test('missing package/inject, bad Config and one metadata-losing default export fail without live residue', async () => {
  writeFixture('missing-inject', "export const name = 'h01-missing-inject';\nexport const inject = ['h01NeverProvidedService'];\nexport function apply() {}\n");
  writeFixture('bad-config', "import z from '@deepseek-ai/schemastery';\nexport const name = 'h01-bad-config';\nexport const Config = z.object({ requiredField: z.string().required() });\nexport function apply() {}\n");
  writeFixture('default-only', "export const name = 'h01-default-only';\nexport const inject = ['h01NeverProvidedService'];\nexport default function apply(ctx) { ctx.h01NeverProvidedService.register(); }\n");
  await writePreset('h01-missing-package', [{ id: 'missing-package', name: '@h01-fixtures/does-not-exist' }]);
  await writePreset('h01-missing-inject', [{ id: 'missing-inject', name: '@h01-fixtures/missing-inject' }]);
  await writePreset('h01-bad-config', [{ id: 'bad-config', name: '@h01-fixtures/bad-config', config: { wrongField: true } }]);
  await writePreset('h01-bundle-bad-config', [{ id: 'bundle-bad-config', name: bundleName, config: { presetId: 'broken' } }]);
  await writePreset('h01-default-only', [{ id: 'default-only', name: '@h01-fixtures/default-only' }]);
  await assertMountFailure('h01-missing-package', /missing-package \(@h01-fixtures\/does-not-exist\): never started/);
  await assertMountFailure('h01-missing-inject', /waiting for h01NeverProvidedService/);
  await assertMountFailure('h01-bad-config', /invalid config/);
  await assertMountFailure('h01-bundle-bad-config', /invalid config/);
  assert.throws(() => (rootModule.Config as (value: unknown) => unknown)({ presetId: 'x' }));
  // This specifically proves lost inject metadata; it is not a claim that the
  // Loader rejects every module whose default export drops name or Config.
  await assertMountFailure('h01-default-only', /without inject/);
});

test('a new process-global service is rejected and fully removed after failed preset creation', async () => {
  // An agent that joined a working preset BEFORE the refusal: the original host
  // service and this agent must both keep working afterwards.
  const keeper = await createRootAgent(fixture, 'leak-keeper');
  const prior = await executeProbe(fixture, keeper, 'keep-after-leak');
  const priorMount = standingMountFor(keeper.agent.ctx);
  writeFixture('leaked-service', "export const name = 'h01-leaked-service';\nexport function apply(ctx) { ctx.provide('h01LeakedService', { hello: true }); }\n");
  await writePreset('h01-leaked-service', [{ id: 'leaked-service', name: '@h01-fixtures/leaked-service' }]);
  await assertMountFailure('h01-leaked-service', /Preset services require isolate realms: h01LeakedService/);
  assert.equal(fixture.ctx.get('h01LeakedService'), undefined, 'the out-of-domain service must be gone, not shadowed');
  assert.equal(fixture.ctx.agents.get(keeper.agent.id), keeper.agent);
  assert.equal(standingMountFor(keeper.agent.ctx)?.fiber, priorMount?.fiber);
  assert.deepEqual(await executeProbe(fixture, keeper), prior, 'the pre-existing agent must still run its tool');
});

test('duplicate host service registration rejects without replacing the bridge or harming an existing agent', async () => {
  const keeper = await createRootAgent(fixture, 'duplicate-keeper');
  const prior = await executeProbe(fixture, keeper, 'keep-this-ledger');
  const priorMount = standingMountFor(keeper.agent.ctx);
  writeFixture('duplicate-service', "export const name = 'h01-duplicate-service';\nexport function apply(ctx) { ctx.provide('code2paperBridge', { replaced: true }); }\n");
  await writePreset('h01-duplicate-service', [{ id: 'duplicate-service', name: '@h01-fixtures/duplicate-service' }]);
  await assertMountFailure('h01-duplicate-service', /service "code2paperBridge" has been registered/);
  assert.equal(fixture.ctx.agents.get(keeper.agent.id), keeper.agent);
  assert.equal(standingMountFor(keeper.agent.ctx)?.fiber, priorMount?.fiber);
  assert.deepEqual(await executeProbe(fixture, keeper), prior);
});

test('agent disposal removes its live state but preserves the shared standing composition', async () => {
  const handle = await createRootAgent(deployment, 'dispose-me');
  const mount = standingMountFor(handle.agent.ctx);
  assert.ok(mount);
  await disposeHandle(handle, deployment);
  assert.ok(livePresetMounts(deployment.ctx.fiber).some((live) => live.fiber === mount.fiber));
  const survivor = await createRootAgent(deployment, 'survivor');
  assert.equal(standingMountFor(survivor.agent.ctx)?.fiber, mount.fiber);
  assert.deepEqual(await executeProbe(deployment, survivor), {
    sessionId: survivor.agent.session.id, presetId, hostGeneration: deployment.bridge.hostGeneration,
    noteCount: 0, notes: [],
  });
});

test('both real hosts remain model-free and shared profile/staging bytes stay unchanged with fixtures present', () => {
  assert.equal(deployment.modelCalls.count, 0);
  assert.equal(fixture.modelCalls.count, 0);
  // Every mutable fixture lives under this run's private root; the shared preset
  // root still holds exactly the shipped preset, and no fixture namespace leaked
  // into the shared module fallback.
  assert.ok(privateRoot!.startsWith(`${runRoot}${path.sep}`), 'the private root must be run-scoped');
  assert.ok(fixturePresets.startsWith(`${privateRoot!}${path.sep}`), 'fixture presets must be private');
  assert.ok(existsSync(path.join(privateRoot!, 'node_modules/@h01-fixtures')), 'fixtures must exist while this asserts');
  assert.equal(existsSync(path.join(home, 'profiles/node_modules/@h01-fixtures')), false,
    'no fixture namespace may be created in the shared module fallback');
  assert.deepEqual(readdirSync(stagedPresets), ['code2paper.patch.yml'], 'the shared preset root must hold only the shipped declaration');
  assert.deepEqual(protectedInputs(), protectedBefore);
  // Every refusal above was observed on the real roster/mount path; print the
  // verbatim reasons so the run's evidence names each negative case.
  assert.equal(refusals.length, 7, `expected 7 refusals, observed ${refusals.length}`);
  process.stdout.write(`H01 refusals (${refusals.length}):\n${refusals.map((line) => `  - ${line}`).join('\n')}\n`);
});
