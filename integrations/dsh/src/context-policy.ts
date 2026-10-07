/** V2 context restoration on the real append-only DSH Session surface.
 * Capsules and summary text cannot satisfy exact material requirements.
 * This module never calls a provider, drops an obligation or rewrites prose.
 */
import { createHash } from 'node:crypto';
import type { Context } from '@deepseek-ai/cordis';
import { createUserMessage } from '@deepseek-ai/dsh-llm';
import type { RequestMessage } from '@deepseek-ai/dsh-llm';
import type { Session, SessionEvent } from '@deepseek-ai/dsh-session';

export interface MaterialScope {
  readonly executionId: string;
  readonly taskId: string;
  readonly sessionId: string;
  readonly epoch: number;
  readonly revision: number;
  readonly snapshotDigest: string;
}

export interface RequiredMaterial {
  readonly id: string;
  readonly kind: 'author_surface' | 'exact_excerpt' | 'occurrence' | 'formula' | 'writer_task_view';
  readonly text: string;
  /** Digest of these original bytes, not a summary or capsule digest. */
  readonly bytesDigest: string;
}

declare module '@deepseek-ai/dsh-llm' {
  interface MessageSourceMap {
    'code2paper-material': {
      kind: 'code2paper-material';
      scope: MaterialScope;
      materialId: string;
      materialKind: RequiredMaterial['kind'];
      bytesDigest: string;
    };
  }
}

function sameScope(a: MaterialScope, b: MaterialScope): boolean {
  return a.executionId === b.executionId && a.taskId === b.taskId && a.sessionId === b.sessionId && a.epoch === b.epoch
    && a.revision === b.revision && a.snapshotDigest === b.snapshotDigest;
}

function exactMessage(message: RequestMessage, scope: MaterialScope, material: RequiredMaterial): boolean {
  const source = 'source' in message ? message.source : undefined;
  return message.role === 'user' && source?.kind === 'code2paper-material'
    && sameScope(source.scope, scope) && source.materialId === material.id
    && source.materialKind === material.kind && source.bytesDigest === material.bytesDigest
    && message.content.length === 1 && message.content[0]?.type === 'text'
    && message.content[0].text === material.text;
}

/** Private bootstrap supplies original, source-validated frozen owner bytes. */
export class MaterialRestoration {
  readonly scope: MaterialScope;
  readonly required: readonly RequiredMaterial[];
  constructor(scope: MaterialScope, required: readonly RequiredMaterial[]) {
    if (!scope.executionId || !scope.taskId || !scope.sessionId || !Number.isSafeInteger(scope.epoch) || scope.epoch < 0
      || !Number.isSafeInteger(scope.revision) || scope.revision < 0
      || !/^sha256:[0-9a-f]{64}$/.test(scope.snapshotDigest) || required.length === 0) {
      throw new Error('material_scope_invalid');
    }
    const ids = new Set<string>();
    this.scope = Object.freeze({ ...scope });
    this.required = Object.freeze(required.map(material => {
      if (!material.id || ids.has(material.id) || !material.text
        || !['author_surface', 'exact_excerpt', 'occurrence', 'formula', 'writer_task_view'].includes(material.kind)
        || `sha256:${createHash('sha256').update(material.text, 'utf8').digest('hex')}` !== material.bytesDigest) {
        throw new Error('material_binding_invalid');
      }
      ids.add(material.id);
      return Object.freeze({ ...material });
    }));
  }

  missing(messages: readonly RequestMessage[]): readonly RequiredMaterial[] {
    return this.required.filter(material => !messages.some(message => exactMessage(message, this.scope, material)));
  }

  assertCurrent(current: MaterialScope): void {
    if (!sameScope(this.scope,current)) throw new Error('material_scope_stale');
  }

  /** Use the actual SDK admitted user batch so its system stays first. */
  recoveryMessages(messages: readonly RequestMessage[], current: MaterialScope) {
    this.assertCurrent(current);
    return this.missing(messages).map(material=>createUserMessage({
      source:{kind:'code2paper-material',scope:this.scope,materialId:material.id,
        materialKind:material.kind,bytesDigest:material.bytesDigest},content:[{type:'text',text:material.text}],
    }));
  }

  /** Appends the actual recovery messages; callers await session durability. */
  restore(session: Session, current: MaterialScope): readonly SessionEvent<'user/message'>[] {
    this.assertCurrent(current);
    if (String(session.id) !== this.scope.sessionId) throw new Error('material_session_invalid');
    const added = this.missing(session.deriveMessages()).map(material => createUserMessage({
      source: { kind: 'code2paper-material', scope: this.scope, materialId: material.id,
        materialKind: material.kind, bytesDigest: material.bytesDigest },
      content: [{ type: 'text', text: material.text }],
    }));
    return added.map(message => session.append('user/message',message,{surfaceOp:'append'}));
  }

  /** Final actual assembly guard, before reserve/token measurement/dispatch. */
  assertRequest(messages: readonly RequestMessage[], current: MaterialScope): void {
    this.assertCurrent(current);
    if (this.missing(messages).length !== 0) throw new Error('material_restoration_required');
  }
}

/** Restore after downstream compaction but before the loop assembles its step. */
export function installMaterialRestoration(ctx: Context, policy: MaterialRestoration,
  current: () => Promise<MaterialScope>, admittedBatch=false): void {
  ctx.on('agent/pre-step',async (payload,next) => {
    const decision = await next();
    if (decision.kind === 'reject') return decision;
    const scope = await current();
    if (String(payload.agent.session.id) !== policy.scope.sessionId) throw new Error('material_session_invalid');
    if (admittedBatch) {
      const visible=[...payload.agent.session.deriveMessages(),...decision.messages];
      const messages=[...decision.messages,...policy.recoveryMessages(visible,scope)];
      policy.assertRequest([...payload.agent.session.deriveMessages(),...messages],scope);
      return {...decision,messages};
    }
    policy.restore(payload.agent.session,scope);
    if (!await ctx.sessions.flush(payload.agent.session)) throw new Error('material_restore_not_durable');
    policy.assertRequest(payload.agent.session.deriveMessages(),scope);
    return decision;
  });
}
