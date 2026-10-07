/**
 * H03 terminal result: the typed terminal tool, its raw/normalized provenance,
 * and the persisted record a restarted consumer rebuilds from.
 *
 * ## What this module is, and is not
 *
 * It proves the DSH-side *representation* of a Writer terminal: one typed tool
 * call whose argument schema is an object root wrapping `result.oneOf`, the
 * separate sources that argument text can come from, the guard that makes the
 * terminal final for its turn, and a durable record that survives a process
 * restart. It is NOT the domain model: the full `WriterTaskResultV1`, its
 * Python parser/assessor and the production ingest belong to C01/C03, and the
 * `TerminalResult` union here is the minimal H03 fixture those tasks replace.
 *
 * ## The three argument sources are never conflated
 *
 * 1. `rawArguments` — the `llm/stream` `tool-call-delta` text, verbatim and in
 *    arrival order. Only a real observation produces it; otherwise the record
 *    says `not_observed` and no digest is invented.
 * 2. `normalizedArguments` — the `tool/call` argument string the session
 *    recorded. A provider adapter may re-serialize at `toolcall_end`, so this is
 *    a legitimate source of its own and must not be presented as the raw bytes.
 * 3. `parsed` — the validated domain object the tool received, plus the prose
 *    the child produced. Both carry their own digest.
 *
 * A `JSON.stringify(parsed)` reconstruction is therefore never accepted as raw:
 * whitespace, escape spelling and key order differ, and each source is digested
 * separately.
 *
 * ## Durability
 *
 * The commit appends one `c2p/terminal` session event inside the same turn that
 * produced it. That event is the durable artifact: {@link rebuildTerminal} reads
 * it back from a persisted log, and a restarted consumer gets the same record —
 * including an explicit `not_observed` when the raw source was never captured.
 * `whenIdle()`/turn-end are not durability; the caller must await the session
 * persistence flush before treating the record as recoverable.
 */

import { createHash } from 'node:crypto';

import type { Context } from '@deepseek-ai/cordis';
import type { Session, SessionEvent, SessionId } from '@deepseek-ai/dsh-session';
import type { StreamChunk } from '@deepseek-ai/dsh-llm';
import { defineTool } from '@deepseek-ai/dsh-tools';

/** Model-facing terminal tool name. */
export const TERMINAL_TOOL = 'c2p_terminal';

/** Schema/record version this module writes. */
export const TERMINAL_SCHEMA_VERSION = 'c2p-terminal/1';

/** The minimal H03 domain outcome. C01/C03 replace this with the full model. */
export type TerminalResult =
  | { readonly kind: 'draft'; readonly draft: { readonly title: string; readonly body: string } }
  | { readonly kind: 'research_required'; readonly gap: string }
  | { readonly kind: 'blocked'; readonly reason: string };

/**
 * The model-facing parameter schema: an implicit object root whose single
 * `result` property is a `oneOf` union.
 *
 * This is the representation H03 verifies on the real tool path. Every branch
 * keeps `additionalProperties: false` and its own required fields, so the union
 * constraint is enforced rather than flattened into one permissive object.
 */
export const TERMINAL_PARAMETERS = {
  result: {
    required: true,
    oneOf: [
      {
        type: 'object',
        additionalProperties: false,
        properties: {
          kind: { type: 'string', enum: ['draft'], required: true },
          draft: {
            type: 'object',
            additionalProperties: false,
            required: true,
            properties: {
              title: { type: 'string', required: true },
              body: { type: 'string', required: true },
            },
          },
        },
      },
      {
        type: 'object',
        additionalProperties: false,
        properties: {
          kind: { type: 'string', enum: ['research_required'], required: true },
          gap: { type: 'string', required: true },
        },
      },
      {
        type: 'object',
        additionalProperties: false,
        properties: {
          kind: { type: 'string', enum: ['blocked'], required: true },
          reason: { type: 'string', required: true },
        },
      },
    ],
  },
} as const;

/** SHA-256 of one UTF-8 text, lowercase hex. */
export function digestText(text: string): string {
  return createHash('sha256').update(text, 'utf8').digest('hex');
}

/** SHA-256 of one value's canonical JSON text (sorted keys). */
export function digestJson(value: unknown): string {
  return digestText(canonicalJson(value));
}

