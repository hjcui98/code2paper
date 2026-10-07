/** C00 Host-private projection. Python owns input validation and canonical seals. */
import { createHash, randomUUID } from 'node:crypto';
import { readFile, realpath } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import type { Context } from '@deepseek-ai/cordis';
import { assembleContextFor } from '@deepseek-ai/dsh-agent';
import type { Agent, AgentHandle } from '@deepseek-ai/dsh-agent';
import type { GenerateOptions, LlmCallConfig, ToolSchema } from '@deepseek-ai/dsh-llm';
import type { SessionId } from '@deepseek-ai/dsh-session';
import { renderPrompt, renderContextSections } from '@deepseek-ai/dsh-system-prompt';
import { assertObjectJsonSchema } from '@deepseek-ai/dsh-tools';
import { decodeWire, immutable, isObject, parseWire, WireError } from './wire.js';
import { TerminalArgumentCapture } from './terminal-result.js';
import type { JsonObject, JsonValue } from './wire.js';

export const WRITER_RENDERER_VERSION = 'native-text/1';
export const WRITER_TERMINAL = 'c2p_terminal';
export const WRITER_TERMINAL_DESCRIPTION = 'Return the single WriterTaskResultV1 terminal candidate. No domain acceptance is granted.';

export interface WriterInputRefV1 extends JsonObject {
  schema_version: 'WriterInputRefV1';
  request_ref: JsonObject;
  writer_request: JsonObject;
  task_view_json: string;
  terminal_schema: JsonObject;
  native_terminal_schema: JsonObject;
  native_schema_enforcement: JsonObject[];
  terminal_instruction: string;
  model: string;
  effective_options: JsonObject;
  post_clamp_max_output_tokens: number;
  composition_digest: string;
  renderer_version: string;
  renderer_digest: string;
  input_digest: string;
}

export interface WriterWireProjectionV1 extends JsonObject {
  schema_version: 'WriterWireProjectionV1';
  protocol_version: 'c2p-dsh/1';
  renderer_version: string;
  renderer_digest: string;
  composition_digest: string;
  input_digest: string;
  task_view_digest: string;
  terminal_schema_digest: string;
  model: string;
  effective_options: JsonObject;
  post_clamp_max_output_tokens: number;
  system_text: string;
  user_text: string;
  tools: JsonObject[];
  measurement_ref: JsonObject;
  wire_equivalence_ref: JsonObject;
  projection_digest: string;
}

/** Actual locations pinned by I01. verify() runs the Python composition primitive. */
export interface WriterComposition {
  readonly digest: string;
  readonly rendererVersion: string;
  /** SHA-256 of the actual executed writer-request.js, covered by composition. */
  readonly rendererDigest: string;
  readonly files: readonly { readonly path: string; readonly resolvedPath: string; readonly digest: string }[];
  verify(): Promise<void>;
}

export interface ProjectionEvidence {
  readonly binding: JsonObject;
  readonly measurement_ref: JsonObject;
  readonly wire_equivalence_ref: JsonObject;
}

/** Injected solely by the trusted Host; these are not model tools or send capabilities. */
export interface WriterProjectionAuthority {
  /** Explicit Host capability with agents injection; never an RPC/model field. */
  readonly agentHost: Context;
  readonly inputSchema: JsonObject;
  readonly projectionSchema: JsonObject;
  validateInput(raw: Uint8Array): Promise<Uint8Array>;
  digestValue(value: JsonValue): Promise<string>;
  /** Must return previously observed immutable evidence, or reject not-ready. */
  evidenceFor(binding: JsonObject): Promise<ProjectionEvidence>;
  sealProjection(value: JsonObject): Promise<Uint8Array>;
}

function reject(code: string): never { throw new WireError(code); }

function same(left: JsonValue, right: JsonValue): boolean {
  if (left === right) return true;
  if (Array.isArray(left) && Array.isArray(right)) return left.length === right.length && left.every((entry, index) => same(entry, right[index]!));
  if (isObject(left) && isObject(right)) return Object.keys(left).length === Object.keys(right).length
    && Object.keys(left).every(key => Object.hasOwn(right, key) && same(left[key]!, right[key]!));
  return false;
}

