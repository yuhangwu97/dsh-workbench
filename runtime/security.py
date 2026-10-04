"""Small dependency-free JWT and role helpers for the reference service."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


def _decode_segment(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def verify_hs256(token: str, secret: str, *, issuer: str = "") -> dict[str, Any] | None:
    parts = token.split(".")
    if len(parts) != 3 or not secret:
        return None
    try:
        header = json.loads(_decode_segment(parts[0]))
        claims = json.loads(_decode_segment(parts[1]))
        if header.get("alg") != "HS256":
            return None
        expected = hmac.new(secret.encode(), f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).digest()
        supplied = _decode_segment(parts[2])
        if not hmac.compare_digest(expected, supplied):
            return None
        if claims.get("exp") is not None and int(claims["exp"]) < int(time.time()):
            return None
        if issuer and claims.get("iss") != issuer:
            return None
        return claims
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def roles_from_claims(claims: dict[str, Any]) -> set[str]:
    roles = claims.get("roles", claims.get("role", []))
    if isinstance(roles, str):
        roles = roles.split()
    return {str(item) for item in roles if str(item)} if isinstance(roles, list) else set()
