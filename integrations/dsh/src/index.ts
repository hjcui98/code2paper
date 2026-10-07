/**
 * `@code2paper/dsh-bundle` — the Code2Paper DSH bundle root (HOST plane).
 *
 * This module publishes the `code2paperBridge` service and the two composition
 * entry points an agent creation uses:
 *
 * - {@link mountCode2PaperPreset} — root creation, awaited inside
 *   `agents.create({ setup })`, so the standing preset composition exists before
 *   the agent is published and before any first prompt material is assembled.
 * - {@link applyChildComposition} — child creation, synchronous by contract: it
 *   binds the child to the SAME standing generation its parent runs on instead
 *   of re-resolving the preset (which would re-read the file and could hand the
 *   child a different generation than its parent's history was produced under).
 *
 * Model-facing rows live in the preset (`./tools`), mounted once per preset and
 * joined per agent scope. This module registers no model-facing tool, so a
 * host-only reader never sees a task tool.
 *
 * The module deliberately has NO default export. The 0.1.5-rc.3 Loader's
 * `unwrapExports` prefers `exports.default`, so a default export would replace
 * the named `name`/`inject`/`Config`/`apply` surface this bundle is composed by
 * and silently drop the injection metadata.
 */

import { Service, type Context } from '@deepseek-ai/cordis';
import type { AgentPreset } from '@deepseek-ai/dsh-agent-preset-registry';
import z from '@deepseek-ai/schemastery';

import { mkdirSync } from 'node:fs';
import { prepare_projection } from './writer-request.js';
import type { WriterComposition, WriterProjectionAuthority, WriterWireProjectionV1 } from './writer-request.js';
import { WireError } from './wire.js';

/** Stable Cordis plugin name of the bundle root row. */
export const name = 'code2paper-bridge';

/**
 * The host row composes no model-facing row, but it does need the preset
 * roster: the composition entry points below resolve through this row, and the
 * roster must exist before the bridge is published.
 */
export const inject: readonly string[] = ['agentPresets'];

/**
 * Deployment configuration. `presetRoot` and `runRoot` are required on purpose:
 * a composition that cannot name its preset directory or its writable run root
 * must fail at activation rather than guess one.
 */
export const Config = z.object({
  presetId: z.string().default('code2paper'),
  presetRoot: z.string().required(),
  runRoot: z.string().required(),
});

/** Validated shape of {@link Config}. */
export interface BridgeConfig {
  readonly presetId: string;
  readonly presetRoot: string;
  readonly runRoot: string;
}

/** One session's own note ledger, as the bridge hands it back. */
export interface SessionLedger {
  readonly sessionId: string;
  readonly notes: readonly string[];
}

/** Monotonic host-composition generation, so two hosts are distinguishable. */
let hostGenerations = 0;

/**
 * The host-plane bridge.
 *
 * It is intentionally thin: H01 proves the composition and the plane split, not
 * the kernel protocol (C04). Its only mutable state is a per-session note ledger,
 * keyed by the session the executing agent reports — never by mount-local state,
 * because a standing preset mount is shared by every agent joined to it.
 */
export class Code2PaperBridge extends Service {
  /** Host plane: the bridge needs the roster, nothing else. */
  static readonly inject: readonly string[] = ['agentPresets'];

  /** Deployment configuration this host composition was built with. */
  static readonly Config = Config;

  private readonly ledgers = new Map<string, string[]>();
  private readonly generation: number;
  /**
   * The plugin context this service was composed on. Held rather than read as
   * `this.ctx` because a traced service's `this.ctx` is rebound to the caller;
   * the composition entry points must resolve through the row's own inject
   * store, not through whoever calls them.
   */
  private readonly hostCtx: Context;

  constructor(ctx: Context, config: BridgeConfig) {
    super(ctx, 'code2paperBridge');
    this.hostCtx = ctx;
    this.generation = ++hostGenerations;
    this.presetId = config.presetId;
    this.presetRoot = config.presetRoot;
    this.runRoot = config.runRoot;
    // The run root is the one directory this composition may write in; create it
    // here so every later caller sees a real path instead of a promise.
    mkdirSync(this.runRoot, { recursive: true });
  }

  /** Preset this deployment composes its agents from. */
  readonly presetId: string;

  /** Absolute directory scanned for the deployment's presets. */
  readonly presetRoot: string;

  /** Absolute writable run root for this development composition. */
  readonly runRoot: string;

  /** This host composition's generation number. */
  get hostGeneration(): number {
    return this.generation;
  }

  /** Number of sessions this bridge has recorded state for. */
  get sessionCount(): number {
    return this.ledgers.size;
  }

