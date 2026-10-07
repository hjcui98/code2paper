/**
 * H02 role dispatch: the narrow public `c2p-spawn` subagent provider.
 *
 * ## Why a narrow provider instead of the standard `spawn`
 *
 * The frozen 0.1.5-rc.3 standard spawn path cannot bind a task identity before
 * the child's first prompt is delivered. `SubagentStartRequest` carries only
 * data (`label`, `prompt`, `parent`, `signal`, `agentOptions`, `outputSchema`,
 * `maxDepth`, `toolFilter`, `persona`) — no setup hook — and the driver's own
 * creation window is a fixed closure that composes the child and returns; the
 * prompt is delivered to the child's inbox before `ctx.subagents.start()`
 * resolves. The only later moments a caller can observe (`agent/created`,
 * `agent/pre-step`) are announcements, not a binding site. `binding.test.ts`
 * records that measurement.
 *
 * This provider therefore calls the PUBLIC `agents.create({ setup })` and
 * composes the child with the same public helpers the standard driver uses
 * (`@deepseek-ai/dsh-subagent`'s `childSessionMeta`, `resolveChildDepth`,
 * `resolveChildAgentOptions`, `applyChildComposition`,
 * `captureDelegatedPolicyOverrides`, `appendDelegatedPolicyOverrides`). It does
 * not replace the global loop factory, does not import a private helper, and
 * adds exactly one thing inside the creation window: the trusted binding.
 *
 * ## Capabilities it does NOT claim
 *
 * `outputSchema`, `persona` and `toolFilter` are declared unsupported, so the
 * service refuses a request that asks for them instead of silently ignoring it.
 * Structured output belongs to H03's terminal contract; persona and tool scoping
 * have no H02 consumer.
 */

import { randomUUID } from 'node:crypto';

import type { Context } from '@deepseek-ai/cordis';
import { foldConsumedWork, type Agent, type AgentHandle, type AgentOptions } from '@deepseek-ai/dsh-agent';
import { standingMountFor } from '@deepseek-ai/dsh-agent-preset-registry';
import { createUserMessage, type ContentBlock } from '@deepseek-ai/dsh-llm';
import { SessionId, SessionLogOffset, type Session } from '@deepseek-ai/dsh-session';
import {
  appendDelegatedPolicyOverrides,
  applyChildComposition,
  captureDelegatedPolicyOverrides,
  childSessionMeta,
  finalAssistantOutput,
  resolveChildAgentOptions,
  resolveChildDepth,
  type ResolvedSubagentStartRequest,
  type SubagentProvider,
  type SubagentResult,
  type SubagentRun,
  type SubagentStopReason,
} from '@deepseek-ai/dsh-subagent';

import { BindingRejection, type SessionBinding, type SessionBindings, type GrantedTask } from './session-binding.js';

/** Registry name of the narrow Code2Paper spawn provider. */
export const CODE2PAPER_SPAWN_PROVIDER = 'c2p-spawn';

/**
 * Protocol tag a delegation provider declares.
 *
 * The tag states INTENT only: it is a public, forgeable string, so it never
 * authorizes a delegation on its own. Admission is decided by
 * {@link registerCode2PaperSpawn}'s process-local registration record, which binds
 * one provider OBJECT to the {@link SessionBindings} it was registered for (see
 * {@link isBoundDelegationProvider} for the diagnostic-only predicate).
 */
export const BINDING_PROTOCOL = 'c2p-trusted-binding/1';

/**
 * Whether one provider object merely DECLARES {@link BINDING_PROTOCOL}.
 *
 * Diagnostic only: a foreign object can carry the same string, so this predicate
 * must not gate a send. {@link dispatchRole} checks the registration record.
 */
export function isBoundDelegationProvider(provider: SubagentProvider | undefined): boolean {
  return (provider as { readonly bindingProtocol?: string } | undefined)?.bindingProtocol === BINDING_PROTOCOL;
}

