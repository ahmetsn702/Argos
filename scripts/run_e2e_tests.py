import time
import requests
import json
import sys

BASE_URLS = ["http://localhost:8000", "http://127.0.0.1:8000"]
base_url = None

print("Checking API connection...")
for url in BASE_URLS:
    try:
        response = requests.get(f"{url}/__ping", timeout=3)
        if response.status_code == 200:
            base_url = url
            print(f"Connected successfully to API at: {base_url}")
            print(f"Ping response: {response.json()}\n")
            break
    except Exception as e:
        print(f"Failed to connect to {url}: {e}")

if not base_url:
    print("Error: Could not connect to ARGOS OSINT API on localhost:8000 or 127.0.0.1:8000.")
    print("Please make sure the server is running.")
    sys.exit(1)

def run_test_1():
    print("=" * 60)
    print("TEST 1 — Pivot dry_run")
    print("=" * 60)
    url = f"{base_url}/pivot/run"
    body = {
        "seed_finding_id": "test",
        "seed_key": "email:test@test.com",
        "max_depth": 2,
        "dry_run": True
    }
    print(f"POST {url}")
    print(f"Body: {json.dumps(body)}")
    
    try:
        r = requests.post(url, json=body, timeout=10)
        print(f"HTTP Status: {r.status_code}")
        print("Response Body:")
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
        
        # Validation
        data = r.json()
        assert r.status_code == 200, f"Expected status code 200, got {r.status_code}"
        assert data.get("status") == "completed", f"Expected status 'completed', got '{data.get('status')}'"
        assert data.get("plan") is not None and len(data.get("plan")) > 0, "Expected non-empty plan"
        print("\n--> TEST 1 SUCCESSFUL")
    except Exception as e:
        print(f"\n--> TEST 1 FAILED: {e}")

def run_test_2():
    print("=" * 60)
    print("TEST 2 — Pivot gerçek oturum")
    print("=" * 60)
    url = f"{base_url}/pivot/run"
    body = {
        "seed_finding_id": "email_1",
        "seed_key": "email:ahmet@gmail.com",
        "max_depth": 1,
        "dry_run": False
    }
    print(f"POST {url}")
    print(f"Body: {json.dumps(body)}")
    
    session_id = None
    try:
        r = requests.post(url, json=body, timeout=10)
        print(f"HTTP Status: {r.status_code}")
        print("Response Body:")
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
        
        data = r.json()
        assert r.status_code == 200, f"Expected status code 200, got {r.status_code}"
        assert data.get("status") == "pending", f"Expected status 'pending', got '{data.get('status')}'"
        session_id = data.get("session_id")
        assert session_id, "Expected non-empty session_id"
        print(f"Session ID acquired: {session_id}")
    except Exception as e:
        print(f"\n--> TEST 2 (Initiation) FAILED: {e}")
        return None

    print("\nWaiting 3 seconds before querying session...")
    time.sleep(3)
    
    session_url = f"{base_url}/pivot/session/{session_id}"
    print(f"GET {session_url}")
    try:
        r = requests.get(session_url, timeout=10)
        print(f"HTTP Status: {r.status_code}")
        print("Response Body:")
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
        
        data = r.json()
        assert r.status_code == 200, f"Expected status code 200, got {r.status_code}"
        status = data.get("status")
        assert status in ["completed", "failed", "running"], f"Expected status completed, failed, or running, got '{status}'"
        print(f"\n--> TEST 2 SUCCESSFUL (Status: {status})")
    except Exception as e:
        print(f"\n--> TEST 2 (Query) FAILED: {e}")
        
    return session_id

def run_test_3(session_id):
    print("=" * 60)
    print("TEST 3 — History")
    print("=" * 60)
    url = f"{base_url}/pivot/history"
    print(f"GET {url}")
    
    try:
        r = requests.get(url, timeout=10)
        print(f"HTTP Status: {r.status_code}")
        print("Response Body:")
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
        
        data = r.json()
        assert r.status_code == 200, f"Expected status code 200, got {r.status_code}"
        assert isinstance(data, list), "Expected list of sessions"
        
        if session_id:
            found = any(s.get("session_id") == session_id for s in data)
            assert found, f"Session ID {session_id} was not found in history"
            print(f"Verified: session_id {session_id} exists in history")
        
        print("\n--> TEST 3 SUCCESSFUL")
    except Exception as e:
        print(f"\n--> TEST 3 FAILED: {e}")

def run_test_4():
    print("=" * 60)
    print("TEST 4 — Confidence graph ile entegrasyon")
    print("=" * 60)
    url = f"{base_url}/confidence/build"
    
    # 4A. Exact test body requested by user (using "key" instead of "seed_key")
    body_exact = {
        "key": "email:test@argos.com",
        "raw": {
            "mosint": {
                "email": "test@argos.com",
                "domain": "argos.com"
            }
        }
    }
    print("--- 4A: User Request Body (uses 'key') ---")
    print(f"POST {url}")
    print(f"Body: {json.dumps(body_exact)}")
    
    try:
        r = requests.post(url, json=body_exact, timeout=10)
        print(f"HTTP Status: {r.status_code}")
        try:
            print("Response Body:")
            print(json.dumps(r.json(), indent=2, ensure_ascii=False))
        except:
            print(r.text)
    except Exception as e:
        print(f"Request failed: {e}")
        
    print("\n--- 4B: Corrected Request Body (uses 'seed_key' as defined by API Pydantic model) ---")
    body_corrected = {
        "seed_key": "email:test@argos.com",
        "raw": {
            "mosint": {
                "email": "test@argos.com",
                "domain": "argos.com"
            }
        }
    }
    print(f"POST {url}")
    print(f"Body: {json.dumps(body_corrected)}")
    
    try:
        r = requests.post(url, json=body_corrected, timeout=10)
        print(f"HTTP Status: {r.status_code}")
        print("Response Body:")
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
        
        data = r.json()
        assert r.status_code == 200, f"Expected status code 200, got {r.status_code}"
        assert data.get("seed_key") == "email:test@argos.com", f"Expected seed_key 'email:test@argos.com', got '{data.get('seed_key')}'"
        assert "findings" in data, "Expected 'findings' in confidence graph"
        print("\n--> TEST 4 SUCCESSFUL")
    except Exception as e:
        print(f"\n--> TEST 4 FAILED: {e}")

if __name__ == "__main__":
    run_test_1()
    print()
    session_id = run_test_2()
    print()
    run_test_3(session_id)
    print()
    run_test_4()
