# tests/test_smart_bar_ui.py
"""HTML token tests for the smart bar (H5) in ui/mini_panel.html.

These don't run a browser; they just confirm the smart bar markup and
the detection/dispatch JavaScript helpers are present in the served
HTML. Browser-level interaction is left to the playwright smoke
suite (`tests/ui_smoke_test.py`) which boots a real server.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_smart_bar_present_in_html():
    r = client.get("/mini")
    assert r.status_code == 200
    html = r.text
    for token in (
        'id="smart-bar"',
        'id="sb-text"',
        'id="sb-file"',
        'id="sb-go"',
        'id="sb-indicator"',
        'id="sb-file-btn"',
    ):
        assert token in html, f"missing {token} in /mini HTML"


def test_smart_bar_detect_function_present():
    r = client.get("/mini")
    html = r.text
    assert "function detectInputType" in html
    assert "updateSbIndicator" in html
    assert "initSmartBar" in html


def test_smart_bar_type_label_map_present():
    """Indicator label map covers all 6 detected types."""
    r = client.get("/mini")
    html = r.text
    assert "SB_TYPE_LABEL" in html
    for label in ("email", "phone", "domain", "image", "ambiguous_text", "empty"):
        assert label in html, f"missing label {label} in SB_TYPE_LABEL map"


def test_smart_bar_css_block_present():
    r = client.get("/mini")
    html = r.text
    assert "#smart-bar{" in html
    assert ".sb-source-badge" in html


def test_smart_bar_dispatch_functions_present():
    """Task 6: dispatch + modal helpers."""
    r = client.get("/mini")
    html = r.text
    for token in (
        "function dispatchToCard",
        "function activateCard",
        "function setInputAuditFlag",
        "function openModal",
        "function closeModal",
        "initSmartBarDispatch",
    ):
        assert token in html, f"missing {token}"


def test_smart_bar_modal_choices_present():
    """Task 6: modal HTML and the 4 choice buttons."""
    r = client.get("/mini")
    html = r.text
    assert 'id="sb-modal"' in html
    assert 'id="sb-modal-value"' in html
    for choice in ("name", "username", "domain", "cancel"):
        assert f'data-sb-choice="{choice}"' in html, f"missing modal choice {choice}"


def test_smart_bar_dispatch_targets_match_known_cards():
    """The dispatch table should reference cards/inputs that actually exist
    in the panel — guards against typos like #ms-email vs #mosint-email."""
    r = client.get("/mini")
    html = r.text
    # dispatch invocations
    assert "dispatchToCard('card-mosint'" in html
    assert "dispatchToCard('card-phone'" in html
    assert "dispatchToCard('card-domain'" in html
    assert "dispatchToCard('card-face'" in html
    assert "dispatchToCard('card-unified'" in html
    assert "dispatchToCard('card-bios'" in html
    # corresponding inputs/buttons must exist as elements
    for input_id in ('ms-email', 'phone-num', 'dm-target', 'face-file', 'uni-fname', 'uni-lname', 'bios-user'):
        assert f'id="{input_id}"' in html, f"dispatch references missing #{input_id}"
    for btn_id in ('ms-btn', 'phone-btn', 'dm-btn', 'bios-btn'):
        assert f'id="{btn_id}"' in html, f"dispatch references missing button #{btn_id}"
