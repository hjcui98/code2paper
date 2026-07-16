"""PaperBanana backend for method overview figures."""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import io
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .method_draft_adapter import (
    build_paperbanana_figure_brief,
    clean_method_draft,
    clean_method_text_for_figure,
    clean_tex_to_plain_text,
)


class PaperBananaBackendError(RuntimeError):
    """Raised when the PaperBanana backend cannot be loaded or executed."""


@dataclass(frozen=True)
class PaperBananaFigureConfig:
    draft_path: str | Path
    out_dir: str | Path
    method_evidence_path: str | Path | None = None
    claim_map_path: str | Path | None = None
    paperbanana_root: str | Path | None = None
    chat_api_url: str = ""
    model: str = ""
    retrieval_model: str = ""
    retrieval_ref_limit: int = 40
    image_model: str = ""
    graph_type: str = "tech_route"
    language: str = "en"
    style: str = "academic"
    figure_complex: str = "easy"
    resolution: str = "2K"
    retrieval_setting: str = "auto"
    exp_mode: str = "demo_stylist_once"
    aspect_ratio: str = "16:9"
    max_critic_rounds: int = 0
    num_candidates: int = 1
    clean_tex_to_txt: bool = False
    semantic_anchor: str = ""
    optimize_rounds: int = 1


def generate_paperbanana_figure(**kwargs: Any) -> dict:
    """Synchronous wrapper around the async PaperBanana workflow."""

    return asyncio.run(generate_paperbanana_figure_async(PaperBananaFigureConfig(**kwargs)))


async def generate_paperbanana_figure_async(config: PaperBananaFigureConfig) -> dict:
    """Generate a method overview figure through local PaperBanana."""

    root = _resolve_paperbanana_root(config.paperbanana_root)
    out_dir = Path(config.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_dir = out_dir / "paperbanana_run"
    run_dir.mkdir(parents=True, exist_ok=True)

    draft_path = Path(config.draft_path).expanduser().resolve()
    output_path = out_dir / "method_overview.png"
    _clear_previous_outputs(out_dir)
    content_file = _prepare_content_file(
        draft_path,
        out_dir,
        method_evidence_path=config.method_evidence_path,
        claim_map_path=config.claim_map_path,
        clean_tex_to_txt=config.clean_tex_to_txt,
        semantic_anchor=config.semantic_anchor,
        revision_note="",
    )
    args = SimpleNamespace(
        content="",
        content_file=str(content_file),
        pdf_file="",
        pdf_page_range="1-12",
        caption="Method overview figure generated from an implementation-grounded method draft.",
        task="diagram" if config.graph_type != "plot" else "plot",
        output=str(output_path),
        aspect_ratio=config.aspect_ratio,
        max_critic_rounds=config.max_critic_rounds,
        num_candidates=config.num_candidates,
        retrieval_setting=config.retrieval_setting,
        main_model_name=config.model,
        image_gen_model_name=config.image_model,
        exp_mode=config.exp_mode,
    )
    stdout = io.StringIO()
    stderr = io.StringIO()
    old_env = _apply_paperbanana_env(config, root=root, run_dir=run_dir)
    try:
        module = _load_skill_run_module(root)
        if not hasattr(module, "run"):
            raise PaperBananaBackendError(f"PaperBanana skill module has no run(args): {root / 'skill' / 'run.py'}")
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            await module.run(args)
    except SystemExit as exc:
        code = int(exc.code or 0) if isinstance(exc.code, int) else 1
        if code != 0:
            raise PaperBananaBackendError(
                f"PaperBanana skill exited with code {code}.\nSTDOUT:\n{stdout.getvalue()}\nSTDERR:\n{stderr.getvalue()}"
            ) from exc
    except Exception as exc:
        raise PaperBananaBackendError(
            f"PaperBanana skill failed: {exc}\nSTDOUT:\n{stdout.getvalue()}\nSTDERR:\n{stderr.getvalue()}"
        ) from exc
    finally:
        _restore_env(old_env)

    generated_paths = _parse_generated_paths(stdout.getvalue(), output_path)
    intermediate_outputs = _collect_intermediate_outputs(out_dir)
    for intermediate_path in intermediate_outputs:
        if intermediate_path not in generated_paths:
            generated_paths.append(intermediate_path)
    normalized = _normalize_outputs(generated_paths, out_dir)
    if not any(normalized.values()):
        raise PaperBananaBackendError(
            "PaperBanana completed without producing a supported output file.\n"
            f"Expected output: {output_path}\n"
            f"STDOUT:\n{stdout.getvalue()}\nSTDERR:\n{stderr.getvalue()}"
        )
    warnings = _collect_paperbanana_warnings(
        stdout.getvalue(),
        stderr.getvalue(),
        retrieval_setting=config.retrieval_setting,
    )
    run_log = {
        "round": 1,
        "content_file": str(content_file),
        "warnings": warnings,
        "generated_paths": [str(path) for path in generated_paths],
        "intermediate_outputs": [str(path) for path in intermediate_outputs],
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
    }
    meta = {
        "backend": "paperbanana",
        "status": "success_with_warnings" if warnings else "success",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "draft_path": str(config.draft_path),
            "method_evidence_path": str(config.method_evidence_path) if config.method_evidence_path else "",
            "claim_map_path": str(config.claim_map_path) if config.claim_map_path else "",
            "paperbanana_root": str(root),
            "content_file": str(content_file),
            "clean_tex_to_txt": config.clean_tex_to_txt,
            "semantic_anchor": config.semantic_anchor,
            "optimize_rounds": 1,
            "requested_optimize_rounds": max(1, int(config.optimize_rounds)),
            "single_generation": True,
        },
        "paperbanana": {
            "graph_type": config.graph_type,
            "language": config.language,
            "style": config.style,
            "figure_complex": config.figure_complex,
            "resolution": config.resolution,
            "model": config.model,
            "retrieval_model": config.retrieval_model,
            "retrieval_ref_limit": config.retrieval_ref_limit,
            "image_model": config.image_model,
            "retrieval_setting": config.retrieval_setting,
            "exp_mode": config.exp_mode,
            "aspect_ratio": config.aspect_ratio,
            "max_critic_rounds": config.max_critic_rounds,
            "num_candidates": config.num_candidates,
            "clean_tex_to_txt": config.clean_tex_to_txt,
            "skill_run_path": str(root / "skill" / "run.py"),
            "args": vars(args),
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "rounds": [run_log],
        },
        "outputs": normalized,
        "intermediate_outputs": [str(path) for path in intermediate_outputs],
        "source_outputs": [str(path) for path in generated_paths],
        "warnings": warnings,
        "notes": [
            "PaperBanana receives the selected content file through --content-file.",
            "The upstream PaperBanana skill currently emits PNG images; SVG/PDF are not assumed.",
        ],
    }
    meta_path = out_dir / "method_overview.meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


