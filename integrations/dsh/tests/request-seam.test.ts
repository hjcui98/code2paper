/**
 * H04 — request accounting at the real LLM seam.
 *
 * This file starts with the experiment §4 of `h02_acceptance.md` requires
 * *before* any design decision: what a listener registered on an Agent's scoped
 * context actually observes. The answer decides whether protected provenance can
 * come from the registration site, or whether the scope capability is too narrow
 * and must be reported as a named gap instead of degrading to a self-reported
 * session id lookup.
 *
 * Everything runs offline through the real frozen composition: no network, no
 * provider, one registered mock adapter. Only the adapter is a stand-in, and it
 * records facts; the middleware under test does all refusing.
 */

import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { boot, loadOverlayPatches, loadProfileDirectory } from '@deepseek-ai/dsh-app-boot';
import { provideCmdline } from '@deepseek-ai/dsh-cmdline';
import { LlmAdapter, isAgentLoopRequest } from '@deepseek-ai/dsh-llm';
import type { GenerateOptions, StreamChunk } from '@deepseek-ai/dsh-llm';
import type { Context } from '@deepseek-ai/cordis';
import type { AgentHandle } from '@deepseek-ai/dsh-agent';
import type { SessionId } from '@deepseek-ai/dsh-session';

// H04 under test: types from the real source exports, values from the staged
// build (imported in `before`, after staging exists).
import type * as AccountingApi from '../src/request-accounting.js';
import type * as ContractApi from '../src/request-contract.js';

const packageDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
// The launcher decides which development root is active (default or an isolated
// candidate) and exports it, so the guard compares against that same root.
const devRoot = process.env.C2P_DSH_DEV_ROOT
  ? path.resolve(process.env.C2P_DSH_DEV_ROOT)
  : path.resolve(packageDir, '../../.dsh-dev');
const home = path.join(devRoot, 'home');
const runRoot = process.env.C2P_DSH_RUN_ROOT ?? path.join(devRoot, 'run');
const runtimeRoot = path.join(devRoot, 'runtime');
const installAnchor = path.join(runtimeRoot, 'node_modules/@deepseek-ai/dsh/package.json');
const profileDir = path.join(home, 'profiles/code2paper-dev-compat');
const policyFile = path.join(packageDir, 'dev/offline.patch.yml');
const bundleName = '@code2paper/dsh-bundle';
const stagedBundle = path.join(home, 'profiles/node_modules', bundleName);
const runId = `${String(process.pid)}-${Date.now().toString(36)}`;

const MOCK_PROVIDER = 'c2p-h04-mock';
const MOCK_MODEL = 'h04-mock-model';

/** What one observed dispatch looked like, recorded by the adapter itself. */
interface AdapterRecord {
  readonly label: string;
  readonly provider: string;
  readonly model: string;
  readonly maxTokens: number | undefined;
  readonly sessionId: string | undefined;
  readonly loopMarked: boolean;
  readonly frozen: boolean;
  readonly messageSummary: string;
}

/** One listener's observation log, keyed by registration scope label. */
type Observations = Map<string, unknown[]>;

const adapterRecords: AdapterRecord[] = [];
let adapterLabel = 'unlabeled';

class RecordingMockAdapter extends LlmAdapter {
  override providerInfo(provider: string): { id: string; name: string } {
    return { id: provider, name: `h04 mock (${provider})` };
  }

  override async listModels(): Promise<never[]> {
    return [];
  }

  override async resolveModel(provider: string, model: string) {
    return {
      provider,
      id: model,
      name: `H04 mock ${model}`,
      context: { contextWindow: 131072 },
      defaultMaxTokens: 4096,
    };
  }

  override async prepareCall(provider: string, model: string) {
    return { model: await this.resolveModel(provider, model), stream: (options: GenerateOptions) => this.stream(options) };
  }

  override async *stream(options: GenerateOptions): AsyncIterable<StreamChunk> {
    adapterRecords.push({
      label: adapterLabel,
      provider: options.provider,
      model: options.model,
      maxTokens: options.maxTokens,
      sessionId: options.sessionId === undefined ? undefined : String(options.sessionId),
      loopMarked: isLoopMarked(options),
      frozen: Object.isFrozen(options),
      messageSummary: summarizeMessages(options),
    });
    yield { type: 'block-start', index: 0, blockType: 'text' };
    yield { type: 'text-delta', index: 0, text: 'ok' };
    yield { type: 'block-end', index: 0, block: { type: 'text', text: 'ok' } };
    yield { type: 'usage', usage: { inputTokens: 3, outputTokens: 1 } };
    yield { type: 'finish', reason: { kind: 'stop' } };
  }
}