/** Deterministic JSON text: object keys sorted, so key order cannot change the digest. */
export function canonicalJson(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value) ?? 'null';
  if (Array.isArray(value)) return `[${value.map((item) => canonicalJson(item)).join(',')}]`;
  const entries = Object.entries(value as Record<string, unknown>)
    .filter(([, item]) => item !== undefined)
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
  return `{${entries.map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`).join(',')}}`;
}

/** Trusted identity of one observed model stream. */
export interface ObservedStreamRef {
  /** Monotonic index of this stream within the capture. */
  readonly streamIndex: number;
  /**
   * Session identity the loop stamped on the request (`GenerateOptions.sessionId`).
   * Absent for a hand-built call that never named a session, in which case a
   * caller cannot attribute the source to a session.
   */
  readonly sessionId?: SessionId;
}

/** Fields shared by every observed raw source, complete or not. */
interface ObservedRawArguments extends ObservedStreamRef {
  readonly source: 'llm-stream-tool-call-delta';
  readonly callId: string;
  /** Tool name, when the stream named it. */
  readonly name?: string;
  /** Verbatim concatenation of that stream's deltas for this call, in arrival order. */
  readonly text: string;
  /** How many deltas contributed. */
  readonly chunks: number;
  readonly digest: string;
  readonly byteLength: number;
}

/**
 * Raw text of a call whose OWN completion fact was observed.
 *
 * The fact is the `block-end` chunk closing that call's block in that stream —
 * not "the iterator ended". A stream that later fails for another call does not
 * retract this one, and a stream that merely ends without this call's completion
 * fact never produces this state.
 */
export interface CapturedRawArguments extends ObservedRawArguments {
  readonly state: 'captured';
}

/**
 * Raw text whose call has no completion fact: the stream failed, was aborted, was
 * abandoned by its consumer, or ended without closing this call's block.
 */
export interface IncompleteRawArguments extends ObservedRawArguments {
  readonly state: 'incomplete';
  /** Why this is not a complete source. */
  readonly reason: string;
}

/**
 * The call id appears in more than one observed stream and no stream was named.
 * The candidates are listed; the capture does not guess the most recent one.
 */
export interface AmbiguousRawArguments {
  readonly state: 'ambiguous';
  readonly source: 'llm-stream-tool-call-delta';
  readonly callId: string;
  readonly reason: string;
  readonly candidates: readonly ObservedStreamRef[];
}

/** The raw source was not observed at all; nothing is inferred in its place. */
export interface MissingRawArguments {
  readonly state: 'not_observed';
  readonly source: 'llm-stream-tool-call-delta';
  readonly reason: string;
}

/** One raw-argument source: complete, incomplete, ambiguous, or not observed. */
export type RawArguments = CapturedRawArguments | IncompleteRawArguments | AmbiguousRawArguments | MissingRawArguments;

/** The `tool/call` argument string the session recorded, with its own digest. */
export interface NormalizedArguments {
  readonly source: 'session-tool-call';
  readonly text: string;
  readonly digest: string;
}

/** The assistant prose of the terminal's turn, with its own digest. */
export interface ProseSource {
  readonly source: 'assistant-message';
  readonly text: string;
  readonly blocks: number;
  readonly digest: string;
}

/** One committed terminal, exactly as persisted. */
export interface TerminalRecord {
  /** Record version. */
  readonly schema: typeof TERMINAL_SCHEMA_VERSION;
  /** Identity of this commit. */
  readonly terminalId: string;
  /** The tool call that produced it. */
  readonly callId: string;
  /** Turn and step the call belonged to. */
  readonly turn: number;
  readonly step: number;
  /** Validated domain outcome (minimal H03 fixture). */
  readonly parsed: TerminalResult;
  readonly parsedDigest: string;
  /** Raw provider-side argument text, or an explicit incomplete/ambiguous/missing state. */
  readonly rawArguments: RawArguments;
  /** The session's own `tool/call` argument string. */
  readonly normalizedArguments: NormalizedArguments;
  /** Assistant prose of the same turn. */
  readonly prose: ProseSource;
  /** Digest of the parameter schema this record was validated against. */
  readonly schemaDigest: string;
  /** Commit time, epoch milliseconds. */
  readonly recordedAt: number;
}

declare module '@deepseek-ai/dsh-session' {
  interface SessionEventMap {
    /** One committed Writer terminal, with its separated sources. */
    'c2p/terminal': TerminalRecord;
  }
}

/** How a caller attributes a raw lookup to one observed stream. */
export interface RawLookup {
  /** Trusted session the call belongs to; filters the candidates. */
  readonly sessionId?: SessionId;
  /** Explicit stream to read, when the caller holds one. */
  readonly streamIndex?: number;
}

/**
 * Captures the raw `tool-call-delta` text of every model stream on one host.
 *
 * The capture is passive: it observes the `llm/stream` waterfall's chunk stream
 * without altering it, so the loop sees exactly the chunks the adapter produced.
 *
 * Three properties keep a partial, reused or misattributed source from passing as
 * a whole one:
 *
 * 1. Deltas are keyed by `(streamIndex, callId)`, never by the call id alone, and
 *    each stream records the session the loop stamped on its request. A provider
 *    that reuses one id therefore produces a SECOND entry, and two live sessions
 *    can each read back their own.
 * 2. A source is `captured` only when that call's own `block-end` was observed.
 *    Iterator completion, a normalized failure/abort finish, an abandoned
 *    consumer and a truncated stream all leave `incomplete` with the reason.
 * 3. A lookup that matches several streams without naming one returns
 *    `ambiguous` with the candidates instead of guessing the most recent.
 */
export class TerminalArgumentCapture {
  private streamCount = 0;
  private readonly entries = new Map<string, CallCapture>();
  private readonly byCall = new Map<string, string[]>();

  /**
   * Observe one chunk stream, passing every chunk through unchanged.
   * @param chunks - the downstream stream from the `llm/stream` waterfall.
   * @param ref - the trusted request identity (the loop-stamped session).
   * @returns a stream that records this stream's deltas and its per-call
   *   completion facts, and marks unfinished calls incomplete.
   */
  observe(chunks: AsyncIterable<StreamChunk>, ref: { readonly sessionId?: SessionId } = {},
    onRaw?: (source: CapturedRawArguments) => Promise<void>): AsyncIterable<StreamChunk> {
    const capture = this;
    const streamIndex = ++capture.streamCount;
    const sessionId = ref.sessionId;
    const opened = new Set<string>();
    let completed = false;
    const finishStream = (failure?: string): void => {
      for (const key of opened) {
        const entry = capture.entries.get(key);
        if (entry === undefined) continue;
        if (failure !== undefined && entry.streamFailure === undefined) entry.streamFailure = failure;
      }
    };
    return (async function* observing(): AsyncIterableIterator<StreamChunk> {
      try {
        for await (const chunk of chunks) {
          opened.add(capture.push(streamIndex, sessionId, chunk));
          if (onRaw !== undefined && chunk.type === 'block-end' && chunk.block.type === 'tool-call') {
            const source=capture.raw(chunk.block.id,{streamIndex,...(sessionId === undefined ? {} : {sessionId})});
            if (source.state === 'captured') await onRaw(source);
          }
          yield chunk;
        }
        completed = true;
      } catch (error) {
        finishStream(`the model stream failed: ${describeError(error)}`);
        throw error;
      } finally {
        if (!completed) {
          for (const key of opened) {
            const entry = capture.entries.get(key);
            if (entry !== undefined) entry.abandoned = true;
          }
          finishStream();
        }
      }
    })();
  }

  /**
   * Install the capture on a host context's `llm/stream` waterfall.
   * @param caller - host context carrying the `llm` service.
   * @returns the disposer that removes the listener.
   */
  install(caller: Context, onRaw?: (source: CapturedRawArguments) => Promise<void>): () => void {
    const capture = this;
    const listener = (
      options: { readonly sessionId?: SessionId },
      next: () => AsyncIterable<StreamChunk>,
    ): AsyncIterable<StreamChunk> => capture.observe(next(), { ...(options.sessionId === undefined ? {} : { sessionId: options.sessionId }) },onRaw);
    // `Context.on` returns the exact effect disposer for this listener.
    const remove = caller.on('llm/stream', listener as never) as unknown as () => void;
    return () => { remove(); };
  }

  /**
   * The raw source for one call, attributed to the stream that carried it.
   *
   * @param callId - the tool call to look up.
   * @param lookup - trusted session and/or explicit stream to disambiguate.
   * @returns the captured, incomplete, ambiguous or missing source. An
   *   un-attributable match set is never resolved by recency.
   */
  raw(callId: string, lookup: RawLookup = {}): RawArguments {
    const keys = (this.byCall.get(callId) ?? []).filter((key) => {
      const entry = this.entries.get(key);
      if (entry === undefined) return false;
      if (lookup.streamIndex !== undefined && entry.streamIndex !== lookup.streamIndex) return false;
      if (lookup.sessionId !== undefined && entry.sessionId !== lookup.sessionId) return false;
      return true;
    });
    if (keys.length === 0) {
      const scope = [
        lookup.sessionId === undefined ? undefined : `session ${lookup.sessionId}`,
        lookup.streamIndex === undefined ? undefined : `stream ${String(lookup.streamIndex)}`,
      ].filter((part): part is string => part !== undefined);
      return {
        state: 'not_observed',
        source: 'llm-stream-tool-call-delta',
        reason: `no llm/stream tool-call-delta was observed for this call${scope.length === 0 ? '' : ` in ${scope.join(' / ')}`}`,
      };
    }
    if (keys.length > 1) {
      return {
        state: 'ambiguous',
        source: 'llm-stream-tool-call-delta',
        callId,
        reason: `call ${callId} appears in ${String(keys.length)} observed streams; name a stream to attribute it`,
        candidates: keys.map((key) => {
          const entry = this.entries.get(key)!;
          return {
            streamIndex: entry.streamIndex,
            ...(entry.sessionId === undefined ? {} : { sessionId: entry.sessionId }),
          };
        }),
      };
    }
    const entry = this.entries.get(keys[0]!)!;
    const text = entry.parts.join('');
    const base = {
      source: 'llm-stream-tool-call-delta' as const,
      callId,
      streamIndex: entry.streamIndex,
      ...(entry.sessionId === undefined ? {} : { sessionId: entry.sessionId }),
      ...(entry.name === undefined ? {} : { name: entry.name }),
      text,
      chunks: entry.chunks,
      digest: digestText(text),
      byteLength: Buffer.byteLength(text, 'utf8'),
    };
    if (entry.blockEnded) return { state: 'captured', ...base };
    return { state: 'incomplete', ...base, reason: incompleteReason(entry) };
  }

  /** Forget every captured stream. */
  clear(): void {
    this.entries.clear();
    this.byCall.clear();
    this.streamCount = 0;
  }

  /** Record one chunk into this stream's entry, creating it on first sight. */
  private push(streamIndex: number, sessionId: SessionId | undefined, chunk: StreamChunk): string {
    if (chunk.type === 'tool-call-delta') {
      const key = `${String(streamIndex)}:${chunk.id}`;
      let entry = this.entries.get(key);
      if (entry === undefined) {
        entry = {
          streamIndex,
          ...(sessionId === undefined ? {} : { sessionId }),
          callId: chunk.id,
          parts: [],
          chunks: 0,
          blockEnded: false,
        };
        this.entries.set(key, entry);
        const list = this.byCall.get(chunk.id) ?? [];
        list.push(key);
        this.byCall.set(chunk.id, list);
      }
      if (chunk.name !== undefined) entry.name = chunk.name;
      entry.parts.push(chunk.argumentsDelta);
      entry.chunks += 1;
      return key;
    }
    // The per-call completion fact: the block closing THIS call in THIS stream.
    if (chunk.type === 'block-end' && chunk.block.type === 'tool-call') {
      const key = `${String(streamIndex)}:${chunk.block.id}`;
      const entry = this.entries.get(key);
      if (entry !== undefined) entry.blockEnded = true;
      return key;
    }
    if (chunk.type === 'finish') {
      for (const entry of this.entries.values()) {
        if (entry.streamIndex === streamIndex) entry.finish = chunk.reason.kind;
      }
    }
    return `${String(streamIndex)}:-`;
  }
}

/** One call's deltas and completion facts inside ONE observed model stream. */
interface CallCapture {
  readonly streamIndex: number;
  readonly sessionId?: SessionId;
  readonly callId: string;
  name?: string;
  readonly parts: string[];
  chunks: number;
  /** That call's `block-end` was observed in this stream. */
  blockEnded: boolean;
  /** The stream's finish reason kind, when one was observed. */
  finish?: string;
  /** The stream threw; the message is kept for the reason. */
  streamFailure?: string;
  /** The consumer stopped consuming before the stream ended. */
  abandoned?: boolean;
}

/** Why one observed call is not a complete source. */
function incompleteReason(entry: CallCapture): string {
  if (entry.streamFailure !== undefined) return `${entry.streamFailure} before this call's completion fact`;
  if (entry.abandoned === true) return 'the model stream was abandoned before this call\'s completion fact';
  if (entry.finish !== undefined && entry.finish !== 'stop' && entry.finish !== 'tool-calls') {
    return `the model stream finished with ${entry.finish} before this call's completion fact`;
  }
  return 'the model stream ended without this call\'s block-end completion fact (truncated stream)';
}