/**
 * Process-local record that THIS module registered one provider object for one
 * binding registry.
 *
 * It is execution-object ownership inside this process — not a second task
 * authority, not durable state, and not a budget: it answers only "did this Host
 * hand this exact provider object to this exact registry, and is that
 * registration still live".
 */
interface ProviderAdmission {
  /** The binding registry this object was registered for. */
  readonly bindings: SessionBindings;
  /** The registry name it was registered under. */
  readonly providerName: string;
  /** Set by the registration's disposer; a revoked registration never authorizes. */
  revoked: boolean;
}

/** Admissions keyed by provider OBJECT identity, so a look-alike cannot inherit one. */
const admissions = new WeakMap<SubagentProvider, ProviderAdmission>();

/** Options for {@link Code2PaperSpawnProvider} and {@link registerCode2PaperSpawn}. */
export interface Code2PaperSpawnOptions {
  /** The binding registry that owns the claim seam. */
  readonly bindings: SessionBindings;
  /** Host-private durable binding; awaited before the child is published. */
  readonly persistChildBinding?: (child: Agent, grant: GrantedTask) => Promise<void>;
  /** Registry name override for the default provider; defaults to {@link CODE2PAPER_SPAWN_PROVIDER}. */
  readonly providerName?: string;
  /**
   * A Host-owned provider object to register instead of the bundle's default.
   *
   * The object is registered by this module, so it receives the same admission
   * record and the same checks as the default provider — this is not a bypass.
   * A remote or alternative implementation registers here; its `name` is the
   * registry name used, and the optional protocol tag is carried through as the
   * (non-authoritative) intent marker.
   */
  readonly provider?: SubagentProvider & { readonly bindingProtocol?: string };
}

/** A registered provider and its exact disposer. */
export interface SpawnRegistration {
  /** The name the provider is registered under. */
  readonly providerName: string;
  /** Cordis effect disposer; removing the provider blocks new starts only. */
  readonly dispose: () => void;
}

/**
 * Map one turn-end reason onto the subagent seam's stop vocabulary.
 * @param reason - the `turn/end` reason, when a turn closed.
 * @returns the seam's stop reason.
 */
function toStopReason(reason: { readonly kind?: string } | undefined): SubagentStopReason {
  switch (reason?.kind) {
    case 'completed': return 'completed';
    case 'max-tokens': return 'max-tokens';
    case 'aborted': return 'aborted';
    case 'blocked': return 'refusal';
    default: return 'error';
  }
}

/**
 * Read a settled child's terminal result from its own log.
 *
 * H02 needs a truthful stop reason, not the domain result: H03 owns the typed
 * terminal, and C03 owns the domain object. Only public readers are used.
 *
 * @param session - the child session.
 * @param cancelled - whether the run was cancelled through its signal or disposal.
 * @returns the child's output blocks and stop reason.
 */
function readRunResult(session: Session, cancelled: boolean): SubagentResult {
  const events = session.snapshotEvents(SessionLogOffset(0));
  const end = foldConsumedWork(events).end;
  const output = finalAssistantOutput(events) ?? [];
  const recorded = toStopReason(end?.data.reason);
  return { output, stopReason: cancelled && recorded !== 'completed' ? 'aborted' : recorded };
}

/**
 * The narrow Code2Paper delegation provider.
 *
 * One instance per Host composition. It mints the child session id, claims the
 * child grant BEFORE creating anything, and installs the child's binding inside
 * the creation window; everything else is the frozen runtime's own delegation
 * composition.
 */
export class Code2PaperSpawnProvider implements SubagentProvider {
  /** Registry name. */
  readonly name: string;

  /** Start-time features this provider supports; the rest are refused loudly. */
  readonly capabilities = {
    agentOptions: true,
    outputSchema: false,
    depthLimit: true,
    toolFilter: false,
    persona: false,
  } as const;

  /** A fresh child sees no parent history. */
  readonly inheritsParentContext = false;