export async function verifyWriterComposition(composition: WriterComposition): Promise<void> {
  await composition.verify();
  if (composition.files.length === 0) reject('composition_sources_missing');
  for (const actual of [fileURLToPath(import.meta.url), process.execPath,
    fileURLToPath(import.meta.resolve('@deepseek-ai/dsh-system-prompt'))]) {
    const resolved = await realpath(actual);
    const digest = `sha256:${createHash('sha256').update(await readFile(resolved)).digest('hex')}`;
    if (!composition.files.some(file => file.resolvedPath === resolved && file.digest === digest)) reject('composition_drift');
    if (actual === fileURLToPath(import.meta.url) && digest !== composition.rendererDigest) reject('writer_identity_drift');
  }
  for (const file of composition.files) {
    let resolved: string;
    let bytes: Buffer;
    try { resolved = await realpath(file.path); bytes = await readFile(resolved); }
    catch { return reject('composition_source_missing'); }
    if (resolved !== file.resolvedPath || `sha256:${createHash('sha256').update(bytes).digest('hex')}` !== file.digest) reject('composition_drift');
  }
}

/** Reject content transformations that this native-text renderer cannot prove. */
function nativeConfig(input: WriterInputRefV1): LlmCallConfig {
  const options = input.effective_options;
  if (Object.keys(options).some(key => !['provider', 'temperature', 'reasoningEffort', 'maxTokens', 'nativeToolChoice', 'nativeToolSchemaMode'].includes(key))) reject('writer_options_unsupported');
  if (typeof options['provider'] !== 'string' || options['provider'].length === 0) reject('writer_provider_missing');
  if (options['maxTokens'] !== input.post_clamp_max_output_tokens) reject('writer_cap_mismatch');
  if (options['temperature'] !== undefined && typeof options['temperature'] !== 'number') reject('writer_options_unsupported');
  if (options['reasoningEffort'] !== undefined && typeof options['reasoningEffort'] !== 'string') reject('writer_options_unsupported');
  if (options['nativeToolSchemaMode'] !== undefined
      && (options['nativeToolSchemaMode'] !== 'server-default' || options['provider'] !== 'openai')) reject('writer_options_unsupported');
  // Adapter profile policy is bound by composition and actual provider wire;
  // it is not a loop config field or a credential for native response source.
  const choice = options['nativeToolChoice'];
  if (choice !== undefined && choice !== 'required') {
    if (!isObject(choice) || Object.keys(choice).sort().join(',') !== 'function,type'
        || choice['type'] !== 'function' || !isObject(choice['function'])
        || Object.keys(choice['function']).join(',') !== 'name'
        || choice['function']['name'] !== WRITER_TERMINAL) reject('writer_options_unsupported');
  }
  const request = input.writer_request;
  if (typeof request['prompt'] !== 'string' || typeof input.task_view_json !== 'string') reject('writer_text_missing');
  // These are unsupported transport envelopes, not keywords within evidence prose.
  for (const key of ['messages', 'images', 'files', 'attachments', 'content_blocks']) {
    if (Object.hasOwn(request, key)) reject('writer_content_unsupported');
  }
  return {
    provider: options['provider'], model: input.model, maxTokens: input.post_clamp_max_output_tokens,
    ...options['temperature'] === undefined ? {} : { temperature: options['temperature'] as number },
    ...options['reasoningEffort'] === undefined ? {} : { reasoningEffort: options['reasoningEffort'] as LlmCallConfig['reasoningEffort'] },
  };
}