/** Render one thrown value for a diagnostic. */
function describeError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/** Why a terminal attempt did not commit. */
export type TerminalRefusalCode =
  /** A second terminal call, or any tool call after the terminal, was denied. */
  | 'terminal-already-recorded'
  /** The terminal call was made without an owning agent session. */
  | 'terminal-without-agent';

/** One recorded refusal, for tests and diagnostics. */
export interface TerminalRefusal {
  readonly code: TerminalRefusalCode;
  readonly message: string;
  readonly tool: string;
  readonly callId?: string;
}

/** Options for {@link installTerminalTool}. */
export interface TerminalOptions {
  /** Host-side raw argument capture to read from. */
  readonly capture: TerminalArgumentCapture;
  /**
   * The agent's own session, taken from the creation window (`setup` receives
   * the unpublished agent). The commit reads its `tool/call` record for the
   * normalized source and appends the durable `c2p/terminal` event to it; the
   * agent scope itself does not expose the session as a service.
   */
  readonly session: Session;
  /** Called once, after the commit event was appended. */
  readonly onCommit?: (record: TerminalRecord) => void;
}

/** One agent's installed terminal tool and its committed state. */
export interface TerminalHandle {
  /** The committed terminal, or undefined when none committed. */
  committed(): TerminalRecord | undefined;
  /** Every refusal this install recorded, in order. */
  refusals(): readonly TerminalRefusal[];
  /** Remove the tool, the guard and the commit listener. */
  dispose(): void;
}

