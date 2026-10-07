/**
 * `@code2paper/dsh-bundle/tools` — the Code2Paper agent preset's model-facing row.
 *
 * This module is mounted INSIDE an agent scope by the `code2paper` preset
 * (`presets/code2paper/agent.cordis.yml`). The preset machinery mounts one
 * standing composition per preset and every agent joined to that preset shares
 * it, so this plugin must never keep per-agent state in its own closure: state
 * is keyed by the session the executing agent reports.
 *
 * It injects the host-plane `code2paperBridge` service. That is the plane split
 * H01 verifies: the bridge exists once for the whole process, the tool row
 * exists once per standing preset composition, and the tool is visible only to
 * agents joined to that composition.
 *
 * Like the bundle root this module has NO default export: the 0.1.5-rc.3
 * Loader prefers `exports.default`, which would drop this row's `name`/`inject`
 * metadata.
 */

import type { Context } from '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';

/** Stable Cordis plugin name of the preset's tool row. */
export const name = 'code2paper-tools';

/** The row needs the tool registry and the host-plane bridge. */
export const inject: readonly string[] = ['tools', 'code2paperBridge'];

/** Model-facing tool name. Development probe for the H01 composition spike. */
export const PROBE_TOOL = 'c2p_bridge_probe';

/**
 * Register the bundle's model-facing row.
 * @param ctx - the preset subtree context (an agent's scope).
 */
export function apply(ctx: Context): void {
  ctx.tools.register(defineTool({
    name: PROBE_TOOL,
    description:
      'Code2Paper bridge probe (development composition check). Reports the calling session\'s ' +
      'own bridge ledger and the host composition it is joined to. It never reads another ' +
      'session\'s state.',
    parameters: {
      note: {
        type: 'string',
        description: 'Optional note to append to this session\'s own ledger before reporting it.',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          sessionId: { type: 'string', required: true },
          presetId: { type: 'string', required: true },
          hostGeneration: { type: 'integer', required: true },
          noteCount: { type: 'integer', required: true },
          notes: { type: 'array', required: true, items: { type: 'string' } },
        },
      },
      render: (_args, value) => [{
        type: 'text',
        text:
          `Code2Paper bridge: session ${value.sessionId} on preset "${value.presetId}" ` +
          `(host generation ${String(value.hostGeneration)}) holds ${String(value.noteCount)} note(s).`,
      }],
    },
    execute(args, exec) {
      if (exec.agent === undefined) {
        throw new Error(`${PROBE_TOOL} requires an owning agent session`);
      }
      const bridge = ctx.code2paperBridge;
      const presetId = bridge.composedPreset(exec.agent.ctx);
      const ledger = bridge.record(exec.agent.session.id, args.note ?? '');
      return Promise.resolve({
        sessionId: ledger.sessionId,
        presetId,
        hostGeneration: bridge.hostGeneration,
        noteCount: ledger.notes.length,
        notes: [...ledger.notes],
      });
    },
  }));
}

/** Private bootstrap binding; the model never supplies a task or session. */
export interface ScopedReadAuthority {
  readonly sessionId: string;
  read(grantId: string, offset: number, length: number): Promise<{ readonly model_text: string; readonly delivered_bytes: number }>;
  /** Exhaustion/integrity failure stops the owner loop before another step. */
  stop(error: unknown): Promise<void>;
}

/** V2-only registration. V1's single terminal tool surface remains unchanged. */
export const SCOPED_READ_PARAMETERS = {
  grant_id: { type: 'string', required: true },
  offset: { type: 'integer', required: true },
  length: { type: 'integer', required: true },
} as const;

export function createScopedReadTool(authority: ScopedReadAuthority) {
  const tool = defineTool({
    name: 'c2p_read',
    description: 'Read a bounded UTF-8 range from an explicit Kernel-issued grant. Navigation is not evidence. No paths, new grants, scope changes or evidence promotion are accepted.',
    parameters: SCOPED_READ_PARAMETERS,
    output: {
      schema: { type: 'object', additionalProperties: false, properties: {
        model_text: { type: 'string', required: true },
        delivered_bytes: { type: 'integer', required: true },
      } },
      render: (_args, value) => [{ type: 'text', text: value.model_text }],
    },
    execute: async (args, exec) => {
      try {
        if (exec.agent?.session.id !== authority.sessionId) throw new Error('read_session_binding_invalid');
        const value = await authority.read(args.grant_id, args.offset, args.length);
        if (Buffer.byteLength(value.model_text, 'utf8') !== value.delivered_bytes) throw new Error('read_result_bytes_invalid');
        return value;
      } catch (error) {
        await authority.stop(error);
        throw error;
      }
    },
  });
  // defineTool's implicit root is open. Close the same compiled schema object
  // used by its execution validator and published to the actual SDK renderer.
  tool.parameters.additionalProperties = false;
  return tool;
}

export function installScopedRead(ctx: Context, authority: ScopedReadAuthority): void {
  ctx.tools.register(createScopedReadTool(authority));
}

