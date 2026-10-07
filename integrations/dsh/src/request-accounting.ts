/**
 * H04 — request accounting at the real LLM seam.
 *
 * ## What this module is
 *
 * The middleware H04 owns: it reserves, records dispatch, re-checks the request
 * before delegation, settles or marks unknown, and never lets an unaccounted
 * request reach the adapter on a protected route.
 *
 * ## Provenance comes from the registration site, not from the request
 *
 * Measured on the frozen runtime (`tests/request-seam.test.ts`, real loop, one
 * mock adapter):
 *
 * * a listener registered in a **root** agent's `setup` context is **not**
 *   isolated - it observes a sibling agent's dispatch and a hand-built dispatch
 *   issued from the host root;
 * * a listener registered on a **delegated child's** context **is** isolated -
 *   it observes that child's loop dispatch and neither its sibling child's
 *   dispatch nor the host root's bare dispatch.
 *
 * So this middleware only registers on delegated child scopes, and the child's
 * own session id (captured at registration) is the only identity it trusts for
 * attribution. The request's `sessionId` is compared against it and never used
 * to look up authority; the binding comes from `SessionBindings` (Host state).
 *
 * A bare dispatch from the host root naming a protected session is therefore
 * *not observed* here. Not observing is not refusing, and this module must not
 * pretend otherwise: that residual is reported as a named capability gap and is
 * closed at the route owner (the Host's adapter for its own route), not by
 * trusting a self-reported id.
 *
 * Validation is against an H04-owned frozen snapshot of the accepted receipts:
 * a receipt object mutated while a later call is awaited cannot replace what was
 * accepted. `DispatchReceipt` carries no binding, so dispatch is chained back to
 * the accepted reservation through its version, ids, digest and stage.
 */

import { createHash } from 'node:crypto';

import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { GenerateOptions, StreamChunk } from '@deepseek-ai/dsh-llm';
import * as dshLlmModule from '@deepseek-ai/dsh-llm';
import type { SessionId } from '@deepseek-ai/dsh-session';

import {
  REQUEST_CONTRACT_VERSION,
  RequestRejection,
  requestBindingRef,
  sameRequestDigest,
  type DispatchReceipt,
  type RequestBindingRef,
  type RequestDigest,
  type RequestRecorder,
  type RequestStage,
  type ReservationReceipt,
} from './request-contract.js';
import { BindingRejection, type SessionBindings } from './session-binding.js';
import type { JsonObject } from './wire.js';

/** Payload-shape version this module's digest is computed over. */
export const REQUEST_DIGEST_VERSION = 'c2p-dsh-request-payload/1';

/** Stage estimator recorded on every reservation. Not a production tokenizer. */
export const STAGE_ESTIMATOR_VERSION = 'h04-stage-estimator/1';
export const STAGE_ESTIMATOR_SOURCE = 'utf8-byte-length';

/** Bound on `AsyncIterator.return`. Expiry is unsettled, not quiescence. */
export const ITERATOR_RETURN_BUDGET_MS = 250;

/** Wait for `return` until the budget. A timeout is not a claim the iterator stopped. */
export async function boundedIteratorReturn(
  iterator: AsyncIterator<unknown> | undefined,
  budgetMs = ITERATOR_RETURN_BUDGET_MS,
): Promise<'absent' | 'returned' | 'threw' | 'timed-out'> {
  if (iterator?.return === undefined) return 'absent';
  let timer: ReturnType<typeof setTimeout> | undefined;
  let returning: Promise<'returned' | 'threw'>;
  try {
    // `return()` can throw before it produces a promise. That is 'threw',
    // not an exception that escapes this helper.
    returning = Promise.resolve(iterator.return()).then(
      () => 'returned' as const,
      () => 'threw' as const,
    );
  } catch {
    return 'threw';
  }
  try {
    return await Promise.race([
      returning,
      new Promise<'timed-out'>((resolve) => {
        timer = setTimeout(() => resolve('timed-out'), budgetMs);
      }),
    ]);
  } finally {
    if (timer !== undefined) clearTimeout(timer);
  }
}

