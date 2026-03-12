# Deployment Checklist — Crew Intelligent

## Database
- [ ] Migratie 063 gedraaid op productie (`app/migrations/063_inbound_emails_and_users.sql`)
- [ ] Migratie 064 gedraaid op productie (`app/migrations/064_jobs_intake_source.sql`)
- [ ] users tabel gevuld via backfill
- [ ] Supabase auth trigger actief
- [ ] Verificatie: `COUNT(auth.users) = COUNT(public.users)`

## Email Intake
- [ ] Gmail account aangemaakt (bijv. CEOAGENT@gmail.com)
- [ ] IMAP ingeschakeld via Gmail Settings
- [ ] 2-Step Verification aan
- [ ] App Password gegenereerd (Google Account → Security → App Passwords)
- [ ] GMAIL_ADDRESS in productie secrets gezet
- [ ] GMAIL_APP_PASSWORD in productie secrets gezet
- [ ] End-to-end test: email gestuurd → job aangemaakt in DB

## Technische schuld opgelost
- [ ] `app/migrations/__init__.py` aangemaakt
- [ ] Geen process actief op poort 8000 (backend draait op 8090; stop eventueel: `lsof -ti :8000 | xargs kill -9`)
- [ ] FRONTEND_URL in .env.example gedocumenteerd en in productie .env gezet indien CORS restrictie gewenst

## Verificatie queries na deployment
```sql
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM inbound_emails;
SELECT DISTINCT intake_source FROM jobs;
SELECT agent_id, is_active FROM hired_agents ORDER BY hired_at DESC NULLS LAST LIMIT 5;
```

## Supabase auth trigger (uitvoeren in Supabase Dashboard → SQL Editor)
Zie overnight prompt D4 voor de volledige SQL (sync_user_to_app, trigger op auth.users, backfill).
