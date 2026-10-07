/**
 * H02 session binding: the trusted task/epoch/fence identity of one agent.
 *
 * ## Authority boundary
 *
 * The claim authority is Python's `task_store` (R01–R03). This module consumes a
 * {@link ClaimRecorder} seam and nothing else: it does not mint identities, does
 * not deduct budget, and keeps no durable ledger. The registry here is a
 * process-local cache of *granted* receipts, discarded with the composition.
 * H02 ships no recorder implementation at all — its test uses an explicitly
 * labeled mock, and production wiring is R01–R03's.
 *
 * ## Why the binding happens inside `setup`
 *
 * `agents.create({ setup })` awaits setup while the agent is unpublished, so
 * everything registered there exists before `session/created`, `agent/created`,
 * `agent/session-start` and the first prompt assembly. Binding anywhere later —
 * an async `agent/created` listener, `agent/pre-step` (which runs after prompt
 * assembly), or after `start()` returned a handle — would leave a window in
 * which material was read or a model request was issued for an unbound agent.
 * {@link SessionBindings.bind} therefore records `boundIn: 'creation-window'`
 * and the only supported call site is a creation-window setup.
 *
 * ## What a binding is and is not
 *
 * It is the Host's record that *this* session runs under *that* granted claim.
 * It is not a capability: model-visible strings that name a task, epoch or fence
 * are untrusted input, and {@link SessionBindings.assertTrusted} is the only
 * place they may be compared against the trusted record. It is also not the
 * authority to send: the request ledger (R02) and the domain result owner decide
 * separately.
 */

import type { Context } from '@deepseek-ai/cordis';
import type { Agent, AgentHandle } from '@deepseek-ai/dsh-agent';
import type { SessionId } from '@deepseek-ai/dsh-session';

import { mountCode2PaperPreset } from './index.js';

/**
 * Trusted caller identity, injected by the Host that owns the composition. It is
 * never derived from model input, session metadata, or a request field.
 */
export interface CallerRef {
  /** Host execution this composition runs under (one per launched run). */
  readonly executionId: string;
  /** The run identity the Host recorded for this composition. */
  readonly runId: string;
  /** Host-composition generation, so two hosts in one process stay distinguishable. */
  readonly hostGeneration: number;
}

/** The claimed work identity: one task at one epoch. */
export interface TaskRef {
  /** Stable task identity from the Python task store. */
  readonly taskId: string;
  /** Attempt epoch; a new epoch is a new authority for the same task. */
  readonly epoch: number;
}

/** Why a claim is being requested. */
export type ClaimPurpose = 'root' | 'child';

/** One claim request, as the authority receives it. */
export interface ClaimRequest {
  /** Trusted caller the claim is granted to. */
  readonly caller: CallerRef;
  /** Task and epoch being claimed. */
  readonly task: TaskRef;
  /** Whether this grant establishes a root session or a delegated child. */
  readonly purpose: ClaimPurpose;
  /** The parent's claim, for a child grant. */
  readonly parentClaimId?: string;
}

/**
 * One granted claim, as the authority returns it.
 *
 * `fence` is the monotone generation of the (task, epoch) grant: a later grant
 * for the same task and epoch carries a higher fence and supersedes earlier
 * ones. Everything else is opaque identity this module only compares.
 */
export interface ClaimReceipt {
  /** Identity of this grant. */
  readonly claimId: string;
  /** Task the grant belongs to; must echo the request. */
  readonly taskId: string;
  /** Epoch the grant belongs to; must echo the request. */
  readonly epoch: number;
  /** Monotone grant generation for this (task, epoch). */
  readonly fence: number;
  /** Composition identity the authority bound the grant to. */
  readonly compositionRef: string;
  /** Authority-side grant time, in epoch milliseconds. */
  readonly grantedAt: number;
}

/**
 * The claim seam.
 *
 * **Production implementation is Python's task store (R01–R03).** H02 consumes
 * this interface only; its test provides an explicitly labeled mock with delay,
 * refusal and cancellation injection points. A recorder must not be built in
 * TypeScript as a second durable authority.
 */
