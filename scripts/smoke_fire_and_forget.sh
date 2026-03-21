#!/usr/bin/env bash
# Fase 6 — Fire-and-forget smoke tests (curl-only where possible).
# Usage:
#   export ACCESS_TOKEN='eyJ...'   # Supabase JWT (same as UI)
#   export BASE_URL='http://127.0.0.1:8090'   # optional
#   export CLIENT_SLUG='my-client'            # optional, for datasource test
#   export AGENT_ID='agent:copywriter'        # optional, for training test
#   ./scripts/smoke_fire_and_forget.sh
#
# Test C (worker crash) is destructive; run only when intended:
#   RUN_CRASH_TEST=1 ./scripts/smoke_fire_and_forget.sh
#
# Before Test C: set FIRE_AND_FORGET_STUCK_MINUTES=1 on crew-worker (and optionally wonderz-backend)
# overrides, daemon-reload, restart. After Test C: remove override and restart again.

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8090}"
BASE_URL="${BASE_URL%/}"

die() { echo "ERROR: $*" >&2; exit 1; }

[[ -n "${ACCESS_TOKEN:-}" ]] || die "Set ACCESS_TOKEN to a valid Bearer JWT (Supabase)."

HDR=(-H "Authorization: Bearer ${ACCESS_TOKEN}" -H "Content-Type: application/json")

echo "=== Fase 6 — BASE_URL=$BASE_URL ==="

# --- Test A (knowledge): 202 + pending, poll embedding_status ---
echo ""
echo "--- Test A — Knowledge URL upload (pending → processing → complete|failed) ---"
code=$(curl -sS -o /tmp/ff_k_resp.json -w "%{http_code}" -X POST "${BASE_URL}/api/knowledge/upload/url" \
  "${HDR[@]}" \
  -d '{"url":"https://example.com","title":"Smoke example","doc_type":"sop","domain":"core","function_tag":"general"}')
body=$(cat /tmp/ff_k_resp.json)
echo "POST /api/knowledge/upload/url HTTP $code"
echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
[[ "$code" == "202" ]] || die "Expected HTTP 202 for knowledge URL upload"
doc_id=$(python3 -c "import json; print(json.load(open('/tmp/ff_k_resp.json')).get('document_id',''))" 2>/dev/null || true)
[[ -n "$doc_id" ]] || die "No document_id in response"
st=$(python3 -c "import json; print(json.load(open('/tmp/ff_k_resp.json')).get('status',''))" 2>/dev/null || true)
[[ "$st" == "pending" ]] || die "Expected status pending in JSON, got: $st"

echo "Polling GET /api/knowledge/$doc_id (embedding_status) ..."
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  emb=$(curl -sS "${BASE_URL}/api/knowledge/${doc_id}" "${HDR[@]}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('embedding_status',''))" 2>/dev/null || echo "")
  echo "  attempt $i: embedding_status=$emb"
  if [[ "$emb" == "complete" || "$emb" == "failed" ]]; then
    echo "Test A (knowledge): OK (terminal embedding_status=$emb)"
    break
  fi
  sleep 3
done
if [[ "${emb:-}" != "complete" && "${emb:-}" != "failed" ]]; then
  die "Knowledge poll did not reach complete/failed within ~60s (last=$emb)"
fi

# --- Test B (knowledge): same as A pattern — POST then sleep without holding connection ---
echo ""
echo "--- Test B — Knowledge 'browser weg' (POST, sleep 30s, no extra requests, then poll) ---"
code=$(curl -sS -o /tmp/ff_k2_resp.json -w "%{http_code}" -X POST "${BASE_URL}/api/knowledge/upload/url" \
  "${HDR[@]}" \
  -d '{"url":"https://example.org","title":"Smoke gap","doc_type":"sop","domain":"core","function_tag":"general"}')
[[ "$code" == "202" ]] || die "Test B: expected 202"
doc_id2=$(python3 -c "import json; print(json.load(open('/tmp/ff_k2_resp.json'))['document_id'])")
echo "Sleep 30s (simulating closed browser)..."
sleep 30
emb2=""
for i in 1 2 3 4 5 6 7 8 9 10; do
  emb2=$(curl -sS "${BASE_URL}/api/knowledge/${doc_id2}" "${HDR[@]}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('embedding_status',''))" 2>/dev/null || echo "")
  echo "  poll $i: embedding_status=$emb2"
  [[ "$emb2" == "complete" || "$emb2" == "failed" || "$emb2" == "processing" ]] && break
  sleep 3