/** Prose of one turn: the assistant text blocks, in order. */
function proseOfTurn(session: Session, turn: number): ProseSource {
  const blocks: string[] = [];
  for (const event of session.snapshotEvents(0 as never)) {
    if (event.type !== 'assistant/message') continue;
    const data = event.data as { turn?: number; content?: readonly { type: string; text?: string }[] };
    if (data.turn !== turn) continue;
    for (const block of data.content ?? []) {
      if (block.type === 'text' && typeof block.text === 'string') blocks.push(block.text);
    }
  }
  const text = blocks.join('\n');
  return { source: 'assistant-message', text, blocks: blocks.length, digest: digestText(text) };
}

/** The session's own record of one tool call: turn, step and argument string. */
function sessionToolCall(session: Session, callId: string): { turn: number; step: number; arguments: string } {
  let found: { turn: number; step: number; arguments: string } | undefined;
  for (const event of session.snapshotEvents(0 as never)) {
    if (event.type !== 'tool/call') continue;
    const data = event.data as { callId?: string; arguments?: string; turn?: number; step?: number };
    if (data.callId === callId && typeof data.arguments === 'string') {
      found = { turn: data.turn ?? 0, step: data.step ?? 0, arguments: data.arguments };
    }
  }
  if (found === undefined) {
    throw new Error(`terminal: no session tool/call event for ${callId}; refusing to invent normalized arguments`);
  }
  return found;
}

/**
 * Install the terminal tool into one agent's scope.
 *
 * The tool validates through the registry, stages the parsed outcome, and commits
 * only when the authoritative `tools/result` for that same call succeeds — a
 * closing text message, a failed validation or a second call never commits. On
 * success the tool marks the turn concluded, so the loop stops after the
 * terminal instead of asking the model for another step.
 *
 * @param agentCtx - the agent scope to install into.
 * @param options - the host capture and optional commit hook.
 * @returns the handle exposing the committed record and refusals.
 */
