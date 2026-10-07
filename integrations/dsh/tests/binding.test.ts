/**
 * H02 — trusted binding before the first prompt, tool access and model request.
 *
 * Runs the REAL frozen composition (dsh-base + dsh-web-app + `@code2paper/dsh-bundle`)
 * through `@deepseek-ai/dsh-app-boot`'s `boot()`, the real agent factory, the real
 * subagent seam and the real preset roster. Nothing is stubbed except the claim
 * authority, which H02 must not implement: `MockClaimRecorder` below is an
 * explicitly labeled stand-in for Python's task store (R01–R03 own the durable
 * claim, and no TS ledger is created here).
 *
 * Deployment inputs are read-only: the real profile manifest and patch layers,
 * the staged bundle and its preset root are consumed unchanged, and this run's
 * private root holds every mutable fixture. Run it through
 * `npm --prefix integrations/dsh run check:compat` (offline, isolated home,
 * read-only runtime and repository).
 *
 * Acceptance points covered:
 * - the standard `spawn` path cannot bind inside the child's creation window
 *   (measured: the child's prompt is delivered and its turn has started before
 *   `ctx.subagents.start()` resolves, and a provider request carries data only),
 *   so the narrow public `c2p-spawn` provider is the recorded decision;
 * - a blocked claim reads no material, calls no adapter and creates nothing;
 * - the binding is installed inside `create.setup`, before publication;
 * - forged task ids, unbound parents/children, stale fences and creation
 *   cancellation are all refused with named codes, leaving no residue;
 * - bindings do not outlive the agents they describe.
 */

import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import {
  existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readdirSync,
  readlinkSync, rmSync, symlinkSync, writeFileSync,
} from 'node:fs';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { boot, loadOverlayPatches, loadProfileDirectory } from '@deepseek-ai/dsh-app-boot';
import { provideCmdline } from '@deepseek-ai/dsh-cmdline';
import { standingMountFor } from '@deepseek-ai/dsh-agent-preset-registry';
import { scopeOf } from '@deepseek-ai/dsh-scope';
import type { AgentHandle } from '@deepseek-ai/dsh-agent';
import type { Context } from '@deepseek-ai/cordis';
import { createUserMessage } from '@deepseek-ai/dsh-llm';
import type { SessionId } from '@deepseek-ai/dsh-session';
import type { SubagentProvider } from '@deepseek-ai/dsh-subagent';

// Compile-time linkage to the frozen contract. These are type-only imports, so
// nothing is loaded from the source tree at runtime: the values under test come
// from the staged build (dynamic import in `before`). Their TYPES come from the
// real exports, which is what makes every call below compile-checked against the
// frozen contract instead of a local restatement of it.
import type * as RequestContractApi from '../src/request-contract.js';
import type * as RoleDispatchApi from '../src/role-dispatch.js';
import type * as SessionBindingApi from '../src/session-binding.js';

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
const stagingReceipt = path.join(devRoot, 'staging.json');
const policyFile = path.join(packageDir, 'dev/offline.patch.yml');
const runId = `${String(process.pid)}-${Date.now().toString(36)}`;

/**
 * The bundle's H02 modules: runtime values from the staged build, types from the
 * real source exports.
 */
type SessionBindingModule = {
  readonly SessionBindings: typeof SessionBindingApi.SessionBindings;
  readonly BindingRejection: typeof SessionBindingApi.BindingRejection;
  readonly createBoundRootAgent: typeof SessionBindingApi.createBoundRootAgent;
};

type DispatchModule = {
  readonly CODE2PAPER_SPAWN_PROVIDER: typeof RoleDispatchApi.CODE2PAPER_SPAWN_PROVIDER;
  readonly BINDING_PROTOCOL: typeof RoleDispatchApi.BINDING_PROTOCOL;
  readonly Code2PaperSpawnProvider: typeof RoleDispatchApi.Code2PaperSpawnProvider;
  readonly isBoundDelegationProvider: typeof RoleDispatchApi.isBoundDelegationProvider;
  readonly registerCode2PaperSpawn: typeof RoleDispatchApi.registerCode2PaperSpawn;
  readonly dispatchRole: typeof RoleDispatchApi.dispatchRole;
};

type RequestContractModule = {
  readonly REQUEST_CONTRACT_VERSION: typeof RequestContractApi.REQUEST_CONTRACT_VERSION;
  readonly RequestRejection: typeof RequestContractApi.RequestRejection;
  readonly requestBindingRef: typeof RequestContractApi.requestBindingRef;
  readonly sameRequestDigest: typeof RequestContractApi.sameRequestDigest;
  readonly assertRequestBindingCurrent: typeof RequestContractApi.assertRequestBindingCurrent;
  readonly assertReservationMatches: typeof RequestContractApi.assertReservationMatches;
  readonly assertSupportedDigest: typeof RequestContractApi.assertSupportedDigest;
};

type BindingsApi = SessionBindingApi.SessionBindings;
type SessionBindingsApi = SessionBindingApi.SessionBindings;
type RequestRecorderApi = RequestContractApi.RequestRecorder;
type RequestReserveRequestApi = RequestContractApi.RequestReserveRequest;
type ReservationReceiptApi = RequestContractApi.ReservationReceipt;
type RequestDispatchRequestApi = RequestContractApi.RequestDispatchRequest;
type DispatchReceiptApi = RequestContractApi.DispatchReceipt;
type RequestSettleRequestApi = RequestContractApi.RequestSettleRequest;
type SettlementReceiptApi = RequestContractApi.SettlementReceipt;
type RequestMarkUnknownRequestApi = RequestContractApi.RequestMarkUnknownRequest;
type UnknownReceiptApi = RequestContractApi.UnknownReceipt;

interface Host {
  readonly ctx: Context;
  readonly adapterCalls: { count: number };
  readonly createdAgents: Set<string>;
  /** Whether the announced agent was already bound and composed at its announcement. */
  readonly boundAtAnnouncement: Map<string, boolean>;
  readonly joinedAtAnnouncement: Map<string, boolean>;
}

/** A complete, supported request digest for the contract tests. */
function requestDigest(value = 'a'.repeat(64)): RequestContractApi.RequestDigest {
  return { digestVersion: 'c2p-wire/1', algorithm: 'sha256', value, parts: ['messages', 'tools', 'config'] };
}

let privateRoot: string;
let deployment: Host;
let bindings: BindingsApi;
let recorder: MockClaimRecorder;
let sessionModule: SessionBindingModule;
let dispatchModule: DispatchModule;
let requestContract: RequestContractModule;
let bundleModule: { name: string };
const handles: { handle: AgentHandle; host: Host }[] = [];

/**
 * MOCK claim recorder — the controlled stand-in for Python's claim authority.
 *
 * It mints receipts from an in-memory counter and keeps nothing durable; it is
 * H02's test double for the R01–R03 seam, never production wiring. Injection
 * points: `block()`/`release()` for a delayed grant, `refuseWith()` for a
 * refusal, `supersede()` for a newer fence on the same task, and the caller's
 * `signal` for cancellation.
 */
class MockClaimRecorder implements SessionBindingApi.ClaimRecorder {
  readonly requests: { purpose: string; taskId: string; epoch: number; parentClaimId?: string }[] = [];
  private nextClaim = 0;
  private readonly fences = new Map<string, number>();
  private gate: { promise: Promise<void>; release: () => void } | undefined;
  private refusal: Error | undefined;

  /** Delay every later claim until {@link release}. */
  block(): void {
    let release!: () => void;
    const promise = new Promise<void>((resolve) => { release = resolve; });
    this.gate = { promise, release };
  }

  /** Let a blocked claim proceed. */
  release(): void {
    this.gate?.release();
    this.gate = undefined;
  }

  /** Refuse every later claim with this message. */
  refuseWith(message: string): void {
    this.refusal = new Error(message);
  }

  /** Clear the refusal. */
  forgive(): void {
    this.refusal = undefined;
  }

  /** Simulate the authority superseding the grant for one task and epoch. */
  supersede(task: { taskId: string; epoch: number }): number {
    const key = `${task.taskId}@${String(task.epoch)}`;
    const next = (this.fences.get(key) ?? 1) + 1;
    this.fences.set(key, next);
    return next;
  }

  async claim(
    request: SessionBindingApi.ClaimRequest,
    options?: { readonly signal?: AbortSignal },
  ): Promise<SessionBindingApi.ClaimReceipt> {
    this.requests.push({
      purpose: request.purpose,
      taskId: request.task.taskId,
      epoch: request.task.epoch,
      ...(request.parentClaimId === undefined ? {} : { parentClaimId: request.parentClaimId }),
    });
    await this.waitForGate(options?.signal);
    if (options?.signal?.aborted === true) throw new Error('mock claim aborted');
    if (this.refusal !== undefined) throw this.refusal;
    const key = `${request.task.taskId}@${String(request.task.epoch)}`;
    const fence = this.fences.get(key) ?? 1;
    this.fences.set(key, fence);
    this.nextClaim += 1;
    return {
      claimId: `mock-claim-${String(this.nextClaim)}`,
      taskId: request.task.taskId,
      epoch: request.task.epoch,
      fence,
      compositionRef: 'mock-composition',
      grantedAt: 0,
    };
  }

  private async waitForGate(signal?: AbortSignal): Promise<void> {
    const gate = this.gate;
    if (gate === undefined) return;
    // An already-aborted signal never fires its listener, so it must be read
    // before waiting; otherwise a cancelled claim would hang forever.
    if (signal?.aborted === true) throw new Error('mock claim aborted while blocked');
    await new Promise<void>((resolve, reject) => {
      const onAbort = (): void => { reject(new Error('mock claim aborted while blocked')); };
      signal?.addEventListener('abort', onAbort, { once: true });
      gate.promise.then(
        () => { signal?.removeEventListener('abort', onAbort); resolve(); },
        (error: unknown) => { reject(error as Error); },
      );
    });
  }
}

/**
 * MOCK request recorder — the H04-shaped request seam, implemented here against
 * the real frozen contract so that contract is proven consumable.
 *
 * It keeps an in-memory event list for ordering assertions and implements no
 * balance, no persistence, no middleware and no reducer: R02 owns the production
 * ledger. Injection points mirror the claim mock: `block()`/`release()` for a
 * delayed reservation, `refuseWith()` for a refusal, and the caller's `signal`
 * for cancellation.
 */
class MockRequestRecorder implements RequestRecorderApi {
  /** Ordered event log for sequence assertions. */
  readonly events: string[] = [];
  private readonly reservations = new Map<string, ReservationReceiptApi>();
  private readonly bindings: SessionBindingsApi;
  private nextId = 0;
  private gate: { promise: Promise<void>; release: () => void } | undefined;
  private refusal: string | undefined;

  constructor(bindings: SessionBindingsApi) {
    this.bindings = bindings;
  }

  /** Delay every later reservation until {@link release}. */
  block(): void {
    let release!: () => void;
    const promise = new Promise<void>((resolve) => { release = resolve; });
    this.gate = { promise, release };
  }

  /** Let a blocked reservation proceed. */
  release(): void {
    this.gate?.release();
    this.gate = undefined;
  }

  /** Refuse every later reservation with this message. */
  refuseWith(message: string): void {
    this.refusal = message;
  }

  /** Clear the refusal. */
  forgive(): void {
    this.refusal = undefined;
  }

  async reserve(
    request: RequestReserveRequestApi,
    options?: { readonly signal?: AbortSignal },
  ): Promise<ReservationReceiptApi> {
    this.events.push(`reserve:${String(request.identity.sequence)}:${request.identity.purpose}`);
    await this.waitForGate(options?.signal);
    if (options?.signal?.aborted === true) {
      throw new requestContract.RequestRejection('reserve-aborted', 'mock reservation was cancelled');
    }
    if (this.refusal !== undefined) {
      throw new requestContract.RequestRejection('reserve-refused', this.refusal);
    }
    // The authority checks the grant before it grants anything.
    requestContract.assertRequestBindingCurrent(
      request.binding,
      this.bindings.currentFence({ taskId: request.binding.taskId, epoch: request.binding.epoch }),
    );
    requestContract.assertSupportedDigest(request.digest);
    this.nextId += 1;
    const reservation: ReservationReceiptApi = {
      contractVersion: requestContract.REQUEST_CONTRACT_VERSION,
      reservationId: `mock-reservation-${String(this.nextId)}`,
      requestId: `mock-request-${String(this.nextId)}`,
      binding: request.binding,
      digest: request.digest,
      grantedAt: 0,
    };
    this.reservations.set(reservation.reservationId, reservation);
    this.events.push(`reserved:${reservation.reservationId}`);
    return reservation;
  }

