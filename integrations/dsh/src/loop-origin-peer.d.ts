// Loop-origin.1 runtime interface (see
// docs/dsh_execution_20260928/h04_loop_origin_escalation_20261001.md §6.2):
// the patched runtime establishes a private dispatch origin at the agent
// loop's own stream call site, consumes it once at dsh-llm's admission point,
// and exposes a read-only query on the dsh-llm surface. This bundle accesses
// the query through a runtime-checked property read (see request-accounting.ts
// `loopOriginQuery()`); no ambient augmentation is used.

/** The read-only origin facts the patched runtime exposes. The snapshot
 * deliberately excludes the request object and any mutable state. */
export interface LoopDispatchOriginSnapshot {
  readonly sessionId: string;
  readonly signal: AbortSignal;
}