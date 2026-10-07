#!/usr/bin/env python3
"""Use pi-ai's supported OpenAI parameter slot for guarded native selection.

The neutral SimpleStreamOptions.toolChoice type only promises auto/none.
samplingParams is its public OpenAI-compatible request-parameter extension;
only the already validated tool_choice key is added. No arbitrary parameters,
result repair, fetch replacement or dispatch authority are introduced.
"""
import importlib.util
from pathlib import Path
import sys

BASE = Path(__file__).with_name('tool-choice.patch.py')
spec = importlib.util.spec_from_file_location('c2p_tool_choice_base_patch', BASE)
if spec is None or spec.loader is None:
    raise RuntimeError('native tool-choice base patch unavailable')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def patch_runtime(text: str) -> str:
    output = base.patch_runtime(text)
    return base.replace(output,
        '...profile.toolChoice === void 0 ? {} : { toolChoice: profile.toolChoice },',
        '...profile.toolChoice === void 0 ? {} : { samplingParams: { tool_choice: profile.toolChoice } },',
        'supported native OpenAI parameter slot')


def main() -> None:
    package = Path(sys.argv[1]) / 'node_modules/@deepseek-ai/dsh-llm-pi-ai/lib'
    js = package / 'index.js'
    types = package / 'types/config.d.ts'
    patched_js = patch_runtime(js.read_text())
    patched_types = base.patch_types(types.read_text())
    js.write_text(patched_js)
    types.write_text(patched_types)


if __name__ == '__main__':
    main()
