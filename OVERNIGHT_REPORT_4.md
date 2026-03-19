# Overnight Report 4 — 2026-03-19

## Fix 1: Gmail credentials check
Status: ❌
Bevindingen:
- `override.conf` bevat geen zichtbare `gmail`, `email_poller` of `inbox` env verwijzingen (grep gaf geen matches).
- `.env.vm` kon niet bevestigd worden met de gevraagde Gmail keys (`GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`).
- EmailPoller code is aanwezig in:
  - `app/services/email_poller.py`
  - `app/routes/email.py`
Wat nog nodig is:
- Voeg de 3 Gmail env vars toe aan runtime config voor backend service.
- Herstart service na toevoegen en valideer poll-cycle endpoint.
Commit: Geen (alleen check/documentatie).

## Fix 2: Agent count reconciliatie
Status: ❌
Agents aanwezig: Niet te bepalen in deze sessie (SQL query op Supabase niet uitvoerbaar zonder geauthenticeerde DB toegang).
Ontbrekende agents:
- Niet definitief vast te stellen zonder resultaten van:
  - `SELECT role, category, is_active, COUNT(*) ...`
  - `SELECT agent_id, name, role, category, is_active ...`
- Presets wel gevonden in code:
  - `app/data/agent_presets.py` (`AGENT_PRESETS`)
  - gebruikt door `app/routes/agents.py`
Wat nog nodig is:
- Draai de twee SQL queries in Supabase SQL editor en vergelijk met `AGENT_PRESETS`.
Commit: Geen (alleen check/documentatie).

## Fix 3: model_config JSONB
Status: ❌ (gedeeltelijk uitgevoerd, DB-verificatie geblokkeerd)
Wat gedaan:
- `app/migrations/047_agent_model_config.sql` aangemaakt met `ALTER TABLE ... ADD COLUMN IF NOT EXISTS model_config JSONB DEFAULT ...`.
- `app/routes/agents.py` bijgewerkt:
  - `AgentResponse` bevat nu `model_config: Optional[dict] = None`
  - `AgentUpdate` bevat nu `model_config: Optional[dict] = None`
  - `update_agent` verwerkt `model_config` als JSON-field en retourneert `model_config` in de `RETURNING` clause.
Wat nog nodig is:
- SQL uitvoeren/verifiëren in Supabase:
  - kolomcheck in `information_schema.columns`
  - (indien nodig) `ALTER TABLE` runnen
  - `SELECT agent_id, name, model_config FROM hired_agents LIMIT 3;`
Commit: `feat: add model_config JSONB per agent`

## Fix 4: Polling cleanup
Status: 🔄
Wat gedaan: In uitvoering.
Commit: ...

## Fix 5: Shopify + WordPress adapters
Status: 🔄
Wat gedaan: In uitvoering.
Benodigde env vars: ...
Commit: ...

## Samenvatting
- 0 van 5 fixes volledig werkend
- Openstaande items voor volgende sessie: Fix 1 (keys), Fix 2 (DB SQL), overige in uitvoering
