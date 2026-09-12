"""Provider-independent input accounting, without silently trimming evidence."""
import json


def input_token_upper_bound(prompt, payload, schema=None):
    # UTF-8 byte count is an upper bound for byte-tokenizing providers. This
    # deliberately does not pretend that chars/4 is exact for code or CJK.
    parts = [prompt, json.dumps(payload, ensure_ascii=False, default=str)]
    if schema:
        parts.append(json.dumps(schema, ensure_ascii=False, default=str))
    return len("\n".join(parts).encode("utf-8")) + 64


def request_budget_failure(config, request):
    limit = getattr(config, "max_input_tokens", None) or 98_304
    upper = input_token_upper_bound(request.prompt, request.input_payload, request.response_json_schema)
    if upper > limit:
        return f"input_budget_exhausted:upper_bound={upper}:limit={limit}:estimator=utf8_bytes"
    return ""
