import asyncio
import os
import pytest
from app.services.storage.local_fs import LocalFSAdapter
from app.services.storage.s3 import S3Adapter
from app.services.storage.factory import get_adapter


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_local_fs_adapter_basic_ops(tmp_path):
    adapter = LocalFSAdapter(root_dir=str(tmp_path))

    # Save
    uri = _run(adapter.save("test.txt", b"hello world"))
    assert uri == "local://test.txt"
    assert (tmp_path / "test.txt").read_bytes() == b"hello world"

    # Load
    content = _run(adapter.load("test.txt"))
    assert content == b"hello world"

    # List
    files = _run(adapter.list())
    assert files == ["local://test.txt"]

    # Delete
    _run(adapter.delete("test.txt"))
    assert not (tmp_path / "test.txt").exists()

    # Error checking
    with pytest.raises(FileNotFoundError):
        _run(adapter.load("test.txt"))

    with pytest.raises(FileNotFoundError):
        _run(adapter.delete("test.txt"))


def test_local_fs_adapter_path_traversal(tmp_path):
    adapter = LocalFSAdapter(root_dir=str(tmp_path))

    with pytest.raises(ValueError):
        _run(adapter.save("../escaped.txt", b"hello"))

    with pytest.raises(ValueError):
        _run(adapter.load("../escaped.txt"))

    with pytest.raises(ValueError):
        _run(adapter.delete("../escaped.txt"))

    with pytest.raises(ValueError):
        _run(adapter.list("../escaped"))


def test_s3_adapter_not_implemented():
    adapter = S3Adapter()

    with pytest.raises(NotImplementedError):
        _run(adapter.save("test.txt", b"hello"))

    with pytest.raises(NotImplementedError):
        _run(adapter.load("test.txt"))

    with pytest.raises(NotImplementedError):
        _run(adapter.delete("test.txt"))

    with pytest.raises(NotImplementedError):
        _run(adapter.list())


def test_storage_factory(monkeypatch):
    # Test setting backend via function arg
    local_adapter = get_adapter("local")
    assert isinstance(local_adapter, LocalFSAdapter)

    s3_adapter = get_adapter("s3")
    assert isinstance(s3_adapter, S3Adapter)

    with pytest.raises(ValueError):
        get_adapter("invalid_backend")

    # Test singleton caching
    assert get_adapter("local") is local_adapter
    assert get_adapter("s3") is s3_adapter

    # Test env override
    monkeypatch.setenv("ARCHIVE_BACKEND", "s3")
    assert get_adapter() is s3_adapter
