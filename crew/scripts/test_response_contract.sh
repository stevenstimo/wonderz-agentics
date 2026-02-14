#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VALIDATOR="$ROOT/scripts/validate_response_contract.rb"
PROFILE="$ROOT/agents/dave-dev.profile.yml"

pass_files=(
  "$ROOT/examples/responses/pass_layout_1.md"
  "$ROOT/examples/responses/pass_backend_1.md"
)

fail_files=(
  "$ROOT/examples/responses/fail_manual_mode.md"
  "$ROOT/examples/responses/fail_missing_sections.md"
)

echo "Running PASS cases..."
for f in "${pass_files[@]}"; do
  ruby "$VALIDATOR" "$PROFILE" "$f" >/dev/null
  echo "PASS ok: $f"
done

echo "Running FAIL cases..."
for f in "${fail_files[@]}"; do
  if ruby "$VALIDATOR" "$PROFILE" "$f" >/dev/null; then
    echo "FAIL expected but passed: $f"
    exit 1
  fi
  echo "FAIL ok: $f"
done

echo "PASS: response contract test suite completed"
