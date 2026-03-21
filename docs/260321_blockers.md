# 260321 — blockers (overnight resterende blokken)

## Blok F — console.log / console.warn (approve / handleApprove)

- `grep -rn "console\." web_ui/frontend/src/ --include="*.jsx" | grep -i "approve\|handleApprove"` → **geen treffers** (niets op één regel; geen `console.log`/`console.warn` in approve-paden in JSX).
- Extra check: alleen `console.log` in `Newbies.jsx` (niet approve-gerelateerd). **Geen verwijderingen nodig** voor deze scope.

## Blok H — Donna training (curl naar productie)

- Endpoint `POST /api/agents/{agent_id}/train` vereist **`require_super_admin`** (Bearer JWT).
- Curl **zonder** token zou **401** moeten geven; vanuit deze omgeving gaf `curl` **HTTP 000** (geen response — netwerk/proxy/sandbox), dus requests niet verifieerbaar hier.
- **Handmatig:** met super-admin token:
  `curl -X POST "https://wonderz-agentic.exe.xyz/api/agents/agent:c-suite:donna/train" -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"url":"..."}'`
