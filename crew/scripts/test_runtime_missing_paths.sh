#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp /tmp/crew_runtime_missing_paths.XXXXXX)"
cleanup() { rm -f "$TMP"; }
trap cleanup EXIT

echo "[missing-path 1/2] run with profile that points to non-existing web_ui paths"
ruby "$ROOT/scripts/run_agent.rb" \
  --agent-id frontend-worker \
  --intent layout_inconsistency \
  --page-name HRImprovements \
  --path-hint HRImprovements \
  --json > "$TMP"

echo "[missing-path 2/2] validate missing_workspace_path failure typing"
ruby -rjson -e 'j=JSON.parse(File.read(ARGV[0])); fs=Array(j["failures"]); raise "missing failure" if fs.empty?; raise "missing type not found" unless fs.any? { |f| f["type"]=="missing_workspace_path" }; raise "old tool failure still present" if fs.any? { |f| f["type"]=="tool_execution_failed" }; puts "ok"' "$TMP" >/dev/null

echo "PASS: runtime missing-path handling checks"
