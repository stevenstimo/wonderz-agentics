#!/usr/bin/env bash
# Check backend logs for job pipeline activity.
# Run from repo root. Uses /var/log/wonderz/app.log if available.

LOG_FILE="${LOG_FILE:-/var/log/wonderz/app.log}"
echo "=== Pipeline log check (${LOG_FILE}) ==="
echo ""

echo "1. Approve + task queued (route):"
grep -E "Approving plan for job|Job execution task queued" "$LOG_FILE" 2>/dev/null | tail -10
echo ""

echo "2. run_job_inline started (pipeline):"
grep "run_job_inline started" "$LOG_FILE" 2>/dev/null | tail -10
echo ""

echo "3. Steps count (job X has N steps):"
grep "steps to run" "$LOG_FILE" 2>/dev/null | tail -10
echo ""

echo "4. Fallback (had no job_steps; inserted):"
grep "had no job_steps\|inserted.*from context.plan" "$LOG_FILE" 2>/dev/null | tail -5
echo ""

echo "5. Recent ERROR / exception (pipeline or jobs):"
grep -E '"level": "ERROR"' "$LOG_FILE" 2>/dev/null | tail -5
echo ""

echo "6. Any app.services.job_pipeline logs:"
grep "app.services.job_pipeline" "$LOG_FILE" 2>/dev/null | wc -l
