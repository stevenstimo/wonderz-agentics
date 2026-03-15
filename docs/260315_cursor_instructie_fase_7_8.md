# Instructie voor Cursor — Fase 7–8 afronden (opruimen, README, commit-voorbereiding)

- **Fase 7 (E2E-test):** De gebruiker voert die zelf uit op https://wonderz-agentics.vercel.app. Cursor voert Fase 7 niet uit.
- **Scope:** Geen wijzigingen aan app-code of migrations — alleen `.env.example`, README en docs. Voorkomt scope creep.

---

## Fase 8 — Opruimen

### 1. Backup lokale DB (op de server)

**Eerst controleren of de lokale PostgreSQL nog bereikbaar is:**

```bash
pg_isready -h localhost -p 5432 -U wonderz
```

- **Als die niet reageert (exit non-zero):** backup overslaan en dat expliciet rapporteren.
- **Als wel bereikbaar:** volledige dump als backup uitvoeren (lokale DB niet verwijderen):

```bash
pg_dump "postgresql://wonderz:wonderz123@localhost:5432/wonderz" -f ~/wonderz_pre_migration_backup_$(date +%Y%m%d).sql
```

Rapporteer of de dump is gelukt (bestand aanwezig, geen fatale errors) of dat de backup is overgeslagen wegens niet-bereikbare lokale DB.

### 2. `.env.example` bijwerken

- De placeholder voor `DATABASE_URL` aanpassen naar het Supabase-voorbeeld (zonder echt wachtwoord), bijvoorbeeld:
  `DATABASE_URL=postgresql://postgres:[PASSWORD]@db.cqasccazioqjodctawzx.supabase.co:5432/postgres`
- Eventueel een korte comment dat de primaire DB Supabase is.

### 3. README bijwerken

- Een korte sectie **"Database"** toevoegen (of bestaande uitbreiden) met:
  - Applicatiedata draait op Supabase (project: cqasccazioqjodctawzx).
  - Lokale PostgreSQL wordt alleen nog als backup bewaard, niet meer als primaire DB.
  - BGE-M3-embeddings draaien lokaal op exe.dev en schrijven naar Supabase.

### 4. Commit voorbereiden (geen push)

- `git add` voor de gewijzigde bestanden (.env.example, README, en eventuele andere migratie-docs).
- **Niet** zelf `git commit` of `git push` uitvoeren; in plaats daarvan een voorstel voor commit message geven, bijvoorbeeld:
  `chore: post-migratie opruimen (Fase 8), README Database-sectie, .env.example Supabase`

---

De E2E-test op wonderz-agentics.vercel.app voert de gebruiker zelf uit; Cursor rondt alleen Fase 8 af en bereidt de commit voor.