/** The real loop-marker predicate, not a guessed symbol. */
function isLoopMarked(options: GenerateOptions): boolean {
  return isAgentLoopRequest(options);
}

function summarizeMessages(options: GenerateOptions): string {
  const messages = options.messages ?? [];
  return `${String(messages.length)}:${messages.map((message) => message.role).join(',')}`;
}

interface Host {
  readonly ctx: Context;
  readonly observations: Observations;
  readonly registrations: (() => boolean)[];
}

let deployment: Host;
let accounting: typeof AccountingApi;
let contract: typeof ContractApi;
let bindings: import('../src/session-binding.js').SessionBindings;
let authorizations: AccountingApi.DispatchAuthorizations;
let recorder: RecorderStub;
let installed: AccountingApi.RequestAccounting;
const routeDiagnostics: string[] = [];
/** Arrival facts for the S2 legal control: one line per observed stage. */
const arrivalFacts: string[] = [];
let dispatchModule: typeof import('../src/role-dispatch.js');

/** Records request-accounting calls; a fixture, never a durable balance. */
class RecorderStub {
  readonly events: string[] = [];
  private minted = 0;
  async reserve(request: ContractApi.RequestReserveRequest): Promise<ContractApi.ReservationReceipt> {
    this.minted += 1;
    this.events.push(`reserve:${String(request.identity.sequence)}`);
    return {
      contractVersion: contract.REQUEST_CONTRACT_VERSION,
      reservationId: `res-${String(this.minted)}`, requestId: `req-${String(this.minted)}`,
      binding: request.binding, digest: request.digest, grantedAt: Date.now(),
    };
  }
  async dispatch(request: ContractApi.RequestDispatchRequest): Promise<ContractApi.DispatchReceipt> {
    this.events.push('dispatch');
    return {
      contractVersion: contract.REQUEST_CONTRACT_VERSION,
      requestId: request.reservation.requestId, reservationId: request.reservation.reservationId,
      digest: request.digest, stage: 'dispatch-recorded', recordedAt: Date.now(),
    };
  }
  async settle(request: ContractApi.RequestSettleRequest): Promise<ContractApi.SettlementReceipt> {
    this.events.push(`settle:${request.finish.kind}`);
    return {
      contractVersion: contract.REQUEST_CONTRACT_VERSION,
      requestId: request.requestId, settlementId: 'set-1',
      finish: request.finish, response: request.response, settledAt: Date.now(),
    };
  }
  async markUnknown(request: ContractApi.RequestMarkUnknownRequest): Promise<ContractApi.UnknownReceipt> {
    this.events.push(`markUnknown:${request.reason}`);
    return {
      contractVersion: contract.REQUEST_CONTRACT_VERSION,
      requestId: request.requestId, lastStage: request.lastStage, reason: request.reason,
      uncertainty: 'send-outcome-unknown', recordedAt: Date.now(),
    };
  }
}

/** The controlled stand-in for Python's claim authority (R01–R03 own the durable one). */
class ClaimStub {
  private readonly fences = new Map<string, number>();
  private minted = 0;
  supersede(taskId: string, epoch: number): void {
    const key = `${taskId}@${String(epoch)}`;
    this.fences.set(key, (this.fences.get(key) ?? 1) + 1);
  }
  async claim(request: { task: { taskId: string; epoch: number } }): Promise<import('../src/session-binding.js').ClaimReceipt> {
    this.minted += 1;
    const key = `${request.task.taskId}@${String(request.task.epoch)}`;
    const fence = this.fences.get(key) ?? 1;
    this.fences.set(key, fence);
    return {
      claimId: `claim-${String(this.minted)}`, taskId: request.task.taskId, epoch: request.task.epoch,
      fence, compositionRef: 'composition-h04', grantedAt: Date.now(),
    };
  }
}
let privateRoot: string;
const handles: AgentHandle[] = [];

function record(observations: Observations, scope: string, value: unknown): void {
  const rows = observations.get(scope) ?? [];
  rows.push(value);
  observations.set(scope, rows);
}

