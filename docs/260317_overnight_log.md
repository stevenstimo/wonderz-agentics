# Overnight run — Crew Intelligent Fase 2–4
**Started:** 2026-03-17

## Fase 2 — NewCrewMember UI
- **Status:** Afgerond
- Backend: Framework create path in `POST /api/agents` (type, output_format, guardrails, model_config); altijd `is_active = false`. Nieuwe kolommen: tool_whitelist, knowledge_sources (gebruikt; tool_access_whitelist/knowledge_base_sources niet aangeraakt). `GET /api/agents/role-templates`, `POST /api/agents/{id}/activate`. Serialize agent row uitgebreid met framework-velden.
- Frontend: HiringHall uitgebreid met role dropdown (8 framework roles), type (worker/talent/orchestrator), output_format, guardrails (scope_limitation, escalation_rule), model_config (model, temperature). Role templates laden en toepassen bij rol-selectie. Framework payload wordt bij submit meegestuurd wanneer alle velden aanwezig zijn.
- VALID_TOOLS uitgebreid (backend + frontend) met framework tools.

## Fase 3 — Training Workflow
- **Status:** Afgerond
- `POST /api/agents/{agent_id}/train` bestond al. `_set_knowledge_source_status` en `_append_knowledge_processing` aangepast: gebruiken kolom `knowledge_sources` wanneer aanwezig (anders `knowledge_base_sources`). Training pipeline (scrape → chunk → embed → agent_knowledge) en `update_knowledge_sources` in training.py gebruikten al de juiste kolom wanneer die bestaat.

## Fase 4a — 49 hired_agents
- **Status:** Voorbereid (script klaar, niet uitgevoerd in deze run)
- `app/data/persona_roster.py`: alle 49 personas uit framework sectie 10 met (name, badge, score, development_priority, type, role_key).
- `scripts/seed_49_personas.py`: leest roster + role_templates, INSERT hired_agents met is_active = false, agent_id = agent:type:slug. Vereist `asyncpg` in de run-omgeving; zie blockers.

## Fase 4b — development_points
- **Status:** Voorbereid (in hetzelfde script als 4a)
- Script voegt per agent 3 development_points toe (issue_description = afgeleid van Development prioriteit). Gebruikt bestaande tabel `development_points` (point_id, agent_id, issue_description, impact, status).

## Fase 4d
- Niet uitgevoerd (gebruiker doet activatie zelf).