  async dispatch(
    request: RequestDispatchRequestApi,
    options?: { readonly signal?: AbortSignal },
  ): Promise<DispatchReceiptApi> {
    this.events.push('dispatch');
    const known = this.reservations.get(request.reservation.reservationId);
    if (known === undefined) {
      throw new requestContract.RequestRejection(
        'unknown-reservation',
        `mock recorder has no reservation ${request.reservation.reservationId}`,
      );
    }
    requestContract.assertReservationMatches(known, request);
    requestContract.assertRequestBindingCurrent(
      known.binding,
      this.bindings.currentFence({ taskId: known.binding.taskId, epoch: known.binding.epoch }),
    );
    if (options?.signal?.aborted === true) {
      throw new requestContract.RequestRejection('dispatch-refused', 'mock dispatch was cancelled');
    }
    this.events.push('dispatched');
    return {
      contractVersion: requestContract.REQUEST_CONTRACT_VERSION,
      requestId: known.requestId,
      reservationId: known.reservationId,
      digest: request.digest,
      stage: 'dispatch-recorded',
      recordedAt: 0,
    };
  }

  async settle(
    request: RequestSettleRequestApi,
    options?: { readonly signal?: AbortSignal },
  ): Promise<SettlementReceiptApi> {
    this.events.push('settle');
    if (options?.signal?.aborted === true) {
      throw new requestContract.RequestRejection('settle-refused', 'mock settlement was cancelled');
    }
    this.nextId += 1;
    return {
      contractVersion: requestContract.REQUEST_CONTRACT_VERSION,
      requestId: request.requestId,
      settlementId: `mock-settlement-${String(this.nextId)}`,
      finish: request.finish,
      response: request.response,
      settledAt: 0,
    };
  }

  async markUnknown(
    request: RequestMarkUnknownRequestApi,
    options?: { readonly signal?: AbortSignal },
  ): Promise<UnknownReceiptApi> {
    this.events.push('mark-unknown');
    if (options?.signal?.aborted === true) {
      throw new requestContract.RequestRejection('unknown-refused', 'mock unknown record was cancelled');
    }
    return {
      contractVersion: requestContract.REQUEST_CONTRACT_VERSION,
      requestId: request.requestId,
      lastStage: request.lastStage,
      reason: request.reason,
      uncertainty: 'send-outcome-unknown',
      recordedAt: 0,
    };
  }

  private async waitForGate(signal?: AbortSignal): Promise<void> {
    const gate = this.gate;
    if (gate === undefined) return;
    // An already-aborted signal never fires its listener, so read it first.
    if (signal?.aborted === true) throw new Error('mock reservation aborted while blocked');
    await new Promise<void>((resolve, reject) => {
      const onAbort = (): void => { reject(new Error('mock reservation aborted while blocked')); };
      signal?.addEventListener('abort', onAbort, { once: true });
      gate.promise.then(
        () => { signal?.removeEventListener('abort', onAbort); resolve(); },
        (error: unknown) => { reject(error as Error); },
      );
    });
  }
}

function sessionId(label: string): SessionId {
  return `h02-${label}-${runId}` as SessionId;
}

/** Fingerprint bytes, directories and link targets without traversing links. */
function treeSnapshot(root: string, includeWriteMetadata = false): Record<string, string> {
  const entries: Record<string, string> = {};
  const walk = (dir: string): void => {
    for (const name of readdirSync(dir).sort()) {
      const file = path.join(dir, name);
      const relative = path.relative(root, file);
      const stat = lstatSync(file, { bigint: true });
      if (stat.isSymbolicLink()) entries[relative] = `link:${readlinkSync(file)}`;
      else if (stat.isDirectory()) { entries[relative] = 'directory'; walk(file); }
      else entries[relative] = createHash('sha256').update(readFileSync(file)).digest('hex');
      if (includeWriteMetadata) entries[relative] += `|inode:${String(stat.ino)}|mtime_ns:${String(stat.mtimeNs)}`;
    }
  };
  walk(root);
  return entries;
}

/** The shared inputs this test must not touch. */
function protectedInputs() {
  return {
    profile: treeSnapshot(profileDir, true),
    staging: treeSnapshot(stagedBundle),
    receipt: readFileSync(stagingReceipt, 'utf8'),
  };
}

let protectedBefore: ReturnType<typeof protectedInputs>;

async function bootHost(): Promise<Host> {
  const profile = loadProfileDirectory('h02-binding-test', profileDir, installAnchor);
  const configDir = path.join(privateRoot, 'cfg');
  mkdirSync(configDir, { recursive: true });
  const config = path.join(configDir, 'cordis.yml');
  writeFileSync(config, readFileSync(path.join(profileDir, 'cordis.yml')));
  const patches = [
    ...profile.layers.flatMap((layer) => layer.patches), ...profile.patches,
    ...loadOverlayPatches('h02-binding-test', policyFile),
  ];
  const adapterCalls = { count: 0 };
  const createdAgents = new Set<string>();
  const boundAtAnnouncement = new Map<string, boolean>();
  const joinedAtAnnouncement = new Map<string, boolean>();
  const ctx = await boot('h02-binding-test', config, patches, (hostCtx) => {
    provideCmdline(hostCtx, { args: ['--host', '127.0.0.1', '--port', '0', '--no-open'], exit: () => {} });
    hostCtx.on('agent/created', ({ agent }) => {
      createdAgents.add(agent.id);
      // Publication announcement: the binding and the composition must already
      // exist here, because this is the first moment any observer can see the
      // agent at all.
      boundAtAnnouncement.set(agent.id, bindings?.resolve(agent) !== undefined);
      joinedAtAnnouncement.set(agent.id, standingMountFor(agent.ctx) !== undefined);
      return undefined;
    });
    hostCtx.on('llm/stream', () => {
      adapterCalls.count += 1;
      throw new Error('H02 must not reach the model seam');
    });
  });
  return { ctx, adapterCalls, createdAgents, boundAtAnnouncement, joinedAtAnnouncement };
}