function observe(observations: Observations, scope: string, ctx: Context, global: boolean): () => boolean {
  return ctx.on(
    'llm/stream',
    (options: GenerateOptions, next: () => AsyncIterable<StreamChunk>) => {
      record(observations, scope, {
        provider: options.provider,
        sessionId: options.sessionId === undefined ? undefined : String(options.sessionId),
        loopMarked: isLoopMarked(options),
        frozen: Object.isFrozen(options),
      });
      return next();
    },
    global ? { global: true } : {},
  );
}

async function bootHost(): Promise<Host> {
  const profile = loadProfileDirectory('h04-request-seam', profileDir, installAnchor);
  const configDir = path.join(privateRoot, 'cfg');
  mkdirSync(configDir, { recursive: true });
  const config = path.join(configDir, 'cordis.yml');
  writeFileSync(config, readFileSync(path.join(profileDir, 'cordis.yml')));
  const patches = [
    ...profile.layers.flatMap((layer) => layer.patches),
    ...profile.patches,
    ...loadOverlayPatches('h04-request-seam', policyFile),
  ];
  const observations: Observations = new Map();
  const registrations: (() => boolean)[] = [];
  const ctx = await boot('h04-request-seam', config, patches, (hostCtx) => {
    provideCmdline(hostCtx, { args: ['--host', '127.0.0.1', '--port', '0', '--no-open'], exit: () => {} });
    hostCtx.on('agent/error', (payload: unknown) => { agentEvents.push(`error:${JSON.stringify(payload).slice(0, 300)}`); });
    hostCtx.on('agent/created', ({ agent }: { agent: { id: string; ctx: Context } }) => {
      const scope = `agent:${agent.id}`;
      registrations.push(observe(observations, scope, agent.ctx, false));
      registrations.push(observe(observations, `${scope}-global`, agent.ctx, true));
      return undefined;
    });
    registrations.push(observe(observations, 'root-global', hostCtx, true));
    registrations.push(observe(observations, 'root-scoped', hostCtx, false));
    hostCtx.on('agent/created', ({ agent }: { agent: { id: string; options: unknown } }) => {
      createdAgentIds.push(agent.id);
      agentOptionsSeen.set(agent.id, agent.options);
      return undefined;
    });
  });
  return { ctx, observations, registrations };
}

function sessionIdFor(label: string): SessionId {
  return `h04-${label}-${runId}` as SessionId;
}

const agentEvents: string[] = [];
const createdAgentIds: string[] = [];
const agentOptionsSeen = new Map<string, unknown>();
before(async () => {
  assert.equal(process.env.DSH_HOME, home, 'use the isolated launcher (npm run check:compat)');
  privateRoot = mkdtempSync(path.join(runRoot, 'h04-seam-'));
  mkdirSync(path.join(privateRoot, 'workspace'));
  const modules = path.join(privateRoot, 'node_modules');
  mkdirSync(path.join(modules, '@code2paper'), { recursive: true });
  symlinkSync(path.join(runtimeRoot, 'node_modules/@deepseek-ai'), path.join(modules, '@deepseek-ai'), 'dir');
  symlinkSync(stagedBundle, path.join(modules, '@code2paper/dsh-bundle'), 'dir');
  const bundle = await import(pathToFileURL(path.join(stagedBundle, 'lib/index.js')).href) as { name: string };
  assert.equal(bundle.name, 'code2paper-bridge', 'the staged build must be the bundle under test');
  accounting = await import(pathToFileURL(path.join(stagedBundle, 'lib/request-accounting.js')).href) as typeof AccountingApi;
  contract = await import(pathToFileURL(path.join(stagedBundle, 'lib/request-contract.js')).href) as typeof ContractApi;
  dispatchModule = await import(pathToFileURL(path.join(stagedBundle, 'lib/role-dispatch.js')).href) as typeof import('../src/role-dispatch.js');
  deployment = await bootHost();

  // The Host's route is REGISTERED GATED: the underlying recorder adapter is only
  // reachable through a live one-time authorization.
  routeDiagnostics.length = 0;
  authorizations = new accounting.DispatchAuthorizations();
  recorder = new RecorderStub();
  const underlying = new RecordingMockAdapter();
  deployment.ctx.on('agent/request', (
    _payload: { agent: { id: string }; turn: number; step: number; signal?: AbortSignal },
    next: () => Promise<import('@deepseek-ai/dsh-llm').LlmCallConfig>,
  ) => { arrivalFacts.push('agent/request'); return next(); });
  deployment.ctx.on('agent/created', () => { arrivalFacts.push('agent/created'); return undefined; });
  deployment.ctx.llm.registerAdapter([MOCK_PROVIDER], accounting.gatedAdapter(
    underlying as unknown as Parameters<typeof accounting.gatedAdapter>[0],
    authorizations,
    (event) => { routeDiagnostics.push(`${event.kind}:${event.detail}`); },
  ) as never);

  const bridge = deployment.ctx.get('code2paperBridge') as unknown as { hostGeneration: number };
  const sessionApi = await import(pathToFileURL(path.join(stagedBundle, 'lib/session-binding.js')).href) as typeof import('../src/session-binding.js');
  bindings = new sessionApi.SessionBindings({
    caller: { executionId: 'h04-execution', runId: 'h04-run', hostGeneration: bridge.hostGeneration },
    recorder: new ClaimStub() as unknown as import('../src/session-binding.js').ClaimRecorder,
  });

  dispatchModule.registerCode2PaperSpawn(deployment.ctx, { bindings });

});

