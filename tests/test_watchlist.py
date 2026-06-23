import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.routers.watchlist import get_repo
from app.repositories.watchlist_repo import WatchlistRepository
import app.routers.watchlist as watchlist_mod


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_watchlist.db"
    repo = WatchlistRepository(db_path=str(db_file))

    async def _override_get_repo():
        await repo.init_db()
        return repo

    app.dependency_overrides[get_repo] = _override_get_repo
    yield repo
    app.dependency_overrides.pop(get_repo, None)


@pytest.fixture
def client():
    return TestClient(app)


def test_watchlist_disabled(client, monkeypatch):
    monkeypatch.setattr(watchlist_mod, "WATCHLIST_ENABLED", False)

    # Test POST /targets
    r = client.post(
        "/watchlist/targets", json={"type": "email", "value": "test@test.com"}
    )
    assert r.status_code == 200
    assert r.json() == {"enabled": False}

    # Test GET /targets
    r = client.get("/watchlist/targets")
    assert r.status_code == 200
    assert r.json() == {"enabled": False}

    # Test DELETE /targets/1
    r = client.delete("/watchlist/targets/1")
    assert r.status_code == 200
    assert r.json() == {"enabled": False}

    # Test PUT /targets/1
    r = client.put("/watchlist/targets/1", json={"status": "paused"})
    assert r.status_code == 200
    assert r.json() == {"enabled": False}

    # Test GET /targets/1/history
    r = client.get("/watchlist/targets/1/history")
    assert r.status_code == 200
    assert r.json() == {"enabled": False}

    # Test GET /alerts
    r = client.get("/watchlist/alerts")
    assert r.status_code == 200
    assert r.json() == {"enabled": False}

    # Test POST /targets/1/run-now
    r = client.post("/watchlist/targets/1/run-now")
    assert r.status_code == 200
    assert r.json() == {"enabled": False}


def test_create_target(client, test_db, monkeypatch):
    monkeypatch.setattr(watchlist_mod, "WATCHLIST_ENABLED", True)

    payload = {
        "type": "email",
        "value": "john.doe@example.com",
        "description": "John's personal email",
        "status": "active",
    }
    r = client.post("/watchlist/targets", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] is not None
    assert data["type"] == "email"
    assert data["value"] == "john.doe@example.com"
    assert data["description"] == "John's personal email"
    assert data["status"] == "active"
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


def test_get_targets(client, test_db, monkeypatch):
    monkeypatch.setattr(watchlist_mod, "WATCHLIST_ENABLED", True)

    # Initially empty
    r = client.get("/watchlist/targets")
    assert r.status_code == 200
    assert r.json() == []

    # Create target
    client.post(
        "/watchlist/targets",
        json={"type": "username", "value": "john_doe_99"},
    )

    # Get again
    r = client.get("/watchlist/targets")
    assert r.status_code == 200
    targets = r.json()
    assert len(targets) == 1
    assert targets[0]["value"] == "john_doe_99"


def test_update_target(client, test_db, monkeypatch):
    monkeypatch.setattr(watchlist_mod, "WATCHLIST_ENABLED", True)

    # Create target
    r = client.post(
        "/watchlist/targets", json={"type": "domain", "value": "example.com"}
    )
    target_id = r.json()["id"]

    # Update target
    r = client.put(
        f"/watchlist/targets/{target_id}",
        json={"status": "paused", "description": "some domain"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "paused"
    assert data["description"] == "some domain"


def test_delete_target(client, test_db, monkeypatch):
    monkeypatch.setattr(watchlist_mod, "WATCHLIST_ENABLED", True)

    # Create target
    r = client.post(
        "/watchlist/targets", json={"type": "email", "value": "test@test.com"}
    )
    target_id = r.json()["id"]

    # Delete target
    r = client.delete(f"/watchlist/targets/{target_id}")
    assert r.status_code == 200
    assert r.json() == {"success": True}

    # Verify deleted
    r = client.get("/watchlist/targets")
    assert r.json() == []

    # Non-existent delete
    r = client.delete(f"/watchlist/targets/{target_id}")
    assert r.status_code == 404


def test_get_history(client, test_db, monkeypatch):
    monkeypatch.setattr(watchlist_mod, "WATCHLIST_ENABLED", True)

    # Create target
    r = client.post(
        "/watchlist/targets", json={"type": "email", "value": "hist@test.com"}
    )
    target_id = r.json()["id"]

    # Update target
    client.put(f"/watchlist/targets/{target_id}", json={"status": "paused"})

    # Get history
    r = client.get(f"/watchlist/targets/{target_id}/history")
    assert r.status_code == 200
    history = r.json()
    assert len(history) >= 2
    # Ordered DESC, so index 0 is most recent ("updated")
    assert history[0]["change_type"] == "updated"
    assert history[1]["change_type"] == "created"


def test_run_now_creates_alert(client, test_db, monkeypatch):
    monkeypatch.setattr(watchlist_mod, "WATCHLIST_ENABLED", True)

    # Create target with "alert" in value
    r = client.post(
        "/watchlist/targets",
        json={"type": "email", "value": "has_alert@test.com"},
    )
    target_id = r.json()["id"]

    # Run now
    r = client.post(f"/watchlist/targets/{target_id}/run-now")
    assert r.status_code == 200
    res = r.json()
    assert res["success"] is True
    assert res["alerts_created"] == 1

    # Check alerts endpoint
    r = client.get("/watchlist/alerts")
    assert r.status_code == 200
    alerts = r.json()
    assert len(alerts) == 1
    assert alerts[0]["target_id"] == target_id
    assert alerts[0]["severity"] == "high"


def test_run_now_no_alert(client, test_db, monkeypatch):
    monkeypatch.setattr(watchlist_mod, "WATCHLIST_ENABLED", True)

    # Create target without "alert" in value
    r = client.post(
        "/watchlist/targets", json={"type": "email", "value": "clean@test.com"}
    )
    target_id = r.json()["id"]

    # Run now
    r = client.post(f"/watchlist/targets/{target_id}/run-now")
    assert r.status_code == 200
    res = r.json()
    assert res["success"] is True
    assert res["alerts_created"] == 0

    # Check alerts endpoint (should be empty)
    r = client.get("/watchlist/alerts")
    assert r.json() == []


def test_get_alerts_filtering_since(client, test_db, monkeypatch):
    monkeypatch.setattr(watchlist_mod, "WATCHLIST_ENABLED", True)

    # Create target with "alert" in value
    r = client.post(
        "/watchlist/targets",
        json={"type": "email", "value": "alert_target@test.com"},
    )
    target_id = r.json()["id"]

    # Run now to create alert
    client.post(f"/watchlist/targets/{target_id}/run-now")

    # Fetch alerts
    r = client.get("/watchlist/alerts")
    alerts = r.json()
    assert len(alerts) == 1

    # Filter with since before alert
    r = client.get("/watchlist/alerts?since=2020-01-01T00:00:00")
    assert len(r.json()) == 1

    # Filter with since after alert
    r = client.get("/watchlist/alerts?since=2030-01-01T00:00:00")
    assert len(r.json()) == 0