/** Create one bound root agent on the deployment host. */
async function createRoot(
  label: string,
  options: { material?: () => Promise<void>; task?: { taskId: string; epoch: number } } = {},
) {
  const created = await sessionModule.createBoundRootAgent(deployment.ctx, {
    bindings,
    sessionId: sessionId(label),
    task: options.task ?? { taskId: 'task-h02', epoch: 3 },
    cwd: path.join(privateRoot, 'workspace'),
    ...(options.material === undefined ? {} : { material: options.material }),
  });
  handles.push({ handle: created.handle, host: deployment });
  return created;
}

function toolNames(host: Host, agentCtx: Context): string[] {
  return host.ctx.tools.schemas(scopeOf(agentCtx)).map((schema) => schema.name);
}

before(async () => {
  assert.equal(process.env.DSH_HOME, home, 'use the isolated launcher (npm run check:compat)');
  assert.ok(existsSync(installAnchor));
  assert.ok(existsSync(path.join(stagedBundle, 'lib/index.js')), 'build and stage first');
  protectedBefore = protectedInputs();
  privateRoot = mkdtempSync(path.join(runRoot, 'h02-binding-'));
  mkdirSync(path.join(privateRoot, 'workspace'));
  const modules = path.join(privateRoot, 'node_modules');
  mkdirSync(path.join(modules, '@code2paper'), { recursive: true });
  symlinkSync(path.join(runtimeRoot, 'node_modules/@deepseek-ai'), path.join(modules, '@deepseek-ai'), 'dir');
  symlinkSync(stagedBundle, path.join(modules, '@code2paper/dsh-bundle'), 'dir');

  bundleModule = await import(pathToFileURL(path.join(stagedBundle, 'lib/index.js')).href) as { name: string };
  sessionModule = await import(pathToFileURL(path.join(stagedBundle, 'lib/session-binding.js')).href) as SessionBindingModule;
  dispatchModule = await import(pathToFileURL(path.join(stagedBundle, 'lib/role-dispatch.js')).href) as DispatchModule;
  requestContract = await import(pathToFileURL(path.join(stagedBundle, 'lib/request-contract.js')).href) as RequestContractModule;

  deployment = await bootHost();
  recorder = new MockClaimRecorder();
  const bridge = deployment.ctx.get('code2paperBridge') as unknown as { hostGeneration: number };
  bindings = new sessionModule.SessionBindings({
    caller: { executionId: 'h02-execution', runId: 'h02-run', hostGeneration: bridge.hostGeneration },
    recorder,
  });
  dispatchModule.registerCode2PaperSpawn(deployment.ctx, { bindings });
});

after(async () => {
  const errors: unknown[] = [];
  // A test that failed before releasing the mock gate would leave a claim in
  // flight; composition disposal waits for that creation, so the gate is opened
  // and any refusal cleared before teardown begins.
  recorder?.release();
  recorder?.forgive();
  for (const { handle, host } of [...handles].reverse()) {
    try { await handle.dispose(); } catch (error) { errors.push(error); }
    try { assert.equal(host.ctx.agents.get(handle.agent.id), undefined); } catch (error) { errors.push(error); }
  }
  try { bindings?.dispose(); } catch (error) { errors.push(error); }
  try {
    assert.deepEqual(protectedInputs(), protectedBefore,
      'profile, staged files and staging receipt must remain byte-identical');
  } catch (error) { errors.push(error); }
  try { await deployment?.ctx.fiber.dispose(); } catch (error) { errors.push(error); }
  try { if (privateRoot !== undefined) rmSync(privateRoot, { recursive: true, force: true }); } catch (error) { errors.push(error); }
  if (errors.length > 0) throw new AggregateError(errors, 'H02 teardown/preservation failed');
});

test('the standard spawn path cannot bind inside the child creation window', async () => {
  assert.equal(bundleModule.name, 'code2paper-bridge', 'the staged build must be the bundle under test');
  const parent = await createRoot('measure-parent');
  const spawnProvider = deployment.ctx.subagents.getProvider('spawn');
  assert.ok(spawnProvider !== undefined, 'the standard spawn provider must be composed');
  const seen: string[][] = [];
  const measurement: SubagentProvider = {
    name: 'h02-measure',
    capabilities: spawnProvider.capabilities,
    inheritsParentContext: spawnProvider.inheritsParentContext,
    start(request) {
      seen.push(Object.keys(request).sort());
      return spawnProvider.start(request);
    },
  };
  const registration = deployment.ctx.subagents.registerProvider(measurement);
  try {
    const run = await deployment.ctx.subagents.start('h02-measure', {
      parent: parent.handle.agent,
      prompt: [{ type: 'text', text: 'measure the standard path' }],
      signal: new AbortController().signal,
    });
    const child = run.localAgent;
    assert.ok(child !== undefined);
    const events = child.session.snapshotEvents(0 as never).map((event) => event.type);
    // Decisive: by the time the caller holds the handle, the prompt has already
    // been delivered and the child's first turn has started. There is no earlier
    // caller-visible moment, and the provider request carries no creation hook.
    assert.ok(events.includes('turn/start'), `child turn must already have started: ${events.join(',')}`);
    assert.ok(events.includes('agent/inbox/spliced'), `prompt must already be delivered: ${events.join(',')}`);
    assert.equal(bindings.resolve(child), undefined, 'the standard path installs no trusted binding');
    assert.deepEqual(seen, [['descriptor', 'parent', 'prompt', 'signal']],
      'a provider request carries data only — no setup/callback field exists');
    await run.dispose();
  } finally {
    registration();
  }
  assert.equal(deployment.adapterCalls.count, 0);
});

