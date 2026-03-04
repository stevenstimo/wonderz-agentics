#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/10] Validate agent/profile + playbook framework"
ruby "$ROOT/scripts/validate_agent_framework.rb"

echo "[2/10] Validate intent route mapping"
ruby "$ROOT/scripts/validate_intent_routes.rb"

echo "[3/10] Validate intent classifier"
bash "$ROOT/scripts/test_intent_classification.sh"

echo "[4/10] Validate intent ambiguity handling"
bash "$ROOT/scripts/test_intent_ambiguity.sh"

echo "[5/10] Validate response contract examples"
bash "$ROOT/scripts/test_response_contract.sh"

echo "[6/10] Append one lesson sample"
ruby "$ROOT/scripts/append_lesson.rb" \
  --agent-id dave-dev \
  --context-type layout_inconsistency \
  --what-worked "Compare wrapper and baseline classes" \
  --where-path web_ui/frontend/src \
  --evidence 'web_ui/frontend/src/HRImprovements.jsx:149:className="max-w-5xl mx-auto"' \
  --source task_success \
  --confidence 0.9 \
  --json >/dev/null

echo "[7/10] Select active lessons sample"
ruby "$ROOT/scripts/select_lessons.rb" \
  --agent-id dave-dev \
  --context-type layout_inconsistency \
  --limit 2 \
  --json >/dev/null

echo "[8/10] Runtime orchestrator smoke"
bash "$ROOT/scripts/test_runtime.sh"

echo "[9/10] Runtime failure taxonomy checks"
bash "$ROOT/scripts/test_runtime_failures.sh"

echo "[10/10] Runtime missing-path handling checks"
bash "$ROOT/scripts/test_runtime_missing_paths.sh"

echo "PASS: run_all_checks completed"
