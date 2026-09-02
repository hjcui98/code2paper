# DyG-Mamba blind-baseline audit

## Provenance boundary

- Allowed inputs: the supplied author-intent YAML and the supplied
  `DyG-Mamba_ Continuous State Space Modeling on Dynamic Graphs` code tree.
- Not inspected or used: original paper, true answer, `paper_final`, existing
  candidate/verified products, OpenCode documents, `.agent` documents, external
  models, and external execution artifacts.
- This is a manually authored comparison baseline. No Code2Paper writer,
  structural gate, publication gate, or LLM runtime was invoked.

## Requested status fields

- `writer_status`: `manual_baseline_generated`
- `structural_exit`: `not_applicable_no_Code2Paper_writer`
- `publication_ready`: `false`
- `final_text_validation`: `pass_with_pending_and_explicit_intent_code_mismatches`
- `unsupported_positive_claims`: `0 unmarked`; every unsupported intent claim
  is either explicitly pending/unverified or reported as contradicted by code.

## Coverage accounting

The denominators below are declared for this audit rather than inferred from a
Code2Paper schema.

- Paragraph/story coverage: `8/8`. The candidate contains scope/input,
  sequence extraction, four-channel encoding, alignment/control features, SSM
  core, pair interaction/readout, task heads, and training/evaluation/
  limitations.
- Building-block slots: `8/8 represented`; `6 direct`, `2 partial`. The
  partial slots are the SSM core (the code has a Mamba core but not all
  intent-level redesign guarantees) and readout/predictor (the predictor is
  present, but pooling is gated top-k rather than mean).
- Pipeline edges: `4/4 represented`; `2 direct`, `2 partial`. Dynamic graph
  encoding and downstream prediction are direct. Timespan-aware forgetting
  and robust selective reviewing are only partial because monotonicity,
  spectral constraints, and robustness effects are absent from the code.
- Formula obligations: `9/9 addressed`; `7 code-derived`, `2 pending`. The
  code-derived expressions cover elapsed-time cosine encoding, co-occurrence
  counts, normalized control-step construction, `A = -exp(A_log)`, selective
  scan parameter flow, gated readout, and task probabilities. The two pending
  formulas are the intent's monotonic `Delta t = f(gap)` requirement and
  `||W_B||_2 <= 1`, `||W_C||_2 <= 1` constraints; they are explicitly not
  presented as implementation facts.

## Direct code support

- First-hop history lookup, strict-before-time filtering, chronological sort,
  truncation, target prefix, and zero padding: `utils/utils.py:135-179`,
  `utils/utils.py:287-307`, `models/DyGMamba.py:115-140`,
  `models/DyGMamba.py:266-320`.
- Raw node/edge lookup and elapsed-time encoding: `models/DyGMamba.py:322-344`,
  `models/modules.py:7-56`.
- Co-occurrence counts and the two-layer encoder: `models/DyGMamba.py:558-661`.
- Four projections, channel stacking, and the separate `dts` projection:
  `models/DyGMamba.py:61-83`, `models/DyGMamba.py:170-215`.
- Mamba block construction, residual/normalization order, and final norm:
  `models/DyGMamba.py:763-877`, `models/mamba_simple.py:297-350`.
- Time-conditioned step path, trainable `A_log`, selective scan, and absence
  of `time_mamba` in the entry-point config: `models/mamba_simple.py:357-551`,
  `train_link_prediction.py:135-142`, `train_node_classification.py:118-125`.
- Shared encoder, cross-linear attention, gated top-k readout, and inactive
  noise layers: `models/DyGMamba.py:80-98`, `models/DyGMamba.py:217-264`,
  `models/DyGMamba.py:1125-1167`.
- Link and node task heads, losses, optimizer ownership, and metrics:
  `train_link_prediction.py:158-332`, `train_node_classification.py:139-260`,
  `models/modules.py:62-116`, `utils/metrics.py:5-35`.
- Feature padding, temporal splits, and link inductive split construction:
  `utils/DataLoader.py:45-177`.

## Incomplete or pending items

1. The code does not prove that the learned scan step is monotonic in an
   elapsed time gap, nor that it follows an Ebbinghaus forgetting curve.
2. `A_log` is trainable; negative initialization is visible, but a strict
   post-training stability guarantee is not enforced.
3. No spectral normalization or explicit spectral-norm bounds for `B` and `C`
   are present.
4. The code does not prove Lipschitz continuity, noise suppression, robust
   historical review, or any resulting performance improvement.
5. The implementation uses one shared source/destination encoder, not two
   independent encoders.
6. The implementation uses learned gated top-k weighted pooling, not mean
   pooling.
7. The node-classification entry point uses the same pair routine with
   co-occurrence and cross attention, not a separate no-co-occurrence path.
8. Linear-complexity and superiority claims require complexity analysis or
   measured evidence not present in this blind input set.

## Final judgment

The candidate is a valid evidence-bounded method reconstruction, but it is not
publication-ready. The missing guarantees and effects are not safely inferable
from the code, and several stated intent choices are contradicted by the
executable path.
