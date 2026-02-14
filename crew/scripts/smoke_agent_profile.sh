#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: bash crew/scripts/smoke_agent_profile.sh <agent-id>"
  exit 2
fi

AGENT_ID="$1"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="$ROOT/agents/${AGENT_ID}.profile.yml"

if [ ! -f "$PROFILE" ]; then
  echo "Profile not found: $PROFILE"
  exit 2
fi

TMP_RESPONSE="$(mktemp /tmp/crew_smoke_response.XXXXXX.md)"
cleanup() {
  rm -f "$TMP_RESPONSE"
}
trap cleanup EXIT

PROFILE_PATH="$PROFILE" TMP_PATH="$TMP_RESPONSE" ruby <<'RUBY'
require 'yaml'
profile = YAML.load_file(ENV.fetch('PROFILE_PATH'))
closing_question = profile.dig('response_contract', 'closing_question') || 'Wil je dat ik deze wijziging direct doorvoer?'
content = <<~MD
Gevonden:
- `web_ui/frontend/src/HRImprovements.jsx:149` -> `className="max-w-5xl mx-auto"`

Oorzaak:
- Containerafwijking vastgesteld op basis van class-vergelijking.

Fix voorstel:
- Houd wrapper gelijk aan baseline en pas grid-breakpoint aan.
- Command: `echo "smoke"`

Vraag:
- #{closing_question}
MD
File.write(ENV.fetch('TMP_PATH'), content)
RUBY

echo "[smoke] agent=$AGENT_ID"
echo "[1/4] Validate response contract against pass sample"
ruby "$ROOT/scripts/validate_response_contract.rb" "$PROFILE" "$TMP_RESPONSE" >/dev/null

echo "[2/4] Run orchestrator runtime flow"
ruby "$ROOT/scripts/run_agent.rb" \
  --agent-id "$AGENT_ID" \
  --intent layout_inconsistency \
  --page-name HRImprovements \
  --path-hint HRImprovements \
  --json >/dev/null

echo "[3/4] Select active lessons (non-failing even if empty)"
ruby "$ROOT/scripts/select_lessons.rb" \
  --agent-id "$AGENT_ID" \
  --context-type layout_inconsistency \
  --limit 2 \
  --json >/dev/null

echo "[4/4] Validate intent routing map"
ruby "$ROOT/scripts/validate_intent_routes.rb" >/dev/null

echo "PASS: smoke_agent_profile completed for ${AGENT_ID}"
