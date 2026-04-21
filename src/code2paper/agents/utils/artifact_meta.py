import hashlib
import json
import time
from typing import Any, Dict, Optional


def add_meta(data: Any, producer: str, input_obj: Optional[Any] = None, version: str = "v1") -> Any:
    if not isinstance(data, dict):
        return data
    if "meta" in data and isinstance(data.get("meta"), dict) and data["meta"].get("producer"):
        return data
    meta = {
        "version": version,
        "producer": producer,
        "timestamp": time.time(),
    }
    if input_obj is not None:
        meta["input_hash"] = sha1_json(input_obj)
    out = dict(data)
    out["meta"] = meta
    return out


def sha1_json(obj: Any) -> str:
    try:
        payload = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except Exception:
        payload = str(obj).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()

