# Next-repair authoring replay — 2026-09-05

This archive retains the latest three user-authorized authoring replays for
DyG-Mamba, LinearRAG, and EBCAR.  They used the OpenAI-compatible runtime
`http://127.0.0.1:8006`, model `qwen38-27b-nvfp4`, and context length
`131072`.

The complete raw run directories remain under `/tmp`:

- DyG-Mamba: `/tmp/c2p-nextrepair-8006-dyg-20260905-012937/`
- LinearRAG: `/tmp/c2p-nextrepair-8006-linearrag-20260905-012937/`
- EBCAR: `/tmp/c2p-nextrepair-8006-ebcar-20260905-012937/`

Only the necessary review bundle is checked into Git: execution and runtime
ledgers, replay logs, Candidate prose, writer/formalization/callback traces,
formalization evidence, structural exit, validation ledgers, quality reports,
token sidecars, and research generation/content traces.  The large raw
research-tool directories are intentionally left in `/tmp`.

## Final status

All three runs completed but failed closed at the Writer boundary with
`exit_code=2`, `writer=incomplete`, `publication=incomplete`, and
`eligible=false`.

| project | valid paragraphs | valid targets | witnessed slots | quality issue | token subtotal |
| --- | ---: | ---: | --- | ---: | ---: |
| DyG-Mamba | 2/6 | 20/31 | 10/15 | 9 unsupported positive claims; support precision 0 | 542,567 |
| LinearRAG | 0/5 | 8/27 | 0/15 | authorship gate false; callback coverage regression | 1,232,329 |
| EBCAR | 3/7 | 19/26 | 5/9 | 7 unsupported positive claims; support precision 0 | 1,164,319 |

Callback outcomes were: DyG `no_progress` with 0 fulfilled; LinearRAG rolled
back after `8/27->0/27`; EBCAR rolled back after `19/26->9/27`.  Formula
coverage was zero for all three final candidates.  These are diagnostic and
prose-quality artifacts, not publication-ready or D5 evidence.

## Token accounting

The token sidecars contain separate provider-reported input and output totals.
They are marked `partial` because some calls did not return usage:

| project | input | output | captured total | calls without usage |
| --- | ---: | ---: | ---: | ---: |
| DyG-Mamba | 507,067 | 35,500 | 542,567 | 8 |
| LinearRAG | 1,154,235 | 78,094 | 1,232,329 | 5 |
| EBCAR | 1,060,800 | 103,519 | 1,164,319 | 14 |

The execution records bind all three runs to code-state digest
`sha256:5c103f3400e5118ba4ff579601909af6bd483290b70efcd66dde3c909b626b6d`.