/**
 * Dispatch-origin marking for the loop's own model dispatches.
 *
 * H-R4 proved that no public-API fact can identify the loop as the caller:
 * an outermost `agent/request` listener can continue after the waterfall and
 * call the public `llm.prepareCall` with the loop's own signal, so state,
 * first-call order, microtask order, material, and the public setter are all
 * forgeable or stealable. Until the loop-origin interface difference is ruled
 * on, no claiming closure exists and the middleware is fail-closed: the
 * accounting listener refuses every dispatch on a protected session by name.
 * The verification shape below is what the ruling is asked to enable; see
 * h04_loop_origin_escalation_20261001.md for the exact call chains and the
 * minimal interface difference.
 */

function safeCount(value: number): boolean {
  return Number.isSafeInteger(value) && value >= 0;
}

/** Declared, non-serialized runtime objects: never silently dropped from coverage. */
const NON_SERIALIZED_KEYS: readonly string[] = ['signal', 'sessionId'];

/**
 * Every own key this digest version covers; anything else is refused.
 *
 * `toolHistory` is part of the 0.2.0-rc.1 `GenerateOptions` surface and carries
 * model-facing tool material, so it must be inside the digest rather than
 * excluded: a request that differs only in tool history is a different
 * assembly, and an uncovered key is refused as `contract-unsupported`.
 */
const COVERED_KEYS: readonly string[] = [
  'provider', 'model', 'reasoningEffort', 'messages', 'system', 'tools', 'toolHistory',
  'temperature', 'maxTokens', 'stop', 'purpose',
];

/** A local terminal-record attempt; not a durable exactly-once claim. */
export type TerminalOutcome = 'settled' | 'unfinished' | 'unknown' | 'unsettled' | 'not-entered';

/** H04 diagnostics. Deliberately not recorder methods. */
export interface RequestAccountingDiagnostics {
  (event: {
    readonly kind:
      | 'scope-refused' | 'reserve-refused' | 'receipt-refused' | 'pre-dispatch-refused'
      | 'assembly-changed' | 'terminal' | 'skip-unprotected';
    readonly sessionId: string;
    readonly detail: string;
    readonly stage?: RequestStage;
    readonly outcome?: TerminalOutcome;
  }): void;
}

/** Resolves the effective output cap for one protected request, or refuses. */
export interface OutputCapSource {
  readonly version: string;
  /** `undefined` means "not established" - the request must be refused. */
  cap(options: GenerateOptions): number | undefined;
}

export interface RequestAccountingOptions {
  readonly bindings: SessionBindings;
  readonly recorder: RequestRecorder;
  /** Optional production bridge; runs only for a proven, bound loop request. */
  readonly recordActualRequest?: (request: GenerateOptions, binding: RequestBindingRef) => Promise<JsonObject>;
  /** Host-owned provider route the protected children use. */
  readonly route: string;
  /** Purpose label recorded with every request identity. */
  readonly purpose: string | ((agent: Agent) => string);
  readonly outputCap: OutputCapSource;
  readonly diagnostics?: RequestAccountingDiagnostics;
  /** Host-owned decision: does this created agent belong to the protected run? */
  readonly isProtectedAgent?: (agent: Agent) => boolean;
  /** Registry the gated route adapter consumes; created here when omitted. */
  readonly authorizations?: DispatchAuthorizations;
}

/** An accepted reservation, frozen and owned by this module. */
interface AcceptedReservation {
  readonly contractVersion: string;
  readonly requestId: string;
  readonly reservationId: string;
  readonly binding: RequestBindingRef;
  readonly digest: RequestDigest;
  /** Detached receipt passed to dispatch. Mutations of the live object do not reach it. */
  readonly reservation: ReservationReceipt;
}

function deepFreeze<T>(value: T): T {
  if (value !== null && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const item of Object.values(value as object)) deepFreeze(item);
    Object.freeze(value);
  }
  return value;
}

function canonical(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value) ?? 'null';
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  const record = value as Record<string, unknown>;
  const keys = Object.keys(record).sort();
  return `{${keys.map((key) => `${JSON.stringify(key)}:${canonical(record[key])}`).join(',')}}`;
}

function sha256Hex(text: string): string {
  return createHash('sha256').update(text, 'utf8').digest('hex');
}

/**
 * Digest the complete supported assembly.
 *
 * The covered key set is closed: a request carrying an own key this version does
 * not understand is refused rather than digested without it.
 */
