"""Shared utility functions for the FinAlly backend."""

import base64
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

_SSRF_BLOCKLIST = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "169.254.",
    "10.",
    "192.168.",
    "172.16.",
    "::1",
]

_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_source_url(url: str) -> None:
    """Raise HTTP 400 if url is non-HTTPS or targets a private/internal address."""
    if not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="source_url must use https")
    for blocked in _SSRF_BLOCKLIST:
        if blocked in url:
            raise HTTPException(status_code=400, detail="source_url targets a disallowed host")


def validate_chart_image(b64_str: str) -> bytes:
    """Decode and validate a base64 chart image. Returns raw bytes.

    Raises HTTP 400 for invalid base64, oversized images, or non-PNG/JPEG content.
    """
    try:
        raw = base64.b64decode(b64_str, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="chart_image is not valid base64")
    if len(raw) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="chart_image exceeds maximum size of 10 MB")
    if raw[:4] == b"\x89PNG" or raw[:2] == b"\xff\xd8":
        return raw
    raise HTTPException(status_code=400, detail="chart_image must be PNG or JPEG")


def trading_days_from_now(n: int) -> datetime:
    """Return UTC datetime that is n trading days (Mon–Fri) from now."""
    current = datetime.now(timezone.utc)
    remaining = n
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon=0 … Fri=4
            remaining -= 1
    return current
