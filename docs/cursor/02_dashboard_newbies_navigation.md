# CURSOR — CEO Dashboard + Newbies Lifecycle + Navigatie
**Datum:** 18 maart 2026
**Refs:** docs/framework/260317_crew_intelligent_agent_framework.md

---

## Context

Lees eerst:
- `docs/framework/260317_crew_intelligent_agent_framework.md` (architectuur, C-suite structuur)
- `docs/cursor/00_master_index.md` (fasering en status)

Dit zijn drie samenhangende wijzigingen die in één Cursor sessie 
worden uitgevoerd. Werk fase voor fase. Stop na elke fase en 
rapporteer voordat je doorgaat.

---

## Wat je NIET doet

- Geen migrations op `hired_agents` of `agent_knowledge`
- Geen wijzigingen aan de job flow of NEXUS pipeline
- Geen wijzigingen aan bestaande agent endpoints behalve wat hieronder staat
- Geen nieuwe dependencies installeren zonder te melden
- Nooit meerdere fasen tegelijk uitvoeren

---

## Fase A — Newbies lifecycle (backend)

### A.1 Wat het probleem is

De `newbies` tabel bestaat en is leeg. De 49 personas zitten in 
`hired_agents` met `is_active = false`. Dit is architectureel incorrect.

Een NewBie is een kandidaat in opleiding — nog niet operationeel.
Een Agent is operationeel en staat in `hired_agents`.

De juiste lifecycle is:
