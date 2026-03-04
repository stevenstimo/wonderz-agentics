# Runtime Operations

## Output Channels
- Human response: stdout in response-contract format.
- Machine summary: `--json` output from `run_agent.rb`.
- Event stream: `crew/reports/runs/<run_id>.jsonl`.

## Key Runtime Events
- `run_started`
- `intent_classified`
- `playbook_routed`
- `lessons_loaded`
- `step_finished`
- `llm_call`
- `llm_skipped`
- `evaluation_finished`
- `decision_made`
- `lesson_appended`
- `run_completed`
- `run_failed`

## Failure Taxonomy
- `contract_failed`: response failed contract validator.
- `tool_execution_failed`: key step command failed.
- `missing_workspace_path`: configured or inferred workspace path does not exist.
- `governance_blocked`: command blocked by policy.
- `timeout`: max runtime exceeded.
- `retry_exhausted`: evaluation still non-accept after max retries.
- `runtime_error`: unexpected runtime exception outside known classes.
- `intent_ambiguous`: classifier confidence/margin te laag; user clarification nodig.

## Runtime KPI Seeds
- Retry count per intent.
- Step success ratio.
- LLM usage (`prompt_tokens`, `completion_tokens`, `total_tokens`) and LLM latency.
- Evaluation total score.
- Contract pass rate.
- Lesson hit rate per context type.
- Gap hotspots by intent/failure type via `runtime_gap_report.rb`.

## Export Health Snapshot
```bash
bash crew/scripts/export_runtime_health_report.sh
```

Output files:
- `crew/reports/runtime_health_<UTC_TIMESTAMP>.json`
- `crew/reports/runtime_health_<UTC_TIMESTAMP>.md`

## Smoke Commands
```bash
bash crew/scripts/test_runtime.sh
bash crew/scripts/smoke_agent_profile.sh dave-dev
```
