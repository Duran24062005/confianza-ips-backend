from __future__ import annotations

import hashlib
import hmac
import secrets


def normalize_identity(value: str) -> str:
    return " ".join(value.casefold().split())


def generate_activation_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def activation_digest(code: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"), code.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def verify_activation_code(code: str, digest: str, secret: str) -> bool:
    return hmac.compare_digest(activation_digest(code, secret), digest)
