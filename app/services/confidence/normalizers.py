# app/services/confidence/normalizers.py
"""Type-specific normalizers and canonical_id dispatcher."""

import ipaddress
import re

from app.models.confidence import FindingType

_TR_FOLD = str.maketrans(
    "İıŞşĞğÜüÖöÇç",
    "iissggüuöocç".translate(str.maketrans("üöc", "uoc")),
)
# Build the TR fold table cleanly
_TR_FOLD = str.maketrans(
    "İıŞşĞğÜüÖöÇç",
    "iissgguuooccç"[:-1],  # fallback — do it explicitly
)
_TR_FOLD = {
    ord("İ"): "i", ord("ı"): "i",
    ord("Ş"): "s", ord("ş"): "s",
    ord("Ğ"): "g", ord("ğ"): "g",
    ord("Ü"): "u", ord("ü"): "u",
    ord("Ö"): "o", ord("ö"): "o",
    ord("Ç"): "c", ord("ç"): "c",
}

_GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}

# Country prefix map for common cases when 0XXX format used
_COUNTRY_PREFIXES = {"TR": "90"}


def normalize_email(raw: str) -> str:
    raw = raw.strip().lower()
    if "@" not in raw:
        return raw
    local, domain = raw.rsplit("@", 1)
    if domain in _GMAIL_DOMAINS:
        local = local.split("+")[0]   # plus stripping
        local = local.replace(".", "")  # dot stripping
    return f"{local}@{domain}"


def normalize_phone(raw: str, default_country: str = "TR") -> str:
    digits = re.sub(r"\D", "", raw)
    # Already E.164 (starts with +)
    if raw.strip().startswith("+"):
        return "+" + digits
    # Local format starting with 0 (e.g. 0555...)
    if digits.startswith("0") and default_country in _COUNTRY_PREFIXES:
        return "+" + _COUNTRY_PREFIXES[default_country] + digits[1:]
    return "+" + digits


def normalize_username(raw: str) -> str:
    return raw.lstrip("@").lower()


def normalize_name(raw: str) -> str:
    folded = raw.translate(_TR_FOLD).lower()
    tokens = sorted(folded.split())
    return " ".join(tokens)


def normalize_ip(raw: str) -> str:
    try:
        return str(ipaddress.ip_address(raw.strip()))
    except ValueError:
        return raw.strip().lower()


def normalize_domain(raw: str) -> str:
    return raw.strip().lower().rstrip(".")


def normalize_location(lat: float, lng: float) -> str:
    return f"lat:{lat:.4f},lng:{lng:.4f}"


def canonical_id(type: FindingType, value: str) -> str:
    dispatch = {
        FindingType.EMAIL: normalize_email,
        FindingType.PHONE: normalize_phone,
        FindingType.USERNAME: normalize_username,
        FindingType.NAME: normalize_name,
        FindingType.IP: normalize_ip,
        FindingType.DOMAIN: normalize_domain,
        FindingType.LOCATION: lambda v: v,  # already canonical format
    }
    normalized = dispatch[type](value)
    return f"{type.value}:{normalized}"