test('a blocked claim reads no material, calls no adapter and creates nothing', async () => {
  let materialLoads = 0;
  const agentsBefore = deployment.ctx.agents.list().map((agent) => agent.id);
  const bindingsBefore = bindings.size;
  const claimsBefore = recorder.requests.length;
  recorder.block();
  const pending = createRoot('blocked', {
    material: () => { materialLoads += 1; return Promise.resolve(); },
  });
  // While the claim is outstanding: nothing may proceed.
  await new Promise((resolve) => { setTimeout(resolve, 50); });
  assert.equal(materialLoads, 0, 'material must not be read before a granted receipt');
  assert.equal(deployment.adapterCalls.count, 0, 'no adapter call may happen before a granted receipt');
  assert.equal(bindings.size, bindingsBefore, 'no binding may be added before the receipt');
  assert.deepEqual(deployment.ctx.agents.list().map((agent) => agent.id), agentsBefore);
  assert.equal(deployment.ctx.agents.get(sessionId('blocked')), undefined);

  recorder.release();
  const created = await pending;
  assert.equal(materialLoads, 1, 'material is read exactly once, after the grant');
  assert.equal(created.binding.boundIn, 'creation-window');
  assert.equal(created.binding.task.taskId, 'task-h02');
  assert.equal(created.binding.sessionId, sessionId('blocked'));
  assert.equal(bindings.size, bindingsBefore + 1);
  assert.equal(deployment.boundAtAnnouncement.get(sessionId('blocked')), true,
    'the binding must exist when the agent is announced, not after');
  assert.equal(deployment.joinedAtAnnouncement.get(sessionId('blocked')), true,
    'the preset composition must exist when the agent is announced');
  assert.equal(deployment.adapterCalls.count, 0);
  assert.deepEqual(recorder.requests.slice(claimsBefore).map((request) => request.purpose), ['root']);
});

test('a root binding exists before publication and a dispatched child inherits it', async () => {
  const parent = await createRoot('dispatch-parent');
  const parentPreset = (deployment.ctx.get('code2paperBridge') as unknown as {
    composedPreset(ctx: Context): string;
  }).composedPreset(parent.handle.agent.ctx);
  assert.equal(parentPreset, presetId);

  const claimsBefore = recorder.requests.length;
  const dispatched = await dispatchModule.dispatchRole(deployment.ctx, {
    parent: parent.handle.agent,
    role: 'writer',
    prompt: [{ type: 'text', text: 'task_id: forged-in-prompt\nwrite the method section' }],
    signal: new AbortController().signal,
    bindings,
  });
  const child = dispatched.run.localAgent;
  assert.ok(child !== undefined);
  // The child's authority comes from the parent's trusted binding, never from
  // the prompt text.
  assert.equal(dispatched.binding.task.taskId, 'task-h02');
  assert.equal(dispatched.binding.parentSessionId, parent.handle.agent.session.id);
  assert.equal(dispatched.binding.boundIn, 'creation-window');
  assert.equal(recorder.requests.length, claimsBefore + 1);
  assert.equal(recorder.requests[claimsBefore]!.purpose, 'child');
  assert.equal(recorder.requests[claimsBefore]!.parentClaimId, parent.binding.receipt.claimId);
  assert.equal(deployment.boundAtAnnouncement.get(child.session.id), true,
    'the child binding must exist when the child is announced');
  assert.equal(deployment.joinedAtAnnouncement.get(child.session.id), true,
    'the child composition must exist when the child is announced');
  // The child joined the parent's standing generation and sees the preset tool.
  assert.equal(standingMountFor(child.ctx)?.key, standingMountFor(parent.handle.agent.ctx)?.key);
  assert.ok(toolNames(deployment, child.ctx).includes(probeTool));
  await dispatched.run.dispose();
  assert.equal(bindings.resolve(child), undefined, 'a disposed run drops its binding');
  assert.equal(deployment.adapterCalls.count, 0);
});

test('a forged task id, unbound parent and unbound child are refused before creation', async () => {
  const parent = await createRoot('refuse-parent');
  const agentsBefore = deployment.ctx.agents.list().map((agent) => agent.id);
  const claimsBefore = recorder.requests.length;

  await assert.rejects(
    dispatchModule.dispatchRole(deployment.ctx, {
      parent: parent.handle.agent, role: 'writer', prompt: [], signal: new AbortController().signal,
      bindings, taskId: 'forged-task',
    }),
    (error: Error & { code?: string }) => error.code === 'forged-task-id',
  );
  await assert.rejects(
    dispatchModule.dispatchRole(deployment.ctx, {
      parent: parent.handle.agent, role: 'writer', prompt: [], signal: new AbortController().signal,
      bindings, epoch: 99,
    }),
    (error: Error & { code?: string }) => error.code === 'forged-task-id',
  );

  // A bound parent that joined no preset cannot give its child a composition.
  const uncomposedGrant = await bindings.claim({ task: { taskId: 'task-h02', epoch: 3 }, purpose: 'root' });
  const uncomposed = await deployment.ctx.agents.create({
    sessionId: sessionId('uncomposed'),
    meta: { cwd: path.join(privateRoot, 'workspace') },
    setup: (_agentCtx, agent) => { bindings.bind(agent.session.id, uncomposedGrant); },
  });
  handles.push({ handle: uncomposed, host: deployment });
  await assert.rejects(
    dispatchModule.dispatchRole(deployment.ctx, {
      parent: uncomposed.agent, role: 'writer', prompt: [], signal: new AbortController().signal, bindings,
    }),
    (error: Error & { code?: string }) => error.code === 'unbound-child',
  );

  // An agent with no trusted binding at all cannot delegate.
  const plain = await deployment.ctx.agents.create({
    sessionId: sessionId('unbound'),
    meta: { cwd: path.join(privateRoot, 'workspace') },
    setup: () => {},
  });
  handles.push({ handle: plain, host: deployment });
  await assert.rejects(
    dispatchModule.dispatchRole(deployment.ctx, {
      parent: plain.agent, role: 'writer', prompt: [], signal: new AbortController().signal, bindings,
    }),
    (error: Error & { code?: string }) => error.code === 'unbound-parent',
  );

  assert.deepEqual(deployment.ctx.agents.list().map((agent) => agent.id), agentsBefore.concat([
    sessionId('uncomposed'), sessionId('unbound'),
  ]));
  assert.equal(recorder.requests.length, claimsBefore + 1, 'only the explicit root claim was made');
  assert.equal(deployment.adapterCalls.count, 0);
});