def _prepare_content_file(
    draft_path: Path,
    out_dir: Path,
    *,
    method_evidence_path: str | Path | None = None,
    claim_map_path: str | Path | None = None,
    clean_tex_to_txt: bool,
    semantic_anchor: str,
    revision_note: str,
) -> Path:
    if not clean_tex_to_txt:
        return draft_path

    text = draft_path.read_text(encoding="utf-8")
    if draft_path.suffix.lower() == ".tex":
        text = clean_tex_to_plain_text(text)
    else:
        text = clean_method_draft(text)
    text = build_paperbanana_figure_brief(
        text,
        method_evidence_path=method_evidence_path,
        claim_map_path=claim_map_path,
        semantic_anchor=semantic_anchor,
        revision_note=revision_note,
    )
    figure_contract = _prepare_figure_intent(
        out_dir=out_dir,
        method_evidence_path=method_evidence_path,
        claim_map_path=claim_map_path,
    )
    if figure_contract:
        text = text.rstrip() + "\n\n" + figure_contract.rstrip() + "\n"

    content_path = out_dir / "method_overview.paperbanana_input.txt"
    content_path.write_text(text, encoding="utf-8")
    return content_path


def _prepare_figure_intent(
    *,
    out_dir: Path,
    method_evidence_path: str | Path | None,
    claim_map_path: str | Path | None,
) -> str:
    if not method_evidence_path or not claim_map_path:
        return ""
    try:
        from code2paper.agentic.claim_verifier import build_claim_verification_report
        from code2paper.agentic.figure_planner import (
            build_evidence_backed_figure_plan,
            figure_plan_brief,
            write_figure_plan,
        )
        from code2paper.core.schemas import ClaimEvidenceMap, MethodEvidence

        method_evidence = MethodEvidence.model_validate(json.loads(Path(method_evidence_path).read_text(encoding="utf-8")))
        claim_map = ClaimEvidenceMap.model_validate(json.loads(Path(claim_map_path).read_text(encoding="utf-8")))
        verification = build_claim_verification_report(method_evidence, claim_map)
        plan = build_evidence_backed_figure_plan(
            method_evidence=method_evidence,
            claim_map=claim_map,
            claim_verification=verification,
        )
        write_figure_plan(out_dir / "method_overview.intent.json", plan)
        return figure_plan_brief(plan)
    except Exception:
        return ""


def _clear_previous_outputs(out_dir: Path) -> None:
    suffixes = {".png", ".jpg", ".jpeg", ".svg", ".pdf", ".pptx", ".drawio"}
    for suffix in suffixes:
        path = out_dir / f"method_overview{suffix}"
        if path.is_file():
            path.unlink()
    stale_intent = out_dir / "method_overview.intent.json"
    if stale_intent.is_file():
        stale_intent.unlink()