export function digestSupportedRequest(options: GenerateOptions): RequestDigest {
  const present = Object.keys(options as unknown as Record<string, unknown>);
  const unknown = present.filter(
    (key) => !COVERED_KEYS.includes(key) && !NON_SERIALIZED_KEYS.includes(key),
  );
  if (unknown.length > 0) {
    throw new RequestRejection(
      'contract-unsupported',
      `request carries payload this digest version cannot cover: ${unknown.join(', ')}`,
    );
  }
  const covered: Record<string, unknown> = {};
  for (const key of COVERED_KEYS) {
    const value = (options as unknown as Record<string, unknown>)[key];
    if (value !== undefined) covered[key] = value;
  }
  return {
    digestVersion: REQUEST_DIGEST_VERSION,
    algorithm: 'sha256',
    value: sha256Hex(canonical(covered)),
    parts: ['messages', 'tools', 'config'],
  };
}

/** Validate the reservation the authority returned, and snapshot it locally. */
export function acceptReservation(
  receipt: ReservationReceipt,
  expected: { readonly binding: RequestBindingRef; readonly digest: RequestDigest },
): AcceptedReservation {
  if (receipt.contractVersion !== REQUEST_CONTRACT_VERSION) {
    throw new RequestRejection('contract-unsupported', `reservation contract ${String(receipt.contractVersion)}`);
  }
  if (receipt.requestId === '' || receipt.reservationId === '') {
    throw new RequestRejection('unknown-reservation', 'reservation receipt is missing its identity');
  }
  for (const key of ['sessionId', 'taskId', 'epoch', 'fence', 'claimId', 'compositionRef'] as const) {
    if (receipt.binding[key] !== expected.binding[key]) {
      throw new RequestRejection('stale-binding', `reservation binding ${key} is not the submitted binding`);
    }
  }
  if (!sameRequestDigest(receipt.digest, expected.digest)) {
    throw new RequestRejection('digest-mismatch', 'reservation digest is not the submitted digest');
  }
  const reservation = deepFreeze({
    contractVersion: receipt.contractVersion,
    requestId: receipt.requestId,
    reservationId: receipt.reservationId,
    binding: { ...receipt.binding },
    digest: { ...receipt.digest, parts: [...receipt.digest.parts] },
    grantedAt: receipt.grantedAt,
  });
  return deepFreeze({
    contractVersion: reservation.contractVersion,
    requestId: reservation.requestId,
    reservationId: reservation.reservationId,
    binding: reservation.binding,
    digest: reservation.digest,
    reservation,
  });
}

/** Chain the dispatch receipt back to the accepted reservation. */
export function acceptDispatch(
  receipt: DispatchReceipt,
  accepted: AcceptedReservation,
  digest: RequestDigest,
): DispatchReceipt {
  if (receipt.contractVersion !== REQUEST_CONTRACT_VERSION) {
    throw new RequestRejection('contract-unsupported', `dispatch contract ${String(receipt.contractVersion)}`);
  }
  if (receipt.stage !== 'dispatch-recorded') {
    throw new RequestRejection('contract-unsupported', `dispatch claims stage ${String(receipt.stage)}`);
  }
  if (receipt.requestId !== accepted.requestId || receipt.reservationId !== accepted.reservationId) {
    throw new RequestRejection('unknown-reservation', 'dispatch receipt is not the accepted reservation');
  }
  if (!sameRequestDigest(receipt.digest, accepted.digest) || !sameRequestDigest(digest, accepted.digest)) {
    throw new RequestRejection('digest-mismatch', 'dispatch digest is not the accepted reservation digest');
  }
  return receipt;
}

function failureChunk(code: string, cause?: unknown): StreamChunk {
  const message = cause instanceof Error ? cause.message : String(cause ?? code);
  return Object.freeze({
    type: 'finish',
    reason: Object.freeze({
      kind: 'error' as const,
      failure: Object.freeze({ message, code }),
    }),
  }) as unknown as StreamChunk;
}

/** One installed middleware registration. */
export interface RequestAccounting {
  /** The registry the Host's gated route adapter must consume from. */
  readonly authorizations: DispatchAuthorizations;
  /** Stop accounting new agents and release every registered listener. */
  dispose(): void;
}