after(async () => {
  const errors: unknown[] = [];
  for (const handle of [...handles].reverse()) {
    try { await handle.dispose(); } catch (error) { errors.push(error); }
  }
  try { installed?.dispose(); } catch (error) { errors.push(error); }
  try { await deployment?.ctx.fiber.dispose(); } catch (error) { errors.push(error); }
  try { if (privateRoot !== undefined) rmSync(privateRoot, { recursive: true, force: true }); } catch (error) { errors.push(error); }
  if (errors.length > 0) throw new AggregateError(errors, 'H04 teardown failed');
});

function counts(): Map<string, number> {
  const snapshot = new Map<string, number>();
  for (const [key, rows] of deployment.observations) snapshot.set(key, rows.length);
  return snapshot;
}

function delta(before: Map<string, number>, key: string): number {
  return (deployment.observations.get(key)?.length ?? 0) - (before.get(key) ?? 0);
}

/**
 * The gating experiment: what a listener registered on an Agent's scoped context
 * actually observes. Measured facts (this run, real loop, one mock adapter):
 *
 * 1. A listener registered in a ROOT agent's `setup` context is NOT isolated: it
 *    sees every dispatch in the process, including a sibling agent's turn and a
 *    hand-built dispatch issued from the host root.
 * 2. A listener registered on a DELEGATED CHILD's context IS isolated: the child
 *    saw its own loop dispatch, and neither its sibling child's dispatch nor the
 *    host root's bare dispatch.
 * 3. Loop requests arrive deep-frozen and `isAgentLoopRequest` is true; a
 *    hand-built dispatch is neither.
 *
 * Consequence for H04: protected provenance comes from the registration site,
 * and the usable site is the delegated child scope - exactly where a role
 * Writer runs. Root-agent scopes cannot carry provenance.
 */
/**
 * H04-S1 (redo) - and the corrected conclusion.
 *
 * The earlier version of this experiment disposed the child inside
 * `runChildTurn()` before measuring, created only ONE child, and compared a
 * value with itself. Its "delegated child scopes are isolated" conclusion is
 * **WITHDRAWN**.
 *
 * Measured here with THREE live bound children (all still registered while
 * measuring): every listener registered anywhere in the tree observes every
 * `llm/stream` dispatch. A and B both see sibling C's dispatch, all three see a
 * host bare request that merely names A's session id, and the root sees
 * everything.
 *
 * `llm/stream` is emitted by the LlmRuntime on its own (root) context, so Cordis
 * context filtering gives this seam **no isolation at all**. Registration site
 * therefore cannot prove call origin, and the protected route needs an explicit
 * Host-owned gate (see `request-accounting.ts`), not a scope assumption.
 */