export function installTerminalTool(agentCtx: Context, options: TerminalOptions): TerminalHandle {
  const refusals: TerminalRefusal[] = [];
  let committed: TerminalRecord | undefined;
  let staged: { callId: string; parsed: TerminalResult } | undefined;

  const refuse = (code: TerminalRefusalCode, message: string, tool: string, callId?: string): string => {
    refusals.push({ code, message, tool, ...(callId === undefined ? {} : { callId }) });
    return message;
  };

  const definition = defineTool({
    name: TERMINAL_TOOL,
    description:
      'Submit the final typed result for this task. Call it exactly once, when the work is complete; ' +
      'no further tool call is accepted afterwards.',
    parameters: TERMINAL_PARAMETERS,
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          recorded: { type: 'boolean', required: true },
          kind: { type: 'string', required: true },
        },
      },
      render: (_args, value) => [{ type: 'text', text: `terminal ${value.kind} recorded: ${String(value.recorded)}` }],
    },
    execute(args, exec) {
      if (committed !== undefined || staged !== undefined) {
        // The guard denies this earlier; this is the in-body backstop.
        throw new Error(refuse('terminal-already-recorded', 'a terminal result was already submitted', TERMINAL_TOOL, exec.callId));
      }
      if (exec.agent === undefined) {
        throw new Error(refuse('terminal-without-agent', 'the terminal requires an owning agent session', TERMINAL_TOOL, exec.callId));
      }
      staged = { callId: exec.callId, parsed: args.result as TerminalResult };
      exec.concludeTurn();
      return Promise.resolve({ recorded: true, kind: (args.result as TerminalResult).kind });
    },
  });

  const unregister = agentCtx.tools.register(definition);

  // Monotonic guard: once a terminal is staged or committed, no further tool call
  // may run for this agent. The terminal is final for its turn.
  const unguard = agentCtx.tools.guard((exec) => {
    if (committed === undefined && staged === undefined) return undefined;
    return refuse(
      'terminal-already-recorded',
      `tool ${exec.name} denied: the terminal result is final for this turn`,
      exec.name,
      exec.callId,
    );
  });

  const onResult = (exec: { readonly callId: string }, result: { readonly isError: boolean }): void => {
    const pending = staged;
    if (pending === undefined || exec.callId !== pending.callId || result.isError) return;
    staged = undefined;
    const session = options.session;
    // Turn, step and the normalized argument string are read from the session's
    // own tool/call record: the execution context does not carry them, and the
    // normalized source must be what the log actually holds.
    const call = sessionToolCall(session, exec.callId);
    const record: TerminalRecord = {
      schema: TERMINAL_SCHEMA_VERSION,
      terminalId: `terminal-${exec.callId}`,
      callId: exec.callId,
      turn: call.turn,
      step: call.step,
      parsed: pending.parsed,
      parsedDigest: digestJson(pending.parsed),
      rawArguments: options.capture.raw(exec.callId, { sessionId: session.id }),
      normalizedArguments: { source: 'session-tool-call', text: call.arguments, digest: digestText(call.arguments) },
      prose: proseOfTurn(session, call.turn),
      schemaDigest: digestJson(TERMINAL_PARAMETERS),
      recordedAt: Date.now(),
    };
    session.append('c2p/terminal', record);
    committed = record;
    options.onCommit?.(record);
  };
  const removeResultListener = agentCtx.on('tools/result', onResult as never) as unknown as () => void;

  return {
    committed: () => committed,
    refusals: () => [...refusals],
    dispose: () => {
      unguard();
      unregister();
      removeResultListener();
    },
  };
}

/** Why a rebuild could not accept a stored record. */
export type TerminalRebuildReason =
  /** The stored value is not a record object at all. */
  | 'record-malformed'
  /** The stored record's schema version is not this module's. */
  | 'schema-version-mismatch'
  /** The stored record is missing a required identity field. */
  | 'record-missing-field'
  /** `parsed` is not a valid member of the minimal terminal union. */
  | 'parsed-invalid'
  /** A stored digest does not match the value it claims to describe. */
  | 'digest-mismatch'
  /** `schemaDigest` is not the digest of this module's parameter schema. */
  | 'schema-digest-mismatch'
  /** The raw source state or its fields are invalid. */
  | 'raw-source-invalid'
  /** Stored records disagree about the same terminal. */
  | 'conflicting-records'
  /** No terminal tool call in this log matches the record. */
  | 'no-matching-tool-call'
  /** The record's normalized arguments differ from the matching call's text. */
  | 'arguments-mismatch'
  /** The record's parsed value does not match the result inside the call's arguments. */
  | 'parsed-mismatch'
  /** The matching call has no successful tool result in this log. */
  | 'no-successful-tool-result'
  /** The caller did not name a session format this reader understands. */
  | 'format-unsupported'
  /** A tool result is not the shape its session format version declares. */
  | 'tool-result-malformed'
  /** A log entry is not an event object. */
  | 'event-malformed'
  /** A tool call is not the object shape this reader can attribute. */
  | 'tool-call-malformed'
  /** Several calls share the id and turn/step, so the record cannot be attributed. */
  | 'ambiguous-call'
  /** A terminal tool call was logged without a committed record. */
  | 'terminal-call-without-record';

/** The outcome of rebuilding a terminal from persisted session events. */
export type TerminalRebuild =
  | { readonly state: 'committed'; readonly record: TerminalRecord }
  | { readonly state: 'absent'; readonly reason: string }
  | {
    readonly state: 'unresolved';
    readonly reason: string;
    /** Stable reason code; callers branch on this rather than on the message. */
    readonly reasonCode: TerminalRebuildReason;
    readonly callId?: string;
  };

/** One terminal call as the log recorded it, with its outcome. */
interface LoggedCall {
  readonly callId: string;
  readonly name?: string;
  readonly turn: number;
  readonly step: number;
  readonly seq: number;
  readonly arguments?: string;
  succeeded: boolean;
  /** An error, synthetic recovery, or malformed correspondence already won. */
  failed: boolean;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0;
}

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
}

/** Whether one value is a member of the minimal H03 terminal union. */
function isTerminalResult(value: unknown): value is TerminalResult {
  if (!isPlainObject(value)) return false;
  if (value.kind === 'draft') {
    const draft = value.draft;
    return isPlainObject(draft) && typeof draft.title === 'string' && typeof draft.body === 'string';
  }
  if (value.kind === 'research_required') return typeof value.gap === 'string';
  if (value.kind === 'blocked') return typeof value.reason === 'string';
  return false;
}

/** Session formats this reader dispatches on. V4 is the 0.2 independent tool message. */
export const SESSION_FORMAT_V3 = 3;
export const SESSION_FORMAT_V4 = 4;

/**
 * Synthetic recovery results. They close an interrupted log; they are not a
 * tool success, a usage observation, a settlement, a refund, or a resend grant.
 */
const SYNTHETIC_RECOVERY_CODES: ReadonlySet<string> = new Set(['TOOL_NOT_STARTED', 'TOOL_OUTCOME_UNKNOWN']);

interface ToolOutcome {
  readonly callId: string;
  readonly turn: number;
  readonly step: number;
  readonly success: boolean;
}

