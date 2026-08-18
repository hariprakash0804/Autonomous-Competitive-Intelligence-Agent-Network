import pytest
from app.services.scraper import _validate_url


def test_valid_public_urls():
    valid, norm = _validate_url("https://stripe.com")
    assert valid is True
    assert norm == "https://stripe.com"

    valid2, norm2 = _validate_url("linear.app/pricing")
    assert valid2 is True
    assert norm2 == "https://linear.app/pricing"


def test_ssrf_protection_blocks_loopback_and_internal_hosts():
    # Localhost
    valid, err = _validate_url("http://localhost:8000/secret")
    assert valid is False
    assert "SSRF Block" in err

    # 127.0.0.1
    valid, err = _validate_url("http://127.0.0.1:5432")
    assert valid is False
    assert "SSRF Block" in err

    # 0.0.0.0
    valid, err = _validate_url("http://0.0.0.0:80")
    assert valid is False
    assert "SSRF Block" in err

    # IPv6 loopback
    valid, err = _validate_url("http://[::1]:8000")
    assert valid is False
    assert "SSRF Block" in err


def test_unsupported_schemes_blocked():
    valid, err = _validate_url("ftp://ftp.example.com/file")
    assert valid is False
    assert "Unsupported scheme" in err

    valid, err = _validate_url("file:///etc/passwd")
    assert valid is False
    assert "Unsupported scheme" in err
