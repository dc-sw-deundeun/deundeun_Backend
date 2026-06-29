import hashlib
import hmac
import json


def compute_analysis_signature(payload: dict | str, secret: str) -> str:
    if isinstance(payload, str):
        body = payload
    else:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_analysis_signature(body: str, secret: str, signature: str | None) -> bool:
    if not signature or not secret:
        return False
    expected = compute_analysis_signature(body, secret)
    return hmac.compare_digest(expected, signature)