  /** Host-only C00 preparation; never registered in the model tool plane. */
  prepare_projection(input: Uint8Array, composition: WriterComposition, authority: WriterProjectionAuthority): Promise<WriterWireProjectionV1> {
    if (authority.agentHost.code2paperBridge.hostGeneration !== this.generation) {
      throw new WireError('projection_host_mismatch');
    }
    return prepare_projection(authority.agentHost, input, composition, authority);
  }

  /**
   * Append one note to a session's own ledger.
   * @param sessionId - the executing agent's session identity.
   * @param note - the note to append; an empty note only reads the ledger.
   * @returns that session's ledger after the append.
   */
  record(sessionId: string, note: string): SessionLedger {
    const current = this.ledgers.get(sessionId) ?? [];
    if (note !== '') this.ledgers.set(sessionId, [...current, note]);
    return this.read(sessionId);
  }

  /**
   * Read one session's ledger.
   * @param sessionId - the session identity to read.
   * @returns the session's notes, empty for a session this bridge never saw.
   */
  read(sessionId: string): SessionLedger {
    return { sessionId, notes: [...(this.ledgers.get(sessionId) ?? [])] };
  }

  /** Read the agent's actual standing composition, never session metadata. */
  composedPreset(agentCtx: Context): string {
    const presetId = this.hostCtx.agentPresets.composedPreset(agentCtx);
    if (presetId === undefined) {
      throw new Error('code2paper bridge requires an agent joined to a preset');
    }
    return presetId;
  }

  /**
   * Compose a ROOT agent from the deployment's preset.
   *
   * Await it inside `agents.create({ setup })`: setup runs while the agent is
   * unpublished, so a rejected composition rolls the whole creation back and no
   * observer ever sees a half-composed session.
   *
   * @param agentCtx - the unpublished agent scope.
   * @param presetId - preset to mount; defaults to the configured one.
   * @returns the preset that was composed.
   */
  async mountPreset(agentCtx: Context, presetId?: string): Promise<AgentPreset> {
    return this.hostCtx.agentPresets.mount(agentCtx, presetId ?? this.presetId);
  }

  /**
   * Join a CHILD agent to the same standing preset generation its parent runs on.
   *
   * Synchronous and file-free by contract — that is what lets a child creation
   * window call it inside a synchronous `setup`. Re-resolving the parent's preset
   * by id would re-read the roster and could hand the child a generation its
   * parent's history was never produced under.
   *
   * @param agentCtx - the unpublished child scope.
   * @param parentCtx - the parent agent's scope context.
   * @returns the preset id joined, or undefined when the parent joined none.
   */
  joinChild(agentCtx: Context, parentCtx: Context): string | undefined {
    return this.hostCtx.agentPresets.composeFrom(agentCtx, parentCtx);
  }
}

declare module '@deepseek-ai/cordis' {
  interface Context {
    /** The Code2Paper host bridge; provided by this bundle's root row. */
    code2paperBridge: Code2PaperBridge;
  }
}

/**
 * Mount the bundle root: publish the host-plane bridge.
 * @param ctx - the host context the bundle row was activated on.
 * @param config - validated {@link BridgeConfig}.
 */
export function apply(ctx: Context, config: BridgeConfig): void {
  ctx.plugin(Code2PaperBridge, config);
}

/**
 * Compose a ROOT agent from the deployment's preset.
 *
 * Call from `agents.create({ setup })` and await it: setup runs while the agent
 * is unpublished, so a rejected composition rolls the whole creation back and no
 * observer ever sees a half-composed session.
 *
 * @param caller - a context whose plugin injects `code2paperBridge`. The caller
 *   owns the dependency; the agent scope is only the mount target, so reading
 *   the service through it would need the agent scope to declare the inject.
 * @param agentCtx - the unpublished agent scope.
 * @param presetId - preset to mount; defaults to the deployment's configured one.
 * @returns the preset that was composed.
 */
export async function mountCode2PaperPreset(
  caller: Context,
  agentCtx: Context,
  presetId?: string,
): Promise<AgentPreset> {
  return caller.code2paperBridge.mountPreset(agentCtx, presetId);
}

/**
 * Join a CHILD agent to the same standing preset generation its parent runs on.
 *
 * Synchronous and file-free by contract — that is what lets a child creation
 * window call it inside a synchronous `setup`. Re-resolving the parent's preset
 * by id would re-read the roster and could hand the child a generation its
 * parent's history was never produced under.
 *
 * @param caller - a context whose plugin injects `code2paperBridge`.
 * @param agentCtx - the unpublished child scope.
 * @param parentCtx - the parent agent's scope context.
 * @returns the preset id joined, or undefined when the parent joined none.
 */
export function applyChildComposition(caller: Context, agentCtx: Context, parentCtx: Context): string | undefined {
  return caller.code2paperBridge.joinChild(agentCtx, parentCtx);
}