test('S1: two live bound children - observed ranges and impersonation', async () => {
  const root = await (await import(pathToFileURL(path.join(stagedBundle, 'lib/session-binding.js')).href) as typeof import('../src/session-binding.js')).createBoundRootAgent(deployment.ctx, {
    bindings,
    sessionId: sessionIdFor('s1-root'),
    task: { taskId: 'task-h04', epoch: 1 },
    cwd: path.join(privateRoot, 'workspace'),
  });

  const dispatchTo = async (label: string) => {
    adapterLabel = label;
    const dispatched = await dispatchModule.dispatchRole(deployment.ctx, {
      parent: root.handle.agent,
      role: 'writer',
      prompt: [{ type: 'text', text: label }],
      signal: new AbortController().signal,
      bindings,
      agentOptions: { provider: MOCK_PROVIDER, model: MOCK_MODEL, maxTokens: 64 },
    });
    await dispatched.run.result;
    return dispatched;
  };

  const a = await dispatchTo('s1-child-a');
  const b = await dispatchTo('s1-child-b');
  const aId = String(a.binding.sessionId);
  const bId = String(b.binding.sessionId);
  const aScope = `agent:${aId}`;
  const bScope = `agent:${bId}`;

  // Both children must still be live before the measurement.
  assert.ok(deployment.ctx.agents.get(aId as SessionId) !== undefined, 'child A must still be registered');
  assert.ok(deployment.ctx.agents.get(bId as SessionId) !== undefined, 'child B must still be registered');
  assert.ok(aScope !== bScope, 'the two child scopes are distinct');

  // Each dispatchRole mints a NEW bound child, so liveness is proven by a third
  // child rather than by reusing A: all three are alive while measuring.
  const beforeC = counts();
  const c = await dispatchTo('s1-child-c');
  const cId = String(c.binding.sessionId);
  const cScope = `agent:${cId}`;
  const aliveDeltas = {
    root: delta(beforeC, 'root-scoped'),
    childA: delta(beforeC, aScope),
    childB: delta(beforeC, bScope),
    childC: delta(beforeC, cScope),
  };
  console.log('S1 live-sibling deltas (dispatch C):', JSON.stringify(aliveDeltas));
  console.log('S1 registered:', JSON.stringify({
    a: deployment.ctx.agents.get(aId as SessionId) !== undefined,
    b: deployment.ctx.agents.get(bId as SessionId) !== undefined,
    c: deployment.ctx.agents.get(cId as SessionId) !== undefined,
  }));
  console.log('S1 observers:', JSON.stringify([...deployment.observations.keys()].sort()));

  const beforeBare = counts();
  const bare: GenerateOptions = {
    provider: MOCK_PROVIDER, model: MOCK_MODEL, maxTokens: 8, messages: [], sessionId: aId as unknown as SessionId,
  };
  adapterLabel = 's1-bare-impersonating-A';
  for await (const _chunk of deployment.ctx.llm.stream(bare)) { /* drain */ }
  const bareSeen = {
    root: delta(beforeBare, 'root-scoped'),
    childA: delta(beforeBare, aScope),
    childB: delta(beforeBare, bScope),
    childC: delta(beforeBare, cScope),
  };
  console.log('S1 bare-dispatch (impersonating A) deltas:', JSON.stringify(bareSeen));

  // Corrected: all three live children observe sibling dispatches. There is no
  // scope isolation on this seam, so zero counts are never evidence of refusal.
  assert.equal(aliveDeltas.childC, 1, 'C observes its own dispatch (listeners are live)');
  assert.equal(aliveDeltas.root, 1, 'the host root observes C');
  assert.equal(aliveDeltas.childA, 1, 'A DOES observe sibling C: no scope isolation');
  assert.equal(aliveDeltas.childB, 1, 'B DOES observe sibling C: no scope isolation');
  // A host bare request naming A is observed by every live child scope, so it is
  // impossible to attribute it by scope alone - the route gate must refuse it.
  assert.equal(bareSeen.childA, 1, 'A observes the bare request naming A');
  assert.equal(bareSeen.childB, 1);
  assert.equal(bareSeen.childC, 1);
  assert.equal(bareSeen.root, 1);
  // Loop vs hand-built, read from the LISTENER observations: with the route
  // registered gated, an unaccounted dispatch never reaches the adapter, so the
  // adapter records cannot carry this contrast (S2 proves the gate separately).
  const rootRows = (deployment.observations.get('root-scoped') ?? []) as { loopMarked?: boolean; frozen?: boolean }[];
  const loopRow = rootRows.find((row) => row.loopMarked === true);
  const bareRow = rootRows.find((row) => row.loopMarked === false);
  assert.equal(loopRow?.frozen, true, 'a loop request arrives deep-frozen');
  assert.equal(bareRow?.frozen, false, 'a hand-built request is not frozen');
  console.log('S1 agent options seen:', JSON.stringify([...agentOptionsSeen.entries()].slice(-3)));

  await c.run.dispose();
  await a.run.dispose();
  await b.run.dispose();
});

// --------------------------------------------------------------------------- //
// R-receipt: the accepted basis is an H04-owned snapshot, never the live object
// --------------------------------------------------------------------------- //

