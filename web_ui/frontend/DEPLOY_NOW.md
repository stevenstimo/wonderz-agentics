# Deploy frontend (Job Center update)

**Build is klaar.** De map `dist/` bevat de nieuwste frontend met:
- Jobs overzicht (GET /api/jobs)
- New Job-formulier
- Job detailpagina (/jobs/:jobId)
- IntakeChatView met question_id-fix

**API-URL in build:** `VITE_API_URL=https://wonderz-agentic.exe.xyz` (staat in `.env`, wordt bij build ingebakken).

## Live zetten

- **Vercel (verbonden met Git):** push naar `main` triggert automatisch een deploy. Of lokaal: `cd web_ui/frontend && vercel --prod`.
- **Eigen server (nginx etc.):** kopieer de inhoud van `dist/` naar de document root van je domein (bijv. wonderz-agentic.exe.xyz).
- **Vercel env:** in Project Settings → Environment Variables moet `VITE_API_URL=https://wonderz-agentic.exe.xyz` staan (voor volgende builds).

Na deploy: https://wonderz-agentic.exe.xyz/job-center toont het jobs-overzicht en de knop "New Job".