/** Frozen native Writer registration. The full schema guard precedes concludeTurn. */
export function assertNativeWriterSchema(schema: JsonObject): void {
  // Raw native registration preserves JSON Schema cardinality in the actual
  // provider request. DSH's small typed-schema helper lacks minItems; accept
  // only this explicitly enforced extension, preserving all its other checks.
  const structural = (node: JsonObject): JsonObject => {
    const copy: JsonObject = { ...node };
    if (Object.hasOwn(copy, 'minItems')) {
      const minimum = copy['minItems'];
      if (copy['type'] !== 'array' || typeof minimum !== 'number'
        || !Number.isSafeInteger(minimum) || minimum < 0) reject('writer_native_cardinality_invalid');
      delete copy['minItems'];
    }
    if (isObject(copy['properties'])) {
      const properties: JsonObject = {};
      for (const [name, child] of Object.entries(copy['properties'])) {
        if (!isObject(child)) reject('writer_native_schema_invalid');
        properties[name] = structural(child);
      }
      copy['properties'] = properties;
    }
    if (isObject(copy['items'])) copy['items'] = structural(copy['items']);
    if (Array.isArray(copy['oneOf'])) copy['oneOf'] = copy['oneOf'].map(child => {
      if (!isObject(child)) reject('writer_native_schema_invalid');
      return structural(child);
    });
    return copy;
  };
  assertObjectJsonSchema(structural(schema));
}

/** Frozen native Writer registration. The full schema guard precedes concludeTurn. */
export function installNativeWriter(ctx: Context, input: WriterInputRefV1, onTerminal?: (value: JsonValue) => void): void {
  const config = immutable(nativeConfig(input));
  const capture = new TerminalArgumentCapture();
  capture.install(ctx);
  assertNativeWriterSchema(input.native_terminal_schema);
  ctx.systemPrompt.section({ name: 'c2p-writer-native', order: 0, complete: true, interpolate: false,
    text: `${input.writer_request['prompt'] as string}\n\n${input.terminal_instruction}` });
  ctx.systemPrompt.suppressRuntimeContext();
  ctx.tools.register({
    name: WRITER_TERMINAL, description: WRITER_TERMINAL_DESCRIPTION,
    parameters: input.native_terminal_schema,
    output: { schema: { type: 'object', properties: { recorded: { type: 'boolean' } }, required: ['recorded'], additionalProperties: false },
      render: () => [{ type: 'text', text: '{"recorded":true}' }] },
    execute: async (args, exec) => {
      const raw = capture.raw(exec.callId, { sessionId: exec.agent?.session.id });
      if (raw.state !== 'captured') reject('writer_terminal_raw_not_ready');
      // Native emission requirements precede the publication parser's legacy
      // defaults. Neither check grants required-target or domain acceptance.
      parseWire(raw.text, input.native_terminal_schema);
      const value = parseWire(raw.text, input.terminal_schema);
      if (!same(value, decodeWire(JSON.stringify(args)))) reject('writer_terminal_normalized_drift');
      onTerminal?.(immutable(value));
      exec.concludeTurn();
      return { recorded: true };
    },
  });
  ctx.tools.restrict({ allow: [] });
  ctx.on('agent/request', (_request, _next) => Promise.resolve(config));
}

/** Observe the same public assembly/render path the loop calls; this never dispatches. */
export async function renderWriterInput(agent: Agent, input: WriterInputRefV1): Promise<JsonObject> {
  const config = nativeConfig(input);
  const assembly = await agent.ctx.systemPrompt.assemble(assembleContextFor(agent));
  if (renderContextSections(assembly).length !== 0) reject('writer_runtime_context_drift');
  const system = renderPrompt(assembly);
  const expected = `${input.writer_request['prompt'] as string}\n\n${input.terminal_instruction}`;
  if (system !== expected) reject('writer_material_drift');
  const expectedTools = [{ name: WRITER_TERMINAL, description: WRITER_TERMINAL_DESCRIPTION, parameters: input.native_terminal_schema }];
  if (!same(decodeWire(JSON.stringify(assembly.tools)), expectedTools)) reject('writer_tools_drift');
  return immutable({ input_digest: input.input_digest, renderer_digest: input.renderer_digest, composition_digest: input.composition_digest,
    model: config.model, effective_options: input.effective_options, post_clamp_max_output_tokens: config.maxTokens!,
    system_text: system, user_text: input.task_view_json, tools: expectedTools });
}

