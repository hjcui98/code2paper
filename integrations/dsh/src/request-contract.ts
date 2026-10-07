/**
 * H02 Host request-recorder contract — SHAPE ONLY.
 *
 * ## What this file is, and is not
 *
 * It freezes the vocabulary H04's mock recorder and the later R02 wiring both
 * speak: trusted binding reference, request identity, versioned request digest,
 * reservation estimate, reservation/request references, finish/usage/response
 * source, the last provable stage, and the unknown reason.
 *
 * It is NOT the ledger. Nothing here computes a balance, deducts budget,
 * installs middleware, defines an RPC frame, or reduces recovery state: R02 owns
 * the production events and the Python reducer, and H04 owns the runtime seam
 * that calls this contract. H02 proves the contract is *consumable* (its test
 * implements a mock recorder against these real types); the reserve/dispatch
 * hard gates are proven by H04 against the real loop.
 *
 * ## Invariants the shape must keep
 *
 * 1. `reserve` and `dispatch` carry the SAME {@link RequestDigest}; a dispatch
 *    whose digest differs from its reservation is a mismatch, not a new request.
 *    {@link assertReservationMatches} is the shared comparison.
 * 2. The digest covers the complete supported assembly (`messages`, `tools`,
 *    `config`) and names its version. A payload part outside that set is refused
 *    by the producer rather than silently dropped from the digest.
 * 3. A recorded dispatch, and any `next`/adapter entry, never claims HTTP
 *    delivery: {@link DispatchReceipt.stage} has exactly one value, and delivery
 *    remains unknown until a settlement or {@link UnknownReceipt} says otherwise.
 * 4. Missing usage stays missing. `unfinished` may carry no usage at all, and
 *    nothing in this contract invents a zero.
 * 5. An expired binding is expressed by its fence, checked against the current
 *    grant through {@link assertRequestBindingCurrent}; a model-supplied string
 *    can never substitute for {@link RequestBindingRef}.
 */

import type { SessionId } from '@deepseek-ai/dsh-session';

import type { SessionBinding } from './session-binding.js';
import type { JsonObject } from './wire.js';

/** Version of this contract. A receipt carrying another value is unsupported. */
export const REQUEST_CONTRACT_VERSION = 'c2p-host-request/1';

/** Trusted binding reference: which session, task, epoch and grant a request belongs to. */
export interface RequestBindingRef {
  /** Bound session that will run the request. */
  readonly sessionId: SessionId;
  /** Claimed task identity. */
  readonly taskId: string;
  /** Attempt epoch. */
  readonly epoch: number;
  /** Grant generation the request was authorized under. */
  readonly fence: number;
  /** Identity of the grant itself. */
  readonly claimId: string;
  /** Composition identity the grant was bound to. */
  readonly compositionRef: string;
}

/** Which request this is within its epoch. */
export interface RequestIdentity {
  /** 1-based sequence within the epoch; the first Writer request is 1. */
  readonly sequence: number;
  /** Purpose label, e.g. `writer`. */
  readonly purpose: string;
}

/**
 * Payload parts a digest must cover.
 *
 * The list is closed on purpose: a producer that cannot cover a supported part
 * refuses the request (`contract-unsupported`) instead of recording a digest
 * that omits it.
 */
export type RequestPayloadPart = 'messages' | 'tools' | 'config';

/**
 * Versioned digest of the complete supported request assembly.
 *
 * `parts` records exactly what was covered, so a consumer can refuse a digest
 * that does not claim the full supported set rather than trusting its value.
 */
export interface RequestDigest {
  /** Payload-shape version this digest was computed over. */
  readonly digestVersion: string;
  /** Hash algorithm; only `sha256` is supported. */
  readonly algorithm: 'sha256';
  /** Lowercase hex digest. */
  readonly value: string;
  /** Parts actually covered, in canonical order. */
  readonly parts: readonly RequestPayloadPart[];
}

/** Reservation estimate for one request. */
export interface RequestEstimate {
  /** Estimated input tokens. A missing observation is never stored as zero. */
  readonly inputTokens: number;
  /** Estimated output tokens. */
  readonly outputTokens: number;
  /** Optional wall-clock budget in milliseconds. */
  readonly wallClockMs?: number;
  /** Named stage estimator that produced the numbers. */
  readonly source?: string;
  /** Estimator version. Production tokenizer calibration stays with C00/V01. */
  readonly estimatorVersion?: string;
}

/** One reservation request. */
export interface RequestReserveRequest {
  /** Trusted binding the request is authorized under. */
  readonly binding: RequestBindingRef;
  /** Sequence and purpose within the epoch. */
  readonly identity: RequestIdentity;
  /** Digest of the assembly about to be sent. */
  readonly digest: RequestDigest;
  /** Reserved estimate. */
  readonly estimate: RequestEstimate;
  /** Actual live assembly artifact recorded by the trusted accounting hook. */
  readonly actualRequestRef?: JsonObject;
}