  /** Marks this provider as implementing {@link BINDING_PROTOCOL}. */
  readonly bindingProtocol = BINDING_PROTOCOL;

  private readonly bindings: SessionBindings;
  private readonly persistChildBinding: Code2PaperSpawnOptions['persistChildBinding'];

  constructor(options: Code2PaperSpawnOptions) {
    this.bindings = options.bindings;
    this.persistChildBinding = options.persistChildBinding;
    this.name = options.providerName ?? CODE2PAPER_SPAWN_PROVIDER;
  }

  /**
   * Establish one bound child.
   *
   * Order is the whole point: resolve the parent's trusted binding, verify the
   * parent runs a preset composition, claim the child grant, and only then create
   * the agent — with the binding installed in `setup`. A refusal at any step
   * leaves no published child, no binding and no turn.
   *
   * @param request - the service-resolved start request (descriptor included).
   * @returns the published run.
   * @throws {BindingRejection} `unbound-parent`, `unbound-child`, `claim-*`, `creation-aborted`.
   */
  async start(request: ResolvedSubagentStartRequest): Promise<SubagentRun> {
    const parent = request.parent;
    // The parent's own record must still be current: a superseded grant stops
    // authorizing here, before any child claim or creation, with no hint needed.
    let parentBinding;
    try {
      parentBinding = this.bindings.requireCurrent(parent);
    } catch (error) {
      if (error instanceof BindingRejection && error.code === 'unbound-agent') {
        throw new BindingRejection(
          'unbound-parent',
          `subagent parent ${parent.session.id} has no trusted binding; delegation requires a bound parent`,
          { cause: error },
        );
      }
      throw error;
    }
    // The parent must actually be joined to a standing composition. The standard
    // composition helper's join is optional-chained, so this is checked here and
    // re-checked on the child below: an absent join is a failure, never success.
    if (standingMountFor(parent.ctx) === undefined) {
      throw new BindingRejection(
        'unbound-child',
        `subagent parent ${parent.session.id} joined no preset; a child would compose nothing`,
      );
    }

    const childGrant = await this.bindings.claim({
      task: parentBinding.task,
      purpose: 'child',
      parentClaimId: parentBinding.receipt.claimId,
      signal: request.signal,
    });
    if (request.signal.aborted) {
      throw new BindingRejection('creation-aborted', 'delegation was cancelled before the child was created');
    }

    const childDepth = resolveChildDepth(parent, request.maxDepth);
    const inheritedPolicy = captureDelegatedPolicyOverrides(parent);
    const childId = SessionId(randomUUID());
    let handle: AgentHandle;
    try {
      handle = await parent.ctx.agents.create({
        sessionId: childId,
        parentAgent: parent,
        meta: childSessionMeta(parent, childDepth, false),
        agentOptions: resolveChildAgentOptions(parent, request.agentOptions, childDepth),
        signal: request.signal,
        setup: async (childCtx, child) => {
          // The frozen delegation composition: join the parent's standing
          // generation and register the delegation-scope context.
          applyChildComposition(childCtx, parent, {});
          if (standingMountFor(childCtx) === undefined) {
            throw new BindingRejection(
              'unbound-child',
              `child ${child.session.id} did not join its parent's standing composition`,
            );
          }
          appendDelegatedPolicyOverrides(child.session, inheritedPolicy);
          await this.persistChildBinding?.(child, childGrant);
          if (request.signal.aborted) throw new BindingRejection('creation-aborted', 'child binding cancelled before publication');
          this.bindings.bind(child.session.id, childGrant, { parentSessionId: parent.session.id });
        },
      });
    } catch (error) {
      this.bindings.release(childId);
      if (request.signal.aborted) {
        throw new BindingRejection('creation-aborted', 'delegation was cancelled; no child was published', { cause: error });
      }
      throw error;
    }
    return this.drive(handle, request, childId);
  }

