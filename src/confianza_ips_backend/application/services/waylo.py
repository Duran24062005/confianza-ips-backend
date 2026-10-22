from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timezone


def normalize_name(value: str) -> str:
    return " ".join(value.casefold().split())


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def _secret_bytes(secret: str) -> bytes:
    padded = secret.strip().upper() + "=" * (-len(secret.strip()) % 8)
    return base64.b32decode(padded, casefold=True)


def _counter(at: datetime, interval_seconds: int) -> int:
    return max(0, int(at.timestamp()) // interval_seconds)


def _code_for_counter(secret: str, counter: int) -> str:
    digest = hmac.new(
        _secret_bytes(secret), counter.to_bytes(8, byteorder="big"), hashlib.sha1
    ).digest()
    offset = digest[-1] & 0x0F
    number = int.from_bytes(digest[offset : offset + 4], byteorder="big") & 0x7FFFFFFF
    return f"{number % 1_000_000:06d}"


def current_totp(secret: str, interval_seconds: int, at: datetime | None = None) -> str:
    moment = at or datetime.now(timezone.utc)
    return _code_for_counter(secret, _counter(moment, interval_seconds))


def totp_expiry(interval_seconds: int, at: datetime | None = None) -> datetime:
    moment = at or datetime.now(timezone.utc)
    next_boundary = (_counter(moment, interval_seconds) + 1) * interval_seconds
    return datetime.fromtimestamp(next_boundary, tz=timezone.utc)


def verify_totp(
    secret: str,
    code: str,
    interval_seconds: int,
    at: datetime | None = None,
    window: int = 1,
) -> bool:
    moment = at or datetime.now(timezone.utc)
    current_counter = _counter(moment, interval_seconds)
    return any(
        hmac.compare_digest(_code_for_counter(secret, current_counter + offset), code)
        for offset in range(-window, window + 1)
        if current_counter + offset >= 0
    )
