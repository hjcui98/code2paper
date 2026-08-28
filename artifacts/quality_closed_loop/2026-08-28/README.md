# Quality closed-loop live run — 2026-08-28

This directory contains the latest Qwen3.8/8006 real-run evidence for the
paragraph-transaction, formula-consumer, and fail-closed callback changes.

## Contents

- `comparison_retain.json`: aggregate comparison for LinearRAG, DyG, and EBCAR.
- `linearrag/`, `dyg/`, `ebcar/`: complete retained run bundles copied from
  the corresponding 2026-08-28 run directories.
- `*_diagnostics.json` and `*_oracle.json`: per-project quality diagnostics and
  oracle comparisons.
- `*.log`: per-project run logs.
- `runtime/`: model identity and runtime metric snapshots from the run.
- `paperbanana_single_shot_worktree.patch`: the uncommitted nested
  PaperBanana worktree diff, preserved because a root Git commit can only
  record the submodule pointer.

Older runs under `/tmp` are intentionally not included here. The files are
diagnostic evidence only; an empty `repository_verified_method.md` remains a
failed verification result and is not treated as a successful publication.