done
[[ "$emb2" == "pending" ]] && die "Test B: still pending after gap — worker may be down"
echo "Test B (knowledge): OK (embedding_status=$emb2)"

# --- Optional: datasource (needs CLIENT_SLUG) ---
if [[ -n "${CLIENT_SLUG:-}" ]]; then
  echo ""
  echo "--- Test A/B — Datasource create (202 + enqueue) ---"
  code=$(curl -sS -o /tmp/ff_ds.json -w "%{http_code}" -X POST "${BASE_URL}/api/clients/${CLIENT_SLUG}/datasources" \
    "${HDR[@]}" \
    -d '{"name":"smoke-crawl","source_type":"website_crawl","domain":"example.com"}')
  echo "POST datasources HTTP $code"
  cat /tmp/ff_ds.json | python3 -m json.tool
  [[ "$code" == "202" ]] || die "Expected 202 for datasource create"
  ds_id=$(python3 -c "import json; print(json.load(open('/tmp/ff_ds.json'))['datasource_id'])")
  for i in 1 2 3 4 5 6 7 8 9 10; do
    st=$(curl -sS "${BASE_URL}/api/clients/${CLIENT_SLUG}/datasources/${ds_id}/status" "${HDR[@]}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
    echo "  datasource status: $st"
    [[ "$st" == "done" || "$st" == "failed" ]] && break
    sleep 5
  done
  echo "Datasource smoke: last status=$st"
fi

# --- Optional: agent training ---
if [[ -n "${AGENT_ID:-}" ]]; then
  echo ""
  echo "--- Agent training POST (202 + pending) ---"
  code=$(curl -sS -o /tmp/ff_tr.json -w "%{http_code}" -X POST "${BASE_URL}/api/agents/${AGENT_ID}/train" \
    "${HDR[@]}" \
    -d '{"url":"https://example.com","approved_by":"smoke"}')
  echo "HTTP $code"
  cat /tmp/ff_tr.json | python3 -m json.tool
  [[ "$code" == "202" ]] || die "Expected 202 for train"
fi

# --- Test C: worker crash (optional) ---
if [[ "${RUN_CRASH_TEST:-}" == "1" ]]; then
  echo ""
  echo "--- Test C — Worker crash recovery (requires sudo + FIRE_AND_FORGET_STUCK_MINUTES=1 on worker) ---"
  echo "Starting knowledge job..."
  code=$(curl -sS -o /tmp/ff_kc.json -w "%{http_code}" -X POST "${BASE_URL}/api/knowledge/upload/url" \
    "${HDR[@]}" \
    -d '{"url":"https://example.net","title":"Crash test","doc_type":"sop","domain":"core","function_tag":"general"}')
  [[ "$code" == "202" ]] || die "Crash test: 202 expected"
  rid=$(python3 -c "import json; print(json.load(open('/tmp/ff_kc.json'))['document_id'])")
  echo "document_id=$rid — wait until embedding_status=processing, then: sudo systemctl stop crew-worker"
  for i in $(seq 1 40); do
    emb=$(curl -sS "${BASE_URL}/api/knowledge/${rid}" "${HDR[@]}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('embedding_status',''))" 2>/dev/null || echo "")
    echo "  $emb"
    [[ "$emb" == "processing" ]] && break
    sleep 2
  done
  [[ "$emb" == "processing" ]] || die "Never saw processing; cannot crash worker mid-job meaningfully"
  echo "Run manually now: sudo systemctl stop crew-worker && sleep 15 && sudo systemctl start crew-worker"
  echo "Then wait > FIRE_AND_FORGET_STUCK_MINUTES (e.g. 65s if set to 1) and/or restart backend to run recovery."
  echo "Check: curl -s ${BASE_URL}/api/knowledge/${rid} -H \"Authorization: Bearer ...\" | jq .embedding_status"
  if [[ -t 0 ]]; then
    read -r -p "Press Enter after worker restart + wait for recovery timeout..."
  else
    echo "(non-interactive: set rid=$rid and check embedding_status after recovery)"
  fi
  emb=$(curl -sS "${BASE_URL}/api/knowledge/${rid}" "${HDR[@]}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('embedding_status',''))" 2>/dev/null || echo "")
  echo "Final embedding_status=$emb (expect failed if recovery ran and job was stuck)"
else
  echo ""
  echo "--- Test C skipped (set RUN_CRASH_TEST=1 to include manual crash steps) ---"
fi

echo ""
echo "=== Fase 6 smoke script finished ==="
