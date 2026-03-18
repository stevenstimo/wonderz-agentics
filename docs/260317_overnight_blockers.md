# Overnight blockers — Crew Intelligent
**Run:** 2026-03-17

Documenteer hier problemen die een subfase blokkeren. Ga door met de volgende subfase; stop niet op een blocker.

---

## Fase 4a/4b — Seed script

- **Script:** `scripts/seed_49_personas.py` (49 hired_agents + development_points) is klaar.
- **Blocker:** Script vereist `asyncpg` in de Python-omgeving. In de Cursor-run was asyncpg niet geïnstalleerd in de gebruikte interpreter.
- **Oplossing:** Run het script lokaal in de backend-venv waar `pip install asyncpg` al gedaan is: `python scripts/seed_49_personas.py`. Of start de backend en seed via API (POST /api/agents per persona met framework payload).
