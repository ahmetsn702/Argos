# tests/test_confidence_weights.py
"""Tests for app/services/confidence/weights.py"""

from app.services.confidence.weights import (
    DEFAULT_SOURCE_WEIGHTS,
    get_weight,
    load_weights,
)


def test_default_weight_darkweb():
    assert get_weight("darkweb_hibp") == 0.90


def test_default_weight_phone():
    assert get_weight("phone_verified") == 0.85


def test_default_weight_fallback():
    assert get_weight("bilinmeyen_kaynak") == 0.50


def test_default_weights_complete():
    w = load_weights()
    for key in DEFAULT_SOURCE_WEIGHTS:
        assert key in w


def test_env_override_valid(monkeypatch):
    monkeypatch.setenv("CONFIDENCE_WEIGHT_OVERRIDES",
                       "darkweb_hibp=0.92,ai_gemini=0.30")
    weights = load_weights()
    assert weights["darkweb_hibp"] == 0.92
    assert weights["ai_gemini"] == 0.30
    assert weights["phone_verified"] == 0.85  # değişmedi


def test_env_override_invalid_skipped(monkeypatch):
    monkeypatch.setenv("CONFIDENCE_WEIGHT_OVERRIDES",
                       "darkweb_hibp=abc,phone_verified=0.80")
    weights = load_weights()
    assert weights["darkweb_hibp"] == 0.90   # "abc" geçersiz → skip
    assert weights["phone_verified"] == 0.80  # geçerli override uygulandı


def test_env_override_out_of_range_skipped(monkeypatch):
    monkeypatch.setenv("CONFIDENCE_WEIGHT_OVERRIDES",
                       "darkweb_hibp=1.5,ai_gemini=0.30")
    weights = load_weights()
    assert weights["darkweb_hibp"] == 0.90   # 1.5 aralık dışı → skip
    assert weights["ai_gemini"] == 0.30


def test_get_weight_with_custom_dict():
    custom = {"my_source": 0.77}
    assert get_weight("my_source", custom) == 0.77
    assert get_weight("unknown", custom) == 0.50
