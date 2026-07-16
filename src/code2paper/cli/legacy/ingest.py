"""CLI helper for story-first Phase 1 code intake."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from code2paper.llm.providers import load_llm_config_from_env
from code2paper.core.output_paths import resolve_out_root
from code2paper.pipeline.stages.intake import run_phase1_intake


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="code2paper-ingest")
    parser.add_argument("project_root")
    parser.add_argument("--author", dest="author_markers_path", required=True)
    parser.add_argument("--project-id")
    parser.add_argument("--out", help="Write evidence_raw.json to this path (optional convenience export).")
    parser.add_argument(
        "--out-root",
        default="",
        help="Write Phase 1 artifacts under <out-root>/paper/method. Defaults to ./results/<repo_name>_<timestamp>/",
    )
    parser.add_argument("--llm-provider", default=None)
    parser.add_argument("--llm-model", default=None)
    args = parser.parse_args(argv)

    project_root = Path(args.project_root)
    out_root = resolve_out_root(args.out_root, project_root=project_root)
    raw_pack, _comment_index, _raw_context_index, _context_map, paths = run_phase1_intake(
        project_root=project_root,
        method_root=out_root / "paper" / "method",
        author_markers_path=args.author_markers_path,
        project_id=args.project_id,
        llm_config=load_llm_config_from_env(provider=args.llm_provider, model=args.llm_model),
    )
    if args.out:
        _write_json(Path(args.out), raw_pack.model_dump(mode="json"))
    print(json.dumps({name: str(path) for name, path in paths.items()}, ensure_ascii=False, indent=2))
    return 0


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
