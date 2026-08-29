# Quality closed-loop live run — 2026-08-29

This directory contains the final-code real replay evidence produced against
the user-authorized local OpenAI-compatible runtime at `http://127.0.0.1:8006/v1`.

## Runtime

- model: `qwen38-27b-nvfp4`
- profile: `tests/live/profiles/qwen38_vllm_budgeted.example.env`
- maximum context: `131072`
- preflight/postflight `/health` and `/v1/models`: HTTP 200
- postflight running/waiting/KV cache: `0 / 0 / 0`
- postflight preemptions/abort/error: `0 / 0 / 0`
- NVIDIA visibility: 8 × NVIDIA GeForce RTX 5090 outside the sandbox

## Contents

- `ebcar/`, `dyg/`, `linearrag/`: complete retained replay bundles.
- `*_evaluator.json`: corresponding cleanliness, leakage, and coverage
  evaluations.

The replay order was EBCAR → DyG-Mamba → LinearRAG, using independent fresh
roots and the final repository code digest
`sha256:f40b177810115efbb3cfdd54662931e082e5d740bf10e12403fa9e4c50a9018d`.

## Result

All replay and evaluator processes exited with status 0, but this is not a
publication-quality pass. The Writer result was `incomplete` and the
structural exit was `eligible=false` for all three projects. The fail-closed
coverage was:

| project | story | paragraph | slot | edge | formula |
| --- | ---: | ---: | ---: | ---: | ---: |
| EBCAR | `3/28` | `3/29` | `0/28` | n/a | `0/3` |
| DyG-Mamba | `1/23` | `1/22` | `0/33` | n/a | `0/3` |
| LinearRAG | `1/19` | `1/17` | `0/16` | `0/1` | `0/2` |

Candidate authority validation passed and verified leakage remained zero, but
reverse text-evidence validation failed and publication quality remained
blocked. These bundles are diagnostic evidence only; no Candidate is promoted
to Verified or publication-ready.
