"""Immutable, consumer-neutral page manifests for mechanism context delivery.

The existing ``MechanismContextSliceV1`` is the canonical technical record.
This module adds a page-level audit envelope around those exact records: page
bytes are the bytes that appear in the shared Formalizer/Writer payload, and
the manifest never creates a second role-specific serialization.
"""

from __future__ import annotations

import math
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.digest import digest_json
from code2paper.agentic.mechanism_context_models import (
    MechanismContextSliceV1,
    MechanismContextV1,
    MechanismContextViewV1,
    canonical_json_bytes,
    compute_shared_payload_digest,
    conservative_token_estimate,
    shared_slice_payload_record,
    sha256_digest,
)
from code2paper.agentic.mechanism_context_projection import (
    build_mechanism_context_slices,
    build_mechanism_context_view,
)


DEFAULT_SHARED_PAGE_TOKEN_BUDGET = 20_000
TOKEN_ESTIMATOR_ID = "utf8_bytes_div4_ceil_v1"


class SharedPayloadPageV1(BaseModel):
    """One immutable technical page delivered identically to both consumers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    mechanism_id: str
    page_index: int = Field(ge=0)
    detail_ids: tuple[str, ...] = ()
    exact_evidence_ids: tuple[str, ...] = ()
    source_context_digest: str
    view_digest: str
    slice_digest: str
    token_estimate: int = Field(ge=0)
    token_budget: int = Field(gt=0)
    technical_payload: dict[str, Any]
    technical_bytes_digest: str
    content_digest: str = ""

    @property
    def serialized_bytes(self) -> bytes:
        return canonical_json_bytes(self.technical_payload)

    @model_validator(mode="after")
    def _validate_page(self) -> "SharedPayloadPageV1":
        actual_bytes = canonical_json_bytes(self.technical_payload)
        expected_bytes_digest = sha256_digest(actual_bytes)
        if self.technical_bytes_digest != expected_bytes_digest:
            raise ValueError(
                "shared payload page technical_bytes_digest mismatch"
            )
        expected_tokens = conservative_token_estimate(self.technical_payload)
        if self.token_estimate != expected_tokens:
            raise ValueError("shared payload page token_estimate mismatch")
        payload_detail_ids = tuple(
            str(item.get("detail_id"))
            for item in (self.technical_payload.get("technical_payload", {}).get("details", ())
                         if isinstance(self.technical_payload.get("technical_payload"), Mapping)
                         else self.technical_payload.get("details", ()))
            if isinstance(item, Mapping) and str(item.get("detail_id") or "").strip()
        )
        if payload_detail_ids and payload_detail_ids != self.detail_ids:
            raise ValueError("shared payload page detail_ids mismatch")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected_digest = digest_json(payload)
        if self.content_digest and self.content_digest != expected_digest:
            raise ValueError("shared payload page content_digest mismatch")
        object.__setattr__(self, "content_digest", expected_digest)
        return self


class SharedPayloadDeliveryReceiptV1(BaseModel):
    """Receipt proving one consumer received every manifest page byte-for-byte."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    consumer_role: Literal["formalizer", "writer"]
    mechanism_id: str
    manifest_digest: str
    source_context_digest: str
    view_digest: str
    page_indices: tuple[int, ...] = ()
    page_digests: tuple[str, ...] = ()
    page_bytes_digests: tuple[str, ...] = ()
    actual_payload_bytes_digest: str = ""
    accepted: bool = False
    rejection_code: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_receipt(self) -> "SharedPayloadDeliveryReceiptV1":
        if self.accepted and not (
            self.page_indices
            and len(self.page_indices) == len(self.page_digests) == len(self.page_bytes_digests)
            and self.actual_payload_bytes_digest
        ):
            raise ValueError("accepted shared payload receipt is incomplete")
        if not self.accepted and not self.rejection_code.strip():
            raise ValueError("rejected shared payload receipt requires rejection_code")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected_digest = digest_json(payload)
        if self.content_digest and self.content_digest != expected_digest:
            raise ValueError("shared payload receipt content_digest mismatch")
        object.__setattr__(self, "content_digest", expected_digest)
        return self


