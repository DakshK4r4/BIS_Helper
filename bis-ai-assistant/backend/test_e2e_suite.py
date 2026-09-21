"""End-to-End Test Suite for BIS Sahayak AI Assistant & RAG Platform.

Tests:
 1. General conversation fast-path ("Hello")
 2. Exact IS number lookup ("What is IS 456?")
 3. Standard explanation ("Explain IS 14543")
 4. Semantic search ("What is the BIS standard for drinking water?")
 5. Scope / chunk retrieval ("What is the scope of IS 456?")
 6. Specific clause query ("Explain clause 5.2 of IS 10322")
 7. Non-existent standard query -> safe fallback ("What is IS 999999?")
 8. Conversation memory & coreference ("What is its scope?" after IS 456)
 9. Out-of-scope query handling ("Who won the football world cup?")
10. Empty message handling (returns 400 Bad Request)
11. Document Analyzer two-pass evaluation (PDF compliance with PASS/FAIL/UNKNOWN)
12. User watchlist persistence & toggle (/api/watchlist)
13. Complaint investigation workflow (/api/complaints/<id>/investigate)
14. Dynamic dashboard metrics (/api/dashboard)
15. Standards catalogue filtering & sorting
"""

import os
import sys
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import app as flask_app_module
from database import init_db, get_db, get_real_dashboard_metrics
from ai_engine import SAFE_FALLBACK_MESSAGE

passed = 0
failed = 0


def assert_true(cond, msg="Assertion failed"):
    global passed, failed
    if not cond:
        failed += 1
        print(f"  [FAIL] {msg}")
        raise AssertionError(msg)
    else:
        passed += 1


