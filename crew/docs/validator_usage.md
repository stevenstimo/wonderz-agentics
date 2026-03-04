# Response Contract and Lessons Tooling Usage

## 1) Validate response contract

Command:
```bash
ruby crew/scripts/validate_response_contract.rb \
  crew/agents/dave-dev.profile.yml \
  crew/examples/responses/pass_layout_1.md
```

Expected output:
```text
PASS: response_contract validation succeeded
```

JSON output mode:
```bash
ruby crew/scripts/validate_response_contract.rb --json \
  crew/agents/dave-dev.profile.yml \
  crew/examples/responses/fail_manual_mode.md
```

Expected JSON fields:
- `pass` (boolean)
- `error_count` (integer)
- `errors[]` (array of contract violations)
- `profile`
- `response_file`

Exit codes:
- `0`: pass
- `1`: contract failure
- `2`: usage/input error

## 2) Append lesson (append or update)

Append example:
```bash
ruby crew/scripts/append_lesson.rb \
  --agent-id dave-dev \
  --context-type layout_inconsistency \
  --what-worked "Compare target and baseline max-w classes" \
  --where-path web_ui/frontend/src \
  --where-file web_ui/frontend/src/HRImprovements.jsx \
  --evidence "web_ui/frontend/src/HRImprovements.jsx:149:className=\"max-w-5xl mx-auto\"" \
  --source task_success \
  --confidence 0.92 \
  --json
```

Expected output:
- `status: ok`
- `lesson_file: crew/lessons/dave-dev.jsonl`
- `lesson_id: lesson-...`

Update example (replace by id if exists, else append):
```bash
ruby crew/scripts/append_lesson.rb \
  --agent-id dave-dev \
  --context-type layout_inconsistency \
  --what-worked "Use md:grid-cols-1 on medium screens" \
  --where-path web_ui/frontend/src \
  --evidence "web_ui/frontend/src/HRImprovements.jsx:198:className=\"grid gap-6 md:grid-cols-1 lg:grid-cols-2\"" \
  --source user_correction \
  --confidence 0.89 \
  --update-id lesson-demo-123 \
  --json
```

## 3) Select lessons (TTL-aware)

Command:
```bash
ruby crew/scripts/select_lessons.rb \
  --agent-id dave-dev \
  --context-type layout_inconsistency \
  --path-hint HRImprovements \
  --limit 2 \
  --json
```

Expected behavior:
- returns max `limit` lessons,
- excludes expired lessons (`created_at + ttl_days`),
- prioritizes path hint matches and confidence.

## 4) Run contract test suite

Command:
```bash
bash crew/scripts/test_response_contract.sh
```

Expected output:
```text
Running PASS cases...
PASS ok: ...
Running FAIL cases...
FAIL ok: ...
PASS: response contract test suite completed
```

## 5) Validate profile/playbook framework

Command:
```bash
ruby crew/scripts/validate_agent_framework.rb
```

Expected output:
```json
{"status":"PASS","checked_agents":3,"checked_playbooks":2}
```

Validate intent routes profile -> playbook:
```bash
ruby crew/scripts/validate_intent_routes.rb
```

Expected output:
```json
{"status":"PASS","checked_routes":5,"playbooks":["backend_data_trace","layout_inconsistency_diff"]}
```

## 6) Run full check bundle

Command:
```bash
bash crew/scripts/run_all_checks.sh
```

Expected output:
```text
[1/10] Validate agent/profile + playbook framework
[2/10] Validate intent route mapping
[3/10] Validate intent classifier
[4/10] Validate intent ambiguity handling
[5/10] Validate response contract examples
[6/10] Append one lesson sample
[7/10] Select active lessons sample
[8/10] Runtime orchestrator smoke
[9/10] Runtime failure taxonomy checks
[10/10] Runtime missing-path handling checks
PASS: run_all_checks completed
```

Intent classifier checks:
```bash
bash crew/scripts/test_intent_classification.sh
```

Intent ambiguity checks:
```bash
bash crew/scripts/test_intent_ambiguity.sh
```

## 6b) Runtime orchestrator smoke

Command:
```bash
bash crew/scripts/test_runtime.sh
```

Expected output:
```text
[runtime 1/3] run orchestrator happy-path
[runtime 2/3] validate JSON summary fields
[runtime 3/3] validate response contract
PASS: runtime smoke + contract checks
```

Failure taxonomy checks:
```bash
bash crew/scripts/test_runtime_failures.sh
```

Missing-path handling checks:
```bash
bash crew/scripts/test_runtime_missing_paths.sh
```

## 7) Generate KPI report

Command:
```bash
ruby crew/scripts/kpi_report.rb
```

Output:
- JSON with `contract_pass_rate`, `manual_mode_violation_rate`, and lesson coverage metrics.

## 8) Bootstrap lesson files from profiles

Command:
```bash
ruby crew/scripts/bootstrap_lessons.rb
```

Output:
- reports `created` and `skipped` lesson files derived from `learning.lessons_file`.

## 9) CI workflow

GitHub Actions workflow file:
- `.github/workflows/crew-agent-framework.yml`

Pipeline jobs:
- `ruby-syntax`: runs `crew/scripts/check_ruby_syntax.sh`
- `framework-lint`: runs `validate_agent_framework.rb`, `test_intent_classification.sh`, `test_intent_ambiguity.sh`, `test_response_contract.sh`, `test_runtime.sh`, `test_runtime_failures.sh`, and `test_runtime_missing_paths.sh`
- `full-bundle`: runs `run_all_checks.sh`

## 10) Scaffold a new agent profile

Dry run:
```bash
ruby crew/scripts/new_agent_profile.rb \
  --agent-id qa-worker \
  --display-name "QA Worker" \
  --role worker \
  --dry-run
```

Write file:
```bash
ruby crew/scripts/new_agent_profile.rb \
  --agent-id qa-worker \
  --display-name "QA Worker" \
  --role worker
```

Smoke-test one agent profile:
```bash
bash crew/scripts/smoke_agent_profile.sh dave-dev
```

## 11) Install local pre-commit checks (optional)

```bash
bash crew/scripts/install_git_hooks.sh
```

If the repository has `.git`, this installs a `pre-commit` hook that runs:
- `check_ruby_syntax.sh`
- `validate_agent_framework.rb`
- `test_response_contract.sh`

## 12) Export a verification report

```bash
bash crew/scripts/export_verification_report.sh
```

Output:
- creates:
  - `crew/reports/verification_<UTC_TIMESTAMP>.md`
  - `crew/reports/verification_<UTC_TIMESTAMP>.json`