  /**
   * Drive one published child to its terminal result.
   *
   * Ownership: on fulfillment the returned run is the single owner of the child;
   * `dispose()` cancels remaining work, awaits quiescence and disposes the
   * handle. H02's result is a pass-through of the child's own turn outcome.
   */
  private drive(handle: AgentHandle, request: ResolvedSubagentStartRequest, childId: SessionId): SubagentRun {
    const child = handle.agent;
    const bindings = this.bindings;
    let cancelled = false;
    const onAbort = (): void => {
      cancelled = true;
      child.cancel({ kind: 'parent' });
    };
    request.signal.addEventListener('abort', onAbort, { once: true });
    if (request.signal.aborted) onAbort();

    const result = (async (): Promise<SubagentResult> => {
      try {
        if (!cancelled) {
          child.followup(createUserMessage({ content: [...request.prompt], source: { kind: 'user' } }));
          await child.whenIdle();
        }
        return readRunResult(child.session, cancelled);
      } finally {
        request.signal.removeEventListener('abort', onAbort);
      }
    })();

    return {
      id: childId,
      localAgent: child,
      result,
      async dispose(): Promise<void> {
        request.signal.removeEventListener('abort', onAbort);
        cancelled = true;
        const [disposal] = await Promise.allSettled([handle.dispose(), result]);
        // The binding describes the live child session; dropping it with the run
        // keeps the registry from outliving the agents it describes.
        bindings.release(childId);
        if (disposal.status === 'rejected') throw disposal.reason;
      },
    };
  }
}

/**
 * Register the narrow provider on one Host composition.
 * @param caller - host context (must inject `subagents`).
 * @param options - the binding registry and optional name.
 * @returns the registered name and the exact disposer.
 */
export function registerCode2PaperSpawn(caller: Context, options: Code2PaperSpawnOptions): SpawnRegistration {
  const provider = options.provider ?? new Code2PaperSpawnProvider(options);
  const admission: ProviderAdmission = { bindings: options.bindings, providerName: provider.name, revoked: false };
  admissions.set(provider, admission);
  const disposeProvider = caller.subagents.registerProvider(provider);
  return {
    providerName: provider.name,
    dispose: () => {
      // Revoke before unregistering: a later re-registration of the same object
      // must not silently regain authority.
      admission.revoked = true;
      disposeProvider();
    },
  };
}

/** Options for {@link dispatchRole}. */
export interface RoleDispatchOptions {
  /** The bound parent agent the child is delegated from. */
  readonly parent: Agent;
  /** Role label persisted with the child (e.g. `writer`). */
  readonly role: string;
  /** The child's initial user message content. */
  readonly prompt: readonly ContentBlock[];
  /** Cancellation owning the delegation. */
  readonly signal: AbortSignal;
  /** The binding registry that owns the claim seam. */
  readonly bindings: SessionBindings;
  /** Untrusted task id hint; compared against the parent's trusted binding. */
  readonly taskId?: string;
  /** Untrusted epoch hint; compared against the parent's trusted binding. */
  readonly epoch?: number;
  /** Untrusted fence hint; compared against the current grant. */
  readonly fence?: number;
  /** Provider name; it must be registered by {@link registerCode2PaperSpawn} for this registry. */
  readonly providerName?: string;
  /** Per-child route overrides. */
  readonly agentOptions?: AgentOptions;
}

/** One accepted delegation: the run and the child's trusted binding. */
export interface RoleDispatch {
  /** The published run; the caller awaits `result` and always disposes it. */
  readonly run: SubagentRun;
  /** The child's binding, installed in its creation window. */
  readonly binding: SessionBinding;
}

