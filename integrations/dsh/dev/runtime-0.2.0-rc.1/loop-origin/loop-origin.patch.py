#!/usr/bin/env python3
"""Apply the loop-origin runtime source patch to a copied 0.2.0-rc.1 runtime.

Rebuildable contract: every hunk verifies the exact original bytes before
replacing them and refuses on any drift. The patch touches the compiled entry
and the declaration surface of two runtime packages
(`@deepseek-ai/dsh-agent-loop` and `@deepseek-ai/dsh-llm`): `lib/index.js` and
`lib/types/index.d.ts` (runtime-private dispatch origin per the 2026-10-01
interface ruling §6.2, revised by the 2026-10-01/02 acceptances: the public
surface must not be able to consume, mint or reset the origin — including via
a synchronous internal/get hook or a forwarding Proxy returned by the public
service resolver — and every public-equivalent entry must be isolated from a
live origin).

Behavior contract (not re-derived here):
- dsh-agent-loop owns the private origin AsyncLocalStorage. The origin scope
  is established only by the loop's own step dispatch and spans the whole
  stream consumption of that step; establishing it IS the authoritative
  admission — there is no separately consumable one-shot state on the public
  surface.
- The loop's own synchronous stream entry is identified by an unforgeable
  per-dispatch capability (the live origin scope object created by the loop's
  dispatch site). The capability NEVER travels through a public call: the
  loop dispatches through the module-level `runLoopDispatch` reached via the
  static module import, which no Cordis resolver hook or forwarding Proxy can
  intercept. The capability-gated admission verifies the capability by object
  identity against the live scope inside dsh-agent-loop as the first act of
  the entry.
- Every public-equivalent entry (public llm.stream, public prepareCall
  handles, pre-held handles, async hooks, listeners, lazy
  next/return/throw — including caller-provided custom
  `Symbol.asyncIterator` implementations) initiated while an origin scope is
  visible is isolated from the outer origin for its whole construction
  (waterfall creation and iterator retrieval included) and iteration.
- The exported surface is read-only or capability-gated:
  `peekLoopDispatchOrigin` (frozen {sessionId, signal} snapshot, no request
  object, no mutable state), `admitLoopDispatchOrigin(capability)` (object
  identity against the live scope; without that exact object it can neither
  consume, mint nor reset anything) and `runOutsideLoopDispatchOrigin`
  (clear-only isolation runner). No entry-acknowledgement, no symbol-keyed
  proxied method, and no other state a synchronous hook or a forwarding Proxy
  could pre-consume is exported.
- `prepareCall` keeps its original NO_ADAPTER semantics: the loop's fallback
  dispatch enters through `runLoopDispatch` inside the loop's origin scope.
- Both packages declare the new surface in lib/types/index.d.ts so the Host
  consumes it through real types instead of unknown casts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def fail(message: str) -> None:
    print(f"loop-origin-patch: {message}", file=sys.stderr)
    raise SystemExit(1)


def apply_hunk(text: str, original: str, replacement: str, label: str, count: int = 1) -> str:
    occurrences = text.count(original)
    if occurrences != count:
        fail(f"{label}: expected {count} occurrence(s) of the original bytes, found {occurrences}")
    if replacement in text and original not in text:
        fail(f"{label}: the replacement is already present; the runtime looks patched")
    return text.replace(original, replacement, count)


def patch_agent_loop(text: str) -> str:
    # 1. import the async-hooks primitive
    anchor = 'import { randomUUID } from "node:crypto";'
    text = apply_hunk(
        text,
        anchor,
        anchor + '\nimport { AsyncLocalStorage } from "node:async_hooks";',
        "agent-loop: AsyncLocalStorage import",
    )

    # 2. the private origin module. Establishment stays module-private; the
    #    exported surface is read-only or capability-gated (object identity
    #    against the live scope), so no public caller — including a
    #    synchronous internal/get hook or a forwarding Proxy returned by the
    #    public service resolver — can consume, mint or reset the origin.
    origin_module = '''//#region lib/dispatch-origin.c2p.js (loop-origin.1 patch)
/**
* Runtime-private dispatch origin for the agent loop's own model dispatches.
* Only `AgentLoop`'s step dispatch establishes an origin, spanning the whole
* stream consumption of that step. Establishing the scope IS the authoritative
* admission: there is no separately consumable one-shot state on the public
* surface, and no exported oracle or helper can consume, mint or reset the
* origin (the former exported admission oracle and entry acknowledgement were
* removed — a synchronous internal/get hook fired inside the entry chain, or a
* forwarding Proxy returned by the public service resolver, could intercept the
* capability argument and pre-consume them, blocking the legal child).
*/
const dispatchOrigin = new AsyncLocalStorage();
function peekLoopDispatchOrigin() {
\tconst origin = dispatchOrigin.getStore();
\treturn origin === void 0 ? void 0 : Object.freeze({
\t\tsessionId: origin.sessionId,
\t\tsignal: origin.signal
\t});
}
function admitLoopDispatchOrigin(capability) {
\tconst origin = dispatchOrigin.getStore();
\tif (origin === void 0 || origin !== capability || origin.admitted) return false;
\torigin.admitted = true;
\treturn true;
}
function runOutsideLoopDispatchOrigin(fn) {
\treturn dispatchOrigin.run(void 0, fn);
}
function establishLoopDispatchOrigin(origin) {
\treturn { run: (fn) => dispatchOrigin.run(origin, fn), capability: origin };
}
//#endregion
'''
    anchor2 = '\n//#region lib/types/inbox.js\n'
    text = apply_hunk(text, anchor2, '\n' + origin_module + anchor2, "agent-loop: origin module", 1)

    # 3. establish the origin around the ENTIRE stream consumption of the step
    #    and dispatch through the module-level trusted entry (reached via the
    #    static module import, never through the proxied service resolution)
    #    with the live scope object as the unforgeable capability, passed in
    #    the loop's own call frame. The llm/stream waterfall composes listener
    #    wrappers as lazy async generators whose bodies run on iteration, so a
    #    run scope around the bare call site would close before any listener
    #    or adapter executes.
    original_block = (
        '\t\t\t\tconst stream = preparedCall?.stream(request) ?? this.loopCtx.llm.stream(request);\n'
        '\t\t\t\tsignal.throwIfAborted();\n'
        '\t\t\t\tlive.start();\n'
        '\t\t\t\tstarted = true;\n'
        '\t\t\t\tfor await (const chunk of stream) {\n'
        '\t\t\t\t\tsignal.throwIfAborted();\n'
        '\t\t\t\t\tlive.push(chunk);\n'
        '\t\t\t\t}\n'
        '\t\t\t\tsignal.throwIfAborted();\n'
    )
    replaced_block = (
        '\t\t\t\tconst loopDispatch = establishLoopDispatchOrigin({\n'
        '\t\t\t\t\tsessionId: this.session.id,\n'
        '\t\t\t\t\tsignal,\n'
        '\t\t\t\t\trequest,\n'
        '\t\t\t\t\tadmitted: false\n'
        '\t\t\t\t});\n'
        '\t\t\t\tawait loopDispatch.run(async () => {\n'
        '\t\t\t\t\tconst stream = runLoopDispatch(request, preparedCall, loopDispatch.capability);\n'
        '\t\t\t\t\tsignal.throwIfAborted();\n'
        '\t\t\t\t\tlive.start();\n'
        '\t\t\t\t\tstarted = true;\n'
        '\t\t\t\t\tfor await (const chunk of stream) {\n'
        '\t\t\t\t\t\tsignal.throwIfAborted();\n'
        '\t\t\t\t\t\tlive.push(chunk);\n'
        '\t\t\t\t\t}\n'
        '\t\t\t\t\tsignal.throwIfAborted();\n'
        '\t\t\t\t});\n'
    )
    text = apply_hunk(text, original_block, replaced_block, "agent-loop: origin run spans the step stream consumption")

    # 4. the loop's dispatch site imports the module-level trusted entry from
    #    dsh-llm (a value import alongside the existing import).
    anchor3 = 'import { AssistantStreamAccumulator, BlockAssembler, LlmAttemptId, LlmError, createAssistantMessage, createDeveloperMessage, createSystemMessage, createToolResultMessage, createUserMessage, errorChain, markAgentLoopRequest } from "@deepseek-ai/dsh-llm";'
    replaced3 = anchor3 + '\nimport { runLoopDispatch } from "@deepseek-ai/dsh-llm";'
    text = apply_hunk(text, anchor3, replaced3, "agent-loop: runLoopDispatch import")

    # 5. export the bounded surface: the read-only peek, the capability-gated
    #    admission (object identity against the live scope — without that
    #    exact object it can consume, mint or reset nothing) and the
    #    clear-only isolation runner.
    original_exports = 'export { AgentLoop, AgentLoop as default, CONFIGURED_AGENT_IDENTITIES_KEY, DEFAULT_MAX_PARALLEL_TOOL_CALLS, turnBoundaryProjectionDefinition };'
    replaced_exports = 'export { AgentLoop, AgentLoop as default, CONFIGURED_AGENT_IDENTITIES_KEY, DEFAULT_MAX_PARALLEL_TOOL_CALLS, turnBoundaryProjectionDefinition, peekLoopDispatchOrigin, admitLoopDispatchOrigin, runOutsideLoopDispatchOrigin };'
    text = apply_hunk(text, original_exports, replaced_exports, "agent-loop: export list")
    return text


def patch_agent_loop_types(text: str) -> str:
    # 6. declare the new surface matching tsc output:
    anchor1 = "import { DEFAULT_MAX_PARALLEL_TOOL_CALLS } from './constants.ts';"
    replace1 = anchor1 + "\nimport { admitLoopDispatchOrigin, peekLoopDispatchOrigin, runOutsideLoopDispatchOrigin } from './dispatch-origin.c2p.ts';"
    text = apply_hunk(text, anchor1, replace1, "agent-loop: import origin declarations", 1)

    anchor2 = "export default AgentLoop;"
    replace2 = "export { admitLoopDispatchOrigin, peekLoopDispatchOrigin, runOutsideLoopDispatchOrigin, };\nexport default AgentLoop;"
    text = apply_hunk(text, anchor2, replace2, "agent-loop: export origin declarations", 1)
    return text


def patch_llm(text: str) -> str:
    # 1. a lazy runtime-internal bridge to the loop's origin module, at module
    #    scope, plus the module-private helpers of the capability-gated entry:
    #    the runtime registry, the WeakMap of prepared dispatch records and
    #    the module-level trusted dispatch function. A static import would
    #    create an init-time cycle (a package in the loop's graph extends a
    #    class from a partially initialized package), so the peer is resolved
    #    on first dispatch via createRequire, after both packages have fully
    #    loaded.
    anchor = 'import { MAX_TIMER_DELAY_MS } from "@deepseek-ai/dsh-timeout";'
    helper = (
        anchor + '\n'
        'let loopOriginPeer;\n'
        'function loopOriginPeerModule() {\n'
        '\tif (loopOriginPeer === void 0) {\n'
        '\t\tloopOriginPeer = createRequire(import.meta.url)("@deepseek-ai/dsh-agent-loop");\n'
        '\t}\n'
        '\treturn loopOriginPeer;\n'
        '}\n'
        'function currentLoopDispatchOrigin() {\n'
        '\treturn loopOriginPeerModule().peekLoopDispatchOrigin();\n'
        '}\n'
        'const preparedDispatchRecords = new WeakMap();\n'
        'const loopDispatchRuntimes = new Set();\n'
        'const privateLoopDispatchers = new WeakMap();\n'
        'const kRootRuntime = Symbol("dsh.rootRuntime");\n'
        'function unwrapRuntime(runtime) {\n'
        '\tif (runtime == null || typeof runtime !== "object") return void 0;\n'
        '\tconst raw = runtime[kRootRuntime] ?? runtime;\n'
        '\treturn loopDispatchRuntimes.has(raw) ? raw : void 0;\n'
        '}\n'
        'function singleLoopRuntime() {\n'
        '\tif (loopDispatchRuntimes.size !== 1) return void 0;\n'
        '\treturn [...loopDispatchRuntimes][0];\n'
        '}\n'
        'function runLoopDispatch(options, preparedCall, capability) {\n'
        '\tif (!loopOriginPeerModule().admitLoopDispatchOrigin(capability)) {\n'
        '\t\tconst runtime = preparedCall === void 0 ? singleLoopRuntime() : void 0;\n'
        '\t\tif (runtime === void 0) {\n'
        '\t\t\tthrow new LlmError("loop dispatch origin admission refused", "DISPATCH_ORIGIN_CONSUMED");\n'
        '\t\t}\n'
        '\t\treturn runtime.stream(options);\n'
        '\t}\n'
        '\tlet record;\n'
        '\tif (preparedCall !== void 0) {\n'
        '\t\trecord = preparedDispatchRecords.get(preparedCall);\n'
        '\t\tif (record === void 0 || record.dispatched) {\n'
        '\t\t\tthrow new LlmError("a prepared LLM call can only be dispatched once", "INVALID_PREPARED_CALL");\n'
        '\t\t}\n'
        '\t\tif (!callConfigEquals(options, record.config)) {\n'
        '\t\t\tthrow new LlmError("prepared LLM call config changed before adapter dispatch", "INVALID_PREPARED_CALL");\n'
        '\t\t}\n'
        '\t\trecord.dispatched = true;\n'
        '\t}\n'
        '\tconst runtime = record === void 0 ? singleLoopRuntime() : unwrapRuntime(record.runtime);\n'
        '\tif (runtime === void 0) {\n'
        '\t\tthrow new LlmError("loop dispatch origin admission refused", "DISPATCH_ORIGIN_CONSUMED");\n'
        '\t}\n'
        '\tconst dispatcher = privateLoopDispatchers.get(runtime);\n'
        '\tif (dispatcher === void 0) {\n'
        '\t\tthrow new LlmError("loop dispatch origin admission refused", "DISPATCH_ORIGIN_CONSUMED");\n'
        '\t}\n'
        '\treturn dispatcher(options, record);\n'
        '}'
    )
    text = apply_hunk(text, anchor, helper, "llm: lazy origin peer bridge and trusted dispatch entry", 1)

    # 2. the isolation rule for every non-trusted entry: a dispatch initiated
    #    while an origin scope is visible (an async hook, a listener, a
    #    pre-held handle) is isolated from the outer origin for its whole
    #    construction — the waterfall creation and any caller-provided
    #    Symbol.asyncIterator included — and iteration.
    original = (
        '\t\tstreamWithRegistration(options, prepared) {\n'
        '\t\t\treturn this.ctx.waterfall(this, "llm/stream", options, () => this.adapterStream(options, prepared));\n'
        '\t\t}'
    )
    replaced = (
        '\t\tstreamWithRegistration(options, prepared) {\n'
        '\t\t\tif (loopOriginPeerModule().peekLoopDispatchOrigin() !== void 0) {\n'
        '\t\t\t\tconst runIsolated = loopOriginPeerModule().runOutsideLoopDispatchOrigin;\n'
        '\t\t\t\tconst inner = runIsolated(() => {\n'
        '\t\t\t\t\tconst built = this.ctx.waterfall(this, "llm/stream", options, () => this.adapterStream(options, prepared));\n'
        '\t\t\t\t\treturn built[Symbol.asyncIterator]();\n'
        '\t\t\t\t});\n'
        '\t\t\t\tconst isolated = {\n'
        '\t\t\t\t\tnext: (...args) => runIsolated(() => inner.next(...args)),\n'
        '\t\t\t\t\treturn: (...args) => runIsolated(() => inner.return === void 0 ? { done: true, value: void 0 } : inner.return(...args)),\n'
        '\t\t\t\t\tthrow: (...args) => runIsolated(() => inner.throw === void 0 ? { done: true, value: void 0 } : inner.throw(...args))\n'
        '\t\t\t\t};\n'
        '\t\t\t\tisolated[Symbol.asyncIterator] = () => runIsolated(() => isolated);\n'
        '\t\t\t\treturn isolated;\n'
        '\t\t\t}\n'
        '\t\t\treturn this.ctx.waterfall(this, "llm/stream", options, () => this.adapterStream(options, prepared));\n'
        '\t\t}'
    )
    text = apply_hunk(text, original, replaced, "llm: origin isolation at streamWithRegistration", 1)

    # 3. every runtime instance registers itself and its private dispatcher,
    #    and unregisters on lifecycle disposal (ctx.effect).
    anchor3 = '\t\tconstructor(ctx) {\n\t\t\tsuper(ctx, "llm");\n\t\t}'
    replaced3 = (
        '\t\tconstructor(ctx) {\n'
        '\t\t\tsuper(ctx, "llm");\n'
        '\t\t\tthis[kRootRuntime] = this;\n'
        '\t\t\tloopDispatchRuntimes.add(this);\n'
        '\t\t\tprivateLoopDispatchers.set(this, (options, prepared) => {\n'
        '\t\t\t\treturn this.ctx.waterfall(this, "llm/stream", options, () => this.adapterStream(options, prepared));\n'
        '\t\t\t});\n'
        '\t\t\tthis.ctx.effect(() => () => {\n'
        '\t\t\t\tloopDispatchRuntimes.delete(this);\n'
        '\t\t\t\tprivateLoopDispatchers.delete(this);\n'
        '\t\t\t}, "LlmRuntime.loopDispatchLifecycle");\n'
        '\t\t}'
    )
    text = apply_hunk(text, anchor3, replaced3, "llm: runtime registration and lifecycle", 1)

    # 4. record the internal prepared dispatch record when the call is
    #    prepared, so the trusted entry can honour the registration/config/
    #    one-shot checks and bind the real runtime instance without re-entering
    #    the public handle stream.
    original_record = (
        '\t\t\tlet dispatched = false;\n'
        '\t\t\treturn Object.freeze({'
    )
    replaced_record = (
        '\t\t\tconst preparedRecord = { runtime: unwrapRuntime(this) ?? this, registration, config: resolvedConfig, modelInfo, dispatch: (options) => adapterCall.stream(options), dispatched: false };\n'
        '\t\t\tlet dispatched = false;\n'
        '\t\t\tconst handle = Object.freeze({'
    )
    text = apply_hunk(text, original_record, replaced_record, "llm: prepared record and handle name", 1)
    original_tail = (
        '\t\t\t\t\treturn this.streamWithRegistration(options, {\n'
        '\t\t\t\t\t\tregistration,\n'
        '\t\t\t\t\t\tconfig: resolvedConfig,\n'
        '\t\t\t\t\t\tmodelInfo,\n'
        '\t\t\t\t\t\tdispatch: (options) => adapterCall.stream(options)\n'
        '\t\t\t\t\t});'
    )
    replaced_tail = '\t\t\t\t\treturn this.streamWithRegistration(options, preparedRecord);'
    text = apply_hunk(text, original_tail, replaced_tail, "llm: handle stream uses the record", 1)
    original_close = (
        '\t\t\t\t}\n'
        '\t\t\t});\n'
        '\t\t}\n'
        '\t\tregistration(provider) {'
    )
    replaced_close = (
        '\t\t\t\t}\n'
        '\t\t\t});\n'
        '\t\t\tpreparedDispatchRecords.set(handle, preparedRecord);\n'
        '\t\t\treturn handle;\n'
        '\t\t}\n'
        '\t\tregistration(provider) {'
    )
    text = apply_hunk(text, original_close, replaced_close, "llm: register and return the handle", 1)

    # 5. a read-only origin query on the dsh-llm surface so the Host middleware
    #    verifies through the same module instance that owns the origin, and
    #    the module-level trusted dispatch function so the loop's own dispatch
    #    site never passes a capability through a proxied call.
    original_exports = 'export { ACCOUNT_QUOTA_EXCEEDED_CODE,'
    replaced_exports = 'export { ACCOUNT_QUOTA_EXCEEDED_CODE, currentLoopDispatchOrigin, runLoopDispatch,'
    text = apply_hunk(text, original_exports, replaced_exports, "llm: export the origin query and trusted entry", 1)
    return text


def patch_llm_types(text: str) -> str:
    # 6. declare the read-only query and the trusted dispatch entry matching tsc output:
    anchor = "import type { GenerateOptions, LlmConfigurableProvider, LlmDiscoveredModel, LlmFailure, LlmImageRequestPricing, LlmModelContext, LlmModelDiscoveryRequest, LlmModelInfo, LlmResolvedModelInfo, LlmProviderInfo, ModelModality, StreamChunk, SystemPromptUpdate, ToolUpdate } from './types.ts';"
    declarations = anchor + '''
/**
 * loop-origin.1 (c2p patch): read-only query of the runtime-private dispatch
 * origin; `undefined` unless the patched agent loop's dispatch scope is live.
 * Public dispatches initiated inside a live scope are isolated by the runtime
 * and therefore see no origin through this query.
 */
export declare function currentLoopDispatchOrigin(): {
    readonly sessionId: string;
    readonly signal: AbortSignal;
} | undefined;
/**
 * loop-origin.1 (c2p patch): the loop's own trusted dispatch entry, reached
 * through the static module import (never through the proxied service
 * resolution). The capability is the live origin scope object created by the
 * loop's dispatch site and passed in the loop's own call frame; the
 * capability-gated admission verifies it by object identity inside
 * dsh-agent-loop before anything else. Without that exact object the dispatch
 * is isolated from the outer origin like any public call.
 */
export declare function runLoopDispatch(options: GenerateOptions, preparedCall: unknown, capability: unknown): AsyncIterable<StreamChunk>;'''
    return apply_hunk(text, anchor, declarations, "llm: declare the origin query and trusted entry", 1)


DISPATCH_ORIGIN_C2P_DTS = '''import type { SessionId } from '@deepseek-ai/dsh-session';
export interface LoopDispatchOrigin {
    readonly sessionId: SessionId;
    readonly signal: AbortSignal;
    readonly request: unknown;
    capability: unknown;
    admitted: boolean;
}
/** Frozen read-only view of a live origin. */
export interface LoopDispatchOriginSnapshot {
    readonly sessionId: SessionId;
    readonly signal: AbortSignal;
}
/** Establish the origin scope for one step's whole stream consumption. The
 * returned capability is the live scope object itself: the loop passes it as
 * an argument in its own call frame, and the capability-gated admission on
 * the dispatch entry verifies it by object identity. Never exported. */
export declare function establishLoopDispatchOrigin(origin: Omit<LoopDispatchOrigin, 'capability' | 'admitted'>): {
    run<T>(fn: () => T): T;
    capability: unknown;
};
/**
 * Frozen read-only snapshot; `undefined` outside a live dispatch scope. The
 * snapshot deliberately excludes the request object and any mutable state:
 * the same snapshot or request reference must not be able to preempt the
 * legal dispatch.
 */
export declare function peekLoopDispatchOrigin(): LoopDispatchOriginSnapshot | undefined;
/**
 * Admit one stream entry as the loop's own. The capability is the live origin
 * scope object created by the loop's dispatch site and passed in the loop's
 * own call frame; it is verified by object identity against the live scope
 * and consumed once. Without that exact object this call can consume, mint or
 * reset nothing and returns false; a dispatch authorised this way still
 * passes the Host middleware's read-only verification.
 */
export declare function admitLoopDispatchOrigin(capability: unknown): boolean;
/**
 * Clear-only isolation runner: the callback runs with no loop dispatch origin
 * visible. It can never establish, restore or mint an origin. dsh-llm's
 * admission uses it so public dispatches initiated inside a live scope do not
 * inherit the outer origin.
 */
export declare function runOutsideLoopDispatchOrigin<T>(fn: () => T): T;
//# sourceMappingURL=dispatch-origin.c2p.d.ts.map'''


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: loop-origin.patch.py <candidate-runtime-root>")
    root = Path(sys.argv[1])
    files = {
        "agent-loop": root / "node_modules/@deepseek-ai/dsh-agent-loop/lib/index.js",
        "agent-loop-types": root / "node_modules/@deepseek-ai/dsh-agent-loop/lib/types/index.d.ts",
        "llm": root / "node_modules/@deepseek-ai/dsh-llm/lib/index.js",
        "llm-types": root / "node_modules/@deepseek-ai/dsh-llm/lib/types/index.d.ts",
    }
    for name, f in files.items():
        if not f.is_file():
            fail(f"missing runtime file: {f}")
    loop = files["agent-loop"].read_text()
    loop_types = files["agent-loop-types"].read_text()
    llm = files["llm"].read_text()
    llm_types = files["llm-types"].read_text()
    if "dispatchOrigin" in loop or "peekLoopDispatchOrigin" in llm:
        fail("the runtime already carries the loop-origin patch")
    patched_loop = patch_agent_loop(loop)
    patched_loop_types = patch_agent_loop_types(loop_types)
    patched_llm = patch_llm(llm)
    patched_llm_types = patch_llm_types(llm_types)
    files["agent-loop"].write_text(patched_loop)
    files["agent-loop-types"].write_text(patched_loop_types)
    files["llm"].write_text(patched_llm)
    files["llm-types"].write_text(patched_llm_types)
    origin_dts = root / "node_modules/@deepseek-ai/dsh-agent-loop/lib/types/dispatch-origin.c2p.d.ts"
    origin_dts.write_text(DISPATCH_ORIGIN_C2P_DTS)
    print(json.dumps({
        "patched": [str(f) for f in files.values()] + [str(origin_dts)],
        "agent_loop_bytes": len(patched_loop),
        "agent_loop_types_bytes": len(patched_loop_types),
        "llm_bytes": len(patched_llm),
        "llm_types_bytes": len(patched_llm_types),
    }))


if __name__ == "__main__":
    main()