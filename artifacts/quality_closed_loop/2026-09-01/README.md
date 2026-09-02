# Quality closed-loop live runs — 2026-09-01

Three serial replay batches on the user-authorized local runtime at
`http://127.0.0.1:8006/v1` (`qwen38-27b-nvfp4`, profile
`tests/live/profiles/qwen38_vllm_budgeted.example.env`, `max_model_len=131072`).
Frozen research roots remain the v34/v33/08-30 `06_authoring` oracles; each
project uses `--reuse-derived-authoring`, callback `1×8`.

This archive retains diagnostic bundles only (Candidate prose evidence, not D5).

## Batches

| batch | code digest | window (+08) | notes |
| --- | --- | --- | --- |
| `v34prose` | `sha256:fbec291bb6234e199622867007dda04220856b1ce390496930b12ad5a3b5eb7f` | 11:10–12:37 | P0–P3 display-math / leak repairs |
| `v34p0p3` | `sha256:64b7ab754a1ca5a9855271fab8f431eeb1da329dd42f54d47015af702eeb7cdc` | 13:41–15:33 | bound counterexample before six-repair |
| `sixrepair` | `sha256:3bdeeb8d57368664dea46f60a2df739c6f1edae02d4c8d1cd983f08bd1834109` | 18:02–19:14 | six Candidate-first surface repairs |

## Structural exit (all `exit=2`, `writer=incomplete`, `eligible=false`)

| batch | EBCAR paras/slots/formula | DyG paras/slots/formula | LinearRAG paras/slots/formula |
| --- | --- | --- | --- |
| v34prose | 6/7 · 10/11 · 4/4 | 0/6 · 15/17 · 0/0 | 0/5 · 9/16 · 0/0 |
| v34p0p3 | 6/7 · 10/11 · 2/4 | 0/6 · 7/17 · 0/0 | 0/5 · 0/16 · 0/0 |
| sixrepair | 5/7 · 8/11 · 1/1 | 0/6 · 9/17 · 0/0 | 0/5 · 0/16 · 0/0 |

## Layout

- `{batch}/run_serial.sh`, `{batch}/serial.log`: batch wrapper and timeline.
- `{batch}/{ebcar,dyg,linearrag}/execution_record.json`: exit, digest, structural exit.
- `{batch}/{project}/replay.stdout.log`: replay console log.
- `{batch}/{project}/artifacts/06_authoring/publication_candidate_method.md`: Candidate body.
- `{batch}/{project}/artifacts/06_authoring/formalization_section_results_v1.json`: formula traces.
- `{batch}/{project}/artifacts/07_validation/publication_quality_report_v1.json`: quality report.

Verified remained fail-closed on all runs. These bundles are not publication-ready.