/** A fresh render-only Agent is disposed before this returns; no followup/send occurs. */
export async function prepare_projection(
  host: Context, inputBytes: Uint8Array, composition: WriterComposition, authority: WriterProjectionAuthority,
): Promise<WriterWireProjectionV1> {
  const input = parseWire(await authority.validateInput(inputBytes), authority.inputSchema) as WriterInputRefV1;
  await verifyWriterComposition(composition);
  if (input.composition_digest !== composition.digest || input.renderer_digest !== composition.rendererDigest
    || input.renderer_version !== composition.rendererVersion || input.renderer_version !== WRITER_RENDERER_VERSION) reject('writer_identity_drift');
  const config = nativeConfig(input);
  let handle: AgentHandle | undefined;
  try {
    handle = await host.agents.create({ sessionId: `c2p-projection-${randomUUID()}` as SessionId,
      agentOptions: { provider: config.provider, model: config.model, maxTokens: config.maxTokens, reasoningEffort: config.reasoningEffort },
      setup: (ctx) => { installNativeWriter(ctx, input); } });
    const binding = await renderWriterInput(handle.agent, input);
    const evidence = await authority.evidenceFor(binding);
    if (!same(evidence.binding, binding)) reject('wire_evidence_binding_mismatch');
    const value: JsonObject = {
      schema_version: 'WriterWireProjectionV1', protocol_version: 'c2p-dsh/1', renderer_version: input.renderer_version,
      ...binding, task_view_digest: await authority.digestValue(input.writer_request['input_payload']!),
      terminal_schema_digest: await authority.digestValue(input.terminal_schema),
      measurement_ref: evidence.measurement_ref, wire_equivalence_ref: evidence.wire_equivalence_ref,
    };
    const projection = parseWire(await authority.sealProjection(immutable(value)), authority.projectionSchema) as WriterWireProjectionV1;
    for (const [key, item] of Object.entries(value)) if (!same(projection[key]!, item)) reject('projection_seal_mismatch');
    await verifyWriterComposition(composition);
    return immutable(projection);
  } finally { await handle?.dispose(); }
}

/** Request seam validation only: no injection, cap rewrite, material repair or send. */
export function compareWriterRequest(projection: WriterWireProjectionV1, request: GenerateOptions): void {
  const options = projection.effective_options;
  if (request.model !== projection.model || request.provider !== options['provider']) reject('writer_model_drift');
  if (request.maxTokens !== projection.post_clamp_max_output_tokens) reject('writer_cap_mismatch');
  if (request.temperature !== options['temperature'] || request.reasoningEffort !== options['reasoningEffort']) reject('writer_options_drift');
  if (request.stop !== undefined || request.purpose !== undefined || request.system !== undefined) reject('writer_options_unsupported');
  const messages = request.messages;
  if (messages.length !== 2 || messages[0]?.role !== 'system' || messages[1]?.role !== 'user') reject('writer_history_drift');
  for (const [index, expected] of [projection.system_text, projection.user_text].entries()) {
    const content = messages[index]!.content;
    if (content.length !== 1 || content[0]?.type !== 'text' || content[0].text !== expected) reject('writer_material_drift');
  }
  if (!same(decodeWire(JSON.stringify(request.tools ?? [])), projection.tools)) reject('writer_tools_drift');
}

/** Headers and session/message ids are transport metadata, never part of model text. */
export const WRITER_TRANSPORT_WHITELIST = Object.freeze(['http.authorization', 'http.user-agent', 'http.host', 'http.connection',
  'http.content-length', 'request.signal', 'request.sessionId', 'messages.id', 'messages.createdAt']);

// Exported for Host callers that need the real schema shape without another compiler.
export type WriterToolSchema = ToolSchema;