/**
 * Read one tool result in the shape declared by `formatVersion`.
 *
 * V3 is the retired nested `tool-result` block. V4 is one independent
 * `role: 'tool'` message whose `toolCallId` and `isError` sit on the message.
 * The other shape is malformed for that version; there is no field fallback.
 */
function malformed(problem: string): { readonly code: 'tool-result-malformed'; readonly problem: string } {
  return { code: 'tool-result-malformed', problem };
}

/**
 * `isError` may be absent. When the field is present it must be a boolean;
 * a string or number is not a success and not a failure fact.
 */
function readIsError(holder: Record<string, unknown>, problem: string):
  | { readonly isError: boolean }
  | { readonly code: 'tool-result-malformed'; readonly problem: string } {
  if (!Object.hasOwn(holder, 'isError') || holder.isError === undefined) return { isError: false };
  if (typeof holder.isError !== 'boolean') return malformed(problem);
  return { isError: holder.isError };
}

function readErrorIdentity(data: Record<string, unknown>):
  | { readonly code: string | undefined }
  | { readonly code: 'tool-result-malformed'; readonly problem: string } {
  if (!Object.hasOwn(data, 'error') || data.error === undefined) return { code: undefined };
  const error = data.error;
  if (!isPlainObject(error) || typeof error.name !== 'string' || typeof error.code !== 'string'
    || (Object.hasOwn(error, 'reason') && error.reason !== undefined && typeof error.reason !== 'string')) {
    return malformed('tool/result error identity is not { name, code, reason? }');
  }
  return { code: error.code };
}

function readToolOutcome(data: unknown, formatVersion: number):
  | { readonly outcome: ToolOutcome }
  | { readonly code: 'format-unsupported' | 'tool-result-malformed'; readonly problem: string } {
  if (formatVersion !== SESSION_FORMAT_V3 && formatVersion !== SESSION_FORMAT_V4) {
    return { code: 'format-unsupported', problem: `session format ${String(formatVersion)} has no tool-result reader` };
  }
  if (!isPlainObject(data)) return malformed('tool/result data is not an object');
  const turn = isCount(data.turn) ? data.turn : -1;
  const step = isCount(data.step) ? data.step : -1;
  const errorRead = readErrorIdentity(data);
  if ('problem' in errorRead) return errorRead;
  const message = data.message;
  if (!isPlainObject(message)) return malformed('tool/result has no message object');
  let callId: string | undefined;
  let isError = false;
  if (formatVersion === SESSION_FORMAT_V4) {
    if (message.role !== 'tool' || !isNonEmptyString(message.toolCallId)) {
      return malformed('V4 tool/result message is not an independent tool message');
    }
    if (Object.hasOwn(message, 'content') && message.content !== undefined && !Array.isArray(message.content)) {
      return malformed('V4 tool message content is not an array');
    }
    if (Array.isArray(message.content) && message.content.some(
      (block) => isPlainObject(block) && block.type === 'tool-result',
    )) {
      return malformed('V4 tool/result still carries a retired tool-result block');
    }
    const flag = readIsError(message, 'V4 tool message isError must be boolean when present');
    if ('problem' in flag) return flag;
    callId = message.toolCallId;
    isError = flag.isError;
  } else {
    if (Object.hasOwn(message, 'content') && message.content !== undefined && !Array.isArray(message.content)) {
      return malformed('V3 tool/result content is not an array');
    }
    const content = message.content;
    const block = Array.isArray(content) ? content[0] : undefined;
    if (!isPlainObject(block) || block.type !== 'tool-result' || !isNonEmptyString(block.toolCallId)) {
      return malformed('V3 tool/result has no nested tool-result block');
    }
    if (Object.hasOwn(block, 'content') && block.content !== undefined && !Array.isArray(block.content)) {
      return malformed('V3 tool-result block content is not an array');
    }
    const flag = readIsError(block, 'V3 tool-result isError must be boolean when present');
    if ('problem' in flag) return flag;
    callId = block.toolCallId;
    isError = flag.isError;
  }
  if (turn < 0 || step < 0) return malformed('tool/result is missing turn or step');
  const errorCode = errorRead.code;
  if (errorCode !== undefined && !isError) {
    return malformed('tool/result error identity requires isError true');
  }
  const synthetic = errorCode !== undefined && SYNTHETIC_RECOVERY_CODES.has(errorCode);
  return {
    outcome: {
      callId,
      turn,
      step,
      success: !isError && !synthetic && errorCode === undefined,
    },
  };
}

/** Read the tool calls and their real outcomes from a log, in order. */
function loggedCalls(events: readonly SessionEvent[], formatVersion: number):
  | { readonly calls: LoggedCall[] }
  | { readonly code: TerminalRebuildReason; readonly problem: string } {
  const calls: LoggedCall[] = [];
  const byKey = new Map<string, LoggedCall[]>();
  for (const event of events) {
    if (event === null || typeof event !== 'object') {
      return { code: 'event-malformed', problem: 'a session log entry is not an object' };
    }
    if (event.type === 'tool/call') {
      if (!isPlainObject(event.data)) {
        return { code: 'tool-call-malformed', problem: 'tool/call data is not an object' };
      }
      const data = event.data;
      if (Object.hasOwn(data, 'arguments') && data.arguments !== undefined && typeof data.arguments !== 'string') {
        return { code: 'tool-call-malformed', problem: 'tool/call arguments must be a string when present' };
      }
      if (!isNonEmptyString(data.callId) || !isCount(data.turn) || !isCount(data.step)) continue;
      const call: LoggedCall = {
        callId: data.callId,
        ...(typeof data.name === 'string' ? { name: data.name } : {}),
        turn: data.turn,
        step: data.step,
        seq: isCount(event.seq) ? event.seq : -1,
        ...(typeof data.arguments === 'string' ? { arguments: data.arguments } : {}),
        succeeded: false,
        failed: false,
      };
      calls.push(call);
      const key = `${call.callId}\u0000${String(call.turn)}\u0000${String(call.step)}`;
      const list = byKey.get(key) ?? [];
      list.push(call);
      byKey.set(key, list);
      continue;
    }
    if (event.type !== 'tool/result') continue;
    const parsed = readToolOutcome(event.data, formatVersion);
    if ('code' in parsed) return parsed;
    const outcome = parsed.outcome;
    const key = `${outcome.callId}\u0000${String(outcome.turn)}\u0000${String(outcome.step)}`;
    const matches = byKey.get(key) ?? [];
    // Exact callId + turn + step only. A missing or extra match is not guessed
    // from a later call that reused the id.
    if (matches.length !== 1) continue;
    const match = matches[0]!;
    if (!outcome.success) {
      match.succeeded = false;
      match.failed = true;
    } else if (!match.failed) {
      match.succeeded = true;
    }
  }
  return { calls };
}