function submittedBinding(sessionId: SessionId): ContractApi.RequestBindingRef {
  return {
    sessionId: sessionId as unknown as ContractApi.RequestBindingRef['sessionId'],
    taskId: 'task-h04', epoch: 7, fence: 3,
    claimId: 'claim-h04', compositionRef: 'composition-h04',
  };
}

function submittedDigest(): ContractApi.RequestDigest {
  return {
    digestVersion: accounting.REQUEST_DIGEST_VERSION, algorithm: 'sha256',
    value: 'a'.repeat(64), parts: ['messages', 'tools', 'config'],
  };
}

function reservationReceipt(overrides: Partial<ContractApi.ReservationReceipt> = {}): ContractApi.ReservationReceipt {
  return {
    contractVersion: contract.REQUEST_CONTRACT_VERSION,
    reservationId: 'res-1', requestId: 'req-1',
    binding: submittedBinding(sessionIdFor('scope')), digest: submittedDigest(),
    grantedAt: 1, ...overrides,
  };
}

test('R-receipt: a mutated live receipt cannot replace the accepted snapshot', () => {
  const expected = { binding: submittedBinding(sessionIdFor('scope')), digest: submittedDigest() };
  const live = reservationReceipt() as unknown as {
    reservationId: string; binding: { fence: number }; digest: { value: string };
  };
  const accepted = accounting.acceptReservation(live as unknown as ContractApi.ReservationReceipt, expected);

  live.binding.fence = 99;
  live.digest.value = 'b'.repeat(64);
  live.reservationId = 'res-mutated';

  assert.equal(accepted.binding.fence, 3, 'accepted binding must be a copy');
  assert.equal(accepted.digest.value, 'a'.repeat(64), 'accepted digest must be a copy');
  assert.equal(accepted.reservationId, 'res-1');
  assert.ok(Object.isFrozen(accepted) && Object.isFrozen(accepted.binding));
});

test('R-receipt: mis-matched reservation receipts are refused by name', () => {
  const expected = { binding: submittedBinding(sessionIdFor('scope')), digest: submittedDigest() };
  const cases: [string, ContractApi.ReservationReceipt, ContractApi.RequestRejectionCode][] = [
    ['contract version', reservationReceipt({ contractVersion: 'other/9' }), 'contract-unsupported'],
    ['binding fence', reservationReceipt({ binding: { ...submittedBinding(sessionIdFor('scope')), fence: 4 } }), 'stale-binding'],
    ['binding claim', reservationReceipt({ binding: { ...submittedBinding(sessionIdFor('scope')), claimId: 'other' } }), 'stale-binding'],
    ['digest', reservationReceipt({ digest: { ...submittedDigest(), value: 'c'.repeat(64) } }), 'digest-mismatch'],
    ['empty request id', reservationReceipt({ requestId: '' }), 'unknown-reservation'],
  ];
  for (const [label, receipt, code] of cases) {
    assert.throws(() => accounting.acceptReservation(receipt, expected), (error: unknown) => {
      assert.ok(error instanceof contract.RequestRejection, `${label}: must be a RequestRejection`);
      assert.equal(error.code, code, label);
      return true;
    }, label);
  }
});

test('R-receipt: dispatch is chained back to the accepted reservation', () => {
  const expected = { binding: submittedBinding(sessionIdFor('scope')), digest: submittedDigest() };
  const accepted = accounting.acceptReservation(reservationReceipt(), expected);
  const good = (overrides: Partial<ContractApi.DispatchReceipt> = {}): ContractApi.DispatchReceipt => ({
    contractVersion: contract.REQUEST_CONTRACT_VERSION,
    requestId: accepted.requestId, reservationId: accepted.reservationId,
    digest: accepted.digest, stage: 'dispatch-recorded', recordedAt: 2, ...overrides,
  });
  assert.equal(accounting.acceptDispatch(good(), accepted, accepted.digest).requestId, 'req-1');
  const bad: [string, ContractApi.DispatchReceipt, ContractApi.RequestRejectionCode][] = [
    ['other reservation', good({ reservationId: 'res-other' }), 'unknown-reservation'],
    ['other request', good({ requestId: 'req-other' }), 'unknown-reservation'],
    ['other digest', good({ digest: { ...submittedDigest(), value: 'd'.repeat(64) } }), 'digest-mismatch'],
    ['other version', good({ contractVersion: 'other/9' }), 'contract-unsupported'],
    ['delivery claim', good({ stage: 'adapter-entered' as never }), 'contract-unsupported'],
  ];
  for (const [label, receipt, code] of bad) {
    assert.throws(() => accounting.acceptDispatch(receipt, accepted, accepted.digest), (error: unknown) => {
      assert.equal((error as { code?: string }).code, code, label);
      return true;
    }, label);
  }
});

