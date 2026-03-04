#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

TMP_JSON="$(mktemp /tmp/crew_runtime_summary.XXXXXX.json)"
TMP_MD="$(mktemp /tmp/crew_runtime_response.XXXXXX.md)"
cleanup() {
  rm -f "$TMP_JSON" "$TMP_MD"
}
trap cleanup EXIT

echo "[runtime 1/3] run orchestrator happy-path"
ruby "$ROOT/scripts/run_agent.rb" \
  --agent-id dave-dev \
  --intent layout_inconsistency \
  --page-name HRImprovements \
  --path-hint HRImprovements \
  --json > "$TMP_JSON"

echo "[runtime 2/3] validate JSON summary fields"
ruby -rjson -e 'j = JSON.parse(File.read(ARGV[0])); raise "missing status" unless j["status"]; raise "missing response" unless j["response"]; puts "ok"' "$TMP_JSON" >/dev/null

ruby -rjson -e 'j = JSON.parse(File.read(ARGV[0])); File.write(ARGV[1], j.fetch("response"))' "$TMP_JSON" "$TMP_MD"

echo "[runtime 3/3] validate response contract"
ruby "$ROOT/scripts/validate_response_contract.rb" "$ROOT/agents/dave-dev.profile.yml" "$TMP_MD" >/dev/null

echo "PASS: runtime smoke + contract checks"