export interface ClaimRecorder {
  /**
   * Await one grant.
   * @param request - trusted caller, task, epoch, and purpose.
   * @param options - caller cancellation for the wait itself.
   * @returns the granted receipt.
   * @throws when the authority refuses, or when `options.signal` aborts the wait.
   */
  claim(request: ClaimRequest, options?: { readonly signal?: AbortSignal }): Promise<ClaimReceipt>;
}

/** A granted claim together with the identity it was granted to. */
export interface GrantedTask {
  /** Trusted caller the grant belongs to. */
  readonly caller: CallerRef;
  /** Task and epoch, echoed from the receipt. */
  readonly task: TaskRef;
  /** The authority's receipt. */
  readonly receipt: ClaimReceipt;
}

/** One agent's trusted binding, as recorded in its creation window. */
export interface SessionBinding extends GrantedTask {
  /** The bound session. */
  readonly sessionId: SessionId;
  /** The delegating parent session, for a child binding. */
  readonly parentSessionId?: SessionId;
  /** Always `creation-window`; no other binding site is supported. */
  readonly boundIn: 'creation-window';
}

/** Why a binding operation was refused. Stable codes; callers branch on these. */
export type BindingRejectionCode =
  /** The claim authority refused the request. */
  | 'claim-rejected'
  /** The claim wait was cancelled before a receipt arrived. */
  | 'claim-aborted'
  /** The presented receipt or fence is not the current grant for that task/epoch. */
  | 'stale-fence'
  /** The trusted binding itself is superseded: its grant is no longer current. */
  | 'stale-binding'
  /** The named subagent provider is not a registration this Host made for this binding registry. */
  | 'unbound-provider'
  /** The provider is registered, but for a different binding registry than this delegation uses. */
  | 'misbound-provider'
  /** An untrusted task/epoch string does not match the trusted binding. */
  | 'forged-task-id'
  /** No trusted binding exists for the subject. */
  | 'unbound-agent'
  /** The parent has no trusted binding, so a child cannot inherit one. */
  | 'unbound-parent'
  /** The child did not join its parent's standing composition. */
  | 'unbound-child'
  /** Agent creation was cancelled; nothing was published. */
  | 'creation-aborted';

/** A refused binding operation, carrying a stable {@link BindingRejectionCode}. */
export class BindingRejection extends Error {
  /** Stable rejection code. */
  readonly code: BindingRejectionCode;

  constructor(code: BindingRejectionCode, message: string, options?: { readonly cause?: unknown }) {
    super(message, options);
    this.name = 'BindingRejection';
    this.code = code;
  }
}

/** Options for {@link SessionBindings}. */
export interface SessionBindingsOptions {
  /** Trusted caller identity for every grant this instance requests. */
  readonly caller: CallerRef;
  /** The claim authority seam. */
  readonly recorder: ClaimRecorder;
}

/** Inputs for {@link SessionBindings.claim}. */
export interface ClaimInput {
  /** Task and epoch to claim. */
  readonly task: TaskRef;
  /** Root or child grant. */
  readonly purpose: ClaimPurpose;
  /** The parent's claim id, for a child grant. */
  readonly parentClaimId?: string;
  /** Cancellation for the claim wait. */
  readonly signal?: AbortSignal;
}

/** An untrusted identity hint, as it may arrive from a prompt or a request. */
export interface TaskIdentityHint {
  /** Claimed task id string. */
  readonly taskId?: string;
  /** Claimed epoch. */
  readonly epoch?: number;
  /** Claimed fence. */
  readonly fence?: number;
}

function taskKey(taskId: string, epoch: number): string {
  return `${taskId}@${String(epoch)}`;
}

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/**
 * Read a signal's abort state through a function boundary.
 *
 * Control-flow narrowing would otherwise freeze the first read for the rest of
 * the flow, and a cancellation that arrives while a claim is in flight is
 * exactly the case that must still be observed.
 */
function isAborted(signal: AbortSignal | undefined): boolean {
  return signal !== undefined && signal.aborted;
}

