"""Tests for validate_source_url SSRF protection."""

import pytest
from fastapi import HTTPException

from app.utils import validate_source_url


def test_valid_https_url_passes():
    validate_source_url("https://finance.yahoo.com/chart/AAPL")


def test_http_url_rejected():
    with pytest.raises(HTTPException) as exc_info:
        validate_source_url("http://example.com/chart")
    assert exc_info.value.status_code == 400
    assert "https" in exc_info.value.detail


def test_localhost_rejected():
    with pytest.raises(HTTPException) as exc_info:
        validate_source_url("https://localhost/chart")
    assert exc_info.value.status_code == 400
    assert "disallowed" in exc_info.value.detail


def test_loopback_ip_rejected():
    with pytest.raises(HTTPException) as exc_info:
        validate_source_url("https://127.0.0.1/chart")
    assert exc_info.value.status_code == 400


def test_private_class_c_rejected():
    with pytest.raises(HTTPException) as exc_info:
        validate_source_url("https://192.168.1.1/chart")
    assert exc_info.value.status_code == 400


def test_private_class_a_rejected():
    with pytest.raises(HTTPException) as exc_info:
        validate_source_url("https://10.0.0.1/chart")
    assert exc_info.value.status_code == 400


def test_link_local_rejected():
    with pytest.raises(HTTPException) as exc_info:
        validate_source_url("https://169.254.1.1/chart")
    assert exc_info.value.status_code == 400
