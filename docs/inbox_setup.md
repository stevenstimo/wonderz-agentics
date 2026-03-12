# Inbox setup — users, seed, eerste test

## Stap 1 — Users in de database

De tabel `public.users` wordt gevuld via Supabase Auth (bij eerste login). Zonder accounts geen seed.

**Actie:** Supabase Dashboard → Authentication → Users → **Invite user** voor:

- stevenstimo@gmail.com  
- timo@newfoundterritory.nl  
- neil@newfoundterritory.nl  

Na de eerste login van elk account worden ze gesynchroniseerd naar `public.users`.

---

## Stap 2 — Seed opnieuw draaien

Zodra de accounts bestaan, in **Supabase SQL Editor** uitvoeren:

```sql
INSERT INTO inbox_allowed_senders (email, user_id, display_name)
SELECT 'stevenstimo@gmail.com', id::TEXT, 'Timo'
FROM users WHERE LOWER(email) = 'stevenstimo@gmail.com'
ON CONFLICT (email) DO NOTHING;

INSERT INTO inbox_allowed_senders (email, user_id, display_name)
SELECT 'timo@newfoundterritory.nl', id::TEXT, 'Timo (NFT)'
FROM users WHERE LOWER(email) = 'stevenstimo@gmail.com'
ON CONFLICT (email) DO NOTHING;

INSERT INTO inbox_allowed_senders (email, user_id, display_name)
SELECT 'neil@newfoundterritory.nl', id::TEXT, 'Neil'
FROM users WHERE LOWER(email) = 'neil@newfoundterritory.nl'
ON CONFLICT (email) DO NOTHING;
```

**Controle:**

```sql
SELECT * FROM inbox_allowed_senders;
-- Moet 3 rijen tonen
```

---

## Stap 3 — Eerste test

1. Stuur een e-mail naar het Gmail-adres van het systeem (vanaf een van de drie toegestane adressen).
2. Trigger handmatig één poll:

   **Let op:** `POST /api/email/poll` vereist:
   - **Auth:** Bearer token van een user met role `admin` of `super_admin`
   - **ENV:** Alleen beschikbaar als `ENV=development` (anders 403)

   Lokaal (met dev token):

   ```bash
   curl -X POST https://wonderz-agentic.exe.xyz/api/email/poll \
     -H "Authorization: Bearer <JWT_TOKEN>"
   ```

   Op de productieserver is het endpoint vaak uitgeschakeld (ENV ≠ development). Dan werkt de inbox alleen via de **IMAP-poller** als die draait.

3. Open in de browser **/inbox** — de e-mail zou in de lijst moeten staan en de CEO-chat zichtbaar zijn.

---

## Stap 4 — IMAP-poller (Shelley)

Laat bevestigen dat de **IMAP-poller** als persistent process draait na server restart. Zonder dat werkt de inbox alleen bij handmatig pollen (zie Stap 3).

Backend start de poller automatisch bij opstarten als `GMAIL_ADDRESS` en `GMAIL_APP_PASSWORD` in de omgeving staan (`app/main.py` lifespan).