/**
 * The process-local binding registry plus the claim seam it consumes.
 *
 * One instance belongs to one Host composition. It is *not* durable: dropping it
 * loses only the cache, never the authority, and R01–R03 re-establish grants
 * from the Python task store on recovery.
 */
export class SessionBindings {
  private readonly caller: CallerRef;
  private readonly recorder: ClaimRecorder;
  private readonly bindings = new Map<string, SessionBinding>();
  private readonly fences = new Map<string, number>();
  private readonly receipts = new Map<string, ClaimReceipt>();

  constructor(options: SessionBindingsOptions) {
    this.caller = options.caller;
    this.recorder = options.recorder;
  }

  /** Number of live bindings. */
  get size(): number {
    return this.bindings.size;
  }

  /**
   * Await one grant from the authority. Creates nothing and reads no material.
   * @param input - task, purpose, optional parent claim, and cancellation.
   * @returns the granted task.
   * @throws {BindingRejection} `claim-aborted` when the wait was cancelled,
   *   `claim-rejected` when the authority refused, `stale-fence` when the
   *   authority returned a receipt older than the current grant.
   */
  async claim(input: ClaimInput): Promise<GrantedTask> {
    const request: ClaimRequest = {
      caller: this.caller,
      task: input.task,
      purpose: input.purpose,
      ...(input.parentClaimId === undefined ? {} : { parentClaimId: input.parentClaimId }),
    };
    let receipt: ClaimReceipt;
    try {
      receipt = await this.recorder.claim(request, input.signal === undefined ? undefined : { signal: input.signal });
    } catch (error) {
      if (isAborted(input.signal)) {
        throw new BindingRejection(
          'claim-aborted',
          `claim for ${taskKey(input.task.taskId, input.task.epoch)} was cancelled before a receipt`,
          { cause: error },
        );
      }
      throw new BindingRejection(
        'claim-rejected',
        `claim authority refused ${taskKey(input.task.taskId, input.task.epoch)}: ${describe(error)}`,
        { cause: error },
      );
    }
    // A receipt that raced the cancellation is not a usable grant.
    if (isAborted(input.signal)) {
      throw new BindingRejection(
        'claim-aborted',
        `claim for ${taskKey(input.task.taskId, input.task.epoch)} was cancelled as its receipt arrived`,
      );
    }
    if (receipt.taskId !== input.task.taskId || receipt.epoch !== input.task.epoch) {
      throw new BindingRejection(
        'forged-task-id',
        `claim authority returned ${taskKey(receipt.taskId, receipt.epoch)} for ${taskKey(input.task.taskId, input.task.epoch)}`,
      );
    }
    this.accept(receipt);
    return { caller: this.caller, task: { taskId: receipt.taskId, epoch: receipt.epoch }, receipt };
  }

  /**
   * Install a binding for one session. The only supported call site is a
   * creation-window `setup`, which is why the record says so.
   * @param sessionId - the session being created.
   * @param granted - the granted task, from {@link claim}.
   * @param options - the delegating parent session, for a child binding.
   * @returns the installed binding.
   * @throws {BindingRejection} `stale-fence` when the grant is no longer current.
   */
  bind(sessionId: SessionId, granted: GrantedTask, options?: { readonly parentSessionId?: SessionId }): SessionBinding {
    const key = taskKey(granted.task.taskId, granted.task.epoch);
    if (this.fences.get(key) !== granted.receipt.fence) {
      throw new BindingRejection(
        'stale-fence',
        `claim ${granted.receipt.claimId} (fence ${String(granted.receipt.fence)}) is not the current grant for ${key}`,
      );
    }
    const binding: SessionBinding = {
      sessionId,
      caller: this.caller,
      task: granted.task,
      receipt: granted.receipt,
      boundIn: 'creation-window',
      ...(options?.parentSessionId === undefined ? {} : { parentSessionId: options.parentSessionId }),
    };
    this.bindings.set(sessionId, binding);
    return binding;
  }

