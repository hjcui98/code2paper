/** Keep DSH's compaction transaction; replace only its auxiliary-call hook. */
import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { Message, ToolSchema, ContentBlock, TokenUsage } from '@deepseek-ai/dsh-llm';
import { BasicCompactionEngine, type BasicCompactionConfig } from '@deepseek-ai/dsh-compaction-basic';
import { SessionLogOffset } from '@deepseek-ai/dsh-session';
import type { JsonObject } from './wire.js';

export interface CompactionInput {
  readonly messages: readonly Message[];
  readonly tools?: readonly ToolSchema[];
}

/** Supplied by the trusted host after the original ledger has settled the child.
 * This receipt cannot be supplied by a model or inferred from a returned string.
 */
export interface SettledCompaction {
  readonly role: 'compaction';
  readonly parentSessionId: string;
  readonly childSessionId: string;
  readonly requestId: string;
  readonly provider: string;
  readonly model: string;
  readonly maxTokens: number;
  readonly rawOutput: readonly ContentBlock[];
  readonly usage: TokenUsage;
  readonly settlementRef: JsonObject;
  readonly naturalExhaustion: true;
}

export interface CompactionAuthority {
  /** Runs an independently bound DSH child through the same original recorder.
   * Must reject on quota, unknown usage, cancellation, or incomplete transport.
   */
  summarize(input: CompactionInput, parent: Agent, signal?: AbortSignal): Promise<SettledCompaction>;
}

/** No direct ctx.llm.stream fallback, invisible injection, or free retries. */
export class EpochCompactionEngine extends BasicCompactionEngine {
  private readonly authority: CompactionAuthority;
  private readonly attemptedTransactions = new Set<string>();
  constructor(ctx: Context, authority: CompactionAuthority, config: BasicCompactionConfig = {}) {
    // One authorized auxiliary request per transaction; caller can explicitly
    // start another transaction after re-admission, never a hidden retry.
    if ((config.compactionRetries ?? 0) !== 0 || (config.maxOverflowRetries ?? 0) !== 0
      || config.modelPolicies?.some(policy => (policy.compactionRetries ?? 0) !== 0
        || (policy.maxOverflowRetries ?? 0) !== 0)) throw new Error('compaction_implicit_retry_unsupported');
    super(ctx, { ...config, compactionRetries: 0, maxOverflowRetries: 0 });
    this.authority = authority;
  }

  protected override async summarize(input: CompactionInput, parent: Agent, signal?: AbortSignal) {
    signal?.throwIfAborted();
    const start = parent.session.snapshotEvents(SessionLogOffset(0)).findLast(event => event.type === 'compaction/start');
    if (start?.type !== 'compaction/start') throw new Error('compaction_transaction_required');
    const transaction = `${String(parent.session.id)}:${String(start.data.compactionId)}`;
    if (this.attemptedTransactions.has(transaction)) throw new Error('compaction_transaction_request_already_consumed');
    this.attemptedTransactions.add(transaction);
    const result = await this.authority.summarize(input, parent, signal);
    signal?.throwIfAborted();
    const policy=this.config.modelPolicies.find(item=>item.provider === parent.options.provider && item.model === parent.options.model);
    const cap=policy?.maxTokens ?? this.config.maxTokens;
    if (result.role !== 'compaction' || result.parentSessionId !== String(parent.session.id)
      || !result.childSessionId || result.childSessionId === result.parentSessionId || !result.requestId
      || result.naturalExhaustion !== true || !result.provider || !result.model
      || result.provider !== parent.options.provider || result.model !== parent.options.model
      || !Number.isSafeInteger(result.maxTokens) || result.maxTokens <= 0
      || result.maxTokens > cap || !result.usage || !Array.isArray(result.rawOutput) || !result.settlementRef
      || !Number.isSafeInteger(result.usage.inputTokens) || result.usage.inputTokens < 0
      || !Number.isSafeInteger(result.usage.outputTokens) || result.usage.outputTokens < 0
      || [result.usage.cacheReadTokens ?? 0,result.usage.cacheWriteTokens ?? 0]
        .some(value=>!Number.isSafeInteger(value) || value < 0)
      || result.usage.inputTokens+(result.usage.cacheReadTokens ?? 0)+(result.usage.cacheWriteTokens ?? 0)
        +result.usage.outputTokens <= 0
      || result.usage.outputTokens > result.maxTokens
      || result.settlementRef['media_type'] !== 'application/json'
      || typeof result.settlementRef['bytes_digest'] !== 'string'
      || !/^sha256:[0-9a-f]{64}$/.test(result.settlementRef['bytes_digest'])) {
      throw new Error('compaction_settlement_unproven');
    }
    // Only text becomes a derived checkpoint. Never execute model tools or
    // promote reasoning, source labels, or summary prose to exact evidence.
    const summary = result.rawOutput.filter(block => block.type === 'text')
      .map(block => ({ type: 'text' as const, text: block.text }));
    if (!summary.some(block => block.text.trim())) throw new Error('compaction_summary_empty');
    return { summary, rawOutput: [...result.rawOutput], provider: result.provider,
      model: result.model, maxTokens: result.maxTokens, usage: { ...result.usage } };
    // Deliberately unmarked: this is a separate child loop, not the parent's
    // ctx.llm.stream call. DSH must not fabricate an auxiliary call marker.
  }
}
