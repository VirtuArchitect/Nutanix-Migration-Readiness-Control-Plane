from __future__ import annotations

import re
from typing import Any


SECRET_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "credential",
    "credentials",
    "authorization",
}

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
URL_RE = re.compile(r"https?://[^\s)>\"]+")
HOST_RE = re.compile(r"\b[a-zA-Z0-9][a-zA-Z0-9-]{1,62}\.(?:local|lan|corp|internal|com|net|org)\b")


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return redact_dict(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        redacted = URL_RE.sub("[REDACTED_URL]", value)
        redacted = EMAIL_RE.sub("[REDACTED_EMAIL]", redacted)
        redacted = IP_RE.sub("[REDACTED_IP]", redacted)
        redacted = HOST_RE.sub("[REDACTED_HOST]", redacted)
        return redacted
    return value


def redact_dict(payload: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in SECRET_KEYS or any(secret in key.lower() for secret in SECRET_KEYS):
            redacted[key] = "[REDACTED_SECRET]"
        else:
            redacted[key] = redact_value(value)
    return redacted
