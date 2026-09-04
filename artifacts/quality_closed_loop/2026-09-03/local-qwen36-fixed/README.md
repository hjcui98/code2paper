# Local qwen36@8003 authoring reruns — 2026-09-03

This archive retains the key diagnostic evidence from the fixed-token-accounting
replays for DyG-Mamba and LinearRAG.  The runs used the user-authorized local
OpenAI-compatible runtime `http://127.0.0.1:8003/v1`, model
`qwen36-27b-nvfp4`, and `max_model_len=131072`.

The source run directories remain intact under `/tmp`:

- DyG-Mamba: `/tmp/c2p-qwen36-fixed-dyg-20260903-222325/`
- LinearRAG: `/tmp/c2p-qwen36-fixed-linearrag-20260903-222325/`

The full raw directories are intentionally not copied into Git.  Each project
directory here contains the execution record, runtime snapshots, Candidate
prose, writer/formalization/callback evidence, structural exit, publication-quality
report, validation ledgers, token-usage summary, and replay log needed for
review.

## Run summary

Both runs reached the Writer boundary and failed closed with `exit_code=2`;
neither is a publication-ready or D5 result.

| project | writer/publication | structural coverage | callback outcome | token sidecar |
| --- | --- | --- | --- | --- |
| DyG-Mamba | `incomplete` / `incomplete` | 17/37 targets; 1/6 required paragraphs valid | 0 fulfilled; `no_progress`; candidate rolled back | 52 calls, 49 with usage |
| LinearRAG | `incomplete` / `incomplete` | 13/29 targets; 0/5 required paragraphs valid | 2 fulfilled; rollback after coverage regression `13/29→1/29` | 82 calls, 77 with usage |

## Token accounting

The sidecars include both input and output counts reported by the local
provider.  Their status is `partial` because a small number of calls did not
return usage; the totals below are therefore captured subtotals, not guaranteed
whole-run totals.

| project | input tokens | output tokens | captured total | missing-usage calls |
| --- | ---: | ---: | ---: | ---: |
| DyG-Mamba | 414,947 | 42,002 | 456,949 | 3 |
| LinearRAG | 1,420,593 | 65,215 | 1,485,808 | 5 |

The execution records bind both runs to code-state digest
`sha256:8ab9bf2f14de0180449b392b183640b5e5ae2f908cdac48a3e26da06ece93231`.
