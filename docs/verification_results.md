# Crew Intelligent — Verificatie resultaten

Datum: 2025-03-12

## 1. Tests

### Subset (chunking + nexus + GTM)
```
pytest tests/test_training_chunking.py tests/test_nexus_pipeline.py tests/test_gtm_skills.py -v
```
**Resultaat:** 10 passed (3 chunking, 4 nexus, 3 GTM).

### Volledige suite
```
pytest tests/ -v --tb=short
```
**Resultaat:** 5 collection errors — ontbrekende modules in huidige omgeving (`anthropic`, `asyncpg`). Dit is een omgevingsissue (venv niet geactiveerd of andere interpreter); geen fout in de nieuwe code.

## 2. Backend

- `curl http://localhost:8090/health`: 404 (geen /health endpoint).
- `curl http://localhost:8090/api/agents`: 200 met `{"detail": "..."}` — endpoint vereist waarschijnlijk auth; inhoud niet gecontroleerd.
- Backend start: niet opnieuw gestart; bestaande run gebruikt.

## 3. Agents endpoint (GTM)

- Zonder token: response is `{"detail": "..."}` (geen lijst agents). GTM-agent aanwezigheid kon niet worden geverifieerd via curl.
- Na migratie 067 lokaal: `hired_agents` bevat `agent:gtm-specialist`; zodra backend met die DB draait, zou de agent in de Hiring Hall zichtbaar moeten zijn.

## 4. HR scan in logs

- `grep -i "hr scan" logs/app.log`: niet uitgevoerd (geen logs/app.log in repo of pad niet aanwezig). Optioneel handmatig controleren.

## 5. Training endpoint

- `POST /api/agents/agent:gtm-specialist/train` met `{"url": "http://test"}`:
  - Response: `401 Unauthorized: Bearer token required`. Geen 400 voor invalid URL omdat auth eerst wordt gecontroleerd.
  - Met geldige auth zou 400 voor http:// verwacht worden (alleen https).

## 6. Conclusie

- NEXUS pipeline-, GTM- en chunking-tests slagen.
- Volledige suite vereist venv met alle dependencies.
- API-checks vereisen geautoriseerde requests of lokale DB-check op `hired_agents`.
