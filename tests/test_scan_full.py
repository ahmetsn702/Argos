import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_scan_full_email():
    """Test /scan/full endpoint with email parameter"""
    response = client.get("/scan/full?email=test@example.com")
    assert response.status_code == 200
    
    data = response.json()
    
    # Required fields check
    assert "input" in data
    assert "results" in data
    assert "verdict" in data
    assert "took_ms" in data
    
    # Input validation
    assert data["input"]["email"] == "test@example.com"
    assert data["input"]["username"] is None
    assert data["input"]["phone"] is None
    
    # Verdict should be one of the expected values
    assert data["verdict"] in ["ok", "partial", "fail"]
    
    # Results should be a dict
    assert isinstance(data["results"], dict)
    
    # Took_ms should be positive
    assert data["took_ms"] > 0

def test_scan_full_username():
    """Test /scan/full endpoint with username parameter"""
    response = client.get("/scan/full?username=testuser")
    assert response.status_code == 200
    
    data = response.json()
    
    # Required fields check
    assert "input" in data
    assert "results" in data
    assert "verdict" in data
    assert "took_ms" in data
    
    # Input validation
    assert data["input"]["email"] is None
    assert data["input"]["username"] == "testuser"
    assert data["input"]["phone"] is None

def test_scan_full_no_params():
    """Test /scan/full endpoint with no parameters should return 400"""
    response = client.get("/scan/full")
    assert response.status_code == 400

def test_scan_full_multiple_params():
    """Test /scan/full endpoint with multiple parameters"""
    response = client.get("/scan/full?email=test@example.com&username=testuser")
    assert response.status_code == 200
    
    data = response.json()
    
    # Should have both email and username
    assert data["input"]["email"] == "test@example.com"
    assert data["input"]["username"] == "testuser"
    assert data["input"]["phone"] is None