/** Validate one stored value as a terminal record, structure first. */
function validateRecord(value: unknown): { readonly record: TerminalRecord } | { readonly code: TerminalRebuildReason; readonly problem: string } {
  if (!isPlainObject(value)) return { code: 'record-malformed', problem: 'stored c2p/terminal value is not an object' };
  if (value.schema !== TERMINAL_SCHEMA_VERSION) {
    return { code: 'schema-version-mismatch', problem: `stored record declares schema ${JSON.stringify(value.schema)}` };
  }
  const id = isNonEmptyString(value.terminalId) ? value.terminalId : '(no terminalId)';
  if (!isNonEmptyString(value.terminalId) || !isNonEmptyString(value.callId)
    || !isCount(value.turn) || !isCount(value.step)
    || typeof value.recordedAt !== 'number' || !Number.isFinite(value.recordedAt)) {
    return { code: 'record-missing-field', problem: `record ${id} is missing a required identity field` };
  }
  if (!isTerminalResult(value.parsed)) {
    return { code: 'parsed-invalid', problem: `record ${id} parsed value is not a member of the terminal union` };
  }
  if (typeof value.parsedDigest !== 'string') {
    return { code: 'record-missing-field', problem: `record ${id} has no parsed digest` };
  }
  if (value.parsedDigest !== digestJson(value.parsed)) {
    return { code: 'digest-mismatch', problem: `record ${id} parsed digest does not match its parsed value` };
  }
  const normalized = value.normalizedArguments;
  if (!isPlainObject(normalized) || normalized.source !== 'session-tool-call' || typeof normalized.text !== 'string'
    || typeof normalized.digest !== 'string') {
    return { code: 'record-missing-field', problem: `record ${id} normalizedArguments is malformed` };
  }
  if (normalized.digest !== digestText(normalized.text)) {
    return { code: 'digest-mismatch', problem: `record ${id} normalized digest does not match its text` };
  }
  const prose = value.prose;
  if (!isPlainObject(prose) || prose.source !== 'assistant-message' || typeof prose.text !== 'string'
    || !isCount(prose.blocks) || typeof prose.digest !== 'string') {
    return { code: 'record-missing-field', problem: `record ${id} prose is malformed` };
  }
  if (prose.digest !== digestText(prose.text)) {
    return { code: 'digest-mismatch', problem: `record ${id} prose digest does not match its text` };
  }
  const raw = value.rawArguments;
  if (!isPlainObject(raw)) return { code: 'raw-source-invalid', problem: `record ${id} rawArguments is not an object` };
  if (raw.state === 'not_observed') {
    if (!isNonEmptyString(raw.reason)) {
      return { code: 'raw-source-invalid', problem: `record ${id} not_observed raw source has no reason` };
    }
  } else if (raw.state === 'ambiguous') {
    if (!Array.isArray(raw.candidates) || !isNonEmptyString(raw.reason)) {
      return { code: 'raw-source-invalid', problem: `record ${id} ambiguous raw source has no candidates` };
    }
  } else if (raw.state === 'captured' || raw.state === 'incomplete') {
    if (raw.callId !== value.callId || !isCount(raw.streamIndex) || typeof raw.text !== 'string'
      || !isCount(raw.chunks) || !isCount(raw.byteLength)) {
      return { code: 'raw-source-invalid', problem: `record ${id} raw source fields are invalid` };
    }
    if (typeof raw.digest !== 'string') {
      return { code: 'record-missing-field', problem: `record ${id} raw source has no digest` };
    }
    if (raw.state === 'incomplete' && !isNonEmptyString(raw.reason)) {
      return { code: 'raw-source-invalid', problem: `record ${id} incomplete raw source has no reason` };
    }
    if (raw.digest !== digestText(raw.text)) {
      return { code: 'digest-mismatch', problem: `record ${id} raw digest does not match its text` };
    }
  } else {
    return { code: 'raw-source-invalid', problem: `record ${id} raw source state ${JSON.stringify(raw.state)} is invalid` };
  }
  if (typeof value.schemaDigest !== 'string') {
    return { code: 'record-missing-field', problem: `record ${id} has no schema digest` };
  }
  if (value.schemaDigest !== digestJson(TERMINAL_PARAMETERS)) {
    return { code: 'schema-digest-mismatch', problem: `record ${id} schema digest is not this module's parameter schema` };
  }
  return { record: value as unknown as TerminalRecord };
}

