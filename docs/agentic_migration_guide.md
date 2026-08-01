# Code2Paper Agentic Migration Guide

> **Normative self-repair rule:** validation failures must become typed repair
> issues routed back to the owning Agent for bounded retry. Silent filtering,
> pass-by-fallback, hard-gate weakening, and obligation reduction are forbidden.
> See `docs/agentic_error_feedback_and_self_repair_principle.md`.

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
Gemma spec sets `CODE2PAPER_LLM_CACHE=0`; every model-backed spec also freezes a
credential-free OpenAI-compatible base URL and capability profile. Every variant
for a case/intent is bound to the same repository snapshot. The frozen semantic
verifier budget is 16 calls, covering the largest seven-claim case plus one bounded
authoring revision without making a successful validation impossible by construction:

```bash
code2paper-agentic-benchmark-protocol \
  --gold tests/fixtures/benchmark_v2/gold_adversarial_v1.json \
  --workspace-root . \
  --code-root /tmp/code2paper-p4-clean-worktree \
  --out-root /tmp/code2paper-p4-matrix \
  --out /tmp/code2paper-p4-protocol.json \
  --model-id gemma4-31b-nvfp4 \
  --llm-base-url http://127.0.0.1:8000 \
  --capability-profile tests/baselines/agentic/gemma4_mtp_vllm.profile.json \
  --capability-profile-digest sha256:1dce0d3e1e07a6dda065309cdade03907f414187b97e3a401fb6038b737af3a7 \
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
final-text validator and post-hoc trace. For a small ad-hoc set, aggregate
individual reviews with:

```bash
code2paper-agentic-benchmark \
  --gold tests/fixtures/benchmark_v2/gold_adversarial_v1.json \
  --protocol /tmp/code2paper-p4-protocol.json \
  --review /path/to/run-review-1.json \
  --review /path/to/run-review-2.json \
  --observations-out /path/to/extracted-observations.json \
  --workspace-root . \
  --rollout /path/to/rollout.json \
  --rollout-artifact /path/to/validated-shadow-trial.json \
  --out /path/to/benchmark_v2.json \
  --cutover-out /path/to/cutover_decision.json
```

No route becomes default merely because this command succeeds. A schema 2.2
cutover decision must retain the validated review-file digests and pass the
remaining rollout gates before it can authorize the implicit default.
`--rollout` contains policy inputs such as the team false-block threshold and
migration/legacy-contract declarations; its old shadow/opt-in/canary counters
are untrusted and now fail closed. Progress comes only from repeated
`--rollout-artifact` inputs. Each trial binds its case, stage, named reviewer,
timezone-aware review time, prior stage-authorization decision, agentic run
summary/completion, and (for shadow) legacy comparison run by SHA-256. Opt-in
evidence is accepted only after shadow evidence for the same case, and canary
only after opt-in. Any canary incident prevents `default_ready`.

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

The legacy audit is not a count-only advisory. It freezes every visible factual
claim extracted from the exact draft, its V2 verdict, every visible SVG text
annotation, and every rendered arrow. The queue refuses a missing/stale audit,
draft, SVG, claim, or figure element, so reviewers cannot improve the legacy
baseline by selectively omitting weak sentences or diagram elements.

Do not manually copy 25 nested templates out of that queue. Materialize a
non-overwriting review workspace instead:

```bash
code2paper-agentic-benchmark-review-workspace materialize \
  --queue /tmp/code2paper-p4-human-review-queue.json \
  --out-root /tmp/code2paper-p4-review-workspace
```

This creates one editable JSON under `reviews/` and one read-only context file
under `contexts/` for every protocol identity. Context files link the frozen
method text, figure, validator, final invariant, package, code-grounded gold
claims, and their digests. They intentionally exclude the reference paper as
evidence. For every agentic run with a rendered figure, the review JSON also
contains the complete frozen scene inventory. The reviewer must fill
`semantically_supported` and `rendered_drift` for every visible node, edge,
annotation, and group; edges additionally require `direct_relation_evidence`.
Deleting the inventory or leaving it empty is not a valid shortcut. The command
refuses to overwrite a non-empty workspace.

The same exact-inventory rule applies to final prose. Every review must retain
all atomic claim IDs from the digest-pinned `final_text_claims` artifact, with
byte-identical claim text and an explicit validator verdict equal to the frozen
`text_evidence_validation` verdict. The claim, validator, final-trace, and
human-review ID sets must be identical; omitting, duplicating, renaming, or
rewriting a claim fails validation instead of removing it from human metrics.
Every retained claim must explicitly set `semantic_match` (`matched` or
`no_match`), `mutation_match`, `direct_evidence_support`, and
`qualifiers_preserved`. An empty gold or mutation ID is not interpreted as an
answer. Every run also requires an explicit `usable_completion`; paired-intent
runs require `intent_fields_reviewed=true`, and blocked runs require both a
written rationale and a structured correct-repairable/correct-terminal/
false-block classification. Unresolved fields remain `pending_human_review`.
For each retained claim, the reviewer must also set
`direct_evidence_support` after checking the frozen evidence snapshot and code
spans. A gold-claim mapping alone is not a semantic-precision hit: the cited
direct code evidence must independently support the exact final sentence.
The queue, manifest, and every context file are digest-bound to the frozen gold
dataset and protocol; context or template drift fails even while reviewer/name
placeholders are still pending.

Use the workspace command instead of hand-editing adjudication fields. First
inspect exact remaining work:

```bash
code2paper-agentic-benchmark-review-workspace progress \
  --workspace /tmp/code2paper-p4-review-workspace
