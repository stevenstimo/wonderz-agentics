#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP1="$(mktemp /tmp/crew_intent1.XXXXXX)"
TMP2="$(mktemp /tmp/crew_intent2.XXXXXX)"
TMP3="$(mktemp /tmp/crew_intent3.XXXXXX)"
cleanup() { rm -f "$TMP1" "$TMP2" "$TMP3"; }
trap cleanup EXIT

echo "[intent 1/3] classify layout query for dave-dev"
ruby "$ROOT/scripts/run_agent.rb" \
  --agent-id dave-dev \
  --query "waarom is deze pagina smaller dan devbot" \
  --page-name HRImprovements \
  --path-hint HRImprovements \
  --json > "$TMP1"
ruby -rjson -e 'j=JSON.parse(File.read(ARGV[0])); raise "intent mismatch" unless j["intent"]=="layout_inconsistency"; raise "low confidence" if j.dig("evaluation","total_score").to_f <= 0.0' "$TMP1" >/dev/null

echo "[intent 2/3] classify backend query for dave-dev"
ruby "$ROOT/scripts/run_agent.rb" \
  --agent-id dave-dev \
  --query "api endpoint faalt en data komt niet door" \
  --keyword endpoint \
  --path-hint web_ui/backend \
  --json > "$TMP2"
ruby -rjson -e 'j=JSON.parse(File.read(ARGV[0])); raise "intent mismatch" unless j["intent"]=="api_or_data_issue"' "$TMP2" >/dev/null

echo "[intent 3/3] classify architecture query for research-talent"
ruby "$ROOT/scripts/run_agent.rb" \
  --agent-id research-talent \
  --query "kun je de architectuur en data flow uitleggen" \
  --path-hint docs \
  --json > "$TMP3"
ruby -rjson -e 'j=JSON.parse(File.read(ARGV[0])); raise "intent mismatch" unless j["intent"]=="architecture_or_explanation"' "$TMP3" >/dev/null

echo "PASS: intent classification checks"
