# Runtime Architecture

## Central Loop
The runtime uses a single orchestrator state machine:
1. `intake`
2. `classify`
3. `route`
4. `preload_lessons`
5. `plan`
6. `execute`
7. `evaluate`
8. `decide`
9. `learn`
10. `persist`
11. `done`

This prevents agent behavior drift and keeps all retries, evaluations, and logging in one control point.

## Separation of Concerns
- `DecisionEngine`: trigger-driven intent classification, playbook routing, retry decision.
- `ExecutionEngine`: command rendering/execution and step timing.
- `LlmClient`: optional provider adapter for cause/fix synthesis (fallback remains deterministic).
- `Evaluator`: independent quality gate and contract validation.
- `MemoryManager`: lesson retrieval, lesson influence cap, lesson append.
- `Governance`: policy checks for command safety and approval mode.
- `Telemetry`: JSONL run event stream per run.

## Intent Classification
- Primary signal: overlap with configured playbook trigger phrases (`triggers.any_of`).
- Secondary signal: intent-specific keyword hints.
- Confidence is margin-calibrated using top score vs second-best score.
- Classification reason is logged and reused in routing decision metadata.

## Guardrails
- `max_retries`: retry limit before escalation.
- `max_depth`: recursion/retry depth cap.
- `max_runtime_seconds`: wall clock limit per run.
- `max_lesson_influence`: max lessons that can shape one run.

## Entry Command
```bash
ruby crew/scripts/run_agent.rb \
  --agent-id dave-dev \
  --intent layout_inconsistency \
  --page-name HRImprovements \
  --path-hint HRImprovements \
  --json
```

## Optional LLM Mode
LLM is profile-controlled and disabled by default (`llm.enabled: false`).

Enable for a run:
```bash
OPENAI_API_KEY=... ruby crew/scripts/run_agent.rb \
  --agent-id dave-dev \
  --intent layout_inconsistency \
  --query "waarom is deze pagina smaller?" \
  --llm-enabled true \
  --llm-model gpt-4o-mini \
  --json
```