```

Build a read-only dossier before deciding. It includes each generated claim,
the exact EvidenceSpanV2 excerpts actually cited by the validator, code-grounded
gold claims and qualifiers, figure inventory/scene/audit, and full curated
mutation trial payloads. Every source, artifact, and excerpt digest is checked:

```bash
code2paper-agentic-benchmark-review-workspace inspect \
  --workspace /tmp/code2paper-p4-review-workspace \
  --review 002-toy_train-agentic_deterministic-default-r1.json \
  --out /tmp/review-002-dossier.md

code2paper-agentic-benchmark-review-workspace inspect-all \
  --workspace /tmp/code2paper-p4-review-workspace \
  --out-root /tmp/code2paper-p4-review-dossiers
```

`inspect-all` atomically publishes one Markdown file per protocol identity and a
digest-indexed `dossier_manifest.json`. It refuses an existing output directory
and removes staging output if any artifact has drifted. Dossiers intentionally
exclude the reference paper, never suggest a mapping or verdict, and cannot be
used as evidence that a human decision occurred.

Then record one complete claim, figure, or run decision at a time. The `--review`
selector must be an exact manifest basename, `reviews/...` path, or absolute
manifest path. For example:

```bash
code2paper-agentic-benchmark-review-workspace claim \
  --workspace /tmp/code2paper-p4-review-workspace \
  --review 002-toy_train-agentic_deterministic-default-r1.json \
  --claim-id FAC1 \
  --semantic-match matched --gold-claim-id T1 \
  --mutation-match no_match \
  --direct-evidence-support true --qualifiers-preserved true

code2paper-agentic-benchmark-review-workspace run \
  --workspace /tmp/code2paper-p4-review-workspace \
  --review 002-toy_train-agentic_deterministic-default-r1.json \
  --usable-completion true --intent-fields-reviewed true
```

The command rejects unknown gold, mutation, and relation IDs, path escape,
immutable binding drift, incomplete blocked-run classifications, and an intent
review that is false for paired-intent runs. It writes atomically. Only after
`progress` reports `ready_to_sign=true` may the human reviewer sign:

```bash
code2paper-agentic-benchmark-review-workspace sign \
  --workspace /tmp/code2paper-p4-review-workspace \
  --review 002-toy_train-agentic_deterministic-default-r1.json \
  --reviewer "Ada Reviewer" \
  --reviewed-at 2026-07-18T12:00:00+08:00
```

Signing never infers a judgment and does not auto-fill any field. Signed files
are immutable to these commands; corrections require a newly materialized,
auditable review workspace rather than silently rewriting a signature.

After named reviewers fill the JSON files, validate the whole workspace before
benchmark aggregation:

```bash
code2paper-agentic-benchmark-review-workspace validate \
  --queue /tmp/code2paper-p4-human-review-queue.json \
  --workspace /tmp/code2paper-p4-review-workspace \
  --gold tests/fixtures/benchmark_v2/gold_adversarial_v1.json \
  --protocol /tmp/code2paper-p4-protocol.json \
  --report-out /tmp/code2paper-p4-review-validation.json
```

Exit code `1` means human placeholders remain; exit code `2` means an identity,
queue, run, claim/verdict, mutation, artifact digest, or protocol binding is
invalid. Neither state emits observations. A completely validated workspace
can be consumed without spelling out 25 `--review` flags:

```bash
code2paper-agentic-benchmark \
  --gold tests/fixtures/benchmark_v2/gold_adversarial_v1.json \
  --protocol /tmp/code2paper-p4-protocol.json \
  --review-queue /tmp/code2paper-p4-human-review-queue.json \
  --review-workspace /tmp/code2paper-p4-review-workspace \
  --workspace-root . \
  --rollout /path/to/rollout.json \
  --rollout-artifact /path/to/shadow-case-1.json \
  --rollout-artifact /path/to/opt-in-case-1.json \
  --rollout-artifact /path/to/canary-case-1.json \
  --out /path/to/benchmark_v2.json \
  --cutover-out /path/to/cutover_decision.json
```

`legacy_false_success_candidate` is an audit prompt, not an automatic verdict.
Only a named reviewer may confirm it or classify an agentic block as correct or
false. Until all 25 review entries are complete, cutover remains `hold`.

After a reviewed benchmark emits `shadow_ready`, create rollout trials without
hand-copying digests:

```bash
code2paper-agentic-rollout-artifact materialize \
  --stage shadow --case fastgs \
  --authorization-decision /path/to/shadow-ready.json \
  --agentic-run-summary /path/to/agentic_run_summary.json \
  --legacy-run-summary /path/to/code2paper_run_report.json \
  --protocol /tmp/code2paper-p4-protocol.json \
  --out /path/to/shadow-fastgs.json
```

The command refuses to overwrite existing reviewer work. A named reviewer fills
only `reviewer`, `reviewed_at`, `accepted`, and canary `incident_ids`. Validate
the complete accumulated stage set before passing the same artifacts to the
benchmark command:

```bash
code2paper-agentic-rollout-artifact validate \
  --artifact /path/to/shadow-fastgs.json \
  --gold tests/fixtures/benchmark_v2/gold_adversarial_v1.json \
  --protocol /tmp/code2paper-p4-protocol.json \
  --out /path/to/validated-rollout-evidence.json
```
