#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp /tmp/crew_intent_ambig.XXXXXX)"
cleanup() { rm -f "$TMP"; }
trap cleanup EXIT

echo "[ambiguity 1/2] trigger ambiguous classifier path"
set +e
ruby "$ROOT/scripts/run_agent.rb" \
  --agent-id dave-dev \
  --query "help" \
  --json > "$TMP"
RC=$?
set -e

if [ "$RC" -eq 0 ]; then
  echo "Expected non-zero exit code for needs_clarification"
  exit 1
fi

echo "[ambiguity 2/2] validate summary/status/response"
ruby -rjson -e 'j=JSON.parse(File.read(ARGV[0])); raise "status mismatch" unless j["status"]=="needs_clarification"; raise "missing response" unless j["response"].to_s.include?("Bedoel je"); fs=Array(j["failures"]); raise "missing intent_ambiguous failure" unless fs.any? { |f| f["type"]=="intent_ambiguous" }; puts "ok"' "$TMP" >/dev/null

echo "PASS: intent ambiguity checks"