class SharedPayloadManifestV1(BaseModel):
    """Ordered immutable manifest for a mechanism's shared technical pages."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    mechanism_id: str
    source_context_digest: str
    view_digest: str
    token_estimator: str = TOKEN_ESTIMATOR_ID
    token_budget: int = Field(gt=0)
    pages: tuple[SharedPayloadPageV1, ...] = ()
    page_digests: tuple[str, ...] = ()
    page_bytes_digests: tuple[str, ...] = ()
    total_token_estimate: int = Field(ge=0)
    shared_payload_digest: str = ""
    blocking_reasons: tuple[str, ...] = ()
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_manifest(self) -> "SharedPayloadManifestV1":
        if tuple(page.page_index for page in self.pages) != tuple(range(len(self.pages))):
            raise ValueError("shared payload manifest page indices are not contiguous")
        expected_page_digests = tuple(page.content_digest for page in self.pages)
        expected_bytes_digests = tuple(page.technical_bytes_digest for page in self.pages)
        if self.page_digests and self.page_digests != expected_page_digests:
            raise ValueError("shared payload manifest page_digests mismatch")
        if self.page_bytes_digests and self.page_bytes_digests != expected_bytes_digests:
            raise ValueError("shared payload manifest page_bytes_digests mismatch")
        object.__setattr__(self, "page_digests", expected_page_digests)
        object.__setattr__(self, "page_bytes_digests", expected_bytes_digests)
        expected_total = sum(page.token_estimate for page in self.pages)
        if self.total_token_estimate != expected_total:
            raise ValueError("shared payload manifest total_token_estimate mismatch")
        if self.pages:
            actual_shared_digest = sha256_digest(canonical_json_bytes([
                page.technical_payload for page in self.pages
            ]))
            if self.shared_payload_digest and self.shared_payload_digest != actual_shared_digest:
                raise ValueError("shared payload manifest shared_payload_digest mismatch")
            object.__setattr__(self, "shared_payload_digest", actual_shared_digest)
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected_digest = digest_json(payload)
        if self.content_digest and self.content_digest != expected_digest:
            raise ValueError("shared payload manifest content_digest mismatch")
        object.__setattr__(self, "content_digest", expected_digest)
        return self


def _slice_payload(slice_obj: MechanismContextSliceV1) -> dict[str, Any]:
    """Return the exact record used by ``serialize_shared_mechanism_payload``."""

    return shared_slice_payload_record(slice_obj)


def build_shared_payload_manifest(
    view_or_context_or_slices: MechanismContextViewV1 | MechanismContextV1 | Sequence[MechanismContextSliceV1],
    *,
    token_budget: int = DEFAULT_SHARED_PAGE_TOKEN_BUDGET,
    max_supporting_per_slice: int = 4,
) -> SharedPayloadManifestV1:
    """Build a deterministic manifest without dropping or sanitizing bytes.

    When a context is supplied, supporting details are split into small
    immutable records before the token check.  Core details remain together in
    the first slice, so an over-budget core page is reported as a blocking
    reason rather than split in a way that could separate its witness atoms.
    """

    budget = int(token_budget)
    if budget <= 0:
        raise ValueError("shared payload page token_budget must be positive")
    if isinstance(view_or_context_or_slices, (MechanismContextViewV1, MechanismContextV1)):
        view = (
            view_or_context_or_slices
            if isinstance(view_or_context_or_slices, MechanismContextViewV1)
            else build_mechanism_context_view(view_or_context_or_slices)
        )
        slices = build_mechanism_context_slices(
            view,
            max_supporting_per_slice=max(1, int(max_supporting_per_slice)),
            max_slices=max(4, len(view.ordered_details) + len(view.exact_evidence) + 1),
        )
    else:
        slices = tuple(view_or_context_or_slices)
        if not slices:
            raise ValueError("shared payload manifest requires at least one slice")

    pages: list[SharedPayloadPageV1] = []
    blocking: list[str] = []
    for index, slice_obj in enumerate(slices):
        payload = _slice_payload(slice_obj)
        estimate = conservative_token_estimate(payload)
        if estimate > budget:
            blocking.append(f"page_over_budget:{index}:{estimate}>{budget}")
        pages.append(SharedPayloadPageV1(
            mechanism_id=str(slice_obj.mechanism_id),
            page_index=index,
            detail_ids=tuple(str(value) for value in slice_obj.detail_ids),
            exact_evidence_ids=tuple(str(value) for value in slice_obj.exact_evidence_ids),
            source_context_digest=str(payload.get("technical_payload", {}).get("source_context_digest", "")),
            view_digest=str(slice_obj.view_digest),
            slice_digest=str(slice_obj.slice_digest),
            token_estimate=estimate,
            token_budget=budget,
            technical_payload=payload,
            technical_bytes_digest=sha256_digest(canonical_json_bytes(payload)),
        ))

    # The page digest is intentionally computed from the exact existing slice
    # record, so this manifest and the legacy I8 serializer describe the same
    # bytes rather than two merely equivalent projections.
    expected_shared_digest = compute_shared_payload_digest(tuple(slices))
    manifest = SharedPayloadManifestV1(
        mechanism_id=str(slices[0].mechanism_id),
        source_context_digest=str(pages[0].source_context_digest),
        view_digest=str(pages[0].view_digest),
        token_budget=budget,
        pages=tuple(pages),
        total_token_estimate=sum(item.token_estimate for item in pages),
        shared_payload_digest=expected_shared_digest,
        blocking_reasons=tuple(dict.fromkeys(blocking)),
    )
    return manifest


def build_shared_payload_delivery_receipt(
    manifest: SharedPayloadManifestV1,
    *,
    consumer_role: Literal["formalizer", "writer"],
    delivered_page_bytes: Sequence[bytes],
    actual_payload_bytes: bytes | None = None,
) -> SharedPayloadDeliveryReceiptV1:
    """Create a receipt after comparing each delivered page's actual bytes."""

    expected = tuple(page.serialized_bytes for page in manifest.pages)
    actual = tuple(bytes(item) for item in delivered_page_bytes)
    if manifest.blocking_reasons:
        return SharedPayloadDeliveryReceiptV1(
            consumer_role=consumer_role,
            mechanism_id=manifest.mechanism_id,
            manifest_digest=manifest.content_digest,
            source_context_digest=manifest.source_context_digest,
            view_digest=manifest.view_digest,
            accepted=False,
            rejection_code=";".join(manifest.blocking_reasons),
        )
    if actual != expected:
        return SharedPayloadDeliveryReceiptV1(
            consumer_role=consumer_role,
            mechanism_id=manifest.mechanism_id,
            manifest_digest=manifest.content_digest,
            source_context_digest=manifest.source_context_digest,
            view_digest=manifest.view_digest,
            accepted=False,
            rejection_code="actual_page_bytes_mismatch",
        )
    payload_bytes = (
        bytes(actual_payload_bytes)
        if actual_payload_bytes is not None
        else canonical_json_bytes([
            json.loads(item.decode("utf-8"))
            for item in actual
        ])
    )
    return SharedPayloadDeliveryReceiptV1(
        consumer_role=consumer_role,
        mechanism_id=manifest.mechanism_id,
        manifest_digest=manifest.content_digest,
        source_context_digest=manifest.source_context_digest,
        view_digest=manifest.view_digest,
        page_indices=tuple(page.page_index for page in manifest.pages),
        page_digests=manifest.page_digests,
        page_bytes_digests=manifest.page_bytes_digests,
        actual_payload_bytes_digest=sha256_digest(payload_bytes),
        accepted=True,
    )