test('a stale fence is refused while the current grant still works', async () => {
  const task = { taskId: 'task-stale', epoch: 1 };
  const first = await bindings.claim({ task, purpose: 'root' });
  assert.equal(first.receipt.fence, 1);
  // The authority issues a newer grant for the same task and epoch.
  assert.equal(recorder.supersede(task), 2);
  const second = await bindings.claim({ task, purpose: 'root' });
  assert.equal(second.receipt.fence, 2);
  assert.equal(bindings.currentFence(task), 2);

  // The superseded grant can no longer bind, and a stale hint is refused while
  // the current grant keeps working.
  assert.throws(
    () => bindings.bind(sessionId('stale'), first),
    (error: Error & { code?: string }) => error.code === 'stale-fence',
  );
  const parent = await createRoot('stale-parent', { task });
  assert.equal(bindings.assertTrusted(parent.handle.agent, { fence: 2 }).receipt.fence, 2);
  await assert.rejects(
    dispatchModule.dispatchRole(deployment.ctx, {
      parent: parent.handle.agent, role: 'writer', prompt: [], signal: new AbortController().signal,
      bindings, fence: 1,
    }),
    (error: Error & { code?: string }) => error.code === 'stale-fence',
  );
  assert.equal(deployment.adapterCalls.count, 0);
});

test('cancellation before the receipt and before creation both leave nothing behind', async () => {
  const agentsBefore = deployment.ctx.agents.list().map((agent) => agent.id);

  // (a) cancelled while the claim is blocked
  recorder.block();
  const blockedController = new AbortController();
  const blocked = createRoot('cancel-claim', { material: () => Promise.reject(new Error('must not run')) });
  blockedController.abort();
  const releaseGate = (): void => { recorder.release(); };
  await assert.rejects(
    sessionModule.createBoundRootAgent(deployment.ctx, {
      bindings,
      sessionId: sessionId('cancel-claim-2'),
      task: { taskId: 'task-h02', epoch: 3 },
      cwd: path.join(privateRoot, 'workspace'),
      signal: blockedController.signal,
    }),
    (error: Error & { code?: string }) => error.code === 'claim-aborted',
  );
  releaseGate();
  await blocked.then(
    () => { throw new Error('the blocked claim should have completed after release'); },
    () => undefined,
  );

  // (b) cancelled after the receipt, before the agent exists
  const creationController = new AbortController();
  let materialLoads = 0;
  await assert.rejects(
    sessionModule.createBoundRootAgent(deployment.ctx, {
      bindings,
      sessionId: sessionId('cancel-creation'),
      task: { taskId: 'task-h02', epoch: 3 },
      cwd: path.join(privateRoot, 'workspace'),
      signal: creationController.signal,
      material: () => { materialLoads += 1; creationController.abort(); return Promise.resolve(); },
    }),
    (error: Error & { code?: string }) => error.code === 'creation-aborted',
  );
  assert.equal(materialLoads, 1, 'the receipt preceded the material read, which then cancelled creation');
  assert.equal(deployment.ctx.agents.get(sessionId('cancel-creation')), undefined);
  assert.equal(bindings.resolve(sessionId('cancel-creation')), undefined, 'a rolled-back creation leaves no binding');
  assert.deepEqual(deployment.ctx.agents.list().map((agent) => agent.id), agentsBefore);
  assert.equal(deployment.adapterCalls.count, 0);
});

test('bindings do not outlive their agents and the registry is not durable state', async () => {
  const sizeBefore = bindings.size;
  const created = await createRoot('lifecycle');
  assert.equal(bindings.size, sizeBefore + 1);
  assert.equal(bindings.require(created.handle.agent).sessionId, sessionId('lifecycle'));
  await created.dispose();
  handles.splice(handles.findIndex((entry) => entry.handle === created.handle), 1);
  assert.equal(bindings.size, sizeBefore, 'disposing through the owner drops the binding with the agent');
  assert.equal(deployment.ctx.agents.get(sessionId('lifecycle')), undefined);

  // Capabilities the provider does not claim are refused loudly, not ignored.
  await assert.rejects(
    deployment.ctx.subagents.start(dispatchModule.CODE2PAPER_SPAWN_PROVIDER, {
      parent: created.handle.agent,
      prompt: [],
      signal: new AbortController().signal,
      outputSchema: { type: 'object', properties: {} },
    }),
    /UNSUPPORTED_CAPABILITY|does not support/,
  );
  assert.equal(deployment.adapterCalls.count, 0);
});

