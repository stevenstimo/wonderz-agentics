#!/usr/bin/env python3
"""Test Knowledge Centre fase 4 — approval flow + GET endpoints.

Usage:
  export TOKEN="<bearer_token_from_browser_console>"
  python scripts/test_knowledge_phase4.py

Of: curl commands in comments.
"""
import os
import sys

API_BASE = os.getenv("API_BASE", "http://localhost:8090")
TOKEN = os.getenv("TOKEN", "")


def req(method: str, path: str, json_body=None, data=None):
    import urllib.request
    import json

    url = f"{API_BASE}{path}"
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    if data:
        headers = {"Authorization": f"Bearer {TOKEN}"}
    req_obj = urllib.request.Request(url, method=method, headers=headers)
    if json_body:
        req_obj.data = json.dumps(json_body).encode()
    elif data:
        req_obj.data = data
        req_obj.add_header("Content-Type", "multipart/form-data" if "multipart" in str(data) else "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req_obj, timeout=60) as r:
            return r.status, json.loads(r.read().decode()) if r.headers.get("Content-Type", "").startswith("application/json") else r.read().decode()
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            body = json.loads(body)
        except Exception:
            pass
        return e.code, body


def main():
    if not TOKEN:
        print("Set TOKEN env var (Bearer token from browser console)")
        print("  const { data } = await supabase.auth.getSession();")
        print("  console.log(data.session?.access_token);")
        sys.exit(1)

    print("=== Test 1: Upload document (playbook, growth) ===")
    # Use upload/url with a real URL - or create minimal test file
    # For simplicity we use a known-good URL
    status, resp = req(
        "POST",
        "/api/knowledge/upload/url",
        json_body={
            "url": "https://example.com",
            "title": "Test Playbook",
            "doc_type": "playbook",
            "domain": "growth",
        },
    )
    if status != 202:
        print(f"  FAIL: expected 202, got {status} {resp}")
        sys.exit(1)
    doc_id = resp.get("document_id")
    print(f"  OK: document_id={doc_id}, status={resp.get('status')} (async ingest)")

    print("\n=== Test 2: GET /api/knowledge ===")
    status, resp = req("GET", "/api/knowledge")
    if status != 200:
        print(f"  FAIL: {status} {resp}")
        sys.exit(1)
    docs = [d for d in resp if d.get("document_id") == doc_id]
    if not docs:
        print(f"  FAIL: document not in list. Got {len(resp)} docs")
        sys.exit(1)
    print(f"  OK: document visible, status={docs[0].get('status')}")

    print("\n=== Test 3: POST approve ===")
    status, resp = req(
        "POST",
        f"/api/knowledge/{doc_id}/approve",
        json_body={"change_note": "eerste goedkeuring"},
    )
    if status != 200:
        print(f"  FAIL: {status} {resp}")
        sys.exit(1)
    print(f"  OK: status={resp.get('status')}, version={resp.get('version')}")

    print("\n=== Test 4: GET /api/knowledge/{id} ===")
    status, resp = req("GET", f"/api/knowledge/{doc_id}")
    if status != 200:
        print(f"  FAIL: {status} {resp}")
        sys.exit(1)
    versions = resp.get("versions", [])
    chunk_count = resp.get("chunk_count", 0)
    print(f"  OK: versions={len(versions)}, chunk_count={chunk_count}")
    if not versions:
        print("  WARN: versions array empty")
    if chunk_count == 0:
        print("  WARN: chunk_count is 0")

    print("\n=== Test 5: 4-eyes blokkade (policy zonder second_approver) ===")
    status2, resp2 = req(
        "POST",
        "/api/knowledge/upload/url",
        json_body={
            "url": "https://example.com",
            "title": "Test Policy",
            "doc_type": "policy",
            "domain": "compliance",
        },
    )
    if status2 != 202:
        print(f"  FAIL: upload policy expected 202, got {status2} {resp2}")
        sys.exit(1)
    policy_id = resp2.get("document_id")
    status3, resp3 = req(
        "POST",
        f"/api/knowledge/{policy_id}/approve",
        json_body={},
    )
    if status3 != 400:
        print(f"  FAIL: expected 400, got {status3} {resp3}")
        sys.exit(1)
    print(f"  OK: 400 returned as expected")

    print("\n=== All 5 tests passed ===")


if __name__ == "__main__":
    main()
