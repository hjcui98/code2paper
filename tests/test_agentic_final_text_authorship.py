from __future__ import annotations

from code2paper.agentic.final_text_authorship import (
    GeneratedTextSpanV1,
    build_final_text_authorship_ledger,
    rewrite_final_text_authorship_ledger,
)
from code2paper.agentic.rewrite_agent import LocalRewritePatchV1


def test_writer_and_rewrite_spans_own_every_final_lexical_token() -> None:
    writer = "## Mechanism\nThe encoder reads the configured input."
    rewrite = " It then returns the projected representation."
    final_text = writer + rewrite

    ledger = build_final_text_authorship_ledger(
        final_text,
        (
            GeneratedTextSpanV1(
                span_id="writer:section-1",
                text=writer,
                owner="writer",
                response_ref="sha256:writer-response",
                section_id="section-1",
                generation_trace_id="trace:writer",
            ),
            GeneratedTextSpanV1(
                span_id="rewrite:section-1:1",
                text=rewrite,
                owner="rewrite",
                response_ref="sha256:rewrite-response",
                section_id="section-1",
                generation_trace_id="trace:rewrite",
            ),
        ),
    )

    assert ledger.hard_gate_passed
    assert [span.owner for span in ledger.spans] == ["writer", "rewrite"]
    assert not ledger.unowned_token_ranges


def test_deterministic_token_injected_between_generated_spans_fails_ledger() -> None:
    writer = "The encoder reads the configured input."
    final_text = writer + " HARNESS_INSERTED"

    ledger = build_final_text_authorship_ledger(
        final_text,
        (
            GeneratedTextSpanV1(
                span_id="writer:section-1",
                text=writer,
                owner="writer",
                response_ref="sha256:writer-response",
            ),
        ),
    )

    assert not ledger.hard_gate_passed
    assert ledger.unowned_token_ranges
    assert "unowned_lexical_spans:1" in ledger.failures


def test_missing_rewrite_response_reference_fails_ledger() -> None:
    text = "A generated replacement."
    ledger = build_final_text_authorship_ledger(
        text,
        (
            GeneratedTextSpanV1(
                span_id="rewrite:1",
                text=text,
                owner="rewrite",
                response_ref="",
            ),
        ),
    )

    assert not ledger.hard_gate_passed
    assert "missing_generation_response_ref" in ledger.failures


def test_rewrite_ledger_preserves_writer_fragments_and_owns_replacement() -> None:
    incumbent = "The encoder reads stale inputs and returns outputs."
    writer_ledger = build_final_text_authorship_ledger(
        incumbent,
        (GeneratedTextSpanV1(
            span_id="writer:section-1",
            text=incumbent,
            owner="writer",
            response_ref="sha256:writer-response",
            section_id="section-1",
        ),),
    )
    start = incumbent.index("stale")
    patch = LocalRewritePatchV1(
        patch_id="p1",
        start=start,
        end=start + len("stale"),
        original_text="stale",
        replacement_text="configured",
        issue_ids=("FAC1",),
    )
    candidate = incumbent[:start] + "configured" + incumbent[start + len("stale"):]

    ledger = rewrite_final_text_authorship_ledger(
        incumbent_text=incumbent,
        candidate_text=candidate,
        incumbent_ledger=writer_ledger,
        patches=(patch,),
        response_ref="sha256:rewrite-response",
        generation_trace_id="trace:rewrite",
    )

    assert ledger.hard_gate_passed
    assert [span.owner for span in ledger.spans] == ["writer", "rewrite", "writer"]
    assert ledger.spans[1].response_ref == "sha256:rewrite-response"
    assert not ledger.unowned_token_ranges


def test_rewrite_ledger_rejects_unrelated_candidate_bytes() -> None:
    incumbent = "Owned text."
    writer_ledger = build_final_text_authorship_ledger(
        incumbent,
        (GeneratedTextSpanV1(
            span_id="writer:1",
            text=incumbent,
            owner="writer",
            response_ref="sha256:writer",
        ),),
    )
    patch = LocalRewritePatchV1(
        patch_id="p1",
        start=0,
        end=5,
        original_text="Owned",
        replacement_text="Valid",
        issue_ids=("FAC1",),
    )

    try:
        rewrite_final_text_authorship_ledger(
            incumbent_text=incumbent,
            candidate_text="HARNESS " + incumbent,
            incumbent_ledger=writer_ledger,
            patches=(patch,),
            response_ref="sha256:rewrite",
        )
    except ValueError as exc:
        assert str(exc) == "rewrite_candidate_bytes_mismatch"
    else:
        raise AssertionError("unrelated deterministic bytes must fail authorship")