/** A granted reservation, referencing one request identity. */
export interface ReservationReceipt {
  /** Contract version the receipt was produced under. */
  readonly contractVersion: string;
  /** Reservation identity. */
  readonly reservationId: string;
  /** Request identity this reservation belongs to. */
  readonly requestId: string;
  /** Binding the reservation was granted under. */
  readonly binding: RequestBindingRef;
  /** Digest the reservation was granted for; dispatch must repeat it. */
  readonly digest: RequestDigest;
  /** Grant time, epoch milliseconds. */
  readonly grantedAt: number;
}

/**
 * The last stage a request can be *proven* to have reached.
 *
 * `dispatch-recorded` is the boundary this contract can attest on its own;
 * anything beyond it needs an adapter observation.
 */
export type RequestStage = 'reserved' | 'dispatch-recorded' | 'adapter-entered' | 'response-observed';

/** One dispatch record request, taken at the send boundary. */
export interface RequestDispatchRequest {
  /** The reservation this dispatch spends. */
  readonly reservation: ReservationReceipt;
  /** Digest recomputed immediately before delegation; must equal the reserved one. */
  readonly digest: RequestDigest;
}

/**
 * Receipt for entering the send boundary.
 *
 * It records intent, not delivery: the only stage it may carry is
 * `dispatch-recorded`, and no adapter or transport has been observed yet.
 */
export interface DispatchReceipt {
  /** Contract version the receipt was produced under. */
  readonly contractVersion: string;
  /** Request identity, repeated from the reservation. */
  readonly requestId: string;
  /** Reservation identity, repeated from the reservation. */
  readonly reservationId: string;
  /** Digest recorded for this dispatch. */
  readonly digest: RequestDigest;
  /** Always `dispatch-recorded`; never a delivery claim. */
  readonly stage: 'dispatch-recorded';
  /** Record time, epoch milliseconds. */
  readonly recordedAt: number;
}

/** Usage as observed; the source names where the numbers came from. */
export interface RequestUsage {
  /** Observed input tokens. */
  readonly inputTokens: number;
  /** Observed output tokens. */
  readonly outputTokens: number;
  /** Observation source, e.g. `adapter-usage` or `provider-raw`. */
  readonly source: string;
}

/**
 * How one request finished.
 *
 * `unfinished` keeps a missing usage missing; `unknown` carries the last stage
 * that could be proven and never asserts that nothing was sent.
 */
export type RequestFinish =
  | {
    readonly kind: 'settled';
    readonly finishReason: string;
    readonly usage: RequestUsage;
  }
  | {
    readonly kind: 'unfinished';
    readonly finishReason?: string;
    readonly usage?: RequestUsage;
  }
  | {
    readonly kind: 'unknown';
    readonly reason: string;
    readonly lastStage: RequestStage;
  };

/** Where the observable response came from, if anywhere. */
export type RequestResponseSource =
  | { readonly kind: 'adapter-stream'; readonly ref?: string; readonly digest?: string }
  | { readonly kind: 'provider-raw'; readonly ref: string; readonly digest: string }
  | { readonly kind: 'none' };

/** One settlement request. */
export interface RequestSettleRequest {
  /** Request identity being settled. */
  readonly requestId: string;
  /** Reservation the request spent. */
  readonly reservationId: string;
  /** Observed finish and usage. */
  readonly finish: RequestFinish;
  /** Observable response source. */
  readonly response: RequestResponseSource;
}

/** Receipt for a settlement. */
export interface SettlementReceipt {
  /** Contract version the receipt was produced under. */
  readonly contractVersion: string;
  /** Request identity that settled. */
  readonly requestId: string;
  /** Settlement identity. */
  readonly settlementId: string;
  /** Finish recorded. */
  readonly finish: RequestFinish;
  /** Response source recorded. */
  readonly response: RequestResponseSource;
  /** Settlement time, epoch milliseconds. */
  readonly settledAt: number;
}

/** One unknown-outcome record request. */
export interface RequestMarkUnknownRequest {
  /** Request identity whose outcome is unknown. */
  readonly requestId: string;
  /** Reservation the request spent. */
  readonly reservationId: string;
  /** Last stage that could be proven. */
  readonly lastStage: RequestStage;
  /** Why the outcome cannot be established. */
  readonly reason: string;
}

/**
 * Receipt recording an unknown send outcome.
 *
 * The receipt states uncertainty; whether the resource group is blocked, and
 * whether anything is refunded, is the production authority's decision (R02's
 * reducer). This contract neither refunds nor reschedules.
 */
export interface UnknownReceipt {
  /** Contract version the receipt was produced under. */
  readonly contractVersion: string;
  /** Request identity whose outcome is unknown. */
  readonly requestId: string;
  /** Last provable stage. */
  readonly lastStage: RequestStage;
  /** Why the outcome cannot be established. */
  readonly reason: string;
  /** Fixed uncertainty marker. */
  readonly uncertainty: 'send-outcome-unknown';
  /** Record time, epoch milliseconds. */
  readonly recordedAt: number;
}