// --------------------------------------------------------------------------- //
// R-cap / digest coverage
// --------------------------------------------------------------------------- //

test('R-cap: digest coverage is closed and named', () => {
  const digest = accounting.digestSupportedRequest({
    provider: MOCK_PROVIDER, model: MOCK_MODEL, maxTokens: 16, messages: [],
  } as GenerateOptions);
  assert.deepEqual(digest.parts, ['messages', 'tools', 'config']);
  assert.equal(digest.digestVersion, accounting.REQUEST_DIGEST_VERSION);
  assert.equal(digest.value.length, 64);

  assert.throws(
    () => accounting.digestSupportedRequest({
      provider: MOCK_PROVIDER, model: MOCK_MODEL, messages: [], futureField: 1,
    } as unknown as GenerateOptions),
    (error: unknown) => (error as { code?: string }).code === 'contract-unsupported',
  );

  const base = { provider: MOCK_PROVIDER, model: MOCK_MODEL, messages: [{ role: 'user', content: 'a' }] };
  const mutated = { provider: MOCK_PROVIDER, model: MOCK_MODEL, messages: [{ role: 'user', content: 'b' }] };
  assert.notEqual(
    accounting.digestSupportedRequest(base as unknown as GenerateOptions).value,
    accounting.digestSupportedRequest(mutated as unknown as GenerateOptions).value,
  );
});

// --------------------------------------------------------------------------- //
// S2: the trusted authorization source
// --------------------------------------------------------------------------- //

/**
 * A legally bound child must dispatch; an impersonated identity, a copied digest
 * and a replay must not obtain authorization. The route is registered gated, so
 * the underlying recorder adapter is only reachable through a live one-time
 * authorization minted by the middleware.
 */