/**
 * Install request accounting for the Host's protected children.
 *
 * @param hostCtx - the composition context that owns agent creation.
 * @param options - recorder, bindings and the Host-owned route/cap decisions.
 */
export function installRequestAccounting(
  hostCtx: Context,
  options: RequestAccountingOptions,
): RequestAccounting {
  const disposers: (() => boolean)[] = [];
  const authorizations = options.authorizations ?? new DispatchAuthorizations();
  const isProtected = options.isProtectedAgent
    ?? ((agent: Agent) => options.bindings.resolve(agent) !== undefined);
  /** Protected session ids with a live accounting listener (for the public guard). */
  const protectedSessions = new Set<string>();

  // Call-origin evidence. The patched runtime establishes a private dispatch
  // origin at the agent loop's OWN stream call site and dsh-llm consumes it
  // once at the private admission point (runLoopDispatch), before any
  // llm/stream listener runs. Publicly initiated dispatches (the public
  // llm.stream, prepareCall handles held or re-entered by an extension,
  // delayed replays) never carry an admitted origin, so this middleware
  // verifies the runtime's origin as the sole source credential:
  // same session and same signal. No state, timing, material, or public setter
  // participates (H-R1/H-R2/H-R4).
  const verifyOrigin = (request: GenerateOptions, sessionId: string): boolean => {
    // The patched runtime admits the origin at its own admission point and
    // exposes the read-only query declared by the runtime's own types
    // (loop-origin.1, lib/types/index.d.ts). The read stays runtime-checked:
    // an unpatched runtime lacks the export, so the verification fails closed
    // by name instead of passing.
    const query = dshLlmModule.currentLoopDispatchOrigin;
    if (typeof query !== "function") return false;
    const origin = query();
    // The snapshot is read-only and carries no request object; the origin
    // scope itself is established only by the loop's own step dispatch, so a
    // visible origin bound to this session and signal is the loop's dispatch.
    if (origin === undefined) return false;
    if (String(origin.sessionId) !== sessionId) return false;
    if (origin.signal !== (request.signal as AbortSignal | undefined)) return false;
    return true;
  };

  const account = (agent: Agent, sessionId: SessionId): (() => boolean) => {
    let sequence = 0;
    return (agent.ctx as Context).on(
      'llm/stream',
      (request: GenerateOptions, next: () => AsyncIterable<StreamChunk>) => {
        if (request.sessionId !== sessionId) {
          // Every protected listener observes every dispatch. A sibling must
          // not veto or meter a request it does not own; the owning listener
          // is the one that refuses or accounts it.
          return next();
        }
        // A protected session may not leave the Host-owned route: switching the
        // provider must not become a way out of accounting.
        if (request.provider !== options.route) {
          options.diagnostics?.({
            kind: 'scope-refused', sessionId: String(sessionId),
            detail: `protected session used foreign route ${request.provider}`,
          });
          return (async function* () { yield failureChunk('protected_route_mismatch'); })();
        }
        // Proven origin: the patched runtime established and consumed the
        // dispatch origin at its own admission point for this exact request
        // object, session and signal. Everything publicly initiated is
        // refused here.
        if (!verifyOrigin(request, String(sessionId))) {
          options.diagnostics?.({
            kind: 'scope-refused', sessionId: String(sessionId),
            detail: 'no loop preparation for this request signal',
          });
          return (async function* () { yield failureChunk('dispatch_origin_unproven'); })();
        }

        return (async function* (): AsyncIterable<StreamChunk> {
          let recorded = false;
          let accepted: AcceptedReservation | undefined;
          let latestStage: RequestStage = 'reserved';
          let inner: AsyncIterator<StreamChunk> | undefined;
          let usageSeen: { inputTokens: number; outputTokens: number } | undefined;
          let finishSeen: string | undefined;

          const record = async (outcome: TerminalOutcome, stage: RequestStage, reason: string): Promise<void> => {
            if (recorded || accepted === undefined) return;
            recorded = true;
            try {
              if (outcome === 'settled') {
                if (usageSeen === undefined) {
                  await options.recorder.markUnknown({
                    requestId: accepted.requestId, reservationId: accepted.reservationId,
                    lastStage: stage, reason: 'usage-missing',
                  });
                } else {
                  await options.recorder.settle({
                    requestId: accepted.requestId, reservationId: accepted.reservationId,
                    finish: { kind: 'settled', finishReason: finishSeen ?? 'stop',
                      usage: { inputTokens: usageSeen.inputTokens, outputTokens: usageSeen.outputTokens, source: 'adapter-usage' } },
                    response: { kind: 'adapter-stream' },
                  });
                }
              } else if (outcome === 'unfinished') {
                await options.recorder.settle({
                  requestId: accepted.requestId, reservationId: accepted.reservationId,
                  finish: usageSeen === undefined
                    ? { kind: 'unfinished' }
                    : { kind: 'unfinished', usage: { ...usageSeen, source: 'adapter-usage' } },
                  response: { kind: 'adapter-stream' },
                });
              } else {
                await options.recorder.markUnknown({
                  requestId: accepted.requestId, reservationId: accepted.reservationId,
                  lastStage: stage, reason,
                });
              }
            } catch {
              // A failing record stays a named unsettled fact; never retried.
              options.diagnostics?.({
                kind: 'terminal', sessionId: String(sessionId), detail: reason, stage, outcome: 'unsettled',
              });
            }
          };

          try {
            const binding = options.bindings.requireCurrent(sessionId);
            const ref = requestBindingRef(binding);
            const cap = options.outputCap.cap(request);
            if (cap === undefined || !safeCount(cap)) {
              throw new RequestRejection(
                'contract-unsupported',
                `output cap is not established (${options.outputCap.version})`,
              );
            }
            const inputTokens = Buffer.byteLength(canonical({
              messages: request.messages,
              tools: request.tools,
              system: (request as { system?: unknown }).system,
            }), 'utf8');
            if (!safeCount(inputTokens)) {
              throw new RequestRejection('contract-unsupported', `input estimate is not a safe count (${STAGE_ESTIMATOR_VERSION})`);
            }
            const digest = digestSupportedRequest(request);
            const actualRequestRef = await options.recordActualRequest?.(request, ref);
            const reservation = await options.recorder.reserve({
              binding: ref,
              identity: { sequence: (sequence += 1), purpose: typeof options.purpose === 'string' ? options.purpose : options.purpose(agent) },
              digest,
              estimate: {
                inputTokens, outputTokens: cap,
                source: STAGE_ESTIMATOR_SOURCE,
                estimatorVersion: STAGE_ESTIMATOR_VERSION,
              },
              ...(actualRequestRef === undefined ? {} : { actualRequestRef }),
            }, request.signal === undefined ? {} : { signal: request.signal });
            accepted = acceptReservation(reservation, { binding: ref, digest });
            latestStage = 'reserved';

            const recheck = (where: string): void => {
              if (request.signal?.aborted === true) {
                throw new RequestRejection('reserve-aborted', `request was cancelled while ${where}`);
              }
              const live = options.bindings.requireCurrent(sessionId);
              if (live.receipt.fence !== accepted!.binding.fence || live.receipt.claimId !== accepted!.binding.claimId) {
                throw new RequestRejection('stale-binding', `binding changed while ${where}`);
              }
              if (!sameRequestDigest(digestSupportedRequest(request), accepted!.digest)) {
                throw new RequestRejection('digest-mismatch', `assembly changed while ${where}`);
              }
            };
            recheck('reserving');

            const dispatchReceipt = await options.recorder.dispatch(
              { reservation: accepted.reservation, digest: accepted.digest },
              request.signal === undefined ? {} : { signal: request.signal },
            );
            acceptDispatch(dispatchReceipt, accepted, accepted.digest);
            latestStage = 'dispatch-recorded';
            recheck('dispatching');
            // Mint only after the post-dispatch recheck. The gate consumes it
            // synchronously inside next(); anything still outstanding is revoked.
            authorizations.issue({
              requestId: accepted.requestId,
              reservationId: accepted.reservationId,
              sessionId: String(sessionId),
              provider: request.provider,
              digestValue: accepted.digest.value,
            });
          } catch (error) {
            const code = error instanceof RequestRejection
              ? error.code
              : error instanceof BindingRejection
                ? error.code
                : 'request-accounting-failed';
            options.diagnostics?.({
              kind: 'pre-dispatch-refused', sessionId: String(sessionId),
              detail: code, stage: latestStage, outcome: 'not-entered',
            });
            if (accepted !== undefined) await record('unknown', latestStage, code);
            authorizations.revoke(accepted?.requestId);
            yield failureChunk(code, error);
            return;
          }

          let stream: AsyncIterable<StreamChunk>;
          try {
            stream = next();
          } catch (error) {
            authorizations.revoke(accepted.requestId);
            await record('unknown', latestStage, error instanceof Error ? error.message : 'delegation failed');
            throw error;
          }

          try {
            inner = (stream as AsyncIterable<StreamChunk>)[Symbol.asyncIterator]();
            let first = true;
            for (;;) {
              if (first) {
                first = false;
                if (!sameRequestDigest(digestSupportedRequest(request), accepted.digest)) {
                  await record('unknown', 'dispatch-recorded', 'assembly-changed-before-first-iteration');
                  yield failureChunk('request_assembly_changed_before_iteration');
                  return;
                }
              }
              const step = await inner.next();
              if (step.done === true) break;
              if (step.value.type === 'usage'
                && safeCount(step.value.usage.inputTokens)
                && safeCount(step.value.usage.outputTokens)
                // SDK error paths emit an initialized 0/0 counter rather
                // than provider usage. Zero billed input with actual output
                // (for example a cached prompt) remains distinguishable.
                && (step.value.usage.inputTokens > 0 || step.value.usage.outputTokens > 0)) {
                usageSeen = { inputTokens: step.value.usage.inputTokens, outputTokens: step.value.usage.outputTokens };
              }
              if (step.value.type === 'finish') {
                const reason = step.value.reason;
                finishSeen = typeof reason === 'string' ? reason : reason.kind;
              }
              yield step.value;
            }
            const stopWithoutUsage = finishSeen === 'stop' && usageSeen === undefined;
            const errorWithoutUsage = finishSeen === 'error' && usageSeen === undefined;
            await record(
              finishSeen === undefined || stopWithoutUsage || errorWithoutUsage ? 'unknown' : (finishSeen === 'stop' ? 'settled' : 'unfinished'),
              finishSeen === undefined ? 'dispatch-recorded' : 'response-observed',
              errorWithoutUsage ? 'provider-error-usage-missing' : stopWithoutUsage ? 'usage-missing'
                : finishSeen === undefined ? 'stream ended without a finish chunk' : 'stream completed',
            );
          } catch (error) {
            await record('unknown', latestStage, error instanceof Error ? error.message : 'iteration failed');
            throw error;
          } finally {
            authorizations.revoke(accepted.requestId);
            const cleanup = await boundedIteratorReturn(inner);
            if (cleanup === 'threw' || cleanup === 'timed-out') {
              const detail = `iterator-return-${cleanup}`;
              options.diagnostics?.({
                kind: 'terminal', sessionId: String(sessionId),
                detail, stage: latestStage, outcome: 'unsettled',
              });
              // A settlement already recorded is not attempted again. The
              // cleanup fact stays a named diagnostic; the deadline is not quiescence.
              if (!recorded) await record('unknown', latestStage, detail);
            }
          }
        })();
      },
    );
  };

  const created = hostCtx.on('agent/created', ({ agent }: { agent: Agent }) => {
    if (!isProtected(agent)) {
      options.diagnostics?.({
        kind: 'skip-unprotected', sessionId: String(agent.session.id), detail: 'agent is not a protected binding',
      });
      return;
    }
    const protectedSessionId = String(agent.session.id);
    protectedSessions.add(protectedSessionId);
    disposers.push(() => {
      protectedSessions.delete(protectedSessionId);
      return true;
    });
    disposers.push(account(agent, agent.session.id));
      return undefined;
  });

  // Deployment-surface guard (loop-origin.1). The Host's own llm context is a
  // public composition surface: the agent loop never dispatches there (its
  // dispatch runs on the owning agent's context), so a dispatch composed here
  // can never carry a live loop origin. Any request that claims a protected
  // session on this surface is impersonation and is refused fail-closed;
  // requests that claim no protected session are ordinary public traffic and
  // pass. Cordis dispatch runs only the composing context's own hooks, so
  // this guard never double-fires with the per-agent listener above.
  const publicGuard = hostCtx.on(
    'llm/stream',
    ((request: GenerateOptions, next: () => AsyncIterable<StreamChunk>) => {
      const claimed = request.sessionId === undefined ? undefined : String(request.sessionId);
      if (claimed === undefined || !protectedSessions.has(claimed)) return next();
      if (!verifyOrigin(request, claimed)) {
        options.diagnostics?.({
          kind: 'scope-refused', sessionId: claimed,
          detail: 'public surface dispatch claims a protected session without a loop origin',
        });
        return (async function* () { yield failureChunk('dispatch_origin_unproven'); })();
      }
      return next();
    }) as never,
  );
  disposers.push(publicGuard);

  return {
    authorizations,
    dispose(): void {
      created();
      for (const disposer of disposers.splice(0)) disposer();
    },
  };
}

