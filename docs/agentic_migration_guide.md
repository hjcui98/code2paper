# Code2Paper Agentic Migration Guide

This guide defines the P4 rollout boundary. It does not authorize weakening any
Evidence V2 gate to improve completion rate.

## Modes

- `--mode legacy` keeps the fixed Python pipeline and is the default until a
  `CutoverDecisionV2` reaches `default_ready`. Every legacy run emits
  `legacy_trust_contract.json`; it is explicitly not an authoritative V2 final
  invariant.
- `--mode agentic` opts into the LangGraph route, Evidence V2 semantic text and
  figure gates, durable decisions, and explanatory blocking.
- `--mode shadow` preserves legacy delivery while writing the agentic run under
  `<out-root>/shadow_agentic/`. `shadow_comparison.json` forbids treating the
  background result as the delivered completion.

Example opt-in:

```bash
code2paper-run REPO \
  --author author_markers.yaml \
  --out-root /tmp/code2paper-opt-in \
  --mode agentic \
  --run-id project-agentic-1 \
  --max-retrieval-rounds 1 \
  --max-evidence-revision-rounds 1 \
  --max-authoring-revision-rounds 1 \
  --max-figure-revision-rounds 1 \
  --max-semantic-verifier-calls 8
```

## Rollout sequence

The enforced order is `shadow → opt-in → canary → default`. The cutover policy
fails closed when benchmark cases, variants, three-repeat Gemma runs, paired
intent checks, human false-block review, or a hard trust metric are missing.
Default activation additionally requires reviewed shadow cases, opt-in cases,
incident-free canaries, this migration guide, and the legacy contract marker.

After those gates produce a `default_ready` decision, activate the audited
implicit default by passing the exact decision file:

```bash
code2paper-run REPO \
  --author author_markers.yaml \
  --out-root /tmp/code2paper-default \
  --cutover-decision /path/to/cutover_decision.json
```

The CLI writes `cutover_activation.json` with the decision digest and resolved
route. Missing, invalid, `hold`, `shadow_ready`, `opt_in_ready`, or
`canary_ready` decisions all fail closed to legacy. An explicit `--mode` remains
an operator override for legacy rollback, agentic opt-in, or shadow execution.

## Compatibility and rollback

Agentic and legacy output roots must remain separate. A rollback changes routing
only; it must never rewrite an Evidence V2 verdict, digest, repo snapshot, or
audit report. Consumers that require V2 trust must check the final invariant and
must reject `legacy-v1-weaker-trust` output even if legacy fidelity validation
passed.

Legacy remains available through `--mode legacy` during canary and after the
initial default transition. Removal of duplicate orchestration requires several
stable releases and is outside the initial P4 cutover.

## Benchmark evidence

The curated dataset is
`tests/fixtures/benchmark_v2/gold_adversarial_v1.json`. It contains a toy case,
FastGS, Spatial-SSRL, and MOS, exact code-excerpt digests, adversarial mutations,
and paired FastGS intents. Freeze the 25-run protocol before execution. Every
Gemma spec sets `CODE2PAPER_LLM_CACHE=0`, and every variant for a case/intent is
bound to the same repository snapshot:

```bash
code2paper-agentic-benchmark-protocol \
  --gold tests/fixtures/benchmark_v2/gold_adversarial_v1.json \
  --workspace-root . \
  --code-root /tmp/code2paper-p4-clean-worktree \
  --out-root /tmp/code2paper-p4-matrix \
  --out /tmp/code2paper-p4-protocol.json \
  --model-id gemma4-31b-nvfp4 \
  --capability-profile-digest sha256:REPLACE_WITH_PREFLIGHT_PROFILE_DIGEST \
  --author toy_train=tests/fixtures/toy_train_project_author_markers.yaml \
  --author fastgs:training_mechanics=tests/fixtures/benchmark_v2/fastgs_training_intent.yaml \
  --author fastgs:rendering_flow=tests/fixtures/benchmark_v2/fastgs_rendering_intent.yaml \
  --author spatial_ssrl=tests/fixtures/benchmark_v2/spatial_ssrl_intent.yaml \
  --author mos=tests/fixtures/benchmark_v2/mos_intent.yaml
```

Execute the curated mutations separately; each output is a digest-pinned trial
artifact consumed by the run review:

```bash
code2paper-agentic-adversarial-campaign \
  --gold tests/fixtures/benchmark_v2/gold_adversarial_v1.json \
  --case fastgs --workspace-root . \
  --out-root /tmp/code2paper-p4-adversarial-fastgs
```

Do not author observations directly for formal cutover. A named reviewer must
write `BenchmarkRunReviewV2` files that pin the run-summary and mutation-trial
digests. The extractor cross-checks agentic claim verdicts against the real
final-text validator and post-hoc trace. Aggregate those reviews with:

```bash
code2paper-agentic-benchmark \
  --gold tests/fixtures/benchmark_v2/gold_adversarial_v1.json \
  --review /path/to/run-review-1.json \
  --review /path/to/run-review-2.json \
  --observations-out /path/to/extracted-observations.json \
  --workspace-root . \
  --rollout /path/to/rollout.json \
  --out /path/to/benchmark_v2.json \
  --cutover-out /path/to/cutover_decision.json
```

No route becomes default merely because this command succeeds. The generated
cutover decision is the authoritative rollout recommendation.

Before completing those reviews, audit each fixed legacy output against the
same curated V2 slice and generate the review queue:

```bash
code2paper-agentic-legacy-v2-audit \
  --gold tests/fixtures/benchmark_v2/gold_adversarial_v1.json \
  --case fastgs --workspace-root . \
  --legacy-out-root /path/to/fixed-fastgs-output \
  --scratch-root /tmp/code2paper-p4-legacy-audit-scratch \
  --out /tmp/code2paper-p4-legacy-audits/fastgs-training_mechanics.json

code2paper-agentic-benchmark-review-queue \
  --gold tests/fixtures/benchmark_v2/gold_adversarial_v1.json \
  --protocol /tmp/code2paper-p4-protocol.json \
  --run-index /tmp/deterministic-index.json \
  --run-index /tmp/fixed-index.json \
  --run-index /tmp/gemma-index.json \
  --mutation-root toy_train=/tmp/adversarial-toy \
  --mutation-root fastgs=/tmp/adversarial-fastgs \
  --mutation-root spatial_ssrl=/tmp/adversarial-spatial \
  --mutation-root mos=/tmp/adversarial-mos \
  --legacy-audit-root /tmp/code2paper-p4-legacy-audits \
  --out /tmp/code2paper-p4-human-review-queue.json
```

`legacy_false_success_candidate` is an audit prompt, not an automatic verdict.
Only a named reviewer may confirm it or classify an agentic block as correct or
false. Until all 25 review entries are complete, cutover remains `hold`.
