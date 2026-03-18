# Crew Intelligent — Master Index
**Versie:** 1.0 | **Datum:** 18 maart 2026
**Autoritatieve spec:** docs/framework/260317_crew_intelligent_agent_framework.md

---

## Verplichte leesregel voor Cursor

Bij ELKE taak die raakt aan Crew Intelligent, Agent Lifecycle,
hired_agents, newbies, Training Workflow, Dashboard, navigatie
of persona batch:

1. Lees eerst dit document volledig
2. Bepaal welke fase actief is
3. Lees het bijbehorende fase-document
4. Volg de fasering exact

NOOIT een fase-document direct openen zonder eerst
dit master index document te lezen.

---

## Architectuurnotitie

De platformarchitectuur gebruikt een volledige C-suite structuur:
- CEO = strategisch monitorniveau (ziet geen individuele jobs)
- COO = operationeel orchestrator (intake, delegatie, pipeline)
- CFO / CHO / CDO = monitoring en rapportage aan CEO
- Talent = valideert Worker output
- Worker = voert taken uit

Alle orchestrator-agents in hired_agents zijn COO-niveau.
Zie framework sectie 1 voor volledige taakverdeling.

---

## Absolute blokkeerregels

```
REGEL 1 — Start NOOIT een nieuwe fase zonder bevestiging van de vorige.
REGEL 2 — Voer NOOIT tegelijkertijd migrations uit in twee sessies.
REGEL 3 — Activeer NOOIT agents (is_active = true) zonder expliciete opdracht.
REGEL 4 — Wijzig NOOIT tool_access_whitelist of knowledge_base_sources —
           gebruik alleen tool_whitelist en knowledge_sources.
REGEL 5 — Lees ALTIJD dit master index document voor je begint.
```

---

## Fase-documenten

| # | Bestand | Inhoud | Status |
|---|---------|--------|--------|
| 01 | `docs/cursor/01_phased_implementation.md` | Fase 1-4: DB migration, NewCrewMember UI, Training Workflow, Persona batch | ✅ Klaar |
| 02 | `docs/cursor/02_dashboard_newbies_navigation.md` | Fase 5-7: CEO Dashboard, Newbies lifecycle, Navigatie | ⬜ Volgende |
| 03 | `docs/cursor/03_...` | Volgende grote update | 🔒 Nog niet actief |

---

## Huidige status per fase

### Fase 1 — Database migration
**Status:** ✅ Klaar
Migration 041 gedraaid. Schema aligned met framework sectie 9.
Nieuwe kolommen: type, guardrails, output_format, model_config,
tool_whitelist, knowledge_sources, skills, readiness_score, persona_source.

### Fase 2 — NewCrewMember UI
**Status:** ✅ Klaar
Hiring Hall formulier met alle verplichte velden.
Role templates geladen bij rol-selectie.
is_active = false bij aanmaken altijd.

### Fase 3 — Training Workflow
**Status:** ✅ Klaar
POST /api/agents/{id}/train werkt.
BGE-M3 1024-dim embeddings correct opgeslagen.
Bewezen werkend: Forrest Gump 14 chunks geïndexeerd.

### Fase 4a — Persona batch INSERT
**Status:** ✅ Klaar
49 agents in hired_agents met is_active = false.
agent_id formaat: agent:type:naam-slug.

### Fase 4b — Development points
**Status:** ✅ Klaar
147 development points aangemaakt (3 per agent, status open, impact LOW).

### Fase 4c — Knowledge/training
**Status:** ⚡ Gestart
1/49 getraind (Forrest Gump, 14 chunks).
Overige agents nog zonder kennisbron.

### Fase 4d — Activeren
**Status:** ⚡ Gestart
1/49 actief (Forrest Gump, readiness 78).
Overige agents wachten op training en activatie.

### Fase 5 — Newbies lifecycle
**Status:** ⬜ Volgende
Zie: docs/cursor/02_dashboard_newbies_navigation.md Fase A

### Fase 6 — CEO Dashboard
**Status:** ⬜ Volgende
Zie: docs/cursor/02_dashboard_newbies_navigation.md Fase B

### Fase 7 — Navigatie herstructureren
**Status:** ⬜ Volgende
Zie: docs/cursor/02_dashboard_newbies_navigation.md Fase C

---

## Wanneer switch je naar een nieuw fase-document?

Maak een nieuw fase-document `docs/cursor/0X_naam.md` aan wanneer
één van deze triggers geldt:

1. Een fase-document wordt groter dan 150 regels
2. Je werkt met meer dan één Cursor sessie tegelijk
3. Een fase heeft sub-fasen die onafhankelijk kunnen lopen
4. Een tweede persoon gebruikt ook Cursor op dit project
5. Er zijn meer dan 5 fase-documenten actief

Voeg het nieuwe bestand toe aan de tabel hierboven en update
de status van het vorige fase-document naar ✅ Klaar.

---

## Verwijzingen naar het framework

| Onderwerp | Locatie |
|-----------|---------|
| Volledige architectuur | docs/framework/260317_crew_intelligent_agent_framework.md |
| Verplichte velden per agent | Framework sectie 4 |
| Rol-templates met defaults | Framework sectie 5 |
| Model-configuratie per rol | Framework sectie 6 |
| Guardrails | Framework sectie 7 |
| Volledig JSON datamodel | Framework sectie 8 |
| Database schema exact | Framework sectie 9 |
| 50 personas ingedeeld | Framework sectie 10 |
| Pre-flight checklist | Framework sectie 12.3 |

---

## Versiehistorie

| Versie | Datum | Wijzigingen |
|--------|-------|-------------|
| 1.0 | 18 maart 2026 | Master index aangemaakt. Optie B structuur geactiveerd. Status Fase 1-4d gedocumenteerd. |