// --------------------------------------------------------------------------- //
// Trusted authorization for the Host's own route
// --------------------------------------------------------------------------- //
//
// H04-S1 measured that this seam has NO context isolation: every listener sees
// every dispatch, so a registration site cannot prove where a call came from.
// The only public path that can gate the protected route is the route's own
// adapter, because it is the last thing before the provider. This module
// therefore wraps the Host's adapter and requires a one-time authorization that
// only this middleware can mint.
//
// An authorization is bound to the accepted reservation, the exact assembly
// digest, the session and the route. It is consumed by digest, so:
//   * a bare/short-circuited dispatch never gets one -> refused;
//   * copying a digest onto different material changes the recomputed digest
//     -> no match -> refused;
//   * replaying the same material finds the authorization already consumed
//     -> refused.
// Only the middleware's reserve -> dispatch sequence mints one.

/** One one-time dispatch authorization, minted by the middleware. */
export interface DispatchAuthorization {
  readonly requestId: string;
  readonly reservationId: string;
  readonly sessionId: string;
  readonly provider: string;
  readonly digestValue: string;
}

/** Pending one-time authorizations, keyed by route and assembly digest. */
export class DispatchAuthorizations {
  private readonly pending = new Map<string, DispatchAuthorization[]>();

  private static key(provider: string, sessionId: string, digestValue: string): string {
    return `${provider}\u0000${sessionId}\u0000${digestValue}`;
  }

