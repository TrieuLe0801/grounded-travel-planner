"""Secret-safe payload redaction."""

import re
from collections.abc import Mapping
from typing import Any

SECRET_MARKERS = ("api_key", "apikey", "token", "secret", "password", "key")
TOKEN_PATTERN = re.compile(
    r"(?i)(?:sk-|tvly-|bearer\s+)[A-Za-z0-9._-]{8,}|[A-Za-z0-9_-]{32,}"
)


def sanitize_error(error: BaseException | str) -> str:
    """Remove credential-looking values from a bounded error message."""

    return TOKEN_PATTERN.sub("[REDACTED]", str(error))[:300]


def redact_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        lowered = key.lower()
        if any(marker in lowered for marker in SECRET_MARKERS):
            redacted[key] = "[REDACTED]"
        elif isinstance(value, Mapping):
            redacted[key] = redact_mapping(value)
        elif isinstance(value, list):
            redacted[key] = [
                redact_mapping(item) if isinstance(item, Mapping) else item
                for item in value
            ]
        else:
            redacted[key] = (
                TOKEN_PATTERN.sub("[REDACTED]", value)[:500]
                if isinstance(value, str)
                else value
            )
    return redacted
