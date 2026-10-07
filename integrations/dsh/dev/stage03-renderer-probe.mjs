/** Public renderer capability probe. No LLM runtime or provider is mounted. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { measureFile } from './stage03-measure.mjs';

const resolver = createRequire(import.meta.url);
const cordisPath = resolver.resolve('@deepseek-ai/cordis');
const rendererPath = resolver.resolve('@deepseek-ai/dsh-system-prompt');
const { Context } = await import(pathToFileURL(cordisPath).href);
const { default: SystemPrompt, renderPrompt, renderContextSections } = await import(pathToFileURL(rendererPath).href);
const ctx = new Context();
try {
  await ctx.plugin(SystemPrompt, { includeHarnessIdentity: false, includeRuntimeContext: false });
  const text = '作者：“保留 {{literal}} 与换行。”\nEvidence: src/unit.py → Ω 😀\n';
  ctx.systemPrompt.section({ name: 'c2p-writer-native', order: 0, text, complete: true, interpolate: false });
  ctx.systemPrompt.tools(() => ({ schemas: [{ name: 'structured_output', description: 'Writer terminal', parameters: {
    type: 'object', properties: { outcome: { type: 'string', enum: ['blocked'] } },
    required: ['outcome'], additionalProperties: false,
  } }] }));
  const first = await ctx.systemPrompt.assemble();
  const rendered = renderPrompt(first);
  assert.equal(rendered, text);
  assert.deepEqual(renderContextSections(first), []);
  assert.deepEqual(await ctx.systemPrompt.assemble(), first);
  assert.equal(ctx.get('llm'), undefined, 'probe cannot send: no LLM service installed');
  const record = {
    state: 'capability_probe_only', api: ['SystemPrompt.assemble', 'renderPrompt', 'renderContextSections'],
    renderer: await measureFile(rendererPath), cordis: await measureFile(cordisPath),
    assembly: first, rendered_text: rendered, sends: 0, content_attempts: 0,
    private_api_used: false, wire_equivalence: 'not_yet_observed',
  };
  if (process.argv[2] === undefined) throw new Error('output path required');
  await writeFile(process.argv[2], `${JSON.stringify(record, null, 2)}\n`, { flag: 'wx' });
  process.stdout.write('public assemble/render exact Unicode/literal bytes; zero sends; context disposed\n');
} finally {
  await ctx.fiber.dispose();
}
