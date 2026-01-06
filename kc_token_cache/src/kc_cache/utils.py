from __future__ import annotations
import base64
import json
import time
from typing import Any, Dict

def now_ts() -> int:
    return int(time.time())

def decode_jwt_payload(token: str) -> Dict[str, Any]:
    """
    Decode JWT payload (second segment) using base64 url-safe decoding with padding fix.
    Does NOT verify signature; intended only to read claims like exp.
    """
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Invalid JWT: not enough segments")
    b64 = parts[1]
    # url-safe -> standard base64
    b64 = b64.replace("-", "+").replace("_", "/")
    # pad
    padding = (-len(b64)) % 4
    if padding:
        b64 += "=" * padding
    data = base64.b64decode(b64)
    return json.loads(data)