def shared_payload_page_bytes_from_request(
    request: Any,
    *,
    consumer_role: Literal["formalizer", "writer"],
    mechanism_id: str,
) -> tuple[tuple[bytes, ...], bytes]:
    """Extract the technical page bytes from an actual ``LLMRequest``.

    The extraction is deliberately limited to the explicit page envelope used
    by the two production consumers.  It does not reconstruct pages from a
    digest, and it does not inspect the pre-call ``WriterSectionInput``.  This
    makes the resulting receipt evidence about the request handed to the
    caller boundary.
    """

    payload = getattr(request, "input_payload", None)
    if not isinstance(payload, Mapping):
        return (), b""
    if consumer_role == "formalizer":
        raw_pages = payload.get("shared_payload_pages") or ()
    else:
        raw_pages = payload.get("shared_contexts") or ()
        # Mechanism Realizer calls are intentionally one-page calls.  They
        # use the same immutable page bytes under this explicit key rather
        # than routing through the section-level shared-context envelope.
        if not raw_pages and payload.get("shared_page_bytes") is not None:
            raw_pages = (payload.get("shared_page_bytes"),)

    page_bytes: list[bytes] = []
    for raw in raw_pages:
        if isinstance(raw, bytes):
            candidate = bytes(raw)
        elif isinstance(raw, str):
            candidate = raw.encode("utf-8")
        elif isinstance(raw, Mapping):
            candidate = canonical_json_bytes(dict(raw))
        else:
            continue
        try:
            decoded = json.loads(candidate.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(decoded, Mapping):
            continue
        # A page is the canonical slice record itself.  Its nested
        # ``technical_payload`` field contains details/evidence, while the
        # mechanism identity is on the outer record.  Do not accept wrapper
        # or role-specific projections here.
        if not isinstance(decoded.get("technical_payload"), Mapping):
            continue
        if str(decoded.get("mechanism_id") or mechanism_id) != mechanism_id:
            continue
        page_bytes.append(candidate)

    # The full payload digest is calculated from the ordered page records,
    # matching ``serialize_shared_mechanism_payload`` without relying on the
    # caller's self-reported digest.
    actual_payload = canonical_json_bytes([
        json.loads(item.decode("utf-8")) for item in page_bytes
    ]) if page_bytes else b""
    return tuple(page_bytes), actual_payload


def build_request_delivery_receipt(
    manifest: SharedPayloadManifestV1,
    request: Any,
    *,
    consumer_role: Literal["formalizer", "writer"],
) -> SharedPayloadDeliveryReceiptV1:
    """Build a receipt from the bytes present in one real consumer request."""

    delivered, actual_payload = shared_payload_page_bytes_from_request(
        request,
        consumer_role=consumer_role,
        mechanism_id=manifest.mechanism_id,
    )
    return build_shared_payload_delivery_receipt(
        manifest,
        consumer_role=consumer_role,
        delivered_page_bytes=delivered,
        actual_payload_bytes=actual_payload,
    )


__all__ = [
    "DEFAULT_SHARED_PAGE_TOKEN_BUDGET",
    "TOKEN_ESTIMATOR_ID",
    "SharedPayloadPageV1",
    "SharedPayloadManifestV1",
    "SharedPayloadDeliveryReceiptV1",
    "conservative_token_estimate",
    "build_shared_payload_manifest",
    "build_shared_payload_delivery_receipt",
    "shared_payload_page_bytes_from_request",
    "build_request_delivery_receipt",
]
