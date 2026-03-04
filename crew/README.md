# Crew Agent Framework

Production-ready framework for Crew Intelligent Workers and Talents:
- agent profile contracts,
- playbook contracts,
- response contract validation,
- lessons learned append/select tooling,
- automated checks and reporting.

## Quick Start

```bash
cd "/Users/timo/Documents/Codex/Shopify Descriptions"
bash crew/scripts/run_all_checks.sh
```

## Core Scripts

- Validate profile/playbook framework:
  - `ruby crew/scripts/validate_agent_framework.rb`
- Validate intent routing profile -> playbook:
  - `ruby crew/scripts/validate_intent_routes.rb`
- Validate intent classification:
  - `bash crew/scripts/test_intent_classification.sh`
  - `bash crew/scripts/test_intent_ambiguity.sh`
- Validate response contract examples:
  - `bash crew/scripts/test_response_contract.sh`
- Validate runtime orchestrator:
  - `bash crew/scripts/test_runtime.sh`
  - `bash crew/scripts/test_runtime_failures.sh`
  - `bash crew/scripts/test_runtime_missing_paths.sh`
- Validate a single response:
  - `ruby crew/scripts/validate_response_contract.rb crew/agents/dave-dev.profile.yml crew/examples/responses/pass_layout_1.md`
- Append lesson:
  - `ruby crew/scripts/append_lesson.rb --agent-id dave-dev --context-type layout_inconsistency --what-worked "Compare wrappers" --where-path web_ui/frontend/src --evidence 'web_ui/frontend/src/HRImprovements.jsx:149:className="max-w-5xl mx-auto"' --source task_success --confidence 0.9 --json`
- Select active lessons:
  - `ruby crew/scripts/select_lessons.rb --agent-id dave-dev --context-type layout_inconsistency --limit 2 --json`
- KPI report:
  - `ruby crew/scripts/kpi_report.rb`
- Runtime KPI report:
  - `ruby crew/scripts/runtime_kpi_report.rb`
  - `ruby crew/scripts/runtime_kpi_report.rb --since-hours 24`
- Runtime gap report:
  - `ruby crew/scripts/runtime_gap_report.rb`
  - `ruby crew/scripts/runtime_gap_report.rb --since-hours 24`
- Runtime health export (JSON + Markdown):
  - `bash crew/scripts/export_runtime_health_report.sh`
- Export verification report:
  - `bash crew/scripts/export_verification_report.sh`
- Run agent runtime (intent -> playbook -> response):
  - `ruby crew/scripts/run_agent.rb --agent-id dave-dev --intent layout_inconsistency --page-name HRImprovements --path-hint HRImprovements`
  - `ruby crew/scripts/run_agent.rb --agent-id dave-dev --intent api_or_data_issue --keyword dave-dev --path-hint web_ui/backend`
  - JSON summary + telemetry: `ruby crew/scripts/run_agent.rb --agent-id dave-dev --intent layout_inconsistency --query "waarom is HR smaller?" --json`
  - Optional LLM mode: `OPENAI_API_KEY=... ruby crew/scripts/run_agent.rb --agent-id dave-dev --intent layout_inconsistency --query "waarom is HR smaller?" --llm-enabled true --llm-model gpt-4o-mini --json`

## Makefile Shortcuts

```bash
cd crew
make syntax
make framework
make routes
make intent
make intent-ambiguity
make contract
make runtime
make runtime-fail
make runtime-missing-paths
make smoke
make checks
make kpi
make runtime-kpi
make runtime-gap
make runtime-health
make report
```

## CI

Workflow:
- `.github/workflows/crew-agent-framework.yml`

Jobs:
- Ruby syntax check,
- framework lint + response + runtime tests,
- full check bundle.

Runtime docs:
- `crew/docs/runtime_architecture.md`
- `crew/docs/runtime_operations.md`

## Local Quality Gate

If repository has `.git`:
```bash
bash crew/scripts/install_git_hooks.sh
```

This installs a pre-commit hook running syntax + framework + contract checks.