test('S2: only a proven loop origin obtains a dispatch authorization', async () => {
  const sessionApi = await import(pathToFileURL(path.join(stagedBundle, 'lib/session-binding.js')).href) as typeof import('../src/session-binding.js');
  const root = await sessionApi.createBoundRootAgent(deployment.ctx, {
    bindings,
    sessionId: sessionIdFor('s2-root'),
    task: { taskId: 'task-h04-s2', epoch: 1 },
    cwd: path.join(privateRoot, 'workspace'),
  });
  // The accounting middleware is installed only here: S1 measures the raw
  // waterfall fan-out, and a refusing middleware legitimately vetoes the chain
  // (it does not call `next()`), which would hide later listeners from S1.
  installed = accounting.installRequestAccounting(deployment.ctx, {
    bindings,
    recorder: recorder as unknown as ContractApi.RequestRecorder,
    route: MOCK_PROVIDER,
    purpose: 'writer',
    outputCap: { version: 'h04-test-cap/1', cap: () => 512 },
    authorizations,
    isProtectedAgent: () => true,
    diagnostics: (event: { kind: string; detail: string }) => {
      arrivalFacts.push(`accounting:${event.kind}:${event.detail}`);
    },
  });

  // 1. Legal: a real bound child's loop dispatch reaches the underlying adapter.
  const underlyingBefore = adapterRecords.length;
  const eventsBefore = recorder.events.length;
  adapterLabel = 's2-legal';
  const legal = await dispatchModule.dispatchRole(deployment.ctx, {
    parent: root.handle.agent,
    role: 'writer',
    prompt: [{ type: 'text', text: 'legal' }],
    signal: new AbortController().signal,
    bindings,
    agentOptions: { provider: MOCK_PROVIDER, model: MOCK_MODEL, maxTokens: 64 },
  });
  await legal.run.result;
  const legalSession = String(legal.binding.sessionId);
  if (adapterRecords.length - underlyingBefore !== 1) {
    console.log('S2 arrival facts:', JSON.stringify(arrivalFacts.slice(-25), null, 0));
    console.log('S2 recorder events:', JSON.stringify(recorder.events.slice(eventsBefore)));
    console.log('S2 route diagnostics:', JSON.stringify(routeDiagnostics.slice(-10)));
    console.log('S2 run result:', JSON.stringify(await legal.run.result));
  }
  assert.equal(adapterRecords.length - underlyingBefore, 1, 'the legal child dispatch reaches the adapter');
  assert.deepEqual(recorder.events.slice(eventsBefore), ['reserve:1', 'dispatch', 'settle:settled']);
  assert.ok(routeDiagnostics.some((row) => row.startsWith('authorized:')), 'the gate authorized it');

  // 2. Impersonation: a hand-built request naming the live child session has no
  //    loop preparation, so it never gets an authorization and never reaches the
  //    underlying adapter.
  const impersonationBefore = adapterRecords.length;
  adapterLabel = 's2-impersonation';
  const impersonated: GenerateOptions = {
    provider: MOCK_PROVIDER, model: MOCK_MODEL, maxTokens: 64, messages: [],
    sessionId: legalSession as unknown as SessionId,
  };
  const impersonationChunks: StreamChunk[] = [];
  for await (const chunk of deployment.ctx.llm.stream(impersonated)) impersonationChunks.push(chunk);
  assert.equal(adapterRecords.length, impersonationBefore, 'impersonation never reaches the adapter');
  assert.ok(
    impersonationChunks.some((chunk) =>
      chunk.type === 'finish' && typeof chunk.reason !== 'string' && chunk.reason.kind === 'error'
      && String(chunk.reason.failure.code) === 'dispatch_origin_unproven'),
    `impersonation must be refused by name: ${JSON.stringify(impersonationChunks)}`,
  );
  assert.ok(
    arrivalFacts.some((row) => row.includes('scope-refused') && (
      row.includes('no loop preparation for this request signal')
      || row.includes('public surface dispatch claims a protected session without a loop origin'))),
    'the refusal is a named diagnostic');

  // 3. Copied digest: an authorization issued for one assembly does not open a
  //    different assembly, because the digest is recomputed from the material.
  const registry = new accounting.DispatchAuthorizations();
  const assemblyA: GenerateOptions = {
    provider: MOCK_PROVIDER, model: MOCK_MODEL, maxTokens: 32,
    messages: [{ role: 'user', content: 'A' }],
    sessionId: 's' as SessionId,
  } as unknown as GenerateOptions;
  const assemblyB: GenerateOptions = {
    provider: MOCK_PROVIDER, model: MOCK_MODEL, maxTokens: 32,
    messages: [{ role: 'user', content: 'B' }],
    sessionId: 's' as SessionId,
  } as unknown as GenerateOptions;
  const assemblyOtherSession: GenerateOptions = {
    provider: MOCK_PROVIDER, model: MOCK_MODEL, maxTokens: 32,
    messages: [{ role: 'user', content: 'A' }],
    sessionId: 'other-session' as SessionId,
  } as unknown as GenerateOptions;
  const digestA = accounting.digestSupportedRequest(assemblyA);
  registry.issue({
    requestId: 'req-copy', reservationId: 'res-copy', sessionId: 's', provider: MOCK_PROVIDER,
    digestValue: digestA.value,
  });
  assert.equal(registry.consume(assemblyB), undefined,
    'a copied digest on different material must not match');
  assert.equal(registry.consume(assemblyOtherSession), undefined,
    'the same digest in another session must not take the authorization');
  assert.equal(registry.outstanding, 1, 'the authorization is still unspent');

  // 4. Replay: the same assembly consumes its authorization exactly once.
  assert.ok(registry.consume(assemblyA) !== undefined, 'the authorized assembly is admitted once');
  assert.equal(registry.consume(assemblyA), undefined, 'replaying the same assembly is refused');
  assert.equal(registry.outstanding, 0);

  // 5. A protected session may not leave the Host-owned route.
  const foreignBefore = adapterRecords.length;
  const foreign: GenerateOptions = {
    provider: 'some-other-route', model: MOCK_MODEL, maxTokens: 8, messages: [],
    sessionId: legalSession as unknown as SessionId,
  };
  const foreignChunks: StreamChunk[] = [];
  for await (const chunk of deployment.ctx.llm.stream(foreign)) foreignChunks.push(chunk);
  assert.equal(adapterRecords.length, foreignBefore, 'a foreign route is not routed to this adapter');
  assert.ok(
    foreignChunks.some((chunk) =>
      chunk.type === 'finish' && typeof chunk.reason !== 'string' && chunk.reason.kind === 'error'
      && ['protected_route_mismatch', 'dispatch_origin_unproven'].includes(String(chunk.reason.failure.code))),
    `switching provider must not exit accounting: ${JSON.stringify(foreignChunks)}`,
  );

  await legal.run.dispose();
  await root.dispose();
  installed.dispose();
});