  /**
   * Drop a binding whose creation rolled back. Rollback-only: a published agent
   * keeps its binding until the composition is disposed.
   * @param sessionId - the session whose binding must be released.
   */
  release(sessionId: SessionId): void {
    this.bindings.delete(sessionId);
  }

  /**
   * Read the trusted binding for a session or live agent.
   * @param subject - session id or agent.
   * @returns the binding, or undefined when the subject was never bound.
   */
  resolve(subject: SessionId | Agent): SessionBinding | undefined {
    return this.bindings.get(typeof subject === 'string' ? subject : subject.session.id);
  }

  /**
   * Read the trusted binding or refuse.
   *
   * A plain read: it answers "was this session bound", not "may it still act".
   * Authority-bearing paths use {@link requireCurrent}, which also refuses a
   * binding whose grant has been superseded.
   *
   * @param subject - session id or agent.
   * @returns the binding.
   * @throws {BindingRejection} `unbound-agent`.
   */
  require(subject: SessionId | Agent): SessionBinding {
    const binding = this.resolve(subject);
    if (binding === undefined) {
      throw new BindingRejection('unbound-agent', 'no trusted binding for this agent; bind inside the creation window');
    }
    return binding;
  }

  /**
   * Read the trusted binding for an authority-bearing operation, refusing one
   * whose grant is no longer current.
   *
   * This is the check that makes a superseded binding stop authorizing on its
   * own: no caller-supplied fence hint is needed, and no hint can upgrade an old
   * binding, because the record itself is compared against the current grant.
   *
   * @param subject - session id or agent.
   * @returns the still-current binding.
   * @throws {BindingRejection} `unbound-agent`, or `stale-binding` when the
   *   binding's grant was superseded for its task and epoch.
   */
  requireCurrent(subject: SessionId | Agent): SessionBinding {
    const binding = this.require(subject);
    const current = this.currentFence(binding.task);
    if (current !== binding.receipt.fence) {
      throw new BindingRejection(
        'stale-binding',
        `binding of ${binding.sessionId} holds fence ${String(binding.receipt.fence)} but ${taskKey(binding.task.taskId, binding.task.epoch)} is at ${String(current)}`,
      );
    }
    return binding;
  }

  /**
   * Compare an untrusted identity hint against the trusted binding. This is the
   * only place model- or request-supplied task strings may be read.
   * @param subject - session id or agent whose trusted binding is authoritative.
   * @param hint - untrusted task/epoch/fence values.
   * @returns the trusted binding when every supplied field matches.
   * @throws {BindingRejection} `unbound-agent`, `stale-binding`, `forged-task-id`, or `stale-fence`.
   */
  assertTrusted(subject: SessionId | Agent, hint: TaskIdentityHint): SessionBinding {
    // The binding's own validity is checked first and unconditionally: a hint
    // that matches the current grant cannot make a superseded parent current.
    const binding = this.requireCurrent(subject);
    if (hint.taskId !== undefined && hint.taskId !== binding.task.taskId) {
      throw new BindingRejection(
        'forged-task-id',
        `presented task id ${JSON.stringify(hint.taskId)} is not the bound task ${JSON.stringify(binding.task.taskId)}`,
      );
    }
    if (hint.epoch !== undefined && hint.epoch !== binding.task.epoch) {
      throw new BindingRejection(
        'forged-task-id',
        `presented epoch ${String(hint.epoch)} is not the bound epoch ${String(binding.task.epoch)}`,
      );
    }
    if (hint.fence !== undefined && hint.fence !== this.currentFence(binding.task)) {
      throw new BindingRejection(
        'stale-fence',
        `presented fence ${String(hint.fence)} is not the current fence ${String(this.currentFence(binding.task))}`,
      );
    }
    return binding;
  }

  /**
   * The current grant generation for one task and epoch.
   * @param task - the task and epoch.
   * @returns the fence, or undefined when nothing was granted.
   */
  currentFence(task: TaskRef): number | undefined {
    return this.fences.get(taskKey(task.taskId, task.epoch));
  }

  /** Discard every cached binding and grant. The authority is unaffected. */
  dispose(): void {
    this.bindings.clear();
    this.fences.clear();
    this.receipts.clear();
  }