test('the frozen request contract is consumable: reserve, dispatch, settle and unknown', async () => {
  const root = await createRoot('request-consumer');
  const requests = new MockRequestRecorder(bindings);
  const digest = requestDigest();
  const binding = requestContract.requestBindingRef(root.binding);
  assert.equal(binding.sessionId, root.binding.sessionId);
  assert.equal(binding.fence, root.binding.receipt.fence);
  assert.equal(binding.claimId, root.binding.receipt.claimId);

  const reservation = await requests.reserve({
    binding, identity: { sequence: 1, purpose: 'writer' }, digest,
    estimate: { inputTokens: 512, outputTokens: 256 },
  });
  assert.equal(reservation.contractVersion, requestContract.REQUEST_CONTRACT_VERSION);
  assert.equal(requestContract.sameRequestDigest(reservation.digest, digest), true);

  const dispatched = await requests.dispatch({ reservation, digest });
  assert.equal(dispatched.stage, 'dispatch-recorded', 'a dispatch record never claims delivery');
  assert.deepEqual(requests.events, [
    'reserve:1:writer', `reserved:${reservation.reservationId}`, 'dispatch', 'dispatched',
  ]);

  // reserve and dispatch must describe the same assembly.
  await assert.rejects(
    requests.dispatch({ reservation, digest: requestDigest('b'.repeat(64)) }),
    (error: Error & { code?: string }) => error.code === 'digest-mismatch',
  );
  await assert.rejects(
    requests.dispatch({ reservation: { ...reservation, reservationId: 'not-mine' }, digest }),
    (error: Error & { code?: string }) => error.code === 'unknown-reservation',
  );
  // A digest that does not claim the whole supported assembly is refused.
  assert.throws(
    () => requestContract.assertSupportedDigest({ ...digest, parts: ['messages'] }),
    (error: Error & { code?: string }) => error.code === 'contract-unsupported',
  );

  // Missing usage stays missing; an unknown outcome records the last provable stage.
  const settled = await requests.settle({
    requestId: reservation.requestId, reservationId: reservation.reservationId,
    finish: { kind: 'unfinished' }, response: { kind: 'none' },
  });
  assert.equal('usage' in settled.finish, false, 'a missing usage is never invented');
  const unknown = await requests.markUnknown({
    requestId: reservation.requestId, reservationId: reservation.reservationId,
    lastStage: 'dispatch-recorded', reason: 'transport outcome was never observed',
  });
  assert.equal(unknown.uncertainty, 'send-outcome-unknown');
  assert.equal(unknown.lastStage, 'dispatch-recorded');
  assert.equal('refunded' in unknown, false, 'the contract records uncertainty; the authority decides refunds');
});

test('request recording refuses a stale grant and reports delay, refusal and cancellation', async () => {
  const task = { taskId: 'task-request', epoch: 7 };
  const root = await createRoot('request-gate', { task });
  const requests = new MockRequestRecorder(bindings);
  const digest = requestDigest();
  const binding = requestContract.requestBindingRef(root.binding);
  const reserveNext = (sequence: number) => requests.reserve({
    binding, identity: { sequence, purpose: 'writer' }, digest, estimate: { inputTokens: 1, outputTokens: 1 },
  });

  // Delay: a pending reservation records nothing beyond its own wait.
  requests.block();
  const pending = reserveNext(1);
  await new Promise((resolve) => { setTimeout(resolve, 30); });
  assert.deepEqual(requests.events.filter((event) => event === 'dispatch' || event === 'dispatched'), []);
  requests.release();
  await pending;

  // Refusal.
  requests.refuseWith('no budget for this epoch');
  await assert.rejects(reserveNext(2), (error: Error & { code?: string }) => error.code === 'reserve-refused');
  requests.forgive();

  // Cancellation, including a signal already aborted before the call.
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(
    requests.reserve(
      { binding, identity: { sequence: 3, purpose: 'writer' }, digest, estimate: { inputTokens: 1, outputTokens: 1 } },
      { signal: controller.signal },
    ),
    (error: Error & { code?: string }) => error.code === 'reserve-aborted',
  );

  // A superseded grant cannot reserve, even with no hint involved.
  assert.equal(recorder.supersede(task), 2);
  await bindings.claim({ task, purpose: 'root' });
  await assert.rejects(reserveNext(4), (error: Error & { code?: string }) => error.code === 'stale-binding');
});

test('a superseded parent binding stops delegating, with or without a fence hint', async () => {
  const task = { taskId: 'task-superseded', epoch: 5 };
  const parent = await createRoot('superseded-parent', { task });
  assert.equal(parent.binding.receipt.fence, 1);
  assert.equal(recorder.supersede(task), 2);
  const newer = await bindings.claim({ task, purpose: 'root' });
  assert.equal(newer.receipt.fence, 2);
  assert.equal(bindings.require(parent.handle.agent).receipt.fence, 1, 'a plain read still reports what was bound');
  assert.throws(
    () => bindings.requireCurrent(parent.handle.agent),
    (error: Error & { code?: string }) => error.code === 'stale-binding',
  );

  const agentsBefore = deployment.ctx.agents.list().map((agent) => agent.id);
  const claimsBefore = recorder.requests.length;
  const prompt = [{ type: 'text' as const, text: 'must not run' }];
  // (a) no hint: the trusted binding itself is superseded.
  await assert.rejects(
    dispatchModule.dispatchRole(deployment.ctx, {
      parent: parent.handle.agent, role: 'writer', prompt, signal: new AbortController().signal, bindings,
    }),
    (error: Error & { code?: string }) => error.code === 'stale-binding',
  );
  // (b) the CURRENT fence hint cannot upgrade the old parent.
  await assert.rejects(
    dispatchModule.dispatchRole(deployment.ctx, {
      parent: parent.handle.agent, role: 'writer', prompt, signal: new AbortController().signal, bindings, fence: 2,
    }),
    (error: Error & { code?: string }) => error.code === 'stale-binding',
  );
  // (c) the same refusal through the public provider entry.
  await assert.rejects(
    deployment.ctx.subagents.start(dispatchModule.CODE2PAPER_SPAWN_PROVIDER, {
      parent: parent.handle.agent, prompt, signal: new AbortController().signal,
    }),
    (error: Error & { code?: string }) => error.code === 'stale-binding',
  );
  assert.equal(recorder.requests.length, claimsBefore, 'no child claim may happen for a superseded parent');
  assert.deepEqual(deployment.ctx.agents.list().map((agent) => agent.id), agentsBefore);
  assert.equal(deployment.adapterCalls.count, 0);

  // Control: a parent bound to the current grant still delegates.
  const current = await createRoot('current-parent', { task });
  assert.equal(current.binding.receipt.fence, 2);
  const dispatched = await dispatchModule.dispatchRole(deployment.ctx, {
    parent: current.handle.agent, role: 'writer', prompt: [{ type: 'text', text: 'run' }],
    signal: new AbortController().signal, bindings,
  });
  assert.equal(dispatched.binding.task.taskId, task.taskId);
  await dispatched.run.dispose();
});

