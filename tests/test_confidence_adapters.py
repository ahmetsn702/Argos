# tests/test_confidence_adapters.py
"""Tests for app/services/confidence/adapters.py"""

from app.models.confidence import FindingType, SourceKind
from app.services.confidence.adapters import (
    ai_to_findings,
    bios_to_findings,
    darkweb_to_findings,
    domain_to_findings,
    mosint_to_findings,
    phone_to_findings,
)


def test_mosint_empty_payload():
    assert mosint_to_findings({}) == []


def test_mosint_email_finding():
    payload = {"email": "ahmet@gmail.com"}
    findings = mosint_to_findings(payload)
    emails = [f for f in findings if f.type == FindingType.EMAIL]
    assert len(emails) == 1
    assert emails[0].value == "ahmet@gmail.com"


def test_mosint_breach_upgrades_source_kind():
    payload = {
        "email": "ahmet@gmail.com",
        "breaches": ["Adobe", "LinkedIn"],
    }
    findings = mosint_to_findings(payload)
    emails = [f for f in findings if f.type == FindingType.EMAIL]
    assert emails[0].sources[0].source_kind == SourceKind.BREACH


def test_mosint_social_produces_username():
    payload = {
        "email": "ahmet@gmail.com",
        "social": {
            "instagram": "https://instagram.com/ahmet",
            "twitter": "",  # boş → atla
        },
    }
    findings = mosint_to_findings(payload)
    usernames = [f for f in findings if f.type == FindingType.USERNAME]
    assert len(usernames) >= 1


def test_mosint_no_breach_uses_scraping_kind():
    payload = {"email": "ahmet@gmail.com", "breaches": []}
    findings = mosint_to_findings(payload)
    emails = [f for f in findings if f.type == FindingType.EMAIL]
    assert emails[0].sources[0].source_kind == SourceKind.SCRAPING


def test_darkweb_not_found():
    payload = {"email": "x@y.com", "found": False, "breaches": []}
    assert darkweb_to_findings(payload) == []


def test_darkweb_found_produces_email():
    payload = {
        "email": "x@y.com",
        "found": True,
        "breaches": [{"name": "Adobe"}],
    }
    findings = darkweb_to_findings(payload)
    assert len(findings) == 1
    assert findings[0].type == FindingType.EMAIL
    assert findings[0].sources[0].source_kind == SourceKind.BREACH
    assert findings[0].sources[0].weight == 0.90


def test_darkweb_missing_email():
    assert darkweb_to_findings({"found": True}) == []


def test_bios_empty_results():
    payload = {"username": "ahmetx", "results": []}
    assert bios_to_findings(payload) == []


def test_bios_exists_produces_username():
    payload = {
        "username": "ahmetx",
        "results": [
            {"platform": "instagram", "status": "exists",
             "display_name": "Ahmet", "url": "..."},
        ],
    }
    findings = bios_to_findings(payload)
    usernames = [f for f in findings if f.type == FindingType.USERNAME]
    assert len(usernames) >= 1


def test_bios_display_name_produces_name():
    payload = {
        "username": "ahmetx",
        "results": [
            {"platform": "instagram", "status": "exists",
             "display_name": "Ahmet Sayın", "url": "..."},
        ],
    }
    findings = bios_to_findings(payload)
    names = [f for f in findings if f.type == FindingType.NAME]
    assert len(names) >= 1


def test_bios_not_found_skipped():
    payload = {
        "username": "ahmetx",
        "results": [
            {"platform": "instagram", "status": "not_found",
             "display_name": "", "url": ""},
        ],
    }
    findings = bios_to_findings(payload)
    usernames = [f for f in findings if f.type == FindingType.USERNAME]
    assert len(usernames) == 0


def test_phone_valid_produces_phone_verified():
    payload = {"phone": "+905551234567", "valid": True, "country_code": "TR"}
    findings = phone_to_findings(payload)
    assert len(findings) == 1
    assert findings[0].type == FindingType.PHONE
    assert findings[0].sources[0].source_kind == SourceKind.PHONE_VERIFIED


def test_phone_invalid_produces_scraping_kind():
    payload = {"phone": "+905551234567", "valid": False}
    findings = phone_to_findings(payload)
    assert findings[0].sources[0].source_kind == SourceKind.SCRAPING


def test_domain_produces_domain_and_email():
    payload = {
        "domain": "example.com",
        "registrant_email": "admin@example.com",
        "registrant_name": "",
        "ips": [],
    }
    findings = domain_to_findings(payload)
    types = {f.type for f in findings}
    assert FindingType.DOMAIN in types
    assert FindingType.EMAIL in types


def test_domain_ip_produces_ip_finding():
    payload = {"domain": "example.com", "ips": ["1.2.3.4"]}
    findings = domain_to_findings(payload)
    ips = [f for f in findings if f.type == FindingType.IP]
    assert len(ips) >= 1


def test_ai_location_produces_finding():
    payload = {
        "lat": 38.67,
        "lng": 39.22,
        "estimated_country": "Turkey",
        "estimated_region": "Elazığ",
        "confidence": 0.75,
    }
    findings = ai_to_findings(payload)
    assert len(findings) == 1
    assert findings[0].type == FindingType.LOCATION
    assert findings[0].sources[0].weight == 0.35


def test_ai_missing_lat_returns_empty():
    assert ai_to_findings({"lng": 39.22}) == []
