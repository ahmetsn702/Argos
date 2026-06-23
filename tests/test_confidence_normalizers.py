# tests/test_confidence_normalizers.py
"""Tests for app/services/confidence/normalizers.py"""

import pytest

from app.models.confidence import FindingType
from app.services.confidence.normalizers import (
    canonical_id,
    normalize_domain,
    normalize_email,
    normalize_ip,
    normalize_location,
    normalize_name,
    normalize_phone,
    normalize_username,
)


def test_email_lowercase():
    assert normalize_email("TEST@EXAMPLE.COM") == "test@example.com"


def test_email_gmail_dot_strip():
    assert normalize_email("a.h.met@gmail.com") == "ahmet@gmail.com"


def test_email_gmail_plus_strip():
    assert normalize_email("ahmet+spam@gmail.com") == "ahmet@gmail.com"


def test_email_gmail_dot_and_plus():
    assert normalize_email("a.h.met+spam@gmail.com") == "ahmet@gmail.com"


def test_email_non_gmail_unchanged():
    assert normalize_email("test@outlook.com") == "test@outlook.com"


def test_email_non_gmail_no_dot_strip():
    assert normalize_email("first.last@outlook.com") == "first.last@outlook.com"


def test_phone_e164_tr():
    assert normalize_phone("0555 123 4567") == "+905551234567"


def test_phone_already_e164():
    assert normalize_phone("+905551234567") == "+905551234567"


def test_phone_international():
    assert normalize_phone("+1 555 123 4567") == "+15551234567"


def test_phone_tr_with_dashes():
    assert normalize_phone("0555-123-4567") == "+905551234567"


def test_username_at_strip():
    assert normalize_username("@AhmetX") == "ahmetx"


def test_username_lowercase():
    assert normalize_username("AhmetX") == "ahmetx"


def test_name_tr_fold():
    assert normalize_name("İsmail") == "ismail"


def test_name_token_sort():
    result = normalize_name("Yılmaz İsmail")
    assert result == "ismail yilmaz"


def test_name_tr_chars():
    assert normalize_name("Şükrü Öztürk") == "ozturk sukru"


def test_ip_v4_canonical():
    assert normalize_ip("192.168.1.1") == "192.168.1.1"


def test_ip_v6_canonical():
    # Python's ipaddress gives compressed form for ::1
    result = normalize_ip("::1")
    assert result == "::1"


def test_ip_v6_full_form():
    result = normalize_ip("0000:0000:0000:0000:0000:0000:0000:0001")
    assert result == "::1"


def test_domain_trailing_dot():
    assert normalize_domain("example.com.") == "example.com"


def test_domain_lowercase():
    assert normalize_domain("EXAMPLE.COM") == "example.com"


def test_location_canonical():
    result = normalize_location(38.67001, 39.22001)
    assert result == "lat:38.6700,lng:39.2200"


def test_location_rounding():
    result = normalize_location(1.23456789, 9.87654321)
    assert result == "lat:1.2346,lng:9.8765"


def test_canonical_id_format():
    result = canonical_id(FindingType.EMAIL, "Ahmet@Gmail.com")
    assert result == "email:ahmet@gmail.com"


def test_canonical_id_phone():
    result = canonical_id(FindingType.PHONE, "0555 123 4567")
    assert result == "phone:+905551234567"


def test_canonical_id_username():
    result = canonical_id(FindingType.USERNAME, "@TestUser")
    assert result == "username:testuser"


def test_canonical_id_domain():
    result = canonical_id(FindingType.DOMAIN, "EXAMPLE.COM.")
    assert result == "domain:example.com"
