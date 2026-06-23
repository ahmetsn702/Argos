import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings

client = TestClient(app)

class MockResponse:
    def __init__(self, status_code: int, json_data: dict):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data

class MockAsyncClient:
    def __init__(self, get_responses=None, post_responses=None):
        self.get_responses = get_responses or {}
        self.post_responses = post_responses or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def get(self, url, params=None):
        for pattern, res in self.get_responses.items():
            if pattern in url:
                return MockResponse(res[0], res[1])
        return MockResponse(404, {})

    async def post(self, url, json=None):
        for pattern, res in self.post_responses.items():
            if pattern in url:
                return MockResponse(res[0], res[1])
        return MockResponse(404, {})

# 1. Test endpoints when MALTEGO_ENABLED is False
def test_maltego_endpoints_disabled():
    with patch("app.routers.maltego.ff.MALTEGO_ENABLED", False):
        response = client.get("/maltego/transforms")
        assert response.status_code == 200
        assert response.json() == {"enabled": False}

        response = client.post(
            "/maltego/transform/argos.EmailToProfiles",
            json={"value": "test@example.com", "type": "maltego.EmailAddress"}
        )
        assert response.status_code == 200
        assert response.json() == {"enabled": False}

# 3. Test list transforms when enabled and auth bypassed (key is None)
def test_transforms_list_enabled_no_auth():
    with patch("app.routers.maltego.ff.MALTEGO_ENABLED", True), \
         patch("app.routers.maltego.settings.MALTEGO_API_KEY", None):
        response = client.get("/maltego/transforms")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 6
        assert any(t["name"] == "argos.EmailToProfiles" for t in data)

# 4. Test auth missing key
def test_auth_missing_key():
    with patch("app.routers.maltego.ff.MALTEGO_ENABLED", True), \
         patch("app.routers.maltego.settings.MALTEGO_API_KEY", "secret_key"):
        response = client.get("/maltego/transforms")
        assert response.status_code == 401
        assert response.json()["detail"] == "Unauthorized"

# 5. Test auth wrong key
def test_auth_wrong_key():
    with patch("app.routers.maltego.ff.MALTEGO_ENABLED", True), \
         patch("app.routers.maltego.settings.MALTEGO_API_KEY", "secret_key"):
        headers = {"X-Maltego-API-Key": "wrong_key"}
        response = client.get("/maltego/transforms", headers=headers)
        assert response.status_code == 401

# 6. Test auth correct key
def test_auth_correct_key():
    with patch("app.routers.maltego.ff.MALTEGO_ENABLED", True), \
         patch("app.routers.maltego.settings.MALTEGO_API_KEY", "secret_key"):
        headers = {"MALTEGO_API_KEY": "secret_key"}
        response = client.get("/maltego/transforms", headers=headers)
        assert response.status_code == 200
        assert len(response.json()) == 6

