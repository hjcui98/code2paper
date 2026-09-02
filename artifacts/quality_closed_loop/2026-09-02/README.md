# Candidate Method quality comparison — 2026-09-02

This archive preserves the two Method-text artifacts compared during the
2026-09-02 quality review:

- `r5/`: the real serial Code2Paper replay from
  `/tmp/c2p-candidate-repair-r5-8006-20260902/`.
- `blind_baseline/`: the code-grounded manual baseline from
  `/tmp/code2paper-blind-baseline-20260828/`.

The full r5 output is approximately 414 MB and is intentionally not copied
into the repository. These diagnostic bundles retain the Candidate prose,
writer/structural/quality evidence, execution records, and replay logs needed
to compare content quality. The original `/tmp` directories remain intact.

## Status

All three r5 replays completed with `exit=2`, `writer=incomplete`, and
fail-closed publication status. The blind baselines were generated outside the
Code2Paper Writer and therefore have `structural_exit=not_applicable`; their
audits also mark publication readiness as false. Neither set is a
publication-ready output.

## Comparison summary

| project | r5 Candidate | blind baseline | quality observation |
| --- | ---: | ---: | --- |
| EBCAR | 5 H2, 5,468 B | 7 sections, 8,515 B | r5 is cleaner but drops data/evaluation and pending-boundary sections; baseline retains the full retrieval-to-inference chain. |
| DyG-Mamba | 4 H2, 4,973 B | 6 sections, 9,671 B | r5 omits most sequence/SSM/readout mechanics and has notation risks; baseline preserves the implementation-grounded method chain. |
| LinearRAG | 5 H2, 3,528 B | 6 sections, 9,399 B | r5 has the best opening order but omits seeds, fallback, retrieval details, answer generation, and evidence limits. |

The baseline is a content and organization reference, not a gate bypass or a
production fallback. Its code identifiers are retained for audit transparency
and should be projected into publication language before use as final prose.
