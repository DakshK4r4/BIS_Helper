"""
Standalone End-to-End Test Runner for BIS Sahayak Backend & Database
Tests all API endpoints, authentication, standards search/filtering/sorting,
Hallmark verification, complaints, notifications, and user action history.
"""

import os
import sys
import json

backend_dir = r"c:\Users\rgnvu\OneDrive\Desktop\BIS_Sahayak_Upgraded\bis-ai-assistant\backend"
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import app as flask_app_module
from database import init_db, get_db

passed = 0
failed = 0

def assert_true(cond, msg="Assertion failed"):
    global passed, failed
    if not cond:
        failed += 1
        print(f" [FAIL] {msg}")
        raise AssertionError(msg)
    else:
        passed += 1

def run_all_tests():
    global passed, failed
    flask_app_module.app.config["TESTING"] = True
    init_db()
    client = flask_app_module.app.test_client()

    print("\n==================================================")
    print("RUNNING BIS SAHAYAK E2E INTEGRATION SUITE")
    print("==================================================")

    # 1. Standards
    print("\n1. Testing Standards Search, Filtering & Sorting...")
    res = client.get("/api/standards")
    assert_true(res.status_code == 200, f"Status: {res.status_code}")
    data = res.get_json()
    assert_true(data["count"] >= 15, f"Total count: {data['count']}")
    print(f"    Total standards in database: {data['count']}")

    res = client.get("/api/standards?category=Electrical")
    assert_true(res.status_code == 200)
    data = res.get_json()
    assert_true(data["count"] > 0 and all(s["category"] == "Electrical" for s in data["standards"]), "Category Electrical")
    print(f"    Filtered Electrical: {data['count']} standards found")

    res = client.get("/api/standards?q=cement")
    assert_true(res.status_code == 200)
    data = res.get_json()
    assert_true(data["count"] > 0, "Query cement")
    print(f"    Keyword query 'cement': {data['count']} standards found")

    res = client.get("/api/standards?sort=newest")
    assert_true(res.status_code == 200)
    data = res.get_json()
    years = [int(s["year"]) for s in data["standards"] if str(s["year"]).isdigit()]
    assert_true(years == sorted(years, reverse=True), "Sort newest first")
    print(f"    Sorting by newest year: OK ({years[:3]}...)")

    # 2. Authentication
    print("\n2. Testing Demo Authentication...")
    for role in ["officer", "manufacturer", "consumer"]:
        res = client.post("/api/auth/demo", json={"role": role})
        assert_true(res.status_code == 200, f"Auth demo {role}")
        u = res.get_json()
        assert_true("user" in u and "token" in u, f"Token for {role}")
        print(f"    Demo login for '{role}': {u['user']['name']} ({u['user']['role']}) - OK")

    # 3. AI Query
    print("\n3. Testing AI Assistant Query with Grounded RAG...")
    res = client.post(
        "/api/ai/query",
        json={"query": "What are safety requirements for LED luminaires?"},
        headers={"X-User-Email": "officer@bis.gov.in"}
    )
    assert_true(res.status_code == 200, "AI query status 200")
    data = res.get_json()
    assert_true("answer" in data and len(data["answer"]) > 20, "AI answer generated")
    assert_true(data.get("recommended_standard") is not None, "Standard recommendation")
    assert_true("10322" in data["recommended_standard"]["is_number"], f"Expected IS 10322, got {data['recommended_standard']['is_number']}")
    print(f"    Recommended: {data['recommended_standard']['is_number']} - {data['recommended_standard']['title']}")
    print(f"    Answer preview: {data['answer'][:90]}...")

    # 4. License Verification
    print("\n4. Testing License Verification...")
    res = client.get("/api/verify/CM%2FL-1234567")
    assert_true(res.status_code == 200, "Verify valid license")
    data = res.get_json()
    assert_true(data["valid"] is True, "Valid license flag")
    assert_true(data["details"]["product"] == "LED Street Light", "License product")
    print(f"    CM/L-1234567 verified: {data['details']['manufacturer']} ({data['details']['status']})")

    res = client.get("/api/verify/INVALID-999")
    assert_true(res.status_code == 404, "Invalid license returns 404")
    print("    Invalid license rejected correctly with 404: OK")

    # 5. Hallmark Verification
    print("\n5. Testing Hallmark HUID Verification...")
    res = client.get(
        "/api/verify/hallmark/AB1234",
        headers={"X-User-Email": "officer@bis.gov.in"}
    )
    assert_true(res.status_code == 200, "Valid HUID AB1234")
    data = res.get_json()
    assert_true(data["valid"] is True and data["hallmark"]["huid"] == "AB1234", "HUID AB1234 match")
    print(f"    HUID AB1234 verified: {data['hallmark']['jeweler_name']} - {data['hallmark']['metal_purity']} ({data['hallmark']['center_name']})")

    res = client.get("/api/verify/hallmark/ZZ9999")
    assert_true(res.status_code == 404, "Unknown HUID returns 404")
    print("    Unknown HUID ZZ9999 returns 404: OK")

    res = client.get("/api/verify/hallmark/SHORT")
    assert_true(res.status_code == 400, "Invalid length HUID returns 400")
    print("    Short HUID returns 400 bad request: OK")

    # 6. Consumer Complaints
    print("\n6. Testing Consumer Complaints Submission...")
    payload = {
        "complainant_name": "Ramesh Kumar",
        "complainant_email": "ramesh@example.com",
        "complainant_phone": "9876543210",
        "category": "Electronics & IT",
        "reference_number": "CM/L-1234567",
        "subject": "Flickering LED bulb with fake ISI mark",
        "description": "Product purchased on local market fails to comply with IS 10322 specifications."
    }
    res = client.post(
        "/api/complaints",
        json=payload,
        headers={"X-User-Email": "ramesh@example.com"}
    )
    assert_true(res.status_code == 201, "Complaint registered 201")
    data = res.get_json()
    assert_true(data["success"] is True and data["tracking_id"].startswith("BIS-CMP-2026-"), "Tracking ID generated")
    print(f"    Registered complaint tracking ID: {data['tracking_id']} (Status: {data['status']})")

    # 7. Notifications
    print("\n7. Testing Notifications...")
    headers = {"X-User-Email": "officer@bis.gov.in"}
    res = client.get("/api/notifications", headers=headers)
    assert_true(res.status_code == 200, "Get notifications")
    data = res.get_json()
    print(f"    User officer@bis.gov.in has {len(data['notifications'])} notifications (unread: {data['unread_count']})")

    res = client.post("/api/notifications/read-all", headers=headers)
    assert_true(res.status_code == 200, "Mark all read")

    res = client.get("/api/notifications", headers=headers)
    data = res.get_json()
    assert_true(data["unread_count"] == 0, "Unread count is 0 after mark-all-read")
    print("    Marked all notifications as read: OK")

    # 8. Services
    print("\n8. Testing BIS Services Metadata...")
    res = client.get("/api/services")
    assert_true(res.status_code == 200, "Services 200")
    data = res.get_json()
    services = data["services"]
    for svc_key in ["product_certification", "hallmarking", "crs", "fmcs", "laboratory", "training"]:
        assert_true(svc_key in services, f"Service key {svc_key}")
    print(f"    All 6 BIS core services loaded with complete metadata: OK")

    # 9. User Action History
    print("\n9. Testing User Activity & Audit History...")
    res = client.get("/api/history", headers=headers)
    assert_true(res.status_code == 200, "History 200")
    data = res.get_json()
    assert_true(len(data["history"]) > 0, "History recorded actions")
    print(f"    Total recorded actions for officer: {len(data['history'])}")

    res = client.get("/api/history?filter=hallmark_verification", headers=headers)
    assert_true(res.status_code == 200, "Filter hallmark")
    data = res.get_json()
    assert_true(all("hallmark" in i.get("action_key", i.get("action_type", "")).lower() for i in data["history"]), "Filtered hallmark actions")
    print(f"    Filtered hallmark checks in history: {len(data['history'])} - OK")

    # 10. Dashboard
    print("\n10. Testing Industry Dashboard...")
    res = client.get("/api/dashboard")
    assert_true(res.status_code == 200, "Dashboard 200")
    data = res.get_json()
    assert_true(data["metrics"]["products"] > 0, "Dashboard products metric")
    print(f"    Dashboard metrics: {data['metrics']}")

    print("\n==================================================")
    print(f"ALL TESTS PASSED: {passed} assertions verified successfully! (Failed: {failed})")
    print("==================================================\n")

if __name__ == "__main__":
    try:
        run_all_tests()
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        sys.exit(1)
