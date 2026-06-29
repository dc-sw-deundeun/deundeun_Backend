import hashlib
import hmac
import json


def _to_body_bytes(payload: dict | str | bytes) -> bytes:
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def compute_analysis_signature(payload: dict | str | bytes, secret: str) -> str:
    body = _to_body_bytes(payload)
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_analysis_signature(body: dict | str | bytes, secret: str, signature: str | None) -> bool:
    if not signature or not secret:
        return False
    expected = compute_analysis_signature(body, secret)
    return hmac.compare_digest(expected, signature)
