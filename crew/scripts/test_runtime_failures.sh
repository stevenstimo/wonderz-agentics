#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_ID="run-failtest-$(date +%s)"
TMP_JSON="$(mktemp /tmp/crew_runtime_fail.XXXXXX.json)"
cleanup() {
  rm -f "$TMP_JSON"
}
trap cleanup EXIT

echo "[failure 1/3] force non-accept run via high threshold"
set +e
ruby "$ROOT/scripts/run_agent.rb" \
  --agent-id frontend-worker \
  --intent layout_inconsistency \
  --page-name HRImprovements \
  --path-hint HRImprovements \
  --min-accept-score 1.1 \
  --run-id "$RUN_ID" \
  --json > "$TMP_JSON"
RC=$?
set -e

if [ "$RC" -eq 0 ]; then
  echo "Expected non-zero exit code for needs_approval run"
  exit 1
fi

echo "[failure 2/3] verify status and failure entries"
ruby -rjson -e 'j = JSON.parse(File.read(ARGV[0])); raise "unexpected status" unless j["status"] == "needs_approval"; fs = j["failures"] || []; raise "expected failure record" if fs.empty?; puts "ok"' "$TMP_JSON" >/dev/null

echo "[failure 3/3] verify retry_exhausted in runtime log"
ruby -rjson -e 'found=false; File.readlines(ARGV[0], chomp: true).each { |line| row=JSON.parse(line) rescue nil; next unless row.is_a?(Hash); if row["type"]=="failure" && row.dig("failure","type")=="retry_exhausted" then found=true; end }; raise "retry_exhausted missing" unless found; puts "ok"' "$ROOT/reports/runs/${RUN_ID}.jsonl" >/dev/null

echo "PASS: runtime failure taxonomy checks"
