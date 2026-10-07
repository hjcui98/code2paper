/**
 * B02 development-only probe for the isolated toolchain.
 *
 * The probe exists to prove two things at the *installed* bundle location rather
 * than inside this repository:
 *
 * 1. `@deepseek-ai/cordis` and the DSH API packages are external peers. They are
 *    never vendored into this package; Node resolves them from the host
 *    installation that loads the bundle.
 * 2. The type surface this bundle is written against is the frozen runtime's
 *    declaration surface, so a typecheck that passes here also describes the
 *    modules the loader will hand to `apply()`.
 *
 * It is built to `dev/toolchain/build/peer-probe.js` as a compiler/type-surface
 * probe. `staging.test.ts` separately resolves and imports the shared runtime
 * from the staged package. This probe is never copied into the runtime package.
 */

import { createRequire } from 'node:module';

import { Service } from '@deepseek-ai/cordis';

import type { AgentFactory } from '@deepseek-ai/dsh-agent';
import type { AgentPresetRegistry } from '@deepseek-ai/dsh-agent-preset-registry';
import type { SessionStore } from '@deepseek-ai/dsh-session';
import type { ToolDefinition } from '@deepseek-ai/dsh-tools';

export const PROBE_ID = '@code2paper/dsh-bundle:dev-toolchain-probe';

/** Runtime import check: a real cordis export must be loadable from here. */
export function cordisRuntimeIdentity(): { readonly name: string; readonly kind: string } {
  return { name: Service.name, kind: typeof Service };
}

/** Resolve a bare specifier with Node's own rules, relative to this module. */
export function resolvePeer(specifier: string): string {
  return createRequire(import.meta.url).resolve(specifier);
}

/**
 * Type-surface check: these declarations must resolve to the frozen runtime's
 * `lib/types` files, not to a second copy of Cordis/DSH in this repository.
 */
export function describePeerTypes(
  presets: AgentPresetRegistry | undefined,
  factory: AgentFactory | undefined,
  tool: ToolDefinition | undefined,
  sessions: SessionStore | undefined,
): string {
  return [presets, factory, tool, sessions]
    .map((value) => (value === undefined ? 'absent' : typeof value))
    .join(',');
}
