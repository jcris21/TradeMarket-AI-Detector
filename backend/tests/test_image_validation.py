"""Tests for validate_chart_image utility."""

import base64

import pytest
from fastapi import HTTPException

from app.utils import validate_chart_image

_VALID_PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
_VALID_JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 100


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def test_valid_png_passes():
    result = validate_chart_image(_b64(_VALID_PNG_HEADER))
    assert result[:4] == b"\x89PNG"


def test_valid_jpeg_passes():
    result = validate_chart_image(_b64(_VALID_JPEG_HEADER))
    assert result[:2] == b"\xff\xd8"


def test_oversized_image_rejected():
    oversized = b"\x89PNG" + b"\x00" * (10 * 1024 * 1024 + 1)
    with pytest.raises(HTTPException) as exc_info:
        validate_chart_image(_b64(oversized))
    assert exc_info.value.status_code == 400
    assert "10 MB" in exc_info.value.detail


def test_non_image_bytes_rejected():
    with pytest.raises(HTTPException) as exc_info:
        validate_chart_image(_b64(b"This is not an image"))
    assert exc_info.value.status_code == 400
    assert "PNG or JPEG" in exc_info.value.detail


def test_invalid_base64_rejected():
    with pytest.raises(HTTPException) as exc_info:
        validate_chart_image("not!!!valid===base64###")
    assert exc_info.value.status_code == 400
    assert "base64" in exc_info.value.detail