def run_all_tests():
    global passed, failed
    flask_app_module.app.config["TESTING"] = True
    init_db()
    client = flask_app_module.app.test_client()

    print("\n==================================================")
    print("RUNNING BIS SAHAYAK COMPREHENSIVE TEST SUITE")
    print("==================================================")

    # ----------------------------------------------------
    # Scenario 1: General Conversation Fast-Path ("Hello")
    # ----------------------------------------------------
    print("\n[Test 1] Testing General Conversation Fast-Path ('Hello')...")
    res = client.post("/api/ai/query", json={"query": "Hello"})
    assert_true(res.status_code == 200, f"Status: {res.status_code}")
    data = res.get_json()
    assert_true(data.get("intent") == "general_conversation", f"Intent: {data.get('intent')}")
    assert_true("BIS Sahayak" in data.get("answer", ""), "Greeting mentions BIS Sahayak")
    assert_true(data.get("confidence") == 1.0 or data.get("confidence_score") == "100%", "Confidence is 100%")
    print(f"  ✓ Fast-path greeted without RAG noise: '{data['answer'][:60]}...'")

    # ----------------------------------------------------
    # Scenario 2: Exact IS Number Lookup ("What is IS 456?")
    # ----------------------------------------------------
    print("\n[Test 2] Testing Exact IS Number Lookup ('What is IS 456?')...")
    res = client.post("/api/ai/query", json={"query": "What is IS 456?"})
    assert_true(res.status_code == 200, f"Status: {res.status_code}")
    data = res.get_json()
    assert_true(data.get("recommended_standard") is not None, "Has recommended standard")
    assert_true("456" in data["recommended_standard"]["is_number"], f"Matched IS 456, got: {data['recommended_standard']['is_number']}")
    assert_true("concrete" in data["recommended_standard"]["title"].lower() or "concrete" in data["answer"].lower(), "Identified Concrete")
    assert_true(float(data.get("confidence_numeric", 0)) >= 0.85, f"High confidence: {data.get('confidence_score')}")
    print(f"  ✓ Standard identified: {data['recommended_standard']['is_number']} – {data['recommended_standard']['title']}")

    # ----------------------------------------------------
    # Scenario 3: Standard Explanation ("Explain IS 14543")
    # ----------------------------------------------------
    print("\n[Test 3] Testing Standard Explanation ('Explain IS 14543')...")
    res = client.post("/api/ai/query", json={"query": "Explain IS 14543"})
    assert_true(res.status_code == 200)
    data = res.get_json()
    assert_true("14543" in str(data.get("recommended_standard", {}).get("is_number", "")), "IS 14543 matched")
    assert_true("water" in data.get("answer", "").lower(), "Water mentioned in answer")
    print(f"  ✓ IS 14543 packaged water explained: {data['recommended_standard']['title']}")

    # ----------------------------------------------------
    # Scenario 4: Semantic Search ("What is the BIS standard for drinking water?")
    # ----------------------------------------------------
    print("\n[Test 4] Testing Semantic Search ('What is the BIS standard for drinking water?')...")
    res = client.post("/api/ai/query", json={"query": "What is the BIS standard for drinking water?"})
    assert_true(res.status_code == 200)
    data = res.get_json()
    rec = data.get("recommended_standard", {})
    assert_true(rec is not None and "14543" in str(rec.get("is_number")), f"Semantic match IS 14543, got: {rec.get('is_number')}")
    assert_true(float(data.get("confidence_numeric", 0)) > 0.5, f"Semantic confidence: {data.get('confidence_score')}")
    print(f"  ✓ Semantic retrieval matched: {rec.get('is_number')} ({rec.get('title')}) with confidence {data.get('confidence_score')}")

    # ----------------------------------------------------
    # Scenario 5: Scope / Chunk Retrieval ("What is the scope of IS 456?")
    # ----------------------------------------------------
    print("\n[Test 5] Testing Clause / Scope Retrieval ('What is the scope of IS 456?')...")
    res = client.post("/api/ai/query", json={"query": "What is the scope of IS 456?"})
    assert_true(res.status_code == 200)
    data = res.get_json()
    assert_true("456" in str(data.get("recommended_standard", {}).get("is_number")), "IS 456 scope retrieved")
    assert_true("concrete" in data.get("answer", "").lower(), "Concrete code scope in answer")
    print(f"  ✓ Scope retrieved with answer structure: {data['answer'][:80]}...")

    # ----------------------------------------------------
    # Scenario 6: Specific Clause Query ("Explain clause 5.2 of IS 10322")
    # ----------------------------------------------------
    print("\n[Test 6] Testing Specific Clause Query ('Explain clause 5.2 of IS 10322')...")
    res = client.post("/api/ai/query", json={"query": "Explain clause 5.2 of IS 10322"})
    assert_true(res.status_code == 200)
    data = res.get_json()
    assert_true("10322" in str(data.get("recommended_standard", {}).get("is_number")), "IS 10322 matched")
    print(f"  ✓ Clause query resolved: Clause {data.get('recommended_standard', {}).get('clause')}")

    # ----------------------------------------------------
    # Scenario 7: Non-existent Standard Query ("What is IS 999999?")
    # ----------------------------------------------------
    print("\n[Test 7] Testing Non-existent Standard Query ('What is IS 999999?')...")
    res = client.post("/api/ai/query", json={"query": "What is IS 999999?"})
    assert_true(res.status_code == 200)
    data = res.get_json()
    assert_true(data.get("ai_status") == "insufficient_evidence", "Flagged insufficient evidence")
    assert_true(SAFE_FALLBACK_MESSAGE in data.get("answer", ""), "Safe fallback guardrail triggered")
    assert_true(data.get("confidence_numeric") == 0.0 or data.get("confidence") == 0.0, "Zero confidence")
    print("  ✓ Non-existent standard safely returned standard fallback message without hallucinations")

    # ----------------------------------------------------
    # Scenario 8: Conversation Memory & Coreference Resolution
    # Turn 1: "What is IS 456?" -> Turn 2: "What is its scope?"
    # ----------------------------------------------------
    print("\n[Test 8] Testing Conversation Memory & Coreference Resolution...")
    # Turn 1
    t1_res = client.post("/api/ai/query", json={"query": "What is IS 456?"})
    t1_data = t1_res.get_json()

    history = [
        {"role": "user", "content": "What is IS 456?", "query": "What is IS 456?"},
        {"role": "assistant", "content": t1_data.get("answer"), "recommended_standard": t1_data.get("recommended_standard")}
    ]

    # Turn 2 with pronoun "its"
    t2_res = client.post("/api/ai/query", json={
        "query": "What is its scope?",
        "history": history
    })
    assert_true(t2_res.status_code == 200)
    t2_data = t2_res.get_json()
    assert_true(t2_data.get("parsed_query", {}).get("coreference_resolved") is True, "Coreference resolved flag")
    assert_true("456" in str(t2_data.get("recommended_standard", {}).get("is_number")), f"Resolved 'its' to IS 456, got: {t2_data.get('recommended_standard', {}).get('is_number')}")
    print(f"  ✓ Turn 2 'What is its scope?' resolved coreference to {t2_data['recommended_standard']['is_number']}")

    # ----------------------------------------------------
    # Scenario 9: Out-of-Scope Query ("Who won the football world cup?")
    # ----------------------------------------------------
    print("\n[Test 9] Testing Out-of-Scope Query ('Who won the football world cup?')...")
    res = client.post("/api/ai/query", json={"query": "Who won the football world cup?"})
    assert_true(res.status_code == 200)
    data = res.get_json()
    assert_true(data.get("ai_status") == "out_of_scope", f"Status: {data.get('ai_status')}")
    assert_true("Bureau of Indian Standards" in data.get("answer", "") or "Indian Standards" in data.get("answer", ""), "Scope reminder in answer")
    print(f"  ✓ Out-of-scope query deflected cleanly: {data['answer'][:70]}...")

    # ----------------------------------------------------
    # Scenario 10: Empty Message Handling ("")
    # ----------------------------------------------------
    print("\n[Test 10] Testing Empty Message Handling ('')...")
    res = client.post("/api/ai/query", json={"query": "   "})
    assert_true(res.status_code == 400, f"Empty query rejected with 400, got: {res.status_code}")
    data = res.get_json()
    assert_true(data.get("success") is False, "success: false")
    print("  ✓ Empty query rejected with 400 Bad Request")

    # ----------------------------------------------------
    # Scenario 11: Document Analyzer Two-Pass Audit
    # ----------------------------------------------------
    print("\n[Test 11] Testing Document Analyzer Two-Pass Audit...")
    test_pdf = os.path.join(BASE_DIR, "uploads", "BIS_LED_Street_Light_Test_Document.pdf")
    if os.path.exists(test_pdf):
        with open(test_pdf, "rb") as f:
            res = client.post(
                "/api/document/analyze",
                data={"file": (f, "BIS_LED_Street_Light_Test_Document.pdf")},
                content_type="multipart/form-data"
            )
        assert_true(res.status_code == 200, f"Analyze PDF status: {res.status_code}")
        doc_data = res.get_json().get("document", {})
        counts = doc_data.get("status_counts", {})
        print(f"  ✓ Two-pass compliance: {doc_data.get('compliance_score')}% Score | PASS: {counts.get('pass')} | FAIL: {counts.get('fail')} | NOT_FOUND: {counts.get('not_found')}")
        assert_true(counts.get("pass", 0) > 0, "At least 1 pass requirement")
        assert_true(counts.get("fail", 0) > 0, "At least 1 fail requirement")
        assert_true(counts.get("not_found", 0) > 0, "At least 1 not_found requirement")
        assert_true(all("source_clause" in r for r in doc_data.get("requirements", [])), "Each requirement has source_clause")
    else:
        print(f"  (Skipping PDF audit: {test_pdf} not found)")

    # ----------------------------------------------------
    # Scenario 12: User Watchlist Persistence & Toggle
    # ----------------------------------------------------
    print("\n[Test 12] Testing User Watchlist Persistence & Toggle...")
    headers = {"X-User-Email": "officer@bis.gov.in"}
    # Toggle IS 14543
    res = client.post("/api/watchlist", json={"is_number": "IS 14543 : 2024"}, headers=headers)
    assert_true(res.status_code == 200, f"Watchlist toggle status: {res.status_code}")
    
    res = client.get("/api/watchlist", headers=headers)
    assert_true(res.status_code == 200)
    w_data = res.get_json()
    w_list = w_data.get("watchlist", [])
    assert_true(any("14543" in (w.get("is_number") if isinstance(w, dict) else str(w)) for w in w_list), "IS 14543 in watchlist")
    print(f"  ✓ User watchlist persisted: {len(w_list)} bookmarked standards")

    # ----------------------------------------------------
    # Scenario 13: Complaint Investigation Workflow
    # ----------------------------------------------------
    print("\n[Test 13] Testing Complaint Investigation Workflow...")
    # Fetch complaints
    res = client.get("/api/complaints", headers=headers)
    assert_true(res.status_code == 200)
    c_list = res.get_json().get("complaints", [])
    if c_list:
        target_id = c_list[0]["complaint_id"]
        res = client.post(f"/api/complaints/{target_id}/investigate", headers=headers)
        assert_true(res.status_code == 200, f"Investigate status: {res.status_code}")
        inv_data = res.get_json()
        assert_true(inv_data.get("complaint", {}).get("status") == "INVESTIGATION", "Status changed to INVESTIGATION")
        print(f"  ✓ Complaint {target_id} investigated by officer, status: {inv_data.get('complaint', {}).get('status')}")

    # ----------------------------------------------------
    # Scenario 14: Dynamic Dashboard Metrics
    # ----------------------------------------------------
    print("\n[Test 14] Testing Dynamic Dashboard Metrics...")
    res = client.get("/api/dashboard", headers=headers)
    assert_true(res.status_code == 200)
    m = res.get_json().get("metrics", {})
    assert_true(m.get("standards_tracked", 0) >= 15, f"Standards tracked: {m.get('standards_tracked')}")
    assert_true(m.get("products", 0) > 0, f"Products count: {m.get('products')}")
    print(f"  ✓ Dashboard metrics computed: {m}")

    # ----------------------------------------------------
    # Scenario 15: Standards Catalogue Search & Sort
    # ----------------------------------------------------
    print("\n[Test 15] Testing Standards Search, Filtering & Sorting...")
    res = client.get("/api/standards?category=Civil")
    assert_true(res.status_code == 200)
    s_data = res.get_json()
    assert_true(s_data["count"] > 0, "Civil standards found")
    print(f"  ✓ Filtered Civil standards: {s_data['count']} items found")

    print("\n==================================================")
    print(f"ALL TESTS COMPLETED: {passed} assertions PASSED! (Failed: {failed})")
    print("==================================================\n")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