def _collect_paperbanana_warnings(
    stdout: str,
    stderr: str,
    *,
    retrieval_setting: str,
) -> list[str]:
    warnings: list[str] = []
    output = f"{stdout}\n{stderr}"
    if retrieval_setting != "none":
        if "Retrieved 0 references" in output:
            warnings.append(
                f"retrieval_setting={retrieval_setting} produced 0 references; generation continued without retrieved examples."
            )
        if "Failed to parse retrieval result" in output:
            warnings.append("PaperBanana failed to parse the retrieval result.")
        if "Error: All" in output and "attempts failed" in output:
            warnings.append("At least one PaperBanana model-call retry loop exhausted all attempts.")
        if "error code: 429" in output or "'param': '429'" in output:
            warnings.append("Provider returned 429 rate limiting during PaperBanana execution.")
        if "error code: 400" in output or "'param': '400'" in output:
            warnings.append("Provider returned 400 errors during PaperBanana execution.")
    return _dedupe_warnings(warnings)


def _dedupe_warnings(warnings: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for warning in warnings:
        if warning not in seen:
            seen.add(warning)
            deduped.append(warning)
    return deduped


def _resolve_paperbanana_root(root: str | Path | None) -> Path:
    repo_root = Path(__file__).resolve().parents[4]
    raw_candidates = [
        root,
        repo_root / "paperbanana_single_shot",
        Path.cwd() / "paperbanana_single_shot",
        os.environ.get("PAPERBANANA_ROOT"),
    ]
    for candidate in raw_candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser().resolve()
        if (path / "skill" / "run.py").is_file() and (path / "requirements.txt").is_file():
            return path
    searched = ", ".join(str(c) for c in raw_candidates if c)
    raise PaperBananaBackendError(
        "Could not locate PaperBanana root. Expected ./paperbanana_single_shot, "
        "or pass --paperbanana-root for a custom location. "
        f"Searched: {searched}"
    )


def _load_skill_run_module(root: Path):
    run_path = root / "skill" / "run.py"
    module_name = f"_code2paper_paperbanana_skill_{abs(hash(str(run_path.resolve())))}"
    spec = importlib.util.spec_from_file_location(module_name, run_path)
    if spec is None or spec.loader is None:
        raise PaperBananaBackendError(f"Could not load PaperBanana skill module: {run_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _apply_paperbanana_env(
    config: PaperBananaFigureConfig,
    *,
    root: Path,
    run_dir: Path,
) -> dict[str, str | None]:
    updates: dict[str, str] = {}
    text_base_url = _resolve_text_base_url(config)
    image_base_url = _resolve_image_base_url(config, text_base_url=text_base_url)
    if config.model:
        updates["MAIN_MODEL_NAME"] = config.model
    text_model = str(config.model or "").strip()
    retrieval_model = str(config.retrieval_model or "").strip() or text_model
    if retrieval_model:
        updates["RETRIEVER_MODEL_NAME"] = retrieval_model
    if config.retrieval_ref_limit:
        updates["RETRIEVER_REF_LIMIT"] = str(max(1, int(config.retrieval_ref_limit)))
    if config.image_model:
        updates["IMAGE_GEN_MODEL_NAME"] = config.image_model
    _forward_env(
        updates,
        target="OPENAI_API_KEY",
        candidates=["CODE2PAPER_FIGURE_OPENAI_API_KEY", "OPENAI_API_KEY"],
    )
    _forward_env(
        updates,
        target="GOOGLE_API_KEY",
        candidates=["CODE2PAPER_FIGURE_GOOGLE_API_KEY", "GOOGLE_API_KEY"],
    )
    _forward_env(
        updates,
        target="ANTHROPIC_API_KEY",
        candidates=["CODE2PAPER_FIGURE_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"],
    )
    _forward_env(
        updates,
        target="OPENROUTER_API_KEY",
        candidates=["CODE2PAPER_FIGURE_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"],
    )
    if text_base_url:
        updates["OPENAI_BASE_URL"] = text_base_url
    _forward_env(
        updates,
        target="OPENROUTER_BASE_URL",
        candidates=["CODE2PAPER_FIGURE_OPENROUTER_BASE_URL", "OPENROUTER_BASE_URL"],
    )

    image_api_key = _first_nonempty_env(
        "CODE2PAPER_FIGURE_IMAGE_API_KEY",
        "AIHUBMIX_API_KEY",
        "OPENAI_API_KEY",
    )
    if image_api_key:
        updates["AIHUBMIX_API_KEY"] = image_api_key
    if image_base_url:
        updates["AIHUBMIX_BASE_URL"] = image_base_url
    updates.setdefault("MPLCONFIGDIR", str(run_dir / "matplotlib_cache"))

    old_values = {key: os.environ.get(key) for key in updates}
    for key, value in updates.items():
        os.environ[key] = value
    return old_values


def _forward_env(updates: dict[str, str], *, target: str, candidates: list[str]) -> None:
    value = _first_nonempty_env(*candidates)
    if value:
        updates[target] = value


def _first_nonempty_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _resolve_text_base_url(config: PaperBananaFigureConfig) -> str:
    for candidate in (
        config.chat_api_url,
        os.environ.get("CODE2PAPER_FIGURE_OPENAI_BASE_URL", ""),
        os.environ.get("CODE2PAPER_OPENAI_BASE_URL", ""),
    ):
        normalized = _normalize_openai_compatible_base_url(candidate)
        if normalized:
            return normalized
    return ""


def _resolve_image_base_url(config: PaperBananaFigureConfig, *, text_base_url: str) -> str:
    for candidate in (
        os.environ.get("CODE2PAPER_FIGURE_IMAGE_BASE_URL", ""),
        os.environ.get("AIHUBMIX_BASE_URL", ""),
        os.environ.get("OPENAI_BASE_URL", ""),
        text_base_url if str(config.image_model or "").startswith("aihubmix/") else "",
    ):
        normalized = _normalize_openai_compatible_base_url(candidate)
        if normalized:
            return normalized
    return ""


def _normalize_openai_compatible_base_url(raw: str | None) -> str:
    base = str(raw or "").strip().rstrip("/")
    if not base:
        return ""
    for suffix in (
        "/v1/chat/completions",
        "/chat/completions",
        "/v1/images/generations",
        "/images/generations",
    ):
        if base.endswith(suffix):
            return base[: -len(suffix)].rstrip("/")
    return base


def _restore_env(old_values: dict[str, str | None]) -> None:
    for key, value in old_values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _parse_generated_paths(stdout: str, expected_output: Path) -> list[Path]:
    paths: list[Path] = []
    _append_existing(paths, expected_output)
    for line in str(stdout or "").splitlines():
        text = line.strip()
        if not text:
            continue
        _append_existing(paths, text)
    return _dedupe_existing(paths)


def _collect_intermediate_outputs(out_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for directory in [
        out_dir / "method_overview_intermediates",
        out_dir / "method_framework_intermediates",
    ]:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.png")):
            _append_existing(paths, path)
    return _dedupe_existing(paths)


def _append_existing(paths: list[Path], value: Any) -> None:
    if not value:
        return
    path = Path(str(value))
    try:
        if path.exists() and path.is_file():
            paths.append(path)
    except (OSError, ValueError):
        # Ignore non-path stdout lines (e.g., long retry logs) that cannot be stat'ed.
        return


def _dedupe_existing(paths: list[Path]) -> list[Path]:
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        try:
            resolved = path.resolve()
        except (OSError, ValueError):
            continue
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(resolved)
    return deduped


def _normalize_outputs(paths: list[Path], out_dir: Path) -> dict[str, str]:
    targets = {
        "svg": out_dir / "method_overview.svg",
        "png": out_dir / "method_overview.png",
        "pdf": out_dir / "method_overview.pdf",
        "pptx": out_dir / "method_overview.pptx",
        "drawio": out_dir / "method_overview.drawio",
    }
    suffix_map = {
        "svg": [".svg"],
        "png": [".png", ".jpg", ".jpeg"],
        "pdf": [".pdf"],
        "pptx": [".pptx"],
        "drawio": [".drawio"],
    }
    normalized = {key: "" for key in targets}
    for key, suffixes in suffix_map.items():
        source = _first_with_suffix(paths, suffixes)
        if source:
            if source.resolve() != targets[key].resolve():
                shutil.copy2(source, targets[key])
            normalized[key] = str(targets[key])

    if normalized["svg"]:
        converted = _try_convert_svg(Path(normalized["svg"]), targets["png"], targets["pdf"])
        normalized.update({key: value for key, value in converted.items() if not normalized.get(key)})
    return normalized


def _first_with_suffix(paths: list[Path], suffixes: list[str]) -> Path | None:
    for path in paths:
        if path.suffix.lower() in suffixes:
            return path
    return None


def _try_convert_svg(svg_path: Path, png_path: Path, pdf_path: Path) -> dict[str, str]:
    outputs: dict[str, str] = {}
    try:
        import cairosvg  # type: ignore
    except Exception:
        return outputs
    if not png_path.exists():
        try:
            cairosvg.svg2png(url=str(svg_path), write_to=str(png_path))
            outputs["png"] = str(png_path)
        except Exception:
            pass
    if not pdf_path.exists():
        try:
            cairosvg.svg2pdf(url=str(svg_path), write_to=str(pdf_path))
            outputs["pdf"] = str(pdf_path)
        except Exception:
            pass
    return outputs
