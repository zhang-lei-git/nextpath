import base64
import binascii
import hashlib
import hmac
import json
import time

from fastapi import HTTPException


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_token(payload: dict, secret: str, ttl_seconds: int) -> str:
    body = {**payload, "exp": int(time.time()) + ttl_seconds}
    encoded = _encode(json.dumps(body, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))
    signature = _encode(hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def verify_token(token: str, secret: str, *, expected_type: str) -> dict:
    try:
        encoded, signature = token.split(".", 1)
        expected = _encode(hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid signature")
        payload = json.loads(_decode(encoded))
        if payload.get("type") != expected_type or int(payload["exp"]) < int(time.time()):
            raise ValueError("expired or wrong token type")
        return payload
    except (ValueError, KeyError, TypeError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="登录状态已失效，请重新进入小程序") from exc
