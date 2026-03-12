# Overnight Prompt A — Agent Lifecycle UI — Summary

## Wat is gedaan
- **A1** `app/routes/agents.py`: `system_prompt` wordt uit de lijst-response van `list_agents` gehaald (alleen nog in GET detail). Comment toegevoegd: `# spec: system_prompt alleen in detail-endpoint, niet in lijst`.
- **A2** `web_ui/frontend/src/AgentsOverview.jsx`: Badge "Gesuspendeerd" (rood) toegevoegd bij `agent.is_suspended`. Polling elke 30s via `setInterval(loadAgents, 30000)`. Link "Bewerken" wijst naar `/agents/{id}/edit`. DELETE-knop verwijderd; deactiveren gebeurt op de detailpagina.
- **A3** `web_ui/frontend/src/AgentDetail.jsx`: Modaltekst aangepast naar "Weet je zeker dat je **{naam}** wilt deactiveren?". Toggle + modal bestonden al (PATCH `is_active`).
- **A4** `web_ui/frontend/src/NewCrewMember.jsx`: Client-side `validate()` toegevoegd met inline foutmeldingen voor agent_name, role, goal, system_prompt. `field-error` class en weergave voor array/string errors.

## Aannames
- Geen wijzigingen aan bestaande endpoints behalve de lijst-serialisatie (A1).
- Agent ID-formaat blijft `agent:<role>:<slug>` (niet `agent:<role>-<slug>` uit de oorspronkelijke spec).
