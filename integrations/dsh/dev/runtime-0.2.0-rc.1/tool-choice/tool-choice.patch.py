#!/usr/bin/env python3
"""Add explicit native tool selection to a fresh, copied pi-ai runtime.

This provider option neither grants dispatch origin nor accepts tool results.
The existing native adapter, retry policy and stream decoder remain the owners.
Omission preserves the old wire. Never apply to an existing evidence runtime.
"""
from pathlib import Path
import sys


def replace(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"tool-choice original bytes differ: {label}")
    return text.replace(old, new, 1)


def patch_runtime(text: str) -> str:
    anchor = '\tthinkingBudgets,\n\tcacheRetention: z.union(['
    text = replace(text, anchor,
        '\tthinkingBudgets,\n\ttoolChoice: z.union([z.const("required"), z.object({type: z.const("function").required(), function: z.object({name: z.string().required()}).required()})]),\n\tcacheRetention: z.union([', 'profile schema')
    anchor = '\t\tassertValidHeaders(provider, source.headers);'
    validation = '''
\t\tlet toolChoice;
\t\tif (source.toolChoice !== void 0) {
\t\t\tconst choice = source.toolChoice;
\t\t\tif (choice === "required") toolChoice = choice;
\t\t\telse if (choice !== null && typeof choice === "object" && !Array.isArray(choice)
\t\t\t\t&& Object.keys(choice).sort().join(",") === "function,type" && choice.type === "function"
\t\t\t\t&& choice.function !== null && typeof choice.function === "object" && !Array.isArray(choice.function)
\t\t\t\t&& Object.keys(choice.function).join(",") === "name"
\t\t\t\t&& typeof choice.function.name === "string" && choice.function.name.length > 0
\t\t\t\t&& choice.function.name.trim() === choice.function.name) {
\t\t\t\ttoolChoice = Object.freeze({type:"function", function:Object.freeze({name:choice.function.name})});
\t\t\t} else throw new Error(`llm-pi-ai: provider "${provider}" invalid toolChoice`);
\t\t}
'''
    text = replace(text, anchor, anchor + validation, 'profile validation')
    anchor = '\t\t\t...rest.thinkingBudgets === void 0 ? {} : { thinkingBudgets: { ...rest.thinkingBudgets } },'
    text = replace(text, anchor, anchor + '\n\t\t\t...toolChoice === void 0 ? {} : { toolChoice },', 'immutable resolved choice')
    anchor = '\t\t\tconst reasoning = resolveReasoningLevel(model, options.reasoningEffort ?? profile.reasoning);'
    validation = '''
\t\t\tif (profile.toolChoice !== void 0) {
\t\t\t\tif (model.api !== "openai-completions") throw new LlmError("toolChoice requires openai-completions", "UNSUPPORTED_OPTION");
\t\t\t\tif (!Array.isArray(options.tools) || options.tools.length === 0) throw new LlmError("toolChoice requires offered tools", "UNSUPPORTED_OPTION");
\t\t\t\tif (profile.toolChoice !== "required" && options.tools.filter(tool => tool.name === profile.toolChoice.function.name).length !== 1) throw new LlmError("toolChoice must name exactly one offered tool", "UNSUPPORTED_OPTION");
\t\t\t}
'''
    text = replace(text, anchor, anchor + validation, 'pre-provider support and offered-tool check')
    anchor = '\t\t\t\tconst iterator = toStreamChunks(snapshot.models.streamSimple(model, context, {'
    text = replace(text, anchor,
        '\t\t\t\tif (profile.toolChoice !== void 0 && (!Array.isArray(context.tools) || context.tools.length === 0 || (profile.toolChoice !== "required" && context.tools.filter(tool => tool.name === profile.toolChoice.function.name).length !== 1))) throw new LlmError("toolChoice missing from provider tool projection", "UNSUPPORTED_OPTION");\n' + anchor,
        'actual provider tool projection check')
    anchor = '\t\t\t\t\t...options.maxTokens === void 0 ? {} : { maxTokens: options.maxTokens },'
    return replace(text, anchor, anchor + '\n\t\t\t\t\t...profile.toolChoice === void 0 ? {} : { toolChoice: profile.toolChoice },', 'native option forwarding')


def patch_types(text: str) -> str:
    anchor = '    thinkingBudgets?: ThinkingBudgets;'
    return replace(text, anchor, anchor + '\n    /** Explicit native selection; omitted preserves automatic provider selection. */\n    toolChoice?: "required" | { type: "function"; function: { name: string } };', 'profile declaration')


def main() -> None:
    root = Path(sys.argv[1])
    package = root / 'node_modules/@deepseek-ai/dsh-llm-pi-ai/lib'
    js = package / 'index.js'
    types = package / 'types/config.d.ts'
    # Compute both outputs before any mutation; refuse drift and double apply.
    patched_js = patch_runtime(js.read_text())
    patched_types = patch_types(types.read_text())
    js.write_text(patched_js)
    types.write_text(patched_types)


if __name__ == '__main__':
    main()
