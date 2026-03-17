# CURSOR PROMPT — Phase 5 CEO Review (NEXUS Pipeline)

**Locatie:** `app/orchestration/nexus_pipeline.py`

**Doel:** Vervang de stub in `phase_5_ceo_review` met echte CEO-reviewlogica volgens Product Spec v1.1, Sectie 4.

**Spec:**  
"CEO beoordeelt eindresultaat tegen originele job post. Tevreden: JOB_READY. Niet tevreden: agent terug zonder gebruiker te lastigvallen."

---

## PRE-FLIGHT CHECK

Voer uit vóór implementatie:

1. **Traceability**  
   Bevestig in codebase:
   - Waar wordt `_run_step_agent_with_timeout` gedefinieerd? (job_pipeline)
   - Waar wordt TokenGuard gebruikt? (token_guard.check_before_call, register_usage)
   - Welke velden op HandoffContext zijn beschikbaar voor phase_5? (step_outputs, execution_plan, strategic_brief, retry_counts, token_budget, token_used_total)

2. **Phase 6 logica**  
   Hoe wordt "laatste output" bepaald in phase_6? (reversed execution_plan, eerste niet-gtm step met output) — hergebruik dezelfde logica in phase_5.

3. **Reviewer output**  
   Welk formaat retourneert de reviewer in job_pipeline? (approved: bool, review: str; "APPROVED" / "CHANGES NEEDED" in tekst)

---

## FASE 1 — Implementatie

Implementeer `phase_5_ceo_review` als volgt:

1. **Laatste output**  
   Haal uit `ctx.step_outputs` dezelfde "final content" als phase_6 (reversed plan, skip gtm_analysis). Geen output → log en return (geen CEO-call).

2. **CEO aanroep**  
   - Token check: `ctx.is_over_budget()` → BudgetExceededError; `TokenGuard.check_before_call(job_id, estimated_tokens=2000)`.
   - Context: StrategicBrief (ctx.strategic_brief), job_post, objective.
   - Vraag aan CEO: beoordeel of de final output matcht met de objective (via bestaande reviewer-rol: "Review this content" + previous_content = final_output).
   - Gebruik `_run_step_agent_with_timeout(agent_role="reviewer", step_name="ceo_review", context=..., previous_content=final_output)`.
   - Na call: `ctx.register_tokens(tokens_used)`, `token_guard.register_usage(job_id, tokens_used, step_id=None)`.

3. **Verdict**  
   - APPROVED (reviewer zegt approved / geen "changes needed") → logger.info, return.
   - NEEDS_REVISION → als `ctx.retry_counts.get("ceo_review", 0) < 1`: verhoog retry, roep `phase_4_qa_loop(ctx)` aan, daarna `phase_5_ceo_review(ctx)` opnieuw (max 1 retry).
   - Na 1 retry nog steeds NEEDS_REVISION → logger.warning, doorgaan (proceed anyway).

4. **Foutafhandeling**  
   Bij exception in CEO-call: log error, log "doorgaan", return (geen crash).

5. **Logging**  
   INFO: "CEO review: APPROVED", "CEO review: NEEDS_REVISION — retry 1/1 via phase_4", "doorgaan zonder gebruiker te lastigvallen". WARNING bij budget >80%.

---

## FASE 2 — Verify HandoffContext

Controleer dat HandoffContext alle benodigde velden heeft voor phase_5:

- `step_outputs` (dict) — gebruikt voor laatste output
- `execution_plan` (list) — volgorde voor reversed final content
- `strategic_brief` (dict) — objective voor CEO
- `retry_counts` (dict) — key "ceo_review" voor max 1 retry
- `token_used_total`, `token_budget` — is_over_budget(), budget_warning()
- `register_tokens()` — na CEO-call

Geen wijziging aan HandoffContext nodig indien bovenstaande aanwezig is.

---

## FASE 3 — Tests (6 scenario’s)

1. **CEO APPROVED**  
   Na phase_4 heeft step_outputs content; reviewer retourneert approved → phase_5 logt APPROVED en retourneert; phase_6/7 draaien.

2. **NEEDS_REVISION + retry → APPROVED**  
   Eerste CEO-call: NEEDS_REVISION; phase_4 opnieuw; tweede CEO-call: APPROVED → pipeline gaat door.

3. **NEEDS_REVISION na 1 retry → proceed**  
   Eerste: NEEDS_REVISION, retry via phase_4, tweede: nog NEEDS_REVISION → warning log, phase_5 retourneert, phase_6/7 draaien.

4. **Geen eindoutput**  
   step_outputs leeg of alleen gtm_analysis → phase_5 logt "geen eindoutput", retourneert zonder CEO-call.

5. **Over budget vóór CEO**  
   ctx.is_over_budget() True vóór CEO-call → BudgetExceededError, geen CEO-call.

6. **CEO-call exception**  
   _run_step_agent_with_timeout gooit → exception gelogd, "doorgaan" gelogd, return zonder crash.

---

## Constraint

- Geen signature-wijziging van `phase_5_ceo_review(ctx: HandoffContext)`.
- Bestaand _execute_step / _run_step_agent mechanisme hergebruiken (reviewer-rol).