/**
 * Delegate one role to a bound child through the public subagent seam.
 *
 * Untrusted identity hints are validated against the parent's trusted binding
 * first, so a forged task id, epoch or fence is refused before any claim or
 * creation happens. The child's binding is read back from the registry rather
 * than returned by the provider, so a provider that failed to bind cannot be
 * mistaken for a success.
 *
 * @param caller - host context (must inject `subagents`).
 * @param options - parent, role, prompt, cancellation, registry and hints.
 * @returns the run and the child's trusted binding.
 * @throws {BindingRejection} on a forged/stale hint, refusal, or an unbound child.
 */
export async function dispatchRole(caller: Context, options: RoleDispatchOptions): Promise<RoleDispatch> {
  // 1. The entry accepts only a registered provider that implements the binding
  //    protocol. This is checked BEFORE start(), because a provider without the
  //    protocol delivers the prompt before returning and could only be caught
  //    afterwards — too late for a pre-first-turn binding gate.
  const providerName = options.providerName ?? CODE2PAPER_SPAWN_PROVIDER;
  const provider = caller.subagents.getProvider(providerName);
  if (provider === undefined) {
    throw new BindingRejection(
      'unbound-provider',
      `no subagent provider is registered as ${JSON.stringify(providerName)}; ` +
        'register one with registerCode2PaperSpawn and delegate through it',
    );
  }
  // Admission is the registration RECORD for this exact object, not the public
  // protocol string: a look-alike carrying the same tag, a provider registered
  // for another binding registry, and a revoked registration are all refused
  // here — before start(), before any claim, and before any prompt delivery.
  const admission = admissions.get(provider);
  if (admission === undefined) {
    throw new BindingRejection(
      'unbound-provider',
      `provider ${JSON.stringify(providerName)} was not registered by registerCode2PaperSpawn; ` +
        `a ${BINDING_PROTOCOL} label states intent and cannot authorize a delegation`,
    );
  }
  if (admission.revoked) {
    throw new BindingRejection(
      'unbound-provider',
      `provider ${JSON.stringify(providerName)} registration was disposed; re-register before delegating`,
    );
  }
  if (admission.bindings !== options.bindings) {
    throw new BindingRejection(
      'misbound-provider',
      `provider ${JSON.stringify(providerName)} is registered for a different SessionBindings; ` +
        'a delegation must use the registry its provider was registered with',
    );
  }
  // 2. Delegation from an unbound or superseded parent is refused here, still
  //    before any claim, creation or material delivery.
  try {
    options.bindings.requireCurrent(options.parent);
  } catch (error) {
    if (error instanceof BindingRejection && error.code === 'unbound-agent') {
      throw new BindingRejection(
        'unbound-parent',
        `agent ${options.parent.session.id} has no trusted binding; delegation requires a bound parent`,
        { cause: error },
      );
    }
    throw error;
  }
  options.bindings.assertTrusted(options.parent, {
    ...(options.taskId === undefined ? {} : { taskId: options.taskId }),
    ...(options.epoch === undefined ? {} : { epoch: options.epoch }),
    ...(options.fence === undefined ? {} : { fence: options.fence }),
  });
  const run = await caller.subagents.start(providerName, {
    parent: options.parent,
    prompt: [...options.prompt],
    label: options.role,
    signal: options.signal,
    ...(options.agentOptions === undefined ? {} : { agentOptions: options.agentOptions }),
  });
  // 3. Post-start validation is a backstop, not the gate: with a protocol
  //    provider the binding already exists. If it ever fails, this entry owns the
  //    run it just obtained and disposes it before refusing, so a rejected
  //    delegation never leaves a live child behind.
  const child = run.localAgent;
  if (child !== undefined) {
    const binding = options.bindings.resolve(child);
    if (binding !== undefined) return { run, binding };
  }
  let disposalError: unknown;
  try {
    await run.dispose();
  } catch (error) {
    disposalError = error;
  }
  throw new BindingRejection(
    'unbound-child',
    child === undefined
      ? 'the delegation provider returned no local child agent; the run was disposed'
      : `child ${child.session.id} was not bound in its creation window; the run was disposed`,
    disposalError === undefined ? undefined : { cause: disposalError },
  );
}