  /** Mint one authorization; only the accounting middleware may call this. */
  issue(authorization: DispatchAuthorization): void {
    const key = DispatchAuthorizations.key(authorization.provider, authorization.sessionId, authorization.digestValue);
    const queue = this.pending.get(key) ?? [];
    queue.push(authorization);
    this.pending.set(key, queue);
  }

  /**
   * Drop one unconsumed authorization. Returns true when it was still pending,
   * so a caller can tell the protected route never took it.
   */
  revoke(requestId: string | undefined): boolean {
    if (requestId === undefined) return false;
    for (const [key, queue] of this.pending) {
      const index = queue.findIndex((item) => item.requestId === requestId);
      if (index < 0) continue;
      queue.splice(index, 1);
      if (queue.length === 0) this.pending.delete(key);
      return true;
    }
    return false;
  }

  /**
   * Consume the authorization for exactly this assembly, or return `undefined`.
   * The digest is recomputed from the received request, so a copied digest on
   * different material cannot match and a consumed one is gone.
   */
  consume(options: GenerateOptions): DispatchAuthorization | undefined {
    let digestValue: string;
    try {
      digestValue = digestSupportedRequest(options).value;
    } catch {
      return undefined;
    }
    const sessionId = options.sessionId === undefined ? '' : String(options.sessionId);
    if (sessionId === '') return undefined;
    const key = DispatchAuthorizations.key(options.provider, sessionId, digestValue);
    const queue = this.pending.get(key);
    if (queue === undefined || queue.length === 0) return undefined;
    const index = queue.findIndex((item) => item.sessionId === sessionId && item.provider === options.provider && item.digestValue === digestValue);
    if (index < 0) return undefined;
    const [authorization] = queue.splice(index, 1) as [DispatchAuthorization];
    if (queue.length === 0) this.pending.delete(key);
    return authorization;
  }