/** Whether two records describe the exact same terminal. */
function sameRecord(a: TerminalRecord, b: TerminalRecord): boolean {
  return a.terminalId === b.terminalId && a.callId === b.callId && a.turn === b.turn && a.step === b.step
    && a.parsedDigest === b.parsedDigest && a.schemaDigest === b.schemaDigest
    && a.normalizedArguments.text === b.normalizedArguments.text
    && a.normalizedArguments.digest === b.normalizedArguments.digest
    && a.prose.text === b.prose.text && a.prose.digest === b.prose.digest
    && a.rawArguments.state === b.rawArguments.state
    && JSON.stringify(a.rawArguments) === JSON.stringify(b.rawArguments);
}

/**
 * Rebuild the committed terminal from a session log's events.
 *
 * This is the restart path: it reads only what the log persisted, and it
 * VALIDATES what it reads instead of trusting it. A record is accepted only when
 * its structure, identity fields, minimal union member, every digest and its
 * schema digest are valid; EVERY stored record is validated before duplicates are
 * judged (identical repeats are idempotent, any disagreement is a conflict, never
 * first- or last-one-wins); and the log must hold the matching `c2p_terminal`
 * call — attributed by call id, turn and step — whose recorded arguments equal the
 * record's normalized text and whose tool result reports success through the
 * tool-result block's `isError`. Anything else is `unresolved` with a stable
 * reason code, and nothing is reconstructed from closing text or call arguments.
 *
 * @param events - the session's events, in log order.
 * @param formatVersion - the session header's format. V4 reads independent tool
 *   messages; V3 reads nested tool-result blocks. Other versions are refused.
 * @returns the rebuild result.
 */
export function rebuildTerminal(events: readonly SessionEvent[], formatVersion: number): TerminalRebuild {
  const logged = loggedCalls(events, formatVersion);
  if ('code' in logged) {
    return { state: 'unresolved', reasonCode: logged.code, reason: logged.problem };
  }
  const calls = logged.calls;
  const stored: unknown[] = [];
  for (const event of events) {
    if (event.type === 'c2p/terminal') stored.push(event.data);
  }
  if (stored.length === 0) {
    const terminalCall = calls.find((call) => call.name === TERMINAL_TOOL);
    if (terminalCall !== undefined) {
      return {
        state: 'unresolved',
        reasonCode: 'terminal-call-without-record',
        reason: 'a terminal tool call was logged without a committed c2p/terminal record',
        callId: terminalCall.callId,
      };
    }
    return { state: 'absent', reason: `no ${TERMINAL_TOOL} call and no c2p/terminal record in this log` };
  }

  // Every stored record is validated first, so a damaged later record cannot hide
  // behind an intact first one.
  const validated: TerminalRecord[] = [];
  for (const value of stored) {
    const result = validateRecord(value);
    if ('code' in result) {
      const callId = isPlainObject(value) && isNonEmptyString(value.callId) ? value.callId : undefined;
      return {
        state: 'unresolved',
        reasonCode: result.code,
        reason: result.problem,
        ...(callId === undefined ? {} : { callId }),
      };
    }
    validated.push(result.record);
  }

  const first = validated[0]!;
  for (const other of validated.slice(1)) {
    if (!sameRecord(first, other)) {
      return {
        state: 'unresolved',
        reasonCode: 'conflicting-records',
        reason: `the log holds ${String(validated.length)} disagreeing ${TERMINAL_TOOL} records`,
        callId: first.callId,
      };
    }
  }

  // Correspondence with the real call: id + name + turn/step, then the recorded
  // arguments, then a result whose tool-result block reports success.
  const named = calls.filter((call) => call.callId === first.callId && call.name === TERMINAL_TOOL);
  const scoped = named.filter((call) => call.turn === first.turn && call.step === first.step);
  if (scoped.length === 0) {
    return {
      state: 'unresolved',
      reasonCode: 'no-matching-tool-call',
      reason: `record ${first.terminalId} has no ${TERMINAL_TOOL} tool call at turn ${String(first.turn)} step ${String(first.step)}`,
      callId: first.callId,
    };
  }
  if (scoped.length > 1) {
    return {
      state: 'unresolved',
      reasonCode: 'ambiguous-call',
      reason: `record ${first.terminalId} matches ${String(scoped.length)} ${TERMINAL_TOOL} calls at turn ${String(first.turn)} step ${String(first.step)}`,
      callId: first.callId,
    };
  }
  const call = scoped[0]!;
  if (call.arguments !== first.normalizedArguments.text) {
    return {
      state: 'unresolved',
      reasonCode: 'arguments-mismatch',
      reason: `record ${first.terminalId} normalized arguments differ from the logged ${TERMINAL_TOOL} call`,
      callId: first.callId,
    };
  }
  // The parsed value must be the result INSIDE the call's own arguments; two
  // independently self-consistent digests are not a correspondence.
  let parsedFromCall: unknown;
  try {
    parsedFromCall = (JSON.parse(call.arguments ?? '') as { result?: unknown }).result;
  } catch {
    return {
      state: 'unresolved',
      reasonCode: 'arguments-mismatch',
      reason: `record ${first.terminalId}: the logged ${TERMINAL_TOOL} arguments are not parsable JSON`,
      callId: first.callId,
    };
  }
  if (digestJson(parsedFromCall) !== first.parsedDigest) {
    return {
      state: 'unresolved',
      reasonCode: 'parsed-mismatch',
      reason: `record ${first.terminalId} parsed value is not the result of the logged ${TERMINAL_TOOL} arguments`,
      callId: first.callId,
    };
  }
  if (!call.succeeded) {
    return {
      state: 'unresolved',
      reasonCode: 'no-successful-tool-result',
      reason: `record ${first.terminalId} has no successful ${TERMINAL_TOOL} tool result in this log`,
      callId: first.callId,
    };
  }
  return { state: 'committed', record: first };
}