test('the dispatch entry admits only provider objects this Host registered, before any start', async () => {
  const parent = await createRoot('override-parent');
  const spawnProvider = deployment.ctx.subagents.getProvider('spawn');
  assert.ok(spawnProvider !== undefined);

  // The reproduced decoy: a foreign provider that carries the public protocol tag,
  // creates a REAL child through the real factory, and delivers its prompt before
  // returning the run — exactly the shape that defeated a tag-only check. It is
  // registered directly, so it holds no admission record.
  let decoyStartCalls = 0;
  const decoy: SubagentProvider & { readonly bindingProtocol: string } = {
    name: 'h02-decoy',
    capabilities: spawnProvider.capabilities,
    inheritsParentContext: false,
    bindingProtocol: dispatchModule.BINDING_PROTOCOL,
    start: async (request) => {
      decoyStartCalls += 1;
      const childId = sessionId('decoy-child');
      const handle = await request.parent.ctx.agents.create({
        sessionId: childId,
        parentAgent: request.parent,
        meta: { cwd: path.join(privateRoot, 'workspace') },
        setup: () => { /* no binding, no composition: this is the decoy */ },
      });
      handle.agent.followup(createUserMessage({ content: [...request.prompt], source: { kind: 'user' } }));
      return {
        id: childId,
        localAgent: handle.agent,
        result: Promise.resolve({ output: [], stopReason: 'error' as const }),
        dispose: () => handle.dispose(),
      };
    },
  };
  const decoyRegistration = deployment.ctx.subagents.registerProvider(decoy);

  // A provider registered by this Host, but for a DIFFERENT binding registry.
  const otherBindings = new sessionModule.SessionBindings({
    caller: { executionId: 'h02-other-execution', runId: 'h02-other-run', hostGeneration: 99 },
    recorder: new MockClaimRecorder(),
  });
  const misbound = dispatchModule.registerCode2PaperSpawn(deployment.ctx, {
    bindings: otherBindings, providerName: 'c2p-spawn-misbound',
  });

  const agentsBefore = deployment.ctx.agents.list().map((agent) => agent.id);
  const claimsBefore = recorder.requests.length;
  const prompt = [{ type: 'text' as const, text: 'must not run' }];
  const refuse = async (providerName: string, expected: string): Promise<void> => {
    await assert.rejects(
      dispatchModule.dispatchRole(deployment.ctx, {
        parent: parent.handle.agent, role: 'writer', prompt, signal: new AbortController().signal,
        bindings, providerName,
      }),
      (error: Error & { code?: string }) => error.code === expected,
    );
  };

  try {
    // (a) stock spawn: not this Host's provider at all.
    await refuse('spawn', 'unbound-provider');
    // (b) the tag-carrying decoy: refused before start, so nothing it would do happens.
    assert.equal(dispatchModule.isBoundDelegationProvider(decoy), true, 'the decoy does carry the public tag');
    await refuse(decoy.name, 'unbound-provider');
    assert.equal(decoyStartCalls, 0, 'a non-admitted provider must never reach start()');
    // (c) registered by this Host, but bound to another registry.
    await refuse(misbound.providerName, 'misbound-provider');
    // (d) a revoked registration does not regain authority when re-registered.
    const revoked = dispatchModule.registerCode2PaperSpawn(deployment.ctx, { bindings, providerName: 'c2p-spawn-revoked' });
    const revokedProvider = deployment.ctx.subagents.getProvider(revoked.providerName);
    assert.ok(revokedProvider !== undefined);
    revoked.dispose();
    deployment.ctx.subagents.registerProvider(revokedProvider);
    await refuse(revoked.providerName, 'unbound-provider');

    // No child, claim or model call may have happened on any refused path.
    assert.deepEqual(deployment.ctx.agents.list().map((agent) => agent.id), agentsBefore, 'no child may be created');
    assert.equal(recorder.requests.length, claimsBefore, 'no child claim may happen');
    assert.equal(deployment.adapterCalls.count, 0);
    assert.equal(deployment.ctx.agents.get(sessionId('decoy-child')), undefined);
  } finally {
    decoyRegistration();
    misbound.dispose();
    otherBindings.dispose();
  }

  // Legitimate names keep working: the default one, and a custom name registered
  // through the real helper.
  const custom = dispatchModule.registerCode2PaperSpawn(deployment.ctx, { bindings, providerName: 'c2p-spawn-custom' });
  try {
    for (const providerName of [undefined, custom.providerName]) {
      const dispatched = await dispatchModule.dispatchRole(deployment.ctx, {
        parent: parent.handle.agent, role: 'writer', prompt: [{ type: 'text', text: 'legitimate' }],
        signal: new AbortController().signal, bindings,
        ...(providerName === undefined ? {} : { providerName }),
      });
      assert.equal(dispatched.binding.boundIn, 'creation-window');
      await dispatched.run.dispose();
    }
  } finally {
    custom.dispose();
  }

  // Backstop, separate fault scenario: an ADMITTED provider whose run carries no
  // local child (a remote-shaped implementation). The entry owns the run it
  // obtained and disposes it before refusing.
  let disposals = 0;
  const remoteShaped = dispatchModule.registerCode2PaperSpawn(deployment.ctx, {
    bindings,
    providerName: 'c2p-spawn-remote-shaped',
    provider: {
      name: 'c2p-spawn-remote-shaped',
      capabilities: spawnProvider.capabilities,
      inheritsParentContext: false,
      bindingProtocol: dispatchModule.BINDING_PROTOCOL,
      start: () => Promise.resolve({
        id: sessionId('remote-run'),
        localAgent: undefined,
        result: Promise.resolve({ output: [], stopReason: 'error' as const }),
        dispose: () => { disposals += 1; return Promise.resolve(); },
      }),
    },
  });
  try {
    await assert.rejects(
      dispatchModule.dispatchRole(deployment.ctx, {
        parent: parent.handle.agent, role: 'writer', prompt: [], signal: new AbortController().signal,
        bindings, providerName: remoteShaped.providerName,
      }),
      (error: Error & { code?: string }) => error.code === 'unbound-child',
    );
    assert.equal(disposals, 1, 'the entry disposes a run whose child is not bound');
  } finally {
    remoteShaped.dispose();
  }
});
