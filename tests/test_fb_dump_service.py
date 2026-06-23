# tests/test_fb_dump_service.py
import asyncio, io, json, os, zipfile
from unittest.mock import MagicMock, patch
from app.services.fb_dump_service import FbDumpService


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _mock_proc(returncode=0, stdout="", stderr=""):
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


def test_run_dump_success():
    """subprocess exit 0 → ok=True dict."""
    svc = FbDumpService()
    with patch("subprocess.run", return_value=_mock_proc(0, '{"saved":3}')):
        with patch("pathlib.Path.mkdir"):
            result = _run(svc.run_dump("testuser", limit=5))
    assert result["ok"] is True
    assert result["returncode"] == 0
    assert "outdir" in result


def test_run_dump_failure():
    """subprocess exit non-0 → ok=False dict."""
    svc = FbDumpService()
    with patch("subprocess.run", return_value=_mock_proc(1, "", "error")):
        with patch("pathlib.Path.mkdir"):
            result = _run(svc.run_dump("testuser"))
    assert result["ok"] is False
    assert result["returncode"] == 1


def test_run_dump_timeout():
    """subprocess.TimeoutExpired → error dict with ok=False."""
    import subprocess
    svc = FbDumpService()
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 300)):
        with patch("pathlib.Path.mkdir"):
            result = _run(svc.run_dump("testuser"))
    assert result["ok"] is False
    assert result.get("error") == "timeout"


def test_build_zip():
    """build_zip with real temp dir → returns zip bytes."""
    import tempfile
    svc = FbDumpService()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a fake image file
        img_path = os.path.join(tmpdir, "test.jpg")
        with open(img_path, "wb") as f:
            f.write(b"\xff\xd8\xff" + b"x" * 100)
        result = _run(svc.build_zip(tmpdir))
    assert isinstance(result, bytes)
    with zipfile.ZipFile(io.BytesIO(result)) as z:
        names = z.namelist()
    assert "test.jpg" in names
