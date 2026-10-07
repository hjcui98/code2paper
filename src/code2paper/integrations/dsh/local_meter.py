"""Explicit tokenizer for the isolated fake-service protocol tests.

Each original UTF-8 byte is one token ID. This is the fake service's declared
input model, never a measurement of Qwen or a production provider tokenizer.
"""
from .protocol import ProtocolError

VERSION = "controlled-utf8-byte-id/1"
METER_VERSION = "controlled-utf8-byte-id/1"


def controlled_token_ids(raw: bytes) -> tuple[int,...]:
    raw.decode("utf-8",errors="strict")
    return tuple(raw)


def controlled_measure(raw: bytes) -> int:
    return len(controlled_token_ids(raw))


def bind_controlled_meter(config: dict):
    if config.get("model_kind") != "isolated-fake-service" or config.get("tokenizer_version") != VERSION or config.get("meter_version") != METER_VERSION:
        raise ProtocolError("controlled_tokenizer_scope_mismatch")
    return controlled_measure
