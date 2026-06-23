import asyncio
import pytest
from app.services.storage.local_fs import LocalFSAdapter
from app.services.watchlist.snapshot import SnapshotService
from app.services.watchlist.diff import DiffEngine


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def mock_storage(tmp_path):
    return LocalFSAdapter(root_dir=str(tmp_path))


@pytest.fixture
def snapshot_service(mock_storage):
    return SnapshotService(storage_adapter=mock_storage)


@pytest.fixture
def diff_engine():
    return DiffEngine()


def test_snapshot_take_and_get_latest(snapshot_service):
    target_id = 42
    data = {"confidence": 0.8, "platforms": ["x", "facebook"]}

    # Take snapshot
    snap = _run(snapshot_service.take_snapshot(target_id, data))
    assert snap["target_id"] == target_id
    assert snap["data"] == data
    assert "timestamp" in snap

    # Get latest
    latest = _run(snapshot_service.get_latest(target_id))
    assert latest is not None
    assert latest["target_id"] == target_id
    assert latest["data"] == data
    assert latest["timestamp"] == snap["timestamp"]


def test_snapshot_list_snapshots(snapshot_service):
    target_id = 99
    data1 = {"val": 1}
    data2 = {"val": 2}

    # Take snapshots
    snap1 = _run(snapshot_service.take_snapshot(target_id, data1))
    _run(asyncio.sleep(0.01))
    snap2 = _run(snapshot_service.take_snapshot(target_id, data2))

    snapshots = _run(snapshot_service.list_snapshots(target_id))
    assert len(snapshots) == 2
    assert snapshots[0]["data"] == data1
    assert snapshots[1]["data"] == data2
    assert snapshots[0]["timestamp"] <= snapshots[1]["timestamp"]


def test_diff_no_changes(diff_engine):
    old = {"confidence": 0.8, "platforms": ["x"], "breaches": ["b1"], "temporal_anomaly": False}
    new = {"confidence": 0.8, "platforms": ["x"], "breaches": ["b1"], "temporal_anomaly": False}

    diff = diff_engine.compare(old, new)
    assert len(diff["changes"]) == 0
    assert diff["severity"] == "low"


def test_diff_confidence_delta(diff_engine):
    # No delta change
    old = {"confidence": 0.8}
    new = {"confidence": 0.85}
    diff = diff_engine.compare(old, new)
    assert len(diff["changes"]) == 0

    # Delta change exceeds 0.15 threshold
    new_high = {"confidence": 0.96}
    diff = diff_engine.compare(old, new_high)
    assert len(diff["changes"]) == 1
    assert diff["changes"][0]["type"] == "confidence_delta"
    assert diff["changes"][0]["severity"] == "low"
    assert diff["severity"] == "low"


def test_diff_new_platform(diff_engine):
    old = {"platforms": ["x"]}
    new = {"platforms": ["x", "linkedin"]}
    diff = diff_engine.compare(old, new)

    assert len(diff["changes"]) == 1
    assert diff["changes"][0]["type"] == "new_platform"
    assert diff["changes"][0]["severity"] == "medium"
    assert diff["severity"] == "medium"


def test_diff_new_breach(diff_engine):
    old = {"breaches": ["b1"]}
    new = {"breaches": ["b1", "b2"]}
    diff = diff_engine.compare(old, new)

    assert len(diff["changes"]) == 1
    assert diff["changes"][0]["type"] == "new_breach"
    assert diff["changes"][0]["severity"] == "high"
    assert diff["severity"] == "high"


def test_diff_temporal_anomaly(diff_engine):
    # Test boolean transition
    old = {"temporal_anomaly": False}
    new = {"temporal_anomaly": True}
    diff = diff_engine.compare(old, new)
    assert len(diff["changes"]) == 1
    assert diff["changes"][0]["type"] == "temporal_anomaly"
    assert diff["changes"][0]["severity"] == "high"
    assert diff["severity"] == "high"

    # Test list changes
    old_list = {"temporal_anomalies": ["night_activity"]}
    new_list = {"temporal_anomalies": ["night_activity", "coordinated_creation"]}
    diff_list = diff_engine.compare(old_list, new_list)
    assert len(diff_list["changes"]) == 1
    assert diff_list["changes"][0]["type"] == "temporal_anomaly"
    assert diff_list["severity"] == "high"


def test_diff_severity_escalation(diff_engine):
    # confidence_delta (low) + new_platform (medium) + new_breach (high) -> severity high
    old = {"confidence": 0.8, "platforms": ["x"], "breaches": ["b1"]}
    new = {"confidence": 0.96, "platforms": ["x", "y"], "breaches": ["b1", "b2"]}

    diff = diff_engine.compare(old, new)
    assert len(diff["changes"]) == 3
    assert diff["severity"] == "high"


def test_diff_missing_keys_graceful(diff_engine):
    old = None
    new = {"confidence": 0.9, "platforms": ["x"]}
    diff = diff_engine.compare(old, new)

    assert len(diff["changes"]) == 1
    assert diff["changes"][0]["type"] == "new_platform"
    assert diff["severity"] == "medium"
