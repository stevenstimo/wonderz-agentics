.PHONY: syntax framework routes intent intent-ambiguity contract runtime runtime-fail runtime-missing-paths lessons-select checks kpi report runtime-kpi runtime-gap runtime-health bootstrap smoke

syntax:
	bash scripts/check_ruby_syntax.sh

framework:
	ruby scripts/validate_agent_framework.rb

routes:
	ruby scripts/validate_intent_routes.rb

intent:
	bash scripts/test_intent_classification.sh

intent-ambiguity:
	bash scripts/test_intent_ambiguity.sh

contract:
	bash scripts/test_response_contract.sh

runtime:
	bash scripts/test_runtime.sh

runtime-fail:
	bash scripts/test_runtime_failures.sh

runtime-missing-paths:
	bash scripts/test_runtime_missing_paths.sh

checks:
	bash scripts/run_all_checks.sh

kpi:
	ruby scripts/kpi_report.rb

runtime-kpi:
	ruby scripts/runtime_kpi_report.rb

runtime-gap:
	ruby scripts/runtime_gap_report.rb

runtime-health:
	bash scripts/export_runtime_health_report.sh

report:
	bash scripts/export_verification_report.sh

bootstrap:
	ruby scripts/bootstrap_lessons.rb

smoke:
	bash scripts/smoke_agent_profile.sh dave-dev
	bash scripts/smoke_agent_profile.sh frontend-worker
	bash scripts/smoke_agent_profile.sh research-talent