  /** Outstanding authorizations; a non-zero count after a refusal is a defect. */
  get outstanding(): number {
    let total = 0;
    for (const queue of this.pending.values()) total += queue.length;
    return total;
  }
}

/** Minimal adapter surface the gate delegates to the Host's real adapter. */
export interface GatedAdapterSource {
  providerInfo(provider: string): { id: string; name: string };
  listModels(provider: string): Promise<readonly unknown[]>;
  resolveModel(provider: string, model: string, signal?: AbortSignal): Promise<unknown>;
  stream(options: GenerateOptions): AsyncIterable<StreamChunk>;
  providerRetryPolicy(provider: string): unknown;
  imageRequestPricing(provider: string, model: string): unknown;
  prepareCall(provider: string, model: string, signal?: AbortSignal): Promise<PreparedAdapterSource>;
}

/** The adapter-owned prepared call, kept behind the gate. */
export interface PreparedAdapterSource {
  readonly model: unknown;
  stream(options: GenerateOptions): AsyncIterable<StreamChunk>;
}

/** What the gate observed; the underlying adapter is only ever asked to record. */
export interface ProtectedRouteDiagnostics {
  (event: {
    readonly kind: 'authorized' | 'unauthorized';
    readonly provider: string;
    readonly sessionId: string;
    readonly detail: string;
  }): void;
}

