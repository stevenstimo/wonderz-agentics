#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
JSON_OUT="$ROOT/reports/runtime_health_${TS}.json"
MD_OUT="$ROOT/reports/runtime_health_${TS}.md"

KPI_JSON="$(ruby "$ROOT/scripts/runtime_kpi_report.rb" --since-hours 24)"
GAP_JSON="$(ruby "$ROOT/scripts/runtime_gap_report.rb" --since-hours 24)"

printf '{\n  "generated_at": "%s",\n  "kpi": %s,\n  "gaps": %s\n}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$KPI_JSON" "$GAP_JSON" > "$JSON_OUT"

cat > "$MD_OUT" <<EOF
# Runtime Health Report

Generated at: $(date -u +%Y-%m-%dT%H:%M:%SZ)

## KPI (last 24h)

\`\`\`json
$KPI_JSON
\`\`\`

## Gaps (last 24h)

\`\`\`json
$GAP_JSON
\`\`\`
EOF

echo "PASS: runtime health report exported"
echo "- json: $JSON_OUT"
echo "- md:   $MD_OUT"