# 7. Test transform not found
def test_transform_not_found():
    with patch("app.routers.maltego.ff.MALTEGO_ENABLED", True), \
         patch("app.routers.maltego.settings.MALTEGO_API_KEY", None):
        response = client.post(
            "/maltego/transform/argos.NonExistentTransform",
            json={"value": "test", "type": "maltego.Unknown"}
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Transform not found"

# 8. Test EmailToProfiles
def test_email_to_profiles_success():
    mock_data = {
        "email": "test@example.com",
        "sources": {
            "gravatar": {
                "exists": True,
                "profile": {
                    "entry": [
                        {"preferredUsername": "gravatar_user"}
                    ]
                }
            }
        }
    }
    mock_client = MockAsyncClient(get_responses={"/mosint/full": (200, mock_data)})
    
    with patch("app.routers.maltego.ff.MALTEGO_ENABLED", True), \
         patch("app.routers.maltego.settings.MALTEGO_API_KEY", None), \
         patch("app.services.agent.tools.client.get_client", return_value=mock_client):
        response = client.post(
            "/maltego/transform/argos.EmailToProfiles",
            json={"value": "test@example.com", "type": "maltego.EmailAddress"}
        )
        assert response.status_code == 200
        entities = response.json()["entities"]
        assert len(entities) == 2
        # Check first entity (email prefix)
        assert entities[0]["type"] == "maltego.Alias"
        assert entities[0]["value"] == "test"
        # Check second entity (gravatar preferred username)
        assert entities[1]["type"] == "maltego.Alias"
        assert entities[1]["value"] == "gravatar_user"

# 9. Test UsernameToSocial
def test_username_to_social_success():
    mock_data = {
        "username": "testuser",
        "results": [
            {"platform": "Instagram", "url": "https://instagram.com/testuser", "status": "exists"},
            {"platform": "GitHub", "url": "https://github.com/testuser", "status": "exists"},
            {"platform": "X (Twitter)", "url": "https://x.com/testuser", "status": "not_found"}
        ]
    }
    mock_client = MockAsyncClient(get_responses={"/username-scan": (200, mock_data)})
    
    with patch("app.routers.maltego.ff.MALTEGO_ENABLED", True), \
         patch("app.routers.maltego.settings.MALTEGO_API_KEY", None), \
         patch("app.services.agent.tools.client.get_client", return_value=mock_client):
        response = client.post(
            "/maltego/transform/argos.UsernameToSocial",
            json={"value": "testuser", "type": "maltego.Alias"}
        )
        assert response.status_code == 200
        entities = response.json()["entities"]
        assert len(entities) == 2
        assert entities[0]["value"] == "Instagram:testuser"
        assert entities[0]["properties"]["url"] == "https://instagram.com/testuser"
        assert entities[1]["value"] == "GitHub:testuser"

# 10. Test PhoneToIdentity
def test_phone_to_identity_success():
    mock_data = {
        "valid": True,
        "number": "+905554443322",
        "country": "Turkey",
        "carrier": "Turkcell",
        "location": "Istanbul",
        "name": "Ahmet Yilmaz"
    }
    mock_client = MockAsyncClient(get_responses={"/phone/lookup": (200, mock_data)})
    
    with patch("app.routers.maltego.ff.MALTEGO_ENABLED", True), \
         patch("app.routers.maltego.settings.MALTEGO_API_KEY", None), \
         patch("app.services.agent.tools.client.get_client", return_value=mock_client):
        response = client.post(
            "/maltego/transform/argos.PhoneToIdentity",
            json={"value": "+905554443322", "type": "maltego.PhoneNumber"}
        )
        assert response.status_code == 200
        entities = response.json()["entities"]
        assert len(entities) == 4
        # Carrier, Country, Location, Person Name
        types = [e["type"] for e in entities]
        assert "maltego.Unknown" in types
        assert "maltego.Location" in types
        assert "maltego.Person" in types
        assert any(e["value"] == "Ahmet Yilmaz" for e in entities)

# 11. Test DomainToInfra
def test_domain_to_infra_success():
    mock_data = {
        "target": "example.com",
        "ip": "93.184.216.34",
        "dns": {
            "records": {
                "NS": ["ns1.example.com.", "ns2.example.com."],
                "MX": ["10 mail.example.com."]
            }
        }
    }
    mock_client = MockAsyncClient(get_responses={"/domain/lookup": (200, mock_data)})
    
    with patch("app.routers.maltego.ff.MALTEGO_ENABLED", True), \
         patch("app.routers.maltego.settings.MALTEGO_API_KEY", None), \
         patch("app.services.agent.tools.client.get_client", return_value=mock_client):
        response = client.post(
            "/maltego/transform/argos.DomainToInfra",
            json={"value": "example.com", "type": "maltego.Domain"}
        )
        assert response.status_code == 200
        entities = response.json()["entities"]
        assert len(entities) == 4
        # 1 IP + 2 NS + 1 MX
        types = [e["type"] for e in entities]
        assert "maltego.IPv4Address" in types
        assert "maltego.Domain" in types
        assert any(e["value"] == "93.184.216.34" for e in entities)
        assert any(e["value"] == "ns1.example.com" for e in entities)
        assert any(e["value"] == "mail.example.com" for e in entities)

# 12. Test IpToGeo
def test_ip_to_geo_success():
    mock_data = {
        "geo": {
            "country": "United States",
            "city": "Norwell",
            "region": "Massachusetts",
            "isp": "Verizon",
            "lat": 42.16,
            "lng": -70.79
        }
    }
    mock_client = MockAsyncClient(get_responses={"/domain/lookup": (200, mock_data)})
    
    with patch("app.routers.maltego.ff.MALTEGO_ENABLED", True), \
         patch("app.routers.maltego.settings.MALTEGO_API_KEY", None), \
         patch("app.services.agent.tools.client.get_client", return_value=mock_client):
        response = client.post(
            "/maltego/transform/argos.IpToGeo",
            json={"value": "93.184.216.34", "type": "maltego.IPv4Address"}
        )
        assert response.status_code == 200
        entities = response.json()["entities"]
        assert len(entities) == 2
        # Location & ISP
        assert entities[0]["type"] == "maltego.Location"
        assert entities[0]["value"] == "Norwell, Massachusetts, United States"
        assert entities[0]["properties"]["lat"] == "42.16"
        assert entities[1]["type"] == "maltego.Unknown"
        assert entities[1]["value"] == "Verizon"

# 13. Test EntityToConfidence (cached graph case)
def test_entity_to_confidence_cached():
    mock_data = {
        "findings": {
            "f1": {"id": "f1", "type": "email", "value": "test@example.com", "confidence_score": 0.95},
            "f2": {"id": "f2", "type": "phone", "value": "+123", "confidence_score": 0.75}
        }
    }
    mock_client = MockAsyncClient(get_responses={"/confidence/graph": (200, mock_data)})
    
    with patch("app.routers.maltego.ff.MALTEGO_ENABLED", True), \
         patch("app.routers.maltego.settings.MALTEGO_API_KEY", None), \
         patch("app.services.agent.tools.client.get_client", return_value=mock_client):
        response = client.post(
            "/maltego/transform/argos.EntityToConfidence",
            json={"value": "seed_key", "type": "maltego.Unknown"}
        )
        assert response.status_code == 200
        entities = response.json()["entities"]
        assert len(entities) == 2
        assert entities[0]["type"] == "maltego.EmailAddress"
        assert entities[0]["value"] == "test@example.com"
        assert entities[0]["properties"]["confidence_score"] == "0.95"
        assert entities[1]["type"] == "maltego.PhoneNumber"
        assert entities[1]["value"] == "+123"

# 14. Test EntityToConfidence (fallback/build case)
def test_entity_to_confidence_fallback():
    mock_data = {
        "findings": {
            "f1": {"id": "f1", "type": "email", "value": "built@example.com", "confidence_score": 0.8}
        }
    }
    mock_client = MockAsyncClient(
        get_responses={"/confidence/graph": (404, {"detail": "Not found"})},
        post_responses={"/confidence/build": (200, mock_data)}
    )
    
    with patch("app.routers.maltego.ff.MALTEGO_ENABLED", True), \
         patch("app.routers.maltego.settings.MALTEGO_API_KEY", None), \
         patch("app.services.agent.tools.client.get_client", return_value=mock_client):
        response = client.post(
            "/maltego/transform/argos.EntityToConfidence",
            json={"value": "seed_key", "type": "maltego.Unknown"}
        )
        assert response.status_code == 200
        entities = response.json()["entities"]
        assert len(entities) == 1
        assert entities[0]["type"] == "maltego.EmailAddress"
        assert entities[0]["value"] == "built@example.com"