/**
 * Wrap one adapter so that no request reaches it without a live authorization.
 *
 * @param underlying - the Host's real adapter (records facts; never refuses).
 * @param authorizations - the registry this middleware mints into.
 * @param diagnostics - H04 diagnostics sink.
 */
export function gatedAdapter(
  underlying: GatedAdapterSource,
  authorizations: DispatchAuthorizations,
  diagnostics?: ProtectedRouteDiagnostics,
  enter?: (options: GenerateOptions, authorization: DispatchAuthorization) => Promise<void>,
  completed?: (options: GenerateOptions, finishReason: string | undefined) => void,
): GatedAdapterSource {
  return {
    providerInfo: (provider) => underlying.providerInfo(provider),
    listModels: (provider) => underlying.listModels(provider),
    resolveModel: (provider, model, signal) => underlying.resolveModel(provider, model, signal),
    providerRetryPolicy: (provider) => underlying.providerRetryPolicy(provider),
    imageRequestPricing: (provider, model) => underlying.imageRequestPricing(provider, model),
    // The prepared path must not be a way around the gate: the returned handle
    // keeps the adapter's own generation and model info, but its `stream` runs
    // the SAME gate as the direct path. Returning the underlying prepared call
    // unchanged would let the loop reach the provider with no authorization,
    // which is exactly the bypass this wrapper exists to close.
    prepareCall: async (provider, model, signal) => {
      const prepared = await underlying.prepareCall(provider, model, signal);
      return {
        model: prepared.model,
        stream: (options: GenerateOptions) => gate(options, () => prepared.stream(options)),
      };
    },
    stream(options: GenerateOptions): AsyncIterable<StreamChunk> {
      return gate(options, () => underlying.stream(options));
    },
  };

  function gate(
    options: GenerateOptions,
    dispatch: () => AsyncIterable<StreamChunk>,
  ): AsyncIterable<StreamChunk> {
    const authorization = authorizations.consume(options);
    if (authorization === undefined) {
      diagnostics?.({
        kind: 'unauthorized',
        provider: options.provider,
        sessionId: String(options.sessionId ?? ''),
        detail: 'no live dispatch authorization for this assembly',
      });
      return (async function* () {
        yield failureChunk('dispatch_authorization_missing');
      })();
    }
    diagnostics?.({
      kind: 'authorized',
      provider: options.provider,
      sessionId: authorization.sessionId,
      detail: authorization.requestId,
    });
    if (enter === undefined && completed === undefined) return dispatch();
    return (async function* () {
      await enter?.(options, authorization);
      if (digestSupportedRequest(options).value !== authorization.digestValue || options.signal?.aborted === true) {
        throw new Error('adapter_request_changed_or_aborted_after_permit');
      }
      let finishReason: string | undefined;
      for await (const chunk of dispatch()) {
        if (chunk.type === 'finish') finishReason=chunk.reason.kind;
        yield chunk;
      }
      completed?.(options,finishReason);
    })();
  }
}

// The patched runtime's dsh-agent-loop exposes the read-only dispatch-origin
// query (loop-origin.1). The one-shot state and the establishment stay in the
// runtime's private domain; this module only verifies immutable facts.
