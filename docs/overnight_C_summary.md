# Overnight Prompt C — HR Manager — Summary

## Wat is gedaan
- **C1** `app/main.py`: In de lifespan na EmailPoller een `hr_scan_loop()` toegevoegd die elke 24 uur `HRManager(pool).scan_job_steps(since_days=7)` aanroept. Pool wordt per iteratie via `get_db()` opgehaald. Logregel: "HR scan voltooid" / "HR scan fout".
- **C2** `app/middleware/auth.py`: `require_admin_or_super_admin` toegevoegd (403 als role niet admin of super_admin). `app/routes/hr.py`: GET `/api/hr/report` gebruikt nu `require_admin_or_super_admin`. `app/routes/email.py`: importeert `require_admin_or_super_admin` uit auth in plaats van lokaal te definiëren.
- **C3** `web_ui/frontend/src/HRDashboard.jsx`: IMPACT_COLOR (rood/oranje/grijs) voor impact-weergave. Filters toegevoegd (Alle impact / Alle statussen) boven de Development Points-tabel. Modal voor Goedkeuren met optionele trainings-URL; `handleApprove` en `handleDismiss` aanroepen van POST `/api/hr/approve-training`. Sectie "Weekly Report" met knop "Refresh rapport" en GET `/api/hr/report`; per agent: naam, open points count, retry %, completed jobs. Bestaande tab "Training Requests" en Development Points-tabel behouden.

## Aannames
- HR scan loop draait direct bij startup (eerste run na 24u); geen vertraging tot eerste run gedocumenteerd.
- Report API retourneert `{ agents: { agent_id: { agent_name, performance: { retry_rate, jobs_touched_7d }, open_points_count } } }`; frontend gebruikt deze structuur.
