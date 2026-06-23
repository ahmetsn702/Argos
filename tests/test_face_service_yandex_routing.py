# tests/test_face_service_yandex_routing.py
"""
run_face_search engine routing testi:
- "yandex" → _search_yandex (gerçek Yandex)
- "saucenao" → _search_saucenao (SauceNAO API)
- ["yandex","saucenao"] → ikisi paralel
- SauceNAO backward-compat: eski "yandex" davranışı artık gerçek Yandex'e gidiyor (regression)
"""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


FAKE_BYTES = b"fake_img"
_YANDEX_OK = {"engine": "yandex", "ok": True, "results": [
    {"type": "yandex_site", "url": "https://ex.com/1", "title": "T1"}
], "error": None, "took_ms": 100}
_SAUCENAO_OK = {"engine": "saucenao", "ok": True, "results": [
    {"type": "saucenao", "url": "https://ex.com/2", "title": "T2", "similarity": 85}
], "error": None, "took_ms": 200}


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_local_detect(ok=True, face_count=1):
    return {
        "ok": ok, "face_count": face_count,
        "faces": [{"approximate_age": "25-35", "gender_presentation": "male",
                   "emotion": "neutral", "description": "Test"}],
        "cropped_face_b64": None, "engine": "gemini_vision",
    }


def test_yandex_engine_calls_search_yandex():
    """engines=['yandex'] → _search_yandex çağrılır."""
    mock_yandex = AsyncMock(return_value=_YANDEX_OK)

    with patch("app.services.face_service._detect_faces_local",
               return_value=_mock_local_detect()), \
         patch("app.services.face_service._search_yandex", mock_yandex):
        from app.services.face_service import run_face_search
        result = run(run_face_search(FAKE_BYTES, ["yandex"], 10))

    mock_yandex.assert_awaited_once()
    assert result["engines"].get("yandex") is not None
    assert "saucenao" not in result["engines"]
    print("  ✓ 'yandex' engine → _search_yandex çağrıldı")


def test_saucenao_engine_calls_saucenao():
    """engines=['saucenao'] + SAUCENAO_API_KEY var → _search_saucenao çağrılır."""
    mock_saucenao = AsyncMock(return_value=_SAUCENAO_OK)

    with patch("app.services.face_service._detect_faces_local",
               return_value=_mock_local_detect()), \
         patch("app.services.face_service._search_saucenao", mock_saucenao), \
         patch("app.services.face_service.settings") as mock_settings:
        mock_settings.SAUCENAO_API_KEY = "test_key"
        from app.services.face_service import run_face_search
        result = run(run_face_search(FAKE_BYTES, ["saucenao"], 10))

    mock_saucenao.assert_awaited_once()
    assert "saucenao" in result["engines"]
    assert "yandex" not in result["engines"]
    print("  ✓ 'saucenao' engine → _search_saucenao çağrıldı")


def test_yandex_and_saucenao_both_run():
    """engines=['yandex','saucenao'] → her ikisi de çalışır."""
    mock_yandex = AsyncMock(return_value=_YANDEX_OK)
    mock_saucenao = AsyncMock(return_value=_SAUCENAO_OK)

    with patch("app.services.face_service._detect_faces_local",
               return_value=_mock_local_detect()), \
         patch("app.services.face_service._search_yandex", mock_yandex), \
         patch("app.services.face_service._search_saucenao", mock_saucenao), \
         patch("app.services.face_service.settings") as mock_settings:
        mock_settings.SAUCENAO_API_KEY = "test_key"
        from app.services.face_service import run_face_search
        result = run(run_face_search(FAKE_BYTES, ["yandex", "saucenao"], 10))

    mock_yandex.assert_awaited_once()
    mock_saucenao.assert_awaited_once()
    assert "yandex" in result["engines"]
    assert "saucenao" in result["engines"]
    assert result["match_count"] == 2  # 1 yandex + 1 saucenao URL
    print("  ✓ 'yandex'+'saucenao' → ikisi paralel çalıştı, 2 match")


def test_yandex_not_called_without_engine():
    """engines=['google_vision'] → _search_yandex hiç çağrılmaz."""
    mock_yandex = AsyncMock(return_value=_YANDEX_OK)
    mock_gv = AsyncMock(return_value={
        "engine": "google_vision", "ok": True, "results": [],
        "entities": [], "face_count": 0, "face_emotions": [],
        "best_guess": [], "error": None, "took_ms": 50,
    })

    with patch("app.services.face_service._detect_faces_local",
               return_value=_mock_local_detect()), \
         patch("app.services.face_service._search_yandex", mock_yandex), \
         patch("app.services.face_service._search_google_vision", mock_gv):
        from app.services.face_service import run_face_search
        run(run_face_search(FAKE_BYTES, ["google_vision"], 10))

    mock_yandex.assert_not_awaited()
    print("  ✓ 'google_vision' only → _search_yandex çağrılmadı")


if __name__ == "__main__":
    tests = [
        test_yandex_engine_calls_search_yandex,
        test_saucenao_engine_calls_saucenao,
        test_yandex_and_saucenao_both_run,
        test_yandex_not_called_without_engine,
    ]
    failures = []
    print(f"\n{'='*55}\n face_service Yandex routing — {len(tests)} test\n{'='*55}")
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
        except Exception as e:
            import traceback
            print(f"  ✗ {t.__name__}: {e}")
            traceback.print_exc()
            failures.append(t.__name__)
    print(f"\n{'='*55}")
    if failures:
        print(f" BAŞARISIZ: {failures}")
        sys.exit(1)
    print(" TÜM TESTLER GEÇTİ ✓")
    print("="*55)