  /** Record one granted receipt, refusing a grant older than the current one. */
  private accept(receipt: ClaimReceipt): void {
    const key = taskKey(receipt.taskId, receipt.epoch);
    const current = this.fences.get(key);
    if (current !== undefined && receipt.fence < current) {
      throw new BindingRejection(
        'stale-fence',
        `claim authority returned fence ${String(receipt.fence)} below the current ${String(current)} for ${key}`,
      );
    }
    this.fences.set(key, receipt.fence);
    this.receipts.set(receipt.claimId, receipt);
  }
}

/** Options for {@link createBoundRootAgent}. */
export interface BoundRootOptions {
  /** The binding registry that owns the claim seam. */
  readonly bindings: SessionBindings;
  /** Identity the Host reserved for this root session. */
  readonly sessionId: SessionId;
  /** Task and epoch to claim before creating anything. */
  readonly task: TaskRef;
  /** Absolute working directory recorded on the session. */
  readonly cwd: string;
  /** Preset to compose the root agent from; defaults to the bundle's configured one. */
  readonly presetId?: string;
  /** Creation cancellation, owning the whole operation. */
  readonly signal?: AbortSignal;
  /**
   * Material read for this task (the Host's projection step, C00). Invoked only
   * after a granted receipt and before agent creation, so a blocked or refused
   * claim can never read material.
   */
  readonly material?: (granted: GrantedTask) => Promise<void>;
}

/** A published root agent and its trusted binding. */
export interface BoundRoot {
  /** The owned agent handle; dispose through {@link BoundRoot.dispose}. */
  readonly handle: AgentHandle;
  /** The binding installed in the creation window. */
  readonly binding: SessionBinding;
  /**
   * Dispose the agent and drop its binding together.
   *
   * A binding describes one live session, so it must not outlive it: a resumed
   * session re-establishes its authority from the claim recorder (R01–R03)
   * instead of inheriting a stale in-memory record. Disposing through this owner
   * is the supported teardown; disposing the raw handle leaves the cached binding
   * behind until the composition is disposed.
   */
  dispose(): Promise<void>;
}

/**
 * Claim first, then create: await the authority's receipt, read material, and
 * create the root agent with its binding installed inside `setup`.
 *
 * The caller context must inject `agents` (creation) and `code2paperBridge`
 * (composition), which is why this is a function of the caller rather than of
 * the agent scope.
 *
 * @param caller - the Host context that owns the created agent.
 * @param options - identity, task, workspace, optional material port and cancellation.
 * @returns the published handle and its binding.
 * @throws {BindingRejection} on refusal or cancellation; nothing is published then.
 */
export async function createBoundRootAgent(caller: Context, options: BoundRootOptions): Promise<BoundRoot> {
  const granted = await options.bindings.claim({
    task: options.task,
    purpose: 'root',
    ...(options.signal === undefined ? {} : { signal: options.signal }),
  });
  if (options.material !== undefined) await options.material(granted);
  if (isAborted(options.signal)) {
    throw new BindingRejection('creation-aborted', 'root creation was cancelled before the agent was created');
  }
  let handle: AgentHandle;
  try {
    handle = await caller.agents.create({
      sessionId: options.sessionId,
      meta: { cwd: options.cwd },
      ...(options.signal === undefined ? {} : { signal: options.signal }),
      setup: async (agentCtx, agent) => {
        await mountCode2PaperPreset(caller, agentCtx, options.presetId);
        options.bindings.bind(agent.session.id, granted);
      },
    });
  } catch (error) {
    options.bindings.release(options.sessionId);
    if (isAborted(options.signal)) {
      throw new BindingRejection('creation-aborted', 'root creation was cancelled; nothing was published', { cause: error });
    }
    throw error;
  }
  return {
    handle,
    binding: options.bindings.require(handle.agent.session.id),
    async dispose(): Promise<void> {
      try {
        await handle.dispose();
      } finally {
        options.bindings.release(handle.agent.session.id);
      }
    },
  };
}
