import hashlib
import re

from fastapi import Header, HTTPException, status

from triage.config import get_settings

INJECTION_PATTERNS = (
    r"ignore (all|any|the) previous instructions",
    r"reveal (the )?(system|developer) prompt",
    r"print (your )?secrets?",
    r"bypass (the )?(rules|guardrails)",
)


def redact_sensitive_values(text: str) -> tuple[str, list[str]]:
    """Remove actual contact and payment identifiers before model inference."""
    flags: list[str] = []
    patterns = {
        # Detect card-like values before the broader phone expression can consume them.
        "card_number": r"\b(?:\d[ -]*?){13,19}\b",
        "email_address": r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "phone_number": r"(?<!\d)(?:\+?\d[\d .()-]{7,}\d)(?!\d)",
    }
    redacted = text
    for label, pattern in patterns.items():
        updated, count = re.subn(
            pattern, f"[{label.upper()}_REDACTED]", redacted, flags=re.IGNORECASE
        )
        if count:
            flags.append(label)
            redacted = updated
    return redacted, flags


def detect_prompt_injection(text: str) -> bool:
    """Detect common direct injection attempts in untrusted client text."""
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in INJECTION_PATTERNS)


def fingerprint(value: str) -> str:
    """Hash identifiers before using them in logs or rate-limit keys."""
    return hashlib.sha256(value.encode()).hexdigest()[:16]


async def require_api_key(x_api_key: str = Header(default="")) -> str:
    """Authenticate API requests without exposing configured keys."""
    if x_api_key not in get_settings().accepted_api_keys:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return fingerprint(x_api_key)
