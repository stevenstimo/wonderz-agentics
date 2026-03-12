# Overnight Prompt D — Productie Deployment — Summary

## Wat is gedaan
- **D1** `app/migrations/__init__.py` aangemaakt (lege package) om `ModuleNotFoundError app.migrations` te voorkomen.
- **D2** Port 8000: Geen wijzigingen in code; in `docs/deployment_checklist.md` opgenomen: controleer dat geen proces op 8000 draait; backend gebruikt 8090. Eventueel: `lsof -ti :8000 | xargs kill -9`. (web_ui/start.sh en web_ui/backend gebruiken nog 8000; hoofdbackend is app/main.py op 8090.)
- **D5** `.env.example`: `FRONTEND_URL=` toegevoegd met comment voor CORS/productie.
- **D6** `docs/deployment_checklist.md` aangemaakt met secties Database, Email Intake, Technische schuld, verificatie-queries en verwijzing naar Supabase-trigger (D4).

## Niet uitgevoerd (handmatig / productie)
- **D3** Migraties 063/064 op productie-DB: uit te voeren door operator; bij fout documenteren in `docs/overnight_D_blockers.md`.
- **D4** Supabase auth trigger: SQL in Supabase Dashboard → SQL Editor uitvoeren (niet via app-connectie).

## Aannames
- CORS in `app/main.py` blijft een vaste lijst (localhost + wonderz-agentic.exe.xyz); FRONTEND_URL kan later worden gebruikt om dynamisch te restricten.
- DEFAULT_MODEL is al `claude-sonnet-4-5-20251001`; geen D7-wijziging.
