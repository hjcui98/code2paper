"""Original compiled author-only page material for offline V01 consumers.

Only the Writer provider answer is synthetic. The untouched legacy archive,
narrative and Writer manifest retain the technical page and its obligations.
The zero-task Formalizer execution is scoped to this author's empty formula
requirements; it does not certify completion of the neighboring technical page.
This fixture proves local material contracts, not DSH/provider acceptance.
"""

from __future__ import annotations

from typing import Any

from code2paper.agentic.formalization_agent import execute_formalizer_invocation_plan

from . import legacy_fixture_builder as b


def build_fixture(*, material_sink: dict[str, Any] | None = None,
                  budget_envelope: Any = None) -> dict[str, Any]:
    archive, obligations = b._evidence_archive()
    envelope = budget_envelope if budget_envelope is not None else b._budget_envelope()
    narrative = b._narrative_plan(archive)
    manifest, plan, sections = b._writer_material(archive, obligations, narrative, envelope)
    section, = (item for item in sections if item.section_id == b.AUTHOR_NO_ATOM_SECTION_ID)
    page, = (item for item in manifest.pages
             if item.page_id == section.prompt_payload["unified_v2_page_id"])
    invocation, = (item for item in plan.invocations
                   if item.page_id == page.page_id and not item.is_repair)

    # Author scope is taken from the compiled page, not by deleting technical
    # obligations from the shared Writer manifest or editing a receipt.
    rows = b._page_paragraph_rows(section)
    if (page.atom_ids or section.prompt_payload.get("formula_packages")
            or section.prompt_payload.get("formula_obligations")
            or any(any(b.required_targets_from_plan_row(row).values()) for row in rows)):
        raise AssertionError("author fixture unexpectedly requires evidence or formulas")
    formalizer_manifest = b.build_consumer_workset_manifest_v2(
        archive, {}, max_page_input_tokens=envelope.max_page_input_tokens,
        max_obligations_per_page=envelope.max_obligations_per_page,
    )
    formalizer_plan = b.build_consumer_invocation_plan_v1(
        formalizer_manifest, envelope, phase="formalizer", max_attempts=1,
        profile_digest=envelope.profile_digest,
        model_identity_digest=envelope.model_identity_digest, model_context_tokens=131072,
    )
    if formalizer_plan.invocations:
        raise AssertionError("author scope must have no Formalizer tasks")

    def no_provider_calls(*_args, **_kwargs):
        raise AssertionError("author scope must not call a Formalizer provider")

    formalizer = execute_formalizer_invocation_plan(
        plan=formalizer_plan, workset_manifest=formalizer_manifest, archive=archive,
        obligations_by_id={}, caller=no_provider_calls, max_attempts=1,
        budget_envelope=envelope, model_identity_digest=envelope.model_identity_digest,
        run_digest=archive.content_digest,
    )
    if formalizer.task_failures or formalizer.assertion_failures:
        raise AssertionError("original no-task Formalizer execution failed")
    request = b.build_publication_writer_request(
        section, system_prompt=section.system_prompt, schema_name=b.SCHEMA_NAME,
        response_json_schema=b.consumer_response_json_schema("writer", section_id=section.section_id),
    )
    response = b.offline_provider_response(section, request)
    writer = b._page_fixture(
        section=section, request=request, response_schema=request.response_json_schema,
        invocation=invocation, page=page, scenario="author_no_atom_page",
        provider_response=response,
    )
    if material_sink is not None:
        material_sink.update(
            section=section, request=request, page=page, narrative=narrative,
            manifest=manifest, plan=plan, formalizer=formalizer,
            writer_raw=response.text, archive=archive, budget_envelope=envelope,
            formalizer_plan=formalizer_plan, formalizer_manifest=formalizer_manifest,
        )
    return {
        "schema_version": b.FIXTURE_SCHEMA_VERSION,
        "scenario": "author_no_atom_page",
        "writer": writer,
        "formalizer": formalizer.model_dump(mode="json"),
        "formalizer_completion_scope": "author page only: no formula requirements",
        "writer_raw_origin": "offline_provider_response.text before Binder",
        "dsh_provider_acceptance": "not_run",
    }