/** Why a request-recorder call was refused. */
export type RequestRejectionCode =
  /** The authority refused the reservation. */
  | 'reserve-refused'
  /** The reservation wait was cancelled. */
  | 'reserve-aborted'
  /** The binding reference is no longer the current grant. */
  | 'stale-binding'
  /** A receipt or digest does not match the request it claims to describe. */
  | 'digest-mismatch'
  /** The referenced reservation is unknown to the authority. */
  | 'unknown-reservation'
  /** The authority refused the dispatch record. */
  | 'dispatch-refused'
  /** The authority refused the settlement. */
  | 'settle-refused'
  /** The authority refused the unknown record. */
  | 'unknown-refused'
  /** The assembly carries a payload part this contract version cannot cover. */
  | 'contract-unsupported';

/** A refused request-recorder call, carrying a stable {@link RequestRejectionCode}. */
export class RequestRejection extends Error {
  /** Stable rejection code. */
  readonly code: RequestRejectionCode;

  constructor(code: RequestRejectionCode, message: string, options?: { readonly cause?: unknown }) {
    super(message, options);
    this.name = 'RequestRejection';
    this.code = code;
  }
}

/**
 * The Host request-recorder seam.
 *
 * H04 implements a no-network mock against these signatures; R02 later wires the
 * same shape to the Python ledger. Every method takes caller cancellation and
 * every receipt repeats the identity it was produced for.
 */
export interface RequestRecorder {
  /** Reserve budget for one request. No send may happen before a receipt. */
  reserve(request: RequestReserveRequest, options?: { readonly signal?: AbortSignal }): Promise<ReservationReceipt>;
  /** Record entry into the send boundary for a reserved request. */
  dispatch(request: RequestDispatchRequest, options?: { readonly signal?: AbortSignal }): Promise<DispatchReceipt>;
  /** Record the observed finish and response source. */
  settle(request: RequestSettleRequest, options?: { readonly signal?: AbortSignal }): Promise<SettlementReceipt>;
  /** Record that the send outcome cannot be established. */
  markUnknown(request: RequestMarkUnknownRequest, options?: { readonly signal?: AbortSignal }): Promise<UnknownReceipt>;
}

/** Project a trusted session binding into a request binding reference. */
export function requestBindingRef(binding: SessionBinding): RequestBindingRef {
  return {
    sessionId: binding.sessionId,
    taskId: binding.task.taskId,
    epoch: binding.task.epoch,
    fence: binding.receipt.fence,
    claimId: binding.receipt.claimId,
    compositionRef: binding.receipt.compositionRef,
  };
}

/** Whether two digests describe the same assembly version and value. */
export function sameRequestDigest(a: RequestDigest, b: RequestDigest): boolean {
  return a.digestVersion === b.digestVersion && a.algorithm === b.algorithm && a.value === b.value;
}

/**
 * Refuse a binding reference whose grant is no longer current.
 * @param binding - the reference carried by the request.
 * @param currentFence - the current grant generation for that task and epoch.
 * @throws {RequestRejection} `stale-binding`.
 */
export function assertRequestBindingCurrent(binding: RequestBindingRef, currentFence: number | undefined): void {
  if (currentFence !== binding.fence) {
    throw new RequestRejection(
      'stale-binding',
      `request binding holds fence ${String(binding.fence)} but ${binding.taskId}@${String(binding.epoch)} is at ${String(currentFence)}`,
    );
  }
}

/**
 * Refuse a dispatch that does not describe the reservation it spends.
 * @param reservation - the granted reservation.
 * @param dispatched - the dispatch record under consideration.
 * @throws {RequestRejection} `digest-mismatch` or `unknown-reservation`.
 */
export function assertReservationMatches(reservation: ReservationReceipt, dispatched: RequestDispatchRequest): void {
  if (reservation.reservationId !== dispatched.reservation.reservationId) {
    throw new RequestRejection(
      'unknown-reservation',
      `dispatch references reservation ${dispatched.reservation.reservationId}, not ${reservation.reservationId}`,
    );
  }
  if (!sameRequestDigest(reservation.digest, dispatched.digest)) {
    throw new RequestRejection(
      'digest-mismatch',
      `dispatch digest ${dispatched.digest.value} does not match reserved digest ${reservation.digest.value}`,
    );
  }
}

/**
 * Refuse an assembly whose digest does not claim the full supported payload set.
 * @param digest - the digest a producer computed.
 * @throws {RequestRejection} `contract-unsupported`.
 */
export function assertSupportedDigest(digest: RequestDigest): void {
  const required: readonly RequestPayloadPart[] = ['messages', 'tools', 'config'];
  const missing = required.filter((part) => !digest.parts.includes(part));
  if (missing.length > 0) {
    throw new RequestRejection(
      'contract-unsupported',
      `digest ${digest.digestVersion} does not cover ${missing.join(', ')}; refuse the request instead of recording a partial digest`,
    );
  }
  if (digest.algorithm !== 'sha256') {
    throw new RequestRejection('contract-unsupported', `unsupported digest algorithm ${String(digest.algorithm)}`);
  }
}